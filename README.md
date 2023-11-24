<!--
 * @Author         : mengshouer
 * @Date           : 2021-03-16 00:00:00
 * @LastEditors    : mengshouer
 * @LastEditTime   : 2021-03-16 00:00:00
 * @Description    : None
 * @GitHub         : https://github.com/mengshouer/nonebot_plugin_analysis_bilibili
-->

<p align="center">
  <a href="https://v2.nonebot.dev/"><img src="https://v2.nonebot.dev/logo.png" width="200" height="200" alt="nonebot"></a>
</p>

<div align="center">

# nonebot_plugin_analysis_bilibili

_✨ NoneBot bilibili 视频、番剧解析插件 ✨_

</div>

<p align="center">
  <a href="https://raw.githubusercontent.com/cscs181/QQ-Github-Bot/master/LICENSE">
    <img src="https://img.shields.io/github/license/cscs181/QQ-Github-Bot.svg" alt="license">
  </a>
  <a href="https://pypi.python.org/pypi/nonebot-plugin-analysis-bilibili">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-analysis-bilibili.svg" alt="pypi">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">
</p>

## 使用方式

私聊或群聊发送 bilibili 的小程序/链接，所有适配器均可使用，在不支持发送图片的适配器中仅发送文字。

## 额外配置项(可选)

在配置文件中加入(需要什么加什么)

```
# 当图片大小超过下值时，修改图片大小，不填则发送原图，example: 100h / 100w / 100h_100w
analysis_images_size = ""
analysis_cover_images_size = "" # 封面图大小，和上面相同，视频、直播、番剧 封面图使用这个大小
analysis_blacklist = [123456789] # 不解析里面填写的QQ号发的链接 List[int | str]
analysis_group_blacklist = [123456789] # 不解析里面填写的QQ群号发的链接 List[int | str]
analysis_desc_blacklist = [123456789] # 里面填写的群号，发送的解析内容不包含简介 List[int | str]
analysis_display_image = true # 是否显示封面 true/false
# 哪种类型需要显示封面，与上一项相冲突，上一项为true则全开 List[str]
analysis_display_image_list = ["video", "bangumi", "live", "article", "dynamic"]
analysis_enable_search = false # 是否开启搜视频功能 true/false  example: "搜视频 123456"


analysis_trust_env = false # 是否使用环境变量或者当前系统正在使用中的代理设置 true/false
```

## 安装

1. 使用 nb-cli 安装，不需要手动添加入口，更新使用 pip (推荐)

```
nb plugin install nonebot_plugin_analysis_bilibili
```

2. 使用 pip 安装和更新，初次安装需要手动添加入口 （新版默认不带 bot.py 文件）

```
pip install --upgrade nonebot_plugin_analysis_bilibili
```

pip 安装后在 Nonebot2 入口文件（例如 bot.py ）增加：

```python
nonebot.load_plugin("nonebot_plugin_analysis_bilibili")
```
