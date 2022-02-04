import re
import aiohttp
import time
import urllib.parse

analysis_stat = {}  # analysis_stat: video_url(vurl)


async def bili_keyword(group_id, text):
    try:
        # 提取url
        url, page = await extract(text)
        # 如果是小程序就去搜索标题
        if not url:
            pattern = re.compile(r'"desc":".*?"')
            desc = re.findall(pattern, text)
            i = 0
            while i < len(desc):
                title_dict = "{" + desc[i] + "}"
                title = eval(title_dict)
                i += 1
                if title["desc"] == "哔哩哔哩":
                    continue
                vurl = await search_bili_by_title(title["desc"])
                if vurl:
                    url = await extract(vurl)
                    break

        # 获取视频详细信息
        if "bangumi" in url:
            msg, vurl = await bangumi_detail(url)
        elif "live.bilibili.com" in url:
            msg, vurl = await live_detail(url)
        elif "article" in url:
            msg, vurl = await article_detail(url)
        else:
            msg, vurl = await video_detail(url, page)

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
    b23 = re.compile(r"b23.tv/(\w+)|(bili(22|23|33|2233).cn)/(\w+)", re.I).search(
        text.replace("\\", "")
    )
    url = f"https://{b23[0]}"
    async with aiohttp.request(
        "GET", url, timeout=aiohttp.client.ClientTimeout(10)
    ) as resp:
        r = str(resp.url)
    return r


async def extract(text: str):
    try:
        page = re.compile(r"\?p=\d+").search(text)
        aid = re.compile(r"av\d+", re.I).search(text)
        bvid = re.compile(r"BV([a-zA-Z0-9]{10})+", re.I).search(text)
        epid = re.compile(r"ep\d+", re.I).search(text)
        ssid = re.compile(r"ss\d+", re.I).search(text)
        mdid = re.compile(r"md\d+", re.I).search(text)
        room_id = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).search(text)
        cvid = re.compile(r"(cv|/read/(mobile|native)(/|\?id=))(\d+)", re.I).search(
            text
        )
        if bvid:
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid[0]}"
        elif aid:
            url = f"https://api.bilibili.com/x/web-interface/view?aid={aid[0][2:]}"
        elif epid:
            url = (
                f"https://bangumi.bilibili.com/view/web_api/season?ep_id={epid[0][2:]}"
            )
        elif ssid:
            url = f"https://bangumi.bilibili.com/view/web_api/season?season_id={ssid[0][2:]}"
        elif mdid:
            url = f"https://bangumi.bilibili.com/view/web_api/season?media_id={mdid[0][2:]}"
        elif room_id:
            url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={room_id[2]}"
        elif cvid:
            url = f"https://api.bilibili.com/x/article/viewinfo?id={cvid[4]}&mobi_app=pc&from=web"
        return url, page
    except:
        return None, None


async def search_bili_by_title(title: str):
    search_url = f"http://api.bilibili.com/x/web-interface/search/all/v2?keyword={urllib.parse.quote(title)}"

    async with aiohttp.request(
        "GET", search_url, timeout=aiohttp.client.ClientTimeout(10)
    ) as resp:
        r = await resp.json()

    result = r["data"]["result"]
    for i in result:
        if i.get("result_type") != "video":
            continue
        # 只返回第一个结果
        url = i["data"][0].get("arcurl")
        return url


async def video_detail(url, page):
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = await resp.json()
            res = res["data"]
        vurl = f"https://www.bilibili.com/video/av{res['aid']}"
        title = f"\n标题：{res['title']}\n"
        if page:
            page = page[0]
            p = int(page[len("?p=") :])
            if p <= len(res["pages"]):
                vurl += page + ""
                part = res['pages'][p-1]['part']
                if part != res["title"]:
                    title += f"小标题：{part}\n"
        tname = f"类型：{res['tname']} | UP：{res['owner']['name']}\n"
        stat = f"播放：{res['stat']['view']} | 弹幕：{res['stat']['danmaku']} | 收藏：{res['stat']['favorite']}\n"
        stat += f"点赞：{res['stat']['like']} | 硬币：{res['stat']['coin']} | 评论：{res['stat']['reply']}\n"
        desc = f"简介：{res['desc']}"
        desc_list = desc.split("\n")
        desc = ""
        for i in desc_list:
            if i:
                desc += i + "\n"
        desc_list = desc.split("\n")
        if len(desc_list) > 4:
            desc = desc_list[0] + "\n" + desc_list[1] + "\n" + desc_list[2] + "……"
        msg = str(vurl) + str(title) + str(tname) + str(stat) + str(desc)
        return msg, vurl
    except Exception as e:
        msg = "视频解析出错--Error: {}".format(type(e))
        return msg, None


async def bangumi_detail(url):
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = await resp.json()
            res = res["result"]
        title = f"番剧：{res['title']}\n"
        desc = f"{res['newest_ep']['desc']}\n"
        index_title = ""
        style = ""
        for i in res["style"]:
            style += i + ","
        style = f"类型：{style[:-1]}\n"
        evaluate = f"简介：{res['evaluate']}\n"
        if "season_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/play/ss{res['season_id']}\n"
        elif "media_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/media/md{res['media_id']}\n"
        else:
            epid = re.compile(r"ep_id=\d+").search(url)[0][len("ep_id=") :]
            for i in res["episodes"]:
                if str(i["ep_id"]) == epid:
                    index_title = f"标题：{i['index_title']}\n"
                    break
            vurl = f"https://www.bilibili.com/bangumi/play/ep{epid}\n"
        msg = (
            str(vurl)
            + str(title)
            + str(index_title)
            + str(desc)
            + str(style)
            + str(evaluate)
        )
        return msg, vurl
    except Exception as e:
        msg = "番剧解析出错--Error: {}".format(type(e))
        msg += f"\n{url}"
        return msg, None


async def live_detail(url):
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = await resp.json()
        if res["code"] == -400 or res["code"] == 19002000:
            msg = "直播间不存在"
            return msg, None
        uname = res["data"]["anchor_info"]["base_info"]["uname"]
        room_id = res["data"]["room_info"]["room_id"]
        title = res["data"]["room_info"]["title"]
        live_status = res["data"]["room_info"]["live_status"]
        lock_status = res["data"]["room_info"]["lock_status"]
        parent_area_name = res["data"]["room_info"]["parent_area_name"]
        area_name = res["data"]["room_info"]["area_name"]
        online = res["data"]["room_info"]["online"]
        tags = res["data"]["room_info"]["tags"]
        vurl = f"https://live.bilibili.com/{room_id}\n"
        if lock_status:
            lock_time = res["data"]["room_info"]["lock_time"]
            lock_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(lock_time))
            title = f"[已封禁]直播间封禁至：{lock_time}\n"
        elif live_status == 1:
            title = f"[直播中]标题：{title}\n"
        elif live_status == 2:
            title = f"[轮播中]标题：{title}\n"
        else:
            title = f"[未开播]标题：{title}\n"
        up = f"主播：{uname} 当前分区：{parent_area_name}-{area_name} 人气上一次刷新值：{online}\n"
        if tags:
            tags = f"标签：{tags}\n"
        if live_status:
            player = f"独立播放器：https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={room_id}"
        else:
            player = ""
        msg = str(vurl) + str(title) + str(up) + str(tags) + str(player)
        return msg, vurl
    except Exception as e:
        msg = "直播间解析出错--Error: {}".format(type(e))
        return msg, None


async def article_detail(url):
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = await resp.json()
            res = res["data"]
        cvid = re.compile(r"id=(\d+)").search(url).group(1)
        vurl = f"https://www.bilibili.com/read/cv{cvid}\n"
        title = f"标题：{res['title']}\n"
        up = f"作者：{res['author_name']} (https://space.bilibili.com/{res['mid']})\n"
        view = f"阅读数：{res['stats']['view']} "
        favorite = f"收藏数：{res['stats']['favorite']} "
        coin = f"硬币数：{res['stats']['coin']}"
        share = f"分享数：{res['stats']['share']} "
        like = f"点赞数：{res['stats']['like']} "
        dislike = f"不喜欢数：{res['stats']['dislike']}"
        desc = view + favorite + coin + "\n" + share + like + dislike
        msg = str(vurl) + str(title) + str(up) + str(desc)
        return msg, vurl
    except Exception as e:
        msg = "专栏解析出错--Error: {}".format(type(e))
        return msg, None
