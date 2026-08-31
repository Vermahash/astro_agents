"""
Allowlisted chart queries on a precomputed packet (Python calc tool).

Purpose:
    Let the LLM / MCP ask for SAV, planet, cusp, house lord, varga, nadi
    occupancy, and dasha balance without inventing numbers or running swe.

Inputs:
    chart_key or a slices dict; operation name + args.

Outputs:
    JSON result for the named op, or error.
"""

from __future__ import annotations

from typing import Any

from shared.specialists import compact_facts
from shared.vedic_facts import ZODIAC_SIGNS, get_varga_sign, house_lord, sav_status

OPS = (
    "sav",
    "planet",
    "cusp",
    "house",
    "lord",
    "varga",
    "yogas",
    "nadi",
    "dasha",
    "compact",
)


def _slices_for_chart(chart_key: str, fields: list[str] | None = None) -> dict[str, Any]:
    from shared.chart_store import get_fields, list_fields

    if fields:
        return get_fields(chart_key, fields)
    names = [f["field"] for f in list_fields(chart_key)]
    return get_fields(chart_key, names)


def run_chart_query(
    *,
    op: str,
    chart_key: str | None = None,
    slices: dict[str, Any] | None = None,
    house: int | None = None,
    planet: str | None = None,
    division: int | None = None,
    houses: list[int] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute one allowlisted lookup/calculation on engine data.

    Returns:
        {ok, op, result} or {ok: False, error}
    """
    name = (op or "").strip().lower()
    if name not in OPS:
        return {"ok": False, "error": f"unknown op {op!r}; allowed: {', '.join(OPS)}"}

    data = slices
    if data is None:
        if not chart_key:
            return {"ok": False, "error": "chart_key or slices required"}
        data = _slices_for_chart(chart_key)

    facts = compact_facts(data, plan or {"planets": [], "houses": list(range(1, 13)), "kp_cusps": list(range(1, 13))})

    if name == "compact":
        slim = {k: facts[k] for k in ("lagna", "planets", "houses", "sav", "exchanges", "dasha", "vargas") if k in facts}
        return {"ok": True, "op": name, "result": slim}

    if name == "sav":
        if house is None:
            return {"ok": True, "op": name, "result": facts.get("sav")}
        score = (facts.get("sav") or {}).get(str(house))
        return {
            "ok": True,
            "op": name,
            "result": {"house": house, "sav": score, "status": sav_status(score if score is not None else None)},
        }

    if name == "planet":
        if not planet:
            return {"ok": False, "error": "planet required"}
        row = (facts.get("planets") or {}).get(planet) or (facts.get("planets") or {}).get(planet.title())
        star = (facts.get("planet_star_sub_lords") or {}).get(planet) or (facts.get("planet_star_sub_lords") or {}).get(
            planet.title()
        )
        return {"ok": True, "op": name, "result": {"planet": planet, "d1": row, "star_sub": star}}

    if name == "cusp":
        if house is None:
            return {"ok": True, "op": name, "result": facts.get("cusps")}
        return {"ok": True, "op": name, "result": (facts.get("cusps") or {}).get(str(house))}

    if name == "house":
        if house is None:
            return {"ok": False, "error": "house required"}
        return {"ok": True, "op": name, "result": (facts.get("all_houses") or facts.get("houses") or {}).get(str(house))}

    if name == "lord":
        if house is None:
            return {"ok": False, "error": "house required"}
        asc = (facts.get("lagna") or {}).get("sign_index")
        if asc is None:
            return {"ok": False, "error": "lagna missing"}
        lord = house_lord(int(asc), int(house))
        prow = (facts.get("planets") or {}).get(lord)
        return {"ok": True, "op": name, "result": {"house": house, "lord": lord, "placement": prow}}

    if name == "varga":
        if not planet:
            return {"ok": False, "error": "planet required"}
        prow = (facts.get("planets") or {}).get(planet) or (facts.get("planets") or {}).get(planet.title())
        if not prow:
            return {"ok": False, "error": f"planet {planet} not in packet"}
        div = int(division or 9)
        idx = get_varga_sign(float(prow["longitude"]), div)
        return {
            "ok": True,
            "op": name,
            "result": {"planet": planet, "division": div, "sign_index": idx, "sign": ZODIAC_SIGNS[idx], "lon": prow["longitude"]},
        }

    if name == "yogas":
        return {"ok": True, "op": name, "result": facts.get("yogas")}

    if name == "nadi":
        hs = houses or []
        occ = {}
        src = facts.get("all_houses") or facts.get("houses") or {}
        for h in hs:
            row = src.get(str(h)) or {}
            occ[str(h)] = [o.get("planet") for o in row.get("occupants") or [] if o.get("planet")]
        return {"ok": True, "op": name, "result": occ}

    if name == "dasha":
        return {"ok": True, "op": name, "result": facts.get("dasha")}

    return {"ok": False, "error": f"unhandled op {name}"}
