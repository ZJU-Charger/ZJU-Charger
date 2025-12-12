"""服务商管理器：管理所有充电桩服务商，提供统一接口"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import aiohttp
from fetcher.providers.provider_base import ProviderBase
from fetcher.providers.neptune import NeptuneProvider
from fetcher.providers.neptune_junior import NeptuneJuniorProvider
from fetcher.providers.dlmm import DlmmProvider
from fetcher.providers.else_provider import ElseProvider

import logfire
from server.logfire_setup import ensure_logfire_configured

ensure_logfire_configured()


def _now_utc8_iso() -> str:
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()


class ProviderManager:
    """服务商管理器

    负责注册、管理和调用所有服务商适配器
    职责：初始化、管理生命周期、并发调度、结果合并与格式化。
    """

    def __init__(self):
        """初始化服务商管理器"""
        self.providers: List[ProviderBase] = []
        self._register_providers()

    def _register_providers(self):
        """注册所有可用服务商"""
        neptune = NeptuneProvider()
        neptune_junior = NeptuneJuniorProvider()
        dlmm = DlmmProvider()
        else_provider = ElseProvider()
        try:
            neptune.load_stations()
            neptune_junior.load_stations()
            dlmm.load_stations()
            else_provider.load_stations()
        except Exception as exc:
            logfire.error(
                "加载 {provider} 站点失败: {error}",
                provider=neptune.provider,
                error=str(exc),
            )
            logfire.error(
                "加载 {provider} 站点失败: {error}",
                provider=neptune_junior.provider,
                error=str(exc),
            )
            logfire.error(
                "加载 {provider} 站点失败: {error}",
                provider=dlmm.provider,
                error=str(exc),
            )
            logfire.error(
                "加载 {provider} 站点失败: {error}",
                provider=else_provider.provider,
                error=str(exc),
            )
        self.providers.append(neptune)
        logfire.info("已注册服务商: {provider}", provider=neptune.provider)
        self.providers.append(neptune_junior)
        logfire.info("已注册服务商: {provider}", provider=neptune_junior.provider)
        self.providers.append(dlmm)
        logfire.info("已注册服务商: {provider}", provider=dlmm.provider)
        self.providers.append(else_provider)
        logfire.info("已注册服务商: {provider}", provider=else_provider.provider)

    def list_providers(self) -> List[Dict[str, str]]:
        """返回当前已注册的服务商列表"""
        return [{"id": prov.provider, "name": prov.provider} for prov in self.providers]

    async def initialize_providers(self):
        """初始化所有服务商：加载其对应的 CSV 站点数据。"""
        logfire.info("开始初始化并加载所有服务商的站点数据...")

        load_tasks = [prov.load_stations() for prov in self.providers]
        results = await asyncio.gather(*load_tasks, return_exceptions=True)

        for prov, result in zip(self.providers, results):
            if isinstance(result, Exception):
                logfire.error(
                    "服务商 {provider} 加载站点数据失败: {error}",
                    provider=prov.provider,
                    error=str(result),
                )
            elif result is not None:
                logfire.info(
                    "服务商 {provider} 成功加载 {count} 个站点。",
                    provider=prov.provider,
                    count=len(result),
                )

    async def fetch_all_providers(self) -> Dict[str, Any]:
        """并发获取所有服务商的数据"""
        results = {}

        async with aiohttp.ClientSession() as session:
            tasks = []

            for prov in self.providers:
                # fetch_status 负责返回 List[Dict] 且 Dict 已规范化
                tasks.append(prov.fetch_status(session))

            fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for prov, result in zip(self.providers, fetch_results):
                provider_key = prov.provider
                if isinstance(result, Exception):
                    logfire.error(
                        "服务商 {provider} 获取数据失败: {error}",
                        provider=provider_key,
                        error=str(result),
                    )
                    results[provider_key] = {
                        "status": "error",
                        "data": None,
                        "error": str(result),
                    }
                elif result is None:
                    results[provider_key] = {
                        "status": "error",
                        "data": None,
                        "error": "抓取失败或返回空数据",
                    }
                else:
                    results[provider_key] = {
                        "status": "success",
                        "data": result,
                        "error": None,
                    }

        return results

    def merge_stations(self, providers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """合并多个服务商的站点数据到统一格式"""
        all_stations = []

        for result in providers_data.values():
            if result["status"] == "success" and result["data"] is not None:
                data = result["data"]

                # 假设 fetch_status 严格返回 List[Dict[str, Any]]
                if isinstance(data, list):
                    # 无需再进行规范化，直接扩展列表
                    all_stations.extend(data)

        return all_stations

    async def fetch_and_format(self, provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取数据并格式化为 API 响应格式"""

        if provider:
            provider_obj = next(
                (prov for prov in self.providers if prov.provider == provider), None
            )
            if provider_obj is None:
                logfire.error("未找到服务商: {provider}", provider=provider)
                return None

            async with aiohttp.ClientSession() as session:
                stations = await provider_obj.fetch_status(session)

                if stations is None:
                    return None

                # 直接返回单个服务商的结果
                return {"updated_at": _now_utc8_iso(), "stations": stations}

        # 获取所有服务商数据
        providers_data = await self.fetch_all_providers()
        stations = self.merge_stations(providers_data)

        # 即使 stations 为空列表，也应返回格式化的结构
        return {"updated_at": _now_utc8_iso(), "stations": stations}
