import re
from .analysis_bilibili import b23_extract, bili_keyword
from nonebot import on_regex
from nonebot.adapters import Bot, Event

analysis_bili = on_regex(r"(b23.tv)|(bili(22|23|33|2233).cn)|(live.bilibili.com)|(bilibili.com/(video|read|bangumi))|(^(av|cv)(\d+))|(^BV([a-zA-Z0-9])+)|(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)|(QQ小程序&#93;哔哩哔哩)", flags=re.I)

@analysis_bili.handle()
async def analysis_main(bot: Bot, event: Event, state: dict):
    text = str(event.message).strip()
    if re.search(r"(b23.tv)|(bili(22|23|33|2233).cn)", text, re.I):
        # 提前处理短链接，避免解析到其他的
        text = await b23_extract(text)
    try:
        group_id = event.group_id
    except:
        group_id = "1"
    msg = await bili_keyword(group_id, text)
    if msg:
        try:
            await analysis_bili.send(msg)
        except:
            await analysis_bili.send("此次解析可能被风控，尝试去除简介后发送！")
            msg = re.sub(r"简介.*", "", msg)
            await analysis_bili.send(msg)
