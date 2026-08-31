"""Synthetic natal packet for harness specialist tests (Virgo lagna, finance-shaped)."""

from __future__ import annotations

from typing import Any

# Whole-sign from Virgo (5): H1 Virgo … H2 Libra … H9 Taurus … H11 Cancer … H12 Leo
PLANET_LONS = {
    "Sun": 5 * 30 + 22.43,
    "Moon": 1 * 30 + 21.09,
    "Mars": 4 * 30 + 7.45,
    "Mercury": 6 * 30 + 2.53,
    "Jupiter": 10 * 30 + 26.20,
    "Venus": 5 * 30 + 17.31,
    "Saturn": 0 * 30 + 7.28,
    "Rahu": 4 * 30 + 5.01,
    "Ketu": 10 * 30 + 5.01,
}

ASC_LON = 5 * 30 + 10.0  # Virgo


def finance_shaped_payload() -> dict[str, Any]:
    """Engine-shaped structured_payload sufficient for finance + health specialists."""
    sign_index = {p: int(lon / 30) % 12 for p, lon in PLANET_LONS.items()}
    asc_sign = int(ASC_LON / 30) % 12
    house_from = {p: (sign_index[p] - asc_sign) % 12 + 1 for p in PLANET_LONS}
    houses: dict[str, list] = {f"H{i}": [] for i in range(1, 13)}
    houses["H1"].append(
        {
            "planet": "Lagna",
            "sign": "Virgo",
            "sign_index": 5,
            "degree": 10.0,
            "longitude": ASC_LON,
            "direction": "SOUTH",
            "bhava_house": 1,
            "bhava_shift": False,
        }
    )
    for p, lon in PLANET_LONS.items():
        h = house_from[p]
        houses[f"H{h}"].append(
            {
                "planet": p,
                "sign": [
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
                ][sign_index[p]],
                "sign_index": sign_index[p],
                "degree": lon % 30,
                "longitude": lon,
                "direction": "WEST" if sign_index[p] in (2, 6, 10) else "SOUTH" if sign_index[p] in (1, 5, 9) else "EAST" if sign_index[p] in (0, 4, 8) else "NORTH",
                "bhava_house": h,
                "bhava_shift": False,
            }
        )
    sav = {"1": 27, "2": 25, "3": 29, "4": 32, "5": 28, "6": 34, "7": 26, "8": 20, "9": 30, "10": 36, "11": 40, "12": 25}
    return {
        "natal_core": {
            "longitudes": PLANET_LONS,
            "sign_index": sign_index,
            "house_from_lagna": house_from,
            "bhava_house": dict(house_from),
            "baladi_avastha": {"Jupiter": "Mrita"},
            "ascendant_lon": ASC_LON,
        },
        "unified_kundali": {"house_system": "Whole Sign", "houses": houses},
        "ashtakavarga_sav": sav,
        "special_yogas": [
            {
                "yoga_name": "Maha Parivartana",
                "category": "dhana",
                "final_status": "confirmed",
                "rule_summary": "Mercury-Venus exchange 1/10 with 2/9",
                "involved_planets_d1": ["Mercury", "Venus"],
                "involved_houses_d1": [1, 2],
            }
        ],
        "cusps": {
            "1": {"lon": ASC_LON, "star_lord": "Moon", "sub_lord": "Saturn", "sign_lord": "Mercury"},
            "2": {"lon": 180.0, "star_lord": "Rahu", "sub_lord": "Saturn", "sign_lord": "Venus"},
            "6": {"lon": 300.0, "star_lord": "Mars", "sub_lord": "Saturn", "sign_lord": "Saturn"},
            "8": {"lon": 0.5, "star_lord": "Ketu", "sub_lord": "Venus", "sign_lord": "Mars"},
            "11": {"lon": 90.0, "star_lord": "Saturn", "sub_lord": "Jupiter", "sign_lord": "Moon"},
            "12": {"lon": 120.0, "star_lord": "Ketu", "sub_lord": "Rahu", "sign_lord": "Sun"},
        },
        "planet_star_sub_lords": {
            "Saturn": {"star_lord": "Rahu", "sub_lord": "Saturn"},
            "Jupiter": {"star_lord": "Saturn", "sub_lord": "Jupiter"},
            "Mercury": {"star_lord": "Mars", "sub_lord": "Venus"},
        },
        "bnn_module": {
            "directional_groups": {
                "WEST": ["Mercury (Libra 2°53')", "Jupiter (Aquarius 26°20')"],
                "SOUTH": ["Venus (Virgo 17°31')", "Sun (Virgo 22°43')"],
            },
            "groups": {"deva": ["Jupiter", "Sun", "Moon", "Mars", "Ketu"], "asura": ["Saturn", "Venus", "Mercury", "Rahu"]},
        },
        "kp_astrology_matrix": {"moon_dasha_balance_at_birth": {"md_lord": "Jupiter", "balance": "16y"}},
        "kp_prediction": {"note": "sample"},
    }
