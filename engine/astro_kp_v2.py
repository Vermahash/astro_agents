from __future__ import annotations

"""
KP-FOCUSED STREAMLIT FRONTEND (SLIM VERSION)
===========================================

This module reuses the heavy calculation engine from `astro_kp.calculate_vedic_charts`
but exposes a slimmer UI and output that are tailored to KP usage:

- Computes everything via `calculate_vedic_charts` (Krishnamurti ayanamsa,
  D1 + Bhava Chalit, special points, Panchang, Vimshottari Dasha, Hit Theory,
  Ashtakavarga, Avasthas, etc.).
- Surfaces a concise human summary.
- Allows copying the full `structured_payload` JSON (including `kp_master_packet`
  and `kp_prediction`) for use with Gemini + `docs/prompts/Gemini_instructionsKP.md`.

No core math is duplicated here; all numerics stay in `astro_kp.py`.
"""

import datetime
from typing import Any

import pytz
import streamlit as st

import astro_kp
from astro_kp import (
    load_city_data,
    build_city_index,
    search_city,
    calculate_vedic_charts,
)

try:
    from streamlit_searchbox import st_searchbox

    HAS_SEARCHBOX = True
except ImportError:
    HAS_SEARCHBOX = False
    if "streamlit" in dir():
        st.warning("streamlit-searchbox not installed. Install with: pip install streamlit-searchbox")



def _build_transit_aspect_text(rows: list[dict]) -> str:
    """Convert transit aspect impact list to a compact markdown table for the packet."""
    if not rows:
        return "(no transit aspects computed)"
    cols = ["transit_planet", "transit_sign", "aspect_number", "aspected_sign",
            "aspected_house_from_lagna_whole_sign", "aspected_kp_house_by_cusp",
            "motion", "sav_score_of_aspected_sign"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join([":---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def _build_transit_hit_text(rows: list[dict]) -> str:
    """Convert transit degree hit list to a compact markdown table for the packet."""
    if not rows:
        return "(no degree hits within orb)"
    cols = ["transit_planet", "natal_target", "orb_deg", "aspect_arc",
            "transit_motion", "applying_separating"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join([":---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)
def _build_natal_drishti_text(rows: list[dict]) -> str:
    if not rows: return "No natal drishti data."
    cols = ["aspecting_planet", "planet_house", "planet_sign", "natural_nature", "retrograde_context", 
            "aspect_number", "aspected_house", "aspected_sign", "target_planets_in_house", "target_house_lord"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join([":---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)

def _build_house_drishti_summary_text(rows: list[dict]) -> str:
    if not rows: return "No house drishti summary data."
    cols = ["house", "sign", "house_meaning_short", "planets_in_house", "house_lord", "aspected_by", "summary_hint"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join([":---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def _build_yoga_text(yogas: list[dict]) -> str:
    """Format the MVP yogas into the Master Data Packet."""
    if not yogas:
        return "No applicable MVP yogas detected from the implemented rule set."
    
    lines = []
    for r in yogas:
        sn = r.get("strength_notes", {})
        dignity = sn.get("dignity", "")
        planets = ", ".join(str(p) for p in r.get("involved_planets", []))
        houses = ", ".join(str(h) for h in r.get("involved_houses", []))
        
        entry = (
            f"- **{r.get('yoga_name', 'Unknown')}** ({r.get('category', '')})\n"
            f"  Status: {r.get('final_status', '')} (D1: {r.get('d1_status', '')}, D9: {r.get('d9_status', '')})\n"
            f"  Planets: {planets} | Houses: {houses}\n"
        )
        if r.get("detected_relationship"):
            entry += f"  Relationship: {r['detected_relationship']}\n"
        if dignity:
            entry += f"  Dignity: {dignity}\n"
        entry += f"  Rule Summary: {r.get('rule_summary', '')}\n"
        lines.append(entry)
        
    return "\n".join(lines)


def _build_yoga_coverage_text(cov: dict) -> str:
    """Format yoga coverage dictionary."""
    if not cov:
        return "Coverage data not available."
    return (
        f"- Total Rules Checked: {cov.get('total_rules_checked', 0)}\n"
        f"- Applicable Yogas: {cov.get('applicable_count', 0)}\n"
        f"- Confirmed in D9: {cov.get('confirmed_count', 0)}\n"
        f"- Partial (D1 only): {cov.get('partial_d1_only_count', 0)}\n"
        f"- D9 Support Only (Ignored): {cov.get('navamsa_support_only_count', 0)}\n"
        f"- Absent: {cov.get('absent_count', 0)}"
    )

def _build_yoga_matrix_text(matrix: list[dict]) -> str:
    """Format full yoga rule matrix."""
    if not matrix:
        return "No rules checked."
    cols = ["Yoga Name", "D1", "D9", "Final", "Planets", "Houses", "Rel", "Reason"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join([":---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in matrix:
        vals = [
            str(r.get("yoga_name", "")),
            str(r.get("d1_status", "")),
            str(r.get("d9_status", "")),
            str(r.get("final_status", "")),
            ", ".join(str(p) for p in r.get("involved_planets_d1", [])),
            ", ".join(str(h) for h in r.get("involved_houses_d1", [])),
            str(r.get("detected_relationship", "")),
            str(r.get("reason", ""))
        ]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)



# ── Patch B: reusable prompt-block builders ───────────────────────────────────

def build_chart_subject_block(
    name: str = "",
    gender: str = "",
    dob_str: str = "",
    tob_str: str = "",
    place: str = "",
    timezone: str = "",
    lat: float | None = None,
    lon: float | None = None,
) -> str:
    """Return the CHART SUBJECT header block."""
    def _v(x: Any) -> str:
        return str(x) if x not in (None, "", 0.0) else "Unknown"
    return (
        "CHART SUBJECT\n"
        f"Name: {_v(name)}\n"
        f"Gender: {_v(gender)}\n"
        f"Date: {_v(dob_str)}\n"
        f"Time: {_v(tob_str)}\n"
        f"Place: {_v(place)}\n"
        f"Timezone: {_v(timezone)}\n"
        f"Latitude: {_v(lat)}\n"
        f"Longitude: {_v(lon)}\n"
    )


def build_system_role_block() -> str:
    """Return the SYSTEM ROLE block."""
    return (
        "SYSTEM ROLE\n"
        "BRAHMA-DAIVAGYA — The Vedic Calculator & Source-Bound Jyotish Interpreter\n"
    )


_CONTROLLER_BLOCK_TEXT = """\
CONTROLLER BLOCK
Use this entire chat thread as one structured chart-analysis session.

Do not recalculate planetary degrees.
Do not invent missing values.
Use only the MASTER DATA PACKET and explicitly supplied source rules.

System separation:
- KP uses Placidus/KP cusps, star lord, sub lord, sub-sub lord, ruling planets, significators, and Dasha/Bhukti/Anthra timing.
- BPHS uses Rasi, Bhava, Vargas, dignities, yogas, aspects, strengths, and Dasha context.
- BNN uses planetary flow, karaka chains, adjacent houses, 7th/12th relationships, and transit validation.
- Gochar analysis must use the Transit Snapshot, Transit Aspect Impact Table, and Transit Degree Hit Table.
- Retrograde analysis must use the Retrograde/Motion fields, not display labels alone.
- Rahu/Ketu may display as backward nodes, but KP retrograde rejection logic must use kp_treat_as_retrograde.

If data is missing:
- Mark it as missing.
- Do not fill gaps with assumptions.

When systems disagree:
- State the disagreement.
- Explain which system is being used for that layer.
- Do not force false agreement.
"""


def build_controller_block() -> str:
    return _CONTROLLER_BLOCK_TEXT


_INSTRUCTION_BLOCK = """\
INSTRUCTION
O Brahma-Daivagya, align the heavens using the Master Data Packet.

1. Read CHART SUBJECT first.
2. Use the Natal Planet Table, D1 House Chart, and KP Cusp Table as the calculation base.
3. Use the Vimshottari Dasha Timeline for MD/AD/PD timing.
4. Cross-reference the Transit Snapshot with the Natal Chart.
5. Use D1 Natal Drishti Table to understand permanent natal planetary gaze.
6. Evaluate source planet quality before judging its drishti. Evaluate target house, planets sitting there, and house lord. When multiple planets aspect the same house, note Jupiter protection, Saturn pressure, Mars drive, and mixed/conflicting gazes.
7. Use the Transit Aspect Impact Table separately for current Gochar gaze. Do not confuse natal drishti with transit drishti.
8. Use the Transit Degree Hit Table to identify exact degree contacts and applying/separating states.
9. If a hit occurs, check SAV score if available.
10. Check 64th Navamsa or 22nd Drekkana only if those fields exist in the packet.
11. For KP predictions, use Placidus/KP cusps and star/sub/sub-sub lords.
12. For BPHS predictions, use Rasi, Bhava, aspects, dignities, yogas, and Dasha context.
13. For BNN validation, use planetary flow, karaka chains, adjacent houses, 7th/12th relationships, and transit validation.
14. Synthesize only from supplied data. Do not invent missing values.
"""


st.set_page_config(page_title="KP Calculator (Brahma-Daivagya)", page_icon="🕉️", layout="wide")
st.title("🕉️ KP Calculator — Brahma-Daivagya")
st.markdown("Generates a **KP-ready MASTER DATA PACKET** for Gemini (Brahma-Daivagya KP Gem).")

if "name_kp_v2" not in st.session_state:
    st.session_state["name_kp_v2"] = ""
if "name_committed_kp_v2" not in st.session_state:
    st.session_state["name_committed_kp_v2"] = ""


def _commit_name_kp_v2() -> None:
    st.session_state["name_committed_kp_v2"] = st.session_state.get("name_kp_v2", "")


# --- 1. INPUT FORM -------------------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    name = st.text_input(
        "Name",
        placeholder="Enter name",
        key="name_kp_v2",
        on_change=_commit_name_kp_v2,
    )
    dob = st.date_input(
        "Date of Birth",
        min_value=datetime.date(1900, 1, 1),
        key="dob_kp_v2",
    )
    gender = st.selectbox("Gender", ["", "Male", "Female", "Other"], key="gender_kp_v2")

with col2:
    st.markdown("**Time of Birth**")
    # Single widget is more stable than split hour/minute number inputs during reruns.
    if "tob_kp_v2" not in st.session_state:
        st.session_state["tob_kp_v2"] = datetime.time(0, 0)
    tob = st.time_input(
        "Time (HH:MM)",
        key="tob_kp_v2",
        step=60,
    )


# Location helpers reused from astro_kp
df_cities = load_city_data()
lat: float | None = None
lon: float | None = None
selected_city: str | None = None

if "lat_kp_v2" not in st.session_state:
    st.session_state["lat_kp_v2"] = 0.0
if "lon_kp_v2" not in st.session_state:
    st.session_state["lon_kp_v2"] = 0.0
if "selected_city_kp_v2" not in st.session_state:
    st.session_state["selected_city_kp_v2"] = ""
if "location_mode_kp_v2" not in st.session_state:
    st.session_state["location_mode_kp_v2"] = "Search"

st.write("---")
st.markdown("### 🌍 Location Search (Required)")

if df_cities is not None and not df_cities.empty:
    city_index = build_city_index(df_cities)
    location_mode = st.radio(
        "Location Input Mode",
        ["Search", "Dropdown", "Manual"],
        horizontal=True,
        key="location_mode_kp_v2",
    )

    col_city1, col_city2 = st.columns(2)

    with col_city1:
        if location_mode == "Search" and HAS_SEARCHBOX:
            st.caption("🔎 Fast search (recommended)")

            def search_function(search_term: str):
                return search_city(search_term, city_index)

            selected_result = st_searchbox(
                search_function,
                key="city_searchbox_kp_v2",
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
                        st.session_state["lat_kp_v2"] = float(lat)
                        st.session_state["lon_kp_v2"] = float(lon)
                        st.session_state["selected_city_kp_v2"] = selected_city
                        st.success(f"Selected: {selected_city} ({lat:.4f}, {lon:.4f})")
                    else:
                        st.warning("City coordinates found but display name not matched.")
                else:
                    st.error("Unexpected result format from searchbox.")
        elif location_mode == "Search":
            st.caption("🔎 Fast search is unavailable (dependency missing).")

    with col_city2:
        if location_mode == "Dropdown":
            st.caption("📂 Simple dropdown (type to filter)")
            city_list: list[str] = [""] + df_cities["display_name"].tolist()
            dropdown_city = st.selectbox(
                "Select City:",
                city_list,
                help="Start typing the city name to filter the list.",
                key="city_selectbox_kp_v2",
            )
            if dropdown_city:
                row = df_cities[df_cities["display_name"] == dropdown_city].iloc[0]
                lat, lon = float(row["latitude"]), float(row["longitude"])
                selected_city = dropdown_city
                st.session_state["lat_kp_v2"] = float(lat)
                st.session_state["lon_kp_v2"] = float(lon)
                st.session_state["selected_city_kp_v2"] = selected_city
                st.success(f"Selected: {selected_city} ({lat:.4f}, {lon:.4f})")

if st.session_state.get("location_mode_kp_v2") == "Manual":
    with st.expander("📍 Manual Coordinates", expanded=True):
        st.number_input(
            "Lat",
            format="%.4f",
            key="lat_kp_v2",
        )
        st.number_input(
            "Lon",
            format="%.4f",
            key="lon_kp_v2",
        )

lat = float(st.session_state.get("lat_kp_v2", 0.0))
lon = float(st.session_state.get("lon_kp_v2", 0.0))
selected_city = st.session_state.get("selected_city_kp_v2", "") or selected_city

st.write("---")
st.subheader("🕒 Timezone")
common_tz = ["Asia/Kolkata", "UTC", "America/New_York", "Europe/London", "Australia/Sydney"]
sel_tz = st.selectbox("Select Timezone:", common_tz, index=0, key="timezone_kp_v2")

st.write("---")
st.subheader("⚙️ Output Options")
include_structured_json = st.checkbox("Show MASTER DATA PACKET JSON tabs (for Gemini)", value=True)

if "kp_cusp_engine_kp_v2" not in st.session_state:
    st.session_state["kp_cusp_engine_kp_v2"] = "auto"

kp_cusp_engine = st.selectbox(
    "KP Cusp Engine",
    ["auto", "swiss_vp291_sidereal", "legacy_fallback", "kp_new_manual"],
    index=["auto", "swiss_vp291_sidereal", "legacy_fallback", "kp_new_manual"].index(
        st.session_state.get("kp_cusp_engine_kp_v2", "auto")
    ),
    help=(
        "auto: picks most boundary-stable engine per chart, "
        "swiss_vp291_sidereal: default Swiss sidereal cusps, "
        "legacy_fallback: compatibility fallback, "
        "kp_new_manual: tropical Placidus minus manual KP-New ayanamsa."
    ),
    key="kp_cusp_engine_kp_v2",
)


##############################
# 2. GENERATE / PERSIST DATA #
##############################

if "kp_calc_results" not in st.session_state:
    st.session_state.kp_calc_results = None  # type: ignore[assignment]

if st.button("Generate KP MASTER DATA PACKET"):
    # Use a committed fallback in case the page reruns while the user is still editing.
    name_current = (st.session_state.get("name_kp_v2", "") or "").strip()
    name_committed = (st.session_state.get("name_committed_kp_v2", "") or "").strip()
    name_effective = name_current or name_committed
    name_empty = not name_effective
    dob_empty = dob is None
    tob_empty = tob is None
    location_empty = lat is None or lon is None or (
        st.session_state.get("location_mode_kp_v2") == "Manual" and lat == 0.0 and lon == 0.0
    )

    if name_empty or dob_empty or tob_empty or location_empty:
        st.error("Name, Date of Birth, Time of Birth, and Location are all required.")
        st.stop()

    name = name_effective
    selected_city = st.session_state.get("selected_city_kp_v2", "") or selected_city or ""

    local_tz = pytz.timezone(sel_tz)
    dt_naive = datetime.datetime.combine(dob, tob)  # type: ignore[arg-type]
    dt_aware = local_tz.localize(dt_naive)

    # Apply selected cusp engine just before running calculations.
    astro_kp.KP_CUSP_ENGINE = kp_cusp_engine

    (
        lagna,
        d1,
        d9,
        bhava_chalit,
        vargas,
        nak,
        ishta,
        dinamaana,
        sav,
        avasthas,
        upagrahas,
        d64,
        d22,
        transits,
        transit_timestamp_utc,
        natal_table,
        dasha_info,
        panchang_info,
        timeline_full,
        full_timeline_data,
        structured_payload,
        bnn_display_str,
        unified_kundali,
    ) = calculate_vedic_charts(
        name,
        dt_aware,
        lat,
        lon,
        gender,
        birth_place=selected_city or None,
        timezone_name=sel_tz,
    )  # type: ignore[arg-type]

    transit_timestamp = transit_timestamp_utc.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    dob_str = dob.strftime("%d/%m/%Y") if dob else "N/A"
    tob_str = tob.strftime("%H:%M") if tob else "N/A"

    st.session_state.kp_calc_results = {
        "lagna": lagna,
        "d1": d1,
        "d9": d9,
        "bhava_chalit": bhava_chalit,
        "vargas": vargas,
        "nak": nak,
        "ishta": ishta,
        "dinamaana": dinamaana,
        "sav": sav,
        "avasthas": avasthas,
        "upagrahas": upagrahas,
        "d64": d64,
        "d22": d22,
        "transits": transits,
        "transit_timestamp": transit_timestamp,
        "natal_table": natal_table,
        "dasha_info": dasha_info,
        "panchang_info": panchang_info,
        "timeline_full": timeline_full,
        "full_timeline_data": full_timeline_data,
        "structured_payload": structured_payload,
        "bnn_display_str": bnn_display_str,
        "unified_kundali": unified_kundali,
        "name": name,
        "gender": gender,
        "dob_str": dob_str,
        "tob_str": tob_str,
        "selected_city": selected_city,
        "timezone": sel_tz,
        "lat": lat,
        "lon": lon,
    }


###########################
# 3. DISPLAY CALC RESULTS #
###########################

# --- Sidebar debug toggle (Patch B) ---
with st.sidebar:
    st.markdown("### ⚙️ Debug Options")
    show_debug_audits = st.toggle(
        "Show calculation audit/debug tables",
        value=False,
        key="show_debug_audits",
    )
    include_debug_in_export = st.toggle(
        "Include debug audits in raw JSON export",
        value=False,
        key="include_debug_in_export",
    )
    include_yoga_rule_matrix_in_packet = st.toggle(
        "Include full Yoga Rule Matrix in packet",
        value=False,
    )

calc = st.session_state.kp_calc_results
if calc:
    lagna = calc["lagna"]
    d1 = calc["d1"]
    bhava_chalit = calc["bhava_chalit"]
    vargas = calc["vargas"]
    nak = calc["nak"]
    ishta = calc["ishta"]
    dinamaana = calc["dinamaana"]
    sav = calc["sav"]
    avasthas = calc["avasthas"]
    upagrahas = calc["upagrahas"]
    d64 = calc["d64"]
    d22 = calc["d22"]
    transits = calc["transits"]
    transit_timestamp = calc["transit_timestamp"]
    natal_table = calc["natal_table"]
    dasha_info = calc["dasha_info"]
    panchang_info = calc["panchang_info"]
    timeline_full = calc["timeline_full"]
    full_timeline_data = calc["full_timeline_data"]
    structured_payload = calc["structured_payload"]
    bnn_display_str = calc["bnn_display_str"]
    unified_kundali = calc["unified_kundali"]
    name = calc["name"]
    gender = calc["gender"]
    dob_str = calc["dob_str"]
    tob_str = calc["tob_str"]
    selected_city = calc["selected_city"]
    sel_tz = calc["timezone"]
    _lat = calc.get("lat", 0.0)
    _lon = calc.get("lon", 0.0)

    st.write("---")
    st.subheader("🔍 KP Summary (Human-Readable)")
    st.markdown(
        f"- **Lagna**: {lagna}\n"
        f"- **Moon Nakshatra**: {nak}\n"
        f"- **Current Dasha**: {dasha_info}\n"
        f"- **Panchang**: {panchang_info}\n"
        f"- **Ashtakavarga (BAV + SAV)**:\n\n{sav}\n\n"
        f"- **Planetary Avasthas**:\n{avasthas}\n"
        f"- **Special Points**: 64th Navamsa={d64}, 22nd Drekkana={d22}\n"
        f"- **Upagrahas**:\n{upagrahas}\n"
        f"- **Transit Snapshot (as of {transit_timestamp})**:\n{transits}"
    )

    import pandas as pd

    natal_drishti_rows = structured_payload.get("natal_drishti_table", [])
    natal_house_summary = structured_payload.get("natal_house_drishti_summary", [])
    
    if natal_drishti_rows or natal_house_summary:
        st.write("---")
        st.subheader("👁️ D1 NATAL DRISHTI")
        if natal_drishti_rows:
            st.markdown("**1. D1 Natal Drishti Table**")
            st.dataframe(pd.DataFrame(natal_drishti_rows), width='stretch', hide_index=True)
        if natal_house_summary:
            st.markdown("**2. D1 House Drishti Summary**")
            st.dataframe(pd.DataFrame(natal_house_summary), width='stretch', hide_index=True)

    current_month_packet = structured_payload.get("transit_monthly", [{}])[0]
    aspect_impacts = current_month_packet.get("monthly_aspect_impacts", [])
    degree_hits = current_month_packet.get("monthly_degree_hits", [])

    import pandas as pd
    
    if aspect_impacts:
        st.write("---")
        st.subheader("🔭 Transit Aspect Impact Table")
        st.dataframe(pd.DataFrame(aspect_impacts), width='stretch')

    if degree_hits:
        st.write("---")
        st.subheader("🎯 Transit Degree Hit Table")
        st.dataframe(pd.DataFrame(degree_hits), width='stretch')
    # --- SPECIAL YOGAS TABLE (Patch C) ---
    st.write("---")
    st.subheader("🪐 Special Yogas — Applicable MVP/Expanded Rules")
    _yoga_rows = structured_payload.get("special_yogas", [])
    if _yoga_rows:
        _yoga_display = []
        for r in _yoga_rows:
            sn = r.get("strength_notes", {})
            _yoga_display.append({
                "Yoga Name": r["yoga_name"],
                "Category": r["category"],
                "D1 Status": r["d1_status"],
                "D9 Status": r["d9_status"],
                "Final Status": r["final_status"],
                "Involved Planets": ", ".join(str(p) for p in r.get("involved_planets", [])),
                "Involved Houses": ", ".join(str(h) for h in r.get("involved_houses", [])),
                "Detected Relationship": r.get("detected_relationship", ""),
                "Rule Summary": r.get("rule_summary", "")[:80],
                "Strength Notes": f"Dignity: {sn.get('dignity', '')}; {sn.get('house_context', '')}",
            })
        st.dataframe(pd.DataFrame(_yoga_display), width='stretch', hide_index=True)
    else:
        st.info("No applicable MVP yogas detected from the implemented rule set.")
    st.caption("Yoga Engine MVP: showing implemented rules only.")

    _yoga_matrix = structured_payload.get("yoga_rule_matrix", [])
    if _yoga_matrix:
        with st.expander("🧾 Yoga Rule Matrix — Implemented Rules Checked", expanded=False):
            _matrix_display = []
            for r in _yoga_matrix:
                _matrix_display.append({
                    "Yoga Name": r["yoga_name"],
                    "Category": r["category"],
                    "Rule Summary": r.get("rule_summary", "")[:80],
                    "Detected Relationship": r.get("detected_relationship", ""),
                    "Involved Planets D1": ", ".join(str(p) for p in r.get("involved_planets_d1", [])),
                    "Involved Houses D1": ", ".join(str(h) for h in r.get("involved_houses_d1", [])),
                    "Involved Planets D9": ", ".join(str(p) for p in r.get("involved_planets_d9", [])),
                    "Involved Houses D9": ", ".join(str(h) for h in r.get("involved_houses_d9", [])),
                    "D1 Status": r["d1_status"],
                    "D9 Status": r["d9_status"],
                    "Final Status": r["final_status"],
                    "Shown In Main Table": r.get("shown_in_main_table", False),
                    "Reason": r.get("reason", ""),
                })
            st.dataframe(pd.DataFrame(_matrix_display), width='stretch', hide_index=True)

    # --- Audit expanders — visible only when debug toggle is ON (Patch B) ---
    if show_debug_audits:

        # Retrograde / Motion Audit
        retro_audit = structured_payload.get("retrograde_motion_audit", [])
        if retro_audit:
            with st.expander("🔬 Retrograde / Motion Audit (Natal)", expanded=False):
                st.dataframe(pd.DataFrame(retro_audit), width='stretch')

        # Dasha Epoch Audit
        dasha_audit = structured_payload.get("dasha_epoch_audit", {})
        if dasha_audit:
            with st.expander("📅 Dasha Epoch Audit", expanded=False):
                st.json(dasha_audit)

        # Dasha Timeline Debug
        dasha_dbg = structured_payload.get("dasha_timeline_debug", {})
        if dasha_dbg:
            with st.expander("🐛 DASHA TIMELINE DEBUG", expanded=False):
                st.write("**Birth / Scan inputs**")
                st.json({k: dasha_dbg.get(k) for k in [
                    "birth_dt_local", "target_datetime_local", "target_source",
                    "dasha_ayanamsha_mode", "chart_moon_longitude", "dasha_moon_longitude",
                    "moon_difference_arcmin", "dasha_engine_version",
                ]})
                st.write("**Timeline counts & endpoints**")
                st.json({k: dasha_dbg.get(k) for k in [
                    "count_pd_periods", "first_pd_row", "last_pd_row",
                    "birth_md_lord", "birth_md_end_dt", "rahu_md_end_dt",
                    "rendered_rahu_mars_moon_row",
                ]})
                st.write("**Current scan result**")
                st.json({k: dasha_dbg.get(k) for k in [
                    "current_md", "current_ad", "current_pd",
                    "current_row_index", "current_row_start", "current_row_end",
                    "current_row_duration_days", "selected_rows_count",
                ]})
                st.write("**Selected rows raw**")
                for row_str in (dasha_dbg.get("selected_rows_raw") or []):
                    st.code(row_str)

        # Cusp Sub-Sub Lord Audit
        cusp_audit = structured_payload.get("cusp_subsub_audit", [])
        if cusp_audit:
            with st.expander("🔍 Cusp Sub-Sub Lord Audit", expanded=False):
                _cols = ["cusp", "lon", "nakshatra", "star_lord", "sub_lord", "sub_sub_lord",
                         "offset_in_star_years", "offset_in_sub_years", "match"]
                _rows = [{k: r[k] for k in _cols} for r in cusp_audit]
                _df_cusp = pd.DataFrame(_rows)
                st.dataframe(_df_cusp.style.apply(
                    lambda row: ["background-color: #ffcccc" if not row["match"] else "" for _ in row],
                    axis=1
                ), width='stretch')

        # Cusp Engine Comparison Audit
        engine_audit = structured_payload.get("cusp_engine_comparison_audit", [])
        if engine_audit:
            with st.expander("⚙️ Cusp Engine Comparison Audit", expanded=False):
                st.dataframe(pd.DataFrame(engine_audit), width='stretch')

        # Yoga Engine Debug (Patch C)
        from yoga_engine import detect_special_yogas as _dsy
        _retro_map_ui = {
            p: info.get("kp_treat_as_retrograde", False)
            for p, info in structured_payload.get("kp_master_packet", {})
            .get("planet_star_sub_lords", {}).items()
        }
        _pp_ui = {
            p: info.get("longitude", 0.0)
            for p, info in structured_payload.get("kp_astrology_matrix", {})
            .get("planetary_star_sub_lords", {}).items()
        }
        # Fallback: get longitudes from kp_master_packet cusps sign index
        # Use the already-computed main yoga debug list if planet_positions available
        _all_yogas, _debug_yogas = _dsy(
            planet_positions=structured_payload.get("_planet_positions_raw", {}),
            asc_sign=0,
            asc_lon=0.0,
            retrograde_map=_retro_map_ui,
            debug=True,
        ) if structured_payload.get("_planet_positions_raw") else ([], [])

        # Prefer pre-computed debug rows from payload if available
        if not _debug_yogas:
            _debug_yogas = structured_payload.get("special_yogas_debug_full", [])

        if _debug_yogas:
            with st.expander("🔮 Yoga Engine Debug (all rules checked)", expanded=False):
                _dbg_display = []
                for r in _debug_yogas:
                    _dbg_display.append({
                        "Yoga": r["yoga_name"],
                        "D1": r["d1_status"],
                        "D9": r["d9_status"],
                        "Final": r["final_status"],
                        "Planets": ", ".join(str(p) for p in r.get("involved_planets", [])),
                        "Rule": r.get("rule_summary", "")[:80],
                    })
                st.dataframe(pd.DataFrame(_dbg_display), use_container_width=True, hide_index=True)
        else:
            st.info("Yoga debug: re-run chart to populate debug list.")

    st.write("---")
    st.subheader("📜 Text Prompts (choose BPHS / KP / Unified)")

    tabs_text = st.tabs(["Unified (BPHS + KP)", "BPHS / BNN Only", "KP Only"])

    kp_master = structured_payload.get("kp_master_packet", {}) or {}
    kp_cusps = kp_master.get("cusps", {}) or structured_payload.get("cusps", {}) or {}
    kp_star_sub = kp_master.get("planet_star_sub_lords", {}) or structured_payload.get(
        "planet_star_sub_lords", {}
    ) or {}

    kp_cusp_lines: list[str] = [
        "| House | Longitude (DMS) | Longitude (Decimal) | Sign | Sign Lord | Star Lord | Sub Lord | Sub-Sub Lord |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for house_key in sorted(kp_cusps.keys(), key=lambda x: int(x)):
        c = kp_cusps[house_key]
        lon_dms = c.get("lon_dms", "")
        lon_dec = c.get("lon", "")
        kp_cusp_lines.append(
            f"| {house_key} | {lon_dms} | {lon_dec} | {c.get('sign','')} | {c.get('sign_lord','')} | "
            f"{c.get('star_lord','')} | {c.get('sub_lord','')} | {c.get('sub_sub_lord','')} |"
        )
    kp_cusps_table = "\n".join(kp_cusp_lines)

    kp_planet_lines: list[str] = [
        "| Planet | Sign | Sign Lord | Star Lord | Sub Lord | Sub-Sub Lord | Retrograde |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        info = kp_star_sub.get(p_name, {})
        # Use correct retrograde flags from new motion payload
        if p_name in ("Rahu", "Ketu"):
            retro_flag = "R" if info.get("is_backward_motion") else ""
        else:
            retro_flag = "R" if info.get("is_retrograde_by_speed") else ""
        kp_planet_lines.append(
            f"| {p_name} | {info.get('sign','')} | {info.get('sign_lord','')} | "
            f"{info.get('star_lord','')} | {info.get('sub_lord','')} | {info.get('sub_sub_lord','')} | {retro_flag} |"
        )
    kp_planets_table = "\n".join(kp_planet_lines)

    kp_matrix = structured_payload.get("kp_astrology_matrix", {}) or {}
    rasi_chart_table = kp_matrix.get("rasi_chart_table", "")
    planets_core_table = kp_matrix.get("planets_table", "")
    planet_signification_table = kp_matrix.get("planet_signification_table", "")
    house_significators_table = kp_matrix.get("house_significators_table", "")
    nakshatra_nadi_table = kp_matrix.get("nakshatra_nadi_table", "")
    cil_sub_sub_table = kp_matrix.get("cil_sub_sub_table", "")
    four_step_theory_table = kp_matrix.get("four_step_theory_table", "")
    cil_sub_table = kp_matrix.get("cil_sub_table", "")
    ruling_planets_table = kp_matrix.get("ruling_planets_table", "")
    current_ruling_planets_table = kp_matrix.get("current_ruling_planets_table", "")
    fortuna_table = kp_matrix.get("fortuna_table", "")
    badhaka_maraka_table = kp_matrix.get("badhaka_maraka_table", "")
    nodal_decode_table = kp_matrix.get("nodal_decode_table", "")
    moon_dasha_balance_at_birth = kp_matrix.get("moon_dasha_balance_at_birth", {}) or {}
    moon_dasha_balance_display = moon_dasha_balance_at_birth.get("display", "")
    kp_cusp_aspects_table = kp_matrix.get("kp_cusp_aspects_table", "")
    navamsa_check_table = kp_matrix.get("navamsa_check_table", "")

    _chart_subject = build_chart_subject_block(
        name=name, gender=gender, dob_str=dob_str, tob_str=tob_str,
        place=selected_city, timezone=sel_tz, lat=_lat, lon=_lon,
    )
    unified_prompt = (
        _chart_subject + "\n"
        + build_system_role_block() + "\n"
        + build_controller_block() + "\n"
        "*** MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
        "A. CALCULATION SETTINGS\n"
        f"Chart Ayanamsha: KP (Krishnamurti VP291)\n"
        f"Dasha Ayanamsha: {astro_kp.DASHA_AYANAMSHA_MODE}\n"
        f"Cusp Engine: {astro_kp.KP_CUSP_ENGINE}\n"
        "House System: Placidus\n"
        f"Dasha Year Basis: {astro_kp.DASHA_YEAR_DAYS} days/year\n\n"
        "B. NATAL PLANET TABLE:\n"
        f"{natal_table}\n\n"
        "C. D1 HOUSE CHART (Rashi - Whole Sign):\n"
        f"{d1}\n\n"
        "D. D1 NATAL DRISHTI TABLE:\n"
        f"{_build_natal_drishti_text(structured_payload.get('natal_drishti_table', []))}\n\n"
        "E. D1 HOUSE DRISHTI SUMMARY:\n"
        f"{_build_house_drishti_summary_text(structured_payload.get('natal_house_drishti_summary', []))}\n\n"
        "F. BHAVA CHALIT CHART (Sripati):\n"
        f"{bhava_chalit}\n"
        "(Note: [Rashi HX → Bhava HY] = house shift. Critical for prediction.)\n\n"
        "G. VIMSHOTTARI DASHA TIMELINE (Relevant Period):\n"
        f"{timeline_full}\n\n"
        "H. TRANSIT SNAPSHOT:\n"
        f"As of: {transit_timestamp}\n{transits}\n\n"
        "I. TRANSIT ASPECT IMPACT TABLE (Parashari Drishti):\n"
        f"{_build_transit_aspect_text(structured_payload.get('current_transit_aspect_impacts', []))}\n\n"
        "J. TRANSIT DEGREE HIT TABLE (Degree Proximity):\n"
        f"{_build_transit_hit_text(structured_payload.get('current_transit_degree_hits', []))}\n\n"
        "K. SHODASHAVARGA MATRIX (16 CHARTS):\n"
        f"{vargas}\n\n"
        "L. SPECIAL POINTS:\n"
        f"- 64th Navamsa Sign: {d64}\n"
        f"- 22nd Drekkana Sign: {d22}\n"
        f"- Upagrahas:\n{upagrahas}\n\n"
        "M. ASHTAKAVARGA:\n"
        f"{sav}\n"
        "(SAV >28 = Strong sign, SAV <25 = Vulnerable)\n\n"
        "N. PANCHANG:\n"
        f"{panchang_info}\n\n"
        "O. BNN MODULE:\n"
        f"{bnn_display_str}\n\n"
        "P. UNIFIED KUNDALI:\n"
        f"{unified_kundali}\n\n"
        "Q. SPECIAL YOGAS:\n"
        f"{_build_yoga_text(structured_payload.get('special_yogas', []))}\n\n"
        "Q2. YOGA RULE COVERAGE SUMMARY:\n"
        f"{_build_yoga_coverage_text(structured_payload.get('yoga_rule_coverage', {}))}\n\n"
        + (f"Q3. YOGA RULE MATRIX — ALL CHECKED YOGAS:\n{_build_yoga_matrix_text(structured_payload.get('yoga_rule_matrix', []))}\n\n" if include_yoga_rule_matrix_in_packet else "") +
        "*** KP-SPECIFIC DATA ***\n\n"
        "KP PLACIDUS CUSPS:\n"
        f"{kp_cusps_table}\n\n"
        "KP PLANETARY STAR/SUB-LORDS:\n"
        f"{kp_planets_table}\n\n"
        "KP RASI CHART:\n"
        f"{rasi_chart_table}\n\n"
        "KP PLANET SIGNIFICATION TABLE:\n"
        f"{planet_signification_table}\n\n"
        "KP HOUSE SIGNIFICATORS:\n"
        f"{house_significators_table}\n\n"
        "KP CIL SUB-SUB TABLE:\n"
        f"{cil_sub_sub_table}\n\n"
        "KP 4-STEP THEORY TABLE:\n"
        f"{four_step_theory_table}\n\n"
        "KP CIL SUB TABLE:\n"
        f"{cil_sub_table}\n\n"
        "KP RULING PLANETS:\n"
        f"{ruling_planets_table}\n\n"
        "KP CURRENT RULING PLANETS:\n"
        f"{current_ruling_planets_table}\n\n"
        "KP FORTUNA:\n"
        f"{fortuna_table}\n\n"
        "KP BADHAKA/MARAKA:\n"
        f"{badhaka_maraka_table}\n\n"
        "KP NODAL DECODE:\n"
        f"{nodal_decode_table}\n\n"
        "KP CUSP ASPECT TABLE:\n"
        f"{kp_cusp_aspects_table}\n\n"
        "NAVAMSA CHECK:\n"
        f"{navamsa_check_table}\n\n"
        + _INSTRUCTION_BLOCK
    )


    bphs_prompt = (
        _chart_subject + "\n"
        + build_system_role_block() + "\n"
        + build_controller_block() + "\n"
        "*** MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
        "A. CALCULATION SETTINGS\n"
        f"Chart Ayanamsha: KP (Krishnamurti VP291)\nDasha Ayanamsha: {astro_kp.DASHA_AYANAMSHA_MODE}\n\n"
        "B. NATAL PLANET TABLE:\n"
        "1. NATAL CHART (Hardware):\n"
        f"{natal_table}\n\n"
        "8. D1 HOUSE CHART (Rashi - Whole Sign):\n"
        f"{d1}\n\n"
        "8A. D1 NATAL DRISHTI TABLE:\n"
        f"{_build_natal_drishti_text(structured_payload.get('natal_drishti_table', []))}\n\n"
        "8B. D1 HOUSE DRISHTI SUMMARY:\n"
        f"{_build_house_drishti_summary_text(structured_payload.get('natal_house_drishti_summary', []))}\n\n"
        "9. BHAVA CHALIT CHART (Sripati - House Shifts):\n"
        f"{bhava_chalit}\n"
        "(Note: If a planet shows \"[Rashi HX → Bhava HY]\", it has shifted houses. This is critical for prediction.)\n\n"
        "10. SHODASHAVARGA MATRIX (16 CHARTS):\n"
        f"{vargas}\n\n"
        "2. SPECIAL POINTS (Vulnerable Spots):\n"
        f"- 64th Navamsa Sign: {d64}\n"
        f"- 22nd Drekkana Sign: {d22}\n"
        f"- Upagrahas:\n{upagrahas}\n\n"
        "3. ASHTAKAVARGA (Bhinna + Sarva):\n"
        f"{sav}\n"
        "(Rule: SAV >28 = Strong sign, SAV <25 = Vulnerable sign)\n\n"
        "4. CURRENT TIMING (Vimshottari Dasha System):\n"
        f"{dasha_info}\n"
        "(Note: Hit Theory is the \"Trigger,\" but Dasha is the \"Gun.\" A hit usually doesn't manifest unless the Dasha Lord is involved.)\n\n"
        "5. TIME VARIABLES:\n"
        f"- Birth Ghati: {ishta:.2f}\n"
        f"- Day Duration: {dinamaana:.2f}\n"
        f"- Planetary Avasthas (Moods):\n{avasthas}\n\n"
        "6. PANCHANG (Five Limbs of Time):\n"
        f"{panchang_info}\n"
        "- Tithi: Crucial for relationship and emotional depth\n"
        "- Yoga: Crucial for health and innate nature\n"
        "- Karana: Crucial for career/work success\n\n"
        "7. TRANSIT SNAPSHOT (Current Real-Time Positions):\n"
        f"As of: {transit_timestamp}\n{transits}\n"
        "(Logic: If Transit Planet hits Natal Planet within 3 deg, it is a significant event. Retrograde planets hitting natal points are MORE POTENT (karmic/repetitive) than direct ones. All planets are checked for hits, not just slow planets.)\n\n"
        "11. VIMSHOTTARI DASHA TIMELINE (Relevant Period):\n"
        f"{timeline_full}\n\n"
        "12. BNN MODULE (Bhrigu Nandi Nadi - Geometry-Based Analysis):\n"
        f"{bnn_display_str}\n"
        "(Note: BNN uses Directional Grouping and Orbital Order instead of House-based analysis. Retrograde planets project into previous sign. Friend/Enemy relationships follow Deva/Asura groups, not Parashari Tatkalik Maitri.)\n\n"
        "13. UNIFIED BNN-PARASHARI KUNDALI (The Snapshot):\n"
        f"{unified_kundali}\n"
        "(Note: This table uses Whole Sign Houses (Rashi = House) for BNN geometry compatibility. Bhava Shift markers [→ HX] indicate planets that moved to different houses in Bhava Chalit chart. For Direction/Trines (BNN), use the Sign column. For Career/Outcome (Parashari), check Bhava Shift if present.)\n\n"
        "14. SPECIAL YOGAS:\n"
        f"{_build_yoga_text(structured_payload.get('special_yogas', []))}\n\n"
        "15. YOGA RULE COVERAGE SUMMARY:\n"
        f"{_build_yoga_coverage_text(structured_payload.get('yoga_rule_coverage', {}))}\n\n"
        + (f"16. YOGA RULE MATRIX — ALL CHECKED YOGAS:\n{_build_yoga_matrix_text(structured_payload.get('yoga_rule_matrix', []))}\n\n" if include_yoga_rule_matrix_in_packet else "") +
        "*** KARMA ALIGNMENT ANALYSIS ***\n\n"
        "Karma Alignment Principles:\n"
        "- 8th house: Past karma, debts, chronic issues\n"
        "- 12th house: Past life karma, losses, spiritual liberation\n"
        "- Saturn: Karmic lessons, delays, discipline\n"
        "- Rahu/Ketu: Karmic nodes, desires vs detachment\n"
        "- Dasha lords: Timing of karmic fruition\n"
        "- Retrograde planets: Karmic repetition, unresolved past\n"
        "- Bhava shifts: Karmic redirection of house significations\n\n"
        + _INSTRUCTION_BLOCK
    )

    kp_prompt = (
        _chart_subject + "\n"
        + build_system_role_block() + "\n"
        + build_controller_block() + "\n"
        "*** KP MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
        "A. CALCULATION SETTINGS\n"
        "Ayanamsa: KP (Krishnamurti VP291)\n"
        f"Dasha Ayanamsha: {astro_kp.DASHA_AYANAMSHA_MODE}\n"
        "House System: Placidus\nSub-Divisions: 249\n"
        f"Lagna: {lagna}\nMoon Nakshatra: {nak}\n\n"
        "*** KP PLACIDUS CUSPS (Sign / Star / Sub-Lords) ***\n"
        f"{kp_cusps_table}\n\n"
        "*** KP PLANETARY SIGN / STAR / SUB-LORDS ***\n"
        f"{kp_planets_table}\n\n"
        "*** KP RASI CHART (WITH FLAGS) ***\n"
        f"{rasi_chart_table}\n"
        "(Flags: R=Retrograde, Vargottama=Rasi sign matches Navamsa sign. "
        "In KP a debilitated/exalted planet still delivers results per its Star/Sub Lord significations.)\n\n"
        "*** KP PLANET SIGNIFICATION TABLE ***\n"
        f"{planet_signification_table}\n"
        "(4-Source Rule: 1. Star-lord occupancy, 2. Planet occupancy, "
        "3. Star-lord ownership, 4. Planet ownership — all via Placidus houses.)\n\n"
        "*** KP HOUSE SIGNIFICATORS (A/B/C/D) ***\n"
        f"{house_significators_table}\n"
        "(A=planets in star of occupant, B=occupant, C=planets in star of owner, D=owner)\n\n"
        "*** KP NAKSHATRA NADI TABLE ***\n"
        f"{nakshatra_nadi_table}\n"
        "(Interpretation priority: Sub Lord > Star Lord > Planet)\n\n"
        "*** KP CIL SUB-SUB TABLE (with Position Status) ***\n"
        f"{cil_sub_sub_table}\n"
        "(Position Status TRUE = planet is UNTENANTED — in its own star OR no planet occupies "
        "its stars. An untenanted planet is the STRONGEST significator for its own occupied/owned houses.)\n\n"
        "*** KP 4-STEP THEORY TABLE ***\n"
        f"{four_step_theory_table}\n"
        "(Chain: Planet → Star Lord → Sub Lord → Star Lord of Sub Lord)\n\n"
        "*** KP CIL SUB TABLE (Cuspal Interlinks) ***\n"
        f"{cil_sub_table}\n"
        "(t1=Involvement, t2=Commitment, t3=Final Confirmation, t4=Conditioning)\n\n"
        "*** KP RULING PLANETS (Birth Moment) ***\n"
        f"{ruling_planets_table}\n\n"
        "*** KP CURRENT RULING PLANETS (Judgment Moment) ***\n"
        f"{current_ruling_planets_table}\n\n"
        "*** KP FORTUNA TABLE ***\n"
        f"{fortuna_table}\n\n"
        "*** KP BADHAKA / MARAKA TABLE ***\n"
        f"{badhaka_maraka_table}\n\n"
        "*** KP NODAL DECODE TABLE ***\n"
        f"{nodal_decode_table}\n\n"
        "*** KP CUSP ASPECT TABLE ***\n"
        f"{kp_cusp_aspects_table}\n\n"
        "*** NAVAMSA CHECK (VARGOTTAMA) ***\n"
        f"{navamsa_check_table}\n"
        "(A vargottama planet gains extra strength in KP delivery.)\n\n"
        "*** CURRENT TIMING (Vimshottari Dasha — DBA) ***\n"
        f"{dasha_info}\n"
        f"Moon Dasha Balance at Birth: {moon_dasha_balance_display}\n"
        "(In KP, an event manifests ONLY during the DBA of planets that signify the relevant houses "
        "AND agree with Ruling Planets.)\n\n"
        "*** TRANSIT SNAPSHOT (KP Hit Theory) ***\n"
        f"As of: {transit_timestamp}\n{transits}\n"
        "(KP Hit Theory: A transit triggers an event when a significator transits through the "
        "Sign/Star/Sub of another significator of the same house group. "
        "Sun and Moon transits are the final TRIGGER for events promised by DBA lords.)\n\n"
        "*** KP PREDICTION METHODOLOGY ***\n\n"
        "A. PROMISE vs TIMING vs TRIGGER (Strict 3-Step Separation):\n"
        "   STEP 1 — PROMISE: Is the event promised?\n"
        "   → Check the Cuspal Sub-Lord (CSL) of the relevant house.\n"
        "   → If the CSL signifies favorable houses for the event, the event IS promised.\n"
        "   → If the CSL signifies detrimental houses, the event is DENIED.\n"
        "   → Example: For marriage (7th house), the 7th CSL must signify 2, 7, 11.\n"
        "             If it signifies 1, 6, 10, 12 instead → marriage denied/delayed.\n\n"
        "   STEP 2 — TIMING: When will it happen?\n"
        "   → Identify the DBA (Dasha-Bhukti-Anthra) lords currently running.\n"
        "   → The DBA lords MUST be significators of the relevant house group.\n"
        "   → Cross-check DBA lords against Ruling Planets (RP) at judgment time.\n"
        "   → If DBA lord appears in RPs, timing is confirmed for that period.\n\n"
        "   STEP 3 — TRIGGER: The exact date.\n"
        "   → Sun transiting the Sign/Star/Sub of a significator triggers the event.\n"
        "   → Moon transiting the Star/Sub of a significator narrows it to the day.\n"
        "   → The transit must be in the zone of a planet that is also in the RPs.\n\n"
        "B. CUSPAL SUB-LORD THEORY:\n"
        "   - The Sub-Lord of each cusp is the FINAL AUTHORITY on whether that house delivers.\n"
        "   - The CSL's signified houses determine WHAT the house will give.\n"
        "   - If CSL signifies houses favorable to the query → positive result.\n"
        "   - If CSL signifies houses unfavorable to the query → negative/denied.\n\n"
        "C. SIGNIFICATOR RANKING (4-Step Rule with A/B/C/D):\n"
        "   A = Planets in the star of the OCCUPANT (strongest)\n"
        "   B = OCCUPANT of the house\n"
        "   C = Planets in the star of the OWNER\n"
        "   D = OWNER of the house (weakest)\n"
        "   → A planet at level A overrides level D.\n"
        "   → If a planet is an A-level significator AND untenanted (Position Status = TRUE), "
        "it is the most powerful significator.\n\n"
        "D. UNTENANTED PLANETS (Critical KP Rule):\n"
        "   - Check the 'Position Status' column in the CIL Sub-Sub table.\n"
        "   - If a planet has Position Status = TRUE, it means NO other planet sits in its stars.\n"
        "   - Such a planet becomes the DIRECT and STRONGEST significator of its own "
        "occupied and owned houses.\n"
        "   - Always check for untenanted planets BEFORE ranking significators.\n\n"
        "E. RAHU/KETU NODAL AGENCY (Critical KP Rule):\n"
        "   - Rahu and Ketu do NOT give independent results. They act as AGENTS.\n"
        "   - Priority of agency:\n"
        "     1. Planet CONJOINED with the node (within the same sign)\n"
        "     2. Planet ASPECTING the node\n"
        "     3. The node's STAR LORD\n"
        "     4. The node's SIGN LORD (last resort)\n"
        "   - When Rahu/Ketu appear as significators, decode their agency to find "
        "the REAL planet delivering results.\n"
        "   - If a Node's sign lord appears in the Ruling Planets, the Node acts as "
        "a powerful proxy and should be treated as a Ruling Planet too.\n\n"
        "F. RULING PLANETS (RP) — Final Confirmation:\n"
        "   - RPs = Asc Sign Lord, Asc Star Lord, Moon Sign Lord, Moon Star Lord, Day Lord, "
        "Asc Sub Lord, Moon Sub Lord.\n"
        "   - An event will manifest ONLY during the DBA of planets present in the RPs.\n"
        "   - If a DBA lord is NOT in the RPs, that period will NOT trigger the event.\n"
        "   - RPs at the time of JUDGMENT (current moment) confirm which significators "
        "are active NOW.\n\n"
        "G. KP HIT THEORY (Transit Triggers):\n"
        "   - Transits hitting natal Placidus cusps within 1° trigger events.\n"
        "   - The transit planet must be a significator of the relevant house group.\n"
        "   - Sun/Moon transits through the Star/Sub of DBA lords provide the exact trigger date.\n"
        "   - Slow planets (Saturn, Jupiter, Rahu/Ketu) set the WINDOW; "
        "fast planets (Sun, Moon) provide the TRIGGER within that window.\n\n"
        "\n"
        + _INSTRUCTION_BLOCK
    )

    with tabs_text[0]:
        st.code(unified_prompt, language="markdown")
    with tabs_text[1]:
        st.code(bphs_prompt, language="markdown")
    with tabs_text[2]:
        st.code(kp_prompt, language="markdown")

    # JSON for Gemini (MASTER DATA PACKETs) – in three tabs
    if include_structured_json:
        st.write("---")
        import json as _json

        tabs = st.tabs(["Both (Full structured_payload)", "BPHS/BNN Only", "KP Only"])

        def _export_payload(payload: dict) -> dict:
            """Strip debug audit keys unless the export toggle is on."""
            _filtered = dict(payload)
            if not include_debug_in_export:
                _debug_keys = {
                    "retrograde_motion_audit", "dasha_epoch_audit",
                    "dasha_timeline_debug", "cusp_subsub_audit",
                    "cusp_engine_comparison_audit", "special_yogas_debug_full",
                    "_planet_positions_raw"
                }
                _filtered = {k: v for k, v in _filtered.items() if k not in _debug_keys}
            if not (include_debug_in_export or include_yoga_rule_matrix_in_packet):
                _filtered.pop("yoga_rule_matrix", None)
            return _filtered

        with tabs[0]:
            st.subheader("📦 Full structured_payload (BPHS + KP)")
            both_json = _json.dumps(_export_payload(structured_payload), separators=(",", ":"), ensure_ascii=False)
            st.code(both_json, language="json")

        with tabs[1]:
            st.subheader("📦 BPHS/BNN MASTER DATA PACKET")
            bphs_json = _json.dumps(_export_payload(structured_payload), separators=(",", ":"), ensure_ascii=False)
            st.code(bphs_json, language="json")


        with tabs[2]:
            st.subheader("📦 KP MASTER DATA PACKET")
            kp_only = {
                "kp_master_packet": structured_payload.get("kp_master_packet"),
                "kp_prediction": structured_payload.get("kp_prediction"),
                "kp_astrology_matrix": structured_payload.get("kp_astrology_matrix"),
            }
            kp_json = _json.dumps(kp_only, separators=(",", ":"), ensure_ascii=False)
            st.code(kp_json, language="json")

    # Optional: show compact tables for reference
    with st.expander("📊 Natal Chart (Hardware)"):
        st.markdown(natal_table)
    with st.expander("📊 D1 Rashi Chart (Whole Sign)"):
        st.markdown(d1)
    with st.expander("📊 Bhava Chalit (Sripati)"):
        st.markdown(bhava_chalit)

else:
    # ── Skeleton preview: show all headings/table headers with blank data ──
    st.write("---")
    st.info("👆 Enter birth details above and click **Generate KP MASTER DATA PACKET** to compute your chart.")
    st.write("---")
    st.subheader("📋 Preview — What Will Be Calculated")

    _E = ""  # empty placeholder

    skel_tabs = st.tabs(["Unified (BPHS + KP)", "BPHS / BNN Only", "KP Only"])

    # ── helpers for blank tables ──
    def _blank_table(headers: list[str], rows: int = 0, stub_col0: list[str] | None = None) -> str:
        hdr = "| " + " | ".join(headers) + " |"
        sep = "| " + " | ".join([":---"] * len(headers)) + " |"
        lines = [hdr, sep]
        if stub_col0:
            for label in stub_col0:
                lines.append("| " + label + " | " + " | ".join([_E] * (len(headers) - 1)) + " |")
        else:
            for _ in range(rows):
                lines.append("| " + " | ".join([_E] * len(headers)) + " |")
        return "\n".join(lines)

    _PLANETS_9 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    _HOUSES_12 = [str(i) for i in range(1, 13)]

    # ── Skeleton: KP-only tables ──
    skel_kp_cusps = _blank_table(
        ["House", "Longitude", "Sign", "Sign Lord", "Star Lord", "Sub Lord", "Sub-Sub Lord"],
        stub_col0=_HOUSES_12,
    )
    skel_kp_planets = _blank_table(
        ["Planet", "Sign", "Sign Lord", "Star Lord", "Sub Lord", "Sub-Sub Lord", "Retrograde"],
        stub_col0=["Ascendant"] + _PLANETS_9,
    )
    skel_rasi = _blank_table(
        ["Planet", "Longitude", "Sign", "House", "Retrograde", "Combust", "Vargottama", "Exalted", "Debilitated"],
        stub_col0=_PLANETS_9,
    )
    skel_signif = _blank_table(["Planet", "Houses Signified"], stub_col0=_PLANETS_9)
    skel_house_sig = _blank_table(["House", "Significators"], stub_col0=_HOUSES_12)
    skel_nadi = _blank_table(["Planet", "Star Lord", "Sub Lord"], stub_col0=_PLANETS_9)
    skel_cil_sub_sub = _blank_table(
        ["Planet", "Star", "Sub", "Sub Sub", "Position Status"], stub_col0=_PLANETS_9,
    )
    skel_4step = _blank_table(
        ["Planet", "Star Lord", "Sub Lord", "Star Lord of Sub Lord"], stub_col0=_PLANETS_9,
    )
    skel_cil_sub = _blank_table(
        ["Cuspal", "Involvement (t1)", "Commitment (t2)", "Confirmation (t3)", "Conditioning (t4)"],
        stub_col0=_HOUSES_12,
    )
    skel_rp = _blank_table(
        ["Asc Nakshatra Lord", "Asc Sign Lord", "Moon Nakshatra Lord",
         "Moon Sign Lord", "Day Lord", "Asc Sub Lord", "Moon Sub Lord"], rows=1,
    )
    skel_crp = _blank_table(
        ["Date", "Asc Star Lord", "Asc Sign Lord", "Moon Star Lord",
         "Moon Sign Lord", "Day Lord", "Asc Sub Lord", "Moon Sub Lord"], rows=1,
    )
    skel_fortuna = _blank_table(
        ["Fortuna Degree", "Fortuna Sign", "Fortuna House", "Fortuna Sub", "Fortuna Sub Sub", "KP Ayanamsa"], rows=1,
    )
    skel_badhaka_maraka = _blank_table(
        ["Lagna Sign", "Lagna Type", "Badhaka House", "Maraka Houses"], rows=1,
    )
    skel_nodal_decode = _blank_table(
        ["Node", "Conjoined With (Same Sign)", "Conjoined With (Same Star)", "Star Lord", "Sign Lord", "Node Agent", "Agency Source"],
        stub_col0=["Rahu", "Ketu"],
    )
    skel_aspects = _blank_table(
        ["Planet"] + _HOUSES_12, stub_col0=_PLANETS_9,
    )
    skel_navamsa = _blank_table(
        ["Planet", "Rasi Sign", "Navamsa Sign", "Vargottama"], stub_col0=_PLANETS_9,
    )

    # ── Skeleton: BPHS-only tables ──
    skel_natal = _blank_table(
        ["Planet (Deg Nak(Pada))", "Sign", "Degree", "Nakshatra", "Pada",
         "Retrograde", "Baladi Avastha", "Bhava House"],
        stub_col0=_PLANETS_9,
    )
    skel_d1 = _blank_table(["House", "Planets (Deg/Nak/Pada)", "Sign"], stub_col0=_HOUSES_12)
    skel_bhava = _blank_table(["Bhava House", "Planets (Deg/Nak/Pada)", "Sign"], stub_col0=_HOUSES_12)

    # ────────────────────────────────────────────────────────────
    # TAB 1: Unified (BPHS + KP)
    # ────────────────────────────────────────────────────────────
    with skel_tabs[0]:
        st.code(
            "SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (The Vedic Calculator & Seer)\n\n"
            "*** MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
            "1. NATAL CHART (Hardware):\n"
            f"{skel_natal}\n\n"
            "8. D1 HOUSE CHART (Rashi - Whole Sign):\n"
            f"{skel_d1}\n\n"
            "9. BHAVA CHALIT CHART (Sripati - House Shifts):\n"
            f"{skel_bhava}\n\n"
            "10. SHODASHAVARGA MATRIX (16 CHARTS):\n"
            "  (D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45, D60)\n\n"
            "2. SPECIAL POINTS (Vulnerable Spots):\n"
            "- 64th Navamsa Sign:\n"
            "- 22nd Drekkana Sign:\n"
            "- Upagrahas:\n"
            "  Gulika:\n"
            "  Mandi:\n\n"
            "3. ASHTAKAVARGA (Bhinna + Sarva):\n"
            "  (BAV matrix for 7 planets × 12 signs + SAV totals)\n\n"
            "4. CURRENT TIMING (Vimshottari Dasha System):\n\n"
            "5. TIME VARIABLES:\n"
            "- Birth Ghati:\n"
            "- Day Duration:\n"
            "- Planetary Avasthas (Moods):\n"
            "  Sun: / Moon: / Mars: / Mercury: / Jupiter: / Venus: / Saturn: / Rahu: / Ketu:\n\n"
            "6. PANCHANG (Five Limbs of Time):\n"
            "  Tithi: / Yoga: / Karana:\n\n"
            "7. TRANSIT SNAPSHOT (Current Real-Time Positions):\n\n"
            "11. VIMSHOTTARI DASHA TIMELINE (Relevant Period):\n\n"
            "12. BNN MODULE (Bhrigu Nandi Nadi):\n\n"
            "13. UNIFIED BNN-PARASHARI KUNDALI:\n\n"
            "*** KP-SPECIFIC DATA ***\n\n"
            "*** KP PLACIDUS CUSPS (Sign / Star / Sub-Lords) ***\n"
            f"{skel_kp_cusps}\n\n"
            "*** KP PLANETARY SIGN / STAR / SUB-LORDS ***\n"
            f"{skel_kp_planets}\n\n"
            f"*** KP RASI CHART (WITH FLAGS) ***\n{skel_rasi}\n\n"
            f"*** KP PLANET SIGNIFICATION TABLE ***\n{skel_signif}\n\n"
            f"*** KP HOUSE SIGNIFICATORS (A/B/C/D) ***\n{skel_house_sig}\n\n"
            f"*** KP NAKSHATRA NADI TABLE ***\n{skel_nadi}\n\n"
            f"*** KP CIL SUB-SUB TABLE ***\n{skel_cil_sub_sub}\n\n"
            f"*** KP 4-STEP THEORY TABLE ***\n{skel_4step}\n\n"
            f"*** KP CIL SUB TABLE (Cuspal Interlinks) ***\n{skel_cil_sub}\n\n"
            f"*** KP RULING PLANETS ***\n{skel_rp}\n\n"
            f"*** KP CURRENT RULING PLANETS ***\n{skel_crp}\n\n"
            f"*** KP FORTUNA TABLE ***\n{skel_fortuna}\n\n"
            f"*** KP BADHAKA / MARAKA TABLE ***\n{skel_badhaka_maraka}\n\n"
            f"*** KP NODAL DECODE TABLE ***\n{skel_nodal_decode}\n\n"
            f"*** KP CUSP ASPECT TABLE ***\n{skel_aspects}\n\n"
            f"*** NAVAMSA CHECK (VARGOTTAMA) ***\n{skel_navamsa}\n",
            language="markdown",
        )

    # ────────────────────────────────────────────────────────────
    # TAB 2: BPHS / BNN Only
    # ────────────────────────────────────────────────────────────
    with skel_tabs[1]:
        st.code(
            "SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (BPHS + BNN + Karma Alignment Engine)\n\n"
            "*** MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
            "1. NATAL CHART (Hardware):\n"
            f"{skel_natal}\n\n"
            "8. D1 HOUSE CHART (Rashi - Whole Sign):\n"
            f"{skel_d1}\n\n"
            "9. BHAVA CHALIT CHART (Sripati - House Shifts):\n"
            f"{skel_bhava}\n\n"
            "10. SHODASHAVARGA MATRIX (16 CHARTS):\n"
            "  (D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45, D60)\n\n"
            "2. SPECIAL POINTS (Vulnerable Spots):\n"
            "- 64th Navamsa Sign:\n"
            "- 22nd Drekkana Sign:\n"
            "- Upagrahas:\n"
            "  Gulika:\n"
            "  Mandi:\n\n"
            "3. ASHTAKAVARGA (Bhinna + Sarva):\n"
            "  (BAV matrix for 7 planets × 12 signs + SAV totals)\n\n"
            "4. CURRENT TIMING (Vimshottari Dasha System):\n\n"
            "5. TIME VARIABLES:\n"
            "- Birth Ghati:\n"
            "- Day Duration:\n"
            "- Planetary Avasthas (Moods):\n"
            "  Sun: / Moon: / Mars: / Mercury: / Jupiter: / Venus: / Saturn: / Rahu: / Ketu:\n\n"
            "6. PANCHANG (Five Limbs of Time):\n"
            "  Tithi: / Yoga: / Karana:\n\n"
            "7. TRANSIT SNAPSHOT (Current Real-Time Positions):\n\n"
            "11. VIMSHOTTARI DASHA TIMELINE (Relevant Period):\n\n"
            "12. BNN MODULE (Bhrigu Nandi Nadi):\n\n"
            "13. UNIFIED BNN-PARASHARI KUNDALI:\n\n"
            "*** KARMA ALIGNMENT ANALYSIS ***\n"
            "- 8th house: Past karma, debts, chronic issues\n"
            "- 12th house: Past life karma, losses, spiritual liberation\n"
            "- Saturn: Karmic lessons, delays, discipline\n"
            "- Rahu/Ketu: Karmic nodes, desires vs detachment\n",
            language="markdown",
        )

    # ────────────────────────────────────────────────────────────
    # TAB 3: KP Only (Pure KP — no BPHS items)
    # ────────────────────────────────────────────────────────────
    with skel_tabs[2]:
        st.code(
            "SYSTEM ROLE: 'BRAHMA-DAIVAGYA' (Pure KP Engine — Krishnamurti Paddhati)\n\n"
            "*** KP MASTER DATA PACKET (PRE-CALCULATED) ***\n\n"
            "KP FUNDAMENTALS:\n"
            "- Ayanamsa: KP (Krishnamurti)\n"
            "- House System: Placidus (unequal houses)\n"
            "- Sub-Divisions: 249 sub-divisions\n"
            "- Prediction Method: Cuspal Sub-Lord → Signification → DBA Timing → Transit Trigger\n\n"
            "Lagna:\nMoon Nakshatra:\n\n"
            "*** KP PLACIDUS CUSPS (Sign / Star / Sub-Lords) ***\n"
            f"{skel_kp_cusps}\n\n"
            "*** KP PLANETARY SIGN / STAR / SUB-LORDS ***\n"
            f"{skel_kp_planets}\n\n"
            f"*** KP RASI CHART (WITH FLAGS) ***\n{skel_rasi}\n\n"
            f"*** KP PLANET SIGNIFICATION TABLE ***\n{skel_signif}\n\n"
            f"*** KP HOUSE SIGNIFICATORS (A/B/C/D) ***\n{skel_house_sig}\n\n"
            f"*** KP NAKSHATRA NADI TABLE ***\n{skel_nadi}\n\n"
            f"*** KP CIL SUB-SUB TABLE (with Position Status) ***\n{skel_cil_sub_sub}\n\n"
            f"*** KP 4-STEP THEORY TABLE ***\n{skel_4step}\n\n"
            f"*** KP CIL SUB TABLE (Cuspal Interlinks) ***\n{skel_cil_sub}\n\n"
            f"*** KP RULING PLANETS (Birth Moment) ***\n{skel_rp}\n\n"
            f"*** KP CURRENT RULING PLANETS (Judgment Moment) ***\n{skel_crp}\n\n"
            f"*** KP FORTUNA TABLE ***\n{skel_fortuna}\n\n"
            f"*** KP BADHAKA / MARAKA TABLE ***\n{skel_badhaka_maraka}\n\n"
            f"*** KP NODAL DECODE TABLE ***\n{skel_nodal_decode}\n\n"
            f"*** KP CUSP ASPECT TABLE ***\n{skel_aspects}\n\n"
            f"*** NAVAMSA CHECK (VARGOTTAMA) ***\n{skel_navamsa}\n\n"
            "*** CURRENT TIMING (Vimshottari Dasha — DBA) ***\n\n"
            "Moon Dasha Balance at Birth:\n\n"
            "*** TRANSIT SNAPSHOT (KP Hit Theory) ***\n\n"
            "*** KP PREDICTION METHODOLOGY ***\n"
            "A. PROMISE vs TIMING vs TRIGGER (3-Step Separation)\n"
            "B. CUSPAL SUB-LORD THEORY\n"
            "C. SIGNIFICATOR RANKING (A/B/C/D)\n"
            "D. UNTENANTED PLANETS (Position Status = TRUE)\n"
            "E. RAHU/KETU NODAL AGENCY\n"
            "F. RULING PLANETS (RP) — Final Confirmation\n"
            "G. KP HIT THEORY (Transit Triggers)\n",
            language="markdown",
        )
