"""
NVIDIA NIM OpenAI-compatible LLM client (Muse Glimmer default).

Purpose:
    Call cloud open models for chart interpretation without reinventing math.
    Supports plain chat and OpenAI-style tool calling for the ask agent.

Inputs:
    Messages + model id; NVIDIA_API_KEY from env.

Outputs:
    Assistant text and/or tool_calls + token usage.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from openai import APITimeoutError, OpenAI, RateLimitError

from shared.config import ROOT  # load .env
from shared.models_catalog import DEEPSEEK_FLASH, MINIMAX_M3, resolve_model_id

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")


def _client() -> OpenAI:
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. Create a key at build.nvidia.com and set it in the environment."
        )
    timeout_s = float(os.getenv("NVIDIA_TIMEOUT_S", "90"))
    http_timeout = httpx.Timeout(timeout_s, connect=20.0)
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=key, timeout=http_timeout)


def resolve_model(model: str | None = None) -> str:
    return resolve_model_id(model)


def _extra_body_for_model(model_id: str) -> dict[str, Any] | None:
    """NIM model-specific chat_template_kwargs (thinking modes)."""
    if model_id == DEEPSEEK_FLASH:
        # Keep thinking off for faster, cheaper A/B answers
        return {"chat_template_kwargs": {"thinking": False}}
    if model_id == MINIMAX_M3:
        return {"chat_template_kwargs": {"thinking_mode": "disabled"}}
    return None


def _extract_text(message: Any) -> tuple[str, str]:
    """
    Muse Glimmer / NIM reasoning models often put text in reasoning_content
    while content is empty when the token budget is spent on CoT.
    """
    content = getattr(message, "content", None) or ""
    reasoning = getattr(message, "reasoning_content", None) or ""
    if not isinstance(content, str):
        content = str(content or "")
    if not isinstance(reasoning, str):
        reasoning = str(reasoning or "")

    if not reasoning:
        extra = getattr(message, "model_extra", None) or {}
        if isinstance(extra, dict):
            reasoning = str(extra.get("reasoning_content") or "")

    text = (content or "").strip()
    source = "content"
    if not text and reasoning.strip():
        text = reasoning.strip()
        source = "reasoning_content"
    return text, source


def _parse_tool_calls(message: Any) -> list[dict[str, Any]]:
    raw = getattr(message, "tool_calls", None) or []
    out: list[dict[str, Any]] = []
    for tc in raw:
        fn = getattr(tc, "function", None)
        name = getattr(fn, "name", None) if fn is not None else None
        arg_s = getattr(fn, "arguments", None) if fn is not None else "{}"
        tc_id = getattr(tc, "id", None) or f"call_{len(out)}"
        args: dict[str, Any] = {}
        if isinstance(arg_s, str) and arg_s.strip():
            try:
                parsed = json.loads(arg_s)
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {"_raw": arg_s}
        elif isinstance(arg_s, dict):
            args = arg_s
        if name:
            out.append({"id": tc_id, "name": name, "arguments": args})
    return out


def chat_completion(
    *,
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """
    Run one chat completion against NVIDIA NIM (no tools).

    Returns:
        {content, model, prompt_tokens, completion_tokens, finish_reason, content_source}
    """
    return chat_messages(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def chat_messages(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
) -> dict[str, Any]:
    """
    Chat completion with optional OpenAI tools.

    Returns:
        {content, tool_calls, model, prompt_tokens, completion_tokens, finish_reason, content_source}
    """
    model_id = resolve_model(model)
    client = _client()
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.95,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
    extra = _extra_body_for_model(model_id)
    if extra:
        kwargs["extra_body"] = extra

    logger.info(
        "nvidia chat model=%s max_tokens=%s temp=%s tools=%s",
        model_id,
        max_tokens,
        temperature,
        len(tools or []),
    )
    timeout_s = float(os.getenv("NVIDIA_TIMEOUT_S", "90"))
    try:
        completion = client.chat.completions.create(timeout=timeout_s, **kwargs)
    except (APITimeoutError, httpx.TimeoutException) as exc:
        logger.warning("nvidia timeout model=%s: %s", model_id, exc)
        raise RuntimeError(
            f"NVIDIA NIM timed out after {timeout_s:.0f}s for {model_id}. Retry or raise NVIDIA_TIMEOUT_S."
        ) from exc
    except RateLimitError as exc:
        logger.warning("nvidia rate limited model=%s: %s", model_id, exc)
        raise RuntimeError(
            f"NVIDIA NIM rate limit (429) for {model_id}. "
            "MiniMax especially hits this on multi-round tool calls — wait and retry, "
            "or switch to deepseek-ai/deepseek-v4-flash-0731 / Muse Glimmer."
        ) from exc
    except Exception as exc:
        # Some NIM models reject tools — surface clearly for agent fallback
        if tools and "tool" in str(exc).lower():
            logger.warning("nvidia tools rejected: %s", exc)
            raise RuntimeError(f"tool_calling_unsupported: {exc}") from exc
        raise

    choice = completion.choices[0]
    message = choice.message
    text, source = _extract_text(message)
    tool_calls = _parse_tool_calls(message)
    finish = getattr(choice, "finish_reason", None) or ""
    usage = completion.usage

    if not text and not tool_calls:
        logger.warning(
            "nvidia empty answer finish=%s source=%s",
            finish,
            source,
        )

    return {
        "content": text,
        "tool_calls": tool_calls,
        "model": model_id,
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "finish_reason": finish,
        "content_source": source,
        "assistant_message": {
            "role": "assistant",
            "content": getattr(message, "content", None) or (text if source == "content" else None),
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
            ]
            or None,
        },
    }


# Back-compat alias used by ask agent docs
chat_completion_tools = chat_messages
