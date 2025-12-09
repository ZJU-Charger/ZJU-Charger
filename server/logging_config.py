"""logfire 配置兼容模块."""

from typing import Any, Optional

import logfire

from server.logfire_setup import ensure_logfire_configured


def setup_logging(level: Optional[Any] = None, log_file: Optional[str] = None):
    """保持与旧接口兼容，转而初始化 logfire。"""
    ensure_logfire_configured()
    if log_file:
        logfire.warn(
            "logfire 当前不支持写入自定义日志文件，忽略 log_file 参数",
            log_file=log_file,
        )
    if level is not None:
        logfire.info(
            "logfire 使用固定日志级别，忽略传入 level 参数: {level}",
            level=str(level),
        )
    return logfire
