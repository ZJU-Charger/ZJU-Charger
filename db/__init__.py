# db/__init__.py
"""
数据库操作模块的公共接口 (Repository Layer)
统一对外暴露的函数，避免外部模块直接依赖 db 目录下的子文件结构。
"""

# --- 0. 客户端配置和管理 ---
# 导入并暴露配置入口，这是实现解耦的关键
from .client import (
    initialize_supabase_config,
    get_supabase_client,
    reset_supabase_client,
)

# --- 1. 站点元数据仓库 (stations 表) ---
from .station_repo import (
    upsert_station,
    batch_upsert_stations,
    fetch_station_metadata,
    fetch_all_stations_data,  # 低耦合查询接口，返回 List[Dict]
)

# --- 2. 使用数据仓库 (usage, latest 表) ---
from .usage_repo import (
    insert,  # 单条插入接口
    batch_insert,  # 批量插入接口
    load_latest,  # 读取最新缓存接口
)

# --- 3. 业务管道 (核心写入逻辑) ---
from .pipeline import record_usage_data

# 统一导出所有公共接口
__all__ = [
    # 客户端配置
    "initialize_supabase_config",
    "get_supabase_client",
    "reset_supabase_client",
    # station_repo
    "upsert_station",
    "batch_upsert_stations",
    "fetch_station_metadata",
    "fetch_all_stations_data",
    # usage_repo
    "insert",
    "batch_insert",
    "load_latest",
    # pipeline
    "record_usage_data",
]
