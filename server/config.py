"""环境变量配置管理"""

import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# 加载 .env 文件
load_dotenv()


class Config:
    """配置类，从环境变量读取配置"""

    # 钉钉机器人配置
    DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
    DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")

    # API 服务器配置
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    BACKEND_FETCH_INTERVAL = int(
        os.getenv("BACKEND_FETCH_INTERVAL", "300")
    )  # 后端定时抓取间隔（秒），默认300秒（5分钟）

    # 限流配置
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_DEFAULT = os.getenv(
        "RATE_LIMIT_DEFAULT", "60/hour"
    )  # 默认限流规则，适用于大部分 API 端点
    RATE_LIMIT_STATUS = os.getenv(
        "RATE_LIMIT_STATUS", "3/minute"
    )  # /api/status 端点限流规则，允许前端60秒刷新+容错

    # Supabase 配置
    # 注意：建议使用 Service Role Key（服务端密钥），它会绕过 RLS 策略
    # 在 Supabase Dashboard → Settings → API 中可以找到 Service Role Key
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # 应使用 Service Role Key，而非 anon key
    SUPABASE_HISTORY_ENABLED = os.getenv("SUPABASE_HISTORY_ENABLED", "true").lower() == "true"

    # 服务商配置
    # 格式：PROVIDER_<PROVIDER_ID>_<CONFIG_KEY>=<value>
    # 例如：PROVIDER_NEPTUNE_API_URL=https://api.example.com
    # 当前支持的服务商配置：
    # - NEPTUNE: 尼普顿服务商配置
    #   可通过 PROVIDER_NEPTUNE_* 环境变量配置
    @classmethod
    def get_provider_config(cls, provider_id: str) -> Dict[str, Any]:
        """获取指定服务商的配置

        Args:
            provider_id: 服务商标识（如 'neptune'）

        Returns:
            服务商配置字典，包含该服务商的所有环境变量配置
        """
        config = {}
        prefix = f"PROVIDER_{provider_id.upper()}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀，转换为小写作为配置键
                config_key = key[len(prefix) :].lower()
                config[config_key] = value

        return config

    @classmethod
    def get_provider_config_value(
        cls, provider_id: str, config_key: str, default: Optional[str] = None
    ) -> Optional[str]:
        """获取指定服务商的特定配置值

        Args:
            provider_id: 服务商标识（如 'neptune'）
            config_key: 配置键名（如 'api_url'）
            default: 默认值

        Returns:
            配置值，如果不存在返回 default
        """
        env_key = f"PROVIDER_{provider_id.upper()}_{config_key.upper()}"
        return os.getenv(env_key, default)

    @classmethod
    def validate(cls):
        """验证必需的配置项"""
        errors = []
        return errors
