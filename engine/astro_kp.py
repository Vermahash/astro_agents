import streamlit as st
import swisseph as swe
import datetime
import pytz
import pandas as pd
import os
import math
import json
import re  # Moved to top of file for efficiency
from fractions import Fraction
from decimal import Decimal
from typing import Any
from dateutil.relativedelta import relativedelta  # Available but not used in timeline (uses pure timedelta for precision)

from kp_logic import analyze_master_packet, MasterPacket
from kp_book_rules import load_kp_rule_config
from kp_cusp_legacy import compute_legacy_sidereal_placidus
from yoga_engine import detect_special_yogas

# Try to import streamlit-searchbox, fallback to native selectbox if not available
try:
    from streamlit_searchbox import st_searchbox
    HAS_SEARCHBOX = True
except ImportError:
    HAS_SEARCHBOX = False
    # Only show warning if streamlit is initialized (not during import)
    if 'streamlit' in dir():
        st.warning("streamlit-searchbox not installed. Install with: pip install streamlit-searchbox")

# Year length constants for Vimshottari Dasha calculations
SOLAR_YEAR = 365.2425  # Tropical solar year
SAVANA_YEAR = 360.0    # Traditional Vedic year (for proportional division only)

# DASHA_YEAR_DAYS: Used for converting dasha years to calendar dates
# Most software (including AstroSage) uses 365.2425 for calendar conversion
# even though proportional division uses the 120-year cycle
DASHA_YEAR_DAYS = 365.2425  # Standard calendar year for date conversion
GREGORIAN_YEAR = 365.2425  # Solar calendar year

# Panchang (Five Limbs of Time) - Tithi names
TITHI_NAMES = [
    "Prathama", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima/Amavasya"
]

# Yoga names (27 total)
YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shula", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti"
]

# Karana names (11 total, repeating)
KARANA_NAMES = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garija",
    "Vanija", "Visti", "Shakuni", "Chatushpada", "Naga", "Kimstughna"
]

# ==========================================
# 0. HELPER CONSTANTS FOR HIT THEORY
# ==========================================

SLOW_PLANETS = ["Saturn", "Jupiter", "Rahu", "Ketu"]

KALAPURUSHA_MAP = {
    1: "self, head, overall life path",
    2: "wealth, speech, family, face",
    3: "courage, siblings, arms",
    4: "home, mother, chest, heart",
    5: "children, creativity, stomach",
    6: "disease, debts, intestines",
    7: "marriage, partnerships, lower abdomen",
    8: "sudden events, chronic issues, genitals",
    9: "fortune, father, thighs",
    10: "career, knees, status",
    11: "income, gains, ankles",
    12: "loss, expenditure, feet",
}

DOMAIN_MAP = {
    "wealth": [2, 11],
    "career": [10, 6],
    "health": [1, 6, 8, 12],
    "relationships": [5, 7],
    "property": [4],
    "luck_spirituality": [9],
}

# Vimshottari Dasha sequence (120 years total) - CORRECT ORDER: Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury
VIMSHOTTARI_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
    ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
]

# Proper Vedha pairs: {planet: {auspicious_house: vedha_house}} - Standard Gochara Vedha
VEDHA_PAIRS = {
    "Sun": {11: 5, 3: 9, 6: 12, 10: 4},
    "Mars": {11: 5, 3: 12, 6: 9},
    "Jupiter": {11: 8, 2: 12, 7: 3, 9: 10, 5: 4},
    "Saturn": {11: 5, 3: 12, 6: 9},
    "Venus": {1: 8, 2: 9, 3: 10, 4: 11, 5: 12, 6: 1, 7: 2, 8: 3, 9: 4, 10: 5, 11: 6, 12: 7},  # Forward Vedha
    "Mercury": {11: 5, 3: 12, 2: 12, 4: 10},  # Similar to Sun
    "Moon": {11: 5, 3: 12, 2: 12, 4: 10},  # Similar to Sun
    "Rahu": {11: 5, 3: 12, 2: 12, 4: 10},  # Similar to Sun
    "Ketu": {11: 5, 3: 12, 2: 12, 4: 10},  # Similar to Sun
}

# ==========================================
# 1. DATABASE ENGINE
# ==========================================

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_APP_ROOT, "global_cities_full.csv")
DATA_URL = "https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/master/csv/cities.csv"

@st.cache_data
def load_city_data():
    try:
        df = None
        if os.path.exists(DB_FILE):
            if os.path.getsize(DB_FILE) == 0: os.remove(DB_FILE)
            
        if os.path.exists(DB_FILE):
            df = pd.read_csv(DB_FILE, usecols=['name', 'country_name', 'latitude', 'longitude'],
                             dtype={'name': str, 'country_name': str, 'latitude': float, 'longitude': float},
                             low_memory=False)
        else:
            with st.spinner("Downloading City DB..."):
                df = pd.read_csv(DATA_URL)
                df.to_csv(DB_FILE, index=False)
                df = pd.read_csv(DB_FILE, usecols=['name', 'country_name', 'latitude', 'longitude'],
                                 dtype={'name': str, 'country_name': str, 'latitude': float, 'longitude': float},
                                 low_memory=False)
        
        df['display_name'] = df['name'] + ", " + df['country_name']
        return df
    except:
        return None

@st.cache_resource
def build_city_index(df_cities):
    """Pre-computed 3-character prefix index for O(1) city lookup.
    
    Returns a dictionary where:
    - Key: First 3 characters of city name (lowercased)
    - Value: List of tuples (display_name, latitude, longitude)
    """
    if df_cities is None or df_cities.empty:
        return {}
    
    index = {}
    short_names = []  # Cities with names < 3 characters
    
    for _, row in df_cities.iterrows():
        city_name = str(row['name']).strip()
        display_name = str(row['display_name']).strip()
        lat = float(row['latitude'])
        lon = float(row['longitude'])
        
        city_lower = city_name.lower()
        
        if len(city_lower) < 3:
            # Store short names separately
            short_names.append((display_name, lat, lon))
        else:
            # Extract first 3 characters as key
            prefix = city_lower[:3]
            if prefix not in index:
                index[prefix] = []
            index[prefix].append((display_name, lat, lon))
    
    # Store short names under special key
    if short_names:
        index['__short__'] = short_names
    
    return index

def search_city(search_term, city_index):
    """Search function for streamlit-searchbox using prefix index.
    
    Args:
        search_term: User input string
        city_index: Pre-computed index from build_city_index
    
    Returns:
        List of tuples (label, value) where value is (lat, lon)
    """
    if not search_term or not city_index:
        return []
    
    # Sanitize: lowercase and strip
    search_term = search_term.lower().strip()
    
    # 3-Level Trigger: Don't search if less than 3 characters
    if len(search_term) < 3:
        return []
    
    # Extract first 3 characters as key for O(1) lookup
    prefix = search_term[:3]
    
    # O(1) Lookup: Get the bucket of cities
    candidates = list(city_index.get(prefix, []))
    
    # Also check short names if search term is short
    if len(search_term) <= 3:
        candidates.extend(city_index.get('__short__', []))
    
    # Refined Filter: Filter remaining characters from the small sub-list
    results = []
    
    for display_name, lat, lon in candidates:
        display_lower = display_name.lower()
        
        # Check if search term matches (either prefix match or contains)
        if search_term in display_lower or display_lower.startswith(search_term):
            # Format: (label, value) where value will be used to extract lat/lon
            results.append((display_name, (lat, lon)))
    
    # Limit results to top 20 for performance
    return results[:20]

# ==========================================
# 2. VEDIC MATH ENGINE
# ==========================================

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "P. Phalguni", "U. Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "P. Ashadha", "U. Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "P. Bhadrapada", "U. Bhadrapada", "Revati"
]

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE, "Ketu": None  # Note: Using MEAN_NODE (always retrograde). For True Nodes (can be direct), use swe.TRUE_NODE 
}

PLANET_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

AVASTHAS = [
    "Sayana (Sleeping)", "Upavesana (Sitting)", "Netrapani (Hand on Eye)", 
    "Prakasana (Shining)", "Gamana (Moving)", "Agamana (Coming)", 
    "Sabha (Assembly)", "Agama (Acquiring)", "Bhojana (Eating)", 
    "Nrityalipsa (Desire to Dance)", "Kautuka (Eager)", "Nidra (Sleep)"
]

# ---------------------------------------------------------------------------
# PARASHARA BHINNA ASHTAKAVARGA (BAV) TABLES  (BPHS Chapters 66-72)
# For each of the 7 planets (Sun–Saturn), 8 contributors (7 planets + Lagna)
# give bindus at the listed house-offsets counted from the contributor.
# Offset 1 = same sign as the contributor, 2 = next sign, etc.
# ---------------------------------------------------------------------------
BAV_TABLES: dict[str, dict[str, list[int]]] = {
    "Sun": {
        "Sun":     [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon":    [3, 6, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus":   [6, 7, 12],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun":     [3, 6, 7, 8, 10, 11],
        "Moon":    [1, 3, 6, 7, 10, 11],
        "Mars":    [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus":   [3, 4, 5, 7, 9, 10, 11],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [3, 6, 10, 11],
    },
    "Mars": {
        "Sun":     [3, 5, 6, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus":   [6, 8, 11, 12],
        "Saturn":  [1, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun":     [5, 6, 9, 11, 12],
        "Moon":    [2, 4, 6, 8, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun":     [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon":    [2, 5, 7, 9, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus":   [2, 5, 6, 9, 10, 11],
        "Saturn":  [3, 5, 6, 12],
        "Lagna":   [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun":     [8, 11, 12],
        "Moon":    [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars":    [3, 5, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn":  [3, 4, 5, 8, 9, 10, 11],
        "Lagna":   [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun":     [1, 2, 4, 7, 8, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus":   [6, 11, 12],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [1, 3, 4, 6, 10, 11],
    },
}

# Backward-compat alias (kept for any external references)
ASHTAKA_POINTS = {p: BAV_TABLES[p][p] for p in BAV_TABLES}

# Nakshatra rulers in Vimshottari order (Ketu..Mercury) repeated
NAKSHATRA_RULERS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
] * 3

# Sign lords (sidereal) for 0..11 = Aries..Pisces
SIGN_LORDS = [
    "Mars",    # Aries
    "Venus",   # Taurus
    "Mercury", # Gemini
    "Moon",    # Cancer
    "Sun",     # Leo
    "Mercury", # Virgo
    "Venus",   # Libra
    "Mars",    # Scorpio
    "Jupiter", # Sagittarius
    "Saturn",  # Capricorn
    "Saturn",  # Aquarius
    "Jupiter", # Pisces
]

EXALTATION_SIGNS = {
    "Sun": 0,       # Aries
    "Moon": 1,      # Taurus
    "Mars": 9,      # Capricorn
    "Mercury": 5,   # Virgo
    "Jupiter": 3,   # Cancer
    "Venus": 11,    # Pisces
    "Saturn": 6,    # Libra
}

DEBILITATION_SIGNS = {
    "Sun": 6,       # Libra
    "Moon": 7,      # Scorpio
    "Mars": 3,      # Cancer
    "Mercury": 11,  # Pisces
    "Jupiter": 9,   # Capricorn
    "Venus": 5,     # Virgo
    "Saturn": 0,    # Aries
}

COMBUST_ORB_DEG = {
    "Mercury": 14.0,
    "Venus": 10.0,
    "Mars": 17.0,
    "Jupiter": 11.0,
    "Saturn": 15.0,
}

WEEKDAY_LORDS = {
    0: "Moon",     # Monday
    1: "Mars",     # Tuesday
    2: "Mercury",  # Wednesday
    3: "Jupiter",  # Thursday
    4: "Venus",    # Friday
    5: "Saturn",   # Saturday
    6: "Sun",      # Sunday
}

KP_RULES = load_kp_rule_config()
KP_RULER_ORDER = list(KP_RULES.ruler_order)
KP_DASHA_YEARS_SEQ = list(KP_RULES.dasha_years_seq)
KP_TOTAL_YEARS = KP_RULES.vimshottari_total_years
KP_NAK_LEN_ARCMIN = KP_RULES.nakshatra_span_arcmin

# Cusp engine toggle:
# - "auto": evaluate all engines and pick the most boundary-stable result
# - "swiss_vp291_sidereal": Swiss sidereal houses_ex (current stable baseline)
# - "kp_new_manual": tropical Placidus cusps minus KP-New manual ayanamsa
# - "legacy_fallback": Swiss sidereal cusps with legacy correction offset
KP_CUSP_ENGINE = "auto"

# Dasha ayanamsha mode (independent of KP cusp ayanamsha)
# "lahiri"         = Lahiri/Chitrapaksha sidereal (standard Vimshottari default)
# "kp"             = KP Krishnamurti VP291 (same as chart cusps)
# "same_as_chart"  = use planet_positions["Moon"] — no re-fetch
DASHA_AYANAMSHA_MODE = "lahiri"


def calculate_dasha_moon_longitude(jd_ut: float, ayanamsha_mode: str, chart_moon_lon: float | None = None) -> dict:
    """Compute sidereal Moon longitude for Vimshottari Dasha, using a dedicated ayanamsha.

    Returns a dict with:
        moon_longitude      - sidereal longitude used for Dasha calculation
        ayanamsha_mode      - mode used
        ayanamsha_value     - ayanamsha applied (degrees)
        tropical_longitude  - tropical raw longitude (before ayanamsha subtraction)
    """
    if ayanamsha_mode == "same_as_chart":
        if chart_moon_lon is None:
            raise ValueError("chart_moon_lon required when ayanamsha_mode='same_as_chart'")
        return {
            "moon_longitude": chart_moon_lon,
            "ayanamsha_mode": "same_as_chart",
            "ayanamsha_value": 0.0,
            "tropical_longitude": chart_moon_lon,
        }

    # Fetch tropical Moon once
    trop_res = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)
    trop_lon = trop_res[0][0]

    if ayanamsha_mode == "lahiri":
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        ayan = swe.get_ayanamsa_ut(jd_ut)
    elif ayanamsha_mode == "kp":
        swe.set_sid_mode(swe.SIDM_KRISHNAMURTI_VP291, 0, 0)
        ayan = swe.get_ayanamsa_ut(jd_ut)
    else:
        raise ValueError(f"Unknown dasha ayanamsha_mode: {ayanamsha_mode!r}")

    sid_lon = (trop_lon - ayan) % 360
    return {
        "moon_longitude": sid_lon,
        "ayanamsha_mode": ayanamsha_mode,
        "ayanamsha_value": ayan,
        "tropical_longitude": trop_lon,
    }

def decimal_to_dms(deg_float):
    d = int(deg_float)
    m = int((deg_float - d) * 60)
    return d, m

def decimal_to_dms_full(deg_float):
    """Return (degrees, minutes, seconds) as integers."""
    d = int(deg_float)
    rem = (deg_float - d) * 60
    m = int(rem)
    s = int((rem - m) * 60)
    return d, m, s

def get_nakshatra(longitude):
    """Returns (Name, Index 1-27, Pada 1-4)"""
    nak_len = 13.333333
    idx = int(longitude / nak_len)
    pos_in_nak = longitude % nak_len
    pada = int(pos_in_nak / 3.333333) + 1
    return NAKSHATRAS[idx % 27], (idx % 27) + 1, pada

def get_sign_from_lon(lon):
    return int(lon / 30)


def get_sign_lord_from_index(sign_idx: int) -> str:
    return SIGN_LORDS[sign_idx % 12]


def rotate_vimshottari_from(lord_name: str) -> list[str]:
    """Return the Vimshottari sequence starting from a given lord."""
    start_idx = KP_RULER_ORDER.index(lord_name)
    return [KP_RULER_ORDER[(start_idx + i) % 9] for i in range(9)]


def find_weighted_segment(value: Fraction, total_span: Fraction, sequence: list[str]) -> tuple[str, Fraction, Fraction]:
    """
    Finds the sub-segment in a Vimsottari sequence.
    """
    acc = Fraction(0, 1)
    for lord in sequence:
        idx = KP_RULER_ORDER.index(lord)
        span = total_span * Fraction(KP_DASHA_YEARS_SEQ[idx], KP_TOTAL_YEARS)
        if value < acc + span:
            return lord, acc, acc + span
        acc += span
    # Fallback to last in case of float boundary
    last_lord = sequence[-1]
    last_idx = KP_RULER_ORDER.index(last_lord)
    return last_lord, acc - total_span * Fraction(KP_DASHA_YEARS_SEQ[last_idx], KP_TOTAL_YEARS), acc


def classify_kp_longitude(raw_longitude: float, *, debug=False) -> dict[str, Any]:
    """Canonical helper for KP classification."""
    lon_norm = raw_longitude % 360.0
    
    NAKSHATRA_SPAN = Fraction(40, 3)
    
    lon_frac = Fraction(str(Decimal(str(lon_norm))))
    
    nak_index = int(lon_frac / NAKSHATRA_SPAN)
    offset_in_star = lon_frac - (nak_index * NAKSHATRA_SPAN)
    star_lord = NAKSHATRA_RULERS[nak_index]
    
    sub_sequence = rotate_vimshottari_from(star_lord)
    sub_lord, sub_start, sub_end = find_weighted_segment(
        value=offset_in_star,
        total_span=NAKSHATRA_SPAN,
        sequence=sub_sequence
    )
    
    offset_in_sub = offset_in_star - sub_start
    sub_span = sub_end - sub_start
    
    sub_sub_sequence = rotate_vimshottari_from(sub_lord)
    sub_sub_lord, sub_sub_start, sub_sub_end = find_weighted_segment(
        value=offset_in_sub,
        total_span=sub_span,
        sequence=sub_sub_sequence
    )
    
    sign_idx = int(lon_norm / 30)
    sign = ZODIAC_SIGNS[sign_idx]
    degree_in_sign = lon_norm % 30
    nak_name = NAKSHATRAS[nak_index]
    
    PADA_SPAN = Fraction(10, 3)
    pada = int(offset_in_star / PADA_SPAN) + 1

    res = {
        "raw_longitude": raw_longitude,
        "normalized_longitude": lon_norm,
        "sign": sign,
        "degree_in_sign": degree_in_sign,
        "nakshatra": nak_name,
        "pada": pada,
        "star_lord": star_lord,
        "sub_lord": sub_lord,
        "sub_sub_lord": sub_sub_lord,
        "offset_in_star": float(offset_in_star),
        "sub_start": float(sub_start),
        "sub_end": float(sub_end),
        "offset_in_sub": float(offset_in_sub),
        "sub_sub_sequence_start": float(sub_sub_start),
    }
    return res


def get_houses_owned_by_planet(planet: str, asc_sign_id: int) -> list[int]:
    """Return whole-sign houses (1..12) owned by a planet from Lagna."""
    out: list[int] = []
    for h in range(1, 13):
        sign_idx = (asc_sign_id + h - 1) % 12
        if get_sign_lord_from_index(sign_idx) == planet:
            out.append(h)
    return out


def build_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not headers:
        return ""
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join([":---"] * len(headers)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join([head, sep] + body)


def get_kp_ayanamsa_ut(jd: float) -> float:
    """
    Return KP (Krishnamurti) ayanamsa for a given Julian Day.

    Uses Swiss Ephemeris SIDM_KRISHNAMURTI_VP291 (aka KP VP291),
    which aligns better with AstroSage KP cusp/sub-lord outputs in
    boundary-sensitive charts.
    """
    sid_mode = getattr(swe, "SIDM_KRISHNAMURTI_VP291", 45)
    swe.set_sid_mode(sid_mode)
    ayan = swe.get_ayanamsa_ut(jd)
    swe.set_sid_mode(0)  # reset to default
    return ayan


def get_kp_new_manual_ayanamsa_ut(jd: float) -> float:
    """
    KP-New style linear ayanamsa approximation (manual):
    epoch 291 AD, rate 50.2388475 arcsec/year.
    """
    y, _, _, _ = swe.revjul(jd)
    jd_start = swe.julday(int(y), 1, 1, 0.0)
    year_frac = (jd - jd_start) / 365.2425
    year_decimal = float(y) + year_frac
    return (year_decimal - 291.0) * 50.2388475 / 3600.0


def _compute_placidus_cusps_by_engine(
    jd: float,
    lat: float,
    lon: float,
    engine: str,
) -> tuple[list[float], float, float]:
    if engine == "kp_new_manual":
        cuss_plac_trop, ascmc_trop = swe.houses_ex(jd, lat, lon, b"P", 0)
        ayan_kp_cusp = get_kp_new_manual_ayanamsa_ut(jd)
        asc_deg_sidereal_plac = (ascmc_trop[0] - ayan_kp_cusp) % 360
        mc_deg_sidereal_plac = (ascmc_trop[1] - ayan_kp_cusp) % 360
        placidus_cusps = [((c - ayan_kp_cusp) % 360) for c in cuss_plac_trop[:12]]
        return placidus_cusps, asc_deg_sidereal_plac, mc_deg_sidereal_plac

    if engine == "legacy_fallback":
        sid_mode = getattr(swe, "SIDM_KRISHNAMURTI_VP291", 45)
        return compute_legacy_sidereal_placidus(
            jd=jd,
            lat=lat,
            lon=lon,
            sid_mode=sid_mode,
            cusp_correction_arcsec=-79.0,
        )

    # swiss_vp291_sidereal
    swe.set_sid_mode(getattr(swe, "SIDM_KRISHNAMURTI_VP291", 45), 0, 0)
    cuss_plac_sid, ascmc_sid = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    asc_deg_sidereal_plac = ascmc_sid[0] % 360
    mc_deg_sidereal_plac = ascmc_sid[1] % 360
    placidus_cusps = [c % 360 for c in cuss_plac_sid[:12]]
    return placidus_cusps, asc_deg_sidereal_plac, mc_deg_sidereal_plac


def _subsub_boundary_stability_score(cusps: list[float]) -> int:
    """
    Higher score means cusps are less sensitive to +/-1 arcsecond perturbations.
    """
    score = 0
    eps = 1.0 / 3600.0
    for lon in cusps:
        ss = classify_kp_longitude(lon)["sub_sub_lord"]
        ss_l = classify_kp_longitude((lon - eps) % 360.0)["sub_sub_lord"]
        ss_r = classify_kp_longitude((lon + eps) % 360.0)["sub_sub_lord"]
        if ss_l == ss:
            score += 1
        if ss_r == ss:
            score += 1
    return score


def _subsub_clearance_score(cusps: list[float], max_arcsec: int = 600) -> float:
    """
    Average arcsecond distance to nearest sub-sub boundary.
    Higher is better (more robust).
    """
    total = 0.0
    for lon in cusps:
        base = classify_kp_longitude(lon)["sub_sub_lord"]
        left = max_arcsec
        for s in range(1, max_arcsec + 1):
            if classify_kp_longitude((lon - s / 3600.0) % 360.0)["sub_sub_lord"] != base:
                left = s
                break
        right = max_arcsec
        for s in range(1, max_arcsec + 1):
            if classify_kp_longitude((lon + s / 3600.0) % 360.0)["sub_sub_lord"] != base:
                right = s
                break
        total += float(min(left, right))
    return total / max(1, len(cusps))


def _temporal_stability_score(
    jd: float,
    lat: float,
    lon: float,
    engine: str,
) -> int:
    """
    Stability of sub-sub assignments under tiny birth-time perturbation (+/-1 sec).
    Higher is better; max 24 (12 cusps x 2 checks).
    """
    base_cusps, _, _ = _compute_placidus_cusps_by_engine(jd, lat, lon, engine)
    left_cusps, _, _ = _compute_placidus_cusps_by_engine(jd - (1.0 / 86400.0), lat, lon, engine)
    right_cusps, _, _ = _compute_placidus_cusps_by_engine(jd + (1.0 / 86400.0), lat, lon, engine)

    score = 0
    for i in range(12):
        ss = classify_kp_longitude(base_cusps[i])["sub_sub_lord"]
        if classify_kp_longitude(left_cusps[i])["sub_sub_lord"] == ss:
            score += 1
        if classify_kp_longitude(right_cusps[i])["sub_sub_lord"] == ss:
            score += 1
    return score

def calculate_bav_sav(
    planet_positions: dict[str, float],
    asc_sign_id: int,
) -> tuple[dict[str, dict[int, int]], dict[int, int]]:
    """Full Parashara Bhinna Ashtakavarga (BAV) + Sarva Ashtakavarga (SAV).

    Returns
    -------
    bav_matrix : {planet_name: {sign_index_0_11: bindu_count}}
        Bhinna (individual) scores for each of the 7 planets across 12 signs.
    sav_scores : {sign_index_0_11: total_bindu}
        Sarva (aggregate) sum of all 7 BAV rows.  Standard total = 337.
    """
    BAV_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    # Map contributor names → sign index (0-based).  Lagna is the Ascendant sign.
    contributor_sign: dict[str, int] = {}
    for p_name in BAV_PLANETS:
        if p_name in planet_positions:
            contributor_sign[p_name] = int(planet_positions[p_name] / 30)
    contributor_sign["Lagna"] = asc_sign_id

    bav_matrix: dict[str, dict[int, int]] = {}
    sav_scores: dict[int, int] = {i: 0 for i in range(12)}

    for planet, contributors in BAV_TABLES.items():
        row: dict[int, int] = {i: 0 for i in range(12)}
        for contrib_name, offsets in contributors.items():
            c_sign = contributor_sign.get(contrib_name)
            if c_sign is None:
                continue  # contributor planet not available (shouldn't happen)
            for offset in offsets:
                target_sign = (c_sign + offset - 1) % 12
                row[target_sign] += 1
        bav_matrix[planet] = row
        for sign_idx in range(12):
            sav_scores[sign_idx] += row[sign_idx]

    return bav_matrix, sav_scores


def calculate_sav(planet_positions: dict[str, float], asc_sign_id: int = 0) -> dict[int, int]:
    """Backward-compatible wrapper returning only SAV totals per sign."""
    _, sav = calculate_bav_sav(planet_positions, asc_sign_id)
    return sav

def get_varga_sign(lon, division):
    sign_idx = int(lon / 30)
    deg_in_sign = lon % 30
    if division == 1: return sign_idx
    if division == 2:
        is_odd = ((sign_idx + 1) % 2 != 0)
        first = (deg_in_sign < 15)
        return (4 if first else 3) if is_odd else (3 if first else 4)
    if division == 3: return (sign_idx + int(deg_in_sign/10)*4) % 12
    if division == 4: return (sign_idx + int(deg_in_sign/7.5)*3) % 12
    if division == 7: 
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = sign_idx if is_odd else (sign_idx + 6)
        return (start + int(deg_in_sign/(30/7))) % 12
    if division == 8:
        # D8 (Ashtamsha): 8 parts of 3°45' each
        # Movable→Aries(0), Fixed→Leo(4), Dual→Sagittarius(8) per BPHS
        mod = sign_idx % 3  # 0=Movable, 1=Fixed, 2=Dual
        start = [0, 4, 8][mod]
        return (start + int(deg_in_sign * 8 / 30)) % 12
    if division == 9:
        element = sign_idx % 4
        start = [0, 9, 6, 3][element]
        return (start + int(deg_in_sign/(30/9))) % 12
    if division == 10:
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = sign_idx if is_odd else (sign_idx + 8)
        return (start + int(deg_in_sign/3)) % 12
    if division == 12: return (sign_idx + int(deg_in_sign/2.5)) % 12
    if division == 16:
        mod = (sign_idx + 1) % 3
        start = [8, 0, 4][mod]
        return (start + int(deg_in_sign * 16 / 30)) % 12
    if division == 20:
        mod = (sign_idx + 1) % 3
        start = [4, 0, 8][mod]
        return (start + int(deg_in_sign/1.5)) % 12
    if division == 24:
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = 4 if is_odd else 3
        return (start + int(deg_in_sign/1.25)) % 12
    if division == 27:
        element = sign_idx % 4
        start = element * 3
        return (start + int(deg_in_sign/(30/27))) % 12
    if division == 30:
        is_odd = ((sign_idx + 1) % 2 != 0)
        d = deg_in_sign
        if is_odd:
            return 0 if d<=5 else (10 if d<=10 else (8 if d<=18 else (2 if d<=25 else 6)))
        else:
            return 1 if d<=5 else (5 if d<=12 else (11 if d<=20 else (9 if d<=25 else 7)))
    if division == 40:
        is_odd = ((sign_idx + 1) % 2 != 0)
        start = 0 if is_odd else 6
        return (start + int(deg_in_sign * 40 / 30)) % 12
    if division == 45:
        mod = (sign_idx + 1) % 3
        start = [8, 0, 4][mod]
        return (start + int(deg_in_sign * 45 / 30)) % 12
    if division == 60: 
        # D60 (Shashtiamsa): Parashara method - Sign + Part
        # Note: Some traditions use "Aries + Part" instead of "Sign + Part"
        # This implementation uses "Sign + Part" method
        return (sign_idx + int(deg_in_sign/0.5)) % 12
    return sign_idx

def calculate_upagrahas(sunrise_jd, sunset_jd, is_day_birth, weekday_idx, birth_jd, lat, lon):
    if is_day_birth:
        duration = sunset_jd - sunrise_jd
        base_time = sunrise_jd
    else:
        duration = (sunrise_jd + 1.0) - sunset_jd if birth_jd > sunset_jd else sunrise_jd - (sunset_jd - 1.0) 
        base_time = sunset_jd

    part_len = duration / 8.0
    vedic_day = (weekday_idx + 1) % 7 
    
    if is_day_birth:
        segments = {0:7, 1:6, 2:5, 3:4, 4:3, 5:2, 6:1}
    else:
        segments = {0:3, 1:2, 2:1, 3:7, 4:6, 5:5, 6:4}
        
    saturn_part = segments[vedic_day]
    
    gulika_start_jd = base_time + ((saturn_part - 1) * part_len)
    mandi_start_jd = gulika_start_jd + (part_len / 2)
    
    # Swiss Ephemeris returns tropical Ascendants; convert to sidereal
    res_g, _ = swe.houses(gulika_start_jd, lat, lon, b'P')
    ayanamsa_g = swe.get_ayanamsa_ut(gulika_start_jd)
    gulika_lon = (res_g[0] - ayanamsa_g) % 360
    
    res_m, _ = swe.houses(mandi_start_jd, lat, lon, b'P')
    ayanamsa_m = swe.get_ayanamsa_ut(mandi_start_jd)
    mandi_lon = (res_m[0] - ayanamsa_m) % 360
    
    return gulika_lon, mandi_lon


# ==========================================
# 2A. HIT THEORY HELPERS (NO CALC IN LLM)
# ==========================================

def angle_diff_deg(a, b):
    """Smallest absolute angular distance 0-180."""
    diff = abs(a - b) % 360
    return diff if diff <= 180 else 360 - diff

def get_baladi_avastha(lon):
    """Return (avastha_label, strength_factor) per Baladi rules.
    
    Odd Signs (Aries, Gemini, Leo, Libra, Sagittarius, Aquarius): 
    Bala → Kumara → Yuva → Vriddha → Mrita (ascending order)
    
    Even Signs (Taurus, Cancer, Virgo, Scorpio, Capricorn, Pisces):
    Mrita → Vriddha → Yuva → Kumara → Bala (reversed order)
    """
    sign_idx = int(lon / 30)
    deg_in_sign = lon % 30
    is_odd = ((sign_idx + 1) % 2 != 0)  # Aries=0 (odd), Taurus=1 (even)
    band = int(deg_in_sign / 6)  # 0..4 (0-6°, 6-12°, 12-18°, 18-24°, 24-30°)
    
    if is_odd:
        # Odd Signs: Bala → Kumara → Yuva → Vriddha → Mrita
        if band == 0:  # 0-6°
            return ("Bala", 0.25)
        elif band == 1:  # 6-12°
            return ("Kumara", 0.5)
        elif band == 2:  # 12-18°
            return ("Yuva", 1.0)
        elif band == 3:  # 18-24°
            return ("Vriddha", 0.1)
        else:  # band == 4, 24-30°
            return ("Mrita", 0.0)
    else:
        # Even Signs: Mrita → Vriddha → Yuva → Kumara → Bala (reversed)
        if band == 0:  # 0-6°
            return ("Mrita", 0.0)
        elif band == 1:  # 6-12°
            return ("Vriddha", 0.1)
        elif band == 2:  # 12-18°
            return ("Yuva", 1.0)
        elif band == 3:  # 18-24°
            return ("Kumara", 0.5)
        else:  # band == 4, 24-30°
            return ("Bala", 0.25)

def calculate_panchang(sun_lon, moon_lon):
    """Calculate Tithi, Yoga, and Karana (Panchang - Five Limbs of Time)."""
    # Tithi: Angular distance between Sun and Moon / 12° (1-30, not capped at 15)
    moon_sun_diff = (moon_lon - sun_lon) % 360
    tithi_num = int(moon_sun_diff / 12.0) + 1
    if tithi_num > 30:
        tithi_num = 30
    
    # Determine Paksha (lunar fortnight) and get correct Tithi name
    if tithi_num <= 15:
        # Shukla Paksha (waxing moon)
        paksha = "Shukla"
        tithi_index = tithi_num - 1
    else:
        # Krishna Paksha (waning moon)
        paksha = "Krishna"
        tithi_index = (tithi_num - 16) % 15  # Maps 16->0, 17->1, ... 30->14
    tithi_name = f"{paksha} {TITHI_NAMES[tithi_index]}"
    
    # Yoga: (Sun Longitude + Moon Longitude) / 13°20' (13.3333°)
    yoga_sum = (sun_lon + moon_lon) % 360
    yoga_num = int(yoga_sum / 13.333333) + 1
    if yoga_num > 27:
        yoga_num = 27
    yoga_name = YOGA_NAMES[yoga_num - 1]
    
    # Karana: Each Tithi has 2 Karanas (first half and second half)
    # 60 Karanas in a lunar month, 11 names cycling (first 4 are fixed, last 7 repeat)
    degree_in_tithi = moon_sun_diff % 12.0
    is_first_half = degree_in_tithi < 6.0
    
    # Calculate which Karana (0-59) we're in
    karana_absolute = (tithi_num - 1) * 2 + (0 if is_first_half else 1)
    
    # Map to Karana name (11 names, but first 4 are special/fixed for specific positions)
    # Simplified: cycle through the 11 names
    karana_index = karana_absolute % 11
    karana_num = karana_index + 1
    karana_name = KARANA_NAMES[karana_index]
    karana_half = "1st half" if is_first_half else "2nd half"
    
    return {
        "tithi": tithi_num,
        "tithi_name": tithi_name,
        "paksha": paksha,
        "yoga": yoga_num,
        "yoga_name": yoga_name,
        "karana": karana_num,
        "karana_name": f"{karana_name} ({karana_half})",
    }

def calculate_sunrise_trigonometric(jd, lat, lon):
    """Calculate sunrise/sunset using trigonometric method (declination, hour angle) - Ganita-Shastri precision."""
    # Get Sun's position (tropical coordinates)
    sun_res = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)
    sun_lon_tropical = sun_res[0][0]
    sun_lat = sun_res[0][1]
    
    # Convert ecliptic longitude to right ascension and declination
    # Simplified: use obliquity of ecliptic (~23.44°) for conversion
    obliquity = 23.4392911  # Approximate obliquity
    sun_lon_rad = math.radians(sun_lon_tropical)
    sun_lat_rad = math.radians(sun_lat)
    obl_rad = math.radians(obliquity)
    
    # Convert ecliptic to equatorial coordinates
    sin_dec = math.sin(sun_lat_rad) * math.cos(obl_rad) + math.cos(sun_lat_rad) * math.sin(obl_rad) * math.sin(sun_lon_rad)
    declination_deg = math.degrees(math.asin(sin_dec))
    
    # Calculate half-day arc: cos(H) = -tan(lat) * tan(decl)
    lat_rad = math.radians(lat)
    decl_rad = math.radians(declination_deg)
    
    # Check if sun rises/sets (polar day/night)
    cos_h = -math.tan(lat_rad) * math.tan(decl_rad)
    if abs(cos_h) > 1.0:
        # Polar day or night
        if cos_h > 1.0:
            # Polar night - no sunrise
            return None, None
        else:
            # Polar day - sun always up
            return jd - 0.5, jd + 0.5
    
    hour_angle_rad = math.acos(cos_h)
    hour_angle_hours = math.degrees(hour_angle_rad) / 15.0
    
    # Equation of Time (EoT) - more accurate approximation
    # EoT ≈ 4 * (L - RA) where L is mean longitude, RA is right ascension
    # Simplified: EoT ≈ 9.87 * sin(2B) - 7.53 * cos(B) - 1.5 * sin(B)
    # where B = 360 * (N - 81) / 365, N = day of year
    dt_tuple = swe.revjul(jd)
    year = int(dt_tuple[0])
    month = int(dt_tuple[1])
    day = int(dt_tuple[2])
    # Approximate day of year
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day_of_year = sum(days_in_month[:month-1]) + day
    B = 360.0 * (day_of_year - 81) / 365.0
    B_rad = math.radians(B)
    eq_time_minutes = 9.87 * math.sin(2 * B_rad) - 7.53 * math.cos(B_rad) - 1.5 * math.sin(B_rad)
    eq_time_hours = eq_time_minutes / 60.0
    
    # Local Mean Time of Sunrise (LMT)
    sunrise_lmt = 12.0 - hour_angle_hours - eq_time_hours
    sunset_lmt = 12.0 + hour_angle_hours - eq_time_hours
    
    # Apply longitude correction: LMT to Local Apparent Time
    # Each 15° of longitude = 1 hour difference from central meridian
    lon_correction_hours = lon / 15.0
    
    # Sunrise/Sunset in terms of hours from midnight (UT)
    # LMT is at the location, we need to convert to UT by subtracting longitude offset
    sunrise_ut = sunrise_lmt - lon_correction_hours
    sunset_ut = sunset_lmt - lon_correction_hours
    
    # Get the date at noon UT from the input JD
    dt_tuple = swe.revjul(jd)
    year_jd = int(dt_tuple[0])
    month_jd = int(dt_tuple[1])
    day_jd = int(dt_tuple[2])
    
    # Calculate JD at midnight UT for this date
    jd_midnight = swe.julday(year_jd, month_jd, day_jd, 0.0)
    
    # Calculate sunrise/sunset JD
    sunrise_jd = jd_midnight + (sunrise_ut / 24.0)
    sunset_jd = jd_midnight + (sunset_ut / 24.0)
    
    # Apply refraction correction (34 arc minutes) and solar disc (16 arc minutes)
    # Total correction: ~50 arc minutes = ~2 minutes of time
    correction_days = 2.0 / (24.0 * 60.0)
    sunrise_jd -= correction_days
    sunset_jd += correction_days
    
    return sunrise_jd, sunset_jd

def calculate_sripati_bhava_cusps(mc_lon, asc_lon):
    """Calculate Bhava Chalit cusps using the equal-house method.
    
    Standard Bhava Chalit (as used in most Jyotish software):
    - Lagna (Ascendant) degree = midpoint (Bhava Madhya) of House 1
    - Each house spans exactly 30 degrees
    - House START boundary = ASC - 15° + (house_index * 30°)
    
    Returns 12 cusps representing the START boundary of each house.
    Planet is in House i+1 if between cusps[i] and cusps[i+1].
    mc_lon is accepted for API compatibility but not used.
    """
    cusps = [0.0] * 12
    for i in range(12):
        # Each cusp is the START of house (i+1)
        # H1 starts at ASC - 15°, H2 at ASC + 15°, H3 at ASC + 45°, etc.
        cusps[i] = (asc_lon - 15.0 + i * 30.0) % 360
    return cusps

def drishti_kona(a, b):
    """Drishti Kona logic - shortest angular distance."""
    raw = abs(a - b) % 360
    return raw if raw <= 180 else 360 - raw

def get_house_from_lagna(lon_deg, asc_sign_id):
    sign_idx = int(lon_deg / 30)
    return (sign_idx - asc_sign_id + 12) % 12 + 1

def nak_pada(lon):
    _, nak_idx, pada = get_nakshatra(lon)
    return nak_idx, pada

def is_same_pada(lon_a, lon_b):
    nak_a, pada_a = nak_pada(lon_a)
    nak_b, pada_b = nak_pada(lon_b)
    return nak_a == nak_b and pada_a == pada_b

def detect_hit_strength(transit_planet, lon_t, lon_n):
    """Detect hit strength including Vedic special aspects and conjunctions."""
    diff = angle_diff_deg(lon_t, lon_n)
    raw_diff = abs(lon_t - lon_n) % 360
    
    # Conjunction (within 3 degrees) - applies to all planets
    if diff <= 3:
        if is_same_pada(lon_t, lon_n):
            return "strong", diff
        return "medium", diff
    
    # Vedic Special Aspects (planet-specific)
    if transit_planet == "Mars":
        # Mars: 4th house (~90°) and 8th house (~210°) aspects
        if abs(raw_diff - 90) <= 3 or abs(raw_diff - 270) <= 3:
            return "strong", diff
        if abs(raw_diff - 210) <= 3 or abs(raw_diff - 150) <= 3:
            return "strong", diff
    
    elif transit_planet == "Saturn":
        # Saturn: 3rd house (~60°) and 10th house (~270°) aspects
        if abs(raw_diff - 60) <= 3 or abs(raw_diff - 300) <= 3:
            return "strong", diff
        if abs(raw_diff - 270) <= 3 or abs(raw_diff - 90) <= 3:
            return "strong", diff
    
    elif transit_planet == "Jupiter":
        # Jupiter: 5th house (~120°) and 9th house (~240°) aspects (Trines)
        if abs(raw_diff - 120) <= 3 or abs(raw_diff - 240) <= 3:
            return "strong", diff
    
    # Opposition (180° ± 3°) - applies to all planets
    if abs(raw_diff - 180) <= 3 or abs(raw_diff - 180) >= 357:
        return "strong", diff
    
    # Trine (120° or 240° ± 3°) - for planets without special aspects
    if transit_planet not in ["Mars", "Saturn", "Jupiter"]:
        if abs(raw_diff - 120) <= 3 or abs(raw_diff - 240) <= 3:
            return "strong", diff
    
    # Same nakshatra but different pada (weaker hit)
    nak_t, pada_t = nak_pada(lon_t)
    nak_n, pada_n = nak_pada(lon_n)
    if nak_t == nak_n and pada_t != pada_n:
        return "weak", diff
    
    return None, diff

def compute_argala_vedha(transit_planet, hit_house_from_target, transit_positions, target_house, moon_sign_id):
    """Return argala_type, vedha_type using proper Vedha pairs logic.
    
    CRITICAL: Vedha must always be calculated from Natal Moon (Gochara reference),
    not from Lagna or target house.
    """
    # Argala houses: 2nd, 4th, 11th from target
    if hit_house_from_target in {2, 4, 11}:
        argala = "auspicious"
    else:
        argala = "none"

    # Check Vedha: Vedha is always calculated from Natal Moon (Gochara reference)
    vedha = "none"
    if transit_planet in VEDHA_PAIRS:
        vedha_map = VEDHA_PAIRS[transit_planet]
        # Use hit_house_from_target (which should be from Moon) for Vedha calculation
        if hit_house_from_target in vedha_map:
            vedha_house = vedha_map[hit_house_from_target]
            # Check if any other planet occupies the vedha house (from Moon reference)
            for other_planet, other_lon in transit_positions.items():
                if other_planet == transit_planet:
                    continue
                other_sign = int(other_lon / 30)
                # CRITICAL: Calculate house from Moon, not Lagna
                other_house_from_moon = (other_sign - moon_sign_id + 12) % 12 + 1
                if other_house_from_moon == vedha_house:
                    # Sun-Saturn exception: no Vedha between Sun and Saturn
                    if not (transit_planet == "Sun" and other_planet == "Saturn") and \
                       not (transit_planet == "Saturn" and other_planet == "Sun"):
                        vedha = "malefic_vedha"
                    break
    
    return argala, vedha

def map_house_to_domain(house):
    domains = []
    for name, houses in DOMAIN_MAP.items():
        if house in houses:
            domains.append(name)
    return domains or ["general"]

def _jd_to_datetime(jd_val):
    """Convert Julian Day to datetime with full hour/minute/second precision."""
    y, m, d, h = swe.revjul(jd_val)
    hour = int(h)
    minute = int((h - hour) * 60)
    second = int(((h - hour) * 60 - minute) * 60)
    # Clamp to valid ranges (swe.revjul can return e.g. 24:00 on day boundary)
    if hour >= 24:
        dt = datetime.datetime(int(y), int(m), int(d), 0, 0, 0) + datetime.timedelta(hours=hour, minutes=minute, seconds=second)
        return dt
    return datetime.datetime(int(y), int(m), int(d), hour, minute, second)


def motion_marker_for_display(planet_name, planet_payload):
    """Determine the accurate retrograde marker string for table displays."""
    if planet_name in ("Sun", "Moon"):
        return ""
    if planet_name in ("Rahu", "Ketu"):
        return " (R)" if planet_payload.get("is_backward_motion") else ""
    return " (R)" if planet_payload.get("is_retrograde_by_speed") else ""


def generate_vimshottari_timeline(moon_lon, birth_dt_local, max_years=80):
    """Generator: Three-level Mahadasha → Antardasha → Pratyantar timeline.

    Uses datetime/timedelta arithmetic strictly from birth_dt_local.
    """
    from datetime import timedelta
    import math
    
    NAKSHATRA_SPAN = Fraction(40, 3)
    moon_lon_frac = Fraction(str(Decimal(str(moon_lon))))
    nak_index = math.floor(moon_lon_frac / NAKSHATRA_SPAN)
    offset_in_nak = moon_lon_frac - (nak_index * NAKSHATRA_SPAN)
    
    elapsed_fraction = offset_in_nak / NAKSHATRA_SPAN
    remaining_fraction = 1 - elapsed_fraction
    
    sequence_order = [p[0] for p in VIMSHOTTARI_SEQUENCE]
    dasha_yrs = dict(VIMSHOTTARI_SEQUENCE)
    
    birth_md_lord = NAKSHATRA_RULERS[nak_index]
    dasha_lord_idx = sequence_order.index(birth_md_lord)
    
    birth_md_total_days = dasha_yrs[birth_md_lord] * DASHA_YEAR_DAYS
    birth_md_elapsed_days = float(birth_md_total_days) * float(elapsed_fraction)
    
    virtual_md_start_dt = birth_dt_local - timedelta(days=birth_md_elapsed_days)
    end_limit_dt = birth_dt_local + timedelta(days=max_years * DASHA_YEAR_DAYS)

    md_idx = dasha_lord_idx
    md_start_dt = virtual_md_start_dt
    md_safety = 0

    while md_start_dt < end_limit_dt and md_safety < 20:
        md_safety += 1
        md_lord = sequence_order[md_idx]
        md_total = dasha_yrs[md_lord]
        md_dur_days = md_total * DASHA_YEAR_DAYS
        md_end_dt = md_start_dt + timedelta(days=md_dur_days)

        if md_end_dt <= birth_dt_local:
            md_start_dt = md_end_dt
            md_idx = (md_idx + 1) % 9
            continue

        ad_idx = md_idx
        ad_start_dt = md_start_dt

        for _ad in range(9):
            ad_lord = sequence_order[ad_idx]
            ad_total = dasha_yrs[ad_lord]
            ad_dur_years = (md_total * ad_total) / 120.0
            ad_dur_days = ad_dur_years * DASHA_YEAR_DAYS
            ad_end_dt = ad_start_dt + timedelta(days=ad_dur_days)

            if ad_end_dt <= birth_dt_local:
                ad_start_dt = ad_end_dt
                ad_idx = (ad_idx + 1) % 9
                continue
            if ad_start_dt >= end_limit_dt:
                break

            pd_idx = ad_idx
            pd_start_dt = ad_start_dt

            for _pd in range(9):
                pd_lord = sequence_order[pd_idx]
                pd_total = dasha_yrs[pd_lord]
                pd_dur_years = (ad_dur_years * pd_total) / 120.0
                pd_dur_days = pd_dur_years * DASHA_YEAR_DAYS
                pd_end_dt = pd_start_dt + timedelta(days=pd_dur_days)

                if pd_end_dt <= birth_dt_local:
                    pd_start_dt = pd_end_dt
                    pd_idx = (pd_idx + 1) % 9
                    continue
                if pd_start_dt >= end_limit_dt:
                    break

                disp_start_dt = max(pd_start_dt, birth_dt_local)
                disp_end_dt   = min(pd_end_dt, end_limit_dt)
                disp_dur_days = (disp_end_dt - disp_start_dt).total_seconds() / 86400.0

                yield {
                    "level": 3,
                    "mahadasha": md_lord,
                    "antardasha": ad_lord,
                    "pratyantar": pd_lord,
                    "start_solar": disp_start_dt,
                    "end_solar": disp_end_dt,
                    "start_savana": disp_start_dt,
                    "end_savana": disp_end_dt,
                    "duration_solar_days": disp_dur_days,
                    "duration_savana_days": disp_dur_days * (SAVANA_YEAR / DASHA_YEAR_DAYS),
                    "duration_years": pd_dur_years,
                }

                pd_start_dt = pd_end_dt
                pd_idx = (pd_idx + 1) % 9

            ad_start_dt = ad_end_dt
            ad_idx = (ad_idx + 1) % 9

        md_start_dt = md_end_dt
        md_idx = (md_idx + 1) % 9

def calculate_vimshottari_dasha(moon_lon, birth_jd, current_jd):
    """Calculate current Mahadasha and Antardasha using the virtual-start method.

    This mirrors the logic in ``generate_vimshottari_timeline`` so that both
    functions always agree on the current MD / AD for a given Moon longitude.
    """
    # Exact fractional calculation for Dasha Balance
    lon_arcsec = Fraction(str(Decimal(str(moon_lon)) * Decimal("3600")))
    lon_arcmin = lon_arcsec / Fraction(60)
    nak_len_arcmin = Fraction(800, 1)
    
    nak_idx_0 = int(lon_arcmin / nak_len_arcmin) % 27
    dasha_lord_idx = nak_idx_0 % 9

    sequence_order = [p[0] for p in VIMSHOTTARI_SEQUENCE]
    dasha_yrs = dict(VIMSHOTTARI_SEQUENCE)
    total_cycle = 120.0  # sum of all dasha years

    pos_in_nak_arcmin = lon_arcmin - (nak_idx_0 * nak_len_arcmin)
    
    birth_md_lord = sequence_order[dasha_lord_idx]
    
    elapsed_fraction = float(pos_in_nak_arcmin / nak_len_arcmin)
    remaining_fraction = float((nak_len_arcmin - pos_in_nak_arcmin) / nak_len_arcmin)
    
    birth_md_total_days = dasha_yrs[birth_md_lord] * DASHA_YEAR_DAYS
    birth_md_elapsed_days = birth_md_total_days * elapsed_fraction
    birth_md_balance_days = birth_md_total_days * remaining_fraction
    
    virtual_md_start_jd = birth_jd - birth_md_elapsed_days

    # Walk the Mahadasha sequence to find the MD that contains current_jd
    md_idx = dasha_lord_idx
    md_start_jd = virtual_md_start_jd

    for _ in range(20):  # safety
        md_lord = sequence_order[md_idx]
        md_total = dasha_yrs[md_lord]
        md_dur_days = md_total * DASHA_YEAR_DAYS
        md_end_jd = md_start_jd + md_dur_days

        if current_jd < md_end_jd:
            # Found the current Mahadasha
            md_years_left = (md_end_jd - current_jd) / DASHA_YEAR_DAYS
            break
        md_start_jd = md_end_jd
        md_idx = (md_idx + 1) % 9
    else:
        # Fallback (should not happen within 120 years)
        md_lord = sequence_order[md_idx]
        md_total = dasha_yrs[md_lord]
        md_years_left = 0.0

    # Walk the Antardasha sequence within that MD
    ad_idx = md_idx
    ad_start_jd = md_start_jd

    current_ad_lord = sequence_order[ad_idx]
    ad_dur_years = (md_total * dasha_yrs[current_ad_lord]) / total_cycle
    ad_years_left = 0.0

    for _ in range(9):
        ad_lord_c = sequence_order[ad_idx]
        ad_total_c = dasha_yrs[ad_lord_c]
        ad_dur_yrs = (md_total * ad_total_c) / total_cycle
        ad_dur_d = ad_dur_yrs * DASHA_YEAR_DAYS
        ad_end_jd = ad_start_jd + ad_dur_d

        if current_jd < ad_end_jd:
            current_ad_lord = ad_lord_c
            ad_dur_years = ad_dur_yrs
            ad_years_left = (ad_end_jd - current_jd) / DASHA_YEAR_DAYS
            break
        ad_start_jd = ad_end_jd
        ad_idx = (ad_idx + 1) % 9

    return {
        "mahadasha_lord": md_lord,
        "mahadasha_years_remaining": round(md_years_left, 2),
        "antardasha_lord": current_ad_lord,
        "antardasha_years_remaining": round(ad_years_left, 2),
        "mahadasha_years_total": md_total,
        "antardasha_years_total": round(ad_dur_years, 2),
    }

def detect_eclipse_for_month(jd_mid):
    """Detect eclipse by finding actual New Moon (Amavasya) and Full Moon (Purnima) dates."""
    # Tropical topocentric — only angular differences matter for eclipses,
    # so sidereal conversion is unnecessary here.
    eclipse_calc_flag = swe.FLG_TOPOCTR | swe.FLG_SWIEPH
    
    # Get month start and end - use swe.revjul to convert JD to date
    dt_tuple = swe.revjul(jd_mid)
    year = int(dt_tuple[0])
    month = int(dt_tuple[1])
    day = int(dt_tuple[2])
    
    # Find actual New Moon (Sun-Moon conjunction) and Full Moon (Sun-Moon opposition)
    # Search within the month ± 2 days for accuracy
    month_start_jd = swe.julday(year, month, 1, 12.0)
    if month == 12:
        month_end_jd = swe.julday(year + 1, 1, 1, 12.0)
    else:
        month_end_jd = swe.julday(year, month + 1, 1, 12.0)
    
    # Search for New Moon (conjunction) - check every 0.5 days
    new_moon_jd = None
    min_conjunction_diff = 360.0
    check_jd = month_start_jd - 2.0  # Start 2 days before month
    while check_jd < month_end_jd + 2.0:
        sun_res = swe.calc_ut(check_jd, swe.SUN, eclipse_calc_flag)
        moon_res = swe.calc_ut(check_jd, swe.MOON, eclipse_calc_flag)
        sun_lon = sun_res[0][0]
        moon_lon = moon_res[0][0]
        diff = angle_diff_deg(sun_lon, moon_lon)
        if diff < min_conjunction_diff:
            min_conjunction_diff = diff
            new_moon_jd = check_jd
        check_jd += 0.5
    
    # Search for Full Moon (opposition) - check every 0.5 days
    full_moon_jd = None
    min_opposition_diff = 360.0
    check_jd = month_start_jd - 2.0
    while check_jd < month_end_jd + 2.0:
        sun_res = swe.calc_ut(check_jd, swe.SUN, eclipse_calc_flag)
        moon_res = swe.calc_ut(check_jd, swe.MOON, eclipse_calc_flag)
        sun_lon = sun_res[0][0]
        moon_lon = moon_res[0][0]
        diff = angle_diff_deg(sun_lon, moon_lon)
        # Opposition is ~180 degrees
        if abs(diff - 180) < abs(min_opposition_diff - 180):
            min_opposition_diff = diff
            full_moon_jd = check_jd
        check_jd += 0.5
    
    eclipse_type = None
    eclipse_jd = None
    
    # Check both New Moon and Full Moon for eclipses
    for check_jd in [new_moon_jd, full_moon_jd]:
        if check_jd is None:
            continue
        sun_res = swe.calc_ut(check_jd, swe.SUN, eclipse_calc_flag)
        moon_res = swe.calc_ut(check_jd, swe.MOON, eclipse_calc_flag)
        rahu_res = swe.calc_ut(check_jd, swe.MEAN_NODE, eclipse_calc_flag)
        
        sun_lon = sun_res[0][0]
        moon_lon = moon_res[0][0]
        rahu_lon = rahu_res[0][0]
        ketu_lon = (rahu_lon + 180) % 360
        
        sun_rahu_diff = angle_diff_deg(sun_lon, rahu_lon)
        sun_ketu_diff = angle_diff_deg(sun_lon, ketu_lon)
        moon_rahu_diff = angle_diff_deg(moon_lon, rahu_lon)
        moon_ketu_diff = angle_diff_deg(moon_lon, ketu_lon)
        moon_sun_diff = angle_diff_deg(moon_lon, sun_lon)
        
        # Solar eclipse: Sun conjunct Rahu/Ketu (within 15 degrees) - New Moon
        if sun_rahu_diff <= 15 or sun_ketu_diff <= 15:
            eclipse_type = "Solar Eclipse"
            eclipse_jd = check_jd
            break
        
        # Lunar eclipse: Moon opposite Sun and conjunct Rahu/Ketu (within 15 degrees) - Full Moon
        if (moon_sun_diff >= 165 and moon_sun_diff <= 195) and (moon_rahu_diff <= 15 or moon_ketu_diff <= 15):
            eclipse_type = "Lunar Eclipse"
            eclipse_jd = check_jd
            break
    
    return eclipse_type, eclipse_jd

def build_monthly_transits(base_date):
    """Return list of (year, month, jd_mid) for next 12 months."""
    months = []
    year = base_date.year
    month = base_date.month
    for i in range(12):
        m = ((month - 1 + i) % 12) + 1
        y = year + ((month - 1 + i) // 12)
        mid_day = 15
        jd_mid = swe.julday(y, m, mid_day, 0.0)
        months.append((y, m, jd_mid))
    return months

def compute_transit_positions(jd_value):
    """Return sidereal positions and retrograde status (topocentric + KP ayanamsa)."""
    transit_calc_flag = swe.FLG_TOPOCTR | swe.FLG_SWIEPH | swe.FLG_SPEED  # topocentric + speed for retrograde detection
    ayan = get_kp_ayanamsa_ut(jd_value)             # Swiss SIDM_KRISHNAMURTI
    positions = {}
    retrograde_status = {}

    for p_name, p_id in PLANETS.items():
        if p_name in ["Sun", "Moon"]:
            res = swe.calc_ut(jd_value, p_id, transit_calc_flag)
            t_lon = (res[0][0] - ayan) % 360
            speed = res[0][3] if len(res[0]) > 3 else 0
            motion = "direct"
            is_backward_motion = False
            is_retrograde_by_speed = False
            kp_treat_as_retrograde = False
        elif p_name in ["Rahu", "Ketu"]:
            node_mode = "mean"
            if p_name == "Ketu":
                rahu_data = swe.calc_ut(jd_value, swe.MEAN_NODE, transit_calc_flag)
                t_lon = (rahu_data[0][0] + 180 - ayan) % 360
                speed = rahu_data[0][3] if len(rahu_data[0]) > 3 else 0
            else:
                res = swe.calc_ut(jd_value, swe.MEAN_NODE, transit_calc_flag)
                t_lon = (res[0][0] - ayan) % 360
                speed = res[0][3] if len(res[0]) > 3 else 0
            if node_mode == "mean":
                motion = "backward"
                is_backward_motion = True
                is_retrograde_by_speed = True
            else:
                motion = "backward" if speed < 0 else "direct"
                is_backward_motion = speed < 0
                is_retrograde_by_speed = speed < 0
            kp_treat_as_retrograde = False
        else:
            res = swe.calc_ut(jd_value, p_id, transit_calc_flag)
            t_lon = (res[0][0] - ayan) % 360
            speed = res[0][3] if len(res[0]) > 3 else 0
            motion = "retrograde" if speed < 0 else "direct"
            is_backward_motion = speed < 0
            is_retrograde_by_speed = speed < 0
            kp_treat_as_retrograde = speed < 0
            
        positions[p_name] = t_lon
        retrograde_status[p_name] = {
            "speed": speed,
            "motion": motion,
            "is_backward_motion": is_backward_motion,
            "is_retrograde_by_speed": is_retrograde_by_speed,
            "kp_treat_as_retrograde": kp_treat_as_retrograde
        }
    return positions, retrograde_status

def calculate_gochara_vedha(transit_positions, moon_sign_id, asc_sign_id):
    """Calculate Gochara (sign-based transit) and Vedha for all planets from Moon."""
    gochara_results = []
    
    for tp_name, t_lon in transit_positions.items():
        if tp_name == "Moon":
            continue
        
        t_sign_idx = int(t_lon / 30)
        t_house_from_moon = (t_sign_idx - moon_sign_id + 12) % 12 + 1
        t_house_from_lagna = (t_sign_idx - asc_sign_id + 12) % 12 + 1
        
        # Check if transit is in auspicious house from Moon (3, 6, 10, 11)
        is_auspicious_house = t_house_from_moon in {3, 6, 10, 11}
        
        # Check Vedha for this transit (sign-based, not degree-based)
        vedha_status = "none"
        if tp_name in VEDHA_PAIRS and is_auspicious_house:
            vedha_map = VEDHA_PAIRS[tp_name]
            if t_house_from_moon in vedha_map:
                vedha_house = vedha_map[t_house_from_moon]
                # Check if any other planet occupies the vedha house
                for other_planet, other_lon in transit_positions.items():
                    if other_planet == tp_name:
                        continue
                    # Sun-Saturn exception
                    if tp_name == "Sun" and other_planet == "Saturn":
                        continue
                    other_sign = int(other_lon / 30)
                    other_house_from_moon = (other_sign - moon_sign_id + 12) % 12 + 1
                    if other_house_from_moon == vedha_house:
                        vedha_status = "obstructed"
                        break
        
        gochara_results.append({
            "planet": tp_name,
            "transit_sign": ZODIAC_SIGNS[t_sign_idx],
            "house_from_moon": t_house_from_moon,
            "house_from_lagna": t_house_from_lagna,
            "is_auspicious": is_auspicious_house,
            "vedha_status": vedha_status,
        })
    
    return gochara_results

def count_from_house(occupied_house, aspect_number):
    return ((occupied_house + aspect_number - 2) % 12) + 1

def calculate_transit_aspects(transit_planet, t_lon, is_retrograde_by_speed, motion, asc_sign_id, moon_sign_id, placidus_cusps, sav_scores, node_aspect_mode="none"):
    """
    Returns a list of dictionaries for each aspect emitted by the transit_planet.
    Uses directional Parashari aspect arcs.
    """
    t_sign_idx = int(t_lon / 30)
    occupied_house_from_lagna = (t_sign_idx - asc_sign_id + 12) % 12 + 1
    occupied_house_from_moon = (t_sign_idx - moon_sign_id + 12) % 12 + 1
    
    occupied_kp_house = 1
    for i in range(12):
        c_start = placidus_cusps[i]
        c_end = placidus_cusps[(i + 1) % 12]
        if c_end < c_start:
            if t_lon >= c_start or t_lon < c_end:
                occupied_kp_house = i + 1
                break
        else:
            if c_start <= t_lon < c_end:
                occupied_kp_house = i + 1
                break

    aspects = []
    if transit_planet in ["Sun", "Moon", "Mercury", "Venus"]:
        aspects = [7]
    elif transit_planet == "Mars":
        aspects = [4, 7, 8]
    elif transit_planet == "Jupiter":
        aspects = [5, 7, 9]
    elif transit_planet == "Saturn":
        aspects = [3, 7, 10]
    elif transit_planet in ["Rahu", "Ketu"]:
        if node_aspect_mode == "seventh_only":
            aspects = [7]
        elif node_aspect_mode == "jupiter_style":
            aspects = [5, 7, 9]

    emitted_aspects = []
    retrograde_modifier_note = "Intensified/Modified by Retrograde motion" if is_retrograde_by_speed and transit_planet not in ["Rahu", "Ketu"] else None

    for asp in aspects:
        aspect_arc_degrees = (asp - 1) * 30.0
        aspect_point_lon = (t_lon + aspect_arc_degrees) % 360.0
        aspected_sign_idx = int(aspect_point_lon / 30)
        aspected_sign = ZODIAC_SIGNS[aspected_sign_idx]
        aspect_point_degree_in_sign = aspect_point_lon % 30.0

        aspected_house_from_lagna = count_from_house(occupied_house_from_lagna, asp)
        aspected_house_from_moon = count_from_house(occupied_house_from_moon, asp)

        aspected_kp_house = 1
        for i in range(12):
            c_start = placidus_cusps[i]
            c_end = placidus_cusps[(i + 1) % 12]
            if c_end < c_start:
                if aspect_point_lon >= c_start or aspect_point_lon < c_end:
                    aspected_kp_house = i + 1
                    break
            else:
                if c_start <= aspect_point_lon < c_end:
                    aspected_kp_house = i + 1
                    break

        sav_score = sav_scores.get(aspected_sign_idx)

        emitted_aspects.append({
            "transit_planet": transit_planet,
            "transit_sign": ZODIAC_SIGNS[t_sign_idx],
            "transit_degree": t_lon % 30.0,
            "motion": motion,
            "is_retrograde_by_speed": is_retrograde_by_speed,
            "occupied_house_from_lagna_whole_sign": occupied_house_from_lagna,
            "occupied_house_from_moon_whole_sign": occupied_house_from_moon,
            "occupied_kp_house_by_cusp": occupied_kp_house,
            "aspect_number": asp,
            "aspected_sign": aspected_sign,
            "aspect_point_longitude": aspect_point_lon,
            "aspect_point_degree_in_sign": aspect_point_degree_in_sign,
            "aspected_house_from_lagna_whole_sign": aspected_house_from_lagna,
            "aspected_house_from_moon_whole_sign": aspected_house_from_moon,
            "aspected_kp_house_by_cusp": aspected_kp_house,
            "aspect_type": "Parashari",
            "aspect_intent": "General",
            "target_planets_in_aspected_house": [],
            "target_cusps_in_aspected_house": [],
            "sav_score_of_aspected_sign": sav_score,
            "retrograde_modifier_note": retrograde_modifier_note,
        })
    return emitted_aspects


def calculate_transit_hits(transit_planet, t_lon, t_speed, t_motion, natal_targets, orb_degrees=3.0):
    """
    Pure helper to calculate exact degree proximity hits from transit_planet to natal targets.
    Uses directional Parashari aspect arcs: (aspect_number - 1) * 30.
    """
    hits = []
    aspects = [1]
    if transit_planet in ["Sun", "Moon", "Mercury", "Venus"]:
        aspects.extend([7])
    elif transit_planet == "Mars":
        aspects.extend([4, 7, 8])
    elif transit_planet == "Jupiter":
        aspects.extend([5, 7, 9])
    elif transit_planet == "Saturn":
        aspects.extend([3, 7, 10])

    station_flag = abs(t_speed) < 0.01

    for target in natal_targets:
        n_lon = target["lon"]
        
        for asp in aspects:
            aspect_arc = (asp - 1) * 30.0
            aspect_point_lon = (t_lon + aspect_arc) % 360.0
            
            raw_diff = aspect_point_lon - n_lon
            if raw_diff > 180:
                raw_diff -= 360
            elif raw_diff < -180:
                raw_diff += 360
                
            abs_diff = abs(raw_diff)
            
            if abs_diff <= orb_degrees:
                if raw_diff < 0:
                    applying = t_speed > 0
                    separating = t_speed < 0
                elif raw_diff > 0:
                    applying = t_speed < 0
                    separating = t_speed > 0
                else:
                    applying = False
                    separating = False
                
                hits.append({
                    "transit_planet": transit_planet,
                    "target_type": target["type"],
                    "target_name": target["name"],
                    "transit_longitude": t_lon,
                    "target_longitude": n_lon,
                    "aspect_angle": aspect_arc,
                    "exact_hit_longitude": (n_lon - aspect_arc) % 360.0,
                    "orb_degrees": abs_diff,
                    "transit_speed": t_speed,
                    "motion": t_motion,
                    "applying": applying,
                    "separating": separating,
                    "station_flag": station_flag
                })
    return hits

def detect_monthly_hits(month_tuple, transit_data, natal_targets, asc_sign_id, moon_sign_id, sav_scores, placidus_cusps):
    """Return hit events (degree-based triggers) and domain summary for given month."""
    y, m, jd_mid = month_tuple
    transit_positions, retrograde_status = transit_data
    hits = []
    degree_hits = []
    aspect_impacts = []
    domain_summary = {k: {"positive_hits": 0, "negative_hits": 0, "net_score": 0} for k in DOMAIN_MAP.keys()}
    
    # Check for eclipse in this month (check New Moon and Full Moon)
    eclipse_type, eclipse_jd = detect_eclipse_for_month(jd_mid)
    
    # Calculate Gochara (sign-based transit analysis) FIRST - separate from Hit Theory
    gochara_results = calculate_gochara_vedha(transit_positions, moon_sign_id, asc_sign_id)
    gochara_map = {g["planet"]: g for g in gochara_results}
    
    for tp_name, t_lon in transit_positions.items():
        # Skip Moon for monthly snapshots (moves too fast, position is misleading)
        if tp_name == "Moon":
            continue
        
        t_sign_idx = int(t_lon / 30)
        t_house = (t_sign_idx - asc_sign_id + 12) % 12 + 1
        t_house_from_moon = (t_sign_idx - moon_sign_id + 12) % 12 + 1
        t_nak, t_pada = nak_pada(t_lon)
        is_malefic = tp_name in ["Saturn", "Rahu", "Ketu", "Mars"]
        
        t_retro_dict = retrograde_status.get(tp_name, {})
        is_retrograde_by_speed = t_retro_dict.get("is_retrograde_by_speed", False)
        is_retrograde = is_retrograde_by_speed # for legacy logic below
        t_speed = t_retro_dict.get("speed", 0.0)
        t_motion = t_retro_dict.get("motion", "direct")
        
        aspect_impacts.extend(calculate_transit_aspects(tp_name, t_lon, is_retrograde_by_speed, t_motion, asc_sign_id, moon_sign_id, placidus_cusps, sav_scores))
        degree_hits.extend(calculate_transit_hits(tp_name, t_lon, t_speed, t_motion, natal_targets))
        
        # Get Gochara status for this planet
        gochara_info = gochara_map.get(tp_name, {})
        gochara_vedha = gochara_info.get("vedha_status", "none")
        
        houses_to_check = [t_house]
        if is_retrograde:
            prev_house = ((t_house - 2) % 12) + 1
            houses_to_check.append(prev_house)
        
        for target in natal_targets:
            target_house = get_house_from_lagna(target["lon"], asc_sign_id)
            target_house_from_moon = get_house_from_lagna(target["lon"], moon_sign_id)
            strength, diff = detect_hit_strength(tp_name, t_lon, target["lon"])
            
            # Skip if no hit detected (Hit Theory = degree-based trigger)
            if strength is None:
                continue
            # Skip if target natal planet is Mrit (dead)
            if target.get("baladi_status") == "Mrit":
                continue
            
            # Calculate aspect types
            raw_diff = abs(t_lon - target["lon"]) % 360
            is_conj = diff <= 3
            is_opp = abs(raw_diff - 180) <= 3 or abs(raw_diff - 180) >= 357
            is_trine = abs(raw_diff - 120) <= 3 or abs(raw_diff - 240) <= 3
            
            for effective_house in houses_to_check:
                rel_house = (effective_house - target_house + 12) % 12 + 1
                rel_house_from_moon = (t_house_from_moon - target_house_from_moon + 12) % 12 + 1
                # CRITICAL: Vedha must be calculated from Moon reference
                argala, vedha = compute_argala_vedha(tp_name, rel_house_from_moon, transit_positions, target_house_from_moon, moon_sign_id)
                
                # Use Gochara Vedha (sign-based) as primary, Hit Theory Vedha as secondary
                effective_vedha = gochara_vedha if gochara_vedha != "none" else vedha
                
                sav_at_sign = sav_scores.get(t_sign_idx, 0)
                hit_domains = map_house_to_domain(effective_house)
                
                # Check if hit occurs near eclipse
                near_eclipse = False
                if eclipse_type and eclipse_jd:
                    days_diff = abs(jd_mid - eclipse_jd)
                    if days_diff <= 7:  # Within 7 days of eclipse
                        near_eclipse = True
                
                hit_entry = {
                    "year": y,
                    "month": m,
                    "transit_planet": tp_name,
                    "transit_lon": round(t_lon, 4),
                    "transit_sign_index": t_sign_idx,
                    "transit_nakshatra_index": t_nak,
                    "transit_pada": t_pada,
                    "is_retrograde": is_retrograde,
                    "target_type": target["type"],
                    "target_name": target["name"],
                    "target_lon": round(target["lon"], 4),
                    "target_sign_index": int(target["lon"] / 30),
                    "target_house_from_lagna": target_house,
                    "target_house_from_moon": target_house_from_moon,
                    "drishti_kona_deg": round(drishti_kona(t_lon, target["lon"]), 2),
                    "degree_diff_abs": round(diff, 2),
                    "is_conjunction": is_conj,
                    "is_opposition": is_opp,
                    "is_trine": is_trine,
                    "is_same_trikona": ((t_sign_idx - int(target["lon"] / 30)) % 4 == 0),
                    "target_nakshatra_index": target["nak_idx"],
                    "target_pada": target["pada"],
                    "hit_strength": strength,
                    "argala_type": argala,
                    "vedha_type": effective_vedha,
                    "gochara_vedha": gochara_vedha,  # Sign-based vedha
                    "hit_theory_vedha": vedha,  # Degree-based vedha
                    "is_malefic": is_malefic,
                    "sav_score_at_hit_sign": sav_at_sign,
                    "is_sav_strong": sav_at_sign > 28,
                    "is_sav_weak": sav_at_sign < 25,
                    "kalapurusha_domain": KALAPURUSHA_MAP.get(effective_house, "general"),
                    "life_domains": hit_domains,
                    "near_eclipse": near_eclipse,
                    "eclipse_type": eclipse_type if near_eclipse else None,
                    "from_retro_previous_house": (effective_house != t_house),
                }
                hits.append(hit_entry)
                # domain scoring
                for dom in hit_domains:
                    if dom not in domain_summary:
                        domain_summary[dom] = {"positive_hits": 0, "negative_hits": 0, "net_score": 0}
                    # Use Gochara Vedha for scoring (sign-based obstruction)
                    vedha_for_scoring = gochara_vedha if gochara_vedha != "none" else effective_vedha
                    if is_malefic or vedha_for_scoring == "obstructed" or vedha_for_scoring == "malefic_vedha" or sav_at_sign < 25 or target["name"] in ["64th_navamsa", "22nd_drekkana"] or near_eclipse or (is_retrograde and is_malefic):
                        domain_summary[dom]["negative_hits"] += 1
                    else:
                        domain_summary[dom]["positive_hits"] += 1
                    domain_summary[dom]["net_score"] = domain_summary[dom]["positive_hits"] - domain_summary[dom]["negative_hits"]
    
    return hits, domain_summary, eclipse_type, gochara_results, degree_hits, aspect_impacts


def calculate_bnn_module(planet_positions, planet_sign_index, natal_retrograde, birth_datetime):
    """
    Calculate Bhrigu Nandi Nadi (BNN) specific data:
    - Directional Trikona (Nadi Grouping)
    - Orbital Order (Degree-based influence)
    - Retrograde Phantom Positions
    - Friend/Enemy Matrix (Deva vs Asura)
    - BNN Transit Cycles (Saturn and Jupiter)
    - Special Yogas (Parivartana)
    """
    # Directional mapping: East/South/West/North based on signs
    # East: Aries(0), Leo(4), Sagittarius(8) - Fire signs
    # South: Taurus(1), Virgo(5), Capricorn(9) - Earth signs
    # West: Gemini(2), Libra(6), Aquarius(10) - Air signs
    # North: Cancer(3), Scorpio(7), Pisces(11) - Water signs
    DIRECTIONAL_MAP = {
        0: "EAST", 4: "EAST", 8: "EAST",  # Fire signs
        1: "SOUTH", 5: "SOUTH", 9: "SOUTH",  # Earth signs
        2: "WEST", 6: "WEST", 10: "WEST",  # Air signs
        3: "NORTH", 7: "NORTH", 11: "NORTH"  # Water signs
    }
    
    # BNN Friend/Enemy Groups (Static, not Tatkalik Maitri)
    DEVA_GROUP = ["Jupiter", "Sun", "Moon", "Mars", "Ketu"]
    ASURA_GROUP = ["Saturn", "Venus", "Mercury", "Rahu"]
    # Exception: Mercury is often neutral/friendly to Jupiter in BNN
    
    # 1. Directional Groups
    directional_groups = {
        "EAST": [],
        "SOUTH": [],
        "WEST": [],
        "NORTH": []
    }
    
    for p_name, lon in planet_positions.items():
        sign_idx = planet_sign_index.get(p_name, int(lon / 30))
        direction = DIRECTIONAL_MAP.get(sign_idx, "UNKNOWN")
        deg_in_sign = lon % 30
        d, m = decimal_to_dms(deg_in_sign)
        sign_name = ZODIAC_SIGNS[sign_idx]
        retro_str = " (R)" if natal_retrograde.get(p_name, False) else ""
        directional_groups[direction].append(f"{p_name} ({sign_name} {d}°{m}'){retro_str}")
    
    # 2. Orbital Order (Sorted by degree within each sign)
    effective_order = {}
    sign_occupants = {i: [] for i in range(12)}
    
    for p_name, lon in planet_positions.items():
        sign_idx = planet_sign_index.get(p_name, int(lon / 30))
        deg_in_sign = lon % 30
        sign_occupants[sign_idx].append({
            "planet": p_name,
            "degree": deg_in_sign,
            "longitude": lon,
            "retrograde": natal_retrograde.get(p_name, False)
        })
    
    # Sort by degree within each sign
    for sign_idx in range(12):
        sign_occupants[sign_idx].sort(key=lambda x: x["degree"])
        sign_name = ZODIAC_SIGNS[sign_idx]
        if sign_occupants[sign_idx]:
            effective_order[f"{sign_name}_SEQUENCE"] = [
                f"{p['planet']} ({p['degree']:.2f}°)" + (" R" if p['retrograde'] else "")
                for p in sign_occupants[sign_idx]
            ]
    
    # Also create directional sequences (sorted by degree within direction)
    directional_sequences = {
        "EAST": [],
        "SOUTH": [],
        "WEST": [],
        "NORTH": []
    }
    
    for sign_idx in range(12):
        direction = DIRECTIONAL_MAP.get(sign_idx, "UNKNOWN")
        for p_data in sign_occupants[sign_idx]:
            p_name = p_data["planet"]
            deg_in_sign = p_data["degree"]
            sign_name = ZODIAC_SIGNS[sign_idx]
            retro_str = " R" if p_data["retrograde"] else ""
            directional_sequences[direction].append({
                "planet": p_name,
                "sign": sign_name,
                "degree": deg_in_sign,
                "longitude": p_data["longitude"],
                "retrograde": p_data["retrograde"]
            })
    
    # Sort each directional group by longitude
    for direction in directional_sequences:
        directional_sequences[direction].sort(key=lambda x: x["longitude"])
    
    # 3. Retrograde Phantom Positions (Rear-View Calculation)
    retrograde_impact = {}
    for p_name, is_retro in natal_retrograde.items():
        if is_retro and p_name in planet_positions:
            current_sign_idx = planet_sign_index.get(p_name, int(planet_positions[p_name] / 30))
            phantom_sign_idx = (current_sign_idx - 1) % 12
            phantom_sign_name = ZODIAC_SIGNS[phantom_sign_idx]
            current_sign_name = ZODIAC_SIGNS[current_sign_idx]
            retrograde_impact[f"{p_name}_R"] = f"Projecting into {phantom_sign_name} (12th from {current_sign_name})"
    
    # 4. Friend/Enemy Matrix
    friend_enemy_matrix = {}
    planet_list = list(planet_positions.keys())
    
    for i, p1 in enumerate(planet_list):
        for p2 in planet_list[i+1:]:
            p1_deva = p1 in DEVA_GROUP
            p2_deva = p2 in DEVA_GROUP
            p1_asura = p1 in ASURA_GROUP
            p2_asura = p2 in ASURA_GROUP
            
            # Exception: Mercury is neutral/friendly to Jupiter
            if (p1 == "Mercury" and p2 == "Jupiter") or (p1 == "Jupiter" and p2 == "Mercury"):
                relationship = "NEUTRAL/FRIENDLY"
            elif (p1_deva and p2_asura) or (p1_asura and p2_deva):
                relationship = "ENEMY/OBSTRUCTION"
            elif (p1_deva and p2_deva) or (p1_asura and p2_asura):
                relationship = "FRIEND"
            else:
                relationship = "NEUTRAL"
            
            friend_enemy_matrix[f"{p1}_vs_{p2}"] = relationship
    
    # 5. BNN Transit Cycles (Saturn and Jupiter cycles based on age)
    current_date = datetime.datetime.now(datetime.timezone.utc)
    age_years = (current_date - birth_datetime).total_seconds() / (365.2425 * 24 * 3600)
    
    saturn_round = int(age_years / 30) + 1
    saturn_round_progress = (age_years % 30) / 30.0
    saturn_phase = "Setup/Struggle" if saturn_round == 1 else "Establishment"
    
    jupiter_round = int(age_years / 12) + 1
    jupiter_round_progress = (age_years % 12) / 12.0
    
    transit_cycles = {
        "saturn_cycle": {
            "round": saturn_round,
            "round_progress": round(saturn_round_progress, 4),
            "phase": saturn_phase,
            "age_range": f"{(saturn_round-1)*30}-{saturn_round*30} years"
        },
        "jupiter_cycle": {
            "round": jupiter_round,
            "round_progress": round(jupiter_round_progress, 4),
            "age_range": f"{(jupiter_round-1)*12}-{jupiter_round*12} years"
        },
        "current_age_years": round(age_years, 2)
    }
    
    # 6. Special Yogas - Parivartana (Mutual Reception)
    special_yogas = {
        "parivartana_exchange": []
    }
    
    # Check for mutual reception: Planet A in Planet B's sign, Planet B in Planet A's sign
    for p1_name, p1_lon in planet_positions.items():
        p1_sign_idx = planet_sign_index.get(p1_name, int(p1_lon / 30))
        p1_sign_name = ZODIAC_SIGNS[p1_sign_idx]
        
        # Check if any other planet is in p1's natural sign
        for p2_name, p2_lon in planet_positions.items():
            if p1_name == p2_name:
                continue
            p2_sign_idx = planet_sign_index.get(p2_name, int(p2_lon / 30))
            p2_sign_name = ZODIAC_SIGNS[p2_sign_idx]
            
            # Check if p2 is in p1's natural sign and p1 is in p2's natural sign
            # Natural signs: Sun=Leo(4), Moon=Cancer(3), Mars=Aries(0), Mercury=Gemini(2)/Virgo(5),
            #                Jupiter=Sagittarius(8), Venus=Libra(6)/Taurus(1), Saturn=Capricorn(9)/Aquarius(10)
            natural_signs = {
                "Sun": [4], "Moon": [3], "Mars": [0],
                "Mercury": [2, 5], "Jupiter": [8], "Venus": [1, 6], "Saturn": [9, 10]
            }
            
            p1_natural = natural_signs.get(p1_name, [])
            p2_natural = natural_signs.get(p2_name, [])
            
            if p2_sign_idx in p1_natural and p1_sign_idx in p2_natural:
                special_yogas["parivartana_exchange"].append(
                    f"{p1_name} in {p2_sign_name} ↔ {p2_name} in {p1_sign_name}"
                )
    
    # Format output for display
    bnn_display = []
    bnn_display.append("### DIRECTIONAL GROUPS (Nadi Grouping):")
    for direction, planets in directional_groups.items():
        if planets:
            bnn_display.append(f"- **{direction}:** {', '.join(planets)}")
    
    bnn_display.append("\n### ORBITAL ORDER (Degree-Based Influence):")
    for sign_seq, planets in effective_order.items():
        bnn_display.append(f"- **{sign_seq}:** {', '.join(planets)}")
    
    bnn_display.append("\n### RETROGRADE PHANTOM POSITIONS:")
    if retrograde_impact:
        for key, value in retrograde_impact.items():
            bnn_display.append(f"- {key}: {value}")
    else:
        bnn_display.append("- No retrograde planets")
    
    bnn_display.append("\n### FRIEND/ENEMY MATRIX (BNN Groups):")
    bnn_display.append(f"- **Deva Group:** {', '.join(DEVA_GROUP)}")
    bnn_display.append(f"- **Asura Group:** {', '.join(ASURA_GROUP)}")
    bnn_display.append("\n**Relationships (All Pairs):**")
    
    # Create table format for all pairs
    bnn_display.append("\n| Planet 1 | Planet 2 | Relationship |")
    bnn_display.append("| :--- | :--- | :--- |")
    
    # Sort pairs for better readability
    sorted_pairs = sorted(friend_enemy_matrix.items())
    for pair_key, relationship in sorted_pairs:
        # Extract planet names from pair key (format: "Planet1_vs_Planet2")
        parts = pair_key.split("_vs_")
        if len(parts) == 2:
            planet1 = parts[0]
            planet2 = parts[1]
            bnn_display.append(f"| {planet1} | {planet2} | {relationship} |")
    
    bnn_display.append("\n### BNN TRANSIT CYCLES:")
    bnn_display.append(f"- **Saturn Cycle:** Round {transit_cycles['saturn_cycle']['round']} ({transit_cycles['saturn_cycle']['phase']}) - {transit_cycles['saturn_cycle']['age_range']}")
    bnn_display.append(f"- **Jupiter Cycle:** Round {transit_cycles['jupiter_cycle']['round']} - {transit_cycles['jupiter_cycle']['age_range']}")
    bnn_display.append(f"- **Current Age:** {transit_cycles['current_age_years']} years")
    
    bnn_display.append("\n### SPECIAL YOGAS:")
    if special_yogas["parivartana_exchange"]:
        for yoga in special_yogas["parivartana_exchange"]:
            bnn_display.append(f"- **Parivartana:** {yoga}")
    else:
        bnn_display.append("- No Parivartana Yogas detected")
    
    bnn_display_str = "\n".join(bnn_display)
    
    # Structured data for JSON payload
    bnn_structured = {
        "directional_groups": directional_groups,
        "effective_order": effective_order,
        "directional_sequences": {
            k: [
                {
                    "planet": p["planet"],
                    "sign": p["sign"],
                    "degree": round(p["degree"], 2),
                    "retrograde": p["retrograde"]
                }
                for p in v
            ]
            for k, v in directional_sequences.items()
        },
        "retrograde_impact": retrograde_impact,
        "friend_enemy_matrix": friend_enemy_matrix,
        "transit_cycles": transit_cycles,
        "special_yogas": special_yogas,
        "groups": {
            "deva": DEVA_GROUP,
            "asura": ASURA_GROUP
        }
    }
    
    return bnn_display_str, bnn_structured

def calculate_unified_kundali(planet_positions, planet_sign_index, planet_bhava_house, planet_house_from_lagna,
                               asc_deg_sidereal, asc_sign_id, planet_nakshatra_index, planet_pada,
                               planet_motion_payload=None):
    """
    Generate Unified BNN-Parashari Kundali (Step 12/13):
    A table sorted by Whole Sign Houses (1-12) showing:
    - House, Planet, Sign, Degree (D-M-S), Nakshatra (Pada), BNN Direction, Bhava Shift
    Uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility.
    """
    # Directional mapping for BNN
    DIRECTIONAL_MAP = {
        0: ("EAST", "Fire"), 4: ("EAST", "Fire"), 8: ("EAST", "Fire"),  # Fire signs
        1: ("SOUTH", "Earth"), 5: ("SOUTH", "Earth"), 9: ("SOUTH", "Earth"),  # Earth signs
        2: ("WEST", "Air"), 6: ("WEST", "Air"), 10: ("WEST", "Air"),  # Air signs
        3: ("NORTH", "Water"), 7: ("NORTH", "Water"), 11: ("NORTH", "Water")  # Water signs
    }
    
    # Planet roles/meanings
    PLANET_ROLES = {
        "Sun": "Self/Authority", "Moon": "Mind", "Mars": "Sibling/Energy",
        "Mercury": "Communication", "Jupiter": "Wisdom", "Venus": "Relationships",
        "Saturn": "Karma", "Rahu": "Desire", "Ketu": "Spirituality"
    }
    
    # Initialize house list (1-12) with Whole Sign system
    house_data = {i: [] for i in range(1, 13)}
    
    # Add Lagna to House 1
    asc_d, asc_m, asc_s = decimal_to_dms_full(asc_deg_sidereal % 30)
    asc_nak_idx = planet_nakshatra_index.get("Lagna", get_nakshatra(asc_deg_sidereal)[1])
    asc_nak_name = NAKSHATRAS[(asc_nak_idx - 1) % 27]
    asc_pada = planet_pada.get("Lagna", get_nakshatra(asc_deg_sidereal)[2])
    asc_direction, asc_element = DIRECTIONAL_MAP.get(asc_sign_id, ("UNKNOWN", ""))
    
    house_data[1].append({
        "planet": "Lagna",
        "role": "Self",
        "sign_idx": asc_sign_id,
        "sign_name": ZODIAC_SIGNS[asc_sign_id],
        "degree": asc_deg_sidereal % 30,
        "degree_dms": f"{asc_d}° {asc_m}' {asc_s}\"",
        "longitude": asc_deg_sidereal,
        "nakshatra": asc_nak_name,
        "pada": asc_pada,
        "direction": asc_direction,
        "element": asc_element,
        "rashi_house": 1,
        "bhava_house": 1,  # Lagna is always in House 1
        "bhava_shift": False
    })
    
    # Add all planets to their respective Whole Sign Houses
    for p_name, lon in planet_positions.items():
        sign_idx = planet_sign_index.get(p_name, int(lon / 30))
        rashi_house = planet_house_from_lagna.get(p_name, ((sign_idx - asc_sign_id) % 12) + 1)
        bhava_house = planet_bhava_house.get(p_name, rashi_house)
        
        # Check for Bhava shift
        has_bhava_shift = (bhava_house != rashi_house)
        
        # Calculate degree in sign
        deg_in_sign = lon % 30
        d, m, s = decimal_to_dms_full(deg_in_sign)
        
        # Get Nakshatra
        nak_idx = planet_nakshatra_index.get(p_name, get_nakshatra(lon)[1])
        nak_name = NAKSHATRAS[(nak_idx - 1) % 27]
        pada = planet_pada.get(p_name, get_nakshatra(lon)[2])
        
        # Get BNN Direction
        direction, element = DIRECTIONAL_MAP.get(sign_idx, ("UNKNOWN", ""))
        
        house_data[rashi_house].append({
            "planet": p_name,
            "role": PLANET_ROLES.get(p_name, p_name),
            "sign_idx": sign_idx,
            "sign_name": ZODIAC_SIGNS[sign_idx],
            "degree": deg_in_sign,
            "degree_dms": f"{d}° {m}' {s}\"",
            "retro_marker": motion_marker_for_display(p_name, (planet_motion_payload or {}).get(p_name, {})),
            "longitude": lon,
            "nakshatra": nak_name,
            "pada": pada,
            "direction": direction,
            "element": element,
            "rashi_house": rashi_house,
            "bhava_house": bhava_house,
            "bhava_shift": has_bhava_shift
        })
    
    # Sort planets within each house by degree (for orbital order)
    for house_num in house_data:
        house_data[house_num].sort(key=lambda x: x["degree"])
    
    # Generate markdown table
    table_rows = []
    table_rows.append("| House | Planet (Role) | Sign (Rashi) | Degree (D-M-S) | Nakshatra (Pada) | BNN Direction | Bhava Shift |")
    table_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for house_num in range(1, 13):
        if house_data[house_num]:
            for planet_data in house_data[house_num]:
                bhava_marker = f"[→ H{planet_data['bhava_house']}]" if planet_data['bhava_shift'] else ""
                retro_str = planet_data.get("retro_marker", "")
                planet_display = f"{planet_data['planet']} ({planet_data['role']}){retro_str}{bhava_marker}"
                table_rows.append(
                    f"| H{house_num} | {planet_display} | {planet_data['sign_name']} | {planet_data['degree_dms']} | "
                    f"{planet_data['nakshatra']} ({planet_data['pada']}) | {planet_data['direction']} ({planet_data['element']}) | "
                    f"{'Yes' if planet_data['bhava_shift'] else 'No'} |"
                )
        else:
            # Empty house - show sign name based on Whole Sign system
            sign_idx = (asc_sign_id + house_num - 1) % 12
            sign_name = ZODIAC_SIGNS[sign_idx]
            direction, element = DIRECTIONAL_MAP.get(sign_idx, ("UNKNOWN", ""))
            table_rows.append(
                f"| H{house_num} | -- | {sign_name} | -- | -- | {direction} ({element}) | -- |"
            )
    
    unified_table = "\n".join(table_rows)
    
    # Generate structured data for JSON
    unified_structured = {
        "house_system": "Whole Sign (Rashi = House)",
        "houses": {}
    }
    
    for house_num in range(1, 13):
        house_planets = []
        for planet_data in house_data[house_num]:
            house_planets.append({
                "planet": planet_data["planet"],
                "role": planet_data["role"],
                "sign": planet_data["sign_name"],
                "sign_index": planet_data["sign_idx"],
                "degree": round(planet_data["degree"], 4),
                "degree_dms": planet_data["degree_dms"],
                "longitude": round(planet_data["longitude"], 4),
                "nakshatra": planet_data["nakshatra"],
                "pada": planet_data["pada"],
                "direction": planet_data["direction"],
                "element": planet_data["element"],
                "rashi_house": planet_data["rashi_house"],
                "bhava_house": planet_data["bhava_house"],
                "bhava_shift": planet_data["bhava_shift"]
            })
        
        # If empty, still record the sign
        if not house_planets:
            sign_idx = (asc_sign_id + house_num - 1) % 12
            sign_name = ZODIAC_SIGNS[sign_idx]
            direction, element = DIRECTIONAL_MAP.get(sign_idx, ("UNKNOWN", ""))
            house_planets = [{
                "planet": None,
                "sign": sign_name,
                "sign_index": sign_idx,
                "direction": direction,
                "element": element
            }]
        
        unified_structured["houses"][f"H{house_num}"] = house_planets
    
    return unified_table, unified_structured

def decimal_to_dms_full(deg_float):
    """Convert decimal degrees to degrees, minutes, seconds (full precision)."""
    d = int(deg_float)
    m_float = (deg_float - d) * 60
    m = int(m_float)
    s = int((m_float - m) * 60)
    return d, m, s

NATAL_DRISHTI_RULES = {
    "Sun": [7],
    "Moon": [7],
    "Mercury": [7],
    "Venus": [7],
    "Mars": [4, 7, 8],
    "Jupiter": [5, 7, 9],
    "Saturn": [3, 7, 10],
    "Rahu": [],
    "Ketu": [],
}

DRISHTI_INTENT = {
    "Sun": {
        "intent": "Illumination / authority / visibility",
        "effect_hint": "Highlights the house; brings ego, father, power, visibility, government or authority themes."
    },
    "Moon": {
        "intent": "Nourishment / emotional attention",
        "effect_hint": "Emotionally activates the house; brings attachment, fluctuation, care, and mind-related influence."
    },
    "Mercury": {
        "intent": "Analysis / communication / trade",
        "effect_hint": "Adds intellect, speech, calculation, business, curiosity, and adaptability."
    },
    "Venus": {
        "intent": "Harmony / pleasure / refinement",
        "effect_hint": "Seeks beauty, comfort, agreement, art, luxury, romance, and balance."
    },
    "Mars": {
        "intent": "Drive / protection / conflict",
        "effect_hint": "Energizes, protects, competes, cuts, fights, or creates urgency in the house."
    },
    "Jupiter": {
        "intent": "Grace / expansion / protection",
        "effect_hint": "Expands and protects; acts as correction, wisdom, blessing, and safety net."
    },
    "Saturn": {
        "intent": "Discipline / delay / karmic pressure",
        "effect_hint": "Creates responsibility, delay, duty, effort, endurance, and karmic accountability."
    },
    "Rahu": {
        "intent": "Amplification / obsession / unconventional drive",
        "effect_hint": "If node aspects are enabled, amplifies, distorts, obsesses, and breaks convention."
    },
    "Ketu": {
        "intent": "Detachment / separation / spiritualization",
        "effect_hint": "If node aspects are enabled, detaches, dries, separates, or spiritualizes the house."
    },
}

HOUSE_MEANINGS = {
    1: "self/body",
    2: "wealth/speech/family",
    3: "courage/siblings/effort",
    4: "home/mother/property",
    5: "children/intelligence/purva punya",
    6: "enemies/debt/disease/service",
    7: "marriage/partnership",
    8: "longevity/transformation/secrets",
    9: "dharma/father/fortune",
    10: "career/karma/status",
    11: "gains/network/desires",
    12: "loss/foreign/spirituality/sleep"
}

def count_from_house(occupied_house, aspect_number):
    return ((occupied_house + aspect_number - 2) % 12) + 1

def _get_natural_nature(planet, pp):
    if planet in ["Sun", "Saturn", "Mars", "Rahu", "Ketu"]: return "Natural Malefic"
    if planet in ["Jupiter", "Venus"]: return "Natural Benefic"
    if planet == "Moon": 
        # approximate waxing/waning via Sun-Moon dist
        if "Sun" in pp and "Moon" in pp:
            dist = (pp["Moon"] - pp["Sun"]) % 360
            return "Benefic (Waxing Moon)" if dist > 12 else "Malefic (Waning Moon)"
        return "Conditional (Moon)"
    if planet == "Mercury": return "Conditional (Benefic unless afflicted)"
    return "Unknown"

def calculate_natal_drishti_table(
    planet_positions,
    d1_house_chart,
    lagna_sign,
    retrograde_map=None,
    node_drishti_mode="none"
) -> list[dict]:
    rows = []
    rules = dict(NATAL_DRISHTI_RULES)
    if node_drishti_mode == "seventh_only":
        rules["Rahu"] = [7]
        rules["Ketu"] = [7]
    elif node_drishti_mode == "jupiter_style":
        rules["Rahu"] = [5, 7, 9]
        rules["Ketu"] = [5, 7, 9]
        
    retrograde_map = retrograde_map or {}
    
    for p, aspects in rules.items():
        if p not in planet_positions: continue
        lon = planet_positions[p]
        p_sign = int(lon / 30)
        p_house = ((p_sign - lagna_sign + 12) % 12) + 1
        
        for aspect_num in aspects:
            target_house = count_from_house(p_house, aspect_num)
            target_sign = (lagna_sign + target_house - 1) % 12
            
            # Find planets in target house
            target_planets = [tp for tp, tlon in planet_positions.items() 
                              if int(tlon / 30) == target_sign and tp != p]
                              
            target_lord = get_sign_lord_from_index(target_sign)
            
            if aspect_num == 7:
                aspect_type = "Universal 7th aspect"
            else:
                aspect_type = f"{p} {aspect_num}th special aspect"
                
            retro_ctx = "Retrograde" if retrograde_map.get(p, False) else "Direct"
            
            rows.append({
                "aspecting_planet": p,
                "planet_house": p_house,
                "planet_sign": ZODIAC_SIGNS[p_sign],
                "planet_degree": round(lon, 4),
                "natural_nature": _get_natural_nature(p, planet_positions),
                "functional_nature": "not_available",
                "dignity": "not_available",
                "retrograde_context": retro_ctx,
                "aspect_number": aspect_num,
                "aspect_type": aspect_type,
                "aspected_house": target_house,
                "aspected_sign": ZODIAC_SIGNS[target_sign],
                "target_planets_in_house": target_planets,
                "target_house_lord": target_lord,
                "intent": DRISHTI_INTENT[p]["intent"],
                "effect_hint": DRISHTI_INTENT[p]["effect_hint"],
                "strength_note": "not_available"
            })
    return rows

def summarize_house_drishti(natal_drishti_rows, d1_house_chart, lagna_sign) -> list[dict]:
    summary = []
    for h in range(1, 13):
        sign_idx = (lagna_sign + h - 1) % 12
        sign_name = ZODIAC_SIGNS[sign_idx]
        lord = get_sign_lord_from_index(sign_idx)
        
        # planets in house
        in_house = d1_house_chart.get(f"H{h}", [])
        planets_in = [p["planet"] for p in in_house if p.get("planet")]
        
        # aspects pointing to this house
        aspects = [r for r in natal_drishti_rows if r["aspected_house"] == h]
        aspecting_planets = [r["aspecting_planet"] for r in aspects]
        
        jup_protect = "Jupiter" in aspecting_planets
        sat_press = "Saturn" in aspecting_planets
        mars_drive = "Mars" in aspecting_planets
        
        ben = [r["aspecting_planet"] for r in aspects if "Benefic" in r["natural_nature"]]
        mal = [r["aspecting_planet"] for r in aspects if "Malefic" in r["natural_nature"]]
        
        mixed = bool(ben) and bool(mal)
        
        hint = f"{HOUSE_MEANINGS[h].capitalize()}."
        if jup_protect: hint += " Protected by Jupiter."
        if sat_press: hint += " Delayed/tested by Saturn."
        if mars_drive: hint += " Energized by Mars."
        if mixed: hint += " Mixed influences."
        
        summary.append({
            "house": h,
            "sign": sign_name,
            "house_meaning_short": HOUSE_MEANINGS[h],
            "planets_in_house": planets_in,
            "house_lord": lord,
            "aspected_by": aspecting_planets,
            "jupiter_protection": jup_protect,
            "saturn_pressure": sat_press,
            "mars_drive": mars_drive,
            "benefic_aspects": ben,
            "malefic_aspects": mal,
            "mixed_gazes": mixed,
            "summary_hint": hint
        })
    return summary


def calculate_vedic_charts(name, dt_aware, lat, lon, gender="Unknown"):
    # Standardize Ayanamsa: Use KRISHNAMURTI_VP291 for better AstroSage alignment
    # Alternative (not used here): swe.SIDM_TRUE_CITRA anchors zodiac to star Spica
    swe.set_sid_mode(getattr(swe, "SIDM_KRISHNAMURTI_VP291", 45), 0, 0)
    
    utc_dt = dt_aware.astimezone(pytz.utc)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                    utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    
    # All planetary positions are computed in TROPICAL, then converted to
    # sidereal by subtracting the KP ayanamsa (Swiss Ephemeris SIDM_KRISHNAMURTI).
    calc_flag = swe.FLG_SWIEPH | swe.FLG_SPEED                         # tropical geocentric + speed
    swe.set_topo(lon, lat, 0)
    calc_flag_topo = swe.FLG_TOPOCTR | swe.FLG_SWIEPH | swe.FLG_SPEED   # tropical topocentric + speed
    
    # --- 1. ASTRONOMICAL CALCULATIONS ---
    # Calculate sunrise and sunset - try multiple methods for compatibility
    geopos = (lon, lat, 0)
    sunrise_jd = None
    sunset_jd = None
    
    # Method 1: Try swe.rise_trans (standard method)
    try:
        res = swe.rise_trans(jd, swe.SUN, '', swe.FLG_SWIEPH, geopos, 1013.25, 15)
        if res[0] >= 0 and len(res) > 1 and len(res[1]) >= 2:
            sunrise_jd = res[1][0]
            sunset_jd = res[1][1]
    except (TypeError, AttributeError, IndexError):
        pass
    
    # Method 2: If Method 1 failed, try with None instead of empty string
    if sunrise_jd is None or sunset_jd is None:
        try:
            res = swe.rise_trans(jd, swe.SUN, None, swe.FLG_SWIEPH, geopos, 1013.25, 15)
            if res[0] >= 0 and len(res) > 1 and len(res[1]) >= 2:
                sunrise_jd = res[1][0]
                sunset_jd = res[1][1]
        except (TypeError, AttributeError, IndexError):
            pass
    
    # Method 3: Fallback - Trigonometric calculation (Ganita-Shastri precision)
    if sunrise_jd is None or sunset_jd is None or sunrise_jd <= 0 or sunset_jd <= 0:
        sunrise_jd, sunset_jd = calculate_sunrise_trigonometric(jd, lat, lon)
        if sunrise_jd is None or sunset_jd is None:
            # Last resort: use approximate based on date/latitude
            local_hour = dt_aware.hour + dt_aware.minute/60.0 + dt_aware.second/3600.0
            lon_offset_hours = lon / 15.0
            solar_hour = local_hour - lon_offset_hours
            sunrise_jd = jd - (solar_hour - 6) / 24.0
            sunset_jd = sunrise_jd + 0.5

    day_diff = jd - sunrise_jd
    ishtakala_ghati = day_diff * 60 
    day_len_ghati = (sunset_jd - sunrise_jd) * 60
    is_day_birth = (jd >= sunrise_jd) and (jd <= sunset_jd)
    
    gulika_lon, mandi_lon = calculate_upagrahas(sunrise_jd, sunset_jd, is_day_birth, dt_aware.weekday(), jd, lat, lon)
    
    # --- 2. BASIC CHART CALC ---
    # Build on top of astro_app_v2.py logic:
    # 1. Calculate Equal House (b'O') for BPHS/BNN compatibility (like astro_app_v2.py)
    # 2. Calculate Placidus (b'P') for KP-specific analysis
    # Both use tropical coordinates, then manual conversion with KP-Newcomb ayanamsa.
    
    # -------------------------------------------------------------------
    # AYANAMSA: Swiss Ephemeris SIDM_KRISHNAMURTI_VP291 (KP VP291).
    #
    # Uses Swiss Ephemeris VP291 Krishnamurti mode to better align cusp
    # boundaries with AstroSage/KP outputs.
    #
    # This single ayanamsa value is subtracted from ALL tropical longitudes
    # (planets, cusps, transits, dasha Moon) to get sidereal coordinates.
    # -------------------------------------------------------------------
    ayanamsa = get_kp_ayanamsa_ut(jd)
    
    # BPHS/BNN: Equal House system (same as astro_app_v2.py)
    # Compute tropical, then convert to sidereal with the same ayanamsa.
    cuss_equal_trop, ascmc_equal_trop = swe.houses_ex(jd, lat, lon, b"O", 0)
    asc_deg_sidereal_equal = (ascmc_equal_trop[0] - ayanamsa) % 360
    mc_deg_sidereal_equal  = (ascmc_equal_trop[1] - ayanamsa) % 360
    
    # KP Placidus cusp engine (manual selection or auto mode).
    def resolve_kp_cusp_engine(selected_engine, chart_mode):
        kp_modes = {
            "KP",
            "Unified",
            "Unified (BPHS + KP)",
            "BPHS + KP",
            "KP Cusp Engine",
        }
        if selected_engine == "auto" and chart_mode in kp_modes:
            return {
                "resolved_engine": "kp_new_manual",
                "reason": "KP/Unified auto resolves to kp_new_manual because KP sub/sub-sub calculations require the validated KP cusp baseline."
            }
        return {
            "resolved_engine": selected_engine,
            "reason": "User-selected explicit cusp engine."
        }

    # Chart mode is intrinsically KP/Unified here since we generate KP tables
    resolved_info = resolve_kp_cusp_engine(KP_CUSP_ENGINE, "Unified")
    selected_cusp_engine = resolved_info["resolved_engine"]
    
    placidus_cusps, asc_deg_sidereal_plac, mc_deg_sidereal_plac = _compute_placidus_cusps_by_engine(
        jd, lat, lon, selected_cusp_engine
    )

    # CRITICAL SPLIT:
    # - D1 Whole Sign Houses use Equal House ASC (BPHS/BNN & your original app: Virgo rising)
    # - KP Placidus cusps use Placidus ASC (separate KP-only matrix)
    asc_deg_sidereal = asc_deg_sidereal_equal
    mc_deg_sidereal = mc_deg_sidereal_equal

    # Calculate Sripati cusps manually (trisecting quadrants) for Bhava Chalit
    # Use Equal House MC/ASC for BPHS compatibility (same as astro_app_v2.py)
    sripati_cusps = calculate_sripati_bhava_cusps(mc_deg_sidereal, asc_deg_sidereal)
    
    # D1 Whole Sign Houses use Equal House ASC sign (BPHS/BNN + astro_app_v2.py behaviour)
    asc_sign_id = int(asc_deg_sidereal_equal / 30)
    
    # KP Placidus ASC sign (for KP cusps display only)
    asc_sign_id_plac = int(asc_deg_sidereal_plac / 30)
    asc_sign_name = ZODIAC_SIGNS[asc_sign_id]
    asc_d, asc_m = decimal_to_dms(asc_deg_sidereal % 30)
    asc_nak, _, asc_pada = get_nakshatra(asc_deg_sidereal)
    
    lagna_str = f"{asc_sign_name} ({asc_sign_id + 1}) at {asc_d}°{asc_m}' | {asc_nak} (Pada {asc_pada})"

    # Build cuspal data for KP-style analysis (Placidus cusps + Nakshatra/Pada + lords)
    cusps_kp: dict[str, dict[str, Any]] = {}
    for i, cusp_lon in enumerate(placidus_cusps):
        house_num = i + 1
        cusp_d, cusp_m, cusp_s = decimal_to_dms_full(cusp_lon)
        # Use the canonical classification helper to compute ALL KP properties, avoiding duplicate/stale logic
        cl = classify_kp_longitude(cusp_lon)
        cusps_kp[str(house_num)] = {
            "lon": round(cusp_lon, 6),
            "lon_dms": f"{cusp_d}d{cusp_m:02d}'{cusp_s:02d}\"",
            "sign": cl["sign"],
            "sign_index": int(cl["normalized_longitude"] / 30),
            "nakshatra": cl["nakshatra"],
            "nakshatra_index": int(cl["normalized_longitude"] * 60 / 800) % 27,
            "pada": cl["pada"],
            "sign_lord": get_sign_lord_from_index(int(cl["normalized_longitude"] / 30)),
            "star_lord": cl["star_lord"],
            "sub_lord": cl["sub_lord"],
            "sub_sub_lord": cl["sub_sub_lord"],
        }

    # --- CUSP ENGINE COMPARISON AUDIT (Issue 1) ---
    cusp_engine_comparison_audit = []
    # Reference engine
    ref_cusps, _, _ = _compute_placidus_cusps_by_engine(jd, lat, lon, "kp_new_manual")
    for eng in ["legacy_fallback", "swiss_vp291_sidereal", "kp_new_manual"]:
        c_cusps, _, _ = _compute_placidus_cusps_by_engine(jd, lat, lon, eng)
        for i in range(12):
            raw_lon = c_cusps[i]
            ref_lon = ref_cusps[i]
            diff_arcsec = float(Fraction(str(Decimal(str(raw_lon)) * Decimal("3600"))) - Fraction(str(Decimal(str(ref_lon)) * Decimal("3600"))))
            cl_eng = classify_kp_longitude(raw_lon)
            cusp_engine_comparison_audit.append({
                "engine_name": eng,
                "cusp_number": i + 1,
                "raw_cusp_longitude": round(raw_lon, 6),
                "normalized_longitude": cl_eng["normalized_longitude"],
                "star_lord": cl_eng["star_lord"],
                "sub_lord": cl_eng["sub_lord"],
                "sub_sub_lord": cl_eng["sub_sub_lord"],
                "classification_helper_used": True,
                "difference_from_kp_new_manual_arcsec": diff_arcsec,
                "warning": "",
            })

    d1_occupants = {i: [] for i in range(1, 13)} 
    d9_occupants = {i: [] for i in range(1, 13)}
    planet_details = {} 
    moon_nak_name = ""
    moon_nak_idx = 1
    planet_positions = {} 
    planet_baladi = {}
    planet_sign_index = {}
    planet_house_from_lagna = {}
    planet_bhava_house = {}
    planet_nakshatra_index = {}
    planet_pada = {}
    
    d22_lon = (asc_deg_sidereal + 210) % 360
    d22_drekkana_sign_id = get_varga_sign(d22_lon, 3)
    d22_sign_name = ZODIAC_SIGNS[d22_drekkana_sign_id]
    d64_sign_name = "Unknown"

    varga_data = {}
    target_vargas = [1, 2, 3, 4, 7, 8, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]
    varga_lagnas = {v: get_varga_sign(asc_deg_sidereal, v) for v in target_vargas}
    
    # Sripati cusps are HOUSE BOUNDARIES (per BPHS), NOT midpoints.
    # Planet is in House i if between Cusp[i-1] and Cusp[i].
    # No midpoint layer needed.

    # --- 3. PLANETARY LOOP ---
    natal_data_for_table = []
    natal_retrograde = {}

    # KP: per-planet sign/star/sub-lord + retrograde meta
    planetary_star_sub: dict[str, dict[str, Any]] = {}
    
    for p_name, p_id in PLANETS.items():
        if p_name in ["Sun", "Moon"]:
            res = swe.calc_ut(jd, p_id, calc_flag)
            lon = (res[0][0] - ayanamsa) % 360  # tropical → sidereal
            speed = res[0][3] if len(res[0]) > 3 else 0
            
            motion = "direct"
            is_backward_motion = False
            is_retrograde_by_speed = False
            kp_treat_as_retrograde = False
            display_motion = "Direct"
        elif p_name in ["Rahu", "Ketu"]:
            node_mode = "mean"  # Fallback. Can be mapped via config if needed.
            if p_name == "Ketu":
                rahu_data = swe.calc_ut(jd, swe.MEAN_NODE, calc_flag)
                speed = rahu_data[0][3] if len(rahu_data[0]) > 3 else 0
                lon = (rahu_data[0][0] + 180 - ayanamsa) % 360  # Ketu = Rahu + 180
            else:
                res = swe.calc_ut(jd, swe.MEAN_NODE, calc_flag)
                speed = res[0][3] if len(res[0]) > 3 else 0
                lon = (res[0][0] - ayanamsa) % 360
            
            if node_mode == "mean":
                motion = "backward"
                is_backward_motion = True
                is_retrograde_by_speed = True
            else:
                motion = "backward" if speed < 0 else "direct"
                is_backward_motion = speed < 0
                is_retrograde_by_speed = speed < 0
                
            kp_treat_as_retrograde = False
            display_motion = "Backward / Anti-clockwise"
        else:
            res = swe.calc_ut(jd, p_id, calc_flag)
            lon = (res[0][0] - ayanamsa) % 360  # tropical → sidereal
            speed = res[0][3] if len(res[0]) > 3 else 0
            
            motion = "retrograde" if speed < 0 else "direct"
            is_backward_motion = speed < 0
            is_retrograde_by_speed = speed < 0
            kp_treat_as_retrograde = speed < 0
            display_motion = "Retrograde" if speed < 0 else "Direct"
        
        natal_retrograde[p_name] = is_retrograde_by_speed
            
        planet_positions[p_name] = lon
        d, m = decimal_to_dms(lon % 30)
        nak_name, nak_idx, pada = get_nakshatra(lon)
        
        planet_sign_index[p_name] = int(lon / 30)
        planet_house_from_lagna[p_name] = get_house_from_lagna(lon, asc_sign_id)
        planet_nakshatra_index[p_name] = nak_idx
        planet_pada[p_name] = pada
        baladi_status, baladi_strength = get_baladi_avastha(lon)
        planet_baladi[p_name] = {"status": baladi_status, "strength": baladi_strength}

        # KP-style sign/star/sub lords for planet
        cl_p = classify_kp_longitude(lon)
        star_lord_p, sub_lord_p, sub_sub_lord_p = cl_p["star_lord"], cl_p["sub_lord"], cl_p["sub_sub_lord"]
        planetary_star_sub[p_name] = {
            "sign": ZODIAC_SIGNS[int(lon / 30)],
            "sign_lord": get_sign_lord_from_index(int(lon / 30)),
            "star_lord": star_lord_p,
            "sub_lord": sub_lord_p,
            "sub_sub_lord": sub_sub_lord_p,
            "speed": speed,
            "motion": motion,
            "is_backward_motion": is_backward_motion,
            "is_retrograde_by_speed": is_retrograde_by_speed,
            "kp_treat_as_retrograde": kp_treat_as_retrograde,
            "display_motion": display_motion,
        }
        
        # Bhava house via Sripati cusps directly (BPHS method)
        # Planet is in House i if between Cusp[i-1] and Cusp[i]
        bhava_house = None
        for i in range(12):
            cusp_start = sripati_cusps[i]           # Start of House (i+1)
            cusp_end = sripati_cusps[(i + 1) % 12]  # Start of next House
            
            p_lon = lon  # planet longitude
            
            # Handle 360° wraparound
            if cusp_end < cusp_start:
                # Wraparound: adjust end and possibly planet longitude
                cusp_end_adj = cusp_end + 360
                p_lon_adj = p_lon + 360 if p_lon < cusp_start else p_lon
            else:
                cusp_end_adj = cusp_end
                p_lon_adj = p_lon
            
            if cusp_start <= p_lon_adj < cusp_end_adj:
                bhava_house = i + 1
                break
        
        # Fallback: if no bhava found (shouldn't happen), use Whole Sign house
        if bhava_house is None:
            bhava_house = planet_house_from_lagna[p_name]
        planet_bhava_house[p_name] = bhava_house
        
        p_sign_id = int(lon / 30)
        p_sign_name = ZODIAC_SIGNS[p_sign_id]
        retro_str = motion_marker_for_display(p_name, planetary_star_sub[p_name])
        planet_details[p_name] = f"{d}°{m}' {nak_name}({pada}){retro_str}"
        
        # Format planet with degrees and nakshatra like D1 chart: "Planet (Degrees Nakshatra(Pada))"
        planet_with_deg = f"{p_name} ({d}°{m}' {nak_name}({pada}){retro_str})"
        natal_data_for_table.append(f"| {planet_with_deg} | {p_sign_name} | {d}°{m}' | {nak_name} | {pada} | {retro_str.strip(' ()')} | {baladi_status} | Bhava H{bhava_house} |")
        
        if p_name == "Sun":
            sun_lon_natal = lon
        if p_name == "Moon": 
            moon_nak_name = nak_name
            moon_nak_idx = nak_idx
            moon_lon_natal = lon
            moon_d64_lon = (lon + 210) % 360
            d64_nav_sign_id = get_varga_sign(moon_d64_lon, 9)
            d64_sign_name = ZODIAC_SIGNS[d64_nav_sign_id]
        
        p_row = {}
        for v in target_vargas:
            v_sign_idx = get_varga_sign(lon, v)
            # For D1 (Whole Sign Houses), use the already-calculated planet_house_from_lagna
            # For other vargas, calculate house from varga lagna
            if v == 1:
                v_house = planet_house_from_lagna[p_name]
            else:
                v_house = (v_sign_idx - varga_lagnas[v] + 12) % 12 + 1
            p_row[f"D{v}"] = f"{ZODIAC_SIGNS[v_sign_idx]} (H{v_house})"
            
            if v == 1: d1_occupants[v_house].append(p_name)
            if v == 9: d9_occupants[v_house].append(p_name)
            
        varga_data[p_name] = p_row
    
    # special targets for hit logic
    special_targets = [
        {"type": "special_point", "name": "64th_navamsa", "lon": (planet_positions.get("Moon", 0) + 210) % 360 if "Moon" in planet_positions else 0, "nak_idx": planet_nakshatra_index.get("Moon", 1), "pada": planet_pada.get("Moon", 1)},
        {"type": "special_point", "name": "22nd_drekkana", "lon": d22_lon, "nak_idx": get_nakshatra(d22_lon)[1], "pada": get_nakshatra(d22_lon)[2]},
        {"type": "angle", "name": "Ascendant", "lon": asc_deg_sidereal, "nak_idx": get_nakshatra(asc_deg_sidereal)[1], "pada": get_nakshatra(asc_deg_sidereal)[2]},
    ]
    natal_targets = []
    for p_name, lon_val in planet_positions.items():
        nak_idx, pd = nak_pada(lon_val)
        natal_targets.append({"type": "natal_planet", "name": p_name, "lon": lon_val, "nak_idx": nak_idx, "pada": pd})
    natal_targets.extend(special_targets)

    # --- 4. CALCULATE CURRENT TRANSITS ---
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    jd_now = swe.julday(now_utc.year, now_utc.month, now_utc.day, 
                        now_utc.hour + now_utc.minute/60.0)
    transit_report = []
    
    # Use topocentric flag for transit positions (observer-centric), tropical → sidereal
    transit_calc_flag = swe.FLG_TOPOCTR | swe.FLG_SWIEPH | swe.FLG_SPEED   # topocentric + speed
    # Transit ayanamsa: same Swiss SIDM_KRISHNAMURTI as natal
    ayan_transit = get_kp_ayanamsa_ut(jd_now)
    for p_name, p_id in PLANETS.items():
        if p_name == "Ketu":
            rahu_data = swe.calc_ut(jd_now, swe.MEAN_NODE, transit_calc_flag)
            t_lon = (rahu_data[0][0] + 180 - ayan_transit) % 360
            speed = rahu_data[0][3] if len(rahu_data[0]) > 3 else 0
        else:
            res = swe.calc_ut(jd_now, p_id, transit_calc_flag)
            t_lon = (res[0][0] - ayan_transit) % 360
            speed = res[0][3] if len(res[0]) > 3 else 0
        
        is_retrograde = speed < 0
        retro_str = " (Retrograde)" if is_retrograde else ""
        t_sign_id = int(t_lon / 30)
        t_d, t_m = decimal_to_dms(t_lon % 30)
        
        hit_str = ""
        for n_name, n_lon in planet_positions.items():
            strength, diff = detect_hit_strength(p_name, t_lon, n_lon)
            if strength is not None and diff <= 3.0:
                hit_str += f" (HITS Natal {n_name} within {diff:.1f}°)"
        
        transit_report.append(f"- Transit {p_name}: {ZODIAC_SIGNS[t_sign_id]} at {t_d}°{t_m}'{retro_str}{hit_str}")

    # Transit timestamp will be formatted in user's timezone later
    transit_timestamp_utc = now_utc
    transit_str = "\n".join(transit_report)

    # --- 5. ADVANCED SCORES ---
    bav_matrix, sav_scores = calculate_bav_sav(planet_positions, asc_sign_id)
    # Build full BAV + SAV markdown table
    _bav_header = "| Planet | Ari | Tau | Gem | Can | Leo | Vir | Lib | Sco | Sag | Cap | Aqu | Pis |"
    _bav_sep    = "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    _bav_rows: list[str] = [_bav_header, _bav_sep]
    BAV_DISPLAY_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    for p_name in BAV_DISPLAY_ORDER:
        row_vals = bav_matrix[p_name]
        cells = " | ".join(str(row_vals[s]) for s in range(12))
        _bav_rows.append(f"| {p_name} | {cells} |")
    # SAV totals row
    total_cells = " | ".join(str(sav_scores[s]) for s in range(12))
    _bav_rows.append(f"| **Total (SAV)** | {total_cells} |")
    sav_str = "\n".join(_bav_rows)
    total_sav_score = sum(sav_scores[s] for s in range(12))
    
    avastha_report = []
    ghati_int = int(ishtakala_ghati)
    lagna_idx = asc_sign_id + 1
    constant_sum = moon_nak_idx + ghati_int + lagna_idx
    
    planet_avasthas_map: dict[str, str] = {}
    for i, p_name in enumerate(PLANET_ORDER):
        if p_name in planet_positions:
            p_idx = i + 1 
            p_lon = planet_positions[p_name]
            _, p_nak_idx, _ = get_nakshatra(p_lon)
            nav_sign_idx = get_varga_sign(p_lon, 9) + 1
            product = p_nak_idx * p_idx * nav_sign_idx
            total = product + constant_sum
            remainder = total % 12
            if remainder == 0:
                remainder = 12
            avastha_label = AVASTHAS[remainder - 1]
            avastha_report.append(f"{p_name}: {avastha_label}")
            planet_avasthas_map[p_name] = avastha_label
    avastha_str = "\n".join(avastha_report)
    
    g_sign = int(gulika_lon / 30)
    g_house = (g_sign - asc_sign_id + 12) % 12 + 1
    m_sign = int(mandi_lon / 30)
    m_house = (m_sign - asc_sign_id + 12) % 12 + 1
    upagraha_str = f"Gulika: {ZODIAC_SIGNS[g_sign]} (H{g_house})\nMandi: {ZODIAC_SIGNS[m_sign]} (H{m_house})"

    # --- 6. FORMATTING ---
    d1_rows = []
    for h in range(1, 13):
        curr_sign = ZODIAC_SIGNS[(asc_sign_id + h - 1) % 12]
        occ = ", ".join([f"{p} ({planet_details[p]})" for p in d1_occupants[h]])
        d1_rows.append(f"| {h} | {occ} | {curr_sign} |")
    d1_table = "| House | Planets (Deg/Nak/Pada) | Sign |\n| :--- | :--- | :--- |\n" + "\n".join(d1_rows)
    
    # Bhava Chalit Chart - Shows house shifts from Rashi
    bhava_rows = []
    for h in range(1, 13):
        curr_sign = ZODIAC_SIGNS[(asc_sign_id + h - 1) % 12]
        # Find planets in this Bhava house
        bhava_planets = []
        for p_name in PLANETS.keys():
            if p_name in planet_bhava_house and planet_bhava_house[p_name] == h:
                rashi_house = planet_house_from_lagna.get(p_name, h)
                shift_note = ""
                if rashi_house != h:
                    shift_note = f" [Rashi H{rashi_house} → Bhava H{h}]"
                bhava_planets.append(f"{p_name} ({planet_details[p_name]}){shift_note}")
        occ = ", ".join(bhava_planets) if bhava_planets else "Empty"
        bhava_rows.append(f"| {h} | {occ} | {curr_sign} |")
    bhava_table = "| Bhava House | Planets (Deg/Nak/Pada) | Sign |\n| :--- | :--- | :--- |\n" + "\n".join(bhava_rows)

    d9_rows = []
    nav_asc = varga_lagnas[9]
    for h in range(1, 13):
        curr_sign = ZODIAC_SIGNS[(nav_asc + h - 1) % 12]
        occ = ", ".join(d9_occupants[h]) if d9_occupants[h] else "Empty"
        d9_rows.append(f"| {h} | {curr_sign} | {occ} |")
    d9_table = "| House | Sign | Occupants |\n| :--- | :--- | :--- |\n" + "\n".join(d9_rows)
    
    v_head = "| Planet | " + " | ".join([f"D{v}" for v in target_vargas]) + " |"
    v_sep = "| :--- | " + " | ".join([":---" for _ in target_vargas]) + " |"
    v_rows = []
    for p in PLANET_ORDER:
        vals = [varga_data[p][f"D{v}"] for v in target_vargas]
        v_rows.append(f"| {p} | " + " | ".join(vals) + " |")
    varga_table = f"{v_head}\n{v_sep}\n" + "\n".join(v_rows)
    
    natal_data_str = "| Planet (Degrees Nakshatra(Pada)) | Sign | Degree | Nakshatra | Pada | Retrograde | Baladi Avastha | Bhava House |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(natal_data_for_table)

    # --- 7. CALCULATE VIMSHOTTARI DASHA ---
    # Use the same sidereal Moon longitude already computed in the planetary loop.
    # Do NOT re-fetch Moon here — re-fetching can pick up a different swe.set_sid_mode
    # state (set by _compute_placidus_cusps_by_engine) and produce a slightly different
    # tropical raw value, leading to a 20-day epoch drift.
    chart_moon_lon = planet_positions["Moon"]  # chart Moon (KP ayanamsha) — for display only

    # Compute Dasha Moon longitude using the dedicated ayanamsha (default: Lahiri)
    # This is independent of the KP cusp ayanamsha used for chart/cusps.
    _dasha_moon_info = calculate_dasha_moon_longitude(jd, DASHA_AYANAMSHA_MODE, chart_moon_lon=chart_moon_lon)
    moon_lon_dasha = _dasha_moon_info["moon_longitude"]
    dasha_ayanamsha_value = _dasha_moon_info["ayanamsha_value"]

    # Restore KP ayanamsha for any subsequent chart calculations that depend on swe.set_sid_mode
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI_VP291, 0, 0)


    # Generate full timeline (Mahadasha -> Antardasha -> Pratyantar) up to 120 years
    # Store start_dt/end_dt as real timezone-aware datetimes for exact comparison
    all_pd_periods = []
    for entry in generate_vimshottari_timeline(moon_lon_dasha, dt_aware, max_years=120):
        start_dt_obj = entry["start_solar"]   # timezone-aware datetime from generator
        end_dt_obj   = entry["end_solar"]     # timezone-aware datetime from generator
        all_pd_periods.append({
            "md": entry["mahadasha"],
            "ad": entry["antardasha"],
            "pd": entry["pratyantar"],
            "start_dt": start_dt_obj,
            "end_dt":   end_dt_obj,
            "start_solar": start_dt_obj.strftime("%d-%m-%Y"),
            "end_solar":   end_dt_obj.strftime("%d-%m-%Y"),
            "start_savana": start_dt_obj.strftime("%d-%m-%Y"),
            "end_savana":   end_dt_obj.strftime("%d-%m-%Y"),
            "start_jd": start_dt_obj.timestamp() / 86400.0 + 2440587.5,
            "end_jd":   end_dt_obj.timestamp() / 86400.0 + 2440587.5,
            "duration_solar_days": round(entry["duration_solar_days"], 1),
            "duration_savana_days": round(entry["duration_savana_days"], 1),
            "duration_years": round(entry["duration_years"], 4),
        })

    # target_dt_local: current moment in the user's birth timezone — use for scan
    target_dt_local = now_utc.astimezone(dt_aware.tzinfo)
    target_source = "now"

    # Scan all_pd_periods using datetime comparison (no JD float conversion)
    current_entry_idx = None
    for i, row in enumerate(all_pd_periods):
        if row["start_dt"] <= target_dt_local < row["end_dt"]:
            current_entry_idx = i
            break
    # Fallback: first future row
    if current_entry_idx is None:
        for i, row in enumerate(all_pd_periods):
            if row["end_dt"] > target_dt_local:
                current_entry_idx = i
                break

    # Show window: 10 rows before + current + 10 rows after
    if current_entry_idx is not None:
        window_start = max(0, current_entry_idx - 10)
        window_end   = min(len(all_pd_periods), current_entry_idx + 11)
        display_entries = all_pd_periods[window_start:window_end]
    else:
        display_entries = all_pd_periods[:20]

    # For backward compat: set current_md/current_ad from scan result
    current_md = all_pd_periods[current_entry_idx]["md"] if current_entry_idx is not None else "Unknown"
    current_ad = all_pd_periods[current_entry_idx]["ad"] if current_entry_idx is not None else "Unknown"
    current_pd_lord = all_pd_periods[current_entry_idx]["pd"] if current_entry_idx is not None else "Unknown"

    dasha_str = f"Mahadasha: {current_md}\nAntardasha: {current_ad}\nPratyantar: {current_pd_lord}"

    # Also keep timeline_entries alias for backward compat with packet code below
    timeline_entries = all_pd_periods

    # Find Rahu MD end from all_pd_periods (first row where Rahu MD ends)
    _rahu_md_end_dt = None
    for _row in all_pd_periods:
        if _row["md"] == "Rahu":
            _rahu_md_end_dt = _row["end_dt"]   # keep overwriting → last Rahu PD end = Rahu MD end
    # Find actual Rahu/Mars/Moon row for acceptance check
    _rahu_mars_moon_row = None
    for _row in all_pd_periods:
        if _row["md"] == "Rahu" and _row["ad"] == "Mars" and _row["pd"] == "Moon":
            _rahu_mars_moon_row = f"{_row['start_solar']} | {_row['end_solar']} | Rahu | Mars | Moon | {_row['duration_solar_days']}"
            break
    # Birth MD end (end of the first MD lord period)
    _birth_md_lord_label = all_pd_periods[0]["md"] if all_pd_periods else "?"
    _birth_md_end_dt = None
    for _row in all_pd_periods:
        if _row["md"] == _birth_md_lord_label:
            _birth_md_end_dt = _row["end_dt"]
    moon_diff_arcmin = (moon_lon_dasha - chart_moon_lon) * 60.0

    dasha_debug_payload = {
        "dasha_engine_version": "canonical_v2_birth_epoch_datetime",
        "dasha_ayanamsha_mode": DASHA_AYANAMSHA_MODE,
        "chart_ayanamsha_mode": "SIDM_KRISHNAMURTI_VP291",
        "chart_moon_longitude": round(chart_moon_lon, 6),
        "dasha_moon_longitude": round(moon_lon_dasha, 6),
        "dasha_ayanamsha_value": round(dasha_ayanamsha_value, 6),
        "moon_difference_arcmin": round(moon_diff_arcmin, 4),
        "moon_difference_arcsec": round(moon_diff_arcmin * 60, 4),
        "target_datetime_local": target_dt_local.isoformat(),
        "target_source": target_source,
        "birth_dt_local": dt_aware.isoformat(),
        "birth_dt_utc": utc_dt.isoformat(),
        "timezone": str(dt_aware.tzinfo),
        "jd_birth": round(jd, 6),
        "jd_now": round(jd_now, 6),
        "scan_source_list_name": "all_pd_periods",
        "count_pd_periods": len(all_pd_periods),
        "first_pd_row": f"{all_pd_periods[0]['start_solar']} | {all_pd_periods[0]['md']} | {all_pd_periods[0]['ad']} | {all_pd_periods[0]['pd']}" if all_pd_periods else "EMPTY",
        "last_pd_row": f"{all_pd_periods[-1]['start_solar']} | {all_pd_periods[-1]['md']} | {all_pd_periods[-1]['ad']} | {all_pd_periods[-1]['pd']}" if all_pd_periods else "EMPTY",
        "birth_md_lord": _birth_md_lord_label,
        "birth_md_end_dt": _birth_md_end_dt.strftime("%d-%m-%Y") if _birth_md_end_dt else None,
        "rahu_md_end_dt": _rahu_md_end_dt.strftime("%d-%m-%Y") if _rahu_md_end_dt else None,
        "current_md": current_md,
        "current_ad": current_ad,
        "current_pd": current_pd_lord,
        "current_row_index": current_entry_idx,
        "current_row_start": all_pd_periods[current_entry_idx]["start_solar"] if current_entry_idx is not None else None,
        "current_row_end": all_pd_periods[current_entry_idx]["end_solar"] if current_entry_idx is not None else None,
        "current_row_duration_days": all_pd_periods[current_entry_idx]["duration_solar_days"] if current_entry_idx is not None else None,
        "selected_window_start_index": (max(0, current_entry_idx - 10)) if current_entry_idx is not None else 0,
        "selected_window_end_index": (min(len(all_pd_periods), current_entry_idx + 11) - 1) if current_entry_idx is not None else 19,
        "selected_rows_count": len(display_entries),
        "rendered_rahu_mars_moon_row": _rahu_mars_moon_row or "NOT FOUND",
        "selected_rows_raw": [
            f"{r['start_solar']} | {r['end_solar']} | {r['md']} | {r['ad']} | {r['pd']} | {r['duration_solar_days']}"
            for r in display_entries
        ],
    }


    
    # Format timeline as PD-level table
    timeline_rows = []
    timeline_rows.append("| Start | End | MD | AD | PD | Duration (Days) | Status |")
    timeline_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for entry in display_entries:
        if entry["start_dt"] <= target_dt_local < entry["end_dt"]:
            status = "▶ CURRENT"
        elif entry["end_dt"] <= target_dt_local:
            status = "past"
        else:
            status = "upcoming"
        timeline_rows.append(
            f"| {entry['start_solar']} | {entry['end_solar']} | {entry['md']} | {entry['ad']} | {entry['pd']} | {entry['duration_solar_days']:.1f} | {status} |"
        )
    timeline_table = "\n".join(timeline_rows)
    
    # Store full timeline for sidebar
    full_timeline_data = timeline_entries
    
    # Create summary timeline string
    timeline_summary = f"Vimshottari Dasha Timeline (Relevant Period):\n{timeline_table}"

    # --- 8. MONTHLY HIT THEORY SNAPSHOTS (NEXT 12 MONTHS) ---
    months = build_monthly_transits(now_utc.date())
    monthly_packets = []
    moon_sign_id = planet_sign_index.get("Moon", asc_sign_id)
    for month_tuple in months:
        _, _, jd_mid = month_tuple
        transit_data = compute_transit_positions(jd_mid)
        hits, domain_summary, eclipse_type, gochara_results, degree_hits, aspect_impacts = detect_monthly_hits(
            month_tuple,
            transit_data,
            natal_targets,
            asc_sign_id,
            moon_sign_id,
            sav_scores,
            placidus_cusps
        )
        t_positions, t_retrograde = transit_data
        monthly_packets.append({
            "year": month_tuple[0],
            "month": month_tuple[1],
            "monthly_transits": {p: round(l, 4) for p, l in t_positions.items() if p in SLOW_PLANETS},
            "monthly_retrograde": {p: t_retrograde.get(p, {}).get("is_retrograde_by_speed", False) for p in SLOW_PLANETS},
            "monthly_gochara": gochara_results,  # Sign-based transit analysis
            "monthly_hits": hits,  # Legacy degree-based triggers
            "monthly_degree_hits": degree_hits,
            "monthly_aspect_impacts": aspect_impacts,
            "monthly_domain_scores": domain_summary,
            "eclipse_type": eclipse_type,
        })

    # Calculate Panchang (Five Limbs of Time) - ensure Sun and Moon are available
    sun_lon_natal = planet_positions.get("Sun", 0)
    moon_lon_natal = planet_positions.get("Moon", 0)
    panchang_data = calculate_panchang(sun_lon_natal, moon_lon_natal)
    panchang_str = f"Tithi: {panchang_data['tithi_name']} ({panchang_data['tithi']})\nYoga: {panchang_data['yoga_name']} ({panchang_data['yoga']})\nKarana: {panchang_data['karana_name']} ({panchang_data['karana']})"

    # --- 12. CALCULATE BNN MODULE (Bhrigu Nandi Nadi) ---
    bnn_display_str, bnn_structured = calculate_bnn_module(planet_positions, planet_sign_index, natal_retrograde, dt_aware)
    
    # --- 13. CALCULATE UNIFIED BNN-PARASHARI KUNDALI ---
    # Add Lagna to planet data for unified table
    planet_positions_with_lagna = planet_positions.copy()
    planet_positions_with_lagna["Lagna"] = asc_deg_sidereal
    planet_sign_index_with_lagna = planet_sign_index.copy()
    planet_sign_index_with_lagna["Lagna"] = asc_sign_id
    planet_bhava_house_with_lagna = planet_bhava_house.copy()
    planet_bhava_house_with_lagna["Lagna"] = 1  # Lagna is always in House 1
    planet_house_from_lagna_with_lagna = planet_house_from_lagna.copy()
    planet_house_from_lagna_with_lagna["Lagna"] = 1
    
    unified_kundali_table, unified_kundali_structured = calculate_unified_kundali(
        planet_positions_with_lagna, planet_sign_index_with_lagna, planet_bhava_house_with_lagna,
        planet_house_from_lagna_with_lagna, asc_deg_sidereal, asc_sign_id,
        planet_nakshatra_index, planet_pada,
        planet_motion_payload=planetary_star_sub,
    )

    # --- 13A. BUILD KP MASTER DATA PACKET ---
    # Ashtakavarga SAV per house 1..12 (convert from sign index 0..11)
    ashtakavarga_sav = {str(h + 1): sav_scores.get(h, 0) for h in range(12)}
    # Full BAV matrix keyed by planet → sign-name → bindu
    ashtakavarga_bav = {
        p: {ZODIAC_SIGNS[s]: bav_matrix[p][s] for s in range(12)}
        for p in bav_matrix
    }

    # D1 planet summary for KP
    d1_planets_kp: dict[str, dict[str, Any]] = {}
    for p_name, lon in planet_positions.items():
        sign_idx = planet_sign_index.get(p_name, int(lon / 30))
        house_from_lagna = planet_house_from_lagna.get(p_name, ((sign_idx - asc_sign_id) % 12) + 1)
        bhava_house_val = planet_bhava_house.get(p_name, house_from_lagna)
        d1_planets_kp[p_name] = {
            "lon": round(lon, 4),
            "sign": ZODIAC_SIGNS[sign_idx],
            "sign_index": sign_idx,
            "house_from_lagna": house_from_lagna,
            "bhava_house": bhava_house_val,
        }

    # Bhava positions mapping
    bhava_positions_kp = {
        p_name: {
            "rashi_house": planet_house_from_lagna.get(p_name),
            "bhava_house": planet_bhava_house.get(p_name),
        }
        for p_name in planet_positions.keys()
    }

    # Special points from natal core + upagrahas
    special_points_kp = {
        "64th_navamsa": {
            "sign": d64_sign_name,
            "lon": round((planet_positions.get("Moon", 0) + 210) % 360, 4),
        },
        "22nd_drekkana": {
            "sign": d22_sign_name,
            "lon": round(d22_lon, 4),
        },
        "Gulika": {
            "lon": round(gulika_lon, 4),
            "house_from_lagna": (int(gulika_lon / 30) - asc_sign_id + 12) % 12 + 1,
        },
        "Mandi": {
            "lon": round(mandi_lon, 4),
            "house_from_lagna": (int(mandi_lon / 30) - asc_sign_id + 12) % 12 + 1,
        },
    }

    # Moon dasha balance at birth — uses canonical NAKSHATRA_SPAN matching generate_vimshottari_timeline
    import math as _math_kp
    _NAKSHATRA_SPAN_KP = Fraction(40, 3)
    _mld_frac = Fraction(str(Decimal(str(moon_lon_dasha % 360))))
    _nak_idx_kp = _math_kp.floor(_mld_frac / _NAKSHATRA_SPAN_KP)
    _offset_in_nak_kp = _mld_frac - (_nak_idx_kp * _NAKSHATRA_SPAN_KP)
    _elapsed_frac_kp = _offset_in_nak_kp / _NAKSHATRA_SPAN_KP
    _remaining_frac_kp = 1 - _elapsed_frac_kp
    moon_birth_md_lord = NAKSHATRA_RULERS[_nak_idx_kp]
    moon_birth_md_total_years = dict(VIMSHOTTARI_SEQUENCE).get(moon_birth_md_lord, 0)
    moon_dasha_balance_years = float(moon_birth_md_total_years) * float(_remaining_frac_kp)
    moon_dasha_balance_days = moon_dasha_balance_years * DASHA_YEAR_DAYS
    moon_bal_years = int(moon_dasha_balance_days // DASHA_YEAR_DAYS)
    _rem_days_after_years = moon_dasha_balance_days - (moon_bal_years * DASHA_YEAR_DAYS)
    moon_bal_months = int(_rem_days_after_years // (DASHA_YEAR_DAYS / 12.0))
    moon_bal_days = int(round(_rem_days_after_years - (moon_bal_months * (DASHA_YEAR_DAYS / 12.0))))
    moon_dasha_balance_display = f"{moon_bal_years}y {moon_bal_months}m {moon_bal_days}d"

    dasha_kp = {
        "maha": current_md or moon_birth_md_lord,
        "antara": current_ad or "",
        "lord_chain": [current_md or moon_birth_md_lord, current_ad or ""],
        "moon_dasha_balance_at_birth": {
            "mahadasha_lord": moon_birth_md_lord,
            "years": round(moon_dasha_balance_years, 4),
            "days": round(moon_dasha_balance_days, 2),
            "display": moon_dasha_balance_display,
        },
    }

    # Transit hit list for KP Hit Theory: use current month's monthly_hits
    transit_hits_kp = []
    if monthly_packets:
        current_month_packet = monthly_packets[0]
        for hit in current_month_packet.get("monthly_hits", []):
            t_sign_idx = hit.get("transit_sign_index")
            t_house_from_lagna = (t_sign_idx - asc_sign_id + 12) % 12 + 1 if isinstance(t_sign_idx, int) else None
            transit_hits_kp.append(
                {
                    "transit_planet": hit.get("transit_planet"),
                    "natal_target_type": hit.get("target_type"),
                    "natal_target_id": hit.get("target_name"),
                    "orb_deg": hit.get("degree_diff_abs"),
                    "retrograde": hit.get("is_retrograde"),
                    "sign": ZODIAC_SIGNS[t_sign_idx] if isinstance(t_sign_idx, int) else None,
                    "house": t_house_from_lagna,
                }
            )

    # --- 13B. KP FULL OUTPUT CHECKLIST TABLES ---

    # KP Placidus house occupancy for each planet.
    # In KP, a planet is in the house between two consecutive Placidus cusps.
    planet_placidus_house: dict[str, int] = {}
    for p_name, p_lon in planet_positions.items():
        p_house_kp = 1  # fallback
        for i in range(12):
            c_start = placidus_cusps[i]
            c_end = placidus_cusps[(i + 1) % 12]
            if c_end > c_start:
                if c_start <= p_lon < c_end:
                    p_house_kp = i + 1
                    break
            else:  # wraps around 360°
                if p_lon >= c_start or p_lon < c_end:
                    p_house_kp = i + 1
                    break
        planet_placidus_house[p_name] = p_house_kp

    # Build reusable star/sub/sub-sub map for planets
    planet_star_sub_sub: dict[str, dict[str, Any]] = {}
    for p_name, lon in planet_positions.items():
        cl_lon = classify_kp_longitude(lon)
        star_lord, sub_lord, sub_sub_lord = cl_lon["star_lord"], cl_lon["sub_lord"], cl_lon["sub_sub_lord"]
        planet_star_sub_sub[p_name] = {
            "star_lord": star_lord,
            "sub_lord": sub_lord,
            "sub_sub_lord": sub_sub_lord,
        }

    # RASI chart with flags
    rasi_rows: list[list[Any]] = []
    navamsa_rows: list[list[Any]] = []
    for p_name in PLANET_ORDER:
        lon = planet_positions[p_name]
        sign_idx = int(lon / 30)
        sign_name = ZODIAC_SIGNS[sign_idx]
        house_num = planet_house_from_lagna[p_name]
        speed_retro = natal_retrograde.get(p_name, False)
        is_combust = False
        if p_name in COMBUST_ORB_DEG:
            is_combust = angle_diff_deg(lon, sun_lon_natal) < COMBUST_ORB_DEG[p_name]
        is_exalted = EXALTATION_SIGNS.get(p_name) == sign_idx
        is_debilitated = DEBILITATION_SIGNS.get(p_name) == sign_idx
        nav_sign_idx = get_varga_sign(lon, 9)
        is_vargottama = nav_sign_idx == sign_idx

        rasi_rows.append(
            [
                p_name,
                round(lon, 4),
                sign_name,
                house_num,
                "Y" if speed_retro else "",
                "Y" if is_combust else "",
                "Y" if is_vargottama else "",
                "Y" if is_exalted else "",
                "Y" if is_debilitated else "",
            ]
        )
        navamsa_rows.append(
            [
                p_name,
                sign_name,
                ZODIAC_SIGNS[nav_sign_idx],
                "TRUE" if is_vargottama else "FALSE",
            ]
        )

    rasi_chart_table = build_markdown_table(
        ["Planet", "Longitude", "Sign", "House", "Retrograde", "Combust", "Vargottama", "Exalted", "Debilitated"],
        rasi_rows,
    )
    navamsa_check_table = build_markdown_table(
        ["Planet", "Rasi Sign", "Navamsa Sign", "Vargottama"],
        navamsa_rows,
    )

    # PLANETS TABLE (with Ascendant as first row)
    planets_table_rows: list[list[Any]] = []
    # Ascendant row (Placidus cusp 1)
    asc_kp = cusps_kp["1"]
    planets_table_rows.append(
        [
            "Ascendant",
            ZODIAC_SIGNS[asc_kp["sign_index"]],
            asc_kp.get("sign_lord", get_sign_lord_from_index(asc_kp["sign_index"])),
            asc_kp.get("star_lord", ""),
            asc_kp.get("sub_lord", ""),
            asc_kp.get("sub_sub_lord", ""),
            "",  # Retrograde: N/A for Ascendant
        ]
    )
    for p_name in PLANET_ORDER:
        lon = planet_positions[p_name]
        ss = planet_star_sub_sub[p_name]
        retro = "R" if natal_retrograde.get(p_name, False) else ""
        planets_table_rows.append(
            [
                p_name,
                ZODIAC_SIGNS[int(lon / 30)],
                get_sign_lord_from_index(int(lon / 30)),
                ss["star_lord"],
                ss["sub_lord"],
                ss["sub_sub_lord"],
                retro,
            ]
        )
    planets_kp_table = build_markdown_table(
        ["Planet", "Sign", "Sign Lord", "Nakshatra Lord", "Sub Lord", "Sub Sub Lord", "Retrograde"],
        planets_table_rows,
    )

    # Planet Signification table (4-source rule, KP-style):
    # KP rule: occupancy = Placidus house; ownership = Placidus cusp sign-lords.
    # S1: house occupied by planet's star lord (Placidus)
    # S2: house occupied by planet itself (Placidus)
    # S3: houses owned by planet's star lord (via Placidus cusp sign-lords)
    # S4: houses owned by planet itself (via Placidus cusp sign-lords)
    kp_owned_houses_by_planet: dict[str, list[int]] = {p: [] for p in PLANET_ORDER}
    for h in range(1, 13):
        cusp_lord = cusps_kp[str(h)].get("sign_lord")
        if isinstance(cusp_lord, str) and cusp_lord in kp_owned_houses_by_planet:
            kp_owned_houses_by_planet[cusp_lord].append(h)

    planet_significations: dict[str, list[int]] = {}
    for p_name in PLANET_ORDER:
        star_lord = planet_star_sub_sub[p_name]["star_lord"]
        # S1: star lord's Placidus house
        star_occ = [planet_placidus_house[star_lord]] if star_lord in planet_placidus_house else []
        # S2: planet's own Placidus house
        pl_occ = [planet_placidus_house[p_name]] if p_name in planet_placidus_house else []
        # S3: star lord's ownership via Placidus cusps
        star_own = kp_owned_houses_by_planet.get(star_lord, [])
        # S4: planet's own ownership via Placidus cusps
        pl_own = kp_owned_houses_by_planet.get(p_name, [])
        combined: list[int] = []
        for source in [star_occ, pl_occ, star_own, pl_own]:
            for h in source:
                if h not in combined:
                    combined.append(h)
        planet_significations[p_name] = combined

    planet_signification_rows = [[p, planet_significations[p]] for p in PLANET_ORDER]
    planet_signification_table = build_markdown_table(
        ["Planet", "Houses Signified"],
        planet_signification_rows,
    )

    # House significators (A/B/C/D hierarchy) — KP: Placidus occupancy + Placidus cusp ownership
    house_significators: dict[str, dict[str, Any]] = {}
    house_sig_rows: list[list[Any]] = []
    for h in range(1, 13):
        occupants = [p for p in PLANET_ORDER if planet_placidus_house.get(p) == h]
        owner = cusps_kp[str(h)].get("sign_lord", "")
        level_a = [p for p in PLANET_ORDER if planet_star_sub_sub[p]["star_lord"] in occupants]
        level_b = occupants
        level_c = [p for p in PLANET_ORDER if planet_star_sub_sub[p]["star_lord"] == owner]
        level_d = [owner] if owner else []
        final: list[str] = []
        for arr in [level_a, level_b, level_c, level_d]:
            for p in arr:
                if p not in final:
                    final.append(p)
        house_significators[str(h)] = {
            "A": level_a,
            "B": level_b,
            "C": level_c,
            "D": level_d,
            "final": final,
        }
        house_sig_rows.append([h, final])
    house_significators_table = build_markdown_table(
        ["House", "Significators"],
        house_sig_rows,
    )

    # Nakshatra Nadi table
    nak_nadi_rows: list[list[Any]] = []
    for p in PLANET_ORDER:
        nak_nadi_rows.append([p, planet_star_sub_sub[p]["star_lord"], planet_star_sub_sub[p]["sub_lord"]])
    nakshatra_nadi_table = build_markdown_table(
        ["Planet", "Star Lord", "Sub Lord"],
        nak_nadi_rows,
    )

    # CIL Sub-Sub table (with Position Status)
    cil_sub_sub_rows: list[list[Any]] = []
    for p in PLANET_ORDER:
        star = planet_star_sub_sub[p]["star_lord"]
        sub = planet_star_sub_sub[p]["sub_lord"]
        sub_sub = planet_star_sub_sub[p]["sub_sub_lord"]
        in_own_star = star == p
        no_planet_in_its_stars = all(planet_star_sub_sub[x]["star_lord"] != p for x in PLANET_ORDER)
        position_status = in_own_star or no_planet_in_its_stars
        cil_sub_sub_rows.append([p, star, sub, sub_sub, "TRUE" if position_status else "FALSE"])
    cil_sub_sub_table = build_markdown_table(
        ["Planet", "Star", "Sub", "Sub Sub", "Position Status"],
        cil_sub_sub_rows,
    )

    # 4-step theory table
    four_step_rows: list[list[Any]] = []
    for p in PLANET_ORDER:
        star = planet_star_sub_sub[p]["star_lord"]
        sub = planet_star_sub_sub[p]["sub_lord"]
        sub_star = planet_star_sub_sub.get(sub, {}).get("star_lord", "")
        four_step_rows.append([p, star, sub, sub_star])
    four_step_table = build_markdown_table(
        ["Planet", "Star Lord", "Sub Lord", "Star Lord of Sub Lord"],
        four_step_rows,
    )

    # CIL Sub (Cuspal Interlinks from sub-sub chain)
    cil_sub_rows: list[list[Any]] = []
    cil_sub_data: dict[str, dict[str, Any]] = {}
    for h in range(1, 13):
        c = cusps_kp[str(h)]
        t1 = planet_significations.get(c.get("sub_sub_lord", ""), [])
        t2 = planet_significations.get(c.get("sub_lord", ""), [])
        t3 = planet_significations.get(c.get("star_lord", ""), [])
        t4 = planet_significations.get(c.get("sign_lord", ""), [])
        cil_sub_data[str(h)] = {"t1": t1, "t2": t2, "t3": t3, "t4": t4}
        cil_sub_rows.append([h, t1, t2, t3, t4])
    cil_sub_table = build_markdown_table(
        ["Cuspal", "Involvement (t1)", "Commitment (t2)", "Confirmation (t3)", "Conditioning (t4)"],
        cil_sub_rows,
    )

    # Ruling planets (natal)
    cl_asc = classify_kp_longitude(asc_deg_sidereal)
    asc_star, asc_sub = cl_asc["star_lord"], cl_asc["sub_lord"]
    cl_moon = classify_kp_longitude(moon_lon_natal)
    moon_star, moon_sub = cl_moon["star_lord"], cl_moon["sub_lord"]
    ruling_planets = {
        "asc_nakshatra_lord": asc_star,
        "asc_sign_lord": get_sign_lord_from_index(int(asc_deg_sidereal / 30)),
        "moon_nakshatra_lord": moon_star,
        "moon_sign_lord": get_sign_lord_from_index(int(moon_lon_natal / 30)),
        "day_lord": WEEKDAY_LORDS.get(dt_aware.weekday(), ""),
        "asc_sub_lord": asc_sub,
        "moon_sub_lord": moon_sub,
    }
    ruling_planets_table = build_markdown_table(
        ["Asc Nakshatra Lord", "Asc Sign Lord", "Moon Nakshatra Lord", "Moon Sign Lord", "Day Lord", "Asc Sub Lord", "Moon Sub Lord"],
        [[
            ruling_planets["asc_nakshatra_lord"],
            ruling_planets["asc_sign_lord"],
            ruling_planets["moon_nakshatra_lord"],
            ruling_planets["moon_sign_lord"],
            ruling_planets["day_lord"],
            ruling_planets["asc_sub_lord"],
            ruling_planets["moon_sub_lord"],
        ]],
    )

    # Current ruling planets (dynamic at runtime)
    # Reuse ayan_transit (KP ayanamsa for current moment)
    cuss_now_trop, ascmc_now_trop = swe.houses_ex(jd_now, lat, lon, b"P", 0)
    asc_now_sid = (ascmc_now_trop[0] - ayan_transit) % 360
    moon_now_trop = swe.calc_ut(jd_now, swe.MOON, swe.FLG_SWIEPH)[0][0]
    moon_now_sid = (moon_now_trop - ayan_transit) % 360
    cl_asc_now = classify_kp_longitude(asc_now_sid)
    asc_now_star, asc_now_sub = cl_asc_now["star_lord"], cl_asc_now["sub_lord"]
    cl_moon_now = classify_kp_longitude(moon_now_sid)
    moon_now_star, moon_now_sub = cl_moon_now["star_lord"], cl_moon_now["sub_lord"]
    now_weekday = now_utc.astimezone(dt_aware.tzinfo).weekday() if dt_aware.tzinfo else now_utc.weekday()
    current_ruling_planets = {
        "date": now_utc.isoformat(),
        "asc_star_lord": asc_now_star,
        "asc_sign_lord": get_sign_lord_from_index(int(asc_now_sid / 30)),
        "moon_star_lord": moon_now_star,
        "moon_sign_lord": get_sign_lord_from_index(int(moon_now_sid / 30)),
        "day_lord": WEEKDAY_LORDS.get(now_weekday, ""),
        "asc_sub_lord": asc_now_sub,
        "moon_sub_lord": moon_now_sub,
    }
    current_rp_table = build_markdown_table(
        ["Date", "Asc Star Lord", "Asc Sign Lord", "Moon Star Lord", "Moon Sign Lord", "Day Lord", "Asc Sub Lord", "Moon Sub Lord"],
        [[
            current_ruling_planets["date"],
            current_ruling_planets["asc_star_lord"],
            current_ruling_planets["asc_sign_lord"],
            current_ruling_planets["moon_star_lord"],
            current_ruling_planets["moon_sign_lord"],
            current_ruling_planets["day_lord"],
            current_ruling_planets["asc_sub_lord"],
            current_ruling_planets["moon_sub_lord"],
        ]],
    )

    # Fortuna table
    if is_day_birth:
        fortuna_lon = (asc_deg_sidereal + moon_lon_natal - sun_lon_natal) % 360
    else:
        fortuna_lon = (asc_deg_sidereal + sun_lon_natal - moon_lon_natal) % 360
    cl_f = classify_kp_longitude(fortuna_lon)
    f_star, f_sub, f_sub_sub = cl_f["star_lord"], cl_f["sub_lord"], cl_f["sub_sub_lord"]
    fortuna_data = {
        "degree": round(fortuna_lon, 4),
        "sign": ZODIAC_SIGNS[int(fortuna_lon / 30)],
        "sub": f_sub,
        "sub_sub": f_sub_sub,
        "kp_ayanamsa": round(ayanamsa, 8),
    }
    # KP Fortuna house uses Placidus cusp intervals (same occupancy logic used for planets).
    fortuna_house = 1
    for i in range(12):
        c_start = placidus_cusps[i]
        c_end = placidus_cusps[(i + 1) % 12]
        if c_end > c_start:
            if c_start <= fortuna_lon < c_end:
                fortuna_house = i + 1
                break
        else:
            if fortuna_lon >= c_start or fortuna_lon < c_end:
                fortuna_house = i + 1
                break
    fortuna_data["house"] = fortuna_house
    fortuna_table = build_markdown_table(
        ["Fortuna Degree", "Fortuna Sign", "Fortuna House", "Fortuna Sub", "Fortuna Sub Sub", "KP Ayanamsa"],
        [[fortuna_data["degree"], fortuna_data["sign"], fortuna_data["house"], fortuna_data["sub"], fortuna_data["sub_sub"], fortuna_data["kp_ayanamsa"]]],
    )

    # Badhaka / Maraka house identification from Lagna sign type.
    if asc_sign_id in [0, 3, 6, 9]:      # Movable
        badhaka_house = 11
    elif asc_sign_id in [1, 4, 7, 10]:   # Fixed
        badhaka_house = 9
    else:                                 # Dual
        badhaka_house = 7
    badhaka_maraka = {
        "lagna_sign": asc_sign_name,
        "lagna_type": "Movable" if asc_sign_id in [0, 3, 6, 9] else ("Fixed" if asc_sign_id in [1, 4, 7, 10] else "Dual"),
        "badhaka_house": badhaka_house,
        "maraka_houses": [2, 7],
    }
    badhaka_maraka_table = build_markdown_table(
        ["Lagna Sign", "Lagna Type", "Badhaka House", "Maraka Houses"],
        [[badhaka_maraka["lagna_sign"], badhaka_maraka["lagna_type"], badhaka_maraka["badhaka_house"], "2,7"]],
    )

    # Explicit nodal conjunction / agency decode.
    nodal_decode_rows: list[list[Any]] = []
    nodal_decode: dict[str, dict[str, Any]] = {}
    for node in ["Rahu", "Ketu"]:
        node_lon = planet_positions[node]
        node_sign_idx = int(node_lon / 30)
        node_star = planet_star_sub_sub[node]["star_lord"]
        node_sign_lord = get_sign_lord_from_index(node_sign_idx)

        conj_same_sign = [
            p for p in PLANET_ORDER
            if p != node and int(planet_positions[p] / 30) == node_sign_idx
        ]
        conj_same_star = [
            p for p in PLANET_ORDER
            if p != node and planet_star_sub_sub[p]["star_lord"] == node_star
        ]

        # Keep existing implementation style: conjunction priority first, then fallback to star/sign lord.
        if conj_same_sign:
            node_agent = ",".join(conj_same_sign)
            agency_source = "Conjunction (same sign)"
        elif conj_same_star:
            node_agent = ",".join(conj_same_star)
            agency_source = "Conjunction (same star)"
        elif node_star not in ["Rahu", "Ketu"]:
            node_agent = node_star
            agency_source = "Star Lord"
        else:
            node_agent = node_sign_lord
            agency_source = "Sign Lord"

        nodal_decode[node] = {
            "conjoined_with_sign": conj_same_sign,
            "conjoined_with_star": conj_same_star,
            "star_lord": node_star,
            "sign_lord": node_sign_lord,
            "agent": node_agent,
            "agency_source": agency_source,
        }
        nodal_decode_rows.append([
            node,
            ", ".join(conj_same_sign) if conj_same_sign else "-",
            ", ".join(conj_same_star) if conj_same_star else "-",
            node_star,
            node_sign_lord,
            node_agent,
            agency_source,
        ])

    nodal_decode_table = build_markdown_table(
        ["Node", "Conjoined With (Same Sign)", "Conjoined With (Same Star)", "Star Lord", "Sign Lord", "Node Agent", "Agency Source"],
        nodal_decode_rows,
    )

    # KP cusp aspect table: planet vs 12 cusps
    aspect_angles = {
        0: "Conj",
        30: "Semi-Sextile",
        45: "Semi-Square",
        60: "Sextile",
        90: "Square",
        120: "Trine",
        150: "Quincunx",
        180: "Opposition",
    }
    aspect_orb = 3.0
    kp_cusp_aspects: dict[str, dict[str, str]] = {}
    aspect_rows: list[list[Any]] = []
    for p in PLANET_ORDER:
        row = [p]
        kp_cusp_aspects[p] = {}
        for h in range(1, 13):
            cusp_lon = cusps_kp[str(h)]["lon"]
            diff = angle_diff_deg(planet_positions[p], cusp_lon)
            label = "-"
            for ang, name_ in aspect_angles.items():
                if abs(diff - ang) <= aspect_orb:
                    label = name_
                    break
            kp_cusp_aspects[p][str(h)] = label
            row.append(label)
        aspect_rows.append(row)
    cusp_aspects_table = build_markdown_table(
        ["Planet"] + [str(i) for i in range(1, 13)],
        aspect_rows,
    )

    # Build KP MasterPacket
    kp_master_packet: MasterPacket = {
        "system_role": "BRAHMA-DAIVAGYA",
        "name": name,
        "gender": gender,
        "birth_datetime": dt_aware.isoformat(),
        "birth_place": selected_city if selected_city else "Default Location",
        "timezone": sel_tz,
        "lagna_sign": asc_sign_name,
        "lagna_nakshatra": asc_nak,
        "moon_sign": ZODIAC_SIGNS[planet_sign_index.get("Moon", 0)],
        "moon_nakshatra": moon_nak_name,
        "d1_planets": d1_planets_kp,
        "bhava_positions": bhava_positions_kp,
        "special_points": special_points_kp,
        "ashtakavarga_sav": ashtakavarga_sav,
        "ashtakavarga_bav": ashtakavarga_bav,
        "cusps": cusps_kp,
        "planet_star_sub_lords": planetary_star_sub,
        "dasha": dasha_kp,  # type: ignore[assignment]
        "planet_avasthas": planet_avasthas_map,
        "panchang": {
            "tithi": panchang_data.get("tithi_name"),
            "yoga": panchang_data.get("yoga_name"),
            "karana": panchang_data.get("karana_name"),
        },
        "transit_as_of": transit_timestamp_utc.isoformat(),
        "transit_hits": transit_hits_kp,
        "planet_significations": planet_significations,
        "house_significators": house_significators,
        "ruling_planets": ruling_planets,
        "current_ruling_planets": current_ruling_planets,
        "fortuna": fortuna_data,
        "badhaka_maraka": badhaka_maraka,
        "nodal_decode": nodal_decode,
        "kp_cusp_engine_used": selected_cusp_engine,
    }

    kp_prediction = analyze_master_packet(kp_master_packet)

    structured_payload = {
        "natal_core": {
            "longitudes": {k: round(v, 4) for k, v in planet_positions.items()},
            "sign_index": planet_sign_index,
            "house_from_lagna": planet_house_from_lagna,
            "bhava_house": planet_bhava_house,
            "placidus_house": planet_placidus_house,
            "nakshatra_index": planet_nakshatra_index,
            "pada": planet_pada,
            "baladi_avastha": {k: v for k, v in planet_baladi.items()},
            "ascendant_lon": round(asc_deg_sidereal, 4),
            "special_points": {
                "64th_navamsa": {"lon": round((planet_positions.get("Moon", 0) + 210) % 360, 4), "sign_index": get_varga_sign((planet_positions.get("Moon", 0) + 210) % 360, 9)},
                "22nd_drekkana": {"lon": round(d22_lon, 4), "sign_index": d22_drekkana_sign_id},
            },
        },
        "panchang": panchang_data,
        "transit_monthly": monthly_packets,
        "kalapurusha_map": KALAPURUSHA_MAP,
        "bnn_module": bnn_structured,
        "unified_kundali": unified_kundali_structured,
        "ashtakavarga_sav": ashtakavarga_sav,
        "ashtakavarga_bav": ashtakavarga_bav,
        "cusps": cusps_kp,
        "planet_star_sub_lords": planetary_star_sub,
        "kp_astrology_matrix": {
            "ayanamsa_used": "KP (Krishnamurti)",
            "kp_cusp_engine_used": selected_cusp_engine,
            "placidus_cusps": cusps_kp,
            "planetary_star_sub_lords": planetary_star_sub,
            "rasi_chart_table": rasi_chart_table,
            "planets_table": planets_kp_table,
            "planet_signification_table": planet_signification_table,
            "house_significators_table": house_significators_table,
            "nakshatra_nadi_table": nakshatra_nadi_table,
            "cil_sub_sub_table": cil_sub_sub_table,
            "four_step_theory_table": four_step_table,
            "cil_sub_table": cil_sub_table,
            "ruling_planets_table": ruling_planets_table,
            "current_ruling_planets_table": current_rp_table,
            "fortuna_table": fortuna_table,
            "badhaka_maraka_table": badhaka_maraka_table,
            "nodal_decode_table": nodal_decode_table,
            "kp_cusp_aspects_table": cusp_aspects_table,
            "navamsa_check_table": navamsa_check_table,
            "planet_significations": planet_significations,
            "house_significators": house_significators,
            "ruling_planets": ruling_planets,
            "current_ruling_planets": current_ruling_planets,
            "fortuna": fortuna_data,
            "badhaka_maraka": badhaka_maraka,
            "nodal_decode": nodal_decode,
            "moon_dasha_balance_at_birth": dasha_kp.get("moon_dasha_balance_at_birth", {}),
            "kp_cusp_aspects": kp_cusp_aspects,
        },
        "kp_master_packet": kp_master_packet,
        "kp_prediction": kp_prediction,
    }
    
    structured_payload["cusp_engine_comparison_audit"] = cusp_engine_comparison_audit
    structured_payload["dasha_timeline_debug"] = dasha_debug_payload

    # --- YOGA ENGINE (Patch C) ---
    # Build retrograde_map for yoga strength_notes and drishti
    _retro_map = {
        p: info.get("kp_treat_as_retrograde", False)
        for p, info in planetary_star_sub.items()
    }

    # --- NATAL DRISHTI ---
    _natal_drishti_table = calculate_natal_drishti_table(
        planet_positions=planet_positions,
        d1_house_chart=unified_kundali_structured["houses"],
        lagna_sign=asc_sign_id,
        retrograde_map=_retro_map,
        node_drishti_mode="none"
    )
    _natal_house_drishti_summary = summarize_house_drishti(
        _natal_drishti_table,
        unified_kundali_structured["houses"],
        asc_sign_id
    )
    structured_payload["natal_drishti_table"] = _natal_drishti_table
    structured_payload["natal_house_drishti_summary"] = _natal_house_drishti_summary

    # asc_lon: tropical lagna longitude needed for D9 asc calculation
    _asc_lon_tropical = asc_deg_sidereal + ayanamsa   # reverse sidereal → tropical approx
    # Calculate if day birth (Sun above horizon -> houses 7 to 12 from lagna)
    _sun_sign = int(planet_positions["Sun"] / 30)
    _sun_house_from_lagna = (_sun_sign - asc_sign_id + 12) % 12 + 1
    _is_day_birth = 7 <= _sun_house_from_lagna <= 12
    
    _applicable_yogas, _yoga_rule_matrix = detect_special_yogas(
        planet_positions=planet_positions,
        asc_sign=asc_sign_id,
        asc_lon=_asc_lon_tropical,
        retrograde_map=_retro_map,
        gender=gender,
        is_day_birth=_is_day_birth,
    )
    structured_payload["special_yogas"] = _applicable_yogas
    structured_payload["yoga_rule_matrix"] = _yoga_rule_matrix
    
    # Calculate coverage
    _confirmed = sum(1 for r in _yoga_rule_matrix if r["final_status"] == "confirmed")
    _partial = sum(1 for r in _yoga_rule_matrix if r["final_status"] == "partial_d1_only")
    _navamsa = sum(1 for r in _yoga_rule_matrix if r["final_status"] == "navamsa_support_only_debug")
    _absent = sum(1 for r in _yoga_rule_matrix if r["final_status"] == "absent")
    
    structured_payload["yoga_rule_coverage"] = {
        "total_rules_checked": len(_yoga_rule_matrix),
        "applicable_count": len(_applicable_yogas),
        "confirmed_count": _confirmed,
        "partial_d1_only_count": _partial,
        "navamsa_support_only_count": _navamsa,
        "absent_count": _absent
    }
    
    # Raw planet longitudes for UI-side yoga recompute if needed
    structured_payload["_planet_positions_raw"] = {
        p: round(lon, 6) for p, lon in planet_positions.items()
    }

    # --- AUDIT: Cusp Sub-Sub Lords --- (Issue 2)
    cusp_subsub_audit = []
    for h in range(1, 13):
        c = cusps_kp[str(h)]
        c_lon = c["lon"]
        cl = classify_kp_longitude(c_lon)
        cusp_subsub_audit.append({
            "cusp": h,
            "lon": round(c_lon, 6),
            "nakshatra": c["nakshatra"],
            "star_lord": cl["star_lord"],
            "offset_in_star_years": cl["offset_in_star"],
            "sub_start_years": cl["sub_start"],
            "sub_end_years": cl["sub_end"],
            "sub_lord": cl["sub_lord"],
            "offset_in_sub_years": cl["offset_in_sub"],
            "sub_sub_lord": cl["sub_sub_lord"],
            "stored_star": c["star_lord"],
            "stored_sub": c["sub_lord"],
            "stored_subsub": c["sub_sub_lord"],
            "match": (cl["star_lord"] == c["star_lord"] and cl["sub_lord"] == c["sub_lord"] and cl["sub_sub_lord"] == c["sub_sub_lord"]),
        })
    structured_payload["cusp_subsub_audit"] = cusp_subsub_audit

    # --- AUDIT: Retrograde / Motion --- (Issue 1)
    retrograde_motion_audit = []
    for p_name in PLANET_ORDER:
        p_payload = planetary_star_sub.get(p_name, {})
        retrograde_motion_audit.append({
            "planet": p_name,
            "speed": round(p_payload.get("speed", 0), 6),
            "motion": p_payload.get("motion", ""),
            "is_backward_motion": p_payload.get("is_backward_motion", False),
            "is_retrograde_by_speed": p_payload.get("is_retrograde_by_speed", False),
            "kp_treat_as_retrograde": p_payload.get("kp_treat_as_retrograde", False),
            "display_motion": p_payload.get("display_motion", ""),
        })
    structured_payload["retrograde_motion_audit"] = retrograde_motion_audit

    # --- AUDIT: Dasha Epoch --- uses exactly the same formula as generate_vimshottari_timeline
    import math as _math_audit
    _NAKSHATRA_SPAN_AUDIT = Fraction(40, 3)
    _ml_frac_audit = Fraction(str(Decimal(str(moon_lon_dasha % 360))))
    _nak_index_audit = _math_audit.floor(_ml_frac_audit / _NAKSHATRA_SPAN_AUDIT)
    _offset_in_nak_audit = _ml_frac_audit - (_nak_index_audit * _NAKSHATRA_SPAN_AUDIT)
    _elapsed_frac_audit = _offset_in_nak_audit / _NAKSHATRA_SPAN_AUDIT
    _remaining_frac_audit = 1 - _elapsed_frac_audit
    _md_lord_audit = NAKSHATRA_RULERS[_nak_index_audit]
    _md_yrs_audit = dict(VIMSHOTTARI_SEQUENCE)[_md_lord_audit]
    _birth_md_total_days_audit = _md_yrs_audit * DASHA_YEAR_DAYS
    _birth_md_elapsed_days_audit = float(_birth_md_total_days_audit) * float(_elapsed_frac_audit)
    _birth_md_balance_days_audit = float(_birth_md_total_days_audit) * float(_remaining_frac_audit)
    from datetime import timedelta as _td_audit
    _birth_md_start_dt_audit = dt_aware - _td_audit(days=_birth_md_elapsed_days_audit)
    _birth_md_end_dt_audit = dt_aware + _td_audit(days=_birth_md_balance_days_audit)
    dasha_epoch_audit = {
        "dasha_engine_version": "canonical_v2_birth_epoch_datetime",
        "dasha_ayanamsha_mode": DASHA_AYANAMSHA_MODE,
        "dasha_ayanamsha_value": round(dasha_ayanamsha_value, 6),
        "chart_ayanamsha_mode": "SIDM_KRISHNAMURTI_VP291",
        "chart_ayanamsha_value": round(ayanamsa, 6),
        "chart_moon_longitude": round(chart_moon_lon, 6),
        "dasha_moon_longitude": round(moon_lon_dasha, 6),
        "moon_difference_arcmin": round((moon_lon_dasha - chart_moon_lon) * 60, 4),
        "moon_difference_arcsec": round((moon_lon_dasha - chart_moon_lon) * 3600, 4),
        "birth_local_datetime": dt_aware.isoformat(),
        "birth_utc_datetime": utc_dt.isoformat(),
        "birth_md_lord": _md_lord_audit,
        "birth_md_balance_days": round(_birth_md_balance_days_audit, 4),
        "birth_md_start_dt": _birth_md_start_dt_audit.strftime("%d-%m-%Y"),
        "birth_md_end_dt": _birth_md_end_dt_audit.strftime("%d-%m-%Y"),
        "rendered_rahu_mars_moon_row": _rahu_mars_moon_row or "NOT FOUND",
        "current_selected_row": (
            f"{timeline_entries[current_entry_idx]['start_solar']} | "
            f"{timeline_entries[current_entry_idx]['end_solar']} | "
            f"{timeline_entries[current_entry_idx]['md']} | "
            f"{timeline_entries[current_entry_idx]['ad']} | "
            f"{timeline_entries[current_entry_idx]['pd']}"
        ) if current_entry_idx is not None else "None",
        "expected_reference_row": "16-05-2025 | 17-06-2025 | Rahu | Mars | Moon",
    }
    structured_payload["dasha_epoch_audit"] = dasha_epoch_audit

    # --- Current transit aspect/hit tables in packet --- (Issue 4)
    if monthly_packets:
        _cp = monthly_packets[0]
        structured_payload["current_transit_aspect_impacts"] = _cp.get("monthly_aspect_impacts", [])
        structured_payload["current_transit_degree_hits"] = _cp.get("monthly_degree_hits", [])

    return (lagna_str, d1_table, d9_table, bhava_table, varga_table, moon_nak_name, 
            ishtakala_ghati, day_len_ghati, sav_str, avastha_str, upagraha_str,
            d64_sign_name, d22_sign_name, transit_str, transit_timestamp_utc, natal_data_str, 
            dasha_str, panchang_str, timeline_summary, full_timeline_data, structured_payload, bnn_display_str, unified_kundali_table)

# ==========================================
# 3. WEB INTERFACE
# ==========================================

st.set_page_config(page_title="Vedic Calculation Engine", page_icon="🕉️", layout="wide")
st.title("🕉️ Vedic Chart Calculator")
st.markdown("Generates **Brahma-Daivagya** Prompt with **Time Variables & Strengths**.")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Name", value="", placeholder="Enter name")
    dob = st.date_input("Date of Birth", value=None, min_value=datetime.date(1910, 1, 1))
    gender = st.selectbox("Gender", ["", "Male", "Female", "Other"], index=0) 

with col2:
    # Custom time input with validation
    st.markdown("**Time of Birth**")
    time_col1, time_col2 = st.columns(2)
    with time_col1:
        hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=None, step=1, help="Enter hour (0-23)")
    with time_col2:
        minute = st.number_input("Minute (0-59)", min_value=0, max_value=59, value=None, step=1, help="Enter minute (0-59)")
    
    # Create time object if both are provided
    if hour is not None and minute is not None:
        tob = datetime.time(hour, minute)
    else:
        tob = None

# Location
df_cities = load_city_data()
lat, lon = None, None

st.write("---")
st.markdown("### 🌍 Location Search (Required for Ishtakala)")
selected_city = None

# High-Performance Indexed Search using streamlit-searchbox (if available)
if df_cities is not None and not df_cities.empty:
    city_index = build_city_index(df_cities)

    col_city1, col_city2 = st.columns(2)

    with col_city1:
        if HAS_SEARCHBOX:
            st.caption("🔎 Fast search (recommended)")

            def search_function(search_term):
                return search_city(search_term, city_index)

            selected_result = st_searchbox(
                search_function,
                key="city_searchbox",
                placeholder="Type city name (min 3 characters)...",
                label="Search City:",
            )

            if selected_result:
                if isinstance(selected_result, tuple) and len(selected_result) == 2:
                    lat, lon = selected_result
                    matching_rows = df_cities[
                        (abs(df_cities["latitude"] - lat) < 0.0001)
                        & (abs(df_cities["longitude"] - lon) < 0.0001)
                    ]
                    if not matching_rows.empty:
                        selected_city = matching_rows.iloc[0]["display_name"]
                        st.success(f"Selected: {selected_city} ({lat:.4f}, {lon:.4f})")
                    else:
                        st.warning("City coordinates found but display name not matched.")
                else:
                    st.error("Unexpected result format from searchbox.")
        else:
            st.caption("🔎 Fast search is unavailable (dependency missing).")

    # Always offer a simple dropdown as a fallback / alternative
    with col_city2:
        st.caption("📂 Simple dropdown (type to filter)")
        city_list: list[str] = [""] + df_cities["display_name"].tolist()
        dropdown_city = st.selectbox(
            "Select City:",
            city_list,
            index=0,
            help="Start typing the city name to filter the list.",
            key="city_selectbox",
        )
        if dropdown_city:
            row = df_cities[df_cities["display_name"] == dropdown_city].iloc[0]
            lat, lon = float(row["latitude"]), float(row["longitude"])
            selected_city = dropdown_city
            st.success(f"Selected: {selected_city} ({lat:.4f}, {lon:.4f})")

# Manual Override
with st.expander("📍 Manual Coordinates"):
    lat = st.number_input("Lat", value=lat if lat else 0.0, format="%.4f")
    lon = st.number_input("Lon", value=lon if lon else 0.0, format="%.4f")

st.write("---")
st.subheader("🕒 Timezone")
common_tz = ["Asia/Kolkata", "UTC", "America/New_York", "Europe/London", "Australia/Sydney"]
sel_tz = st.selectbox("Select Timezone:", common_tz, index=0)

st.write("---")
st.subheader("⚙️ Options")
include_structured_json = st.checkbox("Include Structured JSON Payload (for LLM)", value=False)

if st.button("Generate Prompt"):
    # Check if all fields are empty
    name_empty = not name or name.strip() == ""
    dob_empty = dob is None  # Check if date is None
    tob_empty = tob is None  # Check if time is None
    location_empty = (lat is None or lat == 0.0) and (lon is None or lon == 0.0)
    
    # Check if ANY field has data
    has_any_data = not name_empty or not dob_empty or not tob_empty or not location_empty
    
    # If everything is empty, show only headers
    if name_empty and dob_empty and tob_empty and location_empty:
        final_prompt = """SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

I. CONTEXT & DATA SOURCE
You are the Brahma-Daivagya. Use the provided MASTER DATA PACKET to perform "Hit Theory" analysis.
Do not calculate planetary degrees. Use the pre-calculated values below.

*** MASTER DATA PACKET (PRE-CALCULATED) ***

1. NATAL CHART (Hardware):


2. SPECIAL POINTS (Vulnerable Spots):
- 64th Navamsa Sign: 
- 22nd Drekkana Sign: 
- Upagrahas:


3. ASHTAKAVARGA (Bhinna + Sarva):

(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)

4. CURRENT TIMING (Software - Dasha System):

(Note: Hit Theory is the "Trigger," but Dasha is the "Gun." A hit usually doesn't manifest unless the Dasha Lord is involved.)

5. TIME VARIABLES:
- Birth Ghati: 
- Day Duration: 
- Planetary Avasthas (Moods):


6. PANCHANG (Five Limbs of Time):

- Tithi: Crucial for relationship and emotional depth
- Yoga: Crucial for health and innate nature
- Karana: Crucial for career/work success

7. TRANSIT SNAPSHOT (Current Real-Time Positions):
As of: 

(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)

8. D1 HOUSE CHART (Rashi - Whole Sign):


9. BHAVA CHALIT CHART (Sripati - House Shifts):

(Note: If a planet shows "[Rashi HX → Bhava HY]", it has shifted houses. This is critical for prediction.)

10. SHODASHAVARGA MATRIX (16 CHARTS):


11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):


12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):


Lagna Summary: 
Moon Nakshatra: 

Name: 
Gender: 
Date: 
Time: 
Place: 
Timezone: 

INSTRUCTION:
"O Brahma-Daivagya, align the heavens using the Master Data Packet.
1. Cross-reference the Transit Snapshot with the Natal Chart to find specific hits.
2. If a hit occurs, check the SAV score of that sign.
3. Check if the planet involves the 64th Navamsa or 22nd Drekkana.
4. Note: Eclipse status checks the middle of the month; precise dates may vary by +/- 14 days.
5. Synthesize the prediction.
"""
        st.subheader("Copy This Prompt:")
        st.code(final_prompt, language="markdown")
    else:
        # If any field has data, require all fields and calculate
        # If name is empty, do NOT use defaults - show only headers
        if name_empty or not name or name.strip() == "":
            # No defaults - show blank headers only
            final_prompt = """SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

I. CONTEXT & DATA SOURCE
You are the Brahma-Daivagya. Use the provided MASTER DATA PACKET to perform "Hit Theory" analysis.
Do not calculate planetary degrees. Use the pre-calculated values below.

*** MASTER DATA PACKET (PRE-CALCULATED) ***

1. NATAL CHART (Hardware):


2. SPECIAL POINTS (Vulnerable Spots):
- 64th Navamsa Sign: 
- 22nd Drekkana Sign: 
- Upagrahas:


3. ASHTAKAVARGA (Bhinna + Sarva):

(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)

4. CURRENT TIMING (Software - Dasha System):

(Note: Hit Theory is the "Trigger," but Dasha is the "Gun." A hit usually doesn't manifest unless the Dasha Lord is involved.)

5. TIME VARIABLES:
- Birth Ghati: 
- Day Duration: 
- Planetary Avasthas (Moods):


6. PANCHANG (Five Limbs of Time):

- Tithi: Crucial for relationship and emotional depth
- Yoga: Crucial for health and innate nature
- Karana: Crucial for career/work success

7. TRANSIT SNAPSHOT (Current Real-Time Positions):
As of: 

(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)

8. D1 HOUSE CHART (Rashi - Whole Sign):


9. BHAVA CHALIT CHART (Sripati - House Shifts):

(Note: If a planet shows "[Rashi HX → Bhava HY]", it has shifted houses. This is critical for prediction.)

10. SHODASHAVARGA MATRIX (16 CHARTS):


11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):


12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):


Lagna Summary: 
Moon Nakshatra: 

Name: 
Gender: 
Date: 
Time: 
Place: 
Timezone: 

INSTRUCTION:
"O Brahma-Daivagya, align the heavens using the Master Data Packet.
1. Cross-reference the Transit Snapshot with the Natal Chart to find specific hits.
2. If a hit occurs, check the SAV score of that sign.
3. Check if the planet involves the 64th Navamsa or 22nd Drekkana.
4. Note: Eclipse status checks the middle of the month; precise dates may vary by +/- 14 days.
5. Synthesize the prediction.
"""
            st.subheader("Copy This Prompt:")
            st.code(final_prompt, language="markdown")
        else:
            # Name is present - use defaults for coordinates if needed, then calculate
            if lat is None or lat == 0.0:
                lat = 28.6139  # Default: New Delhi
            if lon is None or lon == 0.0:
                lon = 77.2090  # Default: New Delhi
            if selected_city is None:
                selected_city = ""
            
            # Validate required fields before proceeding
            if dob is None:
                st.error("Date of Birth is required. Please enter a valid date.")
                st.stop()
            if tob is None:
                st.error("Time of Birth is required. Please enter both hour and minute.")
                st.stop()
            
            # Show all actual values
            name_display = name
            gender_display = gender
            dob_display = dob.strftime('%d/%m/%Y')
            tob_display = tob.strftime('%H:%M')
            place_display = selected_city if selected_city else 'Default Location'
            timezone_display = sel_tz
            
            local_tz = pytz.timezone(sel_tz)
            dt_naive = datetime.datetime.combine(dob, tob)
            dt_aware = local_tz.localize(dt_naive)
            
            # Calculate All with renamed function
            (lagna, d1, d9, bhava_chalit, vargas, nak, ishta, dinamaana, sav, avasthas, upagrahas, 
             d64, d22, transits, transit_timestamp_utc, natal_table, dasha_info, panchang_info, timeline_full, full_timeline_data, structured_payload, bnn_display_str, unified_kundali) = calculate_vedic_charts(name_display, dt_aware, lat, lon)
            
            # Convert transit timestamp to user's timezone
            transit_timestamp = transit_timestamp_utc.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            
            # Store all calculation results in session_state to persist across reruns
            st.session_state.calc_results = {
                'lagna': lagna,
                'd1': d1,
                'd9': d9,
                'bhava_chalit': bhava_chalit,
                'vargas': vargas,
                'nak': nak,
                'ishta': ishta,
                'dinamaana': dinamaana,
                'sav': sav,
                'avasthas': avasthas,
                'upagrahas': upagrahas,
                'd64': d64,
                'd22': d22,
                'transits': transits,
                'transit_timestamp': transit_timestamp,
                'natal_table': natal_table,
                'dasha_info': dasha_info,
                'panchang_info': panchang_info,
                'timeline_full': timeline_full,
                'full_timeline_data': full_timeline_data,
                'structured_payload': structured_payload,
                'bnn_display_str': bnn_display_str,
                'unified_kundali': unified_kundali,
                'name_display': name_display,
                'gender_display': gender_display,
                'dob_display': dob_display,
                'tob_display': tob_display,
                'place_display': place_display,
                'timezone_display': timezone_display,
            }
            
            
            # Calculate total SAV score from the Total row in the BAV/SAV table
            _total_line = [ln for ln in sav.split('\n') if 'Total' in ln]
            total_sav_score = sum(int(n) for n in re.findall(r'\d+', _total_line[0])) if _total_line else 0
            
            # Extract BNN Kundali only (Directional Groups and Orbital Order)
            bnn_lines = bnn_display_str.split('\n')
            bnn_kundali_lines = []
            in_kundali_section = False
            for line in bnn_lines:
                if "DIRECTIONAL GROUPS" in line:
                    in_kundali_section = True
                    bnn_kundali_lines.append(line)
                elif "ORBITAL ORDER" in line:
                    in_kundali_section = True
                    bnn_kundali_lines.append(line)
                elif in_kundali_section:
                    if line.startswith("###") and "RETROGRADE" in line:
                        break
                    bnn_kundali_lines.append(line)
            bnn_kundali_only = "\n".join(bnn_kundali_lines) if bnn_kundali_lines else "No BNN Kundali data available"
            
            # Format full timeline
            full_timeline_rows = []
            full_timeline_rows.append("| Start (Solar) | End (Solar) | Start (Savana) | End (Savana) | MD | AD | PD | Duration (Days) |")
            full_timeline_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for entry in full_timeline_data:
                full_timeline_rows.append(f"| {entry.get('start_solar', 'N/A')} | {entry.get('end_solar', 'N/A')} | {entry.get('start_savana', 'N/A')} | {entry.get('end_savana', 'N/A')} | {entry['md']} | {entry['ad']} | {entry['pd']} | {entry.get('duration_solar_days', 0):.1f} |")
            full_timeline_table = "\n".join(full_timeline_rows)
            
            # Build three separate sections
            # Section 1: Charts
            charts_section = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

I. CHARTS SECTION

1. NATAL CHART (Hardware):
{natal_table}

8. D1 HOUSE CHART (Rashi - Whole Sign):
{d1}

9. BHAVA CHALIT CHART (Sripati - House Shifts):
{bhava_chalit}
(Note: If a planet shows "[Rashi HX → Bhava HY]", it has shifted houses. This is critical for prediction.)

10. SHODASHAVARGA MATRIX (16 CHARTS):
{vargas}

13. UNIFIED BNN-PARASHARI KUNDALI (The Snapshot):
{unified_kundali}
(Note: This table uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility. Bhava Shift markers [→ HX] indicate planets that moved to different houses in Bhava Chalit chart. For Direction/Trines (BNN), use the Sign column. For Career/Outcome (Parashari), check Bhava Shift if present.)

14. BNN KUNDALI ONLY:
{bnn_kundali_only}

Lagna Summary: {lagna}
Moon Nakshatra: {nak}

Name: {name_display}
Gender: {gender_display}
Date: {dob_display}
Time: {tob_display}
Place: {place_display}
Timezone: {timezone_display}
"""
            
            # Section 2: Inner Calculations
            inner_calculations_section = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

II. INNER CALCULATIONS SECTION

2. SPECIAL POINTS (Vulnerable Spots):
- 64th Navamsa Sign: {d64}
- 22nd Drekkana Sign: {d22}
- Upagrahas:
{upagrahas}

3. ASHTAKAVARGA (Bhinna + Sarva):
{sav}
Total SAV Score: {total_sav_score} points
(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)

4. CURRENT TIMING (Software - Dasha System):
{dasha_info}
(Note: Hit Theory is the "Trigger," but Dasha is the "Gun." A hit usually doesn't manifest unless the Dasha Lord is involved.)

5. TIME VARIABLES:
- Birth Ghati: {ishta:.2f}
- Day Duration: {dinamaana:.2f}
- Planetary Avasthas (Moods):
{avasthas}

6. PANCHANG (Five Limbs of Time):
{panchang_info}
- Tithi: Crucial for relationship and emotional depth
- Yoga: Crucial for health and innate nature
- Karana: Crucial for career/work success

7. TRANSIT SNAPSHOT (Current Real-Time Positions):
As of: {transit_timestamp}
{transits}
(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)

12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):
{bnn_display_str}
(Note: BNN uses Directional Grouping and Orbital Order instead of House-based analysis. Retrograde planets project into previous sign. Friend/Enemy relationships follow Deva/Asura groups, not Parashari Tatkalik Maitri.)

Name: {name_display}
Gender: {gender_display}
Date: {dob_display}
Time: {tob_display}
Place: {place_display}
Timezone: {timezone_display}
"""
            
            # Section 3: Timeline (will be updated based on toggle)
            timeline_section_base = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

III. VIMSHOTTARI DASHA TIMELINE SECTION

11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):

"""
            
            # Original final_prompt for backward compatibility (if needed)
            final_prompt = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

I. CONTEXT & DATA SOURCE
You are the Brahma-Daivagya. Use the provided MASTER DATA PACKET to perform "Hit Theory" analysis.
Do not calculate planetary degrees. Use the pre-calculated values below.

*** MASTER DATA PACKET (PRE-CALCULATED) ***

1. NATAL CHART (Hardware):
{natal_table}

2. SPECIAL POINTS (Vulnerable Spots):
- 64th Navamsa Sign: {d64}
- 22nd Drekkana Sign: {d22}
- Upagrahas:
{upagrahas}

3. ASHTAKAVARGA (Bhinna + Sarva):
{sav}
(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)

4. CURRENT TIMING (Software - Dasha System):
{dasha_info}
(Note: Hit Theory is the "Trigger," but Dasha is the "Gun." A hit usually doesn't manifest unless the Dasha Lord is involved.)

5. TIME VARIABLES:
- Birth Ghati: {ishta:.2f}
- Day Duration: {dinamaana:.2f}
- Planetary Avasthas (Moods):
{avasthas}

6. PANCHANG (Five Limbs of Time):
{panchang_info}
- Tithi: Crucial for relationship and emotional depth
- Yoga: Crucial for health and innate nature
- Karana: Crucial for career/work success

7. TRANSIT SNAPSHOT (Current Real-Time Positions):
As of: {transit_timestamp}
{transits}
(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)

8. D1 HOUSE CHART (Rashi - Whole Sign):
{d1}

9. BHAVA CHALIT CHART (Sripati - House Shifts):
{bhava_chalit}
(Note: If a planet shows "[Rashi HX → Bhava HY]", it has shifted houses. This is critical for prediction.)

10. SHODASHAVARGA MATRIX (16 CHARTS):
{vargas}

11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):
{timeline_full}

12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):
{bnn_display_str}
(Note: BNN uses Directional Grouping and Orbital Order instead of House-based analysis. Retrograde planets project into previous sign. Friend/Enemy relationships follow Deva/Asura groups, not Parashari Tatkalik Maitri.)

13. UNIFIED BNN-PARASHARI KUNDALI (The Snapshot):
{unified_kundali}
(Note: This table uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility. Bhava Shift markers [→ HX] indicate planets that moved to different houses in Bhava Chalit chart. For Direction/Trines (BNN), use the Sign column. For Career/Outcome (Parashari), check Bhava Shift if present.)

Lagna Summary: {lagna}
Moon Nakshatra: {nak}

Name: {name_display}
Gender: {gender_display}
Date: {dob_display}
Time: {tob_display}
Place: {place_display}
Timezone: {timezone_display}

INSTRUCTION:
"O Brahma-Daivagya, align the heavens using the Master Data Packet.
1. Cross-reference the Transit Snapshot with the Natal Chart to find specific hits.
2. If a hit occurs, check the SAV score of that sign.
3. Check if the planet involves the 64th Navamsa or 22nd Drekkana.
4. Note: Eclipse status checks the middle of the month; precise dates may vary by +/- 14 days.
5. Synthesize the prediction.
"""
            # Hack to inject the variable inside f-string locally
            final_prompt = final_prompt.replace("{natal_table}", natal_table)
            
            # Implement Exclusive Output Switch
            if include_structured_json:
                # Optional: Advanced Condensing Logic - Remove None/empty string values
                def remove_null_values(obj):
                    """Recursively remove keys with None or empty string values (lossless minification)."""
                    if isinstance(obj, dict):
                        return {k: remove_null_values(v) for k, v in obj.items() 
                                if v is not None and v != ""}
                    elif isinstance(obj, list):
                        return [remove_null_values(item) for item in obj]
                    return obj
                
                # Apply condensing (optional - can be disabled if needed)
                condensed_payload = remove_null_values(structured_payload)
                
                # Smart Compression: Lossless Minification (no indent, compact separators)
                json_str = json.dumps(condensed_payload, separators=(',', ':'), ensure_ascii=False)
                
                # Exclusive mode: Only JSON, no text prompt
                final_prompt = json_str
            else:
                # Standard mode: Add structured JSON if requested (legacy behavior)
                # Note: This branch is now only for backward compatibility
                # The exclusive switch above handles the JSON-only mode
                pass
            
            # Sidebar for full timeline reference (only show if we have calculated data)
            if 'calc_results' in st.session_state:
                with st.sidebar:
                    st.markdown("### 📅 Full Dasha Timeline Reference")
                    if st.button("Show All Mahadasha & Antardasha", key="show_full_timeline_sidebar"):
                        st.session_state['show_timeline_sidebar'] = True
                    
                    if st.session_state.get('show_timeline_sidebar', False):
                        st.markdown("**Full 80-Year Timeline (All Entries)**")
                        # Format full timeline from stored data
                        calc_sidebar = st.session_state.calc_results
                        full_timeline_rows = []
                        full_timeline_rows.append("| Start (Solar) | End (Solar) | Start (Savana) | End (Savana) | MD | AD | PD |")
                        full_timeline_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
                        for entry in calc_sidebar['full_timeline_data'][:500]:  # Limit to 500 for performance
                            full_timeline_rows.append(f"| {entry.get('start_solar', 'N/A')} | {entry.get('end_solar', 'N/A')} | {entry.get('start_savana', 'N/A')} | {entry.get('end_savana', 'N/A')} | {entry['md']} | {entry['ad']} | {entry['pd']} |")
                        full_timeline_table_sidebar = "\n".join(full_timeline_rows)
                        st.markdown(full_timeline_table_sidebar)
                        if st.button("Close Timeline", key="close_timeline"):
                            st.session_state['show_timeline_sidebar'] = False

            # Results are stored in session_state above - display logic is handled outside button block

# Display logic OUTSIDE button block - always runs, even when checkboxes are toggled
# This ensures data persists when toggling sections
if 'calc_results' in st.session_state:
    calc = st.session_state.calc_results
    
    # Initialize session state for section visibility and timeline toggle
    if 'show_charts' not in st.session_state:
        st.session_state.show_charts = True
    if 'show_inner_calculations' not in st.session_state:
        st.session_state.show_inner_calculations = True
    if 'show_timeline' not in st.session_state:
        st.session_state.show_timeline = True
    if 'show_full_timeline' not in st.session_state:
        st.session_state.show_full_timeline = False
    
    # Section filter checkboxes - placed right after Generate Prompt button area
    st.write("---")
    st.caption("🔍 Filter sections to show/hide in the complete prompt below:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.show_charts = st.checkbox("📊 Show Charts (Sections 1, 8, 9, 10, 13)", value=st.session_state.show_charts, key="cb_charts")
    with col2:
        st.session_state.show_inner_calculations = st.checkbox("🔬 Show Inner Calculations (Sections 2, 3, 4, 5, 6, 7, 12)", value=st.session_state.show_inner_calculations, key="cb_inner")
    with col3:
        st.session_state.show_timeline = st.checkbox("📅 Show Timeline (Section 11)", value=st.session_state.show_timeline, key="cb_timeline")
    
    # Timeline toggle (only shown if timeline section is selected)
    if st.session_state.show_timeline:
        st.session_state.show_full_timeline = st.checkbox("Show Full 80-Year Timeline", value=st.session_state.show_full_timeline, key="cb_full_timeline")
    
    
    # Rebuild total SAV score from the Total row in the BAV/SAV table
    _total_line = [ln for ln in calc['sav'].split('\n') if 'Total' in ln]
    total_sav_score = sum(int(n) for n in re.findall(r'\d+', _total_line[0])) if _total_line else 0
    
    # Extract BNN Kundali only
    bnn_lines = calc['bnn_display_str'].split('\n')
    bnn_kundali_lines = []
    in_kundali_section = False
    for line in bnn_lines:
        if "DIRECTIONAL GROUPS" in line:
            in_kundali_section = True
            bnn_kundali_lines.append(line)
        elif "ORBITAL ORDER" in line:
            in_kundali_section = True
            bnn_kundali_lines.append(line)
        elif in_kundali_section:
            if line.startswith("###") and "RETROGRADE" in line:
                break
            bnn_kundali_lines.append(line)
    bnn_kundali_only = "\n".join(bnn_kundali_lines) if bnn_kundali_lines else "No BNN Kundali data available"
    
    # Format full timeline
    full_timeline_rows = []
    full_timeline_rows.append("| Start (Solar) | End (Solar) | Start (Savana) | End (Savana) | MD | AD | PD | Duration (Days) |")
    full_timeline_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for entry in calc['full_timeline_data']:
        full_timeline_rows.append(f"| {entry.get('start_solar', 'N/A')} | {entry.get('end_solar', 'N/A')} | {entry.get('start_savana', 'N/A')} | {entry.get('end_savana', 'N/A')} | {entry['md']} | {entry['ad']} | {entry['pd']} | {entry.get('duration_solar_days', 0):.1f} |")
    full_timeline_table = "\n".join(full_timeline_rows)
    
    # Build sections
    charts_section = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

I. CHARTS SECTION

1. NATAL CHART (Hardware):
{calc['natal_table']}

8. D1 HOUSE CHART (Rashi - Whole Sign):
{calc['d1']}

9. BHAVA CHALIT CHART (Sripati - House Shifts):
{calc['bhava_chalit']}
(Note: If a planet shows "[Rashi HX → Bhava HY]", it has shifted houses. This is critical for prediction.)

10. SHODASHAVARGA MATRIX (16 CHARTS):
{calc['vargas']}

13. UNIFIED BNN-PARASHARI KUNDALI (The Snapshot):
{calc['unified_kundali']}
(Note: This table uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility. Bhava Shift markers [→ HX] indicate planets that moved to different houses in Bhava Chalit chart. For Direction/Trines (BNN), use the Sign column. For Career/Outcome (Parashari), check Bhava Shift if present.)

14. BNN KUNDALI ONLY:
{bnn_kundali_only}

Lagna Summary: {calc['lagna']}
Moon Nakshatra: {calc['nak']}

Name: {calc['name_display']}
Gender: {calc['gender_display']}
Date: {calc['dob_display']}
Time: {calc['tob_display']}
Place: {calc['place_display']}
Timezone: {calc['timezone_display']}
"""
    
    inner_calculations_section = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

II. INNER CALCULATIONS SECTION

2. SPECIAL POINTS (Vulnerable Spots):
- 64th Navamsa Sign: {calc['d64']}
- 22nd Drekkana Sign: {calc['d22']}
- Upagrahas:
{calc['upagrahas']}

3. ASHTAKAVARGA (Bhinna + Sarva):
{calc['sav']}
Total SAV Score: {total_sav_score} points
(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)

4. CURRENT TIMING (Software - Dasha System):
{calc['dasha_info']}
(Note: Hit Theory is the "Trigger," but Dasha is the "Gun." A hit usually doesn't manifest unless the Dasha Lord is involved.)

5. TIME VARIABLES:
- Birth Ghati: {calc['ishta']:.2f}
- Day Duration: {calc['dinamaana']:.2f}
- Planetary Avasthas (Moods):
{calc['avasthas']}

6. PANCHANG (Five Limbs of Time):
{calc['panchang_info']}
- Tithi: Crucial for relationship and emotional depth
- Yoga: Crucial for health and innate nature
- Karana: Crucial for career/work success

7. TRANSIT SNAPSHOT (Current Real-Time Positions):
As of: {calc['transit_timestamp']}
{calc['transits']}
(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)

12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):
{calc['bnn_display_str']}
(Note: BNN uses Directional Grouping and Orbital Order instead of House-based analysis. Retrograde planets project into previous sign. Friend/Enemy relationships follow Deva/Asura groups, not Parashari Tatkalik Maitri.)

Name: {calc['name_display']}
Gender: {calc['gender_display']}
Date: {calc['dob_display']}
Time: {calc['tob_display']}
Place: {calc['place_display']}
Timezone: {calc['timezone_display']}
"""
    
    timeline_section_base = f"""SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)

III. VIMSHOTTARI DASHA TIMELINE SECTION

11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):

"""
    
    # Build complete unified prompt dynamically based on checkbox filters
    # Update timeline section based on toggle
    if st.session_state.show_full_timeline:
        timeline_content = full_timeline_table
    else:
        timeline_content = calc['timeline_full']
    
    # Build sections conditionally
    prompt_parts = []
    prompt_parts.append("SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)\n\nI. CONTEXT & DATA SOURCE\nYou are the Brahma-Daivagya. Use the provided MASTER DATA PACKET to perform \"Hit Theory\" analysis.\nDo not calculate planetary degrees. Use the pre-calculated values below.\n\n*** MASTER DATA PACKET (PRE-CALCULATED) ***\n\n")
    
    # Charts sections (1, 8, 9, 10, 13)
    if st.session_state.show_charts:
        prompt_parts.append(f"1. NATAL CHART (Hardware):\n{calc['natal_table']}\n\n")
        prompt_parts.append(f"8. D1 HOUSE CHART (Rashi - Whole Sign):\n{calc['d1']}\n\n")
        prompt_parts.append(f"9. BHAVA CHALIT CHART (Sripati - House Shifts):\n{calc['bhava_chalit']}\n(Note: If a planet shows \"[Rashi HX → Bhava HY]\", it has shifted houses. This is critical for prediction.)\n\n")
        prompt_parts.append(f"10. SHODASHAVARGA MATRIX (16 CHARTS):\n{calc['vargas']}\n\n")
        prompt_parts.append(f"13. UNIFIED BNN-PARASHARI KUNDALI (The Snapshot):\n{calc['unified_kundali']}\n(Note: This table uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility. Bhava Shift markers [→ HX] indicate planets that moved to different houses in Bhava Chalit chart. For Direction/Trines (BNN), use the Sign column. For Career/Outcome (Parashari), check Bhava Shift if present.)\n\n")
    
    # Inner calculations sections (2, 3, 4, 5, 6, 7, 12)
    if st.session_state.show_inner_calculations:
        prompt_parts.append(f"2. SPECIAL POINTS (Vulnerable Spots):\n- 64th Navamsa Sign: {calc['d64']}\n- 22nd Drekkana Sign: {calc['d22']}\n- Upagrahas:\n{calc['upagrahas']}\n\n")
        prompt_parts.append(f"3. ASHTAKAVARGA (Bhinna + Sarva):\n{calc['sav']}\nTotal SAV Score: {total_sav_score} points\n(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)\n\n")
        prompt_parts.append(f"4. CURRENT TIMING (Software - Dasha System):\n{calc['dasha_info']}\n(Note: Hit Theory is the \"Trigger,\" but Dasha is the \"Gun.\" A hit usually doesn't manifest unless the Dasha Lord is involved.)\n\n")
        prompt_parts.append(f"5. TIME VARIABLES:\n- Birth Ghati: {calc['ishta']:.2f}\n- Day Duration: {calc['dinamaana']:.2f}\n- Planetary Avasthas (Moods):\n{calc['avasthas']}\n\n")
        prompt_parts.append(f"6. PANCHANG (Five Limbs of Time):\n{calc['panchang_info']}\n- Tithi: Crucial for relationship and emotional depth\n- Yoga: Crucial for health and innate nature\n- Karana: Crucial for career/work success\n\n")
        prompt_parts.append(f"7. TRANSIT SNAPSHOT (Current Real-Time Positions):\nAs of: {calc['transit_timestamp']}\n{calc['transits']}\n(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)\n\n")
        prompt_parts.append(f"12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):\n{calc['bnn_display_str']}\n(Note: BNN uses Directional Grouping and Orbital Order instead of House-based analysis. Retrograde planets project into previous sign. Friend/Enemy relationships follow Deva/Asura groups, not Parashari Tatkalik Maitri.)\n\n")
    
    # Timeline section (11)
    if st.session_state.show_timeline:
        prompt_parts.append(f"11. VIMSHOTTARI DASHA TIMELINE (Full 80-Year Projection):\n{timeline_content}\n\n")
    
    # Footer (always shown)
    prompt_parts.append(f"Lagna Summary: {calc['lagna']}\nMoon Nakshatra: {calc['nak']}\n\nName: {calc['name_display']}\nGender: {calc['gender_display']}\nDate: {calc['dob_display']}\nTime: {calc['tob_display']}\nPlace: {calc['place_display']}\nTimezone: {calc['timezone_display']}\n\nINSTRUCTION:\n\"O Brahma-Daivagya, align the heavens using the Master Data Packet.\n1. Cross-reference the Transit Snapshot with the Natal Chart to find specific hits.\n2. If a hit occurs, check the SAV score of that sign.\n3. Check if the planet involves the 64th Navamsa or 22nd Drekkana.\n4. Note: Eclipse status checks the middle of the month; precise dates may vary by +/- 14 days.\n5. Synthesize the prediction.\n\"")
    
    complete_unified_prompt = "".join(prompt_parts)
    
    # MAIN OUTPUT: Filtered Unified Prompt
    st.subheader("Copy This Prompt (Complete - Sections 1-13):")
    if include_structured_json:
        # For JSON mode, show only JSON (exclusive mode)
        json_str = json.dumps(calc['structured_payload'], separators=(',', ':'), ensure_ascii=False)
        st.code(json_str, language='json')
    else:
        st.code(complete_unified_prompt, language="markdown")
    
    st.subheader("Data Preview:")
    st.text(calc['vargas'])