import re
from .analysis_bilibili import b23_extract, bili_keyword
from nonebot import on_regex, logger
from nonebot.adapters import Bot, Event

analysis_bili = on_regex(
    r"(b23.tv)|(bili(22|23|33|2233).cn)|(.bilibili.com)|(^(av|cv)(\d+))|(^BV([a-zA-Z0-9]{10})+)|"
    r"(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)|(QQ小程序&#93;哔哩哔哩)",
    flags=re.I,
)


@analysis_bili.handle()
async def analysis_main(bot: Bot, event: Event) -> None:
    text = str(event.message).strip()
    blacklist = getattr(bot.config, "analysis_blacklist", [])
    if blacklist and int(event.get_user_id()) in blacklist:
        return
    if re.search(r"(b23.tv)|(bili(22|23|33|2233).cn)", text, re.I):
        # 提前处理短链接，避免解析到其他的
        text = await b23_extract(text)
    if hasattr(event, "group_id"):
        group_id = event.group_id
    elif hasattr(event, "channel_id"):
        group_id = event.channel_id
    else:
        group_id = None
    msg = await bili_keyword(group_id, text)
    if msg:
        try:
            await analysis_bili.send(msg)
        except:
            logger.warning(f"{msg}\n此次解析可能被风控，尝试去除简介后发送！")
            msg = re.sub(r"简介.*", "", msg)
            await analysis_bili.send(msg)
