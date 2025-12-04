"""DLMM (DianLvMama) provider adapter."""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .provider_base import ProviderBase
from fetcher.station import Station
from server.config import Config

logger = logging.getLogger(__name__)


@dataclass
class DlmmProvider(ProviderBase):
    """Adapter for the DLMM charging pile provider."""

    def __post_init__(self):
        """Load the auth token from the environment."""
        self.token = self.generate_auth_token()

    @property
    def provider(self) -> str:
        return "dlmm"

    def generate_auth_token(self) -> str:
        """
        Placeholder for generating the auth token via login or another API.
        The current implementation relies on the DLMM_AUTH environment variable.
        """
        return Config.get_provider_config_value("dlmm", "token", "")

    # --- ProviderBase abstract method implementations ---
    async def fetch_station_list(
        self, session: aiohttp.ClientSession
    ) -> Optional[List[Dict[str, Any]]]:
        """Station listing API is not available yet."""
        return None

    async def fetch_device_status(
        self, session: aiohttp.ClientSession, device_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        payload = {"stationNo": f"{device_id}"}
        url = "https://dlmmplususer.dianlvmama.com/dlServer/dlmm/getStation"
        try:
            async with session.post(
                url, headers={"authorization": self.token, "tenant-id": "1"}, json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
        except Exception as exc:
            logger.warning("DLMM request failed for device %s: %s", device_id, exc)
            return None, exc

        if result.get("code") != 200 or "data" not in result:
            err = ValueError(f"Unexpected DLMM response for device {device_id}: {result}")
            logger.warning(str(err))
            return None, err

        socket_array = result["data"].get("socketArray", []) or []
        # logger.info(socket_array)
        total = len(socket_array)
        free = sum(1 for socket in socket_array if socket.get("status") == 0)
        used = sum(1 for socket in socket_array if socket.get("status") == 1)
        error = sum(1 for socket in socket_array if socket.get("status") not in (0, 1))

        return {"total": total, "free": free, "used": used, "error": error}, None

    async def fetch_station_status(
        self, station: Station, session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        if not station.device_ids:
            return {"total": 0, "free": 0, "used": 0, "error": 0}, None

        tasks = [self.fetch_device_status(session, device_id) for device_id in station.device_ids]
        results = await asyncio.gather(*tasks)

        total = free = used = error = 0

        for device_id, (data, exc) in zip(station.device_ids, results):
            if exc or data is None:
                logger.warning("Failed to fetch DLMM status for %s: %s", device_id, exc)
                continue
            total += data["total"]
            free += data["free"]
            used += data["used"]
            error += data["error"]

        return {"total": total, "free": free, "used": used, "error": error}, None

    async def fetch_status(self, session: aiohttp.ClientSession) -> Optional[List[Dict[str, Any]]]:
        if not self.station_list:
            return []

        tasks = [self.fetch_station_status(station, session) for station in self.station_list]
        results = await asyncio.gather(*tasks)

        final_list: List[Dict[str, Any]] = []

        for station, (status, exc) in zip(self.station_list, results):
            if exc or status is None:
                logger.warning("DLMM station %s failed, fallback zeros", station.name)
                final_list.append(
                    {
                        "provider": self.provider,
                        "hash_id": station.hash_id,
                        "name": station.name,
                        "campus_id": station.campus_id,
                        "campus_name": station.campus_name,
                        "lat": station.lat,
                        "lon": station.lon,
                        "device_ids": station.device_ids,
                        "updated_at": station.updated_at,
                        "free": 0,
                        "used": 0,
                        "total": 0,
                        "error": 0,
                    }
                )
                continue

            final_list.append(
                {
                    "provider": self.provider,
                    "hash_id": station.hash_id,
                    "name": station.name,
                    "campus_id": station.campus_id,
                    "campus_name": station.campus_name,
                    "lat": station.lat,
                    "lon": station.lon,
                    "device_ids": station.device_ids,
                    "updated_at": station.updated_at,
                    "free": status["free"],
                    "used": status["used"],
                    "total": status["total"],
                    "error": status["error"],
                }
            )

        return final_list
