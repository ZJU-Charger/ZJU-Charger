"""服务商管理器：管理所有充电桩服务商，提供统一接口"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from .provider_base import ProviderBase
from .providers.neptune import NeptuneProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """服务商管理器

    负责注册、管理和调用所有服务商适配器
    """

    def __init__(self):
        """初始化服务商管理器"""
        self.providers: List[ProviderBase] = []
        self._register_providers()

    def _register_providers(self):
        """注册所有可用服务商"""
        # 注册尼普顿服务商
        neptune = NeptuneProvider()
        self.providers.append(neptune)
        logger.info(f"已注册服务商: {neptune.provider_name} ({neptune.provider_id})")

    def get_provider(self, provider_id: str) -> Optional[ProviderBase]:
        """根据 ID 获取服务商

        Args:
            provider_id: 服务商标识

        Returns:
            服务商实例，如果不存在返回 None
        """
        for provider in self.providers:
            if provider.provider_id == provider_id:
                return provider
        return None

    def list_providers(self) -> List[Dict[str, str]]:
        """获取所有可用服务商列表

        Returns:
            服务商列表，格式：[{"id": "neptune", "name": "尼普顿"}, ...]
        """
        return [
            {"id": provider.provider_id, "name": provider.provider_name}
            for provider in self.providers
        ]

    async def fetch_all_providers(self) -> Dict[str, Any]:
        """并发获取所有服务商的数据

        Returns:
            包含所有服务商数据的字典，格式：
            {
                "provider_id": {
                    "status": "success" | "error",
                    "data": {...} | None,
                    "error": str | None
                },
                ...
            }
        """
        results = {}

        # 并发获取所有服务商数据
        tasks = []
        provider_list = []

        for provider in self.providers:
            async with provider:
                task = provider.fetch_status()
                tasks.append(task)
                provider_list.append(provider)

        fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for idx, (provider, result) in enumerate(zip(provider_list, fetch_results)):
            if isinstance(result, Exception):
                logger.error(
                    f"服务商 {provider.provider_name} 获取数据失败: {result}",
                    exc_info=True,
                )
                results[provider.provider_id] = {
                    "status": "error",
                    "data": None,
                    "error": str(result),
                }
            elif result is None:
                logger.warning(f"服务商 {provider.provider_name} 返回空数据")
                results[provider.provider_id] = {
                    "status": "error",
                    "data": None,
                    "error": "返回空数据",
                }
            else:
                results[provider.provider_id] = {
                    "status": "success",
                    "data": result,
                    "error": None,
                }

        return results

    def merge_stations(self, providers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """合并多个服务商的站点数据到统一格式

        Args:
            providers_data: fetch_all_providers() 返回的数据

        Returns:
            合并后的站点列表，每个站点包含 provider_id 和 provider_name
        """
        all_stations = []

        for provider_id, result in providers_data.items():
            if result["status"] != "success" or result["data"] is None:
                continue

            # fetch_status 现在直接返回统一格式的站点列表
            if isinstance(result["data"], list):
                all_stations.extend(result["data"])

        return all_stations

    def _get_timestamp(self):
        """获取当前时间戳（UTC+8）"""
        tz_utc_8 = timezone(timedelta(hours=8))
        return datetime.now(tz_utc_8).isoformat()

    async def fetch_and_format(
        self, provider_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """获取数据并格式化为 API 响应格式

        Args:
            provider_id: 可选，如果指定则只获取该服务商的数据

        Returns:
            API 响应格式的数据，格式：
            {
                "updated_at": "2025-01-01T00:00:00+08:00",
                "stations": [...]
            }
        """
        if provider_id:
            # 只获取指定服务商的数据
            provider = self.get_provider(provider_id)
            if provider is None:
                logger.error(f"未找到服务商: {provider_id}")
                return None

            async with provider:
                stations = await provider.fetch_status()
                if stations is None:
                    return None

                return {"updated_at": self._get_timestamp(), "stations": stations}
        else:
            # 获取所有服务商的数据并合并
            providers_data = await self.fetch_all_providers()
            stations = self.merge_stations(providers_data)

            return {"updated_at": self._get_timestamp(), "stations": stations}
