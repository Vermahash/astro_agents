"""
Allowed NVIDIA NIM models for ask A/B testing.

Purpose:
    Map short aliases to full NIM model ids so web/API can switch between
    Muse Glimmer, DeepSeek Flash, and (optional) MiniMax during comparison.

Inputs:
    Optional alias or full model id from request / env.

Outputs:
    Resolved model id or ValueError if not allowlisted.
"""

from __future__ import annotations

import os
from typing import Any

MUSE_GLIMMER = "meta/muse-glimmer-30b"
DEEPSEEK_FLASH = "deepseek-ai/deepseek-v4-flash-0731"
MINIMAX_M3 = "minimaxai/minimax-m3"

# Per-model behavior on NIM trial / free tiers
MODEL_META: dict[str, dict[str, Any]] = {
    MUSE_GLIMMER: {
        "alias": "muse",
        "label": "Muse Glimmer 30B",
        "role": "default / reasoning",
        "supports_tools": True,
        "notes": "",
    },
    DEEPSEEK_FLASH: {
        "alias": "deepseek",
        "label": "DeepSeek V4 Flash",
        "role": "A/B test synthesizer",
        "supports_tools": False,  # single-shot synthesize — fewer NIM calls
        "notes": "Prefer planet_taste prompt; tools disabled to avoid rate limits",
    },
    MINIMAX_M3: {
        "alias": "minimax",
        "label": "MiniMax M3 (rate-limited)",
        "role": "unstable on NIM trial",
        "supports_tools": False,
        "notes": "Often returns HTTP 429 Too Many Requests after multi-round tool calls",
    },
}

ALIASES: dict[str, str] = {
    "muse": MUSE_GLIMMER,
    "glimmer": MUSE_GLIMMER,
    "muse-glimmer": MUSE_GLIMMER,
    "nvidia/muse-glimmer": MUSE_GLIMMER,
    "meta/muse-glimmer-30b": MUSE_GLIMMER,
    "deepseek": DEEPSEEK_FLASH,
    "flash": DEEPSEEK_FLASH,
    "deepseek-flash": DEEPSEEK_FLASH,
    "deepseek-v4-flash": DEEPSEEK_FLASH,
    "deepseek-ai/deepseek-v4-flash-0731": DEEPSEEK_FLASH,
    "minimax": MINIMAX_M3,
    "m3": MINIMAX_M3,
    "minimax-m3": MINIMAX_M3,
    "minimaxai/minimax-m3": MINIMAX_M3,
}

ALLOWLIST: frozenset[str] = frozenset(MODEL_META.keys())


def default_model() -> str:
    raw = os.getenv("NVIDIA_MODEL", MUSE_GLIMMER).strip()
    try:
        return resolve_model_id(raw)
    except ValueError:
        return MUSE_GLIMMER


def resolve_model_id(model: str | None) -> str:
    """Resolve alias → NIM id; reject unknown models."""
    if not model or not str(model).strip():
        return default_model()
    key = str(model).strip()
    resolved = ALIASES.get(key.lower(), ALIASES.get(key, key))
    if resolved not in ALLOWLIST:
        allowed = ", ".join(sorted(ALLOWLIST))
        raise ValueError(f"model not allowed: {model}. Allowed: {allowed}")
    return resolved


def model_supports_tools(model: str | None) -> bool:
    mid = resolve_model_id(model)
    return bool(MODEL_META.get(mid, {}).get("supports_tools", True))


def list_models() -> list[dict[str, Any]]:
    """Catalog for UI / GET /v1/models."""
    out = []
    for mid, meta in MODEL_META.items():
        out.append(
            {
                "id": mid,
                "alias": meta["alias"],
                "label": meta["label"],
                "role": meta["role"],
                "supports_tools": meta["supports_tools"],
                "notes": meta.get("notes") or "",
            }
        )
    return out
