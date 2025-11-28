"""数据存储管理：latest.json"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 数据目录路径
DATA_DIR = Path(__file__).parent.parent / "data"
LATEST_FILE = DATA_DIR / "latest.json"

# 确保 data 目录存在
DATA_DIR.mkdir(exist_ok=True)


def _get_timestamp():
    """获取当前时间戳（UTC+8）"""
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()


# ========== latest.json 管理 ==========


def load_latest():
    """从 data/latest.json 读取缓存数据

    Returns:
        包含 stations 数组的字典，格式：
        {
            "updated_at": "2025-01-01T00:00:00+08:00",
            "stations": [
                {
                    "provider_id": "neptune",
                    "provider_name": "尼普顿",
                    "id": "站点ID",
                    "name": "站点名称",
                    "campus": 2143,
                    ...
                },
                ...
            ]
        }
        如果文件不存在或读取失败返回 None
    """
    if not LATEST_FILE.exists():
        return None

    try:
        with open(LATEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 验证数据格式
            if not isinstance(data, dict) or "stations" not in data:
                print("Warning: latest.json 格式不正确，缺少 stations 字段")
                return None
            return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading latest.json: {e}")
        return None


def save_latest(data):
    """保存最新数据到 data/latest.json

    数据格式：
    {
        "updated_at": "2025-01-01T00:00:00+08:00",
        "stations": [
            {
                "provider_id": "neptune",
                "provider_name": "尼普顿",
                "id": "站点ID",
                "name": "站点名称",
                "campus": 2143,
                ...
            },
            ...
        ]
    }

    Args:
        data: 包含 stations 数组的字典，每个站点包含 provider_id 和 provider_name
    """
    try:
        # 确保数据是字典格式
        if not isinstance(data, dict):
            raise ValueError("数据必须是字典格式")

        # 确保包含 updated_at
        if "updated_at" not in data:
            data["updated_at"] = _get_timestamp()

        # 确保包含 stations 数组
        if "stations" not in data:
            raise ValueError("数据必须包含 stations 字段")

        with open(LATEST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, ValueError) as e:
        print(f"Error saving latest.json: {e}")
        return False
