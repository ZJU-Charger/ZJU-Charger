#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速查询关注列表站点状态
不启动 API 服务，直接查询并打印到命令行
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from fetcher.fetch import Fetcher
from server.config import Config
from server.storage import load_watchlist, is_in_watchlist
from datetime import datetime


def format_timestamp(timestamp_str):
    """格式化时间戳"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str


def print_station(station, index=None):
    """打印单个站点信息"""
    name = station.get("name", "未知站点")
    free = station.get("free", 0)
    total = station.get("total", 0)
    used = station.get("used", 0)
    error = station.get("error", 0)
    devids = station.get("devids", [])
    
    # 状态指示
    if free > 0:
        if free <= 2:
            status = "⚠️  少量空闲"
            status_color = "\033[33m"  # 黄色
        else:
            status = "✅ 有空闲"
            status_color = "\033[32m"  # 绿色
    else:
        status = "❌ 无空闲"
        status_color = "\033[31m"  # 红色
    
    reset_color = "\033[0m"
    
    # 打印站点信息
    prefix = f"[{index}] " if index is not None else ""
    print(f"\n{prefix}{status_color}{status}{reset_color} {name}")
    print(f"  📍 可用: {status_color}{free}{reset_color} / 总数: {total} | 已用: {used}", end="")
    if error > 0:
        print(f" | 故障: \033[31m{error}\033[0m", end="")
    print()
    if devids:
        print(f"  🔢 DevIDs: {', '.join(map(str, devids))}")


def print_header(updated_at, count):
    """打印表头"""
    print("=" * 60)
    print("🔋 ZJU 充电桩状态查询 - 关注列表")
    print("=" * 60)
    if updated_at:
        print(f"📅 更新时间: {format_timestamp(updated_at)}")
    print(f"📊 关注站点数: {count}")
    print("-" * 60)


async def main():
    """主函数"""
    # 检查 OPENID 配置
    openid = Config.get_openid()
    if not openid:
        print("❌ 错误: OPENID 环境变量未设置")
        print("请设置环境变量: export OPENID=your_openid")
        sys.exit(1)
    
    # 加载关注列表
    watchlist = load_watchlist()
    watchlist_devids = set(watchlist.get("devids", []))
    watchlist_devdescripts = set(watchlist.get("devdescripts", []))
    
    if not watchlist_devids and not watchlist_devdescripts:
        print("⚠️  关注列表为空")
        print("请先添加站点到关注列表")
        sys.exit(0)
    
    print(f"📋 关注列表: {len(watchlist_devids)} 个 devid, {len(watchlist_devdescripts)} 个站点名称")
    if watchlist_devids:
        print(f"   DevIDs: {', '.join(map(str, sorted(watchlist_devids)))}")
    if watchlist_devdescripts:
        print(f"   站点: {', '.join(sorted(watchlist_devdescripts))}")
    print()
    
    # 获取数据
    print("🔄 正在查询站点状态...")
    try:
        async with Fetcher(openid) as fetcher:
            result = await fetcher.fetch_and_format()
            
            if result is None:
                print("❌ 数据抓取失败")
                sys.exit(1)
            
            # 过滤出关注列表中的站点
            stations = result.get("stations", [])
            filtered_stations = [
                station for station in stations
                if is_in_watchlist(
                    devids=station.get("devids"),
                    devdescript=station.get("name")
                )
            ]
            
            # 按空闲数量排序
            filtered_stations.sort(key=lambda x: x.get("free", 0), reverse=True)
            
            # 打印结果
            updated_at = result.get("updated_at", "")
            print_header(updated_at, len(filtered_stations))
            
            if not filtered_stations:
                print("⚠️  未找到匹配的站点")
                print("请检查关注列表中的 devid 或站点名称是否正确")
            else:
                for i, station in enumerate(filtered_stations, 1):
                    print_station(station, index=i)
            
            print("\n" + "=" * 60)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

