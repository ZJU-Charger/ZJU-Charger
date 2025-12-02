"""FastAPI 主服务"""

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import json
import sys
import logging
import asyncio
from pathlib import Path

# 导入 slowapi 限流相关模块
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 配置日志（如果还没有配置）
if not logging.getLogger().handlers:
    from server.logging_config import setup_logging

    setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetcher.provider_manager import ProviderManager
from fetcher.station import Station
from server.config import Config
from db import (
    initialize_supabase_config,
    load_latest as load_latest_cache,
    record_usage_data,
    batch_upsert_stations,
    fetch_station_metadata,
    fetch_all_stations_data,
)
from ding.webhook import router as ding_router

provider_manager = ProviderManager()

app = FastAPI(title="ZJU Charger API", version="1.0.0")

logger.info("初始化 FastAPI 应用")

if Config.SUPABASE_URL and Config.SUPABASE_KEY:
    initialize_supabase_config(Config.SUPABASE_URL, Config.SUPABASE_KEY)
else:
    logger.warning("Supabase URL/KEY 未配置，将无法访问云端缓存和历史数据。")

# 初始化 slowapi 限流器（如果启用限流）
# 默认使用内存存储，如需使用 Redis，可修改为：
# limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379/0")
if Config.RATE_LIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
    # 注册限流异常处理器
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info(
        f"slowapi 限流器已初始化（使用内存存储），默认规则: {Config.RATE_LIMIT_DEFAULT}, /api/status 规则: {Config.RATE_LIMIT_STATUS}"
    )
else:
    limiter = None
    logger.info("限流功能已禁用")


def apply_rate_limit(limit_str: str):
    """应用限流装饰器的辅助函数"""
    if limiter:
        return limiter.limit(limit_str)
    else:
        # 如果限流未启用，返回一个无操作的装饰器
        def noop_decorator(func):
            return func

    return noop_decorator


def _sync_stations_from_providers(manager: ProviderManager):
    stations: List[Station] = []
    for provider in manager.providers:
        station_defs = getattr(provider, "station_list", [])
        if station_defs:
            stations.extend(station_defs)

    if not stations:
        logger.warning("未从服务商加载到站点定义，跳过 stations 表同步")
        return

    if batch_upsert_stations(stations):
        logger.info("已根据服务商定义同步 %d 条站点信息到数据库", len(stations))
    else:
        logger.error("同步服务商站点定义到数据库失败")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_device_ids(value: Any) -> List[str]:
    if not value:
        return []

    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None and str(item).strip()]

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (list, tuple)):
                    return [
                        str(item)
                        for item in parsed
                        if item is not None and str(item).strip()
                    ]
            except json.JSONDecodeError:
                pass
        return [str(stripped)]

    return [str(value)]


def _station_dict_to_model(station: Dict[str, Any]) -> Optional[Station]:
    """将 API 级别的站点字典转换为 Station 数据类实例"""

    provider = station.get("provider")
    if not provider:
        logger.debug("站点数据缺少 provider，跳过: %s", station)
        return None

    name = (
        station.get("name")
        or station.get("devdescript")
        or station.get("hash_id")
        or station.get("id")
        or "未知站点"
    )

    campus_id = _coerce_int(station.get("campus_id"))

    device_ids = _normalize_device_ids(
        station.get("device_ids") or station.get("devids")
    )

    updated_at = (
        station.get("updated_at")
        or station.get("snapshot_time")
        or station.get("updatedAt")
        or _get_timestamp()
    )

    try:
        return Station(
            name=name,
            provider=provider,
            campus_id=campus_id,
            lat=_coerce_float(station.get("lat")),
            lon=_coerce_float(station.get("lon")),
            device_ids=device_ids,
            campus_name=station.get("campus_name", ""),
            updated_at=updated_at,
            free=_coerce_int(station.get("free")),
            used=_coerce_int(station.get("used")),
            total=_coerce_int(station.get("total")),
            error=_coerce_int(station.get("error")),
        )
    except Exception as exc:
        logger.debug("构建 Station 模型失败: %s", exc)
        return None


def _station_models_from_result(stations: List[Dict[str, Any]]) -> List[Station]:
    models = []
    for station in stations:
        model = _station_dict_to_model(station)
        if model:
            models.append(model)
    return models


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
    if Config.RATE_LIMIT_ENABLED:
        logger.info(f"  - 接口限流: 已启用")
        logger.info(f"    - 默认限流规则: {Config.RATE_LIMIT_DEFAULT}")
        logger.info(f"    - /api/status 限流规则: {Config.RATE_LIMIT_STATUS}")
    else:
        logger.info(f"  - 接口限流: 已禁用")

    _sync_stations_from_providers(provider_manager)

    # 启动后台定时抓取任务
    asyncio.create_task(background_fetch_task())
    logger.info(f"已启动后台定时抓取任务，间隔: {Config.BACKEND_FETCH_INTERVAL} 秒")

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

logger.info("FastAPI 仅提供 API 路由；静态前端由独立托管服务提供")


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
        station_id = station.get("id") or station.get("hash_id")
        if not station_id:
            logger.warning("跳过缺少 hash_id 的站点: %s", station)
            continue

        if station_id not in stations_by_id:
            stations_by_id[station_id] = station.copy()

    return list(stations_by_id.values())


def _build_stations_from_latest_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将 latest 行数据与站点信息整合为 API 需要的结构"""

    if not rows:
        return []

    station_ids = [row.get("hash_id") for row in rows if row.get("hash_id")]
    metadata_map = fetch_station_metadata(station_ids)

    stations = []
    for row in rows:
        station_id = row.get("hash_id")
        if not station_id:
            continue

        metadata = metadata_map.get(station_id, {})
        if not metadata:
            logger.debug("站点 %s 缺少 metadata，将返回最小字段", station_id)

        station = {
            "hash_id": station_id,
            "id": station_id,
            "name": metadata.get("name") or station_id,
            "provider": metadata.get("provider"),
            "campus_id": metadata.get("campus_id"),
            "campus_name": metadata.get("campus_name"),
            "lat": metadata.get("lat"),
            "lon": metadata.get("lon"),
            "devids": metadata.get("device_ids") or [],
            "free": int(row.get("free", 0) or 0),
            "used": int(row.get("used", 0) or 0),
            "total": int(row.get("total", 0) or 0),
            "error": int(row.get("error", 0) or 0),
        }
        stations.append(station)

    return stations


def _format_station_definition(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("hash_id") or row.get("id"),
        "name": row.get("name"),
        "devdescript": row.get("name"),
        "provider": row.get("provider"),
        "campus_id": row.get("campus_id"),
        "campus_name": row.get("campus_name"),
        "latitude": row.get("lat"),
        "longitude": row.get("lon"),
        "devids": row.get("device_ids") or [],
    }


def _max_updated_at(rows: List[Dict[str, Any]]) -> str:
    timestamps = []
    for row in rows:
        value = row.get("updated_at")
        if not value:
            continue
        try:
            timestamps.append(datetime.fromisoformat(value))
        except ValueError:
            try:
                timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                logger.debug("无法解析站点 updated_at=%s，忽略", value)

    if timestamps:
        return max(timestamps).isoformat()
    return _get_timestamp()


def _matches_devid(station: Dict[str, Any], devid: str) -> bool:
    if not devid:
        return False
    candidates = station.get("devids") or []
    devid_str = str(devid)
    for candidate in candidates:
        if str(candidate) == devid_str:
            return True
    return False


def _station_provider(station: Dict[str, Any]) -> Optional[str]:
    return station.get("provider")


def _build_cached_response(
    provider: Optional[str] = None,
    station_id: Optional[str] = None,
    devid: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """尝试从 latest 表构建 API 响应"""

    cached_data = load_latest_cache()
    if not cached_data:
        return None

    rows = cached_data.get("rows")
    if not rows:
        return None

    if station_id:
        rows = [row for row in rows if row.get("hash_id") == station_id]
        if not rows:
            return None

    stations = _build_stations_from_latest_rows(rows)
    if provider:
        stations = [s for s in stations if _station_provider(s) == provider]
        if not stations:
            return None

    if devid:
        stations = [s for s in stations if _matches_devid(s, devid)]
        if not stations:
            return None

    if not station_id:
        stations = aggregate_stations_by_id(stations)

    return {
        "updated_at": cached_data.get("updated_at", _get_timestamp()),
        "stations": stations,
    }


@app.get("/api")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def api_info(request: Request):
    """API 信息"""
    return {
        "message": "ZJU Charger API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/status": "实时查询所有站点（支持 ?provider=neptune 参数筛选，支持 ?id=xxx 查询指定站点）",
            "GET /api/providers": "返回可用服务商列表",
            "GET /api/config": "返回前端配置信息（包括抓取间隔等）",
            "GET /api/stations": "返回站点基础信息（id、名称、坐标、服务商）",
        },
    }


@app.get("/api/config")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def get_config(request: Request):
    """返回前端配置信息"""
    logger.info("收到 /api/config 请求")
    return {"fetch_interval": Config.FETCH_INTERVAL}  # 前端自动刷新间隔（秒）


@app.get("/api/providers")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def get_providers(request: Request):
    """返回可用服务商列表"""
    logger.info("收到 /api/providers 请求")
    try:
        providers = provider_manager.list_providers()
        logger.info(f"返回 {len(providers)} 个服务商")
        return providers
    except Exception as e:
        logger.error(f"获取服务商列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取服务商列表失败: {str(e)}")


@app.get("/api/stations")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def get_station_catalog(request: Request):
    """返回站点基础信息列表"""
    logger.info("收到 /api/stations 请求")

    try:
        rows = fetch_all_stations_data()
        if not rows:
            raise HTTPException(status_code=503, detail="站点信息不可用")

        station_defs = [_format_station_definition(row) for row in rows]
        updated_at = _max_updated_at(rows)
        return {"updated_at": updated_at, "stations": station_defs}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询 stations 表失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="站点信息不可用")


@app.get("/api/status")
@apply_rate_limit(Config.RATE_LIMIT_STATUS)
async def get_status(
    request: Request,
    provider: Optional[str] = None,
    hash_id: Optional[str] = Query(None),
    devid: Optional[str] = Query(None, alias="devid"),
):
    """查询所有站点状态（优先从缓存读取）

    Args:
        provider: 可选，服务商标识（如 'neptune'），如果指定则只返回该服务商的数据
        id: 可选，站点唯一标识，如果指定则只返回匹配的站点
    """
    station_id = hash_id
    logger.info(
        "收到 /api/status 请求，provider=%s, hash_id=%s, devid=%s",
        provider,
        station_id,
        devid,
    )

    if devid and not provider:
        raise HTTPException(
            status_code=400, detail="查询 devid 时必须同时提供 provider 参数"
        )

    try:
        cached_response = _build_cached_response(
            provider=provider, station_id=station_id, devid=devid
        )
        if cached_response is not None:
            logger.info(
                "使用 latest 缓存返回 %d 个站点",
                len(cached_response.get("stations", [])),
            )
            return cached_response

        logger.info("缓存不存在或无效，开始实时抓取数据...")
        provider_filter = provider
        result = await provider_manager.fetch_and_format(provider=provider_filter)

        if result is None:
            logger.error("数据抓取失败：返回 None")
            raise HTTPException(status_code=500, detail="数据抓取失败且无缓存数据")

        stations = result.get("stations", [])
        logger.info(f"实时抓取成功，共 {len(stations)} 个站点")

        filtered = stations
        if station_id:
            filtered = [s for s in filtered if s.get("id") == station_id]
            logger.info("按 hash_id 过滤后，共 %d 个站点", len(filtered))
        elif provider and devid:
            filtered = [
                s
                for s in filtered
                if _station_provider(s) == provider and _matches_devid(s, devid)
            ]
            logger.info(
                "按 provider+devid 过滤后，共 %d 个站点（provider=%s, devid=%s）",
                len(filtered),
                provider,
                devid,
            )
        elif provider:
            filtered = [s for s in filtered if _station_provider(s) == provider]
            logger.info("按 provider 过滤后，共 %d 个站点", len(filtered))
        elif devid:
            filtered = [s for s in filtered if _matches_devid(s, devid)]
            logger.info("按 devid 过滤后，共 %d 个站点", len(filtered))

        if not filtered:
            return {
                "updated_at": result.get("updated_at", _get_timestamp()),
                "stations": [],
            }

        if not station_id:
            filtered = aggregate_stations_by_id(filtered)
            logger.info("聚合后，共 %d 个站点", len(filtered))

        result["stations"] = filtered
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


def is_night_time():
    """检查当前时间是否在夜间暂停时段（0:10-5:50）"""
    tz_utc_8 = timezone(timedelta(hours=8))
    now = datetime.now(tz_utc_8)
    current_time = now.time()

    # 定义夜间暂停时段：0:10 到 5:50
    night_start = datetime.strptime("00:10", "%H:%M").time()
    night_end = datetime.strptime("05:50", "%H:%M").time()
    return False
    # 检查是否在夜间时段（0:10 到 5:50 之间）
    # 由于这个时间段在同一天内，可以直接比较
    if night_start <= current_time <= night_end:
        return True

    return False


async def background_fetch_task():
    """后台定时抓取任务，定期从供应商API抓取数据并保存到缓存"""
    fetch_interval = Config.BACKEND_FETCH_INTERVAL

    # 启动时先执行一次，确保有初始缓存（但需要检查时间）
    logger.info("执行首次后台抓取任务，初始化缓存...")
    if not is_night_time():
        try:
            result = await provider_manager.fetch_and_format()

            if result is None:
                logger.error("首次后台抓取数据失败：返回 None")
            else:
                stations = result.get("stations", [])
                station_models = _station_models_from_result(stations)

                if station_models:
                    try:
                        if batch_upsert_stations(station_models):
                            logger.info(
                                f"首次后台抓取数据已同步站点基础信息，共 {len(station_models)} 条"
                            )
                        else:
                            logger.warning("首次后台抓取数据同步站点基础信息失败")
                    except Exception as exc:
                        logger.error(
                            "首次后台抓取同步站点信息发生异常: %s", exc, exc_info=True
                        )

                snapshot_time = result.get("updated_at", _get_timestamp())
                if not snapshot_time:
                    snapshot_time = _get_timestamp()
                    result["updated_at"] = snapshot_time

                history_enabled = Config.SUPABASE_HISTORY_ENABLED
                if record_usage_data(result, history_mode_enabled=history_enabled):
                    logger.info(
                        "首次后台抓取数据成功写入 Supabase（history=%s），共 %d 个站点",
                        history_enabled,
                        len(stations),
                    )
                else:
                    logger.error("首次后台抓取数据写入 Supabase 失败")
        except Exception as e:
            logger.error(f"首次后台抓取任务发生异常: {str(e)}", exc_info=True)
    else:
        logger.info("当前处于夜间暂停时段（0:10-5:50），跳过首次抓取")

    # 然后按间隔定时执行
    while True:
        try:
            await asyncio.sleep(fetch_interval)

            # 检查是否在夜间暂停时段
            if is_night_time():
                tz_utc_8 = timezone(timedelta(hours=8))
                current_time_str = datetime.now(tz_utc_8).strftime("%H:%M")
                logger.info(
                    f"当前时间 {current_time_str} 处于夜间暂停时段（0:10-5:50），跳过本次抓取"
                )
                continue

            logger.info(f"开始后台定时抓取数据（间隔: {fetch_interval}秒）...")

            result = await provider_manager.fetch_and_format()

            if result is None:
                logger.error("后台抓取数据失败：返回 None")
                continue

            stations = result.get("stations", [])
            station_models = _station_models_from_result(stations)

            if station_models:
                try:
                    if batch_upsert_stations(station_models):
                        logger.info(
                            "后台抓取已同步 %d 条站点基础信息", len(station_models)
                        )
                    else:
                        logger.warning("后台抓取同步站点基础信息失败")
                except Exception as exc:
                    logger.error("后台抓取同步站点基础信息异常: %s", exc, exc_info=True)

            snapshot_time = result.get("updated_at", _get_timestamp())
            if not snapshot_time:
                snapshot_time = _get_timestamp()
                result["updated_at"] = snapshot_time

            history_enabled = Config.SUPABASE_HISTORY_ENABLED
            if record_usage_data(result, history_mode_enabled=history_enabled):
                logger.info(
                    "后台抓取数据成功写入 Supabase（history=%s），共 %d 个站点",
                    history_enabled,
                    len(stations),
                )
            else:
                logger.error("后台抓取数据写入 Supabase 失败")
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
        log_config=None,  # 使用我们自己的日志配置
    )
