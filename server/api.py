"""FastAPI 主服务"""

import logfire
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
import json
import sys
from pathlib import Path
from time import perf_counter

# 导入 slowapi 限流相关模块
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from server.logfire_setup import ensure_logfire_configured

ensure_logfire_configured()

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


from server.config import Config
from db import (
    initialize_supabase_config,
    load_latest as load_latest_cache,
    fetch_station_metadata,
    fetch_all_stations_data,
    fetch_distinct_providers,
)
from ding.webhook import router as ding_router

PROVIDER_PATTERN = r"^[A-Za-z0-9_-]+$"
HASH_ID_PATTERN = r"^[0-9a-fA-F]{8}$"
DEVID_PATTERN = r"^[A-Za-z0-9_, -]+$"

app = FastAPI(title="ZJU Charger API", version="1.0.0")

_last_status_snapshot: Optional[Dict[str, Any]] = None
_last_status_filter_mode: Optional[str] = None


def now_utc8_iso() -> str:
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()

# logfire captures structured logs/traces for observability before other startup tasks
logfire.instrument_fastapi(app)
logfire.info("Initializing FastAPI application", name="world")
logfire.info("初始化 FastAPI 应用")

api_request_counter = logfire.metric_counter(
    "api.requests",
    unit="1",
    description="Total FastAPI requests grouped by endpoint/method/status",
)
api_latency_histogram = logfire.metric_histogram(
    "api.request.duration",
    unit="ms",
    description="FastAPI request latency in milliseconds",
)


class ApiCallTelemetry:
    """Context manager that wraps API handlers with a span and metrics."""

    def __init__(
        self,
        request: Request,
        endpoint: str,
        *,
        span_name: Optional[str] = None,
        span_attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.request = request
        self.endpoint = endpoint
        self.metric_attributes: Dict[str, Any] = {}
        self._explicit_status_code: Optional[int] = None
        attributes = span_attributes or {}
        self._span_cm = logfire.span(
            span_name or "Handling {method} {endpoint}",
            method=request.method,
            endpoint=endpoint,
            **attributes,
        )

    def __enter__(self) -> "ApiCallTelemetry":
        self._span_cm.__enter__()
        self._start = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = (perf_counter() - self._start) * 1000
        status_code = self._explicit_status_code or 200
        if exc_type is not None:
            if issubclass(exc_type, HTTPException):
                status_code = getattr(exc, "status_code", status_code)
            else:
                status_code = 500

        self._record_metrics(status_code, duration_ms)
        return self._span_cm.__exit__(exc_type, exc, tb)

    def add_metric_attributes(self, **attrs: Any) -> None:
        for key, value in attrs.items():
            if value is not None:
                self.metric_attributes[key] = value

    def set_status_code(self, status_code: int) -> None:
        self._explicit_status_code = status_code

    def _record_metrics(self, status_code: int, duration_ms: float) -> None:
        attributes = {
            "endpoint": self.endpoint,
            "method": self.request.method,
            "status_code": status_code,
        }
        attributes.update(self.metric_attributes)
        api_request_counter.add(1, attributes)
        api_latency_histogram.record(duration_ms, attributes)

if Config.SUPABASE_URL and Config.SUPABASE_KEY:
    initialize_supabase_config(Config.SUPABASE_URL, Config.SUPABASE_KEY)
else:
    logfire.warn("Supabase URL/KEY 未配置，将无法访问云端缓存和历史数据。")

# 初始化 slowapi 限流器（如果启用限流）
# 默认使用内存存储，如需使用 Redis，可修改为：
# limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379/0")
if Config.RATE_LIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
    # 注册限流异常处理器
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logfire.info(
        "slowapi 限流器已初始化（使用内存存储），默认规则: {default_rule}，/api/status 规则: {status_rule}",
        default_rule=Config.RATE_LIMIT_DEFAULT,
        status_rule=Config.RATE_LIMIT_STATUS,
    )
else:
    limiter = None
    logfire.info("限流功能已禁用")


def apply_rate_limit(limit_str: str):
    """应用限流装饰器的辅助函数"""
    if limiter:
        return limiter.limit(limit_str)
    else:
        # 如果限流未启用，返回一个无操作的装饰器
        def noop_decorator(func):
            return func

    return noop_decorator


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
                    return [str(item) for item in parsed if item is not None and str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [str(stripped)]

    return [str(value)]


@app.on_event("startup")
async def startup_event():
    """服务器启动时执行的操作"""
    with logfire.span("执行启动流程"):
        # 记录配置信息
        logfire.info("配置信息：")
        logfire.info(
            "  - API 地址: {host}:{port}",
            host=Config.API_HOST,
            port=Config.API_PORT,
        )
        logfire.info(
            "  - 后端定时抓取间隔: {interval} 秒",
            interval=Config.BACKEND_FETCH_INTERVAL,
        )
        if Config.RATE_LIMIT_ENABLED:
            logfire.info("  - 接口限流: 已启用")
            logfire.info(
                "    - 默认限流规则: {default_rule}",
                default_rule=Config.RATE_LIMIT_DEFAULT,
            )
            logfire.info(
                "    - /api/status 限流规则: {status_rule}",
                status_rule=Config.RATE_LIMIT_STATUS,
            )
        else:
            logfire.info("  - 接口限流: 已禁用")

        logfire.info("后台抓取任务由 run_server 启动并独立运行")


# 添加 CORS 支持（必须在路由之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logfire.info("CORS 中间件已配置")

# 注册钉钉路由
app.include_router(ding_router)
logfire.info("钉钉路由已注册")

logfire.info("FastAPI 仅提供 API 路由；静态前端由独立托管服务提供")



def _build_stations_from_latest_rows(
    rows: List[Dict[str, Any]],
    *,
    provider: Optional[str] = None,
    devid: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """将 latest 行数据与站点信息整合为 API 需要的结构"""

    if not rows:
        return []

    station_ids = [row.get("hash_id") for row in rows if row.get("hash_id")]
    metadata_map = fetch_station_metadata(station_ids, provider=provider)

    stations = []
    seen_ids: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        station_id = row.get("hash_id")
        if not station_id:
            continue

        metadata = metadata_map.get(station_id, {})
        if provider and not metadata:
            # provider 被过滤掉了
            continue
        if not metadata:
            logfire.debug("站点 {station_id} 缺少 metadata，将返回最小字段", station_id=station_id)

        device_ids = metadata.get("device_ids") or []
        normalized_ids = _normalize_device_ids(device_ids)
        if devid and str(devid) not in normalized_ids:
            continue

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
        if station_id not in seen_ids:
            seen_ids[station_id] = station

    return list(seen_ids.values())


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
                logfire.debug("无法解析站点 updated_at={value}，忽略", value=value)

    if timestamps:
        return max(timestamps).isoformat()
    return now_utc8_iso()


def _remember_status_response(
    response: Dict[str, Any],
    filter_mode: str,
    *,
    allow_stale: bool,
) -> None:
    if not allow_stale:
        return

    global _last_status_snapshot, _last_status_filter_mode
    _last_status_snapshot = {
        "payload": response,
        "recorded_at": now_utc8_iso(),
    }
    _last_status_filter_mode = filter_mode


def _get_fallback_status_response() -> Optional[Tuple[Dict[str, Any], str]]:
    if not _last_status_snapshot:
        return None

    payload = dict(_last_status_snapshot["payload"])
    payload["stale"] = True
    return payload, (_last_status_filter_mode or "all")

def _build_cached_response(
    *,
    provider: Optional[str] = None,
    station_id: Optional[str] = None,
    devid: Optional[str] = None,
) -> Optional[Tuple[Dict[str, Any], str]]:
    """尝试从 latest 表构建 API 响应并返回过滤模式"""
    with logfire.span(
        "构建 latest 缓存响应",
        provider=provider or "all",
        station_id=station_id,
        devid=devid,
    ):
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

        stations = _build_stations_from_latest_rows(
            rows,
            provider=provider,
            devid=devid,
        )
        if not stations:
            return None

        response = {
            "updated_at": cached_data.get("updated_at") or now_utc8_iso(),
            "stations": stations,
        }

        if station_id:
            filter_mode = "hash_id"
        elif provider and devid:
            filter_mode = "provider+devid"
        elif provider:
            filter_mode = "provider"
        elif devid:
            filter_mode = "devid"
        else:
            filter_mode = "all"

        _remember_status_response(response, filter_mode, allow_stale=(filter_mode == "all"))
        return response, filter_mode


@app.get("/api")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def api_info(request: Request):
    """API 信息"""
    with ApiCallTelemetry(request, "/api"):
        return {
            "message": "ZJU Charger API",
            "version": "1.0.0",
            "endpoints": {
                "GET /api/status": "实时查询所有站点（支持 ?provider=neptune 参数筛选，支持 ?id=xxx 查询指定站点）",
                "GET /api/providers": "返回可用服务商列表",
                "GET /api/stations": "返回站点基础信息（id、名称、坐标、服务商）",
            },
        }


@app.get("/api/providers")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def get_providers(request: Request):
    """返回可用服务商列表"""
    with ApiCallTelemetry(request, "/api/providers") as telemetry:
        logfire.info("收到 /api/providers 请求")
        try:
            providers = fetch_distinct_providers()
            provider_entries = [{"id": prov, "name": prov} for prov in providers]
            provider_count = len(provider_entries)
            logfire.info("返回 {provider_count} 个服务商", provider_count=provider_count)
            telemetry.add_metric_attributes(provider_count=provider_count)
            return provider_entries
        except Exception as e:
            logfire.error("获取服务商列表失败: {error}", error=str(e))
            raise HTTPException(status_code=500, detail="获取服务商列表失败")


@app.get("/api/stations")
@apply_rate_limit(Config.RATE_LIMIT_DEFAULT)
async def get_station_catalog(request: Request):
    """返回站点基础信息列表"""
    with ApiCallTelemetry(request, "/api/stations") as telemetry:
        logfire.info("收到 /api/stations 请求")

        try:
            with logfire.span("查询站点基础信息表"):
                rows = fetch_all_stations_data()
            if not rows:
                telemetry.set_status_code(503)
                raise HTTPException(status_code=503, detail="站点信息不可用")

            station_defs = [_format_station_definition(row) for row in rows]
            telemetry.add_metric_attributes(station_count=len(station_defs))
            updated_at = _max_updated_at(rows)
            return {"updated_at": updated_at, "stations": station_defs}
        except HTTPException:
            raise
        except Exception as exc:
            telemetry.set_status_code(503)
            logfire.error("查询 stations 表失败: {error}", error=str(exc))
            raise HTTPException(status_code=503, detail="站点信息不可用")


@app.get("/api/status")
@apply_rate_limit(Config.RATE_LIMIT_STATUS)
async def get_status(
    request: Request,
    provider: Optional[str] = Query(
        None,
        min_length=1,
        max_length=32,
        regex=PROVIDER_PATTERN,
        description="服务商标识，只允许字母、数字、下划线和连字符",
    ),
    hash_id: Optional[str] = Query(
        None,
        min_length=8,
        max_length=8,
        regex=HASH_ID_PATTERN,
        description="站点唯一标识，必须是 8 位十六进制字符串",
    ),
    devid: Optional[str] = Query(
        None,
        alias="devid",
        min_length=1,
        max_length=64,
        regex=DEVID_PATTERN,
        description="设备 ID，可为数字或包含逗号分隔的多个 ID",
    ),
):
    """查询所有站点状态（优先从缓存读取）

    Args:
        provider: 可选，服务商标识（如 'neptune'），如果指定则只返回该服务商的数据
        id: 可选，站点唯一标识，如果指定则只返回匹配的站点
    """
    station_id = hash_id
    has_filter = any([station_id, provider, devid])
    with ApiCallTelemetry(request, "/api/status") as telemetry:
        telemetry.add_metric_attributes(
            provider=provider or "all",
            has_station_id=bool(station_id),
            has_devid=bool(devid),
        )
        logfire.info(
            "收到 /api/status 请求，provider={provider}, hash_id={station_id}, devid={devid}",
            provider=provider,
            station_id=station_id,
            devid=devid,
        )

        if devid and not provider:
            telemetry.set_status_code(400)
            raise HTTPException(status_code=400, detail="查询 devid 时必须同时提供 provider 参数")

        try:
            with logfire.span(
                "读取站点状态缓存",
                provider=provider or "all",
                station_id=station_id,
                devid=devid,
            ):
                cache_result = _build_cached_response(
                    provider=provider,
                    station_id=station_id,
                    devid=devid,
                )

            if cache_result is None:
                telemetry.add_metric_attributes(cache_hit=False)
                if has_filter:
                    telemetry.set_status_code(404)
                    logfire.info(
                        "过滤条件 provider={provider}, hash_id={hash_id}, devid={devid} 未命中",
                        provider=provider,
                        hash_id=station_id,
                        devid=devid,
                    )
                    raise HTTPException(status_code=404, detail="未找到匹配站点或设备")

                fallback = _get_fallback_status_response()
                if fallback is None:
                    telemetry.set_status_code(503)
                    logfire.warn("latest 缓存无可用数据且无本地快照，返回 503")
                    raise HTTPException(status_code=503, detail="站点状态暂不可用")

                response, filter_mode = fallback
                station_count = len(response.get("stations", []))
                telemetry.add_metric_attributes(
                    data_source="fallback",
                    response_station_count=station_count,
                    filter_mode=filter_mode,
                )
                logfire.warn(
                    "latest 缓存缺失，使用内存快照返回 {station_count} 个站点",
                    station_count=station_count,
                )
                return response

            response, filter_mode = cache_result
            station_count = len(response.get("stations", []))
            telemetry.add_metric_attributes(
                cache_hit=True,
                data_source="cache",
                response_station_count=station_count,
                filter_mode=filter_mode,
            )
            logfire.info(
                "使用 latest 缓存返回 {station_count} 个站点",
                station_count=station_count,
            )
            return response
        except HTTPException:
            raise
        except Exception as e:
            telemetry.set_status_code(500)
            logfire.error("查询失败: {error}", error=str(e))
            raise HTTPException(status_code=500, detail="查询站点失败")

if __name__ == "__main__":
    import uvicorn

    logfire.info(
        "启动服务器: {host}:{port}",
        host=Config.API_HOST,
        port=Config.API_PORT,
    )
    uvicorn.run(
        app,
        host=Config.API_HOST,
        port=Config.API_PORT,
        log_config=None,  # 使用我们自己的日志配置
    )
