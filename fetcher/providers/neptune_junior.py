import aiohttp
import asyncio
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

from .provider_base import ProviderBase
from fetcher.station import Station
from server.config import Config


@dataclass
class NeptuneJuniorProvider(ProviderBase):
    """尼普顿智慧生活公众号服务商适配器"""

    token: str = ""

    def __post_init__(self):
        """初始化时从配置读取 openid 和 unionid"""
        self.openid = Config.get_provider_config_value("neptune_junior", "openid", "")
        self.unionid = Config.get_provider_config_value("neptune_junior", "unionid", "")

    @property
    def provider(self) -> str:
        return "neptune_junior"

    async def ensure_token(self, session: aiohttp.ClientSession):
        """如果 token 为空 → 请求一次"""
        if self.token:
            return self.token

        url = (
            f"https://gateway.hzxwwl.com/api/auth/wx/mp?openid={self.openid}&unionid={self.unionid}"
        )

        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            self.token = data.get("data", {}).get("token", "")
            return self.token

    # --- 抽象方法实现 ---
    async def fetch_station_list(
        self, session: aiohttp.ClientSession
    ) -> Optional[List[Dict[str, Any]]]:
        """TODO: 获取站点列表"""
        return None

    async def fetch_device_status(
        self, device_id: str, session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        try:
            await self.ensure_token(session)

            url = (
                "https://gateway.hzxwwl.com/api/charging/pile/"
                f"listChargingPileDistByArea?chargingAreaId={device_id}"
            )

            async with session.get(url, headers={"REQ-NPD-TOKEN": self.token}) as res:
                res.raise_for_status()
                resp = await res.json()

                data = resp.get("data", {})
                total = data.get("totalPileNumber", 0)
                free = data.get("totalFreeNumber", 0)
                error = data.get("totalTroubleNumber", 0)
                booking = data.get("totalBookingNumber", 0)
                upgrade = data.get("totalUpgradeNumber", 0)
                used = total - free - error - booking - upgrade
                return {
                    "total": total,
                    "free": free,
                    "used": used,
                    "error": error,
                    "booking": booking,
                }, None

        except Exception as e:
            return None, e

    async def fetch_station_status(
        self, station: Station, session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        tasks = [self.fetch_device_status(device_id, session) for device_id in station.device_ids]
        results = await asyncio.gather(*tasks)

        total = free = used = error = booking = 0

        for _, (data, exc) in zip(station.device_ids, results):
            if exc or data is None:
                continue
            total += data["total"]
            free += data["free"]
            used += data["used"]
            error += data["error"]
            booking += data["booking"]

        return {
            "total": total,
            "free": free,
            "used": used,
            "error": error,
            "booking": booking,
        }, None

    async def fetch_status(self, session: aiohttp.ClientSession) -> Optional[List[Dict[str, Any]]]:
        if not self.station_list:
            return []

        tasks = [self.fetch_station_status(station, session) for station in self.station_list]
        results = await asyncio.gather(*tasks)

        final_list = []

        for station, (status, exc) in zip(self.station_list, results):
            if exc or status is None:
                final_list.append(
                    {
                        "provider": self.provider,
                        "hash_id": station.hash_id,
                        "name": station.name,
                        "campus_id": station.campus_id,
                        "campus_name": station.campus_name,
                        "lat": station.lat,
                        "lon": station.lon,
                        "device_ids": station.device_ids,
                        "updated_at": station.updated_at,
                        "free": 0,
                        "used": 0,
                        "total": 0,
                        "error": 0,
                    }
                )
                continue

            final_list.append(
                {
                    "provider": self.provider,
                    "hash_id": station.hash_id,
                    "name": station.name,
                    "campus_id": station.campus_id,
                    "campus_name": station.campus_name,
                    "lat": station.lat,
                    "lon": station.lon,
                    "device_ids": station.device_ids,
                    "updated_at": station.updated_at,
                    "free": status["free"],
                    "used": status["used"],
                    "total": status["total"],
                    "error": status["error"],
                }
            )

        return final_list
