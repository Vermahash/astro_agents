"""
Unit tests for chart key, validation, and cache behavior (M1).

Purpose:
    Verifiable success criteria for the chart API service layer.

Inputs:
    Synthetic birth data (no network).

Outputs:
    pytest pass/fail.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.chart_key import make_chart_key
from shared.chart_service import compute_or_get_chart
from shared.config import ENGINE_VERSION, ensure_data_dirs


@pytest.fixture(autouse=True)
def _data_dirs(tmp_path, monkeypatch):
    cache = tmp_path / "charts"
    cache.mkdir()
    sqlite = tmp_path / "sqlite"
    sqlite.mkdir()
    monkeypatch.setattr("shared.chart_service.CACHE_DIR", cache)
    monkeypatch.setattr("shared.config.CACHE_DIR", cache)
    monkeypatch.setattr("shared.config.SQLITE_DIR", sqlite)
    monkeypatch.setattr("shared.chart_store.DB_PATH", sqlite / "charts.db")
    ensure_data_dirs()
    return cache


def test_chart_key_stable():
    dt = datetime(1990, 1, 15, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    a = make_chart_key("Test", dt, 28.6139, 77.2090, "Male", ENGINE_VERSION)
    b = make_chart_key("Test", dt, 28.6139, 77.2090, "Male", ENGINE_VERSION)
    assert a == b
    assert len(a) == 64


def test_rejects_naive_datetime():
    dt = datetime(1990, 1, 15, 14, 30)  # naive
    with pytest.raises(ValueError, match="timezone"):
        compute_or_get_chart(name="X", dt_aware=dt, lat=28.6, lon=77.2)


def test_rejects_empty_name():
    dt = datetime(1990, 1, 15, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    with pytest.raises(ValueError, match="name"):
        compute_or_get_chart(name="  ", dt_aware=dt, lat=28.6, lon=77.2)


def test_compute_and_cache_hit():
    """Requires pyswisseph."""
    dt = datetime(1990, 1, 15, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    first = compute_or_get_chart(
        name="CacheTest",
        dt_aware=dt,
        lat=28.6139,
        lon=77.2090,
        gender="Male",
    )
    assert first["cached"] is False
    assert first["chart_key"]
    assert "structured_payload" in first
    assert "kp_master_packet" in first["structured_payload"] or "natal_core" in first["structured_payload"]

    second = compute_or_get_chart(
        name="CacheTest",
        dt_aware=dt,
        lat=28.6139,
        lon=77.2090,
        gender="Male",
    )
    assert second["cached"] is True
    assert second["chart_key"] == first["chart_key"]
