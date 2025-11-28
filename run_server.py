#!/usr/bin/env python3
"""
快速启动 FastAPI 服务器

用法:
    python run_server.py
    python run_server.py --host 0.0.0.0 --port 8000
    python run_server.py --log-file logs/server.log  # 保存日志到文件
"""
import argparse
import logging
import uvicorn
from server.config import Config
from server.logging_config import setup_logging

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动 ZJU Charger API 服务器")
    parser.add_argument("--host", default=Config.API_HOST, help="服务器地址")
    parser.add_argument("--port", type=int, default=Config.API_PORT, help="服务器端口")
    parser.add_argument(
        "--reload", action="store_true", help="启用自动重载（开发模式）"
    )
    parser.add_argument("--log-file", help="日志文件路径（可选）")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )

    args = parser.parse_args()

    # 配置日志
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(level=log_level, log_file=args.log_file)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("ZJU Charger API 服务器启动")
    logger.info("=" * 60)
    logger.info(f"服务器地址: http://{args.host}:{args.port}")
    logger.info(f"API 文档: http://{args.host}:{args.port}/docs")
    logger.info(f"前端页面: http://{args.host}:{args.port}/web/")
    if args.log_file:
        logger.info(f"日志文件: {args.log_file}")
    logger.info("=" * 60)

    uvicorn.run(
        "server.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # 使用我们自己的日志配置
    )
