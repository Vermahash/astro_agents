"""
Chart computation + disk cache service.

Purpose:
    Call engine.astro_kp.calculate_vedic_charts once per unique birth input,
    persist structured_payload, and serve cache hits for web/Telegram.

Inputs:
    Birth fields (name, aware datetime, lat, lon, gender) and force_recompute flag.

Outputs:
    Dict with chart_key, cached, engine_version, structured_payload, summary fields.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.chart_key import make_chart_key
from shared.chart_store import ensure_chart_in_store, upsert_chart_document
from shared.config import CACHE_DIR, ENGINE_DIR, ENGINE_VERSION, ensure_data_dirs
from shared.pipeline_trace import pipeline, step

logger = logging.getLogger(__name__)

_ENGINE_READY = False


def ensure_engine_on_path() -> None:
    """Put engine/ on sys.path once (safe for repeated imports)."""
    global _ENGINE_READY
    if _ENGINE_READY:
        return
    engine = str(ENGINE_DIR.resolve())
    if engine not in sys.path:
        sys.path.insert(0, engine)
    _ENGINE_READY = True


def _ensure_engine_on_path() -> None:
    ensure_engine_on_path()


def _json_safe(obj: Any) -> Any:
    """Convert payload to JSON-serializable structures."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    # decimals / numpy scalars etc.
    try:
        if hasattr(obj, "item"):
            return obj.item()
    except Exception:
        pass
    return str(obj)


def _cache_path(chart_key: str) -> Path:
    return CACHE_DIR / f"{chart_key}.json"


def get_cached_chart(chart_key: str) -> dict[str, Any] | None:
    """Load a cached chart document or return None."""
    path = _cache_path(chart_key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compute_or_get_chart(
    *,
    name: str,
    dt_aware: datetime,
    lat: float,
    lon: float,
    gender: str = "Unknown",
    force_recompute: bool = False,
) -> dict[str, Any]:
    """
    Return chart result, using disk cache when possible.

    Raises:
        ValueError: invalid inputs.
        Exception: engine failures bubble up for API error handling.
    """
    if not name or not str(name).strip():
        raise ValueError("name is required")
    if dt_aware.tzinfo is None:
        raise ValueError("datetime_iso must include timezone offset")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("lat out of range")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("lon out of range")

    with pipeline("chart") as tr:
        with step(tr, "validate_and_key", name=name.strip()[:40]):
            ensure_data_dirs()
            chart_key = make_chart_key(name, dt_aware, lat, lon, gender, ENGINE_VERSION)
            tr.mark("chart_key", detail={"key": chart_key[:12], "force": force_recompute})

        if not force_recompute:
            with step(tr, "disk_cache_lookup", key=chart_key[:12]):
                cached = get_cached_chart(chart_key)
                if cached is not None:
                    cached["cached"] = True
                    # Backfill SQLite field store for tool lookups
                    with step(tr, "sqlite_ensure"):
                        ensure_chart_in_store(chart_key)
                    tr.mark("cache_hit", detail={"key": chart_key[:12]})
                    logger.info("chart cache hit key=%s", chart_key[:12])
                    return cached

        with step(tr, "import_engine"):
            _ensure_engine_on_path()
            import astro_kp  # noqa: WPS433 — deferred so path is set first

        with step(tr, "calculate_vedic_charts", key=chart_key[:12]):
            logger.info("chart compute start key=%s", chart_key[:12])
            result = astro_kp.calculate_vedic_charts(
                name.strip(),
                dt_aware,
                float(lat),
                float(lon),
                gender=gender or "Unknown",
                birth_place=f"{lat:.4f}, {lon:.4f}",
                timezone_name=str(dt_aware.tzinfo),
            )
            # Return tuple: ... structured_payload is index -3 (see engine return)
            structured_payload = result[-3]
            lagna_str = result[0]
            moon_nak = result[5]
            tr.mark(
                "engine_result",
                detail={
                    "lagna": lagna_str,
                    "moon_nak": moon_nak,
                    "payload_keys": len(structured_payload) if isinstance(structured_payload, dict) else None,
                },
            )

        with step(tr, "serialize_and_cache_write"):
            doc = {
                "chart_key": chart_key,
                "cached": False,
                "engine_version": ENGINE_VERSION,
                "meta": {
                    "name": name.strip(),
                    "datetime_iso": dt_aware.isoformat(),
                    "lat": lat,
                    "lon": lon,
                    "gender": gender or "Unknown",
                    "lagna": lagna_str,
                    "moon_nakshatra": moon_nak,
                },
                "structured_payload": _json_safe(structured_payload),
            }
            path = _cache_path(chart_key)
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            upsert_chart_document(doc)
            logger.info("chart cache write key=%s path=%s", chart_key[:12], path.name)

        return doc
