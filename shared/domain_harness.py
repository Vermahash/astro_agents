"""
Domain harness — maps life domains to required chart payload slices.

Purpose:
    Smart query routing: join one or more life aspects (finance, health, …)
    to the Python-computed fields specialists and the Brain need.

Inputs:
    User question text (keyword router) or explicit domain id.

Outputs:
    {domains, domain, inventory_title, keys, specialists, checkpoints,
     nadi_combos, kp_cusps, houses, planets}
"""

from __future__ import annotations

import re
from typing import Any

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

SPECIALISTS = ("bphs", "varga_sav", "dasha_nadi", "kp", "bnn")

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
        "natal_drishti_table",
        "natal_house_drishti_summary",
    ),
    "marriage": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "yoga_rule_matrix",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "kp_astrology_matrix",
        "natal_drishti_table",
        "natal_house_drishti_summary",
        "bnn_module",
        "ashtakavarga_sav",
    ),
    "career": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "yoga_rule_matrix",
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
        "yoga_rule_matrix",
        "ashtakavarga_sav",
        "ashtakavarga_bav",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "kp_astrology_matrix",
        "bnn_module",
        "natal_drishti_table",
        "natal_house_drishti_summary",
    ),
    "children": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "ashtakavarga_sav",
        "bnn_module",
    ),
    "education": (
        "natal_core",
        "unified_kundali",
        "special_yogas",
        "ashtakavarga_sav",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "bnn_module",
    ),
    "foreign": (
        "natal_core",
        "unified_kundali",
        "cusps",
        "planet_star_sub_lords",
        "kp_prediction",
        "current_transit_aspect_impacts",
        "ashtakavarga_sav",
        "bnn_module",
    ),
    "general": (
        "natal_core",
        "cusps",
        "planet_star_sub_lords",
        "kp_master_packet",
        "kp_prediction",
        "unified_kundali",
        "ashtakavarga_sav",
    ),
}

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
    "health": {
        "vitality": [1, 6],
        "crisis": [8, 12],
        "recovery": [5, 11],
    },
    "children": {
        "promise": [2, 5, 11],
        "denial": [1, 4, 10],
    },
    "education": {
        "success": [4, 5, 9, 11],
        "obstruction": [6, 8, 12],
    },
    "foreign": {
        "travel": [3, 9, 12],
        "settlement": [4, 7, 12],
    },
}

DOMAIN_KP_CUSPS: dict[str, list[int]] = {
    "finance": [2, 11],
    "marriage": [7, 2, 11],
    "career": [10, 6, 11],
    "health": [1, 6, 8, 12],
    "children": [5, 11],
    "education": [4, 5, 9],
    "foreign": [3, 9, 12],
    "general": [1, 11],
}

DOMAIN_HOUSES: dict[str, list[int]] = {
    "finance": [1, 2, 9, 10, 11, 12, 6, 8],
    "marriage": [1, 2, 5, 7, 8, 11, 12],
    "career": [1, 2, 6, 10, 11],
    "health": [1, 6, 8, 12],
    "children": [5, 9, 11],
    "education": [4, 5, 9],
    "foreign": [3, 9, 12],
    "general": [1, 7, 10, 11],
}

DOMAIN_PLANETS: dict[str, list[str]] = {
    "finance": ["Jupiter", "Venus", "Mercury", "Moon", "Saturn", "Mars", "Rahu"],
    "marriage": ["Venus", "Jupiter", "Moon", "Mars", "Rahu", "Saturn"],
    "career": ["Sun", "Saturn", "Mercury", "Jupiter", "Mars"],
    "health": ["Sun", "Moon", "Mars", "Saturn", "Rahu", "Ketu", "Jupiter"],
    "children": ["Jupiter", "Moon", "Mercury"],
    "education": ["Mercury", "Jupiter", "Moon"],
    "foreign": ["Rahu", "Ketu", "Saturn", "Moon"],
    "general": ["Sun", "Moon", "Jupiter", "Saturn"],
}

DOMAIN_SPECIALISTS: dict[str, tuple[str, ...]] = {
    "finance": SPECIALISTS,
    "marriage": SPECIALISTS,
    "career": SPECIALISTS,
    "health": SPECIALISTS,
    "children": ("bphs", "varga_sav", "dasha_nadi", "kp", "bnn"),
    "education": ("bphs", "varga_sav", "dasha_nadi", "kp"),
    "foreign": ("bphs", "dasha_nadi", "kp", "bnn"),
    "general": ("bphs", "kp"),
}

# Checkpoint ids specialists must audit (PRE-AUDIT inventory)
DOMAIN_CHECKPOINTS: dict[str, list[dict[str, str]]] = {
    "finance": [
        {"id": "d1_h2", "system": "bphs", "label": "D1 2nd House (Storage/Dhana)"},
        {"id": "d1_h11", "system": "bphs", "label": "D1 11th House (Income/Gains)"},
        {"id": "d1_h9", "system": "bphs", "label": "D1 9th House (Fortune/Lakshmi)"},
        {"id": "d1_1_10_links", "system": "bphs", "label": "1st/10th lord wealth links"},
        {"id": "yogas_dhana", "system": "bphs", "label": "Dhana / Parivartana / Vipareeta yogas"},
        {"id": "bhava_shift", "system": "bphs", "label": "Bhava Chalit delivery vs whole-sign"},
        {"id": "d2_hora", "system": "varga_sav", "label": "D2 Hora (wealth treasury)"},
        {"id": "d9_fortitude", "system": "varga_sav", "label": "D9 Navamsa wealth fortitude"},
        {"id": "d10_earnings", "system": "varga_sav", "label": "D10 Dasamsha earnings cluster"},
        {"id": "sav_h11", "system": "varga_sav", "label": "SAV 11th (gains threshold >28)"},
        {"id": "sav_h2", "system": "varga_sav", "label": "SAV 2nd (retention zone)"},
        {"id": "sav_h12", "system": "varga_sav", "label": "SAV 12th (drain/expense)"},
        {"id": "nadi_inflow", "system": "dasha_nadi", "label": "Nadi inflow [2,6,10,11]"},
        {"id": "nadi_fortune", "system": "dasha_nadi", "label": "Nadi fortune [5,9,11]"},
        {"id": "nadi_loss", "system": "dasha_nadi", "label": "Nadi loss [6,8,12]"},
        {"id": "vimshottari", "system": "dasha_nadi", "label": "Vimshottari MD/AD wealth links"},
        {"id": "kp_csl_2", "system": "kp", "label": "KP 2nd CSL significations"},
        {"id": "kp_csl_11", "system": "kp", "label": "KP 11th CSL significations"},
        {"id": "bnn_karakas", "system": "bnn", "label": "BNN Jupiter/Venus/Mercury karaka flow"},
        {"id": "bnn_direction", "system": "bnn", "label": "BNN directional groups"},
    ],
    "health": [
        {"id": "d1_h1", "system": "bphs", "label": "D1 1st House (vitality/constitution)"},
        {"id": "d1_h6", "system": "bphs", "label": "D1 6th House (disease/service/recovery)"},
        {"id": "d1_h8", "system": "bphs", "label": "D1 8th House (chronic/surgery/longevity)"},
        {"id": "d1_h12", "system": "bphs", "label": "D1 12th House (hospitalization/drain)"},
        {"id": "yogas_health", "system": "bphs", "label": "Health yogas / afflictions"},
        {"id": "bhava_shift", "system": "bphs", "label": "Bhava Chalit delivery vs whole-sign"},
        {"id": "d30_trimsamsa", "system": "varga_sav", "label": "D30 Trimsamsa (misfortune/ailment)"},
        {"id": "sav_h1", "system": "varga_sav", "label": "SAV 1st (vitality >28 / <25)"},
        {"id": "sav_h6", "system": "varga_sav", "label": "SAV 6th (disease/service capacity)"},
        {"id": "sav_h8", "system": "varga_sav", "label": "SAV 8th (chronic vulnerability)"},
        {"id": "nadi_vitality", "system": "dasha_nadi", "label": "Nadi vitality [1,6]"},
        {"id": "nadi_crisis", "system": "dasha_nadi", "label": "Nadi crisis [8,12]"},
        {"id": "vimshottari", "system": "dasha_nadi", "label": "Vimshottari MD/AD health links"},
        {"id": "kp_csl_6", "system": "kp", "label": "KP 6th CSL significations"},
        {"id": "kp_csl_8", "system": "kp", "label": "KP 8th CSL significations"},
        {"id": "kp_csl_1", "system": "kp", "label": "KP 1st CSL significations"},
        {"id": "bnn_karakas", "system": "bnn", "label": "BNN Sun/Moon/Mars/Saturn vitality chain"},
        {"id": "bnn_direction", "system": "bnn", "label": "BNN directional groups"},
    ],
    "marriage": [
        {"id": "d1_h7", "system": "bphs", "label": "D1 7th House (spouse)"},
        {"id": "d1_h2", "system": "bphs", "label": "D1 2nd House (family)"},
        {"id": "d9_dharma", "system": "varga_sav", "label": "D9 Navamsa marriage fortitude"},
        {"id": "sav_h7", "system": "varga_sav", "label": "SAV 7th"},
        {"id": "nadi_promise", "system": "dasha_nadi", "label": "Nadi promise [2,7,11]"},
        {"id": "nadi_denial", "system": "dasha_nadi", "label": "Nadi denial [1,6,10,12]"},
        {"id": "vimshottari", "system": "dasha_nadi", "label": "Vimshottari marriage timing"},
        {"id": "kp_csl_7", "system": "kp", "label": "KP 7th CSL"},
        {"id": "bnn_karakas", "system": "bnn", "label": "BNN Venus/Jupiter spouse karakas"},
    ],
    "career": [
        {"id": "d1_h10", "system": "bphs", "label": "D1 10th House (profession)"},
        {"id": "d1_h6", "system": "bphs", "label": "D1 6th House (service)"},
        {"id": "d10_dasamsha", "system": "varga_sav", "label": "D10 Dasamsha"},
        {"id": "sav_h10", "system": "varga_sav", "label": "SAV 10th"},
        {"id": "nadi_rise", "system": "dasha_nadi", "label": "Nadi rise [2,6,10,11]"},
        {"id": "vimshottari", "system": "dasha_nadi", "label": "Vimshottari career timing"},
        {"id": "kp_csl_10", "system": "kp", "label": "KP 10th CSL"},
        {"id": "bnn_karakas", "system": "bnn", "label": "BNN Sun/Saturn/Mercury career flow"},
    ],
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
    (
        re.compile(
            r"financ|money|wealth|income|salary|debt|property|invest|asset|"
            r"bank|saving|earn|dhan|cash|profit|gain|2nd\s*house|11th",
            re.I,
        ),
        "finance",
    ),
    (re.compile(r"marri|spouse|wife|husband|7th|partner|love\s*life|relationship|wedding", re.I), "marriage"),
    (re.compile(r"career|job|profess|10th|boss|promot|work|business|service|employ", re.I), "career"),
    (
        re.compile(
            r"health|diseas|6th|illness|hospital|surgery|vitalit|immun|chronic|"
            r"body|recovery|ailment|medic|longevity",
            re.I,
        ),
        "health",
    ),
    (re.compile(r"child|putra|5th|pregnan|offspring", re.I), "children"),
    (re.compile(r"educat|study|exam|college|degree|learning", re.I), "education"),
    (re.compile(r"foreign|abroad|visa|12th|travel|settle|immigration", re.I), "foreign"),
]


def classify_domains(question: str) -> list[str]:
    """Return all matching domain ids (order of pattern table). Empty question → general."""
    q = question or ""
    hits: list[str] = []
    for pat, domain in _DOMAIN_PATTERNS:
        if pat.search(q) and domain not in hits:
            hits.append(domain)
    return hits or ["general"]


def classify_domain(question: str) -> str:
    """Primary domain (first match) — kept for existing tests."""
    return classify_domains(question)[0]


def _merge_unique(seqs: list[list[Any] | tuple[Any, ...]]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for seq in seqs:
        for item in seq:
            key = str(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def build_harness_plan(question: str, available_keys: set[str] | None = None) -> dict[str, Any]:
    """
    Build harness fetch plan for a question (joins multiple life aspects).

    Returns:
        domains, domain (primary), inventory_title, keys, specialists,
        checkpoints, nadi_combos, kp_cusps, houses, planets, pre_audit_prompt
    """
    domains = classify_domains(question)
    primary = domains[0]
    wanted = _merge_unique([list(DOMAIN_PAYLOAD_KEYS.get(d, ())) for d in domains])
    if available_keys is not None:
        keys = [k for k in wanted if k in available_keys]
    else:
        keys = list(wanted)

    nadi: dict[str, list[int]] = {}
    for d in domains:
        nadi.update(DOMAIN_NADI.get(d, {}))

    checkpoints: list[dict[str, str]] = []
    seen_cp: set[str] = set()
    for d in domains:
        for cp in DOMAIN_CHECKPOINTS.get(d, []):
            cid = f"{d}:{cp['id']}"
            if cid in seen_cp:
                continue
            seen_cp.add(cid)
            row = dict(cp)
            row["domain"] = d
            checkpoints.append(row)

    titles = [INVENTORY_TITLES.get(d, "DOMAIN INVENTORY") for d in domains]
    specialists = _merge_unique([list(DOMAIN_SPECIALISTS.get(d, SPECIALISTS)) for d in domains])

    return {
        "domains": domains,
        "domain": primary,
        "inventory_title": " + ".join(titles),
        "keys": keys,
        "specialists": specialists,
        "checkpoints": checkpoints,
        "nadi_combos": nadi,
        "kp_cusps": _merge_unique([DOMAIN_KP_CUSPS.get(d, []) for d in domains]),
        "houses": _merge_unique([DOMAIN_HOUSES.get(d, []) for d in domains]),
        "planets": _merge_unique([DOMAIN_PLANETS.get(d, []) for d in domains]),
        "pre_audit_prompt": "docs/prompts/PRE_AUDIT_DIRECTIVE.md",
    }
