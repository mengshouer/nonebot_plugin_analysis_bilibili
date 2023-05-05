import re
from typing import List, Union
from aiohttp import ClientSession
from nonebot import on_regex, logger
from nonebot.adapters import Event
from .analysis_bilibili import config, b23_extract, bili_keyword

analysis_bili = on_regex(
    r"(b23.tv)|(bili(22|23|33|2233).cn)|(.bilibili.com)|(^(av|cv)(\d+))|(^BV([a-zA-Z0-9]{10})+)|"
    r"(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)|(QQ小程序&#93;哔哩哔哩)",
    flags=re.I,
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.58"
}
blacklist = getattr(config, "analysis_blacklist", [])
group_blacklist = getattr(config, "analysis_group_blacklist", [])
desc_blacklist = getattr(config, "analysis_desc_blacklist", [])
trust_env = getattr(config, "analysis_trust_env", False)


async def send_msg(msg: List[Union[List[str], str]]) -> None:
    try:
        if not msg[0]:
            # 解析不包含图片
            await analysis_bili.send("\n".join(msg[1:]))
            return
        else:
            try:
                from nonebot.adapters.onebot.v11 import Message, MessageSegment

                if isinstance(msg[0], list):
                    tmp = Message([MessageSegment.image(i) for i in msg[0]])
                else:
                    tmp = Message(MessageSegment.image(msg[0]))
                tmp.extend([MessageSegment.text(i) for i in msg[1:]])
                await analysis_bili.send(tmp)
            except ImportError:
                # 不支持的适配器下只发送文字信息
                await analysis_bili.send("\n".join(msg[1:]))
    except Exception as e:
        logger.exception(e)
        logger.warning(f"{msg}\n此次解析的内容可能被风控！")


@analysis_bili.handle()
async def handle_analysis(event: Event) -> None:
    text = str(event.message).strip()
    if blacklist and int(event.get_user_id()) in blacklist:
        return

    async with ClientSession(trust_env=trust_env, headers=headers) as session:
        if re.search(r"(b23.tv)|(bili(22|23|33|2233).cn)", text, re.I):
            # 提前处理短链接，避免解析到其他的
            text = await b23_extract(text, session=session)

        group_id = (
            event.group_id
            if hasattr(event, "group_id")
            else event.channel_id
            if hasattr(event, "channel_id")
            else None
        )

        if group_id in group_blacklist:
            return
        msg = await bili_keyword(group_id, text, session=session)

    if msg:
        if isinstance(msg, str):
            # 说明是错误信息
            await analysis_bili.finish(msg)

        if group_id in desc_blacklist:
            if msg[-1].startswith("简介"):
                msg[-1] = ""

        await send_msg(msg)
