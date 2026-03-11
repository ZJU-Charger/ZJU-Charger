"""

usage 表

字段名,数据类型 (SQLite),描述,对应 Fetcher 字段,约束
id,INTEGER,记录唯一 ID (自增),N/A,Primary Key
hash_id,TEXT,站点唯一标识 (外键),stations[*].hash_id,NOT NULL (Foreign Key to stations.hash_id)
snapshot_time,TEXT,抓取时间 (来自 Fetcher),updated_at,NOT NULL
free,INTEGER,可用数量,stations[*].free,NOT NULL
used,INTEGER,已用数量,stations[*].used,NOT NULL
total,INTEGER,总数,stations[*].total,NOT NULL
error,INTEGER,故障数量,stations[*].error,NOT NULL


latest 表

字段名,数据类型 (SQLite),描述,对应 Fetcher 字段,约束
hash_id,TEXT,站点唯一标识 (主键),stations[*].hash_id,Primary Key (Foreign Key to stations.hash_id)
snapshot_time,TEXT,最新抓取时间 (来自 Fetcher),updated_at,NOT NULL
free,INTEGER,可用数量,stations[*].free,NOT NULL
used,INTEGER,已用数量,stations[*].used,NOT NULL
total,INTEGER,总数,stations[*].total,NOT NULL
error,INTEGER,故障数量,stations[*].error,NOT NULL
"""

# db/usage_repo.py

from typing import List, Dict, Any, Optional

import logfire

from server.logfire_setup import ensure_logfire_configured
from .client import (
    get_db_client,
    execute_upsert,
    execute_batch_upsert,
    execute_query,
)

ensure_logfire_configured()

LATEST_TABLE_NAME = "latest"
USAGE_TABLE_NAME = "usage"

# --- 公共接口实现 ---


def insert(data: Dict[str, Any], sheet_name: str) -> bool:
    """
    插入单条使用情况记录。

    Args:
        data: 包含单个站点信息的字典。
        sheet_name: 目标表单名称 ('latest' 或 'usage')。
    """
    if get_db_client() is None:
        return False

    table_name = sheet_name.lower()
    if table_name not in [LATEST_TABLE_NAME, USAGE_TABLE_NAME]:
        logfire.error("无效的表名: {sheet_name}", sheet_name=sheet_name)
        return False

    snapshot_time = data.get("snapshot_time") or data.get("updated_at")
    if not snapshot_time:
        logfire.error("插入 {table_name} 失败：缺少时间戳字段。", table_name=table_name)
        return False

    # 构建记录
    record = {
        "hash_id": data.get("id") or data.get("hash_id"),
        "snapshot_time": snapshot_time,
        "free": int(data.get("free", 0)),
        "used": int(data.get("used", 0)),
        "total": int(data.get("total", 0)),
        "error": int(data.get("error", 0)),
    }

    if not record["hash_id"]:
        logfire.warn("跳过单条插入：缺少 hash_id")
        return False

    # 必要的 try-catch 块，用于处理数据库交互错误
    try:
        if table_name == LATEST_TABLE_NAME:
            # 针对 latest 表使用 upsert (单条)
            return execute_upsert(table_name, record, conflict_column="hash_id")
        else:
            # 针对 usage 表使用 insert (单条)
            conn = get_db_client()
            if conn is None:
                return False

            columns = list(record.keys())
            placeholders = ",".join(["?" for _ in columns])
            column_names = ",".join(columns)

            query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
            cursor = conn.cursor()
            cursor.execute(query, list(record.values()))
            conn.commit()

            logfire.debug("成功插入 {table_name} 单条记录。", table_name=table_name)
            return True

    except Exception as e:
        logfire.error("执行单条数据库操作失败: {error}", error=str(e))
        return False


def batch_insert(data: Dict[str, Any], sheet_name: str) -> bool:
    """
    批量插入使用情况记录。

    Args:
        data: 包含 'stations' (List[Dict]) 和 'updated_at' (str) 的字典。
        sheet_name: 目标表单名称 ('latest' 或 'usage')。
    """
    if get_db_client() is None:
        return False

    table_name = sheet_name.lower()
    if table_name not in [LATEST_TABLE_NAME, USAGE_TABLE_NAME]:
        logfire.error("无效的表名: {sheet_name}", sheet_name=sheet_name)
        return False

    stations = data.get("stations", [])
    snapshot_time = data.get("updated_at")

    if not snapshot_time:
        logfire.error("批量插入 {table_name} 失败：缺少 updated_at 字段。", table_name=table_name)
        return False

    if not stations:
        logfire.warn("站点列表为空，跳过批量插入 {table_name}。", table_name=table_name)
        return True

    usage_records = []
    # 准备批量插入的数据
    for station in stations:
        station_id = station.get("id") or station.get("hash_id")
        if not station_id:
            continue  # 跳过缺少 id 的记录

        usage_records.append(
            {
                "hash_id": station_id,
                "snapshot_time": snapshot_time,
                "free": int(station.get("free", 0)),
                "used": int(station.get("used", 0)),
                "total": int(station.get("total", 0)),
                "error": int(station.get("error", 0)),
            }
        )

    if not usage_records:
        logfire.warn("没有有效的使用情况记录可插入 {table_name} 表。", table_name=table_name)
        return True

    # 必要的 try-catch 块
    try:
        # 针对 latest 表使用 upsert，针对 usage 表使用 insert
        if table_name == LATEST_TABLE_NAME:
            result = execute_batch_upsert(table_name, usage_records, conflict_column="hash_id")
            action = "更新/插入"
        else:
            conn = get_db_client()
            if conn is None:
                return False

            columns = list(usage_records[0].keys())
            placeholders = ",".join(["?" for _ in columns])
            column_names = ",".join(columns)

            query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
            cursor = conn.cursor()

            values_list = [list(record.values()) for record in usage_records]
            cursor.executemany(query, values_list)
            conn.commit()

            result = True
            action = "插入"

        if result:
            logfire.info(
                "成功批量 {action} {table_name} {count} 条记录。",
                action=action,
                table_name=table_name,
                count=len(usage_records),
            )
        return result

    except Exception as e:
        logfire.error("批量数据库操作失败: {error}", error=str(e))
        return False


def load_latest() -> Optional[Dict[str, Any]]:
    """
    从 SQLite latest 表读取缓存数据。
    返回格式: {"updated_at": latest_snapshot_time (str), "rows": List[Dict]}
    """
    if get_db_client() is None:
        return None

    try:
        query = """
            SELECT hash_id, snapshot_time, free, used, total, error
            FROM latest
        """

        result = execute_query(query)
        if not isinstance(result, list) or not result:
            logfire.warn("latest 表暂无缓存数据。")
            return None

        timestamps = [row.get("snapshot_time") for row in result if row.get("snapshot_time")]
        latest_timestamp = max(timestamps) if timestamps else None
        return {"updated_at": latest_timestamp, "rows": result}

    except Exception as exc:
        logfire.error("读取 latest 表失败: {error}", error=str(exc))
        return None
