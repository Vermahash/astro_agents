"""
SQLite chart field store for tool-facing slice lookups.

Purpose:
    Persist each top-level structured_payload key as a row so MCP/agent tools
    can fetch only the fields needed for a question (no full-packet dumps).

Inputs:
    chart_key, meta, structured_payload from chart_service.

Outputs:
    Charts + field rows in data/sqlite/charts.db.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from shared.config import SQLITE_DIR, ensure_data_dirs

logger = logging.getLogger(__name__)

DB_PATH = SQLITE_DIR / "charts.db"

FIELD_DESCRIPTIONS: dict[str, str] = {
    "natal_core": "Core natal summary (lagna, planets overview)",
    "cusps": "KP house cusps with sign/star/sub lords",
    "planet_star_sub_lords": "Planet star/sub/sub-sub lord table",
    "kp_astrology_matrix": "KP matrix / significator tables",
    "kp_master_packet": "Master KP packet aggregates",
    "kp_prediction": "KP prediction / significator analysis blocks",
    "unified_kundali": "Unified kundali layout data",
    "panchang": "Panchang elements at birth",
    "special_yogas": "Yogas and doshas detected",
    "natal_drishti_table": "Natal aspect (drishti) table",
    "natal_house_drishti_summary": "House-wise drishti summary",
    "current_transit_aspect_impacts": "Current transit aspect impacts",
    "current_transit_degree_hits": "Current transit degree hits",
}


def _connect() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create charts and chart_fields tables if missing."""
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS charts (
                chart_key TEXT PRIMARY KEY,
                engine_version TEXT NOT NULL,
                meta_json TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS chart_fields (
                chart_key TEXT NOT NULL,
                field TEXT NOT NULL,
                json TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                PRIMARY KEY (chart_key, field),
                FOREIGN KEY (chart_key) REFERENCES charts(chart_key) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chart_fields_key ON chart_fields(chart_key);
            """
        )


def upsert_chart_document(doc: dict[str, Any]) -> None:
    """
    Write/replace chart meta + one row per structured_payload top-level key.

    Inputs:
        Full chart document from chart_service (chart_key, meta, structured_payload).
    """
    init_db()
    chart_key = doc["chart_key"]
    meta = doc.get("meta") or {}
    payload = doc.get("structured_payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO charts (chart_key, engine_version, meta_json)
            VALUES (?, ?, ?)
            ON CONFLICT(chart_key) DO UPDATE SET
                engine_version=excluded.engine_version,
                meta_json=excluded.meta_json
            """,
            (chart_key, doc.get("engine_version") or "", json.dumps(meta, ensure_ascii=False)),
        )
        conn.execute("DELETE FROM chart_fields WHERE chart_key = ?", (chart_key,))
        for field, value in payload.items():
            blob = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            conn.execute(
                """
                INSERT INTO chart_fields (chart_key, field, json, bytes)
                VALUES (?, ?, ?, ?)
                """,
                (chart_key, str(field), blob, len(blob.encode("utf-8"))),
            )
    logger.info("chart_store upsert key=%s fields=%s", chart_key[:12], len(payload))


def chart_exists(chart_key: str) -> bool:
    init_db()
    with _db() as conn:
        row = conn.execute("SELECT 1 FROM charts WHERE chart_key = ?", (chart_key,)).fetchone()
    return row is not None


def get_meta(chart_key: str) -> dict[str, Any] | None:
    init_db()
    with _db() as conn:
        row = conn.execute(
            "SELECT meta_json FROM charts WHERE chart_key = ?", (chart_key,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["meta_json"])


def list_fields(chart_key: str) -> list[dict[str, Any]]:
    """Return field catalog with descriptions and byte sizes."""
    init_db()
    with _db() as conn:
        rows = conn.execute(
            "SELECT field, bytes FROM chart_fields WHERE chart_key = ? ORDER BY field",
            (chart_key,),
        ).fetchall()
    if not rows:
        return []
    out = []
    for r in rows:
        name = r["field"]
        out.append(
            {
                "field": name,
                "bytes": r["bytes"],
                "description": FIELD_DESCRIPTIONS.get(name, "KP structured payload field"),
            }
        )
    return out


def get_fields(chart_key: str, fields: list[str]) -> dict[str, Any]:
    """
    Load selected field JSON objects.

    Raises:
        KeyError: chart missing or requested fields not found.
    """
    init_db()
    if not fields:
        return {}
    with _db() as conn:
        if not conn.execute("SELECT 1 FROM charts WHERE chart_key = ?", (chart_key,)).fetchone():
            raise KeyError(f"chart not found in store: {chart_key}")
        placeholders = ",".join("?" * len(fields))
        rows = conn.execute(
            f"SELECT field, json FROM chart_fields WHERE chart_key = ? AND field IN ({placeholders})",
            (chart_key, *fields),
        ).fetchall()
    found = {r["field"]: json.loads(r["json"]) for r in rows}
    missing = [f for f in fields if f not in found]
    if missing:
        raise KeyError(f"unknown fields for chart: {', '.join(missing)}")
    return found


def ensure_chart_in_store(chart_key: str) -> bool:
    """
    If chart is missing from SQLite but present as JSON cache, backfill store.

    Returns:
        True if chart is available in store after call.
    """
    if chart_exists(chart_key):
        return True
    from shared.chart_service import get_cached_chart

    doc = get_cached_chart(chart_key)
    if doc is None:
        return False
    upsert_chart_document(doc)
    return True
