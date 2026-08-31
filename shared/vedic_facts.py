"""
Vedic lookup helpers used by the harness (no Swiss Ephemeris).

Purpose:
    House lords, dignity, and shodashavarga sign indices from packet longitudes.
    Mirrors engine.astro_kp formulas so specialists/tests do not import swe.

Inputs:
    Longitudes, lagna sign index, house numbers, varga division.

Outputs:
    Sign names, lords, dignity labels, varga sign indices.
"""

from __future__ import annotations

ZODIAC_SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

SIGN_LORDS = [
    "Mars",
    "Venus",
    "Mercury",
    "Moon",
    "Sun",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Saturn",
    "Jupiter",
]

EXALTATION_SIGNS: dict[str, int] = {
    "Sun": 0,
    "Moon": 1,
    "Mars": 9,
    "Mercury": 5,
    "Jupiter": 3,
    "Venus": 11,
    "Saturn": 6,
}

DEBILITATION_SIGNS: dict[str, int] = {
    "Sun": 6,
    "Moon": 7,
    "Mars": 3,
    "Mercury": 11,
    "Jupiter": 9,
    "Venus": 5,
    "Saturn": 0,
}

OWN_SIGNS: dict[str, list[int]] = {
    "Sun": [4],
    "Moon": [3],
    "Mars": [0, 7],
    "Mercury": [2, 5],
    "Jupiter": [8, 11],
    "Venus": [1, 6],
    "Saturn": [9, 10],
}

SAV_STRONG = 28
SAV_WEAK = 25

PLANET_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

DIRECTIONAL_MAP = {
    0: ("EAST", "Fire"),
    4: ("EAST", "Fire"),
    8: ("EAST", "Fire"),
    1: ("SOUTH", "Earth"),
    5: ("SOUTH", "Earth"),
    9: ("SOUTH", "Earth"),
    2: ("WEST", "Air"),
    6: ("WEST", "Air"),
    10: ("WEST", "Air"),
    3: ("NORTH", "Water"),
    7: ("NORTH", "Water"),
    11: ("NORTH", "Water"),
}


def sign_index(lon: float) -> int:
    """0-based zodiac sign from sidereal longitude."""
    return int(float(lon) / 30.0) % 12


def sign_name(lon: float | int) -> str:
    """Zodiac name from longitude or 0-based sign index."""
    if isinstance(lon, int) and 0 <= lon <= 11:
        return ZODIAC_SIGNS[lon]
    return ZODIAC_SIGNS[sign_index(float(lon))]


def deg_in_sign(lon: float) -> float:
    return float(lon) % 30.0


def house_from_lagna(planet_sign: int, asc_sign: int) -> int:
    """Whole-sign house 1–12 of planet_sign counted from lagna."""
    return (int(planet_sign) - int(asc_sign)) % 12 + 1


def house_sign_index(asc_sign: int, house: int) -> int:
    return (int(asc_sign) + int(house) - 1) % 12


def house_lord(asc_sign: int, house: int) -> str:
    return SIGN_LORDS[house_sign_index(asc_sign, house)]


def dignity(planet: str, sign_idx: int) -> str:
    """exalted | debilitated | own | neutral."""
    p = planet
    s = int(sign_idx) % 12
    if EXALTATION_SIGNS.get(p) == s:
        return "exalted"
    if DEBILITATION_SIGNS.get(p) == s:
        return "debilitated"
    if s in OWN_SIGNS.get(p, []):
        return "own"
    return "neutral"


def sav_status(score: int | float | None) -> str:
    if score is None:
        return "NOT IN PACKET"
    n = float(score)
    if n > SAV_STRONG:
        return "SUPPORTS"
    if n <= SAV_WEAK:
        return "RESISTS"
    return "MIXED"


def get_varga_sign(lon: float, division: int) -> int:
    """
    Shodashavarga sign index. Same algorithm as engine.astro_kp.get_varga_sign
    (D1–D30; other divisions fall back to D1 sign).
    """
    sign_idx = int(lon / 30) % 12
    deg_in = lon % 30
    if division == 1:
        return sign_idx
    if division == 2:
        is_odd = ((sign_idx + 1) % 2 != 0)
        first = deg_in < 15
        return (4 if first else 3) if is_odd else (3 if first else 4)
    if division == 3:
        return (sign_idx + int(deg_in / 10) * 4) % 12
    if division == 4:
        return (sign_idx + int(deg_in / 7.5) * 3) % 12
    if division == 7:
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = sign_idx if is_odd else (sign_idx + 6)
        return (start + int(deg_in / (30 / 7))) % 12
    if division == 9:
        element = sign_idx % 4
        start = [0, 9, 6, 3][element]
        return (start + int(deg_in / (30 / 9))) % 12
    if division == 10:
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = sign_idx if is_odd else (sign_idx + 8)
        return (start + int(deg_in / 3)) % 12
    if division == 12:
        return (sign_idx + int(deg_in / 2.5)) % 12
    if division == 30:
        is_odd = ((sign_idx + 1) % 2 != 0)
        d = deg_in
        if is_odd:
            return 0 if d <= 5 else (10 if d <= 10 else (8 if d <= 18 else (2 if d <= 25 else 6)))
        return 1 if d <= 5 else (5 if d <= 12 else (11 if d <= 20 else (9 if d <= 25 else 7)))
    return sign_idx
