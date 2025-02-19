import aiohttp
import asyncio
import logging

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from astrbot.api.all import *

@register("blue_archive", "anka", "蔚蓝档案攻略查询插件 - 调用攻略 API 进行查询", "1.0.0")
class StrategyQuery(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        # API 基址及 CDN 前缀
        self.api_base = "https://arona.diyigemt.com/api/v2"
        self.cdn_prefix = "https://arona.cdn.diyigemt.com/image"
        self.logger = logging.getLogger(__name__)

    @filter.command("攻略查询")
    async def query_strategy(self, event: AstrMessageEvent, *, name: str):
        """
        查询攻略图片
        指令格式：/攻略查询 <攻略名称>
        """
        # 提示用户正在查询
        await event.send(Plain("正在查询攻略，请稍候..."))

        # 构造 API 请求 URL 和参数
        url = f"{self.api_base}/image"
        params = {
            "name": name,
            "size": 8,      # 返回结果数量上限，默认8
            "method": 1     # 模糊搜索方式，此处默认使用方法1 (jech)
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        yield event.plain_result(f"API 请求失败，状态码：{resp.status}")
                        return
                    result_json = await resp.json()
        except Exception as e:
            yield event.plain_result(f"查询过程中出现错误：{str(e)}")
            return

        code = result_json.get("code")
        message = result_json.get("message", "")
        data = result_json.get("data")

        if code == 200 and isinstance(data, list) and len(data) == 1:
            # 精确匹配返回，data 列表长度必为1
            item = data[0]
            info_text = (
                f"查询到精确匹配结果：\n"
                f"名称：{item.get('name')}\n"
                f"Hash：{item.get('hash')}\n"
                f"类型：{item.get('type')}"
            )
            yield event.plain_result(info_text)

            # 如果结果类型为 file，则构造图片地址并发送图片消息
            if item.get("type") == "file":
                content = item.get("content")
                # 此处构造的图片地址可选两种形式，根据需要选择一个
                image_url = f"{self.cdn_prefix}{content}"
                yield event.image_result(image_url)
            else:
                # 当类型为 plain 时，直接返回文本内容
                yield event.plain_result(f"结果文本：{item.get('content')}")
        elif code == 101:
            # 模糊搜索结果，返回的 code 固定为 101
            if data and isinstance(data, list) and len(data) > 0:
                msg_lines = ["未找到精确匹配，以下为模糊搜索结果："]
                for idx, item in enumerate(data, 1):
                    msg_lines.append(f"{idx}. 名称：{item.get('name')} | Hash：{item.get('hash')}")
                result_text = "\n".join(msg_lines)
                yield event.plain_result(result_text)
            else:
                yield event.plain_result("未找到相关攻略信息。")
        else:
            yield event.plain_result(f"查询结果异常：code={code}, message={message}")
