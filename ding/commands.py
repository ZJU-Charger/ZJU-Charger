"""钉钉命令解析和执行"""

import re
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.config import Config
import httpx


async def parse_command(text):
    """解析用户命令

    Args:
        text: 用户输入的命令文本

    Returns:
        (command_type, args): 命令类型和参数
        command_type: "all" | "unknown"
    """
    text = text.strip()

    if text == "全部":
        return ("all", None)
    else:
        return ("unknown", None)


async def execute_all_command():
    """执行全部命令（返回所有站点状态）"""
    try:
        # 调用 API 获取所有站点状态
        import os

        api_base = os.getenv("API_URL", f"http://{Config.API_HOST}:{Config.API_PORT}")
        api_url = f"{api_base}/api/status"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API 返回错误: {response.status_code}"}
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
