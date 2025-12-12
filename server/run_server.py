#!/usr/bin/env python3
"""
快速启动 FastAPI 服务器

用法:
    python -m server.run_server
    python -m server.run_server --host 0.0.0.0 --port 8000
    python -m server.run_server --log-file logs/server.log  # 保存日志到文件
"""

import argparse

import logfire
import uvicorn

from server.background_fetcher import BackgroundFetcher
from server.logfire_setup import ensure_logfire_configured
from .config import Config

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

    args = parser.parse_args()

    ensure_logfire_configured()
    separator = "=" * 60

    if args.log_file:
        logfire.warn(
            "logfire 日志目前不支持按文件输出，忽略 --log-file 参数",
            log_file=args.log_file,
        )
    if args.log_level.upper() != "INFO":
        logfire.warn(
            "logfire 日志暂不支持按 CLI 设置日志级别，收到的参数: {log_level}",
            log_level=args.log_level,
        )

    logfire.info("{separator}", separator=separator)
    logfire.info("ZJU Charger API 服务器启动")
    logfire.info("{separator}", separator=separator)
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
