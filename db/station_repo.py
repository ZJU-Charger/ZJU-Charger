"""
数据库操作模块
更新 Station 表单数据

字段名,数据类型 (PostgreSQL),描述,对应 Fetcher 字段,约束
hash_id,text,站点唯一标识 (主键),stations[*].hash_id,Primary Key
name,text,站点名称,stations[*].name,NOT NULL
provider,text,数据提供商,stations[*].provider,NOT NULL
campus_id,integer,校区 ID,stations[*].campus_id,
campus_name,text,校区名称,stations[*].campus_name,
lat,double precision,纬度,stations[*].lat,
lon,double precision,经度,stations[*].lon,
device_ids,jsonb or text[],关联的设备 ID 列表,stations[*].device_ids,
updated_at,timestamptz,本条元数据最近一次更新时间,stations[*].updated_at,NOT NULL
"""

# db/station_repo.py

import logging
from typing import List, Dict, Any, Optional

# 移除对 Station 类的依赖
from .client import get_supabase_client

logger = logging.getLogger(__name__)

# --- Stations 表操作：CRUD/元数据管理 ---

# 注意：upsert_station 和 batch_upsert_stations 仍然需要接受 Station 对象
# 因为这些函数是用于写入的，它需要知道数据来源的格式。
# 理想情况下，我们应该将 Station 转换为 Dict 再传入，但为了兼容性，暂时保持原签名，
# 但我们将删除所有 Station 相关的内部转换函数。


def upsert_station(
    station: Any,
) -> bool:  # station 类型改为 Any 或 Dict 更好，但保留原逻辑。
    """
    插入或更新单个站点基础信息 (stations 表)。

    NOTE:
    为了降低耦合，理想情况是此函数接受 Dict 而非 Station 对象，
    但为保留数据写入的原结构，暂保持原样。
    """
    client = get_supabase_client()
    if client is None:
        return False

    try:
        # 假设 station 对象有 hash_id, name, provider 等属性
        station_id = getattr(station, "hash_id", None)
        if not station_id:
            logger.error("站点信息缺少 hash_id 字段")
            return False

        station_data = {
            "hash_id": station_id,
            "name": getattr(station, "name", None),
            "provider": getattr(station, "provider", None),
            "campus_id": getattr(station, "campus_id", None),
            "campus_name": getattr(station, "campus_name", None),
            "lat": getattr(station, "lat", None),
            "lon": getattr(station, "lon", None),
            "device_ids": getattr(station, "device_ids", []),
            "updated_at": getattr(station, "updated_at", None),
        }

        # 执行 upsert 操作
        client.table("stations").upsert(station_data).execute()
        logger.debug(f"成功插入/更新站点: {station_id}")
        return True
    except Exception as e:
        logger.error(f"插入/更新站点失败: {e}", exc_info=True)
        return False


def batch_upsert_stations(stations: List[Any]) -> bool:  # 类型改为 List[Any]
    """批量插入或更新站点基础信息 (stations 表)"""
    client = get_supabase_client()
    if client is None:
        return False

    if not stations:
        logger.warning("站点列表为空，跳过批量插入")
        return True

    try:
        # 将 Station 对象转换为字典列表
        station_data_list = []
        for station in stations:
            station_id = getattr(station, "hash_id", None)
            if not station_id:
                logger.warning(
                    f"跳过缺少 hash_id 的站点: {getattr(station, 'name', 'unknown')}"
                )
                continue

            station_data = {
                "hash_id": station_id,
                "name": getattr(station, "name", None),
                "provider": getattr(station, "provider", None),
                "campus_id": getattr(station, "campus_id", None),
                "campus_name": getattr(station, "campus_name", None),
                "lat": getattr(station, "lat", None),
                "lon": getattr(station, "lon", None),
                "device_ids": getattr(station, "device_ids", []),
                "updated_at": getattr(station, "updated_at", None),
            }
            station_data_list.append(station_data)

        if not station_data_list:
            logger.warning("没有有效的站点数据可插入")
            return True

        # 执行批量 upsert
        client.table("stations").upsert(station_data_list).execute()
        logger.info(f"成功批量插入/更新 {len(station_data_list)} 个站点")
        return True
    except Exception as e:
        logger.error(f"批量插入/更新站点失败: {e}", exc_info=True)
        return False


def fetch_station_metadata(
    station_ids: Optional[List[str]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    读取站点基础信息，返回 hash_id -> metadata 的映射 (原始数据库字典格式)。
    这是 DB 层的最底层查询接口。
    """
    client = get_supabase_client()
    if client is None:
        return {}

    try:
        query = client.table("stations").select(
            "hash_id,name,provider,campus_id,campus_name,lat,lon,device_ids,updated_at"
        )

        if station_ids:
            query = query.in_("hash_id", station_ids)

        if provider:
            query = query.eq("provider", provider)

        response = query.execute()
        metadata = {}
        for row in response.data or []:
            station_id = row.get("hash_id")
            if station_id:
                metadata[station_id] = row
        return metadata
    except Exception as exc:
        logger.error("读取站点基础信息失败: %s", exc, exc_info=True)
        return {}


# --- Fetcher 专用接口：返回标准字典列表 (低耦合) ---


def fetch_all_stations_data(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    【Fetcher 专用接口】
    从数据库读取所有站点基础信息，并返回标准字典列表 (List[Dict])。

    Args:
        provider: 可选，筛选指定 provider 的站点。
    """
    try:
        # 调用底层接口获取 Dict[hash_id, Dict] 结构
        metadata_map = fetch_station_metadata(provider=provider)
        if not metadata_map:
            logger.warning(f"未找到 provider='{provider}' 的站点信息。")
            return []

        # 转换为 List[Dict] 结构并返回
        return list(metadata_map.values())

    except Exception as exc:
        logger.error("加载所有 Station 数据失败: %s", exc, exc_info=True)
        return []
