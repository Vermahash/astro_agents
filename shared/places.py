"""
Place / city search service (Streamlit search_city parity).

Purpose:
    Typeahead over global_cities_full.csv using the same prefix index as
    engine.astro_kp.search_city so lat/lon fill automatically.

Inputs:
    Query string (min 3 chars).

Outputs:
    List of {label, lat, lon}.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.chart_service import ensure_engine_on_path

logger = logging.getLogger(__name__)

_city_df = None
_city_index = None


def _load() -> tuple[Any, Any]:
    global _city_df, _city_index
    if _city_df is not None and _city_index is not None:
        return _city_df, _city_index
    ensure_engine_on_path()
    import astro_kp

    df = astro_kp.load_city_data()
    if df is None:
        raise RuntimeError("city database unavailable (global_cities_full.csv)")
    index = astro_kp.build_city_index(df)
    _city_df = df
    _city_index = index
    logger.info("city index ready rows=%s", len(df))
    return df, index


def search_places(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return place matches for autocomplete (empty if query too short)."""
    q = (query or "").strip()
    if len(q) < 3:
        return []
    _, index = _load()
    import astro_kp

    raw = astro_kp.search_city(q, index)
    out: list[dict[str, Any]] = []
    for label, value in raw[:limit]:
        lat, lon = value
        out.append({"label": label, "lat": float(lat), "lon": float(lon)})
    return out
