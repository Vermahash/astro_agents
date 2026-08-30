"""
Usage / budget tracking for paid LLM calls.

Purpose:
    Enforce the $5/mo hard cap from the PRD (simple JSON ledger on disk).

Inputs:
    Token counts + estimated USD per call.

Outputs:
    spent_usd, remaining_usd; raises if budget exceeded.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from shared.config import MONTHLY_BUDGET_USD, SQLITE_DIR, ensure_data_dirs

logger = logging.getLogger(__name__)

# Rough defaults for Muse Glimmer-class pricing if provider omits cost
# (override via env later). Kept conservative.
USD_PER_1M_IN = float(__import__("os").getenv("ASTRO_USD_PER_1M_IN", "0.35"))
USD_PER_1M_OUT = float(__import__("os").getenv("ASTRO_USD_PER_1M_OUT", "1.50"))


def _ledger_path() -> Path:
    ensure_data_dirs()
    month = datetime.now().strftime("%Y-%m")
    return SQLITE_DIR / f"usage_{month}.json"


def _load() -> dict:
    path = _ledger_path()
    if not path.exists():
        return {"spent_usd": 0.0, "events": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    path = _ledger_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens / 1_000_000.0) * USD_PER_1M_IN + (
        completion_tokens / 1_000_000.0
    ) * USD_PER_1M_OUT


def get_usage() -> dict:
    data = _load()
    spent = float(data.get("spent_usd", 0.0))
    return {
        "monthly_budget_usd": MONTHLY_BUDGET_USD,
        "spent_usd": round(spent, 6),
        "remaining_usd": round(max(0.0, MONTHLY_BUDGET_USD - spent), 6),
    }


def assert_budget_allows(estimated_usd: float = 0.05) -> None:
    usage = get_usage()
    if usage["spent_usd"] + estimated_usd > MONTHLY_BUDGET_USD:
        raise RuntimeError(
            f"Monthly LLM budget ${MONTHLY_BUDGET_USD} exceeded "
            f"(spent ${usage['spent_usd']:.4f}). Deterministic chart facts still work."
        )


def record_usage(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    note: str = "",
) -> float:
    cost = estimate_cost(prompt_tokens, completion_tokens)
    data = _load()
    data["spent_usd"] = float(data.get("spent_usd", 0.0)) + cost
    events = data.setdefault("events", [])
    events.append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost, 6),
            "note": note,
        }
    )
    # keep ledger small
    data["events"] = events[-200:]
    _save(data)
    logger.info("usage recorded cost=%.6f spent=%.6f model=%s", cost, data["spent_usd"], model)
    return cost
