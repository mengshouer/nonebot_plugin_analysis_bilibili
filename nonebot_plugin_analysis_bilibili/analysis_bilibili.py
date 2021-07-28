import re
import json
import aiohttp
import asyncio
import lxml.html
import urllib.parse
from datetime import datetime

analysis_stat = {}   # analysis_stat: video_url(vurl)

async def bili_keyword(group_id, text):
    try:
        # 提取url
        url = await extract(text)
        # 如果是小程序就去搜索标题
        if not url:
            pattern = re.compile(r'"desc":".*?"')
            desc = re.findall(pattern,text)
            i = 0
            while i < len(desc):
                title_dict = "{"+desc[i]+"}"
                title = eval(title_dict)
                vurl = await search_bili_by_title(title['desc'])
                if vurl:
                    url = await extract(vurl)
                    break
                i += 1
        
        # 获取视频详细信息
        if "www.bilibili.com/bangumi/play/" in url:
            msg = await bangumi_detail(url)
            vurl = url
        elif "live.bilibili.com" in url:
            msg,vurl = await live_detail(url)
        elif "article" in url:
            msg,vurl = await article_detail(url)
        else:
            msg,vurl = await video_detail(url)
        
        # 避免多个机器人解析重复推送
        if group_id not in analysis_stat:
            analysis_stat[group_id] = vurl
            last_vurl = ""
        else:
            last_vurl = analysis_stat[group_id]
            analysis_stat[group_id] = vurl
        if last_vurl == vurl:
            return
    except Exception as e:
        msg = "Error: {}".format(type(e))
    return msg

async def b23_extract(text):
    b23 = re.compile(r'b23.tv\\/(\w+)').search(text)
    if not b23:
        b23 = re.compile(r'b23.tv/(\w+)').search(text)
    url = f'https://b23.tv/{b23[1]}'
    async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
        r = str(resp.url)
    return r

async def extract(text:str):
    try:
        aid = re.compile(r'(av|AV)\d+').search(text)
        bvid = re.compile(r'(BV|bv)([a-zA-Z0-9])+').search(text)
        epid = re.compile(r'ep\d+').search(text)
        ssid = re.compile(r'ss\d+').search(text)
        room_id = re.compile(r"live.bilibili.com/(\d+)").search(text)
        cvid = re.compile(r'(cv|CV)\d+').search(text)
        if bvid:
            url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid[0]}'
        elif aid:
            url = f'https://api.bilibili.com/x/web-interface/view?aid={aid[0][2:]}'
        elif epid:
            url = f'https://www.bilibili.com/bangumi/play/{epid[0]}'
        elif ssid:
            url = f'https://www.bilibili.com/bangumi/play/{ssid[0]}'
        elif room_id:
            url = f'https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={room_id.group(1)}'
        elif cvid:
            url = f"https://api.bilibili.com/x/article/viewinfo?id={cvid[0][2:]}&mobi_app=pc&from=web"
        return url
    except:
        return None

async def search_bili_by_title(title: str):
    brackets_pattern = re.compile(r'[()\[\]{}（）【】]')
    title_without_brackets = brackets_pattern.sub(' ', title).strip()
    search_url = f'https://search.bilibili.com/video?keyword={urllib.parse.quote(title_without_brackets)}'

    try:
        async with aiohttp.request('GET', search_url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            text = await resp.text(encoding='utf8')
            content: lxml.html.HtmlElement = lxml.html.fromstring(text)
    except asyncio.TimeoutError:
        return None

    for video in content.xpath('//li[@class="video-item matrix"]/a[@class="img-anchor"]'):
        if title == ''.join(video.xpath('./attribute::title')):
            url = ''.join(video.xpath('./attribute::href'))
            break
    else:
        url = None
    return url

async def video_detail(url):
    try:
        async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
            res = res['data']
        vurl = f"URL：https://www.bilibili.com/video/av{res['aid']}\n"
        title = f"标题：{res['title']}\n"
        up = f"UP主：{res['owner']['name']} (https://space.bilibili.com/{res['owner']['mid']})\n"
        desc = f"简介：{res['desc']}"
        msg = str(vurl)+str(title)+str(up)+str(desc)
        return msg, vurl
    except Exception as e:
        msg = "视频解析出错--Error: {}".format(type(e))
        return msg, None

async def bangumi_detail(url):
    try:
        async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.text()
        content: lxml.html.HtmlElement = lxml.html.fromstring(res)
        name = content.xpath('//*[@id="media_module"]/div/a/text()')
        detail = content.xpath('//*[@id="media_module"]/div/div[2]/a[1]/text()')
        pubinfo = content.xpath('//*[@id="media_module"]/div/div[2]/span/text()')
        description = content.xpath('//*[@id="media_module"]/div/div[3]/a/span[1]/text()')
        msg = f"URL：{url}\n标题：{name[0]}\n类型：{detail[0]}  {pubinfo[0]}\n简介：{description[0]}"
        return msg
    except Exception as e:
        msg = "番剧解析出错--Error: {}".format(type(e))
        msg += f'\n{url}'
        return msg

async def live_detail(url):
    try:
        async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
        if res['code'] == -400 or res['code'] == 19002000:
            msg = "直播间不存在"
            return msg, None
        uname = res['data']['anchor_info']['base_info']['uname']
        room_id = res['data']['room_info']['room_id']
        title = res['data']['room_info']['title']
        live_status = res['data']['room_info']['live_status']
        lock_status = res['data']['room_info']['lock_status']
        parent_area_name = res['data']['room_info']['parent_area_name']
        area_name = res['data']['room_info']['area_name']
        online = res['data']['room_info']['online']
        tags = res['data']['room_info']['tags']
        vurl = f"URL：https://live.bilibili.com/{room_id}\n"
        if lock_status:
            lock_time = res['data']['room_info']['lock_time']
            lock_time = datetime.fromtimestamp(lock_time).strftime("%Y-%m-%d %H:%M:%S")
            title = f"(已封禁)直播间封禁至：{lock_time}\n"
        elif live_status:
            title = f"(直播中)标题：{title}\n"
        else:
            title = f"(未开播)标题：{title}\n"
        up = f"主播：{uname} 当前分区：{parent_area_name}-{area_name} 人气上一次刷新值：{online}\n"
        tags = f"标签：{tags}"
        msg = str(vurl)+str(title)+str(up)+str(tags)
        return msg, vurl
    except Exception as e:
        msg = "直播间解析出错--Error: {}".format(type(e))
        return msg, None

async def article_detail(url):
    try:
        async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
            res = res['data']
        cvid = re.compile(r'id=(\d+)').search(url).group(1)
        vurl = f"URL：https://www.bilibili.com/read/cv{cvid}\n"
        title = f"标题：{res['title']}\n"
        up = f"作者：{res['author_name']} (https://space.bilibili.com/{res['mid']})\n"
        view = f"阅读数：{res['stats']['view']} "
        favorite = f"收藏数：{res['stats']['favorite']} "
        coin = f"硬币数：{res['stats']['coin']}"
        share = f"分享数：{res['stats']['share']} "
        like = f"点赞数：{res['stats']['like']} "
        dislike = f"不喜欢数：{res['stats']['dislike']}"
        desc = view + favorite + coin + '\n' + share + like + dislike
        msg = str(vurl)+str(title)+str(up)+str(desc)
        return msg, vurl
    except Exception as e:
        msg = "专栏解析出错--Error: {}".format(type(e))
        return msg, None