"""
Interpretive ask service: tool agent with packet-planner fallback.

Purpose:
    Prefer Muse Glimmer + chart tools (selective SQLite slices). If the model
    cannot use tools, fall back to keyword packet_planner + single synthesize.

Inputs:
    chart_key, user question, optional conversation snippets.

Outputs:
    Answer text + model/usage metadata + pipeline_trace + tools_used.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.ask_agent import run_tool_agent
from shared.chart_service import get_cached_chart
from shared.chart_store import ensure_chart_in_store
from shared.domain_harness import classify_domains
from shared.harness_pipeline import run_harness
from shared.llm_nvidia import chat_completion
from shared.packet_planner import plan_packet_keys
from shared.models_catalog import model_supports_tools, resolve_model_id
from shared.pipeline_trace import pipeline, step
from shared.prompts import load_system_prompt
from shared.usage import assert_budget_allows, record_usage

logger = logging.getLogger(__name__)

MAX_PACKET_CHARS = 24_000
HARNESS_PROFILES = frozenset({"pre_audit"})
HARNESS_DOMAINS = frozenset({"finance", "health", "marriage", "career", "children", "education", "foreign"})


def _should_use_harness(prompt_profile: str, question: str) -> bool:
    """PRE-AUDIT Brain path for pre_audit profile and domain questions on default."""
    name = (prompt_profile or "default").strip().lower()
    if name == "planet_taste":
        return False
    if name in HARNESS_PROFILES:
        return True
    domains = classify_domains(question)
    return any(d in HARNESS_DOMAINS for d in domains)


def _condense_payload(structured: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Keep planner-selected slices; drop bulky audit blobs."""
    out: dict[str, Any] = {}
    for k in keys:
        if k in structured:
            out[k] = structured[k]
    matrix = out.get("kp_astrology_matrix")
    if isinstance(matrix, dict):
        slim = {
            kk: vv
            for kk, vv in matrix.items()
            if not (isinstance(vv, str) and len(vv) > 4000)
        }
        out["kp_astrology_matrix"] = slim
    return out


def build_user_message(
    question: str,
    chart_doc: dict[str, Any],
    history: list[dict[str, str]] | None = None,
    *,
    keys: list[str],
) -> str:
    payload = _condense_payload(chart_doc.get("structured_payload") or {}, keys)
    packet_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(packet_json) > MAX_PACKET_CHARS:
        packet_json = packet_json[:MAX_PACKET_CHARS] + "…[truncated for token budget]"

    meta = chart_doc.get("meta") or {}
    hist_lines: list[str] = []
    for turn in (history or [])[-4:]:
        role = turn.get("role", "user")
        content = (turn.get("content") or "").strip()
        if content.startswith("— ") or content.startswith("Ask failed:"):
            continue
        if content:
            hist_lines.append(f"{role.upper()}: {content[:800]}")

    parts = [
        "KP MASTER DATA PACKET (authoritative — do not recalculate):",
        packet_json,
        "",
        f"Chart meta: {json.dumps(meta, ensure_ascii=False)}",
        f"Packet slices included: {', '.join(keys)}",
        "",
    ]
    if hist_lines:
        parts.append("Recent conversation:")
        parts.extend(hist_lines)
        parts.append("")
    parts.append("USER QUESTION:")
    parts.append(question.strip())
    parts.append("")
    parts.append(
        "Answer in PURE KP STRICT MODE. "
        "Start with Verdict (PROMISED|DENIED|DELAYED|MIXED|INSUFFICIENT DATA). "
        "In KP Evidence, quote cusp sub-lord, star/sub lords, and house significators from THIS packet only. "
        "Do not use vague or motivational language. If data is missing, say INSUFFICIENT DATA."
    )
    return "\n".join(parts)


def _ask_fallback_planner(
    *,
    chart_key: str,
    question: str,
    history: list[dict[str, str]] | None,
    max_tokens: int,
    system: str,
    doc: dict[str, Any],
    tr: Any,
    model: str | None = None,
    prompt_profile: str = "default",
) -> dict[str, Any]:
    structured = doc.get("structured_payload") or {}
    with step(tr, "plan_packet_fallback", q_len=len(question)):
        plan = plan_packet_keys(question, structured if isinstance(structured, dict) else {})
        tr.mark(
            "packet_plan",
            detail={
                "rationale": plan["rationale"],
                "key_count": len(plan["keys"]),
                "keys": ",".join(plan["keys"][:12]),
            },
        )

    with step(tr, "build_user_msg", q_len=len(question)):
        user = build_user_message(question, doc, history, keys=plan["keys"])
        tr.mark(
            "user_message_ready",
            detail={"user_chars": len(user), "history_turns": len(history or []), "max_tokens": max_tokens},
        )

    # planet_taste: slightly cooler sampling for placement fidelity
    temp = 0.4 if prompt_profile == "planet_taste" else 1.0
    with step(tr, "nvidia_synthesize", model=str(model or "default")[:24]):
        result = chat_completion(
            system=system,
            user=user,
            max_tokens=max_tokens,
            model=model,
            temperature=temp,
        )
        tr.mark(
            "llm_response",
            detail={
                "model": result["model"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "answer_chars": len(result.get("content") or ""),
                "finish_reason": result.get("finish_reason"),
                "content_source": result.get("content_source"),
            },
        )
        if not (result.get("content") or "").strip():
            raise RuntimeError(
                "Model returned empty answer (likely reasoning used the whole token budget). "
                "Retry with a shorter question or higher max_tokens."
            )

    with step(tr, "record_usage"):
        cost = record_usage(
            model=result["model"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            note=f"ask_fallback:{prompt_profile}",
        )

    return {
        "answer": result["content"],
        "model": result["model"],
        "chart_key": chart_key,
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "estimated_cost_usd": round(cost, 6),
        "trace_id": tr.trace_id,
        "pipeline_trace": tr.summary(),
        "packet_plan": plan,
        "tools_used": [],
        "mode": "fallback_planner",
        "prompt_profile": prompt_profile,
    }


def ask_chart(
    *,
    chart_key: str,
    question: str,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 4096,
    model: str | None = None,
    prompt_profile: str = "default",
    use_web_law: bool = False,
) -> dict[str, Any]:
    if not question or not question.strip():
        raise ValueError("question is required")

    model_id = resolve_model_id(model)

    with pipeline("ask") as tr:
        with step(tr, "load_cached_chart", chart_key=chart_key[:12]):
            doc = get_cached_chart(chart_key)
            if doc is None:
                raise FileNotFoundError(f"chart not found: {chart_key}")
            ensure_chart_in_store(chart_key)
            meta = doc.get("meta") or {}
            structured = doc.get("structured_payload") or {}
            tr.mark(
                "chart_meta",
                detail={
                    "name": meta.get("name"),
                    "lagna": meta.get("lagna"),
                    "keys": len(structured) if isinstance(structured, dict) else 0,
                },
            )

        with step(tr, "budget_gate"):
            assert_budget_allows(0.08)

        if _should_use_harness(prompt_profile, question):
            tr.mark(
                "harness_route",
                detail={"profile": prompt_profile, "domains": ",".join(classify_domains(question))},
            )
            return run_harness(
                chart_key=chart_key,
                question=question,
                doc=doc,
                tr=tr,
                model=model_id,
                max_tokens=max_tokens,
                prompt_profile="pre_audit" if prompt_profile != "planet_taste" else "pre_audit",
                use_rag=True,
                use_web_law=use_web_law,
            )

        with step(tr, "load_system_prompt", profile=prompt_profile):
            system = load_system_prompt(prompt_profile)
            tr.mark(
                "prompt_ready",
                detail={
                    "profile": prompt_profile,
                    "model": model_id,
                    "system_chars": len(system),
                    "system_preview": system[:80].replace("\n", " "),
                },
            )

        use_tools = model_supports_tools(model_id)
        if not use_tools:
            tr.mark(
                "skip_tool_agent",
                detail={"reason": "model_disables_tools", "model": model_id},
            )
            return _ask_fallback_planner(
                chart_key=chart_key,
                question=question,
                history=history,
                max_tokens=max_tokens,
                system=system,
                doc=doc,
                tr=tr,
                model=model_id,
                prompt_profile=prompt_profile,
            )

        with step(tr, "tool_agent"):
            try:
                agent_out = run_tool_agent(
                    chart_key=chart_key,
                    question=question,
                    system_prompt=system,
                    history=history,
                    max_tokens=max_tokens,
                    model=model_id,
                    tr=tr,
                )
            except RuntimeError as exc:
                if str(exc).startswith("fallback:"):
                    tr.mark("tool_agent_fallback", detail={"reason": str(exc)[:200]})
                    logger.info("ask tool agent fallback: %s", exc)
                    return _ask_fallback_planner(
                        chart_key=chart_key,
                        question=question,
                        history=history,
                        max_tokens=max_tokens,
                        system=system,
                        doc=doc,
                        tr=tr,
                        model=model_id,
                        prompt_profile=prompt_profile,
                    )
                raise

        with step(tr, "record_usage"):
            cost = record_usage(
                model=agent_out["model"],
                prompt_tokens=agent_out["prompt_tokens"],
                completion_tokens=agent_out["completion_tokens"],
                note=f"ask_tools:{prompt_profile}",
            )

        return {
            "answer": agent_out["answer"],
            "model": agent_out["model"],
            "chart_key": chart_key,
            "prompt_tokens": agent_out["prompt_tokens"],
            "completion_tokens": agent_out["completion_tokens"],
            "estimated_cost_usd": round(cost, 6),
            "trace_id": tr.trace_id,
            "pipeline_trace": tr.summary(),
            "packet_plan": None,
            "tools_used": agent_out.get("tools_used") or [],
            "mode": agent_out.get("mode") or "tools",
            "prompt_profile": prompt_profile,
        }
