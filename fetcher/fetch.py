import aiohttp
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class Fetcher:
    def __init__(self, openId):
        self.api_address = "http://www.szlzxn.cn/wxn/getStationList"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.60(0x18003c2f) NetType/WIFI Language/zh_CN",
            "Host": "www.szlzxn.cn",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        self.openId = openId
        self.status = True
        self.session = None
        # stations.json 路径（相对于项目根目录，在 data 文件夹中）
        self.stations_file = Path(__file__).parent.parent / "data" / "stations.json"
        # 向后兼容：如果 stations.json 不存在，尝试使用 location.json
        self.location_file = Path(__file__).parent.parent / "location.json"

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    def make_params(self, lat, lng):
        return {
            "openId": self.openId,
            "latitude": lat,
            "longitude": lng,
            "areaid": 6,
            "devtype": 0,
        }

    async def fetch(self, params, session=None):
        """异步获取单个站点的数据"""
        if session is None:
            session = self.session
        if session is None:
            async with aiohttp.ClientSession() as temp_session:
                return await self._fetch_with_session(params, temp_session)
        return await self._fetch_with_session(params, session)

    async def _fetch_with_session(self, params, session):
        """使用指定 session 进行请求"""
        max_retries = 5
        timeout = aiohttp.ClientTimeout(total=3)

        for attempt in range(max_retries):
            try:
                async with session.post(
                    self.api_address, headers=self.headers, data=params, timeout=timeout
                ) as response:
                    try:
                        json_data = await response.json()
                    except aiohttp.ContentTypeError:
                        # the response is not valid JSON
                        if attempt == max_retries - 1:
                            return -2
                        continue

                    # Check if the response contains the expected structure
                    if "success" not in json_data or json_data["success"] != True:
                        return -1
                    return json_data

            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    return -2
                continue
            except aiohttp.ClientError:
                if attempt == max_retries - 1:
                    return -2
                continue

    async def _fetch_single_device(self, detail, session, site_name):
        """异步获取单个设备的数据，包含站点信息"""
        devaddress = detail["devaddress"]
        devid = detail.get("devid")  # 获取 devid
        latitude = detail["latitude"]
        longitude = detail["longitude"]
        params = self.make_params(latitude, longitude)
        result = await self.fetch(params, session)

        # 错误处理
        if result == -1:
            print(f"Failed to fetch data for {devaddress}")
            return None, -1
        elif result == -2:
            print(f"Invalid JSON response for {devaddress}, retrying...")
            # 重试一次
            result = await self.fetch(params, session)
            if result == -1 or result == -2:
                print(f"Retry failed for {devaddress}")
                return None, -1

        # 解析结果
        for item in result.get("obj", []):
            if item.get("devaddress") == devaddress:
                portstatus = item.get("portstatus")
                if portstatus:
                    return {
                        "devid": devid,  # 包含 devid
                        "devaddress": devaddress,
                        "site_name": site_name,
                        "latitude": latitude,
                        "longitude": longitude,
                        "available": portstatus.count("0"),
                        "used": portstatus.count("1"),
                        "error": portstatus.count("3"),
                        "total": len(portstatus),
                    }, 0
                else:
                    print(f"Port status is None for {devaddress}")
                    return None, 0

        print(f"No matching device found for {devaddress}")
        return None, 0

    def _get_timestamp(self):
        """获取当前时间戳（UTC+8）"""
        tz_utc_8 = timezone(timedelta(hours=8))
        return datetime.now(tz_utc_8).isoformat()

    async def full_fetch(self):
        """异步并发获取所有站点数据，返回标准化格式"""
        # 优先使用 stations.json，如果不存在则使用 location.json（向后兼容）
        if self.stations_file.exists():
            logger.info(f"使用站点文件: {self.stations_file}")
            with open(self.stations_file, "r", encoding="utf-8") as f:
                stations_data = json.load(f)
            # 转换 stations.json 格式为兼容格式
            stations = stations_data.get("stations", [])
            # 直接使用所有station，每个设备使用devdescript作为站点名称
            data = {
                "sites_yq": [
                    {
                        "group_id": idx + 1,
                        "group_site_nums": 1,
                        "group_sim_name": station.get("devdescript", "未知站点"),
                        "details": [station],
                    }
                    for idx, station in enumerate(stations)
                ]
            }
        elif self.location_file.exists():
            logger.info(f"使用旧版站点文件: {self.location_file}")
            with open(self.location_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            logger.error(
                f"站点文件不存在: {self.stations_file} 或 {self.location_file}"
            )
            raise FileNotFoundError(
                f"站点文件不存在: {self.stations_file} 或 {self.location_file}"
            )

        # 确保有 session
        if self.session is None:
            self.session = aiohttp.ClientSession()
            should_close_session = True
        else:
            should_close_session = False

        try:
            all_tasks = []
            device_details_list = []  # 存储每个设备的详细信息

            # 为每个设备创建异步任务
            for site in data.get("sites_yq", []):
                site_name = site["group_sim_name"]
                for detail in site.get("details", []):
                    task = self._fetch_single_device(detail, self.session, site_name)
                    all_tasks.append(task)
                    device_details_list.append((site_name, detail))

            # 并发执行所有任务
            logger.info(f"开始异步抓取 {len(all_tasks)} 个设备...")
            print(f"Starting async fetch for {len(all_tasks)} devices...")
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # 处理结果，按站点分组统计
            site_stats = {}
            device_data_list = []

            for idx, result in enumerate(results):
                site_name, detail = device_details_list[idx]
                devaddress = detail["devaddress"]

                if isinstance(result, Exception):
                    logger.error(f"设备 {devaddress} 发生异常: {result}")
                    print(f"Exception occurred for {devaddress}: {result}")
                    continue

                device_data, status = result
                if status == -1:
                    logger.error(f"设备 {devaddress} 数据抓取失败")
                    print(f"Failed to fetch data for {devaddress}")
                    self.status = False
                    break

                if device_data:
                    # 保存设备数据
                    device_data_list.append(device_data)

                    # 获取 areaid（从 detail 中获取）
                    areaid = detail.get("areaid")

                    # 按站点分组统计
                    if site_name not in site_stats:
                        site_stats[site_name] = {
                            "site_total": 0,
                            "site_available": 0,
                            "site_used": 0,
                            "site_error": 0,
                            "areaid": areaid,  # 保存 areaid
                            "devices": [],
                        }

                    site_stats[site_name]["site_total"] += device_data["total"]
                    site_stats[site_name]["site_available"] += device_data["available"]
                    site_stats[site_name]["site_used"] += device_data["used"]
                    site_stats[site_name]["site_error"] += device_data["error"]
                    site_stats[site_name]["devices"].append(device_data)

            if not self.status:
                logger.error("完整抓取失败")
                print("Full fetch failed.")
                return -1

            # 封装站点组信息（旧格式，向后兼容）
            info = []
            for site_name, stats in site_stats.items():
                logger.info(
                    f"站点 {site_name} - 总数: {stats['site_total']}, 可用: {stats['site_available']}, 已用: {stats['site_used']}, 错误: {stats['site_error']}"
                )
                print(
                    f"Site {site_name} - Total: {stats['site_total']}, Available: {stats['site_available']}, Used: {stats['site_used']}, Error: {stats['site_error']}"
                )
                site_info = {
                    "site_name": site_name,
                    "site_total": stats["site_total"],
                    "site_available": stats["site_available"],
                    "site_used": stats["site_used"],
                    "site_error": stats["site_error"],
                }
                info.append(site_info)

            # 返回包含详细信息的格式
            return {
                "raw_data": info,  # 旧格式
                "site_stats": site_stats,  # 按站点分组
                "device_data": device_data_list,  # 所有设备数据
            }

        finally:
            if should_close_session and self.session:
                await self.session.close()
                self.session = None

    def format_to_api_response(self, fetch_result):
        """将 fetch_result 转换为标准 API 响应格式"""
        if fetch_result == -1:
            return None

        stations = []
        site_stats = fetch_result.get("site_stats", {})

        for site_name, stats in site_stats.items():
            # 计算站点的平均经纬度（使用第一个设备的坐标）
            # 收集该站点的所有 devid
            devids = []
            if stats["devices"]:
                first_device = stats["devices"][0]
                lat = first_device["latitude"]
                lon = first_device["longitude"]
                # 收集所有设备的 devid
                for device in stats["devices"]:
                    if device.get("devid") is not None:
                        devids.append(device["devid"])
            else:
                # 如果没有设备数据，使用默认值
                lat = 30.27
                lon = 120.12

            station = {
                "id": str(site_name),  # 使用站点名作为 ID（向后兼容）
                "name": site_name,
                "devids": devids,  # 添加 devid 列表
                "lat": lat,
                "lon": lon,
                "free": stats["site_available"],
                "total": stats["site_total"],
                "used": stats["site_used"],
                "error": stats["site_error"],
                "areaid": stats.get("areaid"),  # 包含 areaid
            }
            stations.append(station)

        return {"updated_at": self._get_timestamp(), "stations": stations}

    async def fetch_and_format(self):
        """获取数据并格式化为 API 响应格式"""
        result = await self.full_fetch()
        if result == -1:
            return None
        return self.format_to_api_response(result)


if __name__ == "__main__":

    async def test():
        async with Fetcher(" ") as fetcher:
            result = await fetcher.full_fetch()
            print(result)
            if result != -1:
                formatted = fetcher.format_to_api_response(result)
                print("\nFormatted API response:")
                print(json.dumps(formatted, ensure_ascii=False, indent=2))

    asyncio.run(test())
