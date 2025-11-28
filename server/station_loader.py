"""站点信息加载模块：从 API 获取站点列表并保存"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from server.config import Config
from fetcher.provider_manager import ProviderManager

logger = logging.getLogger(__name__)

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"
STATIONS_FILE = DATA_DIR / "stations.json"

# 确保 data 目录存在
DATA_DIR.mkdir(exist_ok=True)


def _get_timestamp():
    """获取当前时间戳（UTC+8）"""
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()


async def fetch_stations_from_providers() -> Optional[List[Dict[str, Any]]]:
    """从所有服务商获取站点列表

    通过获取站点状态数据，从中提取站点基础信息
    注意：需要从现有的 stations.json 中获取 simDevaddress（如果存在）

    Returns:
        站点列表，格式与 stations.json 兼容，如果失败返回 None
    """
    try:
        manager = ProviderManager()

        # 加载现有的 stations.json（如果存在），用于获取 simDevaddress
        existing_stations_map = {}
        if STATIONS_FILE.exists():
            try:
                with open(STATIONS_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    for station in existing_data.get("stations", []):
                        devaddress = station.get("devaddress")
                        if devaddress:
                            existing_stations_map[devaddress] = station
                logger.info(
                    f"加载了 {len(existing_stations_map)} 个现有站点信息（用于获取 simDevaddress）"
                )
            except Exception as e:
                logger.warning(f"加载现有站点信息失败: {e}，将使用空值")

        # 获取所有服务商的数据
        providers_data = await manager.fetch_all_providers()

        # 收集所有站点的基础信息
        all_stations = []

        for provider_id, result in providers_data.items():
            if result["status"] != "success" or result["data"] is None:
                logger.warning(
                    f"服务商 {provider_id} 数据获取失败: {result.get('error')}"
                )
                continue

            provider = manager.get_provider(provider_id)
            if provider is None:
                continue

            site_stats = result["data"].get("site_stats", {})

            # 从每个站点的状态数据中提取基础信息
            for site_name, stats in site_stats.items():
                devices = stats.get("devices", [])
                if not devices:
                    continue

                # 收集该站点的所有设备信息
                for device in devices:
                    devaddress = device.get("devaddress")

                    # 尝试从现有站点信息中获取 simDevaddress
                    sim_devaddress = ""
                    if devaddress and devaddress in existing_stations_map:
                        sim_devaddress = existing_stations_map[devaddress].get(
                            "simDevaddress", ""
                        )

                    station_info = {
                        "devid": device.get("devid"),
                        "devaddress": devaddress,
                        "campus": stats.get("areaid"),  # 使用 campus 字段（原 areaid）
                        "devdescript": site_name,  # 使用站点名称作为 devdescript
                        "longitude": device.get("longitude"),
                        "latitude": device.get("latitude"),
                        "simDevaddress": sim_devaddress,
                        "provider_id": provider_id,  # 添加服务商信息
                        "provider_name": provider.provider_name,
                    }

                    # 验证必需字段
                    if all(
                        [
                            station_info["devid"] is not None,
                            station_info["devaddress"],
                            station_info["longitude"],
                            station_info["latitude"],
                        ]
                    ):
                        all_stations.append(station_info)
                    else:
                        logger.warning(f"跳过无效站点设备: {station_info}")

        logger.info(
            f"成功从 {len(providers_data)} 个服务商获取 {len(all_stations)} 个站点设备"
        )
        return all_stations

    except Exception as e:
        logger.error(f"获取站点列表失败: {str(e)}", exc_info=True)
        return None


def extract_station_info(stations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提取站点关键信息并转换为 stations.json 格式

    Args:
        stations: 从服务商获取的站点列表（包含 provider_id, provider_name, campus）

    Returns:
        提取后的站点信息列表（stations.json 格式，保留 areaid 以兼容旧代码）
    """
    extracted = []

    for station in stations:
        # 转换为 stations.json 格式
        # 注意：stations.json 中仍使用 areaid 字段以保持兼容性
        info = {
            "devid": station.get("devid"),
            "devaddress": station.get("devaddress"),
            "areaid": station.get("campus"),  # campus 转换为 areaid（兼容旧格式）
            "devdescript": station.get("devdescript", ""),
            "longitude": station.get("longitude"),
            "latitude": station.get("latitude"),
            "simDevaddress": station.get("simDevaddress", ""),
            # 可选：添加服务商信息（如果 stations.json 需要支持多服务商）
            "provider_id": station.get("provider_id"),
            "provider_name": station.get("provider_name"),
        }

        # 验证必需字段
        if all(
            [
                info["devid"] is not None,
                info["devaddress"],
                info["longitude"],
                info["latitude"],
            ]
        ):
            extracted.append(info)
        else:
            logger.warning(f"跳过无效站点: {info}")

    return extracted


def save_stations(stations_data):
    """保存站点信息到文件

    Args:
        stations_data: 站点数据列表

    Returns:
        是否保存成功
    """
    try:
        data = {"updated_at": _get_timestamp(), "stations": stations_data}

        with open(STATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"站点信息已保存到 {STATIONS_FILE}，共 {len(stations_data)} 个站点")
        return True
    except Exception as e:
        logger.error(f"保存站点信息失败: {str(e)}", exc_info=True)
        return False


def load_stations():
    """从文件加载站点信息

    Returns:
        站点数据，如果文件不存在或读取失败返回 None
    """
    if not STATIONS_FILE.exists():
        logger.warning(f"站点文件不存在: {STATIONS_FILE}")
        return None

    try:
        with open(STATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"从文件加载站点信息，共 {len(data.get('stations', []))} 个站点")
        return data
    except Exception as e:
        logger.error(f"加载站点信息失败: {str(e)}", exc_info=True)
        return None


async def refresh_stations():
    """刷新站点信息（从所有服务商获取并保存）

    使用 ProviderManager 从所有服务商获取站点状态数据，
    从中提取站点基础信息并保存到 stations.json

    Returns:
        是否成功
    """
    logger.info("开始从所有服务商获取站点信息...")
    stations = await fetch_stations_from_providers()

    if stations is None:
        logger.error("获取站点信息失败")
        return False

    if not stations:
        logger.error("没有获取到任何站点信息")
        return False

    # 提取关键信息并转换为 stations.json 格式
    extracted = extract_station_info(stations)

    if not extracted:
        logger.error("没有提取到有效的站点信息")
        return False

    # 保存到文件
    if save_stations(extracted):
        logger.info(f"站点信息刷新成功，共 {len(extracted)} 个站点设备")
        return True
    else:
        logger.error("保存站点信息失败")
        return False
