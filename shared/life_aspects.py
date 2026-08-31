"""
Book-grounded life-aspect catalog (BPHS 12 bhavas + KP event houses + Nadi sets).

Purpose:
    Map any life question onto the same PRE-AUDIT machinery: houses, karakas,
    vargas, SAV, Nadi combos, KP cusps, and a doctrine query for RAG books.
    Sources: BPHS bhava names (Tanu…Vyaya), KP CSL event houses, Nadi
    supporting vs denying sets, BNN karaka + 2/7/12 flow.

Inputs:
    Domain id (or a question classified in domain_harness).

Outputs:
    Aspect records used to build a harness plan (checkpoints, slices, RAG query).
"""

from __future__ import annotations

from typing import Any

# Engine slices every specialist needs. Domain filtering is houses/checkpoints.
PACKET_KEYS: tuple[str, ...] = (
    "natal_core",
    "unified_kundali",
    "special_yogas",
    "yoga_rule_matrix",
    "ashtakavarga_sav",
    "ashtakavarga_bav",
    "bnn_module",
    "cusps",
    "planet_star_sub_lords",
    "kp_prediction",
    "kp_astrology_matrix",
    "natal_drishti_table",
    "natal_house_drishti_summary",
)

SPECIALISTS = ("bphs", "varga_sav", "dasha_nadi", "kp", "bnn")

# BPHS Sanskrit bhava names (Brihat Parashara Hora Shastra, house chapters).
BHAVA_NAMES = {
    1: "Tanu (self/body)",
    2: "Dhana (wealth/speech/family)",
    3: "Sahaja (siblings/courage/skills)",
    4: "Sukha (home/mother/property)",
    5: "Putra (children/intellect/romance)",
    6: "Ripu (enemies/disease/debt/service)",
    7: "Kalatra (spouse/partnership)",
    8: "Ayur (longevity/obstacles/occult)",
    9: "Dharma (father/fortune/guru/dharma)",
    10: "Karma (profession/status)",
    11: "Labha (gains/friends/elders)",
    12: "Vyaya (loss/foreign/moksha/spend)",
}


def _h(n: int, label: str) -> dict[str, str]:
    return {"id": f"d1_h{n}", "system": "bphs", "label": label}


def _sav(n: int, label: str) -> dict[str, str]:
    return {"id": f"sav_h{n}", "system": "varga_sav", "label": label}


def _kp(n: int, label: str) -> dict[str, str]:
    return {"id": f"kp_csl_{n}", "system": "kp", "label": f"KP {n}th CSL — {label}"}


def _nadi(key: str, label: str, combo: list[int]) -> dict[str, Any]:
    return {"id": f"nadi_{key}", "system": "dasha_nadi", "label": label, "houses": list(combo)}


def _yoga(cid: str, label: str, needles: tuple[str, ...]) -> dict[str, Any]:
    return {"id": cid, "system": "bphs", "label": label, "needles": list(needles)}


def _varga(cid: str, label: str) -> dict[str, str]:
    return {"id": cid, "system": "varga_sav", "label": label}


def _bundle(
    *,
    houses: list[int],
    house_labels: dict[int, str],
    nadi: dict[str, list[int]],
    nadi_labels: dict[str, str],
    kp_cusps: list[int],
    kp_labels: dict[int, str] | None = None,
    vargas: list[dict[str, str]] | None = None,
    extra_bphs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Standard PRE-AUDIT checkpoint list for one life aspect."""
    rows: list[dict[str, Any]] = []
    for h in houses:
        rows.append(_h(h, house_labels.get(h, f"D1 {h}th — {BHAVA_NAMES[h]}")))
    rows.extend(extra_bphs or [])
    rows.append({"id": "bhava_shift", "system": "bphs", "label": "Bhava Chalit delivery vs whole-sign"})
    rows.extend(vargas or [])
    for h in houses:
        rows.append(_sav(h, f"SAV {h}th ({BHAVA_NAMES[h].split('(')[0].strip()} >28 / <=25)"))
    for key, combo in nadi.items():
        rows.append(_nadi(key, nadi_labels.get(key, f"Nadi {key} {combo}"), combo))
    rows.append({"id": "vimshottari", "system": "dasha_nadi", "label": "Vimshottari MD/AD house links"})
    for h in kp_cusps:
        rows.append(_kp(h, (kp_labels or {}).get(h, BHAVA_NAMES[h])))
    rows.append({"id": "bnn_karakas", "system": "bnn", "label": "BNN karaka flow (2nd/7th/12th from karaka)"})
    rows.append({"id": "bnn_direction", "system": "bnn", "label": "BNN directional groups"})
    return rows


def _aspect(
    *,
    title: str,
    houses: list[int],
    planets: list[str],
    nadi: dict[str, list[int]],
    kp_cusps: list[int],
    book_query: str,
    book_source: str,
    house_labels: dict[int, str],
    nadi_labels: dict[str, str],
    vargas: list[dict[str, str]] | None = None,
    extra_bphs: list[dict[str, Any]] | None = None,
    kp_labels: dict[int, str] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "keys": list(PACKET_KEYS),
        "specialists": list(SPECIALISTS),
        "houses": houses,
        "planets": planets,
        "nadi": nadi,
        "kp_cusps": kp_cusps,
        "book_query": book_query,
        "book_source": book_source,
        "checkpoints": _bundle(
            houses=houses,
            house_labels=house_labels,
            nadi=nadi,
            nadi_labels=nadi_labels,
            kp_cusps=kp_cusps,
            kp_labels=kp_labels,
            vargas=vargas,
            extra_bphs=extra_bphs,
        ),
    }


# Order is classification priority (first match wins as primary; all matches join).
ASPECTS: dict[str, dict[str, Any]] = {
    "finance": _aspect(
        title="FINANCIAL EVALUATION INVENTORY",
        houses=[1, 2, 9, 10, 11, 12, 6, 8],
        planets=["Jupiter", "Venus", "Mercury", "Moon", "Saturn", "Mars", "Rahu"],
        nadi={"inflow": [2, 6, 10, 11], "fortune": [5, 9, 11], "loss": [6, 8, 12]},
        kp_cusps=[2, 11],
        book_query="BPHS dhana bhava labha 2nd 11th house wealth ashtakavarga SAV dhana yoga",
        book_source="BPHS Dhana/Labha; KP 2nd+11th CSL; Nadi 2-6-10-11 inflow",
        house_labels={
            1: "D1 1st House (self as wealth vessel)",
            2: "D1 2nd House (Storage/Dhana)",
            9: "D1 9th House (Fortune/Lakshmi)",
            10: "D1 10th House (profession/earnings)",
            11: "D1 11th House (Income/Gains)",
            12: "D1 12th House (expense/drain)",
            6: "D1 6th House (debt/service)",
            8: "D1 8th House (sudden loss/inheritance)",
        },
        nadi_labels={
            "inflow": "Nadi inflow [2,6,10,11]",
            "fortune": "Nadi fortune [5,9,11]",
            "loss": "Nadi loss [6,8,12]",
        },
        vargas=[
            _varga("d2_hora", "D2 Hora (wealth treasury)"),
            _varga("d9_fortitude", "D9 Navamsa wealth fortitude"),
            _varga("d10_earnings", "D10 Dasamsha earnings cluster"),
        ],
        extra_bphs=[
            {"id": "d1_1_10_links", "system": "bphs", "label": "1st/10th lord wealth links"},
            _yoga("yogas_dhana", "Dhana / Parivartana / Vipareeta yogas", ("parivartana", "dhana", "raja", "harsha", "sarala", "vipareeta", "lakshmi")),
        ],
        kp_labels={2: "wealth/speech", 11: "gains"},
    ),
    "health": _aspect(
        title="HEALTH & VIABILITY INVENTORY",
        houses=[1, 6, 8, 12],
        planets=["Sun", "Moon", "Mars", "Saturn", "Rahu", "Ketu", "Jupiter"],
        nadi={"vitality": [1, 6], "crisis": [8, 12], "recovery": [5, 11]},
        kp_cusps=[1, 6, 8, 12],
        book_query="BPHS tanu ripu ayur vyaya 6th house disease ashtakavarga trimsamsa D30 hospitalization",
        book_source="BPHS Tanu/Ripu/Ayur; KP 1-6-8-12 CSL; D30 Trimsamsa",
        house_labels={
            1: "D1 1st House (vitality/constitution)",
            6: "D1 6th House (disease/service/recovery)",
            8: "D1 8th House (chronic/surgery/longevity)",
            12: "D1 12th House (hospitalization/drain)",
        },
        nadi_labels={
            "vitality": "Nadi vitality [1,6]",
            "crisis": "Nadi crisis [8,12]",
            "recovery": "Nadi recovery [5,11]",
        },
        vargas=[_varga("d30_trimsamsa", "D30 Trimsamsa (misfortune/ailment)")],
        extra_bphs=[
            _yoga("yogas_health", "Health yogas / afflictions", ("arogya", "vipareeta", "kemadruma", "papakartari", "guru", "chandra")),
        ],
        kp_labels={1: "body", 6: "disease", 8: "chronic", 12: "hospital"},
    ),
    "marriage": _aspect(
        title="MARRIAGE / PARTNERSHIP INVENTORY",
        houses=[1, 2, 5, 7, 8, 11, 12],
        planets=["Venus", "Jupiter", "Moon", "Mars", "Rahu", "Saturn"],
        nadi={"promise": [2, 7, 11], "denial": [1, 6, 10, 12]},
        kp_cusps=[7, 2, 11],
        book_query="BPHS kalatra bhava 7th house marriage navamsa D9 Venus Jupiter spouse KP 7th CSL",
        book_source="BPHS Kalatra; D9 Navamsa; KP 7th CSL; Nadi 2-7-11 vs 1-6-10-12",
        house_labels={
            1: "D1 1st House (self in union)",
            2: "D1 2nd House (family)",
            5: "D1 5th House (romance/poorva punya)",
            7: "D1 7th House (spouse)",
            8: "D1 8th House (in-laws/longevity of union)",
            11: "D1 11th House (fulfilment of marriage)",
            12: "D1 12th House (separation/bed comforts)",
        },
        nadi_labels={
            "promise": "Nadi promise [2,7,11]",
            "denial": "Nadi denial [1,6,10,12]",
        },
        vargas=[_varga("d9_dharma", "D9 Navamsa marriage fortitude")],
        extra_bphs=[_yoga("yogas_marriage", "Kalatra / Manglik / Darakaraka yogas", ("kalatra", "mangal", "daraka", "parivartana", "gaja", "venus"))],
        kp_labels={7: "spouse", 2: "family", 11: "fulfilment"},
    ),
    "career": _aspect(
        title="CAREER & PROFESSION INVENTORY",
        houses=[1, 2, 6, 10, 11],
        planets=["Sun", "Saturn", "Mercury", "Jupiter", "Mars"],
        nadi={"rise": [2, 6, 10, 11], "obstruction": [8, 12]},
        kp_cusps=[10, 6, 11],
        book_query="BPHS karma bhava 10th house profession dasamsa D10 Sun Saturn KP 10th CSL service 6th",
        book_source="BPHS Karma; D10 Dasamsha; KP 10-6-11 CSL",
        house_labels={
            1: "D1 1st House (self in karma)",
            2: "D1 2nd House (speech/resources at work)",
            6: "D1 6th House (service/competition)",
            10: "D1 10th House (profession)",
            11: "D1 11th House (gains from career)",
        },
        nadi_labels={"rise": "Nadi rise [2,6,10,11]", "obstruction": "Nadi obstruction [8,12]"},
        vargas=[_varga("d10_dasamsha", "D10 Dasamsha")],
        extra_bphs=[_yoga("yogas_career", "Raja / Dharma-karmadhipati yogas", ("raja", "dharma", "karma", "sunapha", "akhanda"))],
        kp_labels={10: "profession", 6: "service", 11: "gains"},
    ),
    "children": _aspect(
        title="PROGENY INVENTORY",
        houses=[5, 9, 11],
        planets=["Jupiter", "Moon", "Mercury"],
        nadi={"promise": [2, 5, 11], "denial": [1, 4, 10]},
        kp_cusps=[5, 11],
        book_query="BPHS putra bhava 5th house children saptamsa D7 Jupiter santana KP 5th CSL",
        book_source="BPHS Putra; D7 Saptamsa; KP 5th CSL; Nadi 2-5-11",
        house_labels={
            5: "D1 5th House (children/intellect)",
            9: "D1 9th House (dharma/grandchildren)",
            11: "D1 11th House (fulfilment of progeny)",
        },
        nadi_labels={"promise": "Nadi promise [2,5,11]", "denial": "Nadi denial [1,4,10]"},
        vargas=[_varga("d7_saptamsa", "D7 Saptamsa (progeny)")],
        extra_bphs=[_yoga("yogas_children", "Santana / putra yogas", ("putra", "santana", "jupiter", "gaja"))],
        kp_labels={5: "children", 11: "fulfilment"},
    ),
    "education": _aspect(
        title="EDUCATION INVENTORY",
        houses=[4, 5, 9],
        planets=["Mercury", "Jupiter", "Moon"],
        nadi={"success": [4, 5, 9, 11], "obstruction": [6, 8, 12]},
        kp_cusps=[4, 5, 9],
        book_query="BPHS vidya 4th 5th 9th house education mercury jupiter navamsa budha KP 4th 5th 9th",
        book_source="BPHS Sukha/Putra/Dharma (vidya); KP 4-5-9 CSL",
        house_labels={
            4: "D1 4th House (foundational learning)",
            5: "D1 5th House (intellect/exams)",
            9: "D1 9th House (higher education/guru)",
        },
        nadi_labels={"success": "Nadi success [4,5,9,11]", "obstruction": "Nadi obstruction [6,8,12]"},
        vargas=[_varga("d9_dharma", "D9 Navamsa (higher learning fortitude)")],
        extra_bphs=[_yoga("yogas_education", "Budha-Aditya / Saraswati yogas", ("budha", "saraswati", "mercury", "jupiter"))],
        kp_labels={4: "learning", 5: "intellect", 9: "higher studies"},
    ),
    "foreign": _aspect(
        title="FOREIGN / RELOCATION INVENTORY",
        houses=[3, 9, 12],
        planets=["Rahu", "Ketu", "Saturn", "Moon"],
        nadi={"travel": [3, 9, 12], "settlement": [4, 7, 12]},
        kp_cusps=[3, 9, 12],
        book_query="BPHS vyaya 12th house foreign settlement rahu 9th long travel KP 12th CSL visa abroad",
        book_source="BPHS Vyaya/Dharma/Sahaja; KP 3-9-12 CSL; Rahu karaka",
        house_labels={
            3: "D1 3rd House (short travel/initiative)",
            9: "D1 9th House (long travel/dharma abroad)",
            12: "D1 12th House (foreign residence/loss of homeland)",
        },
        nadi_labels={"travel": "Nadi travel [3,9,12]", "settlement": "Nadi settlement [4,7,12]"},
        vargas=[_varga("d12_dwadasamsa", "D12 Dwadasamsa (exit/lineage)")],
        extra_bphs=[_yoga("yogas_foreign", "Pravasa / Rahu-12 yogas", ("pravasa", "rahu", "ketu", "12"))],
        kp_labels={3: "movement", 9: "long travel", 12: "foreign"},
    ),
    "siblings": _aspect(
        title="SIBLINGS / COURAGE / SKILLS INVENTORY",
        houses=[3, 11],
        planets=["Mars", "Mercury", "Jupiter"],
        nadi={"support": [3, 11], "strife": [6, 8, 12]},
        kp_cusps=[3, 11],
        book_query="BPHS sahaja 3rd house siblings courage mars parakrama KP 3rd CSL younger brother",
        book_source="BPHS Sahaja; KP 3rd CSL; Mars karaka",
        house_labels={
            3: "D1 3rd House (siblings/courage/skills)",
            11: "D1 11th House (elder siblings/allies)",
        },
        nadi_labels={"support": "Nadi support [3,11]", "strife": "Nadi strife [6,8,12]"},
        extra_bphs=[_yoga("yogas_siblings", "Parakrama / bhratru yogas", ("bhratru", "parakrama", "mars", "sahaja"))],
        kp_labels={3: "siblings", 11: "elders"},
    ),
    "home": _aspect(
        title="HOME / MOTHER / PROPERTY / VEHICLES INVENTORY",
        houses=[4, 12],
        planets=["Moon", "Venus", "Mars", "Ketu"],
        nadi={"comfort": [4, 11], "displacement": [8, 12]},
        kp_cusps=[4, 12],
        book_query="BPHS sukha 4th house mother property vehicle chaturthamsa D4 moon KP 4th CSL real estate",
        book_source="BPHS Sukha; D4 Chaturthamsa; KP 4th CSL; Moon/Venus karakas",
        house_labels={
            4: "D1 4th House (home/mother/property/vehicles)",
            12: "D1 12th House (away from home/loss of property)",
        },
        nadi_labels={"comfort": "Nadi comfort [4,11]", "displacement": "Nadi displacement [8,12]"},
        vargas=[_varga("d4_chaturthamsa", "D4 Chaturthamsa (property/vehicles)")],
        extra_bphs=[_yoga("yogas_home", "Bandhu / griha yogas", ("bandhu", "griha", "moon", "ketu", "property"))],
        kp_labels={4: "home/property", 12: "away from home"},
    ),
    "litigation": _aspect(
        title="ENEMIES / DEBT / COURT / SERVICE INVENTORY",
        houses=[6, 8, 12],
        planets=["Mars", "Saturn", "Rahu", "Mercury"],
        nadi={"conflict": [6, 8], "relief": [5, 11]},
        kp_cusps=[6, 8, 12],
        book_query="BPHS ripu 6th house enemies debt litigation court case mars saturn KP 6th CSL",
        book_source="BPHS Ripu; KP 6-8-12 CSL; Mars/Saturn karakas",
        house_labels={
            6: "D1 6th House (enemies/debt/court/service)",
            8: "D1 8th House (hidden opposition/delays)",
            12: "D1 12th House (loss/confinement)",
        },
        nadi_labels={"conflict": "Nadi conflict [6,8]", "relief": "Nadi relief [5,11]"},
        extra_bphs=[_yoga("yogas_litigation", "Ripu / Harsha-Sarala (6-8-12) yogas", ("ripu", "harsha", "sarala", "vimala", "mars"))],
        kp_labels={6: "enemies/court", 8: "hidden trouble", 12: "loss"},
    ),
    "longevity": _aspect(
        title="LONGEVITY / INHERITANCE / OCCULT INVENTORY",
        houses=[1, 3, 8],
        planets=["Saturn", "Ketu", "Mars", "Jupiter"],
        nadi={"span": [1, 8], "crisis": [6, 8, 12]},
        kp_cusps=[1, 8, 3],
        book_query="BPHS ayur 8th house longevity inheritance occult saturn ketu KP 8th CSL maraka",
        book_source="BPHS Ayur; KP 8th CSL; Saturn/Ketu; maraka 2nd/7th noted via BNN",
        house_labels={
            1: "D1 1st House (life force)",
            3: "D1 3rd House (vitality/initiative — 8th from 8th)",
            8: "D1 8th House (longevity/inheritance/occult)",
        },
        nadi_labels={"span": "Nadi span [1,8]", "crisis": "Nadi crisis [6,8,12]"},
        vargas=[_varga("d30_trimsamsa", "D30 Trimsamsa (misfortune/ailment)")],
        extra_bphs=[_yoga("yogas_longevity", "Ayur / maraka yogas", ("ayur", "maraka", "kemadruma", "saturn"))],
        kp_labels={1: "life", 8: "longevity", 3: "vitality"},
    ),
    "dharma": _aspect(
        title="FATHER / GURU / FORTUNE INVENTORY",
        houses=[9, 5, 1],
        planets=["Jupiter", "Sun", "Moon"],
        nadi={"fortune": [5, 9, 11], "obstruction": [6, 8, 12]},
        kp_cusps=[9, 5],
        book_query="BPHS dharma 9th house father guru fortune pitri bhagya jupiter sun KP 9th CSL",
        book_source="BPHS Dharma; KP 9th CSL; Jupiter/Sun karakas",
        house_labels={
            9: "D1 9th House (father/guru/fortune/dharma)",
            5: "D1 5th House (poorva punya)",
            1: "D1 1st House (self as dharmic actor)",
        },
        nadi_labels={"fortune": "Nadi fortune [5,9,11]", "obstruction": "Nadi obstruction [6,8,12]"},
        vargas=[_varga("d9_dharma", "D9 Navamsa (dharma fortitude)")],
        extra_bphs=[_yoga("yogas_dharma", "Bhagya / Dharma-karmadhipati yogas", ("bhagya", "dharma", "guru", "pitri"))],
        kp_labels={9: "father/fortune", 5: "poorva punya"},
    ),
    "gains": _aspect(
        title="GAINS / FRIENDS / ELDERS INVENTORY",
        houses=[11, 2],
        planets=["Jupiter", "Venus", "Mercury"],
        nadi={"inflow": [2, 6, 10, 11], "block": [8, 12]},
        kp_cusps=[11, 2],
        book_query="BPHS labha 11th house gains friends elder siblings ashtakavarga SAV KP 11th CSL",
        book_source="BPHS Labha; KP 11th CSL; Nadi 2-6-10-11",
        house_labels={
            11: "D1 11th House (gains/friends/elders)",
            2: "D1 2nd House (accumulated wealth)",
        },
        nadi_labels={"inflow": "Nadi inflow [2,6,10,11]", "block": "Nadi block [8,12]"},
        extra_bphs=[_yoga("yogas_gains", "Labha yogas", ("labha", "raja", "dhana"))],
        kp_labels={11: "gains", 2: "storage"},
    ),
    "spirituality": _aspect(
        title="DHARMA / MOKSHA / SPIRITUALITY INVENTORY",
        houses=[5, 9, 12],
        planets=["Jupiter", "Ketu", "Saturn", "Moon"],
        nadi={"uplift": [5, 9], "withdrawal": [12, 8]},
        kp_cusps=[9, 12, 5],
        book_query="BPHS moksha 12th 9th 5th house ketu jupiter dharma sadhana ashram KP 12th 9th CSL",
        book_source="BPHS Dharma/Vyaya/Putra; Ketu moksha karaka; KP 9-12 CSL",
        house_labels={
            5: "D1 5th House (mantra/poorva punya)",
            9: "D1 9th House (dharma/guru)",
            12: "D1 12th House (moksha/ashram/loss of ego)",
        },
        nadi_labels={"uplift": "Nadi uplift [5,9]", "withdrawal": "Nadi withdrawal [12,8]"},
        vargas=[_varga("d12_dwadasamsa", "D12 Dwadasamsa (exit/moksha shade)")],
        extra_bphs=[_yoga("yogas_spiritual", "Pravrajya / Ketu-12 yogas", ("pravrajya", "ketu", "moksha", "sanyasa"))],
        kp_labels={9: "dharma", 12: "moksha", 5: "mantra"},
    ),
    "self": _aspect(
        title="SELF / TANU / CHARACTER INVENTORY",
        houses=[1, 5, 9],
        planets=["Sun", "Moon", "Lagna", "Jupiter"],
        nadi={"vitality": [1, 5], "drain": [6, 8, 12]},
        kp_cusps=[1, 5],
        book_query="BPHS tanu lagna 1st house self character appearance sun moon ascendant KP 1st CSL",
        book_source="BPHS Tanu; Lagna/Sun/Moon; KP 1st CSL",
        house_labels={
            1: "D1 1st House (self/body/character)",
            5: "D1 5th House (intelligence/creativity)",
            9: "D1 9th House (dharma/worldview)",
        },
        nadi_labels={"vitality": "Nadi vitality [1,5]", "drain": "Nadi drain [6,8,12]"},
        extra_bphs=[_yoga("yogas_self", "Lagna / Mahapurusha yogas", ("lagna", "mahapurusha", "pancha", "sunapha", "anapha"))],
        kp_labels={1: "self", 5: "intellect"},
    ),
    "general": _aspect(
        title="GENERAL LIFE SURVEY INVENTORY",
        houses=[1, 2, 4, 5, 7, 10, 11],
        planets=["Sun", "Moon", "Jupiter", "Venus", "Saturn", "Mars", "Mercury"],
        nadi={"support": [1, 5, 9, 11], "stress": [6, 8, 12]},
        kp_cusps=[1, 7, 10, 11],
        book_query="BPHS lagna tanu kalatra karma labha general horoscope reading twelve bhavas ashtakavarga",
        book_source="BPHS 12 bhavas survey; KP 1-7-10-11; SAV of key houses",
        house_labels={
            1: "D1 1st House (self)",
            2: "D1 2nd House (wealth/speech)",
            4: "D1 4th House (home/happiness)",
            5: "D1 5th House (intellect/children)",
            7: "D1 7th House (partnership)",
            10: "D1 10th House (career)",
            11: "D1 11th House (gains)",
        },
        nadi_labels={"support": "Nadi support [1,5,9,11]", "stress": "Nadi stress [6,8,12]"},
        extra_bphs=[_yoga("yogas_general", "Raja / Dhana / notable yogas", ("raja", "dhana", "parivartana", "gaja", "kemadruma"))],
        kp_labels={1: "self", 7: "others", 10: "karma", 11: "gains"},
    ),
}

# Keyword router: first listed pattern that hits contributes that domain (joins allowed).
# More specific aspects before generic finance/self/general.
DOMAIN_PATTERNS: list[tuple[str, str]] = [
    (r"marri|spouse|wife|husband|wedding|partner(?:ship)?|love\s*life|kalatra|7th", "marriage"),
    (r"career|job|profess|10th|boss|promot|employ|business|occupation|status\s*at\s*work", "career"),
    (
        r"health|diseas|illness|hospital|surgery|vitalit|immun|chronic|"
        r"ailment|medic|body|recovery|longevity\s*of\s*(?:health|body)|6th\s*house",
        "health",
    ),
    (r"child|putra|pregnan|offspring|santana|progeny|5th\s*house", "children"),
    (r"educat|study|exam|college|degree|learning|vidya|school", "education"),
    (r"foreign|abroad|visa|immigration|relocat|settle\s*overseas|pravasa|12th\s*house", "foreign"),
    (r"sibling|brother|sister|courage|parakrama|bhratru|3rd\s*house", "siblings"),
    (
        r"mother|property|real\s*estate|home|vehicle|car|conveyance|land|4th\s*house|sukha|"
        r"(?:buy|purchase|own)\s+(?:a\s+)?(?:house|home|flat|apartment)|"
        r"house\s*(?:buy|purchase|own)",
        "home",
    ),
    (r"enem(?:y|ies)|litigat|court|lawsuit|debt|ripu|conflict|opposition", "litigation"),
    (r"longevity|inherit|occult|last\s+will|testament|maraka|8th\s*house|ayur", "longevity"),
    (r"father|guru|bhagya|fortune|luck|pitri|9th\s*house|dharma(?!\s*/)", "dharma"),
    (r"friend|elder\s*sibling|labha|fulfil|11th\s*house", "gains"),
    (r"spirit|moksha|sanyas|meditation|ashram|sadhana|pravrajya|ketu.*12", "spirituality"),
    (r"personality|character|appearance|who\s+am\s+i|tanu|lagna\s*nature|self[- ]image", "self"),
    (
        r"financ|money|wealth|income|salary|invest|asset|bank|saving|earn|"
        r"dhan|cash|profit|gain|2nd\s*house",
        "finance",
    ),
]


def list_aspects() -> list[dict[str, Any]]:
    """Public catalog for API / docs: id, title, houses, book source."""
    out = []
    for did, rec in ASPECTS.items():
        out.append(
            {
                "id": did,
                "title": rec["title"],
                "houses": rec["houses"],
                "kp_cusps": rec["kp_cusps"],
                "book_source": rec["book_source"],
                "book_query": rec["book_query"],
                "nadi": rec["nadi"],
            }
        )
    return out
