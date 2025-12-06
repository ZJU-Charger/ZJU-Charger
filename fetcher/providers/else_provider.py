from fetcher.providers.provider_base import ProviderBase
from typing import List, Dict, Any, Optional, Tuple
import aiohttp
import asyncio
from fetcher.station import Station, load_stations_from_csv
from server.config import Config
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class ElseProvider(ProviderBase):
    def __init__(self):
        super().__init__()
        self.opentool_token = Config.get_provider_config_value(
            "else_provider", "opentool_token", ""
        )

    @property
    def provider(self) -> str:
        return "其他"

    def load_station_from_csv(self) -> List[Station]:
        csv_filename = f"else_stations.csv"
        csv_path = self.DATA_DIR / csv_filename
        if not csv_path.exists():
            print(f"Warning: Station file not found for provider '其他' at {csv_path}")
            self.station_list = []
            return []
        self.station_list = load_stations_from_csv(csv_path)
        return self.station_list

    async def fetch_station_list(
        self, session: aiohttp.ClientSession
    ) -> Optional[List[Dict[str, Any]]]:
        return []

    async def fetch_device_status(
        self, station: Station, device_id: str, session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        if station.provider == "万充科技":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "点点畅行":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "超翔科技":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "河狸物联":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "电动车充电网":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "多航科技":
            url = "https://mini.opencool.top/api/device.device/scan"
            headers = {
                "Content-Type": "application/json",
                "token": self.opentool_token,
            }
            data = {
                "sn": f"GD1B{device_id}",
                "_sn": f"GD1B{device_id}",
                "is_check": 0,
                "new_rule": 1,
            }
            try:
                async with session.post(url, headers=headers, json=data) as resp:
                    resp_data = await resp.json()
                    data = resp_data.get("data", {})
                    # name = data.get("device_data", "").get("description", "")
                    port_list = data.get("port_list", [])

                    free = used = total = error = 0
                    for port in port_list:
                        if port.get("status_text") == "使用中":
                            used += 1
                        elif port.get("status_text") == "空闲":
                            free += 1
                        else:
                            error += 1
                    total = free + used + error
                    return {"total": total, "free": free, "used": used, "error": error}, None
            except Exception as exc:
                return {"total": 0, "free": 0, "used": 0, "error": 0}, exc
        elif station.provider == "威可迪换电":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "待补充":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        elif station.provider == "嘟嘟换电":
            url = f"https://api.dudugxcd.com/sharing-citybike-consumer/site/v2/map/info?id={device_id}"  # good!
            try:
                async with session.get(url, headers={"oem_code": "citybike"}) as resp:
                    data = await resp.json()
                    if data.get("code") != 200:
                        error_msg = data.get("message", "Unknown API Error")
                        return {"total": 0, "free": 0, "used": 0, "error": 0}, Exception(error_msg)
                    exchange_vo = data.get("data", {}).get("cbExchangeVOList")
                    free = data.get(
                        "data", {}
                    ).get(
                        "storeTake"
                    )  # 这里没有弄清楚其能用的标准是什么，free就不按照一个电站进行统计了，经过了验证
                    used = error = total = 0
                    if exchange_vo and isinstance(exchange_vo, list):  # 按电站来计算
                        for device in exchange_vo:
                            upload_vo = (
                                device.get("cbExchangeUploadVO", {})
                                if isinstance(device, dict)
                                else {}
                            )
                            used += upload_vo.get("storeNull", 0)  # 这个是对的
                            error += upload_vo.get("storeLowPowerBatteryCharge", 0) + upload_vo.get(
                                "storeSoftLock", 0
                            )  # 这个不一定是对的
                            total += upload_vo.get("storeCount", 0)  # 这个是对的
                    return {"total": total, "free": free, "used": used, "error": error}, None
            except Exception as exc:
                return {"total": 0, "free": 0, "used": 0, "error": 0}, exc
        else:
            return None, ValueError(f"Unknown provider: {station.provider}")

    async def fetch_station_status(
        self, station: Station, session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        if station.provider == "专用站点":
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None
        else:
            tasks = [
                self.fetch_device_status(station, device_id, session)
                for device_id in station.device_ids
            ]
            results = await asyncio.gather(*tasks)
            total = 0
            free = 0
            used = 0
            error = 0
            for data, exc in results:
                if exc or data is None:
                    continue
                total += data["total"]
                free += data["free"]
                used += data["used"]
                error += data["error"]
        return {"total": total, "free": free, "used": used, "error": error}, None

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
                        "provider": station.provider,
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
            else:
                final_list.append(
                    {
                        "provider": station.provider,
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
