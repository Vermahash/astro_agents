"""
Packet planner — chooses which KP payload slices to send for a question.

Purpose:
    First interpretive planning step: decide what information the synthesizer
    needs so we do not dump the entire chart into the LLM every time.

Inputs:
    User question + full structured_payload keys.

Outputs:
    Ordered list of payload keys + short rationale for pipeline logs.
"""

from __future__ import annotations

import re
from typing import Any

# Always include core KP facts (enough for a non-vague CSL/significator answer)
CORE_KEYS = (
    "natal_core",
    "cusps",
    "planet_star_sub_lords",
    "kp_astrology_matrix",
    "kp_master_packet",
    "kp_prediction",
)

TOPIC_KEYS: list[tuple[re.Pattern[str], tuple[str, ...], str]] = [
    (
        re.compile(r"marri|spouse|wed|7th|dara|kalatra|husband|wife|love\s*life|relationship", re.I),
        ("special_yogas", "natal_drishti_table", "natal_house_drishti_summary"),
        "marriage/7th-house focus",
    ),
    (
        re.compile(r"job|career|profess|service|10th|boss|promot|work|employ|business|office", re.I),
        ("special_yogas", "current_transit_aspect_impacts"),
        "career/10th focus",
    ),
    (
        re.compile(r"health|diseas|hospital|6th|illness|disease|surgery|medic", re.I),
        ("special_yogas", "current_transit_degree_hits"),
        "health/6th focus",
    ),
    (
        re.compile(r"money|wealth|finance|income|2nd|11th|gain|salary|loan|debt|property|house\b|land", re.I),
        ("special_yogas", "current_transit_aspect_impacts"),
        "finance/property focus",
    ),
    (
        re.compile(r"child|putra|5th|pregnan|offspring", re.I),
        ("special_yogas", "natal_drishti_table"),
        "children/5th focus",
    ),
    (
        re.compile(r"foreign|abroad|visa|travel|12th|settle|immigration", re.I),
        ("special_yogas", "current_transit_aspect_impacts"),
        "foreign/12th focus",
    ),
    (
        re.compile(r"educat|study|college|exam|9th|degree", re.I),
        ("special_yogas", "natal_drishti_table"),
        "education/9th focus",
    ),
    (
        re.compile(r"dasha|timing|when|period|transit|year|month|date", re.I),
        ("unified_kundali", "panchang", "current_transit_aspect_impacts", "current_transit_degree_hits"),
        "timing/dasha/transit focus",
    ),
    (
        re.compile(r"yog|dosha|mangal|kaal|sarp|pitra", re.I),
        ("special_yogas", "natal_drishti_table"),
        "yoga/dosha focus",
    ),
]


def plan_packet_keys(question: str, available: dict[str, Any]) -> dict[str, Any]:
    """
    Pick payload keys for this question.

    Returns:
        {keys: list[str], rationale: str, matched_topics: list[str]}
    """
    keys: list[str] = []
    seen: set[str] = set()
    topics: list[str] = []

    def add(ks: tuple[str, ...] | list[str]) -> None:
        for k in ks:
            if k in available and k not in seen:
                seen.add(k)
                keys.append(k)

    add(CORE_KEYS)
    q = question or ""
    for pat, extra, label in TOPIC_KEYS:
        if pat.search(q):
            add(extra)
            topics.append(label)

    if not topics:
        # Keep general asks tight — core KP only (avoids vague mega-dumps)
        topics.append("general KP core (tight)")

    rationale = "; ".join(topics)
    return {"keys": keys, "rationale": rationale, "matched_topics": topics}
