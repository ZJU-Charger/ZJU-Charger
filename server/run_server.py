#!/usr/bin/env python3
"""
快速启动 FastAPI 服务器

用法:
    python -m server.run_server
    python -m server.run_server --host 0.0.0.0 --port 8000
    python -m server.run_server --log-file logs/server.log  # 保存日志到文件
"""

import argparse
import sys

import logfire
import uvicorn

from server.background_fetcher import BackgroundFetcher
from server.logfire_setup import ensure_logfire_configured
from server.config import Config
from db import initialize_db_config, get_db_client


def check_and_init_database() -> bool:
    """检查并初始化数据库"""
    try:
        print("正在初始化数据库...")
        db_path = Config.SQLITE_DB_PATH if Config.SQLITE_DB_PATH else None
        if initialize_db_config(db_path):
            print("✅ 数据库初始化成功")
            return True
        else:
            print("❌ 数据库初始化失败")
            return False
    except Exception as e:
        print(f"❌ 数据库初始化错误: {e}")
        return False


def check_sqlite_available() -> bool:
    """检查 SQLite3 是否可用"""
    try:
        import sqlite3

        # 测试创建一个临时数据库
        conn = sqlite3.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()
        print("✅ SQLite3 支持正常")
        return True
    except Exception as e:
        print(f"❌ SQLite3 不可用: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动 ZJU Charger API 服务器")
    parser.add_argument("--host", default=Config.API_HOST, help="服务器地址")
    parser.add_argument("--port", type=int, default=Config.API_PORT, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="启用自动重载（开发模式）")
    parser.add_argument("--log-file", help="日志文件路径（可选）")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--skip-db-check",
        action="store_true",
        help="跳过数据库检查（适用于数据库已在外部初始化的情况）",
    )

    args = parser.parse_args()

    ensure_logfire_configured()
    separator = "=" * 60

    logfire.info("{separator}", separator=separator)
    logfire.info("ZJU Charger API 服务器启动")
    logfire.info("{separator}", separator=separator)

    # 检查 SQLite3 可用性
    print("\n🔍 检查 SQLite3 支持...")
    if not check_sqlite_available():
        print("\n❌ 错误: SQLite3 不可用，无法启动服务器")
        print("SQLite3 是 Python 标准库的一部分，请检查 Python 安装。")
        sys.exit(1)

    # 初始化数据库（除非跳过检查）
    if not args.skip_db_check:
        print("\n🗄️  初始化数据库...")
        if not check_and_init_database():
            print("\n❌ 错误: 数据库初始化失败，无法启动服务器")
            sys.exit(1)
    else:
        print("\n⏭️  跳过数据库检查（由 --skip-db-check 指定）")

    print()
    logfire.info("服务器地址: http://{host}:{port}", host=args.host, port=args.port)
    logfire.info("API 文档: http://{host}:{port}/docs", host=args.host, port=args.port)
    logfire.info("前端页面: http://{host}:{port}/web/", host=args.host, port=args.port)
    logfire.info("{separator}", separator=separator)

    BackgroundFetcher().start()

    uvicorn.run(
        "server.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # 使用我们自己的日志配置
    )
