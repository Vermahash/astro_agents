"""
Tool-using ask agent (single loop, no multi-agent fan-out).

Purpose:
    Muse Glimmer discovers chart tools, fetches only needed KP slices from
    SQLite via the shared registry, then synthesizes an answer.

Inputs:
    chart_key, question, optional history, max_tokens, pipeline trace.

Outputs:
    Answer + usage + tools_used + pipeline_trace; may signal fallback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.chart_store import ensure_chart_in_store
from shared.chart_tools import field_catalog_hint, openai_tool_schemas, run_tool
from shared.llm_nvidia import chat_messages
from shared.pipeline_trace import PipelineTrace, step

logger = logging.getLogger(__name__)

MAX_TOOL_RESULT = 24_000

# Tools that accept chart_key (for auto-inject)
TOOLS_PARAM_NAMES: dict[str, list[str]] = {
    "list_chart_fields": ["chart_key"],
    "get_chart_meta": ["chart_key"],
    "get_chart_slice": ["chart_key", "fields"],
    "get_cusp": ["chart_key", "house"],
    "get_planet": ["chart_key", "planet"],
    "search_places": ["q", "limit"],
}

TOOL_PREAMBLE = """
## Chart tools (deterministic KP data)
You have tools that read a precomputed chart database. Never invent longitudes,
cusp degrees, star/sub lords, or dasha dates — always call tools.

Workflow:
1. Call get_chart_meta, then get_chart_slice for cusps + planet_star_sub_lords + kp_prediction (minimum).
2. For event questions also get_cusp(house) for the principal house (e.g. 7 for marriage, 10 for career).
3. After tools return, write the SESSION OVERRIDE answer skeleton (Verdict / KP Evidence / Timing / Risks / Confidence).
4. Every bullet in KP Evidence must quote a value that appeared in a tool result.

Do not answer with general astrology. If a needed field is missing after tools, Verdict = INSUFFICIENT DATA.
"""


def _history_messages(history: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for turn in (history or [])[-4:]:
        role = turn.get("role", "user")
        content = (turn.get("content") or "").strip()
        if not content or content.startswith("— ") or content.startswith("Ask failed:"):
            continue
        if role not in ("user", "assistant"):
            role = "user"
        msgs.append({"role": role, "content": content[:800]})
    return msgs


def run_tool_agent(
    *,
    chart_key: str,
    question: str,
    system_prompt: str,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 4096,
    max_rounds: int = 4,
    model: str | None = None,
    tr: PipelineTrace | None = None,
) -> dict[str, Any]:
    """
    Run the tool-calling agent loop.

    Returns:
        dict with answer, model, tokens, tools_used, mode="tools".
        Raises RuntimeError with prefix "fallback:" when tools unsupported / unused
        and caller should use packet_planner path.
    """
    if not ensure_chart_in_store(chart_key):
        raise FileNotFoundError(f"chart not found: {chart_key}")

    system = system_prompt.rstrip() + "\n\n" + TOOL_PREAMBLE + "\n" + field_catalog_hint()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(_history_messages(history))
    messages.append(
        {
            "role": "user",
            "content": (
                f"chart_key={chart_key}\n\n"
                f"USER QUESTION:\n{question.strip()}\n\n"
                "Use tools to fetch cusps, planet_star_sub_lords, and kp_prediction at minimum. "
                "Then answer with Verdict + KP Evidence citing exact CSL/star/sub values from tool JSON. "
                "No vague language."
            ),
        }
    )

    tools = openai_tool_schemas()
    tools_used: list[dict[str, Any]] = []
    total_prompt = 0
    total_completion = 0
    model_id = ""
    saw_tool_call = False

    for round_i in range(max_rounds):
        node = f"llm_round_{round_i + 1}"
        if tr is not None:
            ctx = step(tr, node, round=round_i + 1)
        else:
            from contextlib import nullcontext

            ctx = nullcontext()

        with ctx:
            try:
                result = chat_messages(
                    messages=messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=1.0,
                    model=model,
                )
            except RuntimeError as exc:
                if "tool_calling_unsupported" in str(exc):
                    raise RuntimeError(f"fallback: {exc}") from exc
                raise

            model_id = result["model"]
            total_prompt += result["prompt_tokens"]
            total_completion += result["completion_tokens"]
            tool_calls = result.get("tool_calls") or []

            if tr is not None:
                tr.mark(
                    "llm_round_result",
                    detail={
                        "round": round_i + 1,
                        "model": model_id,
                        "finish": result.get("finish_reason"),
                        "tool_calls": len(tool_calls),
                        "answer_chars": len(result.get("content") or ""),
                        "content_source": result.get("content_source"),
                    },
                )

            if tool_calls:
                saw_tool_call = True
                asst = result.get("assistant_message") or {
                    "role": "assistant",
                    "content": result.get("content") or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
                messages.append(asst)

                for tc in tool_calls:
                    args = dict(tc["arguments"] or {})
                    if "chart_key" in (TOOLS_PARAM_NAMES.get(tc["name"]) or []) and "chart_key" not in args:
                        args["chart_key"] = chart_key

                    if tr is not None:
                        tool_ctx = step(tr, f"tool.{tc['name']}", **{k: str(v)[:40] for k, v in list(args.items())[:4]})
                    else:
                        from contextlib import nullcontext

                        tool_ctx = nullcontext()

                    with tool_ctx:
                        out = run_tool(tc["name"], args)
                        tools_used.append(
                            {
                                "name": tc["name"],
                                "ms": out.get("ms"),
                                "bytes": out.get("bytes"),
                                "ok": out.get("ok"),
                            }
                        )
                        if tr is not None:
                            tr.mark(
                                "tool_result",
                                detail={
                                    "name": tc["name"],
                                    "ok": out.get("ok"),
                                    "ms": out.get("ms"),
                                    "bytes": out.get("bytes"),
                                },
                            )
                        payload = out.get("result") if out.get("ok") else {"error": out.get("error")}
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(payload, ensure_ascii=False, default=str)[:MAX_TOOL_RESULT],
                            }
                        )
                continue

            content = (result.get("content") or "").strip()
            if content:
                if not saw_tool_call:
                    raise RuntimeError("fallback: model answered without tool calls")
                return {
                    "answer": content,
                    "model": model_id,
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "tools_used": tools_used,
                    "mode": "tools",
                }

            if saw_tool_call:
                messages.append(
                    {
                        "role": "user",
                        "content": "Using the tool results already returned, write the final KP answer now.",
                    }
                )
                continue

            raise RuntimeError("fallback: empty response without tool calls")

    if saw_tool_call and tools_used:
        if tr is not None:
            final_ctx = step(tr, "llm_final_no_tools")
        else:
            from contextlib import nullcontext

            final_ctx = nullcontext()
        with final_ctx:
            messages.append(
                {
                    "role": "user",
                    "content": "Stop calling tools. Write the final KP answer from the data you already have.",
                }
            )
            result = chat_messages(
                messages=messages,
                max_tokens=max_tokens,
                temperature=1.0,
                model=model,
            )
            total_prompt += result["prompt_tokens"]
            total_completion += result["completion_tokens"]
            content = (result.get("content") or "").strip()
            if content:
                return {
                    "answer": content,
                    "model": result["model"],
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "tools_used": tools_used,
                    "mode": "tools",
                }

    raise RuntimeError("fallback: tool agent exhausted rounds without answer")
