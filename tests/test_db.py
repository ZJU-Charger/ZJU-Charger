"""Unit tests for db/ repository helpers.

These tests avoid hitting the real Supabase service by patching the
`get_supabase_client` function or downstream helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db import pipeline, usage_repo


# ---------------------------------------------------------------------------
# record_usage_data tests
# ---------------------------------------------------------------------------


def make_station(station_id: str) -> Dict[str, Any]:
    return {
        "hash_id": station_id,
        "id": station_id,
        "free": 1,
        "used": 0,
        "total": 1,
        "error": 0,
    }


def test_record_usage_data_requires_timestamp(monkeypatch):
    calls: List[str] = []

    def fake_batch_insert(data: Dict[str, Any], sheet_name: str) -> bool:
        calls.append(sheet_name)
        return True

    monkeypatch.setattr(pipeline, "batch_insert", fake_batch_insert)

    data = {"stations": [make_station("foo")]}

    assert pipeline.record_usage_data(data, history_mode_enabled=False) is False
    assert calls == []


def test_record_usage_data_cache_only(monkeypatch):
    calls: List[str] = []

    def fake_batch_insert(data: Dict[str, Any], sheet_name: str) -> bool:
        calls.append(sheet_name)
        return True

    monkeypatch.setattr(pipeline, "batch_insert", fake_batch_insert)

    payload = {
        "updated_at": "2025-01-01T00:00:00+08:00",
        "stations": [make_station("foo")],
    }

    assert pipeline.record_usage_data(payload, history_mode_enabled=False) is True
    assert calls == ["latest"]


def test_record_usage_data_history_mode(monkeypatch):
    calls: List[str] = []

    def fake_batch_insert(data: Dict[str, Any], sheet_name: str) -> bool:
        calls.append(sheet_name)
        return True

    monkeypatch.setattr(pipeline, "batch_insert", fake_batch_insert)

    payload = {
        "updated_at": "2025-01-01T00:00:00+08:00",
        "stations": [make_station("foo")],
    }

    assert pipeline.record_usage_data(payload, history_mode_enabled=True) is True
    assert calls == ["latest", "usage"]


# ---------------------------------------------------------------------------
# load_latest tests
# ---------------------------------------------------------------------------


@dataclass
class FakeResult:
    data: List[Dict[str, Any]]


class FakeQuery:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> "FakeQuery":
        return self

    def execute(self) -> FakeResult:
        return FakeResult(self._rows)


class FakeClient:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def table(self, name: str) -> FakeQuery:
        assert name == usage_repo.LATEST_TABLE_NAME
        return FakeQuery(self._rows)


def test_load_latest_returns_none_without_client(monkeypatch):
    monkeypatch.setattr(usage_repo, "get_supabase_client", lambda: None)
    assert usage_repo.load_latest() is None


def test_load_latest_returns_latest_timestamp(monkeypatch):
    rows = [
        {
            "hash_id": "station_b",
            "snapshot_time": "2025-01-01T08:00:00+08:00",
            "free": 2,
            "used": 1,
            "total": 3,
            "error": 0,
        },
        {
            "hash_id": "station_a",
            "snapshot_time": "2025-01-01T07:30:00+08:00",
            "free": 1,
            "used": 0,
            "total": 1,
            "error": 0,
        },
    ]

    fake_client = FakeClient(rows)
    monkeypatch.setattr(usage_repo, "get_supabase_client", lambda: fake_client)

    result = usage_repo.load_latest()
    assert result is not None
    assert result["updated_at"] == "2025-01-01T08:00:00+08:00"
    # rows should be returned intact for downstream aggregation
    assert result["rows"] == rows
