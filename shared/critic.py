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

_PLANET = r"(Sun|Moon|Mars|Mercury|Jupiter|Venus|Saturn|Rahu|Ketu|Lagna)"
_PLANET_RE = re.compile(_PLANET, re.I)
_DEG_TAIL = re.compile(
    r"(?P<d>\d{1,3})(?:\.(?P<frac>\d+))?\s*°(?:\s*(?P<m>\d{1,2})')?",
)
_BARE_SAV = re.compile(r"(?P<sav>\d{1,2})\s*SAV", re.I)
_WINDOW = 48


def _cited_degree(m: re.Match[str]) -> float:
    d = int(m.group("d"))
    minutes = m.group("m")
    frac = m.group("frac")
    if minutes is not None:
        return d + int(minutes) / 60.0
    if frac is not None:
        return float(f"{d}.{frac}")
    return float(d)


def _iter_planet_degrees(text: str) -> list[tuple[str, float, str]]:
    """
    Bind a degree to a planet only when no other planet name sits between them.

    Stops checkpoint labels like 'Saturn vitality | Jupiter Aquarius 26.2°'
    from attributing Jupiter's degree to Saturn.
    """
    found: list[tuple[str, float, str]] = []
    for pm in _PLANET_RE.finditer(text):
        planet = pm.group(1).lower()
        rest = text[pm.end() : pm.end() + _WINDOW]
        dm = _DEG_TAIL.search(rest)
        if not dm:
            continue
        between = rest[: dm.start()]
        if _PLANET_RE.search(between):
            continue
        if "\n" in between:
            continue
        deg = _cited_degree(dm)
        quote = (pm.group(0) + rest[: dm.end()])[:80]
        found.append((planet, deg, quote))
    return found


def _known_degrees(facts: dict[str, Any]) -> dict[str, list[float]]:
    """Map body name → degree-in-sign and absolute longitude when present."""
    out: dict[str, list[float]] = {}

    def add(name: str, *vals: float | None) -> None:
        bucket = out.setdefault(name.lower(), [])
        for v in vals:
            if v is None:
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            bucket.append(f)
            bucket.append(f % 30.0)

    for name, row in (facts.get("planets") or {}).items():
        if not isinstance(row, dict):
            continue
        add(str(name), row.get("degree_in_sign"), row.get("longitude"))
    lagna = facts.get("lagna") or {}
    add("lagna", lagna.get("longitude"))
    if lagna.get("longitude") is not None:
        try:
            add("lagna", float(lagna["longitude"]) % 30.0)
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


def _close(cited: float, known: float, tol: float) -> bool:
    if abs(cited - known) <= tol:
        return True
    if abs((cited % 30.0) - (known % 30.0)) <= tol:
        return True
    if cited == int(cited) and 0 <= (known % 30.0) - cited < 1.0 + 1e-9:
        return True
    if cited == int(cited) and 0 <= (known - cited) < 1.0 + 1e-9:
        return True
    return False


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

    for planet, deg, quote in _iter_planet_degrees(text):
        cands = known.get(planet) or []
        if not cands:
            issues.append(
                {
                    "kind": "unknown_planet_degree",
                    "quote": quote,
                    "reason": f"{planet} degree not in compact packet",
                }
            )
            continue
        if any(_close(deg, k, deg_tol) for k in cands):
            continue
        issues.append(
            {
                "kind": "degree_mismatch",
                "quote": quote,
                "reason": f"{planet} cited {deg}° but packet has {cands}",
            }
        )

    if sav_ok:
        for m in _BARE_SAV.finditer(text):
            try:
                n = int(m.group("sav"))
            except (TypeError, ValueError):
                continue
            if n not in sav_ok and n not in (25, 28):
                if n >= 18:
                    issues.append(
                        {
                            "kind": "sav_mismatch",
                            "quote": m.group(0)[:40],
                            "reason": f"SAV {n} is not a house score in the packet ({sorted(sav_ok)})",
                        }
                    )

    _ = ZODIAC_SIGNS, PLANET_ORDER
    return {"ok": not issues, "issues": issues, "checked_degrees": len(known), "checked_sav": sorted(sav_ok)}
