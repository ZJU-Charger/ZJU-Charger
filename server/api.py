"""FastAPI 主服务"""
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import sys
import logging
import asyncio
from pathlib import Path

# 配置日志（如果还没有配置）
if not logging.getLogger().handlers:
    from server.logging_config import setup_logging
    setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetcher.provider_manager import ProviderManager
from server.config import Config
from server.storage import (
    load_latest, save_latest
)
from server.station_loader import load_stations
from ding.webhook import router as ding_router

app = FastAPI(title="ZJU Charger API", version="1.0.0")

logger.info("初始化 FastAPI 应用")

@app.on_event("startup")
async def startup_event():
    """服务器启动时执行的操作"""
    logger.info("=" * 60)
    logger.info("服务器启动中...")
    logger.info("=" * 60)
    
    # 记录配置信息
    logger.info(f"配置信息：")
    logger.info(f"  - API 地址: {Config.API_HOST}:{Config.API_PORT}")
    logger.info(f"  - 前端自动刷新间隔: {Config.FETCH_INTERVAL} 秒")
    logger.info(f"  - 后端定时抓取间隔: {Config.BACKEND_FETCH_INTERVAL} 秒")
    
    # 启动后台定时抓取任务
    asyncio.create_task(background_fetch_task())
    logger.info(f"已启动后台定时抓取任务，间隔: {Config.BACKEND_FETCH_INTERVAL} 秒")
    
    logger.info("服务器启动事件：检查站点信息文件...")
    try:
        stations_data = load_stations()
        if stations_data:
            station_count = len(stations_data.get('stations', []))
            updated_at = stations_data.get('updated_at', '未知')
            logger.info(f"已加载站点信息文件，共 {station_count} 个站点，更新时间: {updated_at}")
        else:
            logger.warning("站点信息文件不存在或加载失败")
            logger.warning("请运行 'python update_stations.py' 来更新站点信息")
    except Exception as e:
        logger.error(f"启动时检查站点信息失败: {str(e)}", exc_info=True)
        logger.warning("服务器将继续启动，但站点信息可能不可用")
    
    logger.info("=" * 60)

# 添加 CORS 支持（必须在路由之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS 中间件已配置")

# 注册钉钉路由
app.include_router(ding_router)
logger.info("钉钉路由已注册")

# 静态文件服务（前端页面）- 必须在 API 路由之后
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")
    logger.info(f"静态文件服务已挂载: /web -> {web_dir}")
else:
    logger.warning(f"web 目录不存在: {web_dir}")

# 数据文件服务（GitHub Pages 使用）
data_dir = Path(__file__).parent.parent / "data"
if data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")
    logger.info(f"数据文件服务已挂载: /data -> {data_dir}")
else:
    logger.warning(f"data 目录不存在: {data_dir}")

def _get_timestamp():
    """获取当前时间戳（UTC+8）"""
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()

def aggregate_stations_by_id(stations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """聚合相同 id 的站点
    
    对于相同 id 的站点：
    - 只保留第一个站点，使用第一个站点的所有信息
    
    Args:
        stations: 站点列表
        
    Returns:
        聚合后的站点列表
    """
    if not stations:
        return []
    
    # 按 id 分组，只保留第一个站点
    stations_by_id = {}
    for station in stations:
        station_id = station.get("id")
        if not station_id:
            # 如果没有 id，使用 name 作为 fallback（向后兼容）
            station_id = station.get("name", "")
            if not station_id:
                continue
        
        if station_id not in stations_by_id:
            # 第一个站点，直接使用
            stations_by_id[station_id] = {
                "station": station.copy(),
                "count": 1
            }
        else:
            # 后续相同 id 的站点，忽略
            stations_by_id[station_id]["count"] += 1
    
    # 转换为列表
    aggregated_stations = []
    for station_id, data in stations_by_id.items():
        station = data["station"]
        aggregated_stations.append(station)
        
        if data["count"] > 1:
            station_name = station.get("name", "未知站点")
            logger.info(f"聚合站点 '{station_name}' (id={station_id[:8]}...): 保留了第一个站点，合并了 {data['count']} 个站点")
    
    return aggregated_stations

@app.get("/")
async def root():
    """根路径 - 重定向到前端页面"""
    logger.info("访问根路径，重定向到 /web/")
    return RedirectResponse(url="/web/")

@app.get("/api")
async def api_info():
    """API 信息"""
    return {
        "message": "ZJU Charger API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/status": "实时查询所有站点（支持 ?provider=neptune 参数筛选，支持 ?id=xxx 查询指定站点）",
            "GET /api/providers": "返回可用服务商列表",
            "GET /api/config": "返回前端配置信息（包括抓取间隔等）"
        }
    }

@app.get("/api/config")
async def get_config():
    """返回前端配置信息"""
    logger.info("收到 /api/config 请求")
    return {
        "fetch_interval": Config.FETCH_INTERVAL  # 前端自动刷新间隔（秒）
    }

@app.get("/api/providers")
async def get_providers():
    """返回可用服务商列表"""
    logger.info("收到 /api/providers 请求")
    try:
        manager = ProviderManager()
        providers = manager.list_providers()
        logger.info(f"返回 {len(providers)} 个服务商")
        return providers
    except Exception as e:
        logger.error(f"获取服务商列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取服务商列表失败: {str(e)}"
        )

@app.get("/api/status")
async def get_status(
    provider: Optional[str] = None,
    id: Optional[str] = None
):
    """查询所有站点状态（优先从缓存读取）
    
    Args:
        provider: 可选，服务商标识（如 'neptune'），如果指定则只返回该服务商的数据
        id: 可选，站点唯一标识，如果指定则只返回匹配的站点
    """
    logger.info(f"收到 /api/status 请求，provider={provider}, id={id}")
    
    try:
        # 优先从缓存读取
        cached_data = load_latest()
        use_cache = False
        
        if cached_data and cached_data.get("stations"):
            # 检查缓存是否有效（有数据且格式正确）
            stations = cached_data.get("stations", [])
            
            # 如果指定了 provider，检查缓存中是否有该服务商的数据
            if provider:
                has_provider_data = any(s.get("provider_id") == provider for s in stations)
                if has_provider_data:
                    use_cache = True
                    logger.info(f"使用缓存数据（provider={provider}）")
            else:
                # 没有指定 provider，使用全部缓存数据
                use_cache = True
                logger.info("使用缓存数据（全部服务商）")
        
        if use_cache:
            # 从缓存中过滤数据
            result = {
                "updated_at": cached_data.get("updated_at", _get_timestamp()),
                "stations": cached_data.get("stations", [])
            }
            
            # 如果指定了 provider，过滤出该服务商的数据
            if provider:
                result["stations"] = [
                    s for s in result["stations"]
                    if s.get("provider_id") == provider
                ]
                logger.info(f"从缓存中过滤出 {len(result['stations'])} 个 {provider} 服务商的站点")
            
            # 如果指定了 id，过滤出匹配的站点
            if id:
                result["stations"] = [
                    s for s in result["stations"]
                    if s.get("id") == id
                ]
                logger.info(f"按 id 过滤后，共 {len(result['stations'])} 个站点")
            
            if not id:
                # 聚合相同 id 的站点（只有在没有指定 id 时才聚合）
                result["stations"] = aggregate_stations_by_id(result["stations"])
                logger.info(f"聚合后，共 {len(result['stations'])} 个站点")
            else:
                logger.info(f"从缓存返回 {len(result['stations'])} 个站点")
            
            return result
        else:
            # 缓存不存在或无效，进行实时抓取
            logger.info("缓存不存在或无效，开始实时抓取数据...")
            manager = ProviderManager()
            result = await manager.fetch_and_format(provider_id=provider)
            
            if result is None:
                logger.error("数据抓取失败：返回 None")
                # 如果抓取失败，尝试返回缓存（即使可能过期）
                if cached_data:
                    logger.warning("实时抓取失败，返回可能过期的缓存数据")
                    result = {
                        "updated_at": cached_data.get("updated_at", _get_timestamp()),
                        "stations": cached_data.get("stations", [])
                    }
                    if provider:
                        result["stations"] = [
                            s for s in result["stations"]
                            if s.get("provider_id") == provider
                        ]
                    if id:
                        result["stations"] = [
                            s for s in result["stations"]
                            if s.get("id") == id
                        ]
                    if not id:
                        # 聚合相同 id 的站点（只有在没有指定 id 时才聚合）
                        result["stations"] = aggregate_stations_by_id(result["stations"])
                    return result
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="数据抓取失败且无缓存数据"
                    )
            
            stations = result.get("stations", [])
            logger.info(f"实时抓取成功，共 {len(stations)} 个站点")
            
            # 如果指定了 id，过滤出匹配的站点
            if id:
                result["stations"] = [
                    s for s in result["stations"]
                    if s.get("id") == id
                ]
                logger.info(f"按 id 过滤后，共 {len(result['stations'])} 个站点")
            
            if not id:
                # 聚合相同 id 的站点（只有在没有指定 id 时才聚合）
                result["stations"] = aggregate_stations_by_id(result["stations"])
                logger.info(f"聚合后，共 {len(result['stations'])} 个站点")
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"查询失败: {str(e)}"
        )

async def background_fetch_task():
    """后台定时抓取任务，定期从供应商API抓取数据并保存到缓存"""
    fetch_interval = Config.BACKEND_FETCH_INTERVAL
    
    # 启动时先执行一次，确保有初始缓存
    logger.info("执行首次后台抓取任务，初始化缓存...")
    try:
        manager = ProviderManager()
        result = await manager.fetch_and_format()
        
        if result is None:
            logger.error("首次后台抓取数据失败：返回 None")
        else:
            # 保存到 latest.json
            if save_latest(result):
                station_count = len(result.get("stations", []))
                logger.info(f"首次后台抓取数据成功并已保存，共 {station_count} 个站点")
            else:
                logger.error("首次后台抓取数据保存失败")
    except Exception as e:
        logger.error(f"首次后台抓取任务发生异常: {str(e)}", exc_info=True)
    
    # 然后按间隔定时执行
    while True:
        try:
            await asyncio.sleep(fetch_interval)
            logger.info(f"开始后台定时抓取数据（间隔: {fetch_interval}秒）...")
            
            manager = ProviderManager()
            result = await manager.fetch_and_format()
            
            if result is None:
                logger.error("后台抓取数据失败：返回 None")
                continue
            
            # 保存到 latest.json
            if save_latest(result):
                station_count = len(result.get("stations", []))
                logger.info(f"后台抓取数据成功并已保存，共 {station_count} 个站点")
            else:
                logger.error("后台抓取数据保存失败")
        except Exception as e:
            logger.error(f"后台抓取任务发生异常: {str(e)}", exc_info=True)
            # 发生异常时等待一段时间再继续，避免频繁重试
            await asyncio.sleep(60)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"启动服务器: {Config.API_HOST}:{Config.API_PORT}")
    uvicorn.run(
        app, 
        host=Config.API_HOST, 
        port=Config.API_PORT,
        log_config=None  # 使用我们自己的日志配置
    )
