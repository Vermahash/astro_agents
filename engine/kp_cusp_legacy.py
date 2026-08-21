from __future__ import annotations

"""
Legacy cusp fallback.

This module intentionally provides a deterministic fallback that mimics
table-style cusp handling by applying a tiny, configurable correction to the
Swiss sidereal Placidus cusps. It is meant for compatibility experiments.
"""

from typing import List, Tuple

import swisseph as swe


def compute_legacy_sidereal_placidus(
    jd: float,
    lat: float,
    lon: float,
    sid_mode: int,
    cusp_correction_arcsec: float = -79.0,
) -> Tuple[List[float], float, float]:
    """
    Return sidereal Placidus cusps + (asc, mc) with a legacy-style correction.

    The correction is applied uniformly to cusp longitudes in arcseconds.
    This keeps behavior deterministic and easy to disable/compare.
    """
    swe.set_sid_mode(sid_mode, 0, 0)
    cuss, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    offset = cusp_correction_arcsec / 3600.0
    cusps = [((c + offset) % 360.0) for c in cuss[:12]]
    asc = (ascmc[0] + offset) % 360.0
    mc = (ascmc[1] + offset) % 360.0
    return cusps, asc, mc

