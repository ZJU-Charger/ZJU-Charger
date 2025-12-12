"""Background fetch loop that keeps Supabase caches fresh."""

import asyncio
import json
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import logfire

from fetcher.provider_manager import ProviderManager
from fetcher.station import Station, StationUsage
from server.config import Config
from server.logfire_setup import ensure_logfire_configured
from db import batch_upsert_stations, record_usage_data

ensure_logfire_configured()


def _now_utc8_iso() -> str:
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()


class BackgroundFetcher:
    """Runs provider fetch cycles in a dedicated thread."""

    def __init__(self) -> None:
        self._manager = ProviderManager()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logfire.info("后台抓取线程已在运行，跳过重复启动")
            return

        self._thread = threading.Thread(
            target=self._run,
            name="background-fetcher",
            daemon=True,
        )
        self._thread.start()
        logfire.info("后台抓取线程启动成功")

    def _run(self) -> None:
        asyncio.run(self._loop())

    async def _loop(self) -> None:
        self._sync_stations_from_providers()
        await self._background_fetch_task()

    def _sync_stations_from_providers(self) -> None:
        with logfire.span(
            "同步服务商站点定义",
            provider_count=len(self._manager.providers),
        ):
            stations: List[Station] = []
            for provider in self._manager.providers:
                station_defs = getattr(provider, "station_list", [])
                if station_defs:
                    stations.extend(station_defs)

            if not stations:
                logfire.warn("未从服务商加载到站点定义，跳过 stations 表同步")
                return

            if batch_upsert_stations(stations):
                logfire.info(
                    "已根据服务商定义同步 {station_count} 条站点信息到数据库",
                    station_count=len(stations),
                )
            else:
                logfire.error("同步服务商站点定义到数据库失败")

    async def _background_fetch_task(self) -> None:
        fetch_interval = Config.BACKEND_FETCH_INTERVAL

        logfire.info("执行首次后台抓取任务，初始化缓存...")
        if not self._is_night_time():
            try:
                await self._run_fetch_cycle("首次后台抓取")
            except Exception as exc:  # pragma: no cover - defensive logging
                logfire.error("首次后台抓取任务发生异常: {error}", error=str(exc))
        else:
            logfire.info("当前处于夜间暂停时段（0:10-5:50），跳过首次抓取")

        while True:
            try:
                await asyncio.sleep(fetch_interval)

                if self._is_night_time():
                    tz_utc_8 = timezone(timedelta(hours=8))
                    current_time_str = datetime.now(tz_utc_8).strftime("%H:%M")
                    logfire.info(
                        "当前时间 {current_time} 处于夜间暂停时段（0:10-5:50），跳过本次抓取",
                        current_time=current_time_str,
                    )
                    continue

                logfire.info(
                    "开始后台定时抓取数据（间隔: {interval}秒）...",
                    interval=fetch_interval,
                )

                await self._run_fetch_cycle("后台抓取")
            except Exception as exc:  # pragma: no cover - defensive logging
                logfire.error("后台抓取任务发生异常: {error}", error=str(exc))
                await asyncio.sleep(60)

    async def _run_fetch_cycle(self, reason_label: str) -> None:
        history_enabled = Config.SUPABASE_HISTORY_ENABLED
        with logfire.span(
            "执行抓取与写入流程",
            reason=reason_label,
            history_enabled=history_enabled,
        ):
            result = await self._manager.fetch_and_format()

            if result is None:
                logfire.error("{reason_label}数据失败：返回 None", reason_label=reason_label)
                return

            stations = result.get("stations", [])
            logfire.info(
                "{reason_label}实时抓取成功，共 {station_count} 个站点",
                reason_label=reason_label,
                station_count=len(stations),
            )

            station_models = self._station_models_from_result(stations)
            if station_models:
                try:
                    with logfire.span(
                        "同步站点基础信息",
                        reason=reason_label,
                        station_count=len(station_models),
                    ):
                        if batch_upsert_stations(station_models):
                            logfire.info(
                                "{reason_label}数据已同步站点基础信息，共 {count} 条",
                                reason_label=reason_label,
                                count=len(station_models),
                            )
                        else:
                            logfire.warn(
                                "{reason_label}数据同步站点基础信息失败",
                                reason_label=reason_label,
                            )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logfire.error(
                        "{reason_label}同步站点信息发生异常: {error}",
                        reason_label=reason_label,
                        error=str(exc),
                    )

            snapshot_time = result.get("updated_at", _now_utc8_iso())
            if not snapshot_time:
                snapshot_time = _now_utc8_iso()
                result["updated_at"] = snapshot_time

            with logfire.span(
                "写入 Supabase usage 缓存",
                reason=reason_label,
                station_count=len(stations),
                history_enabled=history_enabled,
            ):
                if record_usage_data(result, history_mode_enabled=history_enabled):
                    logfire.info(
                        "{reason_label}数据成功写入 Supabase（history={history_enabled}），共 {station_count} 个站点",
                        reason_label=reason_label,
                        history_enabled=history_enabled,
                        station_count=len(stations),
                    )
                else:
                    logfire.error(
                        "{reason_label}数据写入 Supabase 失败",
                        reason_label=reason_label,
                    )

    def _station_dict_to_model(self, station: Dict[str, Any]) -> Optional[Station]:
        provider = station.get("provider")
        if not provider:
            logfire.debug("站点数据缺少 provider，跳过: {station}", station=station)
            return None

        name = (
            station.get("name")
            or station.get("devdescript")
            or station.get("hash_id")
            or station.get("id")
            or "未知站点"
        )

        campus_id = self._coerce_int(station.get("campus_id"))
        device_ids = self._normalize_device_ids(
            station.get("device_ids") or station.get("devids")
        )
        updated_at = (
            station.get("updated_at")
            or station.get("snapshot_time")
            or station.get("updatedAt")
            or now_utc8_iso()
        )

        try:
            station_model = Station(
                name=name,
                provider=provider,
                campus_id=campus_id,
                lat=self._coerce_float(station.get("lat")),
                lon=self._coerce_float(station.get("lon")),
                device_ids=device_ids,
                campus_name=station.get("campus_name", ""),
                updated_at=updated_at,
            )
            station_model.usage = StationUsage(
                free=self._coerce_int(station.get("free")),
                used=self._coerce_int(station.get("used")),
                total=self._coerce_int(station.get("total")),
                error=self._coerce_int(station.get("error")),
            )
            provided_hash_id = station.get("hash_id") or station.get("id")
            if provided_hash_id:
                station_model.hash_id = provided_hash_id
            return station_model
        except Exception as exc:  # pragma: no cover - defensive logging
            logfire.debug("构建 Station 模型失败: {error}", error=str(exc))
            return None

    def _station_models_from_result(self, stations: List[Dict[str, Any]]) -> List[Station]:
        models = []
        for station in stations:
            model = self._station_dict_to_model(station)
            if model:
                models.append(model)
        return models

    @staticmethod
    def _coerce_int(value: Any, default: int = 0) -> int:
        try:
            if value is None or value == "":
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
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
                            str(item) for item in parsed if item is not None and str(item).strip()
                        ]
                except json.JSONDecodeError:
                    pass
            return [str(stripped)]

        return [str(value)]

    @staticmethod
    def _is_night_time() -> bool:
        tz_utc_8 = timezone(timedelta(hours=8))
        now = datetime.now(tz_utc_8)
        current_time = now.time()
        night_start = datetime.strptime("00:10", "%H:%M").time()
        night_end = datetime.strptime("05:50", "%H:%M").time()
        return night_start <= current_time <= night_end
