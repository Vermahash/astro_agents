"""
Shared chart tool registry for the ask agent and MCP server.

Purpose:
    Deterministic, size-capped reads from the SQLite chart field store.
    No LLM inside — tools only return precomputed KP engine data.

Inputs:
    chart_key and tool-specific args (fields, house, planet, query).

Outputs:
    JSON-serializable dicts suitable for tool results / MCP.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from shared.chart_store import (
    FIELD_DESCRIPTIONS,
    ensure_chart_in_store,
    get_fields,
    get_meta,
    list_fields,
)
from shared.places import search_places

logger = logging.getLogger(__name__)

# Soft cap on JSON returned by a single get_chart_slice call
MAX_SLICE_CHARS = 20_000


@dataclass(frozen=True)
class ToolSpec:
    """One callable tool with OpenAI-style JSON schema."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


def _require_chart(chart_key: str) -> None:
    if not chart_key or not str(chart_key).strip():
        raise ValueError("chart_key is required")
    if not ensure_chart_in_store(chart_key):
        raise FileNotFoundError(f"chart not found: {chart_key}")


def _truncate_payload(obj: Any, max_chars: int = MAX_SLICE_CHARS) -> tuple[Any, bool]:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if len(raw) <= max_chars:
        return obj, False
    # Prefer dropping huge string leaves inside dicts
    if isinstance(obj, dict):
        slim: dict[str, Any] = {}
        used = 2
        for k, v in obj.items():
            piece = json.dumps({k: v}, ensure_ascii=False, separators=(",", ":"))
            if used + len(piece) > max_chars:
                slim[k] = "...[truncated]"
                break
            slim[k] = v
            used += len(piece)
        return slim, True
    return raw[:max_chars] + "…[truncated]", True


def tool_list_chart_fields(chart_key: str) -> dict[str, Any]:
    """Catalog available KP payload fields for a chart."""
    _require_chart(chart_key)
    fields = list_fields(chart_key)
    return {"chart_key": chart_key, "fields": fields, "count": len(fields)}


def tool_get_chart_meta(chart_key: str) -> dict[str, Any]:
    """Birth meta: name, datetime, coords, lagna, moon nakshatra."""
    _require_chart(chart_key)
    meta = get_meta(chart_key)
    return {"chart_key": chart_key, "meta": meta}


def tool_get_chart_slice(chart_key: str, fields: list[str]) -> dict[str, Any]:
    """Return only the requested structured_payload fields (size-capped)."""
    _require_chart(chart_key)
    if not fields:
        raise ValueError("fields must be a non-empty list")
    # Normalize + dedupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for f in fields:
        name = str(f).strip()
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    data = get_fields(chart_key, ordered)
    truncated_any = False
    out: dict[str, Any] = {}
    for k, v in data.items():
        slim, trunc = _truncate_payload(v)
        out[k] = slim
        truncated_any = truncated_any or trunc
    blob = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if len(blob) > MAX_SLICE_CHARS:
        blob = blob[:MAX_SLICE_CHARS] + "…[truncated]"
        truncated_any = True
        out = {"_truncated_json": blob}
    return {
        "chart_key": chart_key,
        "fields": ordered,
        "data": out,
        "bytes": len(blob.encode("utf-8")),
        "truncated": truncated_any,
    }


def tool_get_cusp(chart_key: str, house: int) -> dict[str, Any]:
    """Single KP house cusp (1–12) from the cusps field."""
    _require_chart(chart_key)
    if not isinstance(house, int) or house < 1 or house > 12:
        raise ValueError("house must be an integer 1–12")
    cusps = get_fields(chart_key, ["cusps"]).get("cusps")
    entry: Any = None
    if isinstance(cusps, dict):
        entry = cusps.get(str(house)) or cusps.get(house)
        if entry is None:
            # common shapes: list indexed 0 or 1
            pass
    if entry is None and isinstance(cusps, list):
        # try 1-based then 0-based
        if 1 <= house <= len(cusps):
            entry = cusps[house - 1]
        elif 0 <= house < len(cusps):
            entry = cusps[house]
    if entry is None and isinstance(cusps, dict):
        # nested under houses / house_N
        for key in (f"house_{house}", f"H{house}", f"cusp_{house}"):
            if key in cusps:
                entry = cusps[key]
                break
    return {"chart_key": chart_key, "house": house, "cusp": entry, "raw_type": type(cusps).__name__}


def tool_get_planet(chart_key: str, planet: str) -> dict[str, Any]:
    """Planet star/sub lord row for a named planet."""
    _require_chart(chart_key)
    name = (planet or "").strip()
    if not name:
        raise ValueError("planet is required")
    table = get_fields(chart_key, ["planet_star_sub_lords"]).get("planet_star_sub_lords")
    entry: Any = None
    if isinstance(table, dict):
        # case-insensitive key match
        lower = {str(k).lower(): v for k, v in table.items()}
        entry = lower.get(name.lower())
        if entry is None:
            for k, v in table.items():
                if name.lower() in str(k).lower():
                    entry = v
                    break
    elif isinstance(table, list):
        for row in table:
            if isinstance(row, dict):
                label = str(row.get("planet") or row.get("name") or row.get("body") or "")
                if label.lower() == name.lower() or name.lower() in label.lower():
                    entry = row
                    break
    return {"chart_key": chart_key, "planet": name, "data": entry}


def tool_search_places(q: str, limit: int = 10) -> dict[str, Any]:
    """City typeahead (same CSV as Streamlit KP)."""
    hits = search_places(q, limit=min(max(limit, 1), 30))
    return {"query": q, "results": hits, "count": len(hits)}


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="list_chart_fields",
        description=(
            "List available KP chart payload fields for chart_key with sizes and descriptions. "
            "Call this first to decide which slices to fetch."
        ),
        parameters={
            "type": "object",
            "properties": {
                "chart_key": {"type": "string", "description": "Cached chart id"},
            },
            "required": ["chart_key"],
        },
        handler=tool_list_chart_fields,
    ),
    ToolSpec(
        name="get_chart_meta",
        description="Get birth meta for chart_key (name, datetime, lat/lon, lagna, moon nakshatra).",
        parameters={
            "type": "object",
            "properties": {
                "chart_key": {"type": "string"},
            },
            "required": ["chart_key"],
        },
        handler=tool_get_chart_meta,
    ),
    ToolSpec(
        name="get_chart_slice",
        description=(
            "Fetch only the listed structured_payload fields for chart_key. "
            "Prefer cusps, planet_star_sub_lords, kp_prediction for event questions; "
            "never request the entire catalog at once."
        ),
        parameters={
            "type": "object",
            "properties": {
                "chart_key": {"type": "string"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Payload field names from list_chart_fields",
                },
            },
            "required": ["chart_key", "fields"],
        },
        handler=tool_get_chart_slice,
    ),
    ToolSpec(
        name="get_cusp",
        description="Get a single KP house cusp (house 1–12) for significator checks.",
        parameters={
            "type": "object",
            "properties": {
                "chart_key": {"type": "string"},
                "house": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["chart_key", "house"],
        },
        handler=tool_get_cusp,
    ),
    ToolSpec(
        name="get_planet",
        description="Get star/sub/sub-sub lord data for one planet (e.g. Moon, Venus, Jupiter).",
        parameters={
            "type": "object",
            "properties": {
                "chart_key": {"type": "string"},
                "planet": {"type": "string"},
            },
            "required": ["chart_key", "planet"],
        },
        handler=tool_get_planet,
    ),
    ToolSpec(
        name="search_places",
        description="Search birth places by city name prefix (min 3 chars).",
        parameters={
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["q"],
        },
        handler=tool_search_places,
    ),
]

TOOLS_BY_NAME: dict[str, ToolSpec] = {t.name: t for t in TOOLS}


def openai_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI chat.completions tools array."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS
    ]


def tool_names() -> list[str]:
    return [t.name for t in TOOLS]


def run_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Execute a registered tool by name.

    Returns:
        {ok, name, result|error, ms, bytes}
    """
    t0 = time.perf_counter()
    args = arguments or {}
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {
            "ok": False,
            "name": name,
            "error": f"unknown tool: {name}",
            "ms": 0.0,
            "bytes": 0,
        }
    try:
        result = spec.handler(**args)
        blob = json.dumps(result, ensure_ascii=False, default=str)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": True,
            "name": name,
            "result": result,
            "ms": round(ms, 1),
            "bytes": len(blob.encode("utf-8")),
        }
    except TypeError as exc:
        ms = (time.perf_counter() - t0) * 1000
        return {"ok": False, "name": name, "error": f"bad arguments: {exc}", "ms": round(ms, 1), "bytes": 0}
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        logger.exception("tool %s failed", name)
        return {
            "ok": False,
            "name": name,
            "error": f"{type(exc).__name__}: {exc}",
            "ms": round(ms, 1),
            "bytes": 0,
        }


def field_catalog_hint() -> str:
    """Short static hint of known field names for system prompt."""
    lines = [f"- {k}: {v}" for k, v in FIELD_DESCRIPTIONS.items()]
    return "Known KP field names:\n" + "\n".join(lines)
