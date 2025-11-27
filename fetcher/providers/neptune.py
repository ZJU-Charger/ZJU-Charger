"""尼普顿服务商适配器"""
import aiohttp
import asyncio
import json
import requests
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..provider_base import ProviderBase

logger = logging.getLogger(__name__)


class NeptuneProvider(ProviderBase):
    """尼普顿充电桩服务商适配器"""

    @property
    def provider_id(self) -> str:
        return "neptune"

    @property
    def provider_name(self) -> str:
        return "尼普顿"

    def __init__(self):
        self.stations_file = Path(__file__).parent.parent.parent / "data" / "stations.json"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        pass

    # ---------------------------------------------
    # 1️⃣ 获取单个设备信息（你要求 API 写在这里）
    # ---------------------------------------------
    def fetch_device_info(self, areaid: int, devaddress: str):
        """同步获取单个设备信息"""
        url = "http://www.szlzxn.cn/wxn/getDeviceInfo"
        data = {
            "areaId": 6,
            "devaddress": devaddress
        }
        # print(devaddress)

        try:
            resp = requests.post(url, data=data, timeout=10)
            # print(resp.json())
            # print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
            return resp.json()
        except Exception:
            print(f"ERROR: {devaddress}")
            return -2

    # async def fetch_device_info(self, areaid: int, devaddress: str) -> Any:
    #     data = {
    #         "areaId": str(areaid),
    #         "devaddress": str(devaddress)
    #     }

    #     headers = {
    #         "Content-Type": "application/x-www-form-urlencoded",
    #         "User-Agent": "Mozilla/5.0"
    #     }

    #     timeout = aiohttp.ClientTimeout(total=10)

    #     async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
    #         try:
    #             async with session.post(
    #                 "http://www.szlzxn.cn/wxn/getDeviceInfo",
    #                 data=data
    #             ) as resp:

    #                 text = await resp.text()
    #                 print("DEBUG resp text:", text)

    #                 try:
    #                     return json.loads(text)
    #                 except:
    #                     return -2

    #         except Exception as e:
    #             print("ERROR:", e)
    #             return -2



    # ---------------------------------------------
    # 抽象方法实现
    # ---------------------------------------------
    
    async def fetch_stations(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取站点列表
        
        Returns:
            站点列表，如果失败返回 None
        """
        if not self.stations_file.exists():
            logger.error(f"站点文件不存在: {self.stations_file}")
            return None

        try:
            data = json.load(open(self.stations_file, "r", encoding="utf-8"))
            return data.get("neptune", [])
        except Exception as e:
            logger.error(f"加载站点失败: {e}", exc_info=True)
            return None
    
    async def fetch_status(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取站点状态数据
        
        Returns:
            统一格式的站点列表，每个站点包含：
            - provider_id: 服务商标识
            - provider_name: 服务商显示名称
            - id: 站点唯一标识
            - name: 站点名称
            - campus: 校区ID
            - lat: 纬度
            - lon: 经度
            - free: 可用数量
            - total: 总数
            - used: 已用数量
            - error: 故障数量
        """
        stations = await self.fetch_stations()
        if not stations:
            return None

        tasks = []
        ordered = []  # 记录任务对应的设备

        for st in stations:
            tasks.append(
                asyncio.to_thread(
                    self.fetch_device_info,
                    6,
                    st["devaddress"]
                )
            )
            ordered.append((st["devaddress"], st))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 先收集所有设备数据，然后按 id 聚合
        device_list = []

        for (devaddress, dev), result in zip(ordered, results):
            # devaddress 是设备地址，dev 是设备信息
            # result 是 抓取到的设备使用情况
            if isinstance(result, Exception) or result in (-1, -2):
                continue

            obj = result.get("obj")
            if not obj:
                continue
            
            port = obj.get("portstatur", "")
            available = port.count("0")
            used = port.count("1")
            error = port.count("3")
            total = len(port)
            
            # 获取站点名称（devdescript）
            site_name = dev.get("devdescript", "未知站点")
            
            # 生成 id（使用 gen_area_hash）
            station_id = self.gen_area_hash(self.provider_name, site_name, devaddress)
            
            # 在原有 station 信息基础上添加状态信息
            device_data = {
                "devid": dev.get("devid"),
                "devaddress": dev["devaddress"],
                "site_name": site_name,
                "latitude": dev.get("latitude", 30.27),
                "longitude": dev.get("longitude", 120.12),
                "available": available,
                "used": used,
                "error": error,
                "total": total,
                "areaid": dev.get("areaid", 6),
                "station_id": station_id  # 添加 station_id 用于聚合
            }
            
            device_list.append(device_data)

        # 按 id 聚合设备，直接生成统一格式
        aggregated = {}
        for device in device_list:
            station_id = device["station_id"]
            
            if station_id not in aggregated:
                # 第一个设备，创建聚合条目（统一格式）
                aggregated[station_id] = {
                    "provider_id": self.provider_id,
                    "provider_name": self.provider_name,
                    "id": station_id,
                    "name": device.get("site_name", "未知站点"),
                    "campus": device.get("areaid", 6),
                    "lat": device.get("latitude", 30.27),
                    "lon": device.get("longitude", 120.12),
                    "free": device["available"],
                    "total": device["total"],
                    "used": device["used"],
                    "error": device["error"],
                }
            else:
                # 后续相同 id 的设备，累加数值
                aggregated[station_id]["free"] += device["available"]
                aggregated[station_id]["total"] += device["total"]
                aggregated[station_id]["used"] += device["used"]
                aggregated[station_id]["error"] += device["error"]
        
        return list(aggregated.values())
    
    def gen_area_hash(self, provider_name: str, site_name: str, devaddress: str) -> str:
        """生成充电区域的 hash 值
        
        使用 provider_name 和 site_name 的组合生成 hash。
        对于尼普顿服务商，相同 site_name（devdescript）的设备应该属于同一个充电区域，
        因此相同 site_name 的设备会返回相同的 area_hash。
        
        注意：虽然参数包含 devaddress，但对于尼普顿来说，相同 site_name 的设备
        应该属于同一个充电区域，所以不使用 devaddress 来区分。
        
        Args:
            provider_name: 服务商显示名称（如 '尼普顿'）
            site_name: 站点名称（devdescript）
            devaddress: 设备地址（此参数保留以符合接口，但尼普顿不使用它来区分区域）
            
        Returns:
            hash 字符串，用于标识充电区域
        """
        # 对于尼普顿，使用 provider_name 和 site_name 来生成区域 hash
        # 相同 site_name 的设备属于同一个充电区域，会返回相同的 hash
        hash_input = f"{provider_name}:{site_name}"
        hash_obj = hashlib.md5(hash_input.encode('utf-8'))
        return hash_obj.hexdigest()[:8]
    
