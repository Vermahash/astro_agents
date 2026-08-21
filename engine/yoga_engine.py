"""
yoga_engine.py — Special Yogas MVP (Patch C)

Detection order:
  1. Check D1 (Rashi) for each yoga rule.
  2. Check D9 (Navamsa) for the same rule.
  3. Assign final_status = "confirmed" | "partial_d1_only".
  4. D9-only results are tagged "navamsa_support_only_debug" (debug mode only).
  5. Absent yogas are not emitted to structured_payload unless debug mode.

All constants imported from astro_kp to avoid duplication.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Re-use constants already defined in astro_kp to stay DRY.
# ---------------------------------------------------------------------------
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

EXALTATION_SIGNS: dict[str, int] = {
    "Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5,
    "Jupiter": 3, "Venus": 11, "Saturn": 6,
}

# Own signs (list of 0-based indices) per planet
OWN_SIGNS: dict[str, list[int]] = {
    "Sun":     [4],
    "Moon":    [3],
    "Mars":    [0, 7],
    "Mercury": [2, 5],
    "Jupiter": [8, 11],
    "Venus":   [1, 6],
    "Saturn":  [9, 10],
}

KENDRAS = {1, 4, 7, 10}       # Kendra house numbers
TRIKONAS = {1, 5, 9}           # Trikona house numbers
KENDRA_TRIKONA = KENDRAS | TRIKONAS

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _sign(lon: float) -> int:
    """0-based sign index from longitude."""
    return int(lon / 30) % 12


def _house_from(planet_sign: int, ref_sign: int) -> int:
    """Whole-sign house number of planet_sign counted from ref_sign (1-based)."""
    return (planet_sign - ref_sign) % 12 + 1


def _in_own_sign(planet: str, lon: float) -> bool:
    s = _sign(lon)
    return s in OWN_SIGNS.get(planet, [])


def _in_exaltation(planet: str, lon: float) -> bool:
    s = _sign(lon)
    return EXALTATION_SIGNS.get(planet) == s


def _in_own_or_exaltation(planet: str, lon: float) -> bool:
    return _in_own_sign(planet, lon) or _in_exaltation(planet, lon)


def _in_kendra_from_lagna(planet_lon: float, asc_sign: int) -> bool:
    h = _house_from(_sign(planet_lon), asc_sign)
    return h in KENDRAS


def _in_kendra_from_moon(planet_lon: float, moon_sign: int) -> bool:
    h = _house_from(_sign(planet_lon), moon_sign)
    return h in KENDRAS


def _planets_in_house_from(ref_sign: int, house_num: int,
                             planet_positions: dict[str, float],
                             exclude: set[str] | None = None) -> list[str]:
    """Return names of planets in `house_num` counted whole-sign from ref_sign."""
    exclude = exclude or set()
    result = []
    for p, lon in planet_positions.items():
        if p in exclude:
            continue
        if _house_from(_sign(lon), ref_sign) == house_num:
            result.append(p)
    return result


def _sign_lord(sign_idx: int) -> str:
    return SIGN_LORDS[sign_idx % 12]


def _house_lord(house_num: int, asc_sign: int) -> str:
    """Lord of house_num counted from asc_sign (whole-sign)."""
    sign_of_house = (asc_sign + house_num - 1) % 12
    return _sign_lord(sign_of_house)


def _planets_conjunct_or_mutual_aspect(p1: str, p2: str,
                                        planet_positions: dict[str, float],
                                        asc_sign: int) -> bool:
    """True if p1 and p2 share the same whole-sign house OR aspect each other 7th."""
    if p1 not in planet_positions or p2 not in planet_positions:
        return False
    h1 = _house_from(_sign(planet_positions[p1]), asc_sign)
    h2 = _house_from(_sign(planet_positions[p2]), asc_sign)
    if h1 == h2:
        return True
    # 7th mutual aspect
    if abs(h1 - h2) in {6}:  # houses differ by 6 → 7th from each other
        return True
    return False


# ---------------------------------------------------------------------------
# D9 helpers
# ---------------------------------------------------------------------------

def _d9_sign(lon: float) -> int:
    """Navamsa sign (0-based) of a longitude."""
    seg = int((lon % 30) / (30 / 9))          # 0..8 within the rashi
    rashi = int(lon / 30)
    # Navamsa starts: Aries for fire signs (0,4,8), Cancer for earth (1,5,9),
    # Libra for air (2,6,10), Capricorn for water (3,7,11)
    start_map = {0: 0, 1: 3, 2: 6, 3: 9}
    start = start_map[rashi % 4]
    return (start + seg) % 12


def _d9_asc_sign(asc_lon: float) -> int:
    return _d9_sign(asc_lon)


# ---------------------------------------------------------------------------
# MVP Yoga Rule Registry
# ---------------------------------------------------------------------------

def _check_pancha_mahapurusha(
    planet: str,
    planet_positions: dict[str, float],
    asc_sign: int,
    yoga_name: str,
) -> dict | None:
    """Generic Pancha Mahapurusha checker."""
    if planet not in planet_positions:
        return None
    lon = planet_positions[planet]
    dignity_ok = _in_own_or_exaltation(planet, lon)
    kendra_ok  = _in_kendra_from_lagna(lon, asc_sign)
    present = dignity_ok and kendra_ok

    dignity_label = (
        "exalted" if _in_exaltation(planet, lon) else
        "own sign" if _in_own_sign(planet, lon) else
        "none"
    )
    house = _house_from(_sign(lon), asc_sign)
    return {
        "present": present,
        "involved_planets": [planet],
        "involved_houses": [house],
        "rule_summary": (
            f"{planet} must be in own/exaltation sign AND in kendra (1,4,7,10) from Lagna. "
            f"Dignity={dignity_label}, House={house}."
        ),
        "strength_notes": {
            "dignity": dignity_label,
            "house_context": f"H{house} ({'kendra' if kendra_ok else 'not kendra'})",
            "retrograde_context": "",
            "affliction_notes": "",
        },
    }


def _check_pancha_mahapurusha_d9(
    planet: str,
    planet_positions: dict[str, float],
    asc_lon: float,
) -> bool:
    """D9 version: planet in own/exaltation in D9 AND in D9 kendra."""
    if planet not in planet_positions:
        return False
    lon = planet_positions[planet]
    d9_p = _d9_sign(lon)
    d9_a = _d9_asc_sign(asc_lon)
    dignity_ok = (d9_p in OWN_SIGNS.get(planet, []) or
                  EXALTATION_SIGNS.get(planet) == d9_p)
    h = _house_from(d9_p, d9_a)
    return dignity_ok and h in KENDRAS


def _check_gajakesari(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    present = False
    moon_sign = asc_sign  # fallback
    jup_house = 0
    if "Moon" in planet_positions and "Jupiter" in planet_positions:
        moon_sign = _sign(planet_positions["Moon"])
        jup_house = _house_from(_sign(planet_positions["Jupiter"]), moon_sign)
        present = jup_house in KENDRAS
    return {
        "present": present,
        "involved_planets": ["Moon", "Jupiter"],
        "involved_houses": [
            _house_from(_sign(planet_positions.get("Moon", 0)), asc_sign),
            _house_from(_sign(planet_positions.get("Jupiter", 0)), asc_sign),
        ],
        "rule_summary": (
            f"Jupiter must be in kendra (1,4,7,10) from Moon. "
            f"Jupiter is in H{jup_house} from Moon."
        ),
        "strength_notes": {
            "dignity": "",
            "house_context": f"Jupiter H{jup_house} from Moon",
            "retrograde_context": "",
            "affliction_notes": "",
        },
    }


def _check_lunar_yoga(
    name: str,
    planet_positions: dict[str, float],
    asc_sign: int,
    require_2nd: bool,
    require_12th: bool,
) -> dict:
    """Sunapha / Anapha / Durudhara / Kemadruma."""
    if "Moon" not in planet_positions:
        return {"present": False, "involved_planets": [], "involved_houses": [],
                "rule_summary": "Moon position unavailable.", "strength_notes": {}}
    moon_sign = _sign(planet_positions["Moon"])
    exclude = {"Sun", "Rahu", "Ketu"}
    p2nd  = _planets_in_house_from(moon_sign, 2,  planet_positions, exclude)
    p12th = _planets_in_house_from(moon_sign, 12, planet_positions, exclude)

    if name == "Kemadruma":
        # No non-luminary planets in 2nd OR 12th from Moon (no cancellation check in MVP)
        present = not p2nd and not p12th
        involved = []
        rule = "No planets (excl. Sun/Rahu/Ketu) in 2nd or 12th from Moon."
    elif require_2nd and require_12th:
        # Durudhara
        present = bool(p2nd) and bool(p12th)
        involved = p2nd + p12th
        rule = f"Planets in 2nd from Moon: {p2nd or 'none'}; in 12th: {p12th or 'none'}."
    elif require_2nd:
        # Sunapha
        present = bool(p2nd)
        involved = p2nd
        rule = f"Planets (excl. Sun/Rahu/Ketu) in 2nd from Moon: {p2nd or 'none'}."
    else:
        # Anapha
        present = bool(p12th)
        involved = p12th
        rule = f"Planets (excl. Sun/Rahu/Ketu) in 12th from Moon: {p12th or 'none'}."

    moon_h = _house_from(moon_sign, asc_sign)
    h2 = (moon_sign + 1) % 12
    h12 = (moon_sign + 11) % 12
    inv_houses = list({moon_h,
                       _house_from(h2, asc_sign) if require_2nd else moon_h,
                       _house_from(h12, asc_sign) if require_12th else moon_h})
    return {
        "present": present,
        "involved_planets": ["Moon"] + involved,
        "involved_houses": inv_houses,
        "rule_summary": rule,
        "strength_notes": {
            "dignity": "",
            "house_context": f"Moon in H{moon_h}",
            "retrograde_context": "",
            "affliction_notes": "",
        },
    }


def _check_chandra_mangala(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    present = _planets_conjunct_or_mutual_aspect(
        "Moon", "Mars", planet_positions, asc_sign
    )
    moon_h = _house_from(_sign(planet_positions.get("Moon", 0)), asc_sign)
    mars_h = _house_from(_sign(planet_positions.get("Mars", 0)), asc_sign)
    return {
        "present": present,
        "involved_planets": ["Moon", "Mars"],
        "involved_houses": [moon_h, mars_h],
        "rule_summary": (
            f"Moon and Mars in same whole-sign house or 7th from each other. "
            f"Moon=H{moon_h}, Mars=H{mars_h}."
        ),
        "strength_notes": {
            "dignity": "",
            "house_context": f"Moon H{moon_h}, Mars H{mars_h}",
            "retrograde_context": "",
            "affliction_notes": "",
        },
    }


def _check_budha_aditya(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    present = False
    sun_h = mars_h = 0
    if "Sun" in planet_positions and "Mercury" in planet_positions:
        sun_h  = _house_from(_sign(planet_positions["Sun"]),     asc_sign)
        mars_h = _house_from(_sign(planet_positions["Mercury"]), asc_sign)
        present = sun_h == mars_h   # conjunction = same whole-sign house
    return {
        "present": present,
        "involved_planets": ["Sun", "Mercury"],
        "involved_houses": [sun_h, mars_h],
        "rule_summary": (
            f"Sun and Mercury in same whole-sign house. "
            f"Sun=H{sun_h}, Mercury=H{mars_h}."
        ),
        "strength_notes": {
            "dignity": "",
            "house_context": f"Sun H{sun_h}, Mercury H{mars_h}",
            "retrograde_context": "",
            "affliction_notes": "",
        },
    }


def _check_raja_yoga_basic(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    """Parashari Raj Yoga: a kendra lord and a trikona lord are conjunct, mutual aspect, exchange, or placed in each other's house."""
    kendra_lords  = {_house_lord(h, asc_sign) for h in [1, 4, 7, 10]}
    trikona_lords = {_house_lord(h, asc_sign) for h in [1, 5, 9]}
    
    pairs: list[tuple[str, str]] = []
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl != tl:
                pairs.append((kl, tl))

    found_pair: tuple[str, str] | None = None
    relationship_type = ""
    for kl, tl in pairs:
        if kl not in planet_positions or tl not in planet_positions: continue
        h1 = _house_from(_sign(planet_positions[kl]), asc_sign)
        h2 = _house_from(_sign(planet_positions[tl]), asc_sign)
        
        # Check exchange
        kl_in_tl_house = _house_lord(h1, asc_sign) == tl
        tl_in_kl_house = _house_lord(h2, asc_sign) == kl
        
        if h1 == h2:
            found_pair = (kl, tl)
            relationship_type = "conjunction"
            break
        elif abs(h1 - h2) == 6:
            found_pair = (kl, tl)
            relationship_type = "mutual_aspect"
            break
        elif kl_in_tl_house and tl_in_kl_house:
            found_pair = (kl, tl)
            relationship_type = "exchange"
            break
        elif kl_in_tl_house or tl_in_kl_house:
            found_pair = (kl, tl)
            relationship_type = "placement"
            break

    present = found_pair is not None
    inv_planets = list(found_pair) if found_pair else []
    inv_houses = []
    for p in inv_planets:
        if p in planet_positions:
            inv_houses.append(_house_from(_sign(planet_positions[p]), asc_sign))

    rule = f"A kendra lord and a trikona lord must have a relationship (conjunct, aspect, exchange, placement)."
    if found_pair:
        rule += f" Found: {found_pair[0]} & {found_pair[1]} via {relationship_type}."
        
    return {
        "present": present,
        "involved_planets": inv_planets,
        "involved_houses": list(set(inv_houses)),
        "rule_summary": rule,
        "detected_relationship": relationship_type,
        "strength_notes": {},
    }


def _check_dhana_yoga_basic(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    """Dhan Yoga: lords of 2,5,9,11 conjunct, aspect, exchange or placement."""
    dhana_houses = [2, 5, 9, 11]
    lords = {h: _house_lord(h, asc_sign) for h in dhana_houses}
    pairs = []
    checked = set()
    for h1 in dhana_houses:
        for h2 in dhana_houses:
            if h1 >= h2: continue
            pair = (lords[h1], lords[h2])
            if pair[0] == pair[1]: continue
            key = tuple(sorted(pair))
            if key in checked: continue
            checked.add(key)
            pairs.append(pair)

    found_pair = None
    relationship_type = ""
    for kl, tl in pairs:
        if kl not in planet_positions or tl not in planet_positions: continue
        h1 = _house_from(_sign(planet_positions[kl]), asc_sign)
        h2 = _house_from(_sign(planet_positions[tl]), asc_sign)
        
        kl_in_tl_house = _house_lord(h1, asc_sign) == tl
        tl_in_kl_house = _house_lord(h2, asc_sign) == kl
        
        if h1 == h2:
            found_pair = (kl, tl)
            relationship_type = "conjunction"
            break
        elif abs(h1 - h2) == 6:
            found_pair = (kl, tl)
            relationship_type = "mutual_aspect"
            break
        elif kl_in_tl_house and tl_in_kl_house:
            found_pair = (kl, tl)
            relationship_type = "exchange"
            break
        elif kl_in_tl_house or tl_in_kl_house:
            found_pair = (kl, tl)
            relationship_type = "placement"
            break

    present = found_pair is not None
    inv_planets = list(found_pair) if found_pair else []
    inv_houses = []
    for p in inv_planets:
        if p in planet_positions:
            inv_houses.append(_house_from(_sign(planet_positions[p]), asc_sign))

    rule = f"Lords of wealth houses (2,5,9,11) must have a relationship."
    if found_pair:
        rule += f" Found: {found_pair[0]} & {found_pair[1]} via {relationship_type}."
        
    return {
        "present": present,
        "involved_planets": inv_planets,
        "involved_houses": list(set(inv_houses)),
        "rule_summary": rule,
        "detected_relationship": relationship_type,
        "strength_notes": {},
    }

def _check_maha_bhagya(
    planet_positions: dict[str, float],
    asc_sign: int,
    gender: str,
    is_day_birth: bool,
) -> dict:
    if "Sun" not in planet_positions or "Moon" not in planet_positions:
        return {"present": False, "involved_planets": [], "involved_houses": [], "rule_summary": "Missing Sun/Moon"}
    if gender not in ["Male", "Female"]:
        return {
            "present": False, "involved_planets": ["Sun", "Moon"], "involved_houses": [],
            "rule_summary": f"Maha Bhagya requires known gender (got '{gender}').", "strength_notes": {}
        }
        
    sun_sign = _sign(planet_positions["Sun"])
    moon_sign = _sign(planet_positions["Moon"])
    
    # Odd signs (Aries=0, Gemini=2, Leo=4... so even indices) are 0, 2, 4, 6, 8, 10
    # Even signs (Taurus=1, Cancer=3...) are 1, 3, 5, 7, 9, 11
    asc_odd = (asc_sign % 2 == 0)
    sun_odd = (sun_sign % 2 == 0)
    moon_odd = (moon_sign % 2 == 0)
    
    if gender == "Male":
        present = is_day_birth and asc_odd and sun_odd and moon_odd
        rule = "Male: born during day, Lagna, Sun, Moon in odd signs."
    else:
        present = not is_day_birth and not asc_odd and not sun_odd and not moon_odd
        rule = "Female: born during night, Lagna, Sun, Moon in even signs."

    return {
        "present": present,
        "involved_planets": ["Sun", "Moon"],
        "involved_houses": [1, _house_from(sun_sign, asc_sign), _house_from(moon_sign, asc_sign)],
        "rule_summary": f"{rule} (Birth={'Day' if is_day_birth else 'Night'}, Lagna={'Odd' if asc_odd else 'Even'}, Sun={'Odd' if sun_odd else 'Even'}, Moon={'Odd' if moon_odd else 'Even'})",
        "strength_notes": {},
    }

def _check_vipreet_raj(
    planet_positions: dict[str, float],
    asc_sign: int,
    lord_house: int,
    yoga_name: str,
) -> dict:
    lord = _house_lord(lord_house, asc_sign)
    present = False
    house_placed = 0
    if lord in planet_positions:
        house_placed = _house_from(_sign(planet_positions[lord]), asc_sign)
        if house_placed in [6, 8, 12]:
            present = True
            
    return {
        "present": present,
        "involved_planets": [lord],
        "involved_houses": [house_placed] if present else [],
        "rule_summary": f"{lord_house}th lord ({lord}) must be in 6, 8, or 12. Placed in H{house_placed}.",
        "strength_notes": {},
    }

def _check_amala_yoga(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    if "Moon" not in planet_positions:
        return {"present": False, "involved_planets": [], "involved_houses": [], "rule_summary": "Missing Moon"}
    moon_sign = _sign(planet_positions["Moon"])
    benefics = {"Jupiter", "Venus", "Mercury"}
    
    # check 10th from Lagna
    p10_lagna = _planets_in_house_from(asc_sign, 10, planet_positions)
    # check 10th from Moon
    p10_moon = _planets_in_house_from(moon_sign, 10, planet_positions)
    
    ben_lagna = [p for p in p10_lagna if p in benefics]
    ben_moon = [p for p in p10_moon if p in benefics]
    
    present = bool(ben_lagna) or bool(ben_moon)
    involved = list(set(ben_lagna + ben_moon))
    
    rule = "Benefic (Jupiter, Venus, Mercury) in 10th from Lagna OR Moon."
    if present:
        rule += f" Found {involved} in 10th."
        
    return {
        "present": present,
        "involved_planets": involved,
        "involved_houses": [10],
        "rule_summary": rule,
        "strength_notes": {},
    }

def _check_ubhayachari(
    planet_positions: dict[str, float],
    asc_sign: int,
) -> dict:
    if "Sun" not in planet_positions:
        return {"present": False, "involved_planets": [], "involved_houses": [], "rule_summary": "Missing Sun"}
    sun_sign = _sign(planet_positions["Sun"])
    exclude = {"Sun", "Moon", "Rahu", "Ketu"}
    p2nd = _planets_in_house_from(sun_sign, 2, planet_positions, exclude)
    p12th = _planets_in_house_from(sun_sign, 12, planet_positions, exclude)
    
    present = bool(p2nd) and bool(p12th)
    involved = p2nd + p12th
    
    return {
        "present": present,
        "involved_planets": ["Sun"] + involved,
        "involved_houses": [_house_from(sun_sign, asc_sign)],
        "rule_summary": f"Planets (excl. Moon/Nodes) in 2nd ({p2nd}) AND 12th ({p12th}) from Sun.",
        "strength_notes": {},
    }



# ---------------------------------------------------------------------------
# D9 confirmation helpers for non-Pancha-Mahapurusha yogas
# ---------------------------------------------------------------------------

def _check_conjunction_d9(p1: str, p2: str, planet_positions: dict[str, float],
                           asc_lon: float) -> bool:
    """Both planets in same D9 sign (conjunction in Navamsa)."""
    if p1 not in planet_positions or p2 not in planet_positions:
        return False
    return _d9_sign(planet_positions[p1]) == _d9_sign(planet_positions[p2])


def _check_gajakesari_d9(planet_positions: dict[str, float], asc_lon: float) -> bool:
    if "Moon" not in planet_positions or "Jupiter" not in planet_positions:
        return False
    d9_moon = _d9_sign(planet_positions["Moon"])
    d9_jup  = _d9_sign(planet_positions["Jupiter"])
    h = _house_from(d9_jup, d9_moon)
    return h in KENDRAS


def _check_lunar_yoga_d9(name: str, planet_positions: dict[str, float],
                          asc_lon: float) -> bool:
    """Rough D9 check: same logic on D9 longitudes (treat D9 position as new longitude)."""
    if "Moon" not in planet_positions:
        return False
    d9_moon_sign = _d9_sign(planet_positions["Moon"])
    d9_asc       = _d9_asc_sign(asc_lon)
    exclude = {"Sun", "Rahu", "Ketu"}
    p2nd  = [p for p, lon in planet_positions.items()
             if p not in exclude and _house_from(_d9_sign(lon), d9_moon_sign) == 2]
    p12th = [p for p, lon in planet_positions.items()
             if p not in exclude and _house_from(_d9_sign(lon), d9_moon_sign) == 12]
    if name == "Kemadruma":
        return not p2nd and not p12th
    elif name == "Durudhara":
        return bool(p2nd) and bool(p12th)
    elif name == "Sunapha":
        return bool(p2nd)
    elif name == "Anapha":
        return bool(p12th)
    return False


# ---------------------------------------------------------------------------
# MASTER REGISTRY
# ---------------------------------------------------------------------------
#
# Each entry: (yoga_name, category, system, d1_checker, d9_checker)
# Checkers are callables that accept (planet_positions, asc_sign, asc_lon) and
# return a dict with keys: present, involved_planets, involved_houses,
# rule_summary, strength_notes.
# ---------------------------------------------------------------------------

def _wrap_pmp(planet: str, yoga_name: str):
    """Factory that returns (d1_fn, d9_fn) for a Pancha Mahapurusha yoga."""
    def d1_fn(pp, asc_sign, asc_lon, gender, is_day):
        return _check_pancha_mahapurusha(planet, pp, asc_sign, yoga_name)
    def d9_fn(pp, asc_sign, asc_lon, gender, is_day):
        return _check_pancha_mahapurusha_d9(planet, pp, asc_lon)
    return d1_fn, d9_fn


def _build_registry():
    entries = []

    # Pancha Mahapurusha
    for planet, yname in [
        ("Mars",    "Ruchaka Yoga"),
        ("Mercury", "Bhadra Yoga"),
        ("Jupiter", "Hamsa Yoga"),
        ("Venus",   "Malavya Yoga"),
        ("Saturn",  "Sasa Yoga"),
    ]:
        d1f, d9f = _wrap_pmp(planet, yname)
        entries.append((yname, "Pancha Mahapurusha", "BPHS", d1f, d9f))

    # Gajakesari
    entries.append((
        "Gajakesari Yoga", "Lunar", "BPHS",
        lambda pp, asc, lon, g, d: _check_gajakesari(pp, asc),
        lambda pp, asc, lon, g, d: _check_gajakesari_d9(pp, lon),
    ))

    # Sunapha
    entries.append((
        "Sunapha Yoga", "Lunar", "BPHS",
        lambda pp, asc, lon, g, d: _check_lunar_yoga("Sunapha", pp, asc, True, False),
        lambda pp, asc, lon, g, d: _check_lunar_yoga_d9("Sunapha", pp, lon),
    ))

    # Anapha
    entries.append((
        "Anapha Yoga", "Lunar", "BPHS",
        lambda pp, asc, lon, g, d: _check_lunar_yoga("Anapha", pp, asc, False, True),
        lambda pp, asc, lon, g, d: _check_lunar_yoga_d9("Anapha", pp, lon),
    ))

    # Durudhara
    entries.append((
        "Durudhara Yoga", "Lunar", "BPHS",
        lambda pp, asc, lon, g, d: _check_lunar_yoga("Durudhara", pp, asc, True, True),
        lambda pp, asc, lon, g, d: _check_lunar_yoga_d9("Durudhara", pp, lon),
    ))

    # Kemadruma
    entries.append((
        "Kemadruma Yoga", "Lunar", "BPHS",
        lambda pp, asc, lon, g, d: _check_lunar_yoga("Kemadruma", pp, asc, False, False),
        lambda pp, asc, lon, g, d: _check_lunar_yoga_d9("Kemadruma", pp, lon),
    ))

    # Chandra-Mangala
    entries.append((
        "Chandra-Mangala Yoga", "Combination", "BPHS",
        lambda pp, asc, lon, g, d: _check_chandra_mangala(pp, asc),
        lambda pp, asc, lon, g, d: _check_conjunction_d9("Moon", "Mars", pp, lon),
    ))

    # Budha-Aditya
    entries.append((
        "Budha-Aditya Yoga", "Combination", "BPHS",
        lambda pp, asc, lon, g, d: _check_budha_aditya(pp, asc),
        lambda pp, asc, lon, g, d: _check_conjunction_d9("Sun", "Mercury", pp, lon),
    ))

    # Parashari Raj Yoga
    entries.append((
        "Parashari Raj Yoga", "Raja", "BPHS",
        lambda pp, asc, lon, g, d: _check_raja_yoga_basic(pp, asc),
        lambda pp, asc, lon, g, d: False,  # too complex for MVP D9
    ))

    # Dhana Yoga
    entries.append((
        "Dhan Yoga", "Wealth", "BPHS",
        lambda pp, asc, lon, g, d: _check_dhana_yoga_basic(pp, asc),
        lambda pp, asc, lon, g, d: False,
    ))

    # Maha Bhagya Yoga
    entries.append((
        "Maha Bhagya Yoga", "Fortune", "BPHS",
        lambda pp, asc, lon, g, d: _check_maha_bhagya(pp, asc, g, d),
        lambda pp, asc, lon, g, d: False,
    ))

    # Harsha Vipreet Raj Yoga
    entries.append((
        "Harsha Vipreet Raj Yoga", "Vipareeta Raja", "BPHS",
        lambda pp, asc, lon, g, d: _check_vipreet_raj(pp, asc, 6, "Harsha Vipreet Raj Yoga"),
        lambda pp, asc, lon, g, d: False,
    ))

    # Saral Vipreet Raj Yoga
    entries.append((
        "Saral Vipreet Raj Yoga", "Vipareeta Raja", "BPHS",
        lambda pp, asc, lon, g, d: _check_vipreet_raj(pp, asc, 8, "Saral Vipreet Raj Yoga"),
        lambda pp, asc, lon, g, d: False,
    ))

    # Amala Yoga
    entries.append((
        "Amala Yoga", "Other / Reputation", "BPHS",
        lambda pp, asc, lon, g, d: _check_amala_yoga(pp, asc),
        lambda pp, asc, lon, g, d: False,
    ))

    # Ubhayachari Yoga
    entries.append((
        "Ubhayachari Yoga", "Solar", "BPHS",
        lambda pp, asc, lon, g, d: _check_ubhayachari(pp, asc),
        lambda pp, asc, lon, g, d: False,
    ))

    return entries


YOGA_REGISTRY = _build_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_special_yogas(
    planet_positions: dict[str, float],
    asc_sign: int,
    asc_lon: float,
    retrograde_map: dict[str, bool] | None = None,
    gender: str = "Unknown",
    is_day_birth: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    Run all MVP yoga rules.

    Returns:
        applicable_yogas — list of rows with final_status in {"confirmed", "partial_d1_only"}
        yoga_rule_matrix — list of all checked rules
    """
    retrograde_map = retrograde_map or {}
    applicable_yogas: list[dict] = []
    yoga_rule_matrix: list[dict] = []

    for yoga_name, category, system, d1_fn, d9_fn in YOGA_REGISTRY:
        try:
            d1_result = d1_fn(planet_positions, asc_sign, asc_lon, gender, is_day_birth)
        except Exception as e:
            d1_result = {"present": False, "involved_planets": [], "involved_houses": [],
                         "rule_summary": f"Error: {e}", "strength_notes": {}}

        d1_present = d1_result.get("present", False)

        try:
            d9_present = bool(d9_fn(planet_positions, asc_sign, asc_lon, gender, is_day_birth))
        except Exception:
            d9_present = False

        # Annotate retrograde context
        retro_notes = [
            p for p in d1_result.get("involved_planets", [])
            if retrograde_map.get(p, False)
        ]
        if "strength_notes" in d1_result and retro_notes:
            d1_result["strength_notes"]["retrograde_context"] = (
                f"{', '.join(retro_notes)} retrograde — yoga may be internalized or delayed"
            )

        # Status logic
        if d1_present and d9_present:
            final_status = "confirmed"
            d9_status    = "confirmed"
            shown_in_main_table = True
            reason = "Present in D1 and confirmed in D9."
        elif d1_present and not d9_present:
            final_status = "partial_d1_only"
            d9_status    = "absent"
            shown_in_main_table = True
            reason = "Present in D1 but absent in D9."
        elif not d1_present and d9_present:
            final_status = "navamsa_support_only_debug"
            d9_status    = "support_only"
            shown_in_main_table = False
            reason = "Absent in D1. Appears in D9, but D9 cannot create yoga without D1 foundation."
        else:
            final_status = "absent"
            d9_status    = "absent"
            shown_in_main_table = False
            reason = "Absent in D1."

        row = {
            "yoga_name":           yoga_name,
            "category":            category,
            "system":              system,
            "rule_summary":        d1_result.get("rule_summary", ""),
            "d1_status":           "present" if d1_present else "absent",
            "d9_status":           d9_status,
            "final_status":        final_status,
            "shown_in_main_table": shown_in_main_table,
            "involved_planets_d1": d1_result.get("involved_planets", []),
            "involved_houses_d1":  d1_result.get("involved_houses", []),
            "involved_planets_d9": [], # MVP: D9 logic is mostly positional checks
            "involved_houses_d9":  [], 
            "reason":              reason,
            "strength_notes":      d1_result.get("strength_notes", {}),
            # Keep legacy keys to avoid breaking existing UI code if any
            "involved_planets":    d1_result.get("involved_planets", []),
            "involved_houses":     d1_result.get("involved_houses", []),
        }

        if shown_in_main_table:
            applicable_yogas.append(row)

        yoga_rule_matrix.append(row)

    return applicable_yogas, yoga_rule_matrix
