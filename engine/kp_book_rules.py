from __future__ import annotations

"""
Runtime KP rule loader backed by extracted textbook artifacts.

This keeps core calculation constants in one place, with explicit defaults that
follow textbook KP conventions when extraction data is missing.
"""

from dataclasses import dataclass
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent
EXTRACTED_DIR = ROOT / ".extracted"


@dataclass(frozen=True)
class KpRuleConfig:
    ruler_order: tuple[str, ...]
    dasha_years_seq: tuple[int, ...]
    nakshatra_span_arcmin: int
    vimshottari_total_years: int
    interval_mode: str


DEFAULT_RULES = KpRuleConfig(
    ruler_order=("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"),
    dasha_years_seq=(7, 20, 6, 10, 7, 18, 16, 19, 17),
    nakshatra_span_arcmin=800,
    vimshottari_total_years=120,
    interval_mode="half_open_start_inclusive",
)


def load_kp_rule_config() -> KpRuleConfig:
    """
    Return calculation constants used by KP star/sub/sub-sub logic.
    """
    index_path = EXTRACTED_DIR / "kp_book_index.json"
    formulas_path = EXTRACTED_DIR / "kp_formula_candidates.json"
    if not index_path.exists() or not formulas_path.exists():
        return DEFAULT_RULES

    # Hook point for future formula-driven overrides:
    # We currently keep deterministic defaults and only require extraction for provenance.
    try:
        _ = json.loads(index_path.read_text(encoding="utf-8"))
        _ = json.loads(formulas_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_RULES

    return DEFAULT_RULES

