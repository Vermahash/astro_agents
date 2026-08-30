"""Tests for question → packet key planning."""

from shared.packet_planner import plan_packet_keys


def test_marriage_question_selects_extra_keys():
    available = {
        "natal_core": {},
        "cusps": {},
        "planet_star_sub_lords": {},
        "kp_astrology_matrix": {},
        "kp_master_packet": {},
        "kp_prediction": {},
        "special_yogas": {},
        "natal_drishti_table": {},
        "natal_house_drishti_summary": {},
    }
    plan = plan_packet_keys("Is marriage promised?", available)
    assert "kp_prediction" in plan["keys"]
    assert "special_yogas" in plan["keys"]
    assert any("marriage" in t for t in plan["matched_topics"])


def test_general_question_still_gets_core():
    available = {"natal_core": {}, "cusps": {}, "planet_star_sub_lords": {}}
    plan = plan_packet_keys("Tell me about this chart", available)
    assert "natal_core" in plan["keys"]
    assert "cusps" in plan["keys"]
