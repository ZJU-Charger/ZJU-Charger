#!/usr/bin/env python3
"""
更新站点信息脚本

从所有服务商获取站点列表并保存到 data/stations.json

支持多服务商架构：
- 自动从所有已注册的服务商获取站点信息
- 合并多个服务商的数据
- 保留现有 stations.json 中的 simDevaddress 信息（如果存在）
- 站点数据包含 provider_id 和 provider_name 字段

用法:
    python server/update_stations.py
    或
    cd server && python update_stations.py

注意：
- 会从所有服务商获取站点状态数据，然后提取站点基础信息
- 如果 stations.json 已存在，会保留其中的 simDevaddress 字段
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from server.config import Config
from server.logging_config import setup_logging
from server.station_loader import refresh_stations
from fetcher.provider_manager import ProviderManager

async def main():
    """主函数"""
    # 配置日志
    setup_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("开始更新站点信息（多服务商架构）")
    logger.info("=" * 60)
    
    
    # 显示可用的服务商
    try:
        manager = ProviderManager()
        providers = manager.list_providers()
        logger.info(f"可用服务商: {', '.join([p['name'] for p in providers])}")
    except Exception as e:
        logger.warning(f"获取服务商列表失败: {e}")
    
    # 刷新站点信息
    logger.info("")
    logger.info("开始从所有服务商获取站点信息...")
    success = await refresh_stations()
    
    if success:
        logger.info("")
        logger.info("=" * 60)
        logger.info("站点信息更新成功！")
        logger.info("=" * 60)
        logger.info("")
        logger.info("提示：")
        logger.info("  - 站点信息已保存到 data/stations.json")
        logger.info("  - 数据包含所有服务商的站点信息")
        logger.info("  - 每个站点包含 provider_id 和 provider_name 字段")
        logger.info("  - campus 字段已保存为 areaid（兼容旧格式）")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("=" * 60)
        logger.error("站点信息更新失败！")
        logger.error("=" * 60)
        logger.error("")
        logger.error("请检查：")
        logger.error("  1. 网络连接是否正常")
        logger.error("  2. 服务商 API 是否可访问")
        logger.error("  3. 查看上方日志获取详细错误信息")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

