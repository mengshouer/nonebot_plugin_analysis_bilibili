import re
from .analysis_bilibili import b23_extract, bili_keyword
from nonebot import on_message
from nonebot.adapters.cqhttp import Bot, Event

analysis_bili = on_message()

@analysis_bili.handle()
async def analysis_main(bot: Bot, event: Event, state: dict):
    text = str(event.message).strip()
    if "b23.tv" in text:
        # 提前处理短链接，避免解析到其他的
        text = await b23_extract(text)
    patterns = r'(www.bilibili.com/video)|(www.bilibili.com/bangumi)|(^(BV|bv)([0-9A-Za-z]{10}))|(^(av|AV)([0-9]+)(/.*|\\?.*|)$)|(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)'
    match = re.compile(patterns).search(text)
    if match:
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
