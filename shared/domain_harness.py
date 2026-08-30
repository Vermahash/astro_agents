"""
Domain harness — maps life domains to required chart payload slices.

Purpose:
    Smart query routing: only send Python-computed fields the Brain/specialists
    need for a domain (finance, marriage, career, …).

Inputs:
    User question text (keyword router) or explicit domain id.

Outputs:
    {domain, inventory_title, payload_keys, specialist_slices, nadi_combos, kp_houses}
"""

from __future__ import annotations

import re
from typing import Any

# Top-level domains (extend as needed)
DOMAINS = (
    "finance",
    "marriage",
    "career",
    "health",
    "children",
    "education",
    "foreign",
    "general",
)

# Which structured_payload keys the harness should fetch per domain
DOMAIN_PAYLOAD_KEYS: dict[str, tuple[str, ...]] = {
    "finance": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "yoga_rule_matrix",
        "ashtakavarga_sav",
        "ashtakavarga_bav",
        "bnn_module",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "kp_astrology_matrix",
    ),
    "marriage": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "kp_astrology_matrix",
        "natal_drishti_table",
        "natal_house_drishti_summary",
    ),
    "career": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "ashtakavarga_sav",
        "bnn_module",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "kp_astrology_matrix",
    ),
    "health": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "ashtakavarga_sav",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
    ),
    "children": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
    ),
    "education": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "ashtakavarga_sav",
        "cusps",
        "planet_star_sub_lords",
    ),
    "foreign": (
        "natal_core",
        "unified_kundali",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "current_transit_aspect_impacts",
    ),
    "general": (
        "natal_core",
        "cusps",
        "planet_star_sub_lords",
        "kp_master_packet",
        "kp_prediction",
    ),
}

# Nadi house combination sets referenced in inventory (documentation for Brain prompt)
DOMAIN_NADI: dict[str, dict[str, list[int]]] = {
    "finance": {
        "inflow": [2, 6, 10, 11],
        "fortune": [5, 9, 11],
        "loss": [6, 8, 12],
    },
    "marriage": {
        "promise": [2, 7, 11],
        "denial": [1, 6, 10, 12],
    },
    "career": {
        "rise": [2, 6, 10, 11],
        "obstruction": [8, 12],
    },
}

DOMAIN_KP_CUSPS: dict[str, list[int]] = {
    "finance": [2, 11],
    "marriage": [7, 2, 11],
    "career": [10, 6, 11],
    "health": [6, 8, 12],
    "children": [5, 11],
}

INVENTORY_TITLES: dict[str, str] = {
    "finance": "FINANCIAL EVALUATION INVENTORY",
    "marriage": "MARRIAGE / PARTNERSHIP INVENTORY",
    "career": "CAREER & PROFESSION INVENTORY",
    "health": "HEALTH & VIABILITY INVENTORY",
    "children": "PROGENY INVENTORY",
    "education": "EDUCATION INVENTORY",
    "foreign": "FOREIGN / RELOCATION INVENTORY",
    "general": "GENERAL CHART INVENTORY",
}

_DOMAIN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"financ|money|wealth|income|salary|debt|property|invest|asset|2nd|11th|gain", re.I), "finance"),
    (re.compile(r"marri|spouse|wife|husband|7th|partner|love\s*life|relationship", re.I), "marriage"),
    (re.compile(r"career|job|profess|10th|boss|promot|work|business|service", re.I), "career"),
    (re.compile(r"health|diseas|6th|illness|hospital|surgery", re.I), "health"),
    (re.compile(r"child|putra|5th|pregnan|offspring", re.I), "children"),
    (re.compile(r"educat|study|exam|9th|college|degree", re.I), "education"),
    (re.compile(r"foreign|abroad|visa|12th|travel|settle", re.I), "foreign"),
]


def classify_domain(question: str) -> str:
    """Return domain id from question keywords."""
    q = question or ""
    for pat, domain in _DOMAIN_PATTERNS:
        if pat.search(q):
            return domain
    return "general"


def build_harness_plan(question: str, available_keys: set[str] | None = None) -> dict[str, Any]:
    """
    Build harness fetch plan for a question.

    Returns:
        domain, inventory_title, keys (filtered to available), nadi_combos, kp_cusps
    """
    domain = classify_domain(question)
    wanted = DOMAIN_PAYLOAD_KEYS.get(domain, DOMAIN_PAYLOAD_KEYS["general"])
    if available_keys is not None:
        keys = [k for k in wanted if k in available_keys]
    else:
        keys = list(wanted)
    return {
        "domain": domain,
        "inventory_title": INVENTORY_TITLES.get(domain, "DOMAIN INVENTORY"),
        "keys": keys,
        "nadi_combos": DOMAIN_NADI.get(domain, {}),
        "kp_cusps": DOMAIN_KP_CUSPS.get(domain, []),
        "pre_audit_prompt": "docs/prompts/PRE_AUDIT_DIRECTIVE.md",
    }
