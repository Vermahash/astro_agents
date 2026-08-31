"""Tests for domain harness, specialists, critic, RAG, chart query, Brain packet."""

from __future__ import annotations

from shared.chart_query import run_chart_query
from shared.critic import critique_answer
from shared.domain_harness import build_harness_plan, classify_domain, classify_domains
from shared.harness_pipeline import build_brain_user_message, format_inventory_box
from shared.prompts import load_system_prompt
from shared.specialists import compact_facts, flatten_checkpoints, run_specialists, tally_status
from tests.fixtures_packet import finance_shaped_payload


def test_finance_and_health_domains():
    assert classify_domain("Tell me about his finances") == "finance"
    assert classify_domain("How is his health and vitality?") == "health"
    both = classify_domains("Tell me about health and finances")
    assert "finance" in both and "health" in both


def test_finance_plan_includes_sav_and_bnn():
    plan = build_harness_plan("How is my wealth and income?")
    assert plan["inventory_title"] == "FINANCIAL EVALUATION INVENTORY"
    assert "ashtakavarga_sav" in plan["keys"]
    assert "bnn_module" in plan["keys"]
    assert plan["nadi_combos"]["inflow"] == [2, 6, 10, 11]
    assert 2 in plan["kp_cusps"] and 11 in plan["kp_cusps"]
    assert "bphs" in plan["specialists"]


def test_health_plan_cusps():
    plan = build_harness_plan("Is there illness or hospitalization indicated?")
    assert plan["domain"] == "health"
    assert 6 in plan["kp_cusps"] and 8 in plan["kp_cusps"]
    assert "d30_trimsamsa" in {c["id"] for c in plan["checkpoints"]}


def test_specialists_finance_sav_and_parivartana():
    slices = finance_shaped_payload()
    plan = build_harness_plan("Tell me about his finances", set(slices))
    facts = compact_facts(slices, plan)
    assert facts["lagna"]["sign"] == "Virgo"
    assert facts["planets"]["Mercury"]["house"] == 2
    assert facts["planets"]["Moon"]["dignity"] == "exalted"
    assert facts["sav"]["11"] == 40
    reports = run_specialists(facts, plan)
    rows = flatten_checkpoints(reports)
    by_id = {r["id"]: r for r in rows}
    assert by_id["sav_h11"]["status"] == "SUPPORTS"
    assert by_id["sav_h2"]["status"] == "RESISTS"
    assert by_id["sav_h8"]["status"] == "RESISTS" if "sav_h8" in by_id else True
    assert by_id["yogas_dhana"]["status"] == "SUPPORTS"
    assert tally_status(rows)["SUPPORTS"] >= 1


def test_health_specialists_mark_12th_malefics():
    slices = finance_shaped_payload()
    plan = build_harness_plan("How is his health?", set(slices))
    facts = compact_facts(slices, plan)
    rows = flatten_checkpoints(run_specialists(facts, plan))
    h12 = next(r for r in rows if r["id"] == "d1_h12")
    assert h12["status"] in ("RESISTS", "MIXED")
    sav8 = next(r for r in rows if r["id"] == "sav_h8")
    assert sav8["status"] == "RESISTS"


def test_critic_flags_invented_degree():
    slices = finance_shaped_payload()
    plan = build_harness_plan("finances", set(slices))
    facts = compact_facts(slices, plan)
    bad = "Mercury sits at 19.99° in Libra with 99 SAV in the 11th house."
    out = critique_answer(bad, facts)
    assert out["ok"] is False
    kinds = {i["kind"] for i in out["issues"]}
    assert "degree_mismatch" in kinds or "sav_mismatch" in kinds


def test_critic_accepts_packet_degree():
    slices = finance_shaped_payload()
    plan = build_harness_plan("finances", set(slices))
    facts = compact_facts(slices, plan)
    good = "Mercury at 2.53° Libra. 11th house 40 SAV."
    out = critique_answer(good, facts)
    assert out["ok"] is True


def test_chart_query_sav_and_varga():
    slices = finance_shaped_payload()
    sav = run_chart_query(op="sav", slices=slices, house=11)
    assert sav["ok"] is True
    assert sav["result"]["sav"] == 40
    assert sav["result"]["status"] == "SUPPORTS"
    v = run_chart_query(op="varga", slices=slices, planet="Moon", division=9)
    assert v["ok"] is True
    assert v["result"]["sign"] in (
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
    )


def test_brain_message_contains_inventory_and_facts():
    slices = finance_shaped_payload()
    plan = build_harness_plan("Tell me about his finances", set(slices))
    facts = compact_facts(slices, plan)
    rows = flatten_checkpoints(run_specialists(facts, plan))
    box = format_inventory_box(plan)
    assert "FINANCIAL" in box
    msg = build_brain_user_message(
        question="Tell me about his finances",
        plan=plan,
        facts=facts,
        audit_rows=rows,
        rag_hits=[],
        law_hits=[],
        meta={"name": "Harsh", "lagna": "Virgo"},
    )
    assert "python_facts" in msg
    assert "specialist_audit" in msg
    assert "USER QUESTION" in msg


def test_collect_harness_evidence_no_llm():
    from shared.harness_pipeline import collect_harness_evidence

    doc = {"meta": {"name": "Harsh", "lagna": "Virgo"}, "structured_payload": finance_shaped_payload()}
    ev = collect_harness_evidence("Tell me about his finances", doc, use_rag=False)
    assert ev["plan"]["domain"] == "finance"
    assert ev["tally"]["SUPPORTS"] >= 1
    assert "FINANCIAL" in ev["inventory_box"]
    health = collect_harness_evidence("How is his health?", doc, use_rag=False)
    assert health["plan"]["domain"] == "health"
    assert any(r["id"] == "d1_h6" for r in health["audit_rows"])


def test_rag_index_and_search(tmp_path, monkeypatch):
    from shared import rag_hnsw

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    books = tmp_path / "books"
    books.mkdir()
    (books / "dhana.txt").write_text(
        "The 11th house shows gains. Ashtakavarga SAV above 28 is strong for wealth. "
        "The 2nd house retains dhana. BPHS describes dhana yoga via lords of 2 and 11.",
        encoding="utf-8",
    )
    monkeypatch.setattr(rag_hnsw, "RAG_DIR", rag_dir)
    monkeypatch.setattr(rag_hnsw, "RAG_DB", rag_dir / "chunks.db")
    monkeypatch.setattr(rag_hnsw, "INDEX_BIN", rag_dir / "hnsw.bin")
    monkeypatch.setattr(rag_hnsw, "IDS_JSON", rag_dir / "ids.json")
    monkeypatch.setattr(rag_hnsw, "META_JSON", rag_dir / "meta.json")
    meta = rag_hnsw.build_index(roots=[books])
    assert meta["chunks"] >= 1
    hits = rag_hnsw.search_books("11th house gains ashtakavarga wealth", k=3)
    assert hits["ok"] is True
    assert hits["hits"]


def test_harness_pipeline_mocked_llm(monkeypatch):
    from shared.harness_pipeline import run_harness
    from shared.pipeline_trace import PipelineTrace

    slices = finance_shaped_payload()
    doc = {"chart_key": "x" * 40, "meta": {"name": "Harsh", "lagna": "Virgo"}, "structured_payload": slices}

    def fake_chat(**kwargs):
        return {
            "content": "Verdict: YES. Mercury at 2.53° in the 2nd. 11th house 40 SAV. SUPPORTS.",
            "model": "mock",
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }

    monkeypatch.setattr("shared.harness_pipeline.chat_completion", fake_chat)
    monkeypatch.setattr("shared.harness_pipeline.record_usage", lambda **k: 0.0)
    monkeypatch.setattr("shared.harness_pipeline.search_books", lambda *a, **k: {"ok": True, "hits": []})
    tr = PipelineTrace(trace_id="t1", kind="ask")
    out = run_harness(
        chart_key=doc["chart_key"],
        question="Tell me about his finances",
        doc=doc,
        tr=tr,
        model="deepseek-ai/deepseek-v4-flash-0731",
        max_tokens=500,
        prompt_profile="pre_audit",
        use_rag=False,
        use_web_law=False,
    )
    assert out["mode"] == "harness"
    assert out["harness_plan"]["domain"] == "finance"
    assert out["critic"]["ok"] is True
    assert "40 SAV" in out["answer"]
