from __future__ import annotations

"""
KP MASTER LOGIC RULE BOOK
=========================

This module is the central place to encode topic-specific KP logic on top of
the generic engine in `kp_logic.py`.

Design:
- `kp_logic.analyze_master_packet` computes generic area scores + narratives
  using SAV, Hit Theory, Panchang, Bhava shifts, Avasthas.
- This file adds **per-topic analyzers** (marriage, career, health, etc.)
  that:
    - Read the same `MasterPacket`
    - Use KP-style reasoning and packet fields directly
    - Return structured, concise predictions per topic

Use this as the Python "rule book" you can keep extending as you study
more of the Astrology-for-Beginners (Vol 1–6) material.
"""

from typing import Any, Dict, List, TypedDict

from kp_logic import MasterPacket


class TopicPrediction(TypedDict, total=False):
    topic: str
    summary: str
    strengths: List[str]
    risks: List[str]
    timing_highlights: List[str]
    raw_signals: Dict[str, Any]


def analyze_marriage(packet: MasterPacket) -> TopicPrediction:
    """KP-style skeleton for marriage / long-term relationships."""

    sav = packet.get("ashtakavarga_sav") or {}
    dasha = packet.get("dasha") or {}
    hits = packet.get("transit_hits") or []
    d1 = packet.get("d1_planets") or {}
    bhava = packet.get("bhava_positions") or {}

    strengths: List[str] = []
    risks: List[str] = []
    timing: List[str] = []
    raw_signals: Dict[str, Any] = {}

    # House and SAV checks (2/7/11)
    sav_2 = int(sav.get("2", 0))
    sav_7 = int(sav.get("7", 0))
    sav_11 = int(sav.get("11", 0))

    raw_signals["sav"] = {"2": sav_2, "7": sav_7, "11": sav_11}

    if sav_7 >= 31:
        strengths.append("7th house SAV is strong, supporting relationship/marriage potential.")
    elif sav_7 <= 24:
        risks.append("7th house SAV is weak, indicating extra effort and possible delays/strains in relationships.")

    if sav_2 >= 31 or sav_11 >= 31:
        strengths.append("2nd/11th SAV support family stability and fulfillment of alliances.")

    # Basic Dasha context
    maha = dasha.get("maha")
    antara = dasha.get("antara")
    if maha and antara:
        timing.append(
            f"Current {maha}-{antara} period: check KP book for whether these lords signify 2/7/11 and connected houses."
        )

    # Transit hits involving 2/7/11 or Venus
    hit_descriptions: List[str] = []
    for h in hits:
        planet = h.get("transit_planet")
        house = h.get("house")
        target = h.get("natal_target_id")
        orb = h.get("orb_deg")
        if house in (2, 7, 11) or target in ("Venus", "7th_cusp"):
            hit_descriptions.append(
                f"Transit {planet} hits {target} in/through house {house} (orb ~{orb:.2f}°); check as a marriage/relationship trigger in KP book."
            )

    raw_signals["relationship_hits"] = hit_descriptions
    if hit_descriptions:
        timing.append("Upcoming/ongoing transit hits to 2/7/11 or Venus suggest windows for relationship events.")

    summary_parts: List[str] = []
    if strengths:
        summary_parts.append("Marriage/relationship promise is supported by several factors.")
    elif risks:
        summary_parts.append("Marriage/relationship indicators show some strain or delay; outcomes require conscious effort.")
    else:
        summary_parts.append("Marriage indications are moderate; results depend on specific Dasha and transit triggers.")

    if timing:
        summary_parts.append("Timing will crystallise when Dasha lords that signify 2/7/11 run and the noted transits occur.")

    return {
        "topic": "marriage_relationships",
        "summary": " ".join(summary_parts),
        "strengths": strengths,
        "risks": risks,
        "timing_highlights": timing,
        "raw_signals": raw_signals,
    }


def analyze_career(packet: MasterPacket) -> TopicPrediction:
    """KP-style skeleton for career / profession."""

    sav = packet.get("ashtakavarga_sav") or {}
    dasha = packet.get("dasha") or {}
    hits = packet.get("transit_hits") or []

    strengths: List[str] = []
    risks: List[str] = []
    timing: List[str] = []
    raw_signals: Dict[str, Any] = {}

    sav_10 = int(sav.get("10", 0))
    sav_6 = int(sav.get("6", 0))

    raw_signals["sav"] = {"6": sav_6, "10": sav_10}

    if sav_10 >= 31:
        strengths.append("10th house SAV is strong, supporting career growth and visibility.")
    elif sav_10 <= 24:
        risks.append("10th house SAV is weak, indicating career may require persistent effort and conscious navigation.")

    if sav_6 >= 31:
        strengths.append("6th house SAV supports service, employment and problem-solving capacity.")

    maha = dasha.get("maha")
    antara = dasha.get("antara")
    if maha and antara:
        timing.append(
            f"Current {maha}-{antara} period: verify in KP book if these lords signify 2/6/10/11 for career progress or change."
        )

    hit_descriptions: List[str] = []
    for h in hits:
        planet = h.get("transit_planet")
        house = h.get("house")
        orb = h.get("orb_deg")
        if house in (6, 10, 2, 11):
            hit_descriptions.append(
                f"Transit {planet} activates house {house} (orb ~{orb:.2f}°); check for job change/promotion effects as per KP."
            )

    raw_signals["career_hits"] = hit_descriptions
    if hit_descriptions:
        timing.append("Notable transit activations of 2/6/10/11 suggest windows for work changes, promotion, or pressure.")

    summary_parts: List[str] = []
    if strengths:
        summary_parts.append("Career promise is generally favourable in the chart.")
    elif risks:
        summary_parts.append("Career indicators are mixed or strained; progress relies on strategic timing and choices.")
    else:
        summary_parts.append("Career indications are moderate; detailed reading should lean on KP house significators and Dashas.")

    if timing:
        summary_parts.append("Use the current Dasha and recorded transits as the main timing tools per KP guidelines.")

    return {
        "topic": "career",
        "summary": " ".join(summary_parts),
        "strengths": strengths,
        "risks": risks,
        "timing_highlights": timing,
        "raw_signals": raw_signals,
    }


def analyze_health(packet: MasterPacket) -> TopicPrediction:
    """KP-style skeleton for health and disease indications."""

    sav = packet.get("ashtakavarga_sav") or {}
    dasha = packet.get("dasha") or {}
    hits = packet.get("transit_hits") or []
    special = packet.get("special_points") or {}

    strengths: List[str] = []
    risks: List[str] = []
    timing: List[str] = []
    raw_signals: Dict[str, Any] = {}

    sav_1 = int(sav.get("1", 0))
    sav_6 = int(sav.get("6", 0))
    sav_8 = int(sav.get("8", 0))
    sav_12 = int(sav.get("12", 0))

    raw_signals["sav"] = {"1": sav_1, "6": sav_6, "8": sav_8, "12": sav_12}

    if sav_1 >= 31:
        strengths.append("1st house SAV is strong, supporting overall vitality.")
    if sav_6 <= 24 or sav_8 <= 24 or sav_12 <= 24:
        risks.append("One or more dusthana houses (6/8/12) have weak SAV, indicating vulnerability to stress or health challenges.")

    if special.get("64th_navamsa"):
        risks.append("64th Navamsa is present as a sensitive point; check KP book for how transits/Dashas over it may affect health.")
    if special.get("22nd_drekkana"):
        risks.append("22nd Drekkana is highlighted; per KP rules, monitor health-related transits and Dashas near its activation.")

    maha = dasha.get("maha")
    antara = dasha.get("antara")
    if maha and antara:
        timing.append(
            f"Current {maha}-{antara} period: review whether these lords signify 6/8/12 for possible health tests, or benefic houses for recovery."
        )

    hit_descriptions: List[str] = []
    for h in hits:
        planet = h.get("transit_planet")
        house = h.get("house")
        target = h.get("natal_target_id")
        orb = h.get("orb_deg")
        if house in (1, 6, 8, 12) or target in ("64th_navamsa", "22nd_drekkana", "Gulika", "Mandi"):
            hit_descriptions.append(
                f"Transit {planet} hits {target} / house {house} (orb ~{orb:.2f}°); check KP medical rules for likely manifestations."
            )

    raw_signals["health_hits"] = hit_descriptions
    if hit_descriptions:
        timing.append("Upcoming/ongoing transits over health-relevant houses/special points suggest windows to be cautious and proactive.")

    summary_parts: List[str] = []
    if strengths and not risks:
        summary_parts.append("Overall health promise is good; only routine care is needed.")
    elif risks and not strengths:
        summary_parts.append("Chart shows notable health vulnerabilities; timing and lifestyle choices are critical.")
    else:
        summary_parts.append("Health indications are mixed; observe Dashas and transits carefully around known sensitive points.")

    if timing:
        summary_parts.append("Use KP timing (Dasha + transits to 1/6/8/12 and special points) to frame periods of stress vs recovery.")

    return {
        "topic": "health",
        "summary": " ".join(summary_parts),
        "strengths": strengths,
        "risks": risks,
        "timing_highlights": timing,
        "raw_signals": raw_signals,
    }


def analyze_all_topics(packet: MasterPacket) -> Dict[str, TopicPrediction]:
    """Convenience aggregator: run all topic analyzers and return a dict keyed by topic."""

    return {
        "marriage_relationships": analyze_marriage(packet),
        "career": analyze_career(packet),
        "health": analyze_health(packet),
        # Additional topics (wealth, property, litigation, travel, children, spirituality)
        # can be added here following the same pattern as you encode more KP rules.
    }


__all__ = [
    "TopicPrediction",
    "analyze_marriage",
    "analyze_career",
    "analyze_health",
    "analyze_all_topics",
]

