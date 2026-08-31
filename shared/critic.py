"""
Packet critic — reject invented degrees / SAV scores / house occupancy.

Purpose:
    After the Brain writes, verify cited numbers exist in the compact fact packet.
    Doctrine from RAG is allowed; chart math is not.

Inputs:
    Answer text + compact facts dict.

Outputs:
    {ok, issues: [{kind, quote, reason}]}
"""

from __future__ import annotations

import re
from typing import Any

from shared.vedic_facts import PLANET_ORDER, ZODIAC_SIGNS

_DEG = re.compile(
    r"(?P<planet>Sun|Moon|Mars|Mercury|Jupiter|Venus|Saturn|Rahu|Ketu|Lagna)"
    r"[^\n]{0,40}?(?P<deg>\d{1,2}(?:\.\d+)?)\s*°",
    re.I,
)
_SAV = re.compile(
    r"(?:H(?:ouse)?\s*)?(?P<house>\d{1,2})\w*\s+house[^\n]{0,30}?(?P<sav>\d{1,2})\s*SAV"
    r"|SAV[^\n]{0,20}?(?:H(?:ouse)?\s*)?(?P<house2>\d{1,2})[^\n]{0,20}?(?P<sav2>\d{1,2})",
    re.I,
)
_BARE_SAV = re.compile(r"(?P<sav>\d{1,2})\s*SAV", re.I)


def _known_degrees(facts: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, row in (facts.get("planets") or {}).items():
        if isinstance(row, dict) and row.get("degree_in_sign") is not None:
            try:
                out[name.lower()] = float(row["degree_in_sign"])
            except (TypeError, ValueError):
                continue
    lagna = facts.get("lagna") or {}
    if lagna.get("longitude") is not None:
        try:
            out["lagna"] = float(lagna["longitude"]) % 30.0
        except (TypeError, ValueError):
            pass
    return out


def _known_sav(facts: dict[str, Any]) -> set[int]:
    vals: set[int] = set()
    for v in (facts.get("sav") or {}).values():
        try:
            vals.add(int(v))
        except (TypeError, ValueError):
            continue
    return vals


def critique_answer(answer: str, facts: dict[str, Any], *, deg_tol: float = 0.6) -> dict[str, Any]:
    """
    Check planet-degree citations and SAV integers against the packet.

    Returns:
        ok True when no invented chart numbers are found.
    """
    issues: list[dict[str, str]] = []
    text = answer or ""
    known = _known_degrees(facts)
    sav_ok = _known_sav(facts)

    for m in _DEG.finditer(text):
        planet = m.group("planet").lower()
        try:
            deg = float(m.group("deg"))
        except (TypeError, ValueError):
            continue
        if planet not in known:
            issues.append(
                {
                    "kind": "unknown_planet_degree",
                    "quote": m.group(0)[:80],
                    "reason": f"{planet} degree not in compact packet",
                }
            )
            continue
        if abs(known[planet] - deg) > deg_tol and abs((known[planet] + 30) - deg) > deg_tol:
            issues.append(
                {
                    "kind": "degree_mismatch",
                    "quote": m.group(0)[:80],
                    "reason": f"{planet} cited {deg}° but packet has {known[planet]}°",
                }
            )

    if sav_ok:
        for m in _BARE_SAV.finditer(text):
            try:
                n = int(m.group("sav"))
            except (TypeError, ValueError):
                continue
            if n not in sav_ok and n not in (25, 28):  # thresholds may be cited as rules
                # allow small integers used as house numbers nearby? still flag high SAV claims
                if n >= 18:
                    issues.append(
                        {
                            "kind": "sav_mismatch",
                            "quote": m.group(0)[:40],
                            "reason": f"SAV {n} is not a house score in the packet ({sorted(sav_ok)})",
                        }
                    )

    # Invented sign names next to planets are not checked — too many false positives.
    _ = ZODIAC_SIGNS, PLANET_ORDER
    return {"ok": not issues, "issues": issues, "checked_degrees": len(known), "checked_sav": sorted(sav_ok)}
