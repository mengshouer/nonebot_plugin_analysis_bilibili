import re
import json
import nonebot

from time import localtime, strftime
from typing import Dict, List, Optional, Tuple, Union
from aiohttp import ClientSession

from .wbi import get_query


# group_id : last_vurl
analysis_stat: Dict[int, str] = {}

config = nonebot.get_driver().config
analysis_display_image = getattr(config, "analysis_display_image", False)
analysis_display_image_list = getattr(config, "analysis_display_image_list", [])
images_size = getattr(config, "analysis_images_size", "")
cover_images_size = getattr(config, "analysis_cover_images_size", "")


def resize_image(src: str, is_cover=False) -> str:
    img_type = src[-3:]
    if cover_images_size and is_cover:
        return f"{src}@{cover_images_size}.{img_type}"
    if images_size:
        return f"{src}@{images_size}.{img_type}"
    return src


async def bili_keyword(
    group_id: Optional[int], text: str, session: ClientSession
) -> Union[List[Union[List[str], str]], str]:
    try:
        # 提取url
        url, page, time_location = extract(text)
        # 如果是小程序就去搜索标题
        if not url:
            if title := re.search(r'"desc":("[^"哔哩]+")', text):
                vurl = await search_bili_by_title(title[1], session)
                if vurl:
                    url, page, time_location = extract(vurl)

        # 获取视频详细信息
        msg, vurl = "", ""
        if "view?" in url:
            msg, vurl = await video_detail(
                url, page=page, time_location=time_location, session=session
            )
        elif "bangumi" in url:
            msg, vurl = await bangumi_detail(url, time_location, session)
        elif "xlive" in url:
            msg, vurl = await live_detail(url, session)
        elif "article" in url:
            msg, vurl = await article_detail(url, page, session)
        elif "dynamic" in url:
            msg, vurl = await dynamic_detail(url, session)

        # 避免多个机器人解析重复推送
        if group_id:
            if group_id in analysis_stat and analysis_stat[group_id] == vurl:
                return ""
            analysis_stat[group_id] = vurl
    except Exception as e:
        msg = "bili_keyword Error: {}".format(type(e))
    return msg


async def b23_extract(text: str, session: ClientSession) -> str:
    b23 = re.compile(r"b23.tv/(\w+)|(bili(22|23|33|2233).cn)/(\w+)", re.I).search(
        text.replace("\\", "")
    )
    url = f"https://{b23[0]}"

    async with session.get(url) as resp:
        return str(resp.url)


def extract(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    try:
        url = ""
        # 视频分p
        page = re.compile(r"([?&]|&amp;)p=\d+").search(text)
        # 视频播放定位时间
        time = re.compile(r"([?&]|&amp;)t=\d+").search(text)
        # 主站视频 av 号
        aid = re.compile(r"av\d+", re.I).search(text)
        # 主站视频 bv 号
        bvid = re.compile(r"BV([A-Za-z0-9]{10})+", re.I).search(text)
        # 番剧视频页
        epid = re.compile(r"ep\d+", re.I).search(text)
        # 番剧剧集ssid(season_id)
        ssid = re.compile(r"ss\d+", re.I).search(text)
        # 番剧详细页
        mdid = re.compile(r"md\d+", re.I).search(text)
        # 直播间
        room_id = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).search(text)
        # 文章
        cvid = re.compile(
            r"(/read/(cv|mobile|native)(/|\?id=)?|^cv)(\d+)", re.I
        ).search(text)
        # 动态
        dynamic_id_type2 = re.compile(
            r"(t|m).bilibili.com/(\d+)\?(.*?)(&|&amp;)type=2", re.I
        ).search(text)
        # 动态
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
            url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?rid={dynamic_id_type2[2]}&type=2"
        elif dynamic_id:
            url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?id={dynamic_id[2]}"
        return url, page, time
    except Exception:
        return "", None, None


async def search_bili_by_title(title: str, session: ClientSession) -> str:
    # set headers
    mainsite_url = "https://www.bilibili.com"
    async with session.get(mainsite_url) as resp:
        assert resp.status == 200

    query = await get_query({"keyword": title})
    search_url = f"https://api.bilibili.com/x/web-interface/wbi/search/all/v2?{query}"

    async with session.get(search_url) as resp:
        result = await resp.json()

    if result["code"] == -412:
        nonebot.logger.warning(f"analysis_bilibili: {result}")
        return

    for i in result["data"]["result"]:
        if i.get("result_type") != "video":
            continue
        # 只返回第一个结果
        return i["data"][0].get("arcurl")


# 处理超过一万的数字
def handle_num(num: int) -> str:
    if num > 10000:
        num = f"{num / 10000:.2f}万"
    return num


async def video_detail(
    url: str, session: ClientSession, **kwargs
) -> Tuple[List[str], str]:
    try:
        async with session.get(url) as resp:
            res = (await resp.json()).get("data")
            if not res:
                return "解析到视频被删了/稿件不可见或审核中/权限不足", url
        vurl = f"https://www.bilibili.com/video/av{res['aid']}"
        title = f"\n标题：{res['title']}\n"

        has_image = False
        if analysis_display_image or "video" in analysis_display_image_list:
            has_image = True

        cover = resize_image(res["pic"]) if has_image else ""
        vurl = "\n" + vurl if cover else vurl
        if page := kwargs.get("page"):
            page = page[0].replace("&amp;", "&")
            p = int(page[3:])
            if p <= len(res["pages"]):
                vurl += f"?p={p}"
                part = res["pages"][p - 1]["part"]
                if part != res["title"]:
                    title += f"小标题：{part}\n"
        if time_location := kwargs.get("time_location"):
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
        msg = [cover, vurl, title, tname, stat, desc]
        return msg, vurl
    except Exception as e:
        msg = "视频解析出错--Error: {}".format(type(e))
        return msg, None


async def bangumi_detail(
    url: str, time_location: str, session: ClientSession
) -> Tuple[List[str], str]:
    try:
        async with session.get(url) as resp:
            res = (await resp.json()).get("result")
            if not res:
                return None, None

        has_image = False
        if analysis_display_image or "bangumi" in analysis_display_image_list:
            has_image = True

        cover = resize_image(res["cover"], is_cover=True) if has_image else ""
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
        vurl = "\n" + vurl if cover else vurl
        msg = [cover, f"{vurl}\n", title, index_title, desc, style, evaluate]
        return msg, vurl
    except Exception as e:
        msg = "番剧解析出错--Error: {}".format(type(e))
        msg += f"\n{url}"
        return msg, None


async def live_detail(url: str, session: ClientSession) -> Tuple[List[str], str]:
    try:
        async with session.get(url) as resp:
            res = await resp.json()
            if res["code"] != 0:
                return None, None
        res = res["data"]
        uname = res["anchor_info"]["base_info"]["uname"]
        room_id = res["room_info"]["room_id"]
        title = res["room_info"]["title"]

        has_image = False
        if analysis_display_image or "live" in analysis_display_image_list:
            has_image = True

        cover = (
            resize_image(res["room_info"]["cover"], is_cover=True) if has_image else ""
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
        vurl = "\n" + vurl if cover else vurl
        msg = [cover, vurl, title, up, watch, tags, player]
        return msg, vurl
    except Exception as e:
        msg = "直播间解析出错--Error: {}".format(type(e))
        return msg, None


async def article_detail(
    url: str, cvid: str, session: ClientSession
) -> Tuple[List[Union[List[str], str]], str]:
    try:
        async with session.get(url) as resp:
            res = (await resp.json()).get("data")
            if not res:
                return None, None

        has_image = False
        if analysis_display_image or "article" in analysis_display_image_list:
            has_image = True

        images = (
            [resize_image(i) for i in res["origin_image_urls"]] if has_image else []
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
        msg = [images, title, up, desc, vurl]
        return msg, vurl
    except Exception as e:
        msg = "专栏解析出错--Error: {}".format(type(e))
        return msg, None


async def dynamic_detail(
    url: str, session: ClientSession
) -> Tuple[List[Union[List[str], str]], str]:
    try:
        async with session.get(url) as resp:
            res = await resp.json()
            if res["code"] != 0:
                return None, None
        res = res.get("data").get("item")
        dynamic_id = res["id_str"]
        vurl = f"https://t.bilibili.com/{dynamic_id}\n"

        # 动态内容
        module_dynamic = res["modules"]["module_dynamic"]
        module_type = res["type"]

        # 文字信息
        desc = module_dynamic["desc"]
        content = desc.get("text").replace("\r", "\n").replace("\n\n", "\n")

        has_image = False
        if analysis_display_image or "dynamic" in analysis_display_image_list:
            has_image = True

        # 额外信息(会员购)
        additional_msg = []
        additional = module_dynamic.get("additional")
        if isinstance(additional, dict):
            additional_type = additional.get("type")
            if additional_type == "ADDITIONAL_TYPE_GOODS":
                items = additional.get("goods", {}).get("items", [])
                for item in items:
                    additional_msg.append(f"{item.get('name')}（{item.get('price')}）\n")

        # DRAW图片/ARCHIVE转发视频/null纯文字
        draws = []
        archive_cover = ""
        archive_msg = ""
        split = "\n----------------------------------------\n"
        major = module_dynamic["major"]
        if isinstance(major, dict):
            if module_type == "DYNAMIC_TYPE_DRAW":
                split = split if additional_msg else ""
                if has_image:
                    draws = [
                        resize_image(i.get("src"))
                        for i in major.get("draw").get("items", [])
                    ]
                else:
                    items_len = len(major.get("draw").get("items", []))
                    content += f"\nPS：动态中包含{items_len}张图片"

            elif module_type == "DYNAMIC_TYPE_AV":
                jump_url = major.get("archive").get("jump_url")
                archive_cover = (
                    resize_image(major.get("archive").get("cover")) if has_image else ""
                )
                archive_msg += f"转发视频：https:{jump_url}\n"
                archive_msg += f"简介：{major.get('archive').get('desc')}"

        elif module_type == "DYNAMIC_TYPE_FORWARD":
            desc = module_dynamic["desc"]
            orig_id = res.get("orig").get("id_str")
            archive_msg += f"转发动态：https://t.bilibili.com/{orig_id}\n"
        else:
            split = ""

        msg = [
            content,
            draws,
            split,
            archive_cover,
            archive_msg,
            additional_msg,
            f"\n动态链接：{vurl}",
        ]
        return msg, vurl
    except Exception as e:
        msg = "动态解析出错--Error: {}".format(type(e))
        return msg, None
