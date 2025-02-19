import os
import aiohttp
import asyncio
import logging
import json

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from astrbot.api.all import *

@register("blue_archive", "anka", "蔚蓝档案攻略查询插件 - 调用攻略 API 进行查询", "1.0.0")
class StrategyQuery(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.api_base = "https://arona.diyigemt.com/api/v2"
        self.cdn_prefix = "https://arona.cdn.diyigemt.com/image"
        self.logger = logging.getLogger(__name__)

        self.resource_hash_map = {}
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "blue_archive"))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)

        self.hash_map_file = os.path.join(self.base_dir, "resource_hash_map.json")
        if os.path.exists(self.hash_map_file):
            with open(self.hash_map_file, 'r', encoding='utf-8') as f:
                self.resource_hash_map = json.load(f)

    def save_hash_map(self):
        with open(self.hash_map_file, 'w', encoding='utf-8') as f:
            json.dump(self.resource_hash_map, f, ensure_ascii=False, indent=4)

    @filter.command("攻略查询")
    async def query_strategy(self, event: AstrMessageEvent, *, name: str):
        yield event.plain_result("正在查询攻略，请稍候...")

        url = f"{self.api_base}/image"
        params = {
            "name": name,
            "size": 8,
            "method": 2
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
            item = data[0]
            async for ret in self.handle_strategy_item(event, item):
                yield ret
        elif code == 101 and data:
            item = data[0]
            yield event.plain_result(f"为你找到的第一条模糊匹配结果：{item.get('name')}")
            async for ret in self.handle_strategy_item(event, item):
                yield ret
        else:
            yield event.plain_result(f"查询结果异常：code={code}, message={message}")

    async def handle_strategy_item(self, event: AstrMessageEvent, item: dict):
        name = item.get("name")
        file_hash = item.get("hash")
        content = item.get("content")
        file_type = item.get("type")

        self.logger.info("名称：%s", name)
        self.logger.info("Hash：%s", file_hash)
        self.logger.info("类型：%s", file_type)

        if file_type == "file":
            image_url = f"{self.cdn_prefix}{content}"
            old_hash = self.resource_hash_map.get(name)
            _, ext = os.path.splitext(content)
            local_filename = f"{name}{ext}"
            local_path = os.path.join(self.base_dir, local_filename)

            if old_hash == file_hash and os.path.exists(local_path):
                self.logger.info("检测到本地文件已缓存，直接使用。")
                yield event.image_result(local_path)
            else:
                self.logger.info("本地文件不存在或哈希不同，正在更新缓存...")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                with open(local_path, "wb") as f:
                                    f.write(img_data)
                                self.resource_hash_map[name] = file_hash
                                self.save_hash_map()
                                self.logger.info("已更新本地缓存文件：%s", local_filename)
                                yield event.image_result(local_path)
                            else:
                                self.logger.error("下载图片失败，状态码：%s", resp.status)
                                yield event.plain_result(f"下载图片失败，状态码：{resp.status}")
                except Exception as e:
                    self.logger.error("下载图片出现错误：%s", str(e))
                    yield event.plain_result(f"下载图片出现错误：{str(e)}")
        else:
            yield event.plain_result(f"结果文本：{content}")
