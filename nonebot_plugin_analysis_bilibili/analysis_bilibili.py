import re
import urllib.parse
import json
from time import localtime, strftime
from typing import Dict, Optional, Tuple, Union

import aiohttp
import nonebot
from nonebot.adapters.onebot.v11 import Message, MessageSegment

# group_id : last_vurl
analysis_stat: Dict[int, str] = {}

config = nonebot.get_driver().config
analysis_display_image = getattr(config, "analysis_display_image", False)
analysis_display_image_list = getattr(config, "analysis_display_image_list", [])


async def bili_keyword(group_id: Optional[int], text: str) -> Union[Message, str]:
    try:
        # 提取url
        url, page, time_location = extract(text)
        # 如果是小程序就去搜索标题
        if not url:
            title = re.search(r'"desc":("[^"哔哩]+")', text)
            vurl = await search_bili_by_title(title[1])
            if vurl:
                url, page, time_location = extract(vurl)

        # 获取视频详细信息
        msg, vurl = "", ""
        if "view?" in url:
            msg, vurl = await video_detail(url, page=page, time_location=time_location)
        elif "bangumi" in url:
            msg, vurl = await bangumi_detail(url, time_location)
        elif "xlive" in url:
            msg, vurl = await live_detail(url)
        elif "article" in url:
            msg, vurl = await article_detail(url, page)
        elif "dynamic" in url:
            msg, vurl = await dynamic_detail(url)

        # 避免多个机器人解析重复推送
        if group_id:
            if group_id in analysis_stat and analysis_stat[group_id] == vurl:
                return ""
            analysis_stat[group_id] = vurl
    except Exception as e:
        msg = "bili_keyword Error: {}".format(type(e))
    return msg


async def b23_extract(text: str) -> str:
    b23 = re.compile(r"b23.tv/(\w+)|(bili(22|23|33|2233).cn)/(\w+)", re.I).search(
        text.replace("\\", "")
    )
    url = f"https://{b23[0]}"
    async with aiohttp.request(
        "GET", url, timeout=aiohttp.client.ClientTimeout(10)
    ) as resp:
        return str(resp.url)


def extract(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    try:
        url = ""
        page = re.compile(r"([?&]|&amp;)p=\d+").search(text)
        time = re.compile(r"([?&]|&amp;)t=\d+").search(text)
        aid = re.compile(r"av\d+", re.I).search(text)
        bvid = re.compile(r"BV([A-Za-z0-9]{10})+", re.I).search(text)
        epid = re.compile(r"ep\d+", re.I).search(text)
        ssid = re.compile(r"ss\d+", re.I).search(text)
        mdid = re.compile(r"md\d+", re.I).search(text)
        room_id = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).search(text)
        cvid = re.compile(
            r"(/read/(cv|mobile|native)(/|\?id=)?|^cv)(\d+)", re.I
        ).search(text)
        dynamic_id_type2 = re.compile(
            r"(t|m).bilibili.com/(\d+)\?(.*?)(&|&amp;)type=2", re.I
        ).search(text)
        dynamic_id = re.compile(r"(t|m).bilibili.com/(\d+)", re.I).search(text)
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
            page = cvid[4]
            url = f"https://api.bilibili.com/x/article/viewinfo?id={page}&mobi_app=pc&from=web"
        elif dynamic_id_type2:
            url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail?rid={dynamic_id_type2[2]}&type=2"
        elif dynamic_id:
            url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail?dynamic_id={dynamic_id[2]}"
        return url, page, time
    except Exception:
        return "", None, None


async def search_bili_by_title(title: str) -> str:
    search_url = f"https://api.bilibili.com/x/web-interface/search/all/v2?keyword={urllib.parse.quote(title)}"

    async with aiohttp.request(
        "GET", search_url, timeout=aiohttp.client.ClientTimeout(10)
    ) as resp:
        result = (await resp.json())["data"]["result"]

    for i in result:
        if i.get("result_type") != "video":
            continue
        # 只返回第一个结果
        return i["data"][0].get("arcurl")


# 处理超过一万的数字
def handle_num(num: int) -> str:
    if num > 10000:
        num = f"{num / 10000:.2f}万"
    return num


async def video_detail(url: str, **kwargs) -> Tuple[Union[Message, str], str]:
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = (await resp.json()).get("data")
            if not res:
                return "解析到视频被删了/稿件不可见或审核中/权限不足", url
        vurl = f"https://www.bilibili.com/video/av{res['aid']}"
        title = f"\n标题：{res['title']}\n"
        cover = (
            MessageSegment.image(res["pic"])
            if analysis_display_image or "video" in analysis_display_image_list
            else ""
        )
        page = kwargs.get("page")
        if page:
            page = page[0].replace("&amp;", "&")
            p = int(page[3:])
            if p <= len(res["pages"]):
                vurl += f"?p={p}"
                part = res["pages"][p - 1]["part"]
                if part != res["title"]:
                    title += f"小标题：{part}\n"
        time_location = kwargs.get("time_location")
        if time_location:
            time_location = time_location[0].replace("&amp;", "&")[3:]
            if page:
                vurl += f"&t={time_location}"
            else:
                vurl += f"?t={time_location}"
        pubdate = strftime("%Y-%m-%d %H:%M:%S", localtime(res["pubdate"]))
        tname = f"类型：{res['tname']} | UP：{res['owner']['name']} | 日期：{pubdate}\n"
        stat = f"播放：{handle_num(res['stat']['view'])} | 弹幕：{handle_num(res['stat']['danmaku'])} | 收藏：{handle_num(res['stat']['favorite'])}\n"
        stat += f"点赞：{handle_num(res['stat']['like'])} | 硬币：{handle_num(res['stat']['coin'])} | 评论：{handle_num(res['stat']['reply'])}\n"
        desc = f"简介：{res['desc']}"
        desc_list = desc.split("\n")
        desc = "".join(i + "\n" for i in desc_list if i)
        desc_list = desc.split("\n")
        if len(desc_list) > 4:
            desc = desc_list[0] + "\n" + desc_list[1] + "\n" + desc_list[2] + "……"
        msg = Message([cover, vurl, title, tname, stat, desc])
        return msg, vurl
    except Exception as e:
        msg = "视频解析出错--Error: {}".format(type(e))
        return msg, None


async def bangumi_detail(
    url: str, time_location: str = None
) -> Tuple[Union[Message, str], str]:
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = (await resp.json()).get("result")
            if not res:
                return None, None
        cover = (
            MessageSegment.image(res["cover"])
            if analysis_display_image or "bangumi" in analysis_display_image_list
            else ""
        )
        title = f"番剧：{res['title']}\n"
        desc = f"{res['newest_ep']['desc']}\n"
        index_title = ""
        style = "".join(f"{i}," for i in res["style"])
        style = f"类型：{style[:-1]}\n"
        evaluate = f"简介：{res['evaluate']}\n"
        if "season_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/play/ss{res['season_id']}"
        elif "media_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/media/md{res['media_id']}"
        else:
            epid = re.compile(r"ep_id=\d+").search(url)[0][len("ep_id=") :]
            for i in res["episodes"]:
                if str(i["ep_id"]) == epid:
                    index_title = f"标题：{i['index_title']}\n"
                    break
            vurl = f"https://www.bilibili.com/bangumi/play/ep{epid}"
        if time_location:
            time_location = time_location[0].replace("&amp;", "&")[3:]
            vurl += f"?t={time_location}"
        msg = Message([cover, f"{vurl}\n", title, index_title, desc, style, evaluate])
        return msg, vurl
    except Exception as e:
        msg = "番剧解析出错--Error: {}".format(type(e))
        msg += f"\n{url}"
        return msg, None


async def live_detail(url: str) -> Tuple[Union[Message, str], str]:
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = await resp.json()
            if res["code"] != 0:
                return None, None
        res = res["data"]
        uname = res["anchor_info"]["base_info"]["uname"]
        room_id = res["room_info"]["room_id"]
        title = res["room_info"]["title"]
        cover = (
            MessageSegment.image(res["room_info"]["cover"])
            if analysis_display_image or "live" in analysis_display_image_list
            else ""
        )
        live_status = res["room_info"]["live_status"]
        lock_status = res["room_info"]["lock_status"]
        parent_area_name = res["room_info"]["parent_area_name"]
        area_name = res["room_info"]["area_name"]
        online = res["room_info"]["online"]
        tags = res["room_info"]["tags"]
        watched_show = res["watched_show"]["text_large"]
        vurl = f"https://live.bilibili.com/{room_id}\n"
        if lock_status:
            lock_time = res["room_info"]["lock_time"]
            lock_time = strftime("%Y-%m-%d %H:%M:%S", localtime(lock_time))
            title = f"[已封禁]直播间封禁至：{lock_time}\n"
        elif live_status == 1:
            title = f"[直播中]标题：{title}\n"
        elif live_status == 2:
            title = f"[轮播中]标题：{title}\n"
        else:
            title = f"[未开播]标题：{title}\n"
        up = f"主播：{uname}  当前分区：{parent_area_name}-{area_name}\n"
        watch = f"观看：{watched_show}  直播时的人气上一次刷新值：{handle_num(online)}\n"
        if tags:
            tags = f"标签：{tags}\n"
        if live_status:
            player = f"独立播放器：https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={room_id}"
        else:
            player = ""
        msg = Message([cover, vurl, title, up, watch, tags, player])
        return msg, vurl
    except Exception as e:
        msg = "直播间解析出错--Error: {}".format(type(e))
        return msg, None


async def article_detail(url: str, cvid: str) -> Tuple[Union[Message, str], str]:
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = (await resp.json()).get("data")
            if not res:
                return None, None
        images = (
            [MessageSegment.image(i) for i in res["origin_image_urls"]]
            if analysis_display_image or "article" in analysis_display_image_list
            else []
        )
        vurl = f"https://www.bilibili.com/read/cv{cvid}"
        title = f"标题：{res['title']}\n"
        up = f"作者：{res['author_name']} (https://space.bilibili.com/{res['mid']})\n"
        view = f"阅读数：{handle_num(res['stats']['view'])} "
        favorite = f"收藏数：{handle_num(res['stats']['favorite'])} "
        coin = f"硬币数：{handle_num(res['stats']['coin'])}"
        share = f"分享数：{handle_num(res['stats']['share'])} "
        like = f"点赞数：{handle_num(res['stats']['like'])} "
        dislike = f"不喜欢数：{handle_num(res['stats']['dislike'])}"
        desc = view + favorite + coin + "\n" + share + like + dislike + "\n"
        msg = Message(images)
        msg.extend([title, up, desc, vurl])
        return msg, vurl
    except Exception as e:
        msg = "专栏解析出错--Error: {}".format(type(e))
        return msg, None


async def dynamic_detail(url: str) -> Tuple[Union[Message, str], str]:
    try:
        async with aiohttp.request(
            "GET", url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            res = (await resp.json())["data"].get("card")
            if not res:
                return None, None
        card = json.loads(res["card"])
        dynamic_id = res["desc"]["dynamic_id"]
        vurl = f"https://t.bilibili.com/{dynamic_id}\n"
        item = card.get("item")
        if not item:
            return "动态不存在文字内容", vurl
        content = item.get("description")
        if not content:
            content = item.get("content")
        content = content.replace("\r", "\n")
        if len(content) > 250:
            content = content[:250] + "......"
        images = (
            item.get("pictures")
            if analysis_display_image or "dynamic" in analysis_display_image_list
            else []
        )
        if images:
            images = [MessageSegment.image(i.get("img_src")) for i in images]
        else:
            pics = item.get("pictures_count")
            content += f"\nPS：动态中包含{pics}张图片"
        origin = card.get("origin")
        if origin:
            jorigin = json.loads(origin)
            short_link = jorigin.get("short_link")
            if short_link:
                content += f"\n动态包含转发视频{short_link}"
            else:
                content += f"\n动态包含转发其他动态"
        msg = Message(content)
        msg.extend(images)
        msg.append(f"\n{vurl}")
        return msg, vurl
    except Exception as e:
        msg = "动态解析出错--Error: {}".format(type(e))
        return msg, None
