"""
PRE-AUDIT harness pipeline: route → slice → specialists → RAG → Brain → critic.

Purpose:
    For domain questions (finance, health, …) send only Python-computed compact
    facts to the Brain LLM. Specialists are deterministic extractors; optional
    RAG/law search is doctrine-only.

Inputs:
    Cached chart document, user question, model, prompt profile.

Outputs:
    Answer + harness_plan + specialist_audit + rag_hits + critic + usage.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.critic import critique_answer
from shared.domain_harness import build_harness_plan
from shared.llm_nvidia import chat_completion
from shared.pipeline_trace import PipelineTrace, step
from shared.prompts import load_system_prompt
from shared.rag_hnsw import search_books
from shared.specialists import compact_facts, flatten_checkpoints, run_specialists, tally_status
from shared.usage import record_usage
from shared.web_law import search_classical_law

logger = logging.getLogger(__name__)

MAX_BRAIN_CHARS = 18_000
MAX_RAG_SNIPPETS = 4
MAX_LAW_HITS = 2


def collect_harness_evidence(question: str, doc: dict[str, Any], *, use_rag: bool = False) -> dict[str, Any]:
    """
    Run router + slices + specialists (no LLM).

    Returns:
        plan, facts, audit_rows, tally, rag_hits
    """
    structured = doc.get("structured_payload") or {}
    available = set(structured.keys()) if isinstance(structured, dict) else set()
    plan = build_harness_plan(question, available)
    slices = _condense_slices(structured, plan["keys"])
    facts = compact_facts(slices, plan)
    reports = run_specialists(facts, plan)
    audit_rows = flatten_checkpoints(reports)
    rag_hits: list[dict[str, Any]] = []
    if use_rag:
        try:
            rag_hits = (search_books(question, k=MAX_RAG_SNIPPETS).get("hits") or [])
        except Exception as exc:
            logger.info("rag skipped: %s", exc)
    return {
        "plan": plan,
        "facts": facts,
        "audit_rows": audit_rows,
        "tally": tally_status(audit_rows),
        "rag_hits": rag_hits,
        "inventory_box": format_inventory_box(plan),
    }


def _condense_slices(structured: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in keys:
        if k in structured:
            out[k] = structured[k]
    matrix = out.get("kp_astrology_matrix")
    if isinstance(matrix, dict):
        keep = {
            kk: vv
            for kk, vv in matrix.items()
            if kk
            in (
                "moon_dasha_balance_at_birth",
                "ayanamsa_used",
                "planet_significations",
                "house_significators",
                "ruling_planets",
            )
            or not (isinstance(vv, str) and len(vv) > 2000)
        }
        # drop huge table strings
        slim = {}
        for kk, vv in keep.items():
            if isinstance(vv, str) and len(vv) > 2500:
                continue
            slim[kk] = vv
        out["kp_astrology_matrix"] = slim
    return out


def format_inventory_box(plan: dict[str, Any]) -> str:
    """ASCII 3-column inventory matching the finance-style user example."""
    title = plan.get("inventory_title") or "DOMAIN INVENTORY"
    bphs = [c["label"] for c in plan.get("checkpoints") or [] if c.get("system") == "bphs"]
    varga = [c["label"] for c in plan.get("checkpoints") or [] if c.get("system") == "varga_sav"]
    rest = [c["label"] for c in plan.get("checkpoints") or [] if c.get("system") in ("dasha_nadi", "kp", "bnn")]
    def col(items: list[str]) -> str:
        return "\n".join(f" • {x}" for x in items) or " • (none)"
    return (
        f"{title}\n"
        f"{'BPHS / PARASHARI':<28}{'SHODASHAVARGA / SAV':<32}DASHA, NADI, KP & BNN\n"
        f"{col(bphs)}\n---\n{col(varga)}\n---\n{col(rest)}\n"
    )


def build_brain_user_message(
    *,
    question: str,
    plan: dict[str, Any],
    facts: dict[str, Any],
    audit_rows: list[dict[str, Any]],
    rag_hits: list[dict[str, Any]],
    law_hits: list[dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    """Assemble the only payload the Brain LLM is allowed to see."""
    slim_facts = {
        "lagna": facts.get("lagna"),
        "planets": facts.get("planets"),
        "houses": facts.get("houses"),
        "sav": facts.get("sav"),
        "yogas": facts.get("yogas"),
        "exchanges": facts.get("exchanges"),
        "cusps": facts.get("cusps"),
        "dasha": facts.get("dasha"),
        "vargas": facts.get("vargas"),
        "bnn": facts.get("bnn"),
        "planet_star_sub_lords": facts.get("planet_star_sub_lords"),
    }
    audit = [
        {
            "id": r.get("id"),
            "specialist": r.get("specialist"),
            "label": r.get("label"),
            "status": r.get("status"),
            "cite": r.get("cite"),
        }
        for r in audit_rows
    ]
    rag_block = [
        {"source": h.get("source"), "topic": h.get("topic"), "text": (h.get("text") or "")[:700]}
        for h in rag_hits[:MAX_RAG_SNIPPETS]
    ]
    law_block = [
        {"title": h.get("title"), "snippet": h.get("snippet"), "url": h.get("url")}
        for h in law_hits[:MAX_LAW_HITS]
    ]
    body = {
        "chart_meta": {"name": meta.get("name"), "lagna": meta.get("lagna"), "moon_nakshatra": meta.get("moon_nakshatra")},
        "plan": {
            "domains": plan.get("domains"),
            "inventory_title": plan.get("inventory_title"),
            "nadi_combos": plan.get("nadi_combos"),
            "kp_cusps": plan.get("kp_cusps"),
            "houses": plan.get("houses"),
        },
        "inventory_box": format_inventory_box(plan),
        "python_facts": slim_facts,
        "specialist_audit": audit,
        "status_tally": tally_status(audit_rows),
        "rag_doctrine": rag_block,
        "classical_law_web": law_block,
    }
    packet = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    if len(packet) > MAX_BRAIN_CHARS:
        packet = packet[:MAX_BRAIN_CHARS] + "…[truncated]"
    return (
        "HARNESS PACKET (authoritative Python facts + specialist audit). "
        "Do not recalculate longitudes, SAV, or dasha.\n\n"
        f"{packet}\n\n"
        "USER QUESTION:\n"
        f"{question.strip()}\n\n"
        "Follow the PRE-AUDIT directive: inventory box → evidence audit table "
        "(SUPPORTS/RESISTS/MIXED/NOT ACTIVATED/NOT IN PACKET) → verdict from the audit tally. "
        "Cite degrees/houses/SAV only from python_facts. RAG/web is doctrine, not numbers. "
        "If a checkpoint is NOT IN PACKET, say so. End with System Limits (not financial/medical advice)."
    )


def run_harness(
    *,
    chart_key: str,
    question: str,
    doc: dict[str, Any],
    tr: PipelineTrace,
    model: str | None,
    max_tokens: int,
    prompt_profile: str = "pre_audit",
    use_rag: bool = True,
    use_web_law: bool = False,
) -> dict[str, Any]:
    """
    Full PRE-AUDIT path. One Brain LLM call after Python specialists.

    Returns:
        Ask-service shaped dict plus harness fields.
    """
    structured = doc.get("structured_payload") or {}
    meta = doc.get("meta") or {}
    available = set(structured.keys()) if isinstance(structured, dict) else set()

    with step(tr, "domain_router"):
        plan = build_harness_plan(question, available)
        tr.mark(
            "harness_plan",
            detail={
                "domains": ",".join(plan["domains"]),
                "keys": ",".join(plan["keys"][:16]),
                "specialists": ",".join(plan["specialists"]),
            },
        )

    with step(tr, "fetch_slices", key_count=len(plan["keys"])):
        slices = _condense_slices(structured, plan["keys"])
        facts = compact_facts(slices, plan)
        tr.mark("compact_facts", detail={"planets": len(facts.get("planets") or {}), "houses": len(facts.get("houses") or {})})

    with step(tr, "specialists"):
        reports = run_specialists(facts, plan)
        audit_rows = flatten_checkpoints(reports)
        tallies = tally_status(audit_rows)
        tr.mark("specialist_tally", detail=tallies)

    rag_hits: list[dict[str, Any]] = []
    if use_rag:
        with step(tr, "rag_search"):
            try:
                rag = search_books(question, k=MAX_RAG_SNIPPETS)
                rag_hits = rag.get("hits") or []
                tr.mark("rag", detail={"ok": rag.get("ok"), "backend": rag.get("backend"), "hits": len(rag_hits)})
            except Exception as exc:
                logger.info("rag skipped: %s", exc)
                tr.mark("rag_error", detail={"error": str(exc)[:200]})

    law_hits: list[dict[str, Any]] = []
    if use_web_law:
        with step(tr, "web_law"):
            try:
                law = search_classical_law(question, limit=MAX_LAW_HITS)
                law_hits = law.get("hits") or []
                tr.mark("web_law", detail={"ok": law.get("ok"), "hits": len(law_hits)})
            except Exception as exc:
                logger.info("web_law skipped: %s", exc)

    with step(tr, "load_brain_prompt"):
        system = load_system_prompt(prompt_profile if prompt_profile in ("pre_audit", "default") else "pre_audit")
        user = build_brain_user_message(
            question=question,
            plan=plan,
            facts=facts,
            audit_rows=audit_rows,
            rag_hits=rag_hits,
            law_hits=law_hits,
            meta=meta,
        )

    with step(tr, "brain_synthesize", model=str(model or "default")[:24]):
        result = chat_completion(system=system, user=user, max_tokens=max_tokens, model=model, temperature=0.4)
        tr.mark(
            "llm_response",
            detail={
                "model": result["model"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "answer_chars": len(result.get("content") or ""),
            },
        )
        if not (result.get("content") or "").strip():
            raise RuntimeError("Brain returned empty answer. Retry with higher max_tokens.")

    answer = result["content"]
    with step(tr, "critic"):
        critic = critique_answer(answer, facts)
        tr.mark("critic", detail={"ok": critic["ok"], "issues": len(critic["issues"])})
        if not critic["ok"]:
            answer = (
                answer.rstrip()
                + "\n\n---\nCRITIC (packet check): some cited numbers were not in the Python packet:\n"
                + "\n".join(f"- {i['kind']}: {i['reason']}" for i in critic["issues"][:8])
            )

    with step(tr, "record_usage"):
        cost = record_usage(
            model=result["model"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            note=f"harness:{plan['domain']}",
        )

    return {
        "answer": answer,
        "model": result["model"],
        "chart_key": chart_key,
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "estimated_cost_usd": round(cost, 6),
        "trace_id": tr.trace_id,
        "pipeline_trace": tr.summary(),
        "packet_plan": {
            "keys": plan["keys"],
            "rationale": f"harness domains={plan['domains']}",
            "matched_topics": plan["domains"],
        },
        "tools_used": [],
        "mode": "harness",
        "prompt_profile": prompt_profile,
        "harness_plan": {k: plan[k] for k in ("domains", "domain", "inventory_title", "keys", "specialists", "nadi_combos", "kp_cusps", "houses")},
        "specialist_audit": audit_rows,
        "rag_hits": [{"source": h.get("source"), "score": h.get("score"), "topic": h.get("topic")} for h in rag_hits],
        "critic": critic,
    }
