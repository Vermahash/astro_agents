from __future__ import annotations

"""
Minimal KP-style reasoning engine wired to the MASTER DATA PACKET produced by astro_app_v2.

This module does not calculate any longitudes or charts. It expects a pre-populated
MASTER DATA PACKET and focuses only on:
- House strength via SAV (>30 / <25 rule)
- Transit "Hit Theory" (within 3°, retrograde emphasis, Dasha-gun check)
- Panchang modulation (Tithi/Yoga/Karana)
- Bhava Chalit shifts (Rashi Hx → Bhava Hy)
- Planetary avasthas / moods

The main entrypoint is `analyze_master_packet`.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict


LifeArea = Literal[
    "overall",
    "health",
    "career",
    "finance",
    "relationships",
    "family",
    "property",
    "spirituality",
]


class TransitHit(TypedDict, total=False):
    transit_planet: str
    natal_target_type: str
    natal_target_id: str
    orb_deg: float
    retrograde: bool
    sign: Optional[str]
    house: Optional[int]


class AshtakavargaSAV(TypedDict, total=False):
    # keys "1".."12" -> int score
    ...


class PanchangInfo(TypedDict, total=False):
    tithi: Optional[str]
    yoga: Optional[str]
    karana: Optional[str]


class DashaInfo(TypedDict, total=False):
    maha: Optional[str]
    antara: Optional[str]
    lord_chain: List[str]


class BhavaPosition(TypedDict, total=False):
    rashi_house: int
    bhava_house: int


class MasterPacket(TypedDict, total=False):
    system_role: str
    name: str
    gender: Optional[str]
    birth_datetime: Optional[str]
    birth_place: Optional[str]
    timezone: Optional[str]

    lagna_sign: Optional[str]
    lagna_nakshatra: Optional[str]
    moon_sign: Optional[str]
    moon_nakshatra: Optional[str]

    d1_planets: Dict[str, Dict[str, Any]]
    bhava_positions: Dict[str, BhavaPosition]

    special_points: Dict[str, Any]
    ashtakavarga_sav: AshtakavargaSAV
    dasha: DashaInfo
    planet_avasthas: Dict[str, str]
    panchang: PanchangInfo

    transit_as_of: Optional[str]
    transit_hits: List[TransitHit]


@dataclass
class RuleHit:
    area: LifeArea
    severity: Literal["supportive", "neutral", "challenging"]
    weight: float
    tag: str
    description: str


@dataclass
class AreaSummary:
    area: LifeArea
    score: float
    supportive_hits: List[RuleHit]
    challenging_hits: List[RuleHit]
    neutral_hits: List[RuleHit]
    narrative: str


def analyze_master_packet(packet: MasterPacket) -> Dict[str, Any]:
    """High-level orchestrator used by astro_app_v2.

    Returns a dict suitable to embed into the structured JSON payload.
    """

    rule_hits: List[RuleHit] = []
    rule_hits += _rules_from_sav(packet)
    rule_hits += _rules_from_transit_hits(packet)
    rule_hits += _rules_from_panchang(packet)
    rule_hits += _rules_from_bhava_shifts(packet)
    rule_hits += _rules_from_avasthas(packet)

    # Detect classical special yogas from the packet (chart-specific only)
    special_yogas = _detect_special_yogas(packet)

    area_summaries = _summarise_by_area(rule_hits)
    overall_summary = _build_overall_summary(packet, area_summaries)

    return {
        "meta": {
            "system_role": packet.get("system_role"),
            "name": packet.get("name"),
            "birth_place": packet.get("birth_place"),
            "birth_datetime": packet.get("birth_datetime"),
            "timezone": packet.get("timezone"),
            "transit_as_of": packet.get("transit_as_of"),
        },
        "current_timing": {
            "dasha": packet.get("dasha"),
            "panchang": packet.get("panchang"),
        },
        "areas": {a.area: _area_to_dict(a) for a in area_summaries},
        "overall": overall_summary,
        "special_yogas": special_yogas,
        "raw_rule_hits": [hit.__dict__ for hit in rule_hits],
    }


def _detect_special_yogas(packet: MasterPacket) -> List[Dict[str, Any]]:
    """
    Detect a focused set of classical yogas from the MASTER PACKET.

    This operates purely on pre-computed fields (no degree math here):
    - `d1_planets` with `sign_index` and `house_from_lagna`
    - `bhava_positions` for house shifts

    It returns only yogas that are actually present in this chart.
    """
    d1 = packet.get("d1_planets") or {}
    bhava = packet.get("bhava_positions") or {}

    # Helper: get sign index / house from lagna for a planet, if available
    def _sign(p: str) -> Optional[int]:
        info = d1.get(p) or {}
        val = info.get("sign_index")
        return int(val) if isinstance(val, int) else None

    def _house(p: str) -> Optional[int]:
        info = d1.get(p) or {}
        val = info.get("house_from_lagna")
        return int(val) if isinstance(val, int) else None

    def _conj(p1: str, p2: str) -> bool:
        s1, s2 = _sign(p1), _sign(p2)
        return s1 is not None and s1 == s2

    yogas: List[Dict[str, Any]] = []

    # 1. Budh–Aditya Yoga: Sun + Mercury conjunction
    if _conj("Sun", "Mercury"):
        yogas.append(
            {
                "name": "Budh-Aditya Yoga",
                "planets_involved": ["Sun", "Mercury"],
                "houses": [_house("Sun"), _house("Mercury")],
                "strength_note": "Sun and Mercury conjoined, enhancing intellect/communication.",
                "effect_summary": "Supports clarity of thought, learning, commerce and articulation.",
            }
        )

    # 2. Chandra–Mangal Yoga: Moon + Mars conjunction
    if _conj("Moon", "Mars"):
        yogas.append(
            {
                "name": "Chandra-Mangal Yoga",
                "planets_involved": ["Moon", "Mars"],
                "houses": [_house("Moon"), _house("Mars")],
                "strength_note": "Moon and Mars conjoined, activating emotional drive and initiative.",
                "effect_summary": "Can give strong entrepreneurship and courage; needs emotional balance.",
            }
        )

    # 3. Vish (Saturn–Moon) style connection: simple conjunction
    if _conj("Saturn", "Moon"):
        yogas.append(
            {
                "name": "Saturn–Moon Conjunction",
                "planets_involved": ["Saturn", "Moon"],
                "houses": [_house("Saturn"), _house("Moon")],
                "strength_note": "Saturn and Moon together, intensifying mental seriousness and responsibility.",
                "effect_summary": "Suggests emotional heaviness, responsibility and karmic themes around mind/mother.",
            }
        )

    # 4. Grahan Yoga: Sun or Moon with Rahu/Ketu
    for luminary in ("Sun", "Moon"):
        if _conj(luminary, "Rahu") or _conj(luminary, "Ketu"):
            node = "Rahu" if _conj(luminary, "Rahu") else "Ketu"
            yogas.append(
                {
                    "name": "Grahan Yoga",
                    "planets_involved": [luminary, node],
                    "houses": [_house(luminary), _house(node)],
                    "strength_note": f"{luminary} with {node}, eclipse-style emphasis on that house/sign.",
                    "effect_summary": "Brings intense karmic focus and sensitivity to matters of that house.",
                }
            )

    # 5. Sanyasa flavour: 4 or more planets in one house (from bhava_positions)
    house_counts: Dict[int, int] = {}
    for planet, pos in bhava.items():
        h = pos.get("bhava_house")
        if isinstance(h, int):
            house_counts[h] = house_counts.get(h, 0) + 1
    for h, count in house_counts.items():
        if count >= 4:
            yogas.append(
                {
                    "name": "Multi-Planet Concentration",
                    "planets_involved": [
                        p for p, pos in bhava.items() if pos.get("bhava_house") == h
                    ],
                    "houses": [h],
                    "strength_note": f"{count} or more planets gathered in house {h}.",
                    "effect_summary": "Strong focus of life energy in this house; in some traditions linked to Sanyasa-type intensity.",
                }
            )

    return yogas


def _rules_from_sav(packet: MasterPacket) -> List[RuleHit]:
    sav = packet.get("ashtakavarga_sav") or {}
    out: List[RuleHit] = []

    house_to_area: Dict[str, LifeArea] = {
        "1": "health",
        "2": "finance",
        "3": "overall",
        "4": "family",
        "5": "relationships",
        "6": "health",
        "7": "relationships",
        "8": "health",
        "9": "spirituality",
        "10": "career",
        "11": "finance",
        "12": "spirituality",
    }

    for house_str, score in sav.items():
        try:
            score_int = int(score)  # type: ignore[arg-type]
        except Exception:
            continue

        area = house_to_area.get(house_str, "overall")
        tag_base = f"SAV_H{house_str}"

        if score_int >= 31:
            out.append(
                RuleHit(
                    area=area,
                    severity="supportive",
                    weight=1.5,
                    tag=tag_base + "_STRONG",
                    description=f"House {house_str} has strong SAV ({score_int}), indicating durable support in this area.",
                )
            )
        elif score_int <= 24:
            out.append(
                RuleHit(
                    area=area,
                    severity="challenging",
                    weight=1.5,
                    tag=tag_base + "_WEAK",
                    description=f"House {house_str} has weak SAV ({score_int}), indicating vulnerability and need for conscious effort.",
                )
            )
        else:
            out.append(
                RuleHit(
                    area=area,
                    severity="neutral",
                    weight=0.5,
                    tag=tag_base + "_AVERAGE",
                    description=f"House {house_str} has average SAV ({score_int}); results depend more on timing and transits.",
                )
            )

    return out


def _rules_from_transit_hits(packet: MasterPacket) -> List[RuleHit]:
    hits = packet.get("transit_hits") or []
    dasha = packet.get("dasha") or {}
    lord_chain: List[str] = dasha.get("lord_chain") or []

    out: List[RuleHit] = []

    def _area_for_hit(house: Optional[int], target_type: str) -> LifeArea:
        if target_type == "planet":
            return "overall"
        if house is None:
            return "overall"
        if house == 1:
            return "health"
        if house in (2, 11):
            return "finance"
        if house in (3, 9):
            return "overall"
        if house == 4:
            return "family"
        if house in (5, 7):
            return "relationships"
        if house in (6, 8):
            return "health"
        if house == 10:
            return "career"
        if house == 12:
            return "spirituality"
        return "overall"

    benefics = {"Jupiter", "Venus", "Mercury", "Waxing Moon"}
    malefics = {"Saturn", "Mars", "Rahu", "Ketu", "Waning Moon", "Sun"}

    for h in hits:
        planet = h.get("transit_planet")
        if not planet:
            continue

        house = h.get("house")
        target_type = h.get("natal_target_type", "planet")
        area = _area_for_hit(house, target_type)

        try:
            orb = abs(float(h.get("orb_deg", 99.0)))
        except Exception:
            continue

        if orb > 3.0:
            continue

        retro = bool(h.get("retrograde", False))
        natal_id = h.get("natal_target_id", "?")

        base_weight = 1.0
        if retro:
            base_weight *= 1.4
        if planet in lord_chain:
            base_weight *= 1.6

        if planet in benefics:
            severity: Literal["supportive", "neutral", "challenging"] = "supportive"
        elif planet in malefics:
            severity = "challenging"
        else:
            severity = "neutral"

        desc_parts = [
            f"Transit {planet} closely hits natal {target_type} {natal_id} (orb {orb:.2f}°)",
        ]
        if retro:
            desc_parts.append("planet is retrograde, repeating or deepening karmic themes")
        if planet in lord_chain:
            desc_parts.append("hit is tied to the running Dasha, increasing likelihood of manifestation")

        out.append(
            RuleHit(
                area=area,
                severity=severity,
                weight=base_weight,
                tag=f"HIT_{planet}_{target_type}_{natal_id}",
                description="; ".join(desc_parts),
            )
        )

    return out


def _rules_from_panchang(packet: MasterPacket) -> List[RuleHit]:
    p = packet.get("panchang") or {}
    tithi = (p.get("tithi") or "").lower()
    yoga = (p.get("yoga") or "").lower()
    karana = (p.get("karana") or "").lower()

    out: List[RuleHit] = []

    if tithi:
        if "purnima" in tithi or "full" in tithi:
            out.append(
                RuleHit(
                    area="relationships",
                    severity="supportive",
                    weight=0.8,
                    tag="TITHI_PURNIMA",
                    description="Full-moon tithi enhances emotional expressiveness and relational visibility.",
                )
            )
        if "amavasya" in tithi or "new" in tithi:
            out.append(
                RuleHit(
                    area="relationships",
                    severity="challenging",
                    weight=0.8,
                    tag="TITHI_AMAVASYA",
                    description="New-moon tithi internalises emotions; relationships may demand conscious openness.",
                )
            )

    if yoga:
        if "shubha" in yoga or "saubhagya" in yoga:
            out.append(
                RuleHit(
                    area="health",
                    severity="supportive",
                    weight=0.7,
                    tag="YOGA_SHUBHA",
                    description="A benefic yoga at birth supports general vitality and ease in life-flow.",
                )
            )

    if karana:
        if "bava" in karana or "balava" in karana:
            out.append(
                RuleHit(
                    area="career",
                    severity="supportive",
                    weight=0.7,
                    tag="KARANA_MOVING",
                    description="Dynamic karanas at birth favour initiative and adaptability in work.",
                )
            )

    return out


def _rules_from_bhava_shifts(packet: MasterPacket) -> List[RuleHit]:
    bhava_positions = packet.get("bhava_positions") or {}
    out: List[RuleHit] = []

    for planet, pos in bhava_positions.items():
        rashi_h = pos.get("rashi_house")
        bhava_h = pos.get("bhava_house")
        if not rashi_h or not bhava_h or rashi_h == bhava_h:
            continue

        area_from = _area_for_house_basic(rashi_h)
        area_to = _area_for_house_basic(bhava_h)

        out.append(
            RuleHit(
                area=area_to,
                severity="neutral",
                weight=1.0,
                tag=f"BHAVA_SHIFT_{planet}",
                description=(
                    f"{planet} shifts from Rashi house {rashi_h} to Bhava house {bhava_h}, "
                    f"re-routing its primary results from {area_from} into {area_to}."
                ),
            )
        )

    return out


def _rules_from_avasthas(packet: MasterPacket) -> List[RuleHit]:
    avasthas = packet.get("planet_avasthas") or {}
    out: List[RuleHit] = []

    soft_states = {"bala", "kumara", "yuva", "uddipta"}
    afflicted_states = {"mrityu", "mrita", "vriddha", "sushupti", "agitated"}

    for planet, state_raw in avasthas.items():
        state = str(state_raw).lower().strip()
        if not state:
            continue

        if any(k in state for k in soft_states):
            out.append(
                RuleHit(
                    area="overall",
                    severity="supportive",
                    weight=0.6,
                    tag=f"AVASTHA_{planet}_SOFT",
                    description=f"{planet} is in a relatively strong/awake avastha ({state}), easing its significations.",
                )
            )
        if any(k in state for k in afflicted_states):
            out.append(
                RuleHit(
                    area="overall",
                    severity="challenging",
                    weight=0.6,
                    tag=f"AVASTHA_{planet}_AFFLICTED",
                    description=f"{planet} appears weakened or stressed in avastha ({state}), requiring remedial awareness.",
                )
            )

    return out


def _area_for_house_basic(h: int) -> LifeArea:
    if h == 1:
        return "health"
    if h in (2, 11):
        return "finance"
    if h in (3, 9):
        return "overall"
    if h == 4:
        return "family"
    if h in (5, 7):
        return "relationships"
    if h in (6, 8):
        return "health"
    if h == 10:
        return "career"
    if h == 12:
        return "spirituality"
    return "overall"


def _summarise_by_area(hits: List[RuleHit]) -> List[AreaSummary]:
    by_area: Dict[LifeArea, Dict[str, Any]] = {}

    for h in hits:
        bucket = by_area.setdefault(
            h.area,
            {"supportive": [], "challenging": [], "neutral": [], "score": 0.0},
        )
        if h.severity == "supportive":
            bucket["supportive"].append(h)
            bucket["score"] += h.weight
        elif h.severity == "challenging":
            bucket["challenging"].append(h)
            bucket["score"] -= h.weight
        else:
            bucket["neutral"].append(h)

    summaries: List[AreaSummary] = []
    for area, data in by_area.items():
        score = float(data["score"])
        narrative = _build_area_narrative(
            area,
            score,
            data["supportive"],
            data["challenging"],
        )
        summaries.append(
            AreaSummary(
                area=area,
                score=score,
                supportive_hits=data["supportive"],
                challenging_hits=data["challenging"],
                neutral_hits=data["neutral"],
                narrative=narrative,
            )
        )

    # Ensure all areas exist for stable JSON shape
    for area in (
        "overall",
        "health",
        "career",
        "finance",
        "relationships",
        "family",
        "property",
        "spirituality",
    ):
        if area not in [s.area for s in summaries]:
            summaries.append(
                AreaSummary(
                    area=area,  # type: ignore[arg-type]
                    score=0.0,
                    supportive_hits=[],
                    challenging_hits=[],
                    neutral_hits=[],
                    narrative="No strong promises or pressures detected; results depend mainly on effort and minor transits.",
                )
            )

    return summaries


def _build_area_narrative(
    area: LifeArea,
    score: float,
    supportive: List[RuleHit],
    challenging: List[RuleHit],
) -> str:
    if area == "overall":
        label = "Overall life pattern"
    elif area == "health":
        label = "Health and vitality"
    elif area == "career":
        label = "Career and karma-bhumi"
    elif area == "finance":
        label = "Wealth, income and resources"
    elif area == "relationships":
        label = "Relationships, marriage and agreements"
    elif area == "family":
        label = "Home, family and emotional base"
    elif area == "property":
        label = "Property, vehicles and fixed assets"
    else:
        label = "Spirituality, inner life and retreat"

    if score > 2.5:
        tone = "strongly supported with multiple harmonious combinations."
    elif score > 0.8:
        tone = "generally supported, though timing and choices still matter."
    elif -0.8 <= score <= 0.8:
        tone = "balanced; neither strongly promised nor denied, so conscious effort decides outcomes."
    elif score >= -2.5:
        tone = "under moderate strain; disciplined choices and remedies can significantly improve the picture."
    else:
        tone = "under strong karmic pressure; patience, remedial measures and spiritual perspective are essential."

    key_support = supportive[0].description if supportive else ""
    key_challenge = challenging[0].description if challenging else ""

    parts = [f"{label} is {tone}"]
    if key_support:
        parts.append(f"Key support: {key_support}")
    if key_challenge:
        parts.append(f"Key challenge: {key_challenge}")

    return " ".join(parts)


def _build_overall_summary(packet: MasterPacket, areas: List[AreaSummary]) -> Dict[str, Any]:
    overall_area = next((a for a in areas if a.area == "overall"), None)
    if overall_area is None:
        base = {
            "score": 0.0,
            "narrative": "Overall pattern appears balanced; detailed events depend on specific Dashas and transits.",
        }
    else:
        base = {"score": overall_area.score, "narrative": overall_area.narrative}

    dasha = packet.get("dasha") or {}
    maha = dasha.get("maha")
    antara = dasha.get("antara")

    timing_line = ""
    if maha and antara:
        timing_line = (
            f"Currently running {maha}-{antara} period; events that match their house-links and significations "
            "are more likely to manifest."
        )
    elif maha:
        timing_line = f"Currently running {maha} Mahadasha, colouring the overall life tone."

    if timing_line:
        base["narrative"] = timing_line + " " + base["narrative"]

    return base


def _area_to_dict(area: AreaSummary) -> Dict[str, Any]:
    return {
        "score": area.score,
        "narrative": area.narrative,
        "supportive": [h.__dict__ for h in area.supportive_hits],
        "challenging": [h.__dict__ for h in area.challenging_hits],
        "neutral": [h.__dict__ for h in area.neutral_hits],
    }


__all__ = ["analyze_master_packet", "MasterPacket"]

