#!/usr/bin/env python3

import requests, json, re, sys, time, execjs, hashlib
#from urllib import request

source_file = r'/root/Channel.json'
target_file = r'/var/www/tv/tvjson/shenjunfeng.json'
log_file = r'/var/log/tv.log'
num = 1

def load_tvch():
    """清空日志并读取源频道JSON文件"""
    #清空日志文件
    with open(log_file, 'wt', encoding='utf-8') as f:
        f.write(r'')
    #读取源文件
    with open(source_file, 'rt', encoding='utf-8') as f:
        return json.load(f)

def save_tvch():
    """删除未开播频道"""
    for key in reversed(channel_data['live']):
        if 'num' not in key:
            room_id = key['roomid']
            info = key['info']
            channel_data['live'].remove(key)
            sys.stdout.flush()
            run_time = time.strftime('%H:%M:%S', time.localtime())
            print('%s  正在删除 %s 频道---------->  %s' % (run_time, info, room_id))
    """保存频道JSON文件"""
    with open(target_file, 'wt', encoding='utf-8') as f:
        json.dump(channel_data, f, ensure_ascii=False, indent=2)
    print("成功写入频道文件=======================>  %s" % (target_file))

def tv_update(live_url, tv_net, name, key):
    """更新频道视频链接"""
    global num
    channel_data['live'][key]['num'] = str(num).zfill(3)
    num = num + 1
    #删除目标文件不需要的字段
    del channel_data['live'][key]['info']
    del channel_data['live'][key]['roomid']
    #更新频道链接
    channel_data['live'][key]['urllist'] = live_url
    #刷新时间
    sys.stdout.flush()
    run_time = time.strftime('%H:%M:%S', time.localtime())
    print('%s  %s频道成功更新========>   %s' % (run_time, tv_net, name))

def tv_error(tv_net, room_id):
    """更新频道错误码"""
    sys.stdout.flush()
    run_time = time.strftime('%H:%M:%S', time.localtime())
    print('%s  %s频道等待删除-------->   %s' % (run_time, tv_net, room_id))

def huya_get_url(room_id, tv_net, name, key):
    source_url = 'https://m.huya.com/{}'.format(room_id)
    fake_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Mobile Safari/537.36'
    }
    source_html = requests.get(url=source_url, headers=fake_headers).text
    live_url = re.findall(r"hasvedio: '([\s\S]*.m3u8)", source_html, re.I)
    if live_url:
        live_url = live_url[0]
        tv_update(live_url, tv_net, name, key)
    else:
        tv_error(tv_net, room_id)

def bili_get_url(room_id, tv_net, name, key):
    time.sleep(0.5)
    source_url = 'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={}'.format(room_id)
    #source_url = 'https://api.live.bilibili.com/room/v1/Room/room_init?id={}'.format(room_id)
    source_json = requests.get(url=source_url).json()
    data = source_json.get('data', 0)
    if data:
        live_status = data.get('live_status', 0)
        room_id = data.get('room_id', 0)
        if live_status:
            time.sleep(0.5)
            source_url = 'https://api.live.bilibili.com/room/v1/Room/playUrl?cid={}&platform=h5&otype=json&quality=4'.format(room_id)
            source_json = requests.get(url=source_url).json()
            durl = source_json.get('data').get('durl', 0)
            if durl:
                result = durl[0].get('url')
                pattern = r'.com/live-[\S]*/([\s\S]*.m3u8)'
                pattern_result = re.findall(pattern, result, re.I)[0]
                live_url = 'http://cn-hbxy-cmcc-live-01.live-play.acgvideo.com/live-bvc/' + pattern_result
                tv_update(live_url, tv_net, name, key)
            else:
                tv_error(tv_net, room_id)
        else:
            tv_error(tv_net, room_id)
    else:
        tv_error(tv_net, room_id)


def douyu_get_url(room_id, tv_net, name, key):
    tt0 = str(int(time.time()))
    tt1 = str(int((time.time() * 1000)))
    today = time.strftime('%Y%m%d', time.localtime())
    source_url = 'https://playweb.douyucdn.cn/lapi/live/hlsH5Preview/' + room_id
    post_data = {'rid': room_id, 'did': '10000000000000000000000000001501'}
    auth = hashlib.md5((room_id + tt1).encode('utf-8')).hexdigest()
    fake_headers = {'content-type': 'application/x-www-form-urlencoded', 'rid': room_id, 'time': tt1, 'auth': auth}
    try:
        source_json = requests.post(url=source_url, headers=fake_headers, data=post_data).json()
    except Exception:
        tv_error(tv_net, room_id)
        return
    #source_json = source_json.json()
    pre_url = ''
    if source_json.get('error') == 0:
        real_url = (source_json.get('data')).get('rtmp_live')
        if 'mix=1' in real_url:
            pre_url = 'PKing'
        else:
            pattern1 = r'^[0-9a-zA-Z]*'
            pre_url = re.search(pattern1, real_url, re.I).group()
    elif source_json.get('error') == 103:
        tv_error(tv_net, room_id)
        return
    if pre_url:
        live_url = 'http://tx2play1.douyucdn.cn/live/' + pre_url + '.flv?uuid='
        tv_update(live_url, tv_net, name, key)
        return
    else:
        room_url = 'https://m.douyu.com/' + room_id
        source_json = requests.get(url=room_url)
        pattern_real_rid = r'"rid":(\d{1,7})'
        #获取roomid（有一些主播的房间ID是viprid，也就是表面上的rid，例如周淑怡的22222，实际上则是290935）
        real_rid = re.findall(pattern_real_rid, source_json.text, re.I)
        if real_rid:
            real_rid = real_rid[0]
        else:
            real_rid = room_id
        if real_rid != room_id:
            room_id = str(real_rid)
            room_url = 'https://m.douyu.com/' + real_rid
            source_json = requests.get(url=room_url)
        homejs = ''
        pattern = r'(function ub9.*)[\s\S](var.*)'
        result = re.findall(pattern, source_json.text, re.I)
        str1 = re.sub(r'eval.*;}', 'strc;}', result[0][0])
        homejs = str1 + result[0][1] #获得第一段JS代码
        docjs = execjs.compile(homejs) #执行第一段JS代码
        res2 = docjs.call('ub98484234') #调用JS代码里的函数“ub98484234”
        str3 = re.sub(r'\(function[\s\S]*toString\(\)', '\'', res2)
        md5rb = hashlib.md5((room_id + '10000000000000000000000000001501' + tt0 + '2501' + today).encode('utf-8')).hexdigest()
        str4 = 'function get_sign(){var rb=\'' + md5rb + str3
        str5 = re.sub(r'return rt;}[\s\S]*','return re;};', str4) 
        str6 = re.sub(r'"v=.*&sign="\+', '', str5) #获得第二段JS代码
        docjs1 = execjs.compile(str6)  #执行第二段JS代码
        sign = docjs1.call(
            'get_sign', room_id, '10000000000000000000000000001501', tt0) #调用JS里的函数“get_sign”以获取sign值
        source_url = 'https://m.douyu.com/api/room/ratestream'
        post_data = {'v': '2501' + today, 'did': '10000000000000000000000000001501', 'tt': tt0, 'sign': sign, 'ver': '219032101', 'rid': room_id, 'rate': '-1'}
        fake_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Mobile Safari/537.36'
        }
        try:
            source_json = requests.post(url=source_url, headers=fake_headers, data=post_data).json()
        except Exception:
            tv_error(tv_net, room_id)
            return
        if source_json.get('code') == 0:
            real_url = (source_json.get('data')).get('url')
            if 'mix=1' in real_url:
                result1 = 'PKing'
            else:
                pattern1 = r'live/(\d{1,8}[0-9a-zA-Z]+)_?[\d]{0,4}/playlist'
                result1 = re.findall(pattern1, real_url, re.I)[0]
        else:
            result1 = 0
        if result1 != 0:
            live_url = "http://tx2play1.douyucdn.cn/live/" + result1 + ".flv?uuid="
            tv_update(live_url, tv_net, name, key)
        else:
            tv_error(tv_net, room_id)

def dianshi_get_url(room_id, tv_net, name, key):
    live_url = channel_data['live'][key]['urllist']
    tv_update(live_url, tv_net, name, key)

if __name__ == '__main__':
    channel_data = load_tvch()
    for key, data in enumerate(channel_data['live']):
        room_id = data['roomid']
        tv_net = data['info']
        name = data['name']
        if tv_net == '虎牙TV':
            huya_get_url(room_id, tv_net, name, key)
        elif tv_net == '哔哩TV':
            bili_get_url(room_id, tv_net, name, key)
        elif tv_net == '斗鱼TV':
            douyu_get_url(room_id, tv_net, name, key)
        elif tv_net == '电视多':
            dianshi_get_url(room_id, tv_net, name, key)
    save_tvch()



"""
room_id = '5650265'
tv_net = '哔哩TV'
name = '哔哩TV'
key = 6
channel_data = load_tvch()
bili_get_url(room_id, tv_net, name, key)
    #time.sleep(0.5)
    
    source_json = source_json.get('data', 0)
    if source_json:
        live_status = source_json.get('live_status', 0)
        room_id = source_json.get('room_id', 0)
        if live_status:
            live_url = 'http://192.168.192.168/bilibili.php?chs=h50&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=h51&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=h52&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=h53&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=web0&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=web1&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=web2&channel=' + str(room_id)
            live_url += '#http://192.168.192.168/bilibili.php?chs=web3&channel=' + str(room_id)
            tv_update(live_url, tv_net, name, key)
        else:
            tv_error(tv_net, room_id)
    else:
        tv_error(tv_net, room_id)


def bili_get_url(room_id, tv_net, name, key):
    time.sleep(0.5)
    source_url = 'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={}'.format(room_id)
    #source_url = 'https://api.live.bilibili.com/room/v1/Room/room_init?id={}'.format(room_id)
    source_json = requests.get(url=source_url).json()
    data = source_json.get('data', 0)
    if data:
        live_status = data.get('live_status', 0)
        room_id = data.get('room_id', 0)
        if live_status:
            time.sleep(0.5)
            source_url = 'https://api.live.bilibili.com/room/v1/Room/playUrl?cid={}&platform=h5&otype=json&quality=4'.format(room_id)
            source_json = requests.get(url=source_url).json()
            durl = source_json.get('data').get('durl', 0)
            if durl:
                result = durl[0].get('url')
                pattern = r'.com/live-[\S]*/([\s\S]*.m3u8)'
                pattern_result = re.findall(pattern, result, re.I)[0]
                live_url = 'http://cn-hbxy-cmcc-live-01.live-play.acgvideo.com/live-bvc/' + pattern_result
                tv_update(live_url, tv_net, name, key)
            else:
                tv_error(tv_net, room_id)
        else:
            tv_error(tv_net, room_id)
    else:
        tv_error(tv_net, room_id)


"""
