"""尼普顿服务商适配器 - 简化版"""

import aiohttp
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

# 假设这些类和函数已定义或可导入
from .provider_base import ProviderBase
from fetcher.station import Station

logger = logging.getLogger(__name__)

# 确保 ClientSession 类型可用
ClientSession = aiohttp.ClientSession
TIMEOUT = aiohttp.ClientTimeout(total=5)
MAX_RETRIES = 5


@dataclass
class NeptuneProvider(ProviderBase):
    """尼普顿充电桩服务商适配器"""

    @property
    def provider(self) -> str:
        return "neptune"

    # --- 抽象方法实现 ---

    async def fetch_station_list(
        self, session: ClientSession
    ) -> Optional[List[Dict[str, Any]]]:
        """获取供应商 API 返回的所有站点列表 (原始数据)"""
        # TODO: 实现尼普顿的站点列表获取

        return None

    async def fetch_device_status(
        self, station: Station, device_id: str, session: ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """获取单个设备状态数据。通过 getStationList 接口并过滤 device_id。"""
        api_address: str = "http://www.szlzxn.cn/wxn/getDeviceInfo"

        for attempt in range(MAX_RETRIES):
            try:
                async with session.post(
                    api_address,
                    data={"areaId": 6, "devaddress": device_id},
                    timeout=TIMEOUT,
                ) as response:
                    response.raise_for_status()
                    json_data = await response.json()
                    if json_data.get("success") is not True:
                        return None, ValueError(
                            f"API failed for device {device_id}: {json_data.get('msg')}"
                        )

                    # 遍历返回的站点列表，找到匹配 device_id 的设备
                    item = json_data["obj"]
                    if str(item.get("devaddress")) == str(device_id):
                        # 返回包含 portstatur 的原始数据
                        return item, None

                    # 找到了API，但没找到设备
                    return None, ValueError(
                        f"Device {device_id} not found in API response. {json_data}"
                    )

            except (
                asyncio.TimeoutError,
                aiohttp.ClientError,
                json.JSONDecodeError,
            ) as e:
                if attempt == MAX_RETRIES - 1:
                    return None, e
                await asyncio.sleep(1)
                continue
        return None, Exception("Reached max retries fetching device status.")

    async def fetch_station_status(
        self, station: Station, session: ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """获取站点（包含其所有设备）的聚合状态数据。"""

        # 尼普顿模式下，我们必须对每个 device_id 执行一次 API 调用并聚合结果
        tasks = [
            self.fetch_device_status(station, device_id, session)
            for device_id in station.device_ids
        ]

        results = await asyncio.gather(*tasks)

        free = 0
        used = 0
        error = 0
        total = 0

        exceptions = []

        for device_id, (device_data, exc) in zip(station.device_ids, results):
            if exc or device_data is None:
                exceptions.append(exc or ValueError("No device data"))
                continue

            # 提取并聚合 portstatur 核心逻辑 (保持不变)
            portstatus = str(device_data.get("portstatur", ""))

            if not portstatus:
                logger.warning(
                    "Device %s status data has no 'portstatur' string.", device_id
                )
                continue
            # print(portstatus)
            free += portstatus.count("0")
            used += portstatus.count("1")
            error += portstatus.count("3")
            total = len(portstatus)

        # 站点聚合状态数据
        aggregated_status = {
            "provider": self.provider,
            "hash_id": station.hash_id,
            "name": station.name,
            "free": free,
            "used": used,
            "error": error,
            "total": total,
            "lat": station.lat,
            "lon": station.lon,
            "device_ids": station.device_ids,
        }

        # 仅在所有任务都失败时才返回异常
        if exceptions and len(exceptions) == len(station.device_ids):
            return None, exceptions[0]

        return aggregated_status, None

    async def fetch_status(
        self, session: ClientSession
    ) -> Optional[List[Dict[str, Any]]]:
        """获取供应商所有 station 的状态数据并转换为统一格式。"""

        if not self.station_list:
            return []

        tasks = [
            self.fetch_station_status(station, session) for station in self.station_list
        ]

        results = await asyncio.gather(*tasks)
        final_list: List[Dict[str, Any]] = []

        for station, (status_dict, exc) in zip(self.station_list, results):

            # 失败处理：返回全故障条目
            if exc or status_dict is None:
                total_ports = sum(
                    len(d) for d in station.device_ids
                )  # 粗略估计端口总数
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
                        "total": (
                            status_dict.get("total", 0) if status_dict else total_ports
                        ),
                        "error": (
                            status_dict.get("total", 0) if status_dict else total_ports
                        ),
                    }
                )
                continue

            # 成功获取：合并元数据和状态数据
            formatted_item = {
                "provider": status_dict["provider"],
                "hash_id": status_dict["hash_id"],
                "name": status_dict["name"],
                "campus_id": station.campus_id,
                "campus_name": station.campus_name,
                "lat": status_dict["lat"],
                "lon": status_dict["lon"],
                "device_ids": status_dict["device_ids"],
                "updated_at": station.updated_at,
                "free": status_dict["free"],
                "used": status_dict["used"],
                "total": status_dict["total"],
                "error": status_dict["error"],
            }
            final_list.append(formatted_item)

        return final_list
