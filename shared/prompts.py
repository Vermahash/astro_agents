"""
Prompt loading for interpretive agents.

Purpose:
    Load system prompts for /v1/ask. Supports profiles for A/B testing:
    default Gem+KP strict contract, or planet-taste placement prompt.

Inputs:
    prompt_profile name; files under docs/prompts/.

Outputs:
    System prompt string.
"""

from __future__ import annotations

from pathlib import Path

from shared.answer_contract import ANSWER_CONTRACT
from shared.config import ROOT

PROMPTS_DIR = ROOT / "docs" / "prompts"
ACTIVE_GEM = PROMPTS_DIR / "ACTIVE_GEM.md"
DEFAULT_KP = PROMPTS_DIR / "Gemini_instructionsKP.md"
KP_CORE = PROMPTS_DIR / "pmp" / "01_KP_CORE_PROTOCOL.md"
PLANET_TASTE = PROMPTS_DIR / "PLANET_TASTE.md"

PROMPT_PROFILES = ("default", "planet_taste")


def load_system_prompt(profile: str = "default") -> str:
    """
    Return the system prompt for KP interpretation.

    Profiles:
        default — ACTIVE_GEM (or KP docs) + ANSWER_CONTRACT
        planet_taste — focused planet placement / delivery taste prompt
    """
    name = (profile or "default").strip().lower()
    if name not in PROMPT_PROFILES:
        raise ValueError(f"prompt_profile must be one of: {', '.join(PROMPT_PROFILES)}")

    if name == "planet_taste":
        if PLANET_TASTE.exists():
            return PLANET_TASTE.read_text(encoding="utf-8").strip() + "\n"
        return (
            "You are a KP planet-placement analyst. Cite packet star/sub/house only. "
            "Explain what each planet sits in and what taste it delivers for the query.\n"
        )

    base = _load_base_prompt()
    return base.rstrip() + "\n\n" + ANSWER_CONTRACT.strip() + "\n"


def _load_base_prompt() -> str:
    if ACTIVE_GEM.exists():
        text = ACTIVE_GEM.read_text(encoding="utf-8").strip()
        if len(text) > 200 and "Paste the full system instruction" not in text:
            return text

    parts: list[str] = []
    if DEFAULT_KP.exists():
        parts.append(DEFAULT_KP.read_text(encoding="utf-8"))
    if KP_CORE.exists():
        parts.append("\n\n---\n# Supplemental: KP Core Protocol\n\n")
        parts.append(KP_CORE.read_text(encoding="utf-8"))
    if not parts:
        return (
            "You are BRAHMA-DAIVAGYA, a pure KP interpreter. "
            "Never recalculate longitudes. Use only the supplied KP MASTER DATA PACKET."
        )
    return "".join(parts)
