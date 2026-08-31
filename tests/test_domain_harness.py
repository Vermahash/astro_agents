"""Tests for domain harness routing."""

from shared.domain_harness import build_harness_plan, classify_domain


def test_finance_question():
    assert classify_domain("Tell me about his finances") == "finance"
    plan = build_harness_plan("How is my wealth and income?")
    assert plan["inventory_title"] == "FINANCIAL EVALUATION INVENTORY"
    assert "ashtakavarga_sav" in plan["keys"]
    assert "bnn_module" in plan["keys"]
    assert plan["nadi_combos"]["inflow"] == [2, 6, 10, 11]
    assert 2 in plan["kp_cusps"] and 11 in plan["kp_cusps"]


def test_marriage_question():
    assert classify_domain("Is marriage promised?") == "marriage"
    plan = build_harness_plan("Is marriage promised?")
    assert 7 in plan["kp_cusps"]


def test_home_and_siblings_from_bphs_bhavas():
    assert classify_domain("Will I buy a vehicle?") == "home"
    home = build_harness_plan("mother and property")
    assert 4 in home["houses"]
    assert home["book_queries"]
    assert classify_domain("younger brother") == "siblings"
