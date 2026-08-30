"""
Chart cache key helpers.

Purpose:
    Build stable hashes for birth inputs so identical charts hit disk cache.

Inputs:
    Name, aware datetime, lat/lon, gender, engine version.

Outputs:
    Hex SHA-256 chart_key string.
"""

from __future__ import annotations

import hashlib
from datetime import datetime


def make_chart_key(
    name: str,
    dt_aware: datetime,
    lat: float,
    lon: float,
    gender: str,
    engine_version: str,
) -> str:
    """
    Return a stable chart cache key.

    Coordinates are rounded to 6 decimals (~0.1m) to avoid float noise misses.
    """
    if dt_aware.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    utc = dt_aware.isoformat()
    raw = "|".join(
        [
            name.strip().lower(),
            utc,
            f"{lat:.6f}",
            f"{lon:.6f}",
            (gender or "Unknown").strip(),
            engine_version,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
