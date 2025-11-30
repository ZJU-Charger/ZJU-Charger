# db/client.py

"""Supabase 客户端管理"""

import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_supabase_client: Optional[Client] = None
_supabase_url: Optional[str] = None
_supabase_key: Optional[str] = None


def initialize_supabase_config(url: str, key: str):
    """
    【配置入口】
    在应用启动时，设置 Supabase 的连接 URL 和 Key。
    该函数必须在首次调用 get_supabase_client() 之前被调用。
    """
    global _supabase_url, _supabase_key

    if not url or not key:
        logger.error("Supabase URL 或 Key 为空，配置失败。")
        return

    _supabase_url = url
    _supabase_key = key
    logger.info("Supabase 配置参数已设置。")


def get_supabase_client() -> Optional[Client]:
    """获取 Supabase 客户端实例（单例模式）。"""
    global _supabase_client, _supabase_url, _supabase_key

    # 1. 如果客户端已初始化，直接返回
    if _supabase_client is not None:
        return _supabase_client

    # 2. 检查配置是否已通过 initialize_supabase_config 设置
    if not _supabase_url or not _supabase_key:
        logger.warning(
            "Supabase URL 或 Key 未设置。请先调用 initialize_supabase_config() 进行配置。"
        )
        return None

    try:
        # 3. 创建 Supabase 客户端
        _supabase_client = create_client(_supabase_url, _supabase_key)
        logger.info("Supabase 客户端初始化成功")
        return _supabase_client
    except Exception as e:
        logger.error(f"Supabase 客户端初始化失败: {str(e)}", exc_info=True)
        return None


def reset_supabase_client():
    """重置 Supabase 客户端实例（用于测试或重新配置）

    注意：此函数只重置客户端实例，不重置配置（URL 和 Key）。
    如果需要重置配置，请直接调用 initialize_supabase_config() 设置新值。
    """
    global _supabase_client
    _supabase_client = None
    logger.info("Supabase 客户端实例已重置（配置保持不变）")
