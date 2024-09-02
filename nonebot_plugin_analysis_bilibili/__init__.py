import re
from typing import List, Union
from aiohttp import ClientSession
from nonebot import on_regex, logger, require
from nonebot.adapters import Event
from nonebot.rule import Rule
from nonebot.plugin import PluginMetadata
from nonebot.params import RegexStr
from .analysis_bilibili import config, b23_extract, bili_keyword, search_bili_by_title

require("nonebot_plugin_saa")
from nonebot_plugin_saa import (
    MessageFactory,
    MessageSegmentFactory,
    Text,
    Image,
)

__plugin_meta__ = PluginMetadata(
    name="analysis_bilibili",
    description="自动解析bilibili链接内容",
    usage="https://github.com/mengshouer/nonebot_plugin_analysis_bilibili?tab=readme-ov-file#%E4%BD%BF%E7%94%A8%E6%96%B9%E5%BC%8F",
    type="application",
    homepage="https://github.com/mengshouer/nonebot_plugin_analysis_bilibili",
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"
}

whitelist = [str(i) for i in getattr(config, "analysis_whitelist", [])]
group_whitelist = [str(i) for i in getattr(config, "analysis_group_whitelist", [])]
blacklist = [str(i) for i in getattr(config, "analysis_blacklist", [])]
group_blacklist = [str(i) for i in getattr(config, "analysis_group_blacklist", [])]
desc_blacklist = [str(i) for i in getattr(config, "analysis_desc_blacklist", [])]
trust_env = getattr(config, "analysis_trust_env", False)
enable_search = getattr(config, "analysis_enable_search", False)


async def is_enable_search() -> bool:
    return enable_search


async def is_normal(event: Event) -> bool:
    user_id = str(event.get_user_id())
    group_id = str(
        event.group_id
        if hasattr(event, "group_id")
        else event.channel_id
        if hasattr(event, "channel_id")
        else None
    )

    if user_id in whitelist or group_id in group_whitelist:
        return True

    if len(whitelist) > 0 or len(group_whitelist) > 0:
        return False

    if user_id in blacklist or group_id in group_blacklist:
        return False

    return True


analysis_bili = on_regex(
    r".*((b23.tv)|(bili(22|23|33|2233).cn)|(.bilibili.com)|(^(av|cv)(\d+))|(^BV([a-zA-Z0-9]{10})+)|"
    r"(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)|(QQ小程序&#93;哔哩哔哩)).*",
    flags=re.I,
    rule=is_normal,
)

rule = Rule(is_enable_search, is_normal)
search_bili = on_regex(r"^搜视频.*", rule=rule)


def is_image(msg: str) -> bool:
    return msg[-4:].lower() in [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        "jfif",
        "webp",
    ]


def flatten(container):
    for i in container:
        if isinstance(i, (list, tuple)):
            yield from flatten(i)
        else:
            yield i


def format_msg(msg_list: List[Union[List[str], str]], is_plain_text: bool = False):
    flatten_msg_list = list(flatten(msg_list))
    if is_plain_text:
        return "".join([i for i in flatten_msg_list if not is_image(i)])

    msg: List[MessageSegmentFactory] = []

    for i in flatten_msg_list:
        if not i:
            continue
        elif is_image(i):
            msg.append(Image(i))
        else:
            msg.append(Text(i))
    return msg


async def send_msg(msg_list: List[Union[List[str], str, bool]]) -> None:
    if msg_list is False:
        return
    if msg_list is None:
        logger.warning("此次解析的内容为空，接口可能被修改，需要更新！")
        return

    try:
        await MessageFactory(format_msg(msg_list)).send()
    except RuntimeError:
        await analysis_bili.send(format_msg(msg_list, is_plain_text=True))
    except Exception as e:
        logger.exception(e)
        logger.warning(f"{msg_list}\n此次解析的内容可能被风控！")


async def get_msg(
    event: Event, text: str, search: bool = False
) -> Union[List[str], bool]:
    group_id = str(
        event.group_id
        if hasattr(event, "group_id")
        else event.channel_id
        if hasattr(event, "channel_id")
        else None
    )

    async with ClientSession(trust_env=trust_env, headers=headers) as session:
        if search:
            text = await search_bili_by_title(text, session=session)
        else:
            if re.search(r"(b23.tv)|(bili(22|23|33|2233).cn)", text, re.I):
                # 提前处理短链接，避免解析到其他的
                text = await b23_extract(text, session=session)

        msg = await bili_keyword(group_id, text, session=session)

    if msg:
        if isinstance(msg, str):
            # 说明是错误信息
            await analysis_bili.finish(msg)

        if group_id in desc_blacklist:
            if msg[-1].startswith("简介"):
                msg[-1] = ""

    return msg


@analysis_bili.handle()
async def handle_analysis(event: Event, message=RegexStr()) -> None:
    msg = await get_msg(event, message)
    await send_msg(msg)


@search_bili.handle()
async def handle_search(event: Event, message=RegexStr()) -> None:
    msg = await get_msg(event, message[3:].strip(), search=True)
    await send_msg(msg)
