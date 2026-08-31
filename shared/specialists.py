"""
Python specialist extractors — BPHS, Varga/SAV, Dasha/Nadi, KP, BNN.

Purpose:
    Turn harness slices into PRE-AUDIT checkpoint rows. No LLM. Status is
    SUPPORTS | RESISTS | MIXED | NOT ACTIVATED | NOT IN PACKET.

Inputs:
    Compact facts dict + harness plan (checkpoints, nadi, kp cusps).

Outputs:
    {specialist: {checkpoints: [...], notes: [...]}}
"""

from __future__ import annotations

import re
from typing import Any

from shared.vedic_facts import (
    DIRECTIONAL_MAP,
    PLANET_ORDER,
    SAV_STRONG,
    SAV_WEAK,
    ZODIAC_SIGNS,
    deg_in_sign,
    dignity,
    get_varga_sign,
    house_from_lagna,
    house_lord,
    house_sign_index,
    sav_status,
    sign_index,
    sign_name,
)

STATUS = ("SUPPORTS", "RESISTS", "MIXED", "NOT ACTIVATED", "NOT IN PACKET")


def _cp(cid: str, label: str, status: str, cite: str, details: Any = None) -> dict[str, Any]:
    return {
        "id": cid,
        "label": label,
        "status": status if status in STATUS else "MIXED",
        "cite": cite,
        "details": details if details is not None else {},
    }


def _sav(facts: dict[str, Any], house: int) -> int | None:
    sav = facts.get("sav") or {}
    raw = sav.get(str(house))
    if raw is None:
        raw = sav.get(house)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _house_row(facts: dict[str, Any], house: int) -> dict[str, Any]:
    return (facts.get("houses") or {}).get(str(house)) or (facts.get("all_houses") or {}).get(str(house)) or {}


def _planet_row(facts: dict[str, Any], name: str) -> dict[str, Any]:
    lower = {str(k).lower(): v for k, v in (facts.get("planets") or {}).items()}
    return lower.get(name.lower()) or {}


def _yoga_hits(facts: dict[str, Any], needles: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for y in facts.get("yogas") or []:
        blob = " ".join(str(y.get(k, "")) for k in ("yoga_name", "category", "rule_summary", "final_status"))
        if any(n.lower() in blob.lower() for n in needles):
            out.append(f"{y.get('yoga_name')} [{y.get('final_status')}]")
    return out


def compact_facts(slices: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """
    Build a small fact packet from engine slices (planets/houses in the plan only).

    Returns:
        lagna, planets, houses, sav, yogas, cusps, bnn, dasha, vargas
    """
    natal = slices.get("natal_core") if isinstance(slices.get("natal_core"), dict) else {}
    longs = natal.get("longitudes") if isinstance(natal.get("longitudes"), dict) else {}
    houses_from = natal.get("house_from_lagna") if isinstance(natal.get("house_from_lagna"), dict) else {}
    bhava = natal.get("bhava_house") if isinstance(natal.get("bhava_house"), dict) else {}
    avasthas = natal.get("baladi_avastha") if isinstance(natal.get("baladi_avastha"), dict) else {}
    sign_idx_map = natal.get("sign_index") if isinstance(natal.get("sign_index"), dict) else {}

    asc_lon = natal.get("ascendant_lon")
    if asc_lon is None:
        uk = slices.get("unified_kundali") or {}
        h1 = (uk.get("houses") or {}).get("H1") or []
        for row in h1:
            if isinstance(row, dict) and str(row.get("planet") or "").lower() == "lagna":
                asc_lon = row.get("longitude")
                break
    try:
        asc_lon_f = float(asc_lon) if asc_lon is not None else None
    except (TypeError, ValueError):
        asc_lon_f = None
    asc_sign = sign_index(asc_lon_f) if asc_lon_f is not None else None

    wanted_planets = list(PLANET_ORDER)
    wanted_houses = [int(h) for h in (plan.get("houses") or list(range(1, 13)))]

    planets: dict[str, Any] = {}
    for name in PLANET_ORDER:
        lon = longs.get(name)
        if lon is None:
            continue
        try:
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        sidx = sign_idx_map.get(name)
        if sidx is None:
            sidx = sign_index(lon_f)
        else:
            sidx = int(sidx) % 12
        rashi_h = houses_from.get(name)
        if rashi_h is None and asc_sign is not None:
            rashi_h = house_from_lagna(sidx, asc_sign)
        bhav_h = bhava.get(name, rashi_h)
        direction, element = DIRECTIONAL_MAP.get(sidx, ("UNKNOWN", ""))
        planets[name] = {
            "longitude": round(lon_f, 4),
            "degree_in_sign": round(deg_in_sign(lon_f), 4),
            "sign_index": sidx,
            "sign": ZODIAC_SIGNS[sidx],
            "house": int(rashi_h) if rashi_h is not None else None,
            "bhava_house": int(bhav_h) if bhav_h is not None else None,
            "bhava_shift": bool(bhav_h is not None and rashi_h is not None and int(bhav_h) != int(rashi_h)),
            "dignity": dignity(name, sidx),
            "avastha": avasthas.get(name),
            "direction": direction,
            "element": element,
        }

    # Fill houses from unified kundali when present
    uk = slices.get("unified_kundali") if isinstance(slices.get("unified_kundali"), dict) else {}
    uk_houses = uk.get("houses") if isinstance(uk.get("houses"), dict) else {}
    sav_raw = slices.get("ashtakavarga_sav") if isinstance(slices.get("ashtakavarga_sav"), dict) else {}
    sav = {str(k): v for k, v in sav_raw.items()}

    houses: dict[str, Any] = {}
    if asc_sign is not None:
        for h in range(1, 13):
            sidx = house_sign_index(asc_sign, h)
            occupants: list[dict[str, Any]] = []
            uk_row = uk_houses.get(f"H{h}") or uk_houses.get(str(h)) or []
            seen_occ: set[str] = set()
            if isinstance(uk_row, list):
                for row in uk_row:
                    if not isinstance(row, dict):
                        continue
                    pname = row.get("planet")
                    if not pname:
                        continue
                    occ_key = str(pname).lower()
                    if occ_key in seen_occ:
                        continue
                    seen_occ.add(occ_key)
                    occupants.append(
                        {
                            "planet": pname,
                            "degree": row.get("degree"),
                            "degree_dms": row.get("degree_dms"),
                            "sign": row.get("sign"),
                            "direction": row.get("direction"),
                            "bhava_house": row.get("bhava_house"),
                            "bhava_shift": row.get("bhava_shift"),
                        }
                    )
            if not occupants:
                for pname, prow in planets.items():
                    if prow.get("house") == h:
                        occupants.append(
                            {
                                "planet": pname,
                                "degree": prow.get("degree_in_sign"),
                                "sign": prow.get("sign"),
                                "direction": prow.get("direction"),
                                "bhava_house": prow.get("bhava_house"),
                                "bhava_shift": prow.get("bhava_shift"),
                            }
                        )
            houses[str(h)] = {
                "house": h,
                "sign": ZODIAC_SIGNS[sidx],
                "sign_index": sidx,
                "lord": house_lord(asc_sign, h),
                "sav": sav.get(str(h)),
                "occupants": occupants,
                "direction": DIRECTIONAL_MAP.get(sidx, ("UNKNOWN", ""))[0],
                "element": DIRECTIONAL_MAP.get(sidx, ("UNKNOWN", ""))[1],
            }

    yogas: list[dict[str, Any]] = []
    raw_y = slices.get("special_yogas")
    if isinstance(raw_y, list):
        for y in raw_y:
            if isinstance(y, dict):
                yogas.append(
                    {
                        "yoga_name": y.get("yoga_name"),
                        "category": y.get("category"),
                        "final_status": y.get("final_status"),
                        "rule_summary": y.get("rule_summary"),
                        "involved_planets": y.get("involved_planets_d1") or y.get("involved_planets") or [],
                        "involved_houses": y.get("involved_houses_d1") or y.get("involved_houses") or [],
                    }
                )

    cusps_out: dict[str, Any] = {}
    raw_c = slices.get("cusps")
    if isinstance(raw_c, dict):
        for h in plan.get("kp_cusps") or []:
            entry = raw_c.get(str(h)) or raw_c.get(h)
            if entry is not None:
                cusps_out[str(h)] = entry

    star_sub = slices.get("planet_star_sub_lords") if isinstance(slices.get("planet_star_sub_lords"), dict) else {}

    matrix = slices.get("kp_astrology_matrix") if isinstance(slices.get("kp_astrology_matrix"), dict) else {}
    dasha = matrix.get("moon_dasha_balance_at_birth") if isinstance(matrix, dict) else None

    bnn = slices.get("bnn_module") if isinstance(slices.get("bnn_module"), dict) else {}

    vargas: dict[str, Any] = {}
    for pname in wanted_planets:
        prow = planets.get(pname)
        if not prow:
            continue
        lon_f = float(prow["longitude"])
        vargas[pname] = {
            "D2": ZODIAC_SIGNS[get_varga_sign(lon_f, 2)],
            "D4": ZODIAC_SIGNS[get_varga_sign(lon_f, 4)],
            "D7": ZODIAC_SIGNS[get_varga_sign(lon_f, 7)],
            "D9": ZODIAC_SIGNS[get_varga_sign(lon_f, 9)],
            "D10": ZODIAC_SIGNS[get_varga_sign(lon_f, 10)],
            "D12": ZODIAC_SIGNS[get_varga_sign(lon_f, 12)],
            "D30": ZODIAC_SIGNS[get_varga_sign(lon_f, 30)],
        }

    # Parivartana: 1st/10th lord in 2nd and 2nd/9th in 1st (finance) etc.
    exchanges: list[str] = []
    if asc_sign is not None:
        for a, b in ((1, 2), (1, 10), (2, 9), (5, 9), (4, 10), (6, 8), (6, 12), (8, 12)):
            la, lb = house_lord(asc_sign, a), house_lord(asc_sign, b)
            pa, pb = planets.get(la) or {}, planets.get(lb) or {}
            if pa.get("house") == b and pb.get("house") == a:
                exchanges.append(f"{la} (H{a} lord in H{b}) ↔ {lb} (H{b} lord in H{a})")

    return {
        "lagna": {
            "longitude": round(asc_lon_f, 4) if asc_lon_f is not None else None,
            "sign": ZODIAC_SIGNS[asc_sign] if asc_sign is not None else None,
            "sign_index": asc_sign,
        },
        "planets": planets,
        "houses": {str(h): houses[str(h)] for h in wanted_houses if str(h) in houses},
        "all_houses": houses,
        "sav": sav,
        "yogas": yogas,
        "exchanges": exchanges,
        "cusps": cusps_out,
        "planet_star_sub_lords": {k: star_sub[k] for k in star_sub if k in wanted_planets or k in PLANET_ORDER},
        "bnn": {
            "directional_groups": bnn.get("directional_groups"),
            "groups": bnn.get("groups"),
            "special_yogas": bnn.get("special_yogas"),
            "transit_cycles": bnn.get("transit_cycles"),
        }
        if bnn
        else {},
        "dasha": dasha,
        "vargas": vargas,
        "kp_prediction": slices.get("kp_prediction"),
    }


def _bphs_house_checkpoint(facts: dict[str, Any], house: int, label: str, cid: str) -> dict[str, Any]:
    row = _house_row(facts, house)
    if not row:
        return _cp(cid, label, "NOT IN PACKET", f"H{house} missing from compact facts")
    occ = [o.get("planet") for o in row.get("occupants") or [] if o.get("planet")]
    lord = row.get("lord")
    lord_row = _planet_row(facts, str(lord)) if lord else {}
    cite = (
        f"H{house} {row.get('sign')} lord {lord} in H{lord_row.get('house')} "
        f"({lord_row.get('sign')} {lord_row.get('degree_in_sign')}°) "
        f"dignity={lord_row.get('dignity')}; occupants={occ or 'empty'}"
    )
    if lord_row.get("dignity") == "exalted" or (occ and any(str(p) in ("Jupiter", "Venus", "Mercury", "Moon") for p in occ)):
        status = "SUPPORTS"
    elif lord_row.get("dignity") == "debilitated" or any(str(p) in ("Rahu", "Ketu", "Mars", "Saturn") for p in occ):
        status = "MIXED" if occ else "RESISTS"
    else:
        status = "SUPPORTS" if lord_row else "MIXED"
    if lord_row.get("dignity") == "exalted":
        status = "SUPPORTS"
    return _cp(cid, label, status, cite, {"house": row, "lord": lord_row})


def specialist_bphs(facts: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """BPHS / Parashari house-lord, bhava-shift, and yoga checkpoints."""
    rows: list[dict[str, Any]] = []
    for cp in plan.get("checkpoints") or []:
        if cp.get("system") != "bphs":
            continue
        cid = cp.get("id") or ""
        label = cp.get("label") or cid
        house_m = re.match(r"d1_h(\d{1,2})$", cid)
        if house_m:
            rows.append(_bphs_house_checkpoint(facts, int(house_m.group(1)), label, cid))
        elif cid == "d1_1_10_links":
            l1 = facts.get("lagna") or {}
            if l1.get("sign_index") is None:
                rows.append(_cp(cid, label, "NOT IN PACKET", "lagna missing"))
            else:
                merc = _planet_row(facts, house_lord(int(l1["sign_index"]), 1))
                ten_lord = house_lord(int(l1["sign_index"]), 10)
                ten = _planet_row(facts, ten_lord)
                ex = facts.get("exchanges") or []
                status = "SUPPORTS" if ex else ("MIXED" if merc.get("house") in (2, 10, 11) else "RESISTS")
                rows.append(
                    _cp(
                        cid,
                        label,
                        status,
                        f"1st/10th lord {ten_lord} in H{ten.get('house')}; exchanges={ex or 'none'}",
                        {"exchanges": ex, "lord": ten},
                    )
                )
        elif cid.startswith("yogas_"):
            raw = cp.get("needles")
            if isinstance(raw, (list, tuple)) and raw:
                needles = tuple(str(x) for x in raw)
            elif cid == "yogas_dhana":
                needles = ("parivartana", "dhana", "raja", "harsha", "sarala", "vipareeta", "lakshmi")
            else:
                needles = ("parivartana", "raja", "dhana", "vipareeta")
            hits = _yoga_hits(facts, needles)
            ex = facts.get("exchanges") or []
            if hits or ex:
                rows.append(_cp(cid, label, "SUPPORTS", f"yogas={hits or 'none'}; exchanges={ex}", {"hits": hits, "exchanges": ex}))
            elif facts.get("yogas") is None:
                rows.append(_cp(cid, label, "NOT IN PACKET", "special_yogas missing"))
            else:
                rows.append(_cp(cid, label, "NOT ACTIVATED", "no matching yogas in packet", {"yogas": facts.get("yogas")[:8]}))
        elif cid == "bhava_shift":
            shifts = [f"{n} H{p.get('house')}→H{p.get('bhava_house')}" for n, p in (facts.get("planets") or {}).items() if p.get("bhava_shift")]
            rows.append(
                _cp(
                    cid,
                    label,
                    "MIXED" if shifts else "SUPPORTS",
                    f"bhava shifts: {shifts or 'none (delivery matches whole-sign)'}",
                    {"shifts": shifts},
                )
            )
        else:
            rows.append(_cp(cid, label, "NOT ACTIVATED", "no extractor for this checkpoint id"))
    return {"specialist": "bphs", "checkpoints": rows}


def specialist_varga_sav(facts: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """D2/D9/D10/D30 from longitudes + SAV house scores."""
    rows: list[dict[str, Any]] = []
    vargas = facts.get("vargas") or {}
    for cp in plan.get("checkpoints") or []:
        if cp.get("system") != "varga_sav":
            continue
        cid = cp.get("id") or ""
        label = cp.get("label") or cid
        if cid.startswith("sav_h"):
            try:
                h = int(cid.replace("sav_h", ""))
            except ValueError:
                rows.append(_cp(cid, label, "NOT ACTIVATED", cid))
                continue
            score = _sav(facts, h)
            st = sav_status(score)
            rows.append(_cp(cid, label, st, f"H{h} SAV={score} (strong>{SAV_STRONG}, weak<{SAV_WEAK})", {"house": h, "sav": score}))
        elif cid == "d2_hora":
            if not vargas:
                rows.append(_cp(cid, label, "NOT IN PACKET", "no longitudes for D2"))
            else:
                sun_h = [p for p, v in vargas.items() if v.get("D2") == "Leo"]
                moon_h = [p for p, v in vargas.items() if v.get("D2") == "Cancer"]
                status = "SUPPORTS" if len(sun_h) >= 4 else "MIXED"
                rows.append(_cp(cid, label, status, f"Sun Hora (Leo): {sun_h}; Moon Hora (Cancer): {moon_h}", {"sun_hora": sun_h, "moon_hora": moon_h}))
        elif cid in ("d9_fortitude", "d9_dharma"):
            if not vargas:
                rows.append(_cp(cid, label, "NOT IN PACKET", "no D9"))
            else:
                rows.append(_cp(cid, label, "SUPPORTS", f"D9 signs: { {p: v.get('D9') for p, v in vargas.items()} }", {"d9": {p: v.get("D9") for p, v in vargas.items()}}))
        elif cid in ("d10_earnings", "d10_dasamsha"):
            if not vargas:
                rows.append(_cp(cid, label, "NOT IN PACKET", "no D10"))
            else:
                # cluster: planets sharing a D10 sign
                by_sign: dict[str, list[str]] = {}
                for p, v in vargas.items():
                    by_sign.setdefault(str(v.get("D10")), []).append(p)
                cluster = max(by_sign.values(), key=len) if by_sign else []
                status = "SUPPORTS" if len(cluster) >= 3 else "MIXED"
                rows.append(_cp(cid, label, status, f"D10 cluster {cluster} in shared sign; map={by_sign}", {"d10": by_sign}))
        elif cid == "d30_trimsamsa":
            if not vargas:
                rows.append(_cp(cid, label, "NOT IN PACKET", "no D30"))
            else:
                malefic_d30 = [p for p, v in vargas.items() if v.get("D30") in ("Aries", "Scorpio", "Capricorn", "Aquarius") and p in ("Mars", "Saturn", "Rahu", "Sun")]
                status = "RESISTS" if malefic_d30 else "MIXED"
                rows.append(_cp(cid, label, status, f"D30: { {p: v.get('D30') for p, v in vargas.items()} }; harsh={malefic_d30}", {"d30": {p: v.get("D30") for p, v in vargas.items()}}))
        elif cid.startswith("d4_") or cid.startswith("d7_") or cid.startswith("d12_"):
            key = "D4" if cid.startswith("d4_") else ("D7" if cid.startswith("d7_") else "D12")
            if not vargas:
                rows.append(_cp(cid, label, "NOT IN PACKET", f"no {key}"))
            else:
                mapping = {p: v.get(key) for p, v in vargas.items()}
                rows.append(_cp(cid, label, "SUPPORTS", f"{key} signs: {mapping}", {key.lower(): mapping}))
        else:
            rows.append(_cp(cid, label, "NOT ACTIVATED", "no extractor"))
    return {"specialist": "varga_sav", "checkpoints": rows}


def _nadi_occupants(facts: dict[str, Any], houses: list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for h in houses:
        row = _house_row(facts, h)
        names = [str(o.get("planet")) for o in row.get("occupants") or [] if o.get("planet")]
        out[h] = names
    return out


def specialist_dasha_nadi(facts: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Nadi house-combination occupancy + dasha balance from packet."""
    rows: list[dict[str, Any]] = []
    nadi = plan.get("nadi_combos") or {}
    dasha = facts.get("dasha")
    for cp in plan.get("checkpoints") or []:
        if cp.get("system") != "dasha_nadi":
            continue
        cid = cp.get("id") or ""
        label = cp.get("label") or cid
        if cid == "vimshottari":
            if not dasha:
                rows.append(_cp(cid, label, "NOT IN PACKET", "moon_dasha_balance_at_birth missing"))
            else:
                rows.append(_cp(cid, label, "SUPPORTS", f"dasha balance at birth: {dasha}", {"dasha": dasha}))
        elif cid.startswith("nadi_"):
            key = cid.replace("nadi_", "")
            combo = cp.get("houses") or nadi.get(key)
            if not combo:
                combo = nadi.get(cid) or []
            if not combo:
                rows.append(_cp(cid, label, "NOT ACTIVATED", f"no nadi combo for {key}"))
                continue
            occ = _nadi_occupants(facts, combo)
            lords_ok = []
            lagna = facts.get("lagna") or {}
            if lagna.get("sign_index") is not None:
                for h in combo:
                    lord = house_lord(int(lagna["sign_index"]), h)
                    prow = _planet_row(facts, lord)
                    lords_ok.append({"house": h, "lord": lord, "lord_house": prow.get("house"), "dignity": prow.get("dignity")})
            filled = sum(1 for v in occ.values() if v)
            deny = key in ("loss", "crisis", "denial", "obstruction")
            if deny:
                status = "RESISTS" if filled else "SUPPORTS"
            else:
                status = "SUPPORTS" if filled or any(x.get("dignity") == "exalted" for x in lords_ok) else "MIXED"
            rows.append(_cp(cid, label, status, f"houses {combo} occupants={occ}; lords={lords_ok}", {"occupants": occ, "lords": lords_ok}))
        else:
            rows.append(_cp(cid, label, "NOT ACTIVATED", cid))
    return {"specialist": "dasha_nadi", "checkpoints": rows}


def _csl_chain(cusp: Any) -> str:
    if not isinstance(cusp, dict):
        return str(cusp)
    parts = []
    for k in ("sub_lord", "star_lord", "sign_lord", "sub_sub_lord", "nakshatra"):
        if cusp.get(k) is not None:
            parts.append(f"{k}={cusp.get(k)}")
    if cusp.get("lon") is not None:
        parts.append(f"lon={cusp.get('lon')}")
    return "; ".join(parts) or str(cusp)


def specialist_kp(facts: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """KP CSL for domain cusps from packet only."""
    rows: list[dict[str, Any]] = []
    cusps = facts.get("cusps") or {}
    star_sub = facts.get("planet_star_sub_lords") or {}
    for cp in plan.get("checkpoints") or []:
        if cp.get("system") != "kp":
            continue
        cid = cp.get("id") or ""
        label = cp.get("label") or cid
        house = None
        if cid.startswith("kp_csl_"):
            try:
                house = int(cid.replace("kp_csl_", ""))
            except ValueError:
                house = None
        if house is None:
            rows.append(_cp(cid, label, "NOT ACTIVATED", cid))
            continue
        cusp = cusps.get(str(house))
        if not cusp:
            rows.append(_cp(cid, label, "NOT IN PACKET", f"cusp {house} not in harness slice"))
            continue
        sub = cusp.get("sub_lord") if isinstance(cusp, dict) else None
        sub_row = star_sub.get(sub) if isinstance(sub, str) else None
        fruit = []
        if isinstance(sub_row, dict):
            for k in ("star_lord", "sub_lord", "sign_lord", "house", "houses"):
                if sub_row.get(k) is not None:
                    fruit.append(f"{k}={sub_row.get(k)}")
        status = "SUPPORTS" if sub else "MIXED"
        rows.append(
            _cp(
                cid,
                label,
                status,
                f"H{house} CSL {_csl_chain(cusp)}" + (f" | sub-planet {fruit}" if fruit else ""),
                {"cusp": cusp, "sub_planet": sub_row},
            )
        )
    return {"specialist": "kp", "checkpoints": rows}


def specialist_bnn(facts: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """BNN directional groups and karaka placements from packet."""
    rows: list[dict[str, Any]] = []
    bnn = facts.get("bnn") or {}
    groups = bnn.get("directional_groups") or {}
    for cp in plan.get("checkpoints") or []:
        if cp.get("system") != "bnn":
            continue
        cid = cp.get("id") or ""
        label = cp.get("label") or cid
        if cid == "bnn_direction":
            if not groups:
                # derive from planets
                derived: dict[str, list[str]] = {"EAST": [], "SOUTH": [], "WEST": [], "NORTH": []}
                for n, p in (facts.get("planets") or {}).items():
                    d = p.get("direction") or "UNKNOWN"
                    if d in derived:
                        derived[d].append(f"{n} ({p.get('sign')} {p.get('degree_in_sign')}°)")
                rows.append(_cp(cid, label, "SUPPORTS", f"directional groups (from D1): {derived}", {"groups": derived}))
            else:
                rows.append(_cp(cid, label, "SUPPORTS", f"BNN directional_groups={groups}", {"groups": groups}))
        elif cid == "bnn_karakas":
            karakas = {
                "Jupiter": _planet_row(facts, "Jupiter"),
                "Venus": _planet_row(facts, "Venus"),
                "Mercury": _planet_row(facts, "Mercury"),
                "Sun": _planet_row(facts, "Sun"),
                "Moon": _planet_row(facts, "Moon"),
                "Mars": _planet_row(facts, "Mars"),
                "Saturn": _planet_row(facts, "Saturn"),
            }
            present = {k: v for k, v in karakas.items() if v}
            if not present:
                rows.append(_cp(cid, label, "NOT IN PACKET", "planet rows missing"))
            else:
                j, m = present.get("Jupiter") or {}, present.get("Mercury") or {}
                trine = j.get("direction") and j.get("direction") == m.get("direction")
                status = "SUPPORTS" if trine or present else "MIXED"
                cite = "; ".join(
                    f"{k} {v.get('sign')} {v.get('degree_in_sign')}° H{v.get('house')} {v.get('direction')}"
                    for k, v in present.items()
                    if v
                )
                rows.append(_cp(cid, label, status, cite, {"karakas": present, "mercury_jupiter_same_direction": bool(trine)}))
        else:
            rows.append(_cp(cid, label, "NOT ACTIVATED", cid))
    return {"specialist": "bnn", "checkpoints": rows}


_DISPATCH = {
    "bphs": specialist_bphs,
    "varga_sav": specialist_varga_sav,
    "dasha_nadi": specialist_dasha_nadi,
    "kp": specialist_kp,
    "bnn": specialist_bnn,
}


def run_specialists(facts: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Run each specialist named in the plan. Returns list of specialist reports."""
    names = plan.get("specialists") or list(_DISPATCH)
    out: list[dict[str, Any]] = []
    for name in names:
        fn = _DISPATCH.get(str(name))
        if fn is None:
            continue
        out.append(fn(facts, plan))
    return out


def flatten_checkpoints(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge specialist checkpoint rows for Brain + critic."""
    rows: list[dict[str, Any]] = []
    for rep in reports:
        spec = rep.get("specialist")
        for cp in rep.get("checkpoints") or []:
            item = dict(cp)
            item["specialist"] = spec
            rows.append(item)
    return rows


def tally_status(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in STATUS}
    for r in rows:
        st = r.get("status")
        if st in counts:
            counts[st] += 1
    return counts
