# db/client.py

"""SQLite 客户端管理"""

import os
import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import logfire

from server.logfire_setup import ensure_logfire_configured

ensure_logfire_configured()

_db_connection: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None


def get_default_db_path() -> str:
    """获取默认数据库文件路径"""
    # 默认放在项目根目录下的 data 文件夹
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / "charger.db")


def initialize_db_config(db_path: Optional[str] = None) -> bool:
    """
    【配置入口】
    设置 SQLite 数据库文件路径，并初始化数据库结构。

    Args:
        db_path: 数据库文件路径，如果为 None 则使用默认路径

    Returns:
        是否成功初始化
    """
    global _db_path

    if db_path is None:
        db_path = get_default_db_path()

    _db_path = db_path

    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # 初始化数据库结构
    try:
        conn = get_db_client()
        if conn is None:
            logfire.error("数据库连接失败，无法初始化结构")
            return False

        # 读取并执行 schema.sql
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with open(schema_path) as f:
                schema_sql = f.read()
            conn.executescript(schema_sql)
            conn.commit()
            logfire.info("数据库结构初始化成功")
        else:
            logfire.warn("未找到 schema.sql 文件，跳过表结构初始��")

        return True
    except Exception as e:
        logfire.error("数据库初始化失败: {error}", error=str(e))
        return False


def get_db_client() -> Optional[sqlite3.Connection]:
    """获取 SQLite 数据库连接实例（单例模式）"""
    global _db_connection, _db_path

    # 1. 如果连接已存在且有效，直接返回
    if _db_connection is not None:
        return _db_connection

    # 2. 检查路径是否已配置
    if not _db_path:
        _db_path = get_default_db_path()

    try:
        # 3. 创建 SQLite 连接
        _db_connection = sqlite3.connect(
            _db_path,
            check_same_thread=False,  # 允许多线程使用
        )
        _db_connection.row_factory = sqlite3.Row  # 返回字典风格的结果
        logfire.info("SQLite 数据库连接成功: {db_path}", db_path=_db_path)
        return _db_connection
    except Exception as e:
        logfire.error("SQLite 数据库连接失败: {error}", error=str(e))
        return None


def reset_db_client():
    """重置数据库连接实例（用于测试或重新配置）"""
    global _db_connection

    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
        logfire.info("数据库连接已重置（配置保持不变）")


# 辅助函数：处理 JSON 字段（device_ids）


def _json_to_sqlite(value: Any) -> str:
    """将 Python 对象转换为 SQLite 存储的 JSON 字符串"""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _sqlite_to_json(value: Any) -> Any:
    """将 SQLite 读取的 JSON 字符串转换为 Python 对象"""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return value


# 辅助函数：构建查询条件


def _build_where_clause(filters: Dict[str, Any]) -> tuple[str, List[Any]]:
    """
    构建 WHERE 子句

    Returns:
        (where_clause, params) 元组
    """
    conditions = []
    params = []

    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            # IN 查询
            placeholders = ",".join(["?" for _ in value])
            conditions.append(f"{key} IN ({placeholders})")
            params.extend(value)
        else:
            conditions.append(f"{key} = ?")
            params.append(value)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    return where_clause, params


# 执行查询的辅助函数


def execute_query(
    query: str, params: Optional[List[Any]] = None, fetch: str = "all"
) -> List[Dict[str, Any]] | Dict[str, Any] | None:
    """
    执行查询并返回结果

    Args:
        query: SQL 查询语句
        params: 查询参数
        fetch: "all", "one", 或 None（不获取结果）

    Returns:
        fetch="all" 时返回 List[Dict]，fetch="one" 时返回 Dict 或 None
    """
    conn = get_db_client()
    if conn is None:
        return [] if fetch == "all" else None

    try:
        cursor = conn.cursor()
        cursor.execute(query, params or [])

        if fetch == "all":
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        elif fetch == "one":
            row = cursor.fetchone()
            return dict(row) if row else None
        return []
    except Exception as e:
        logfire.error("查询执行失败: {error}, query: {query}", error=str(e), query=query)
        return [] if fetch == "all" else None


def execute_update(query: str, params: Optional[List[Any]] = None) -> bool:
    """
    执行更新/插入/删除操作

    Args:
        query: SQL 语句
        params: 参数

    Returns:
        是否成功
    """
    conn = get_db_client()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        conn.commit()
        return True
    except Exception as e:
        logfire.error("更新执行失败: {error}, query: {query}", error=str(e), query=query)
        conn.rollback()
        return False


def execute_upsert(table: str, data: Dict[str, Any], conflict_column: str = "hash_id") -> bool:
    """
    执行 UPSERT 操作（SQLite 的 INSERT OR REPLACE）

    Args:
        table: 表名
        data: 数据字典
        conflict_column: 冲突检测列

    Returns:
        是否成功
    """
    conn = get_db_client()
    if conn is None:
        return False

    try:
        columns = list(data.keys())
        placeholders = ",".join(["?" for _ in columns])
        column_names = ",".join(columns)

        # 处理 device_ids 字段
        values = []
        for key in columns:
            value = data[key]
            if key == "device_ids":
                value = _json_to_sqlite(value)
            values.append(value)

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT({conflict_column}) DO UPDATE SET
                {", ".join([f"{col}=excluded.{col}" for col in columns if col != conflict_column])}
        """

        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        logfire.error("UPSERT 失败: {error}, table: {table}", error=str(e), table=table)
        conn.rollback()
        return False


def execute_batch_upsert(
    table: str, data_list: List[Dict[str, Any]], conflict_column: str = "hash_id"
) -> bool:
    """
    批量执行 UPSERT 操作

    Args:
        table: 表名
        data_list: 数据字典列表
        conflict_column: 冲突检测列

    Returns:
        是否成功
    """
    if not data_list:
        return True

    conn = get_db_client()
    if conn is None:
        return False

    try:
        columns = list(data_list[0].keys())
        placeholders = ",".join(["?" for _ in columns])
        column_names = ",".join(columns)

        # 处理 device_ids 字段
        values_list = []
        for data in data_list:
            values = []
            for key in columns:
                value = data[key]
                if key == "device_ids":
                    value = _json_to_sqlite(value)
                values.append(value)
            values_list.append(values)

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT({conflict_column}) DO UPDATE SET
                {", ".join([f"{col}=excluded.{col}" for col in columns if col != conflict_column])}
        """

        cursor = conn.cursor()
        cursor.executemany(query, values_list)
        conn.commit()
        return True
    except Exception as e:
        logfire.error("批量 UPSERT 失败: {error}, table: {table}", error=str(e), table=table)
        conn.rollback()
        return False
