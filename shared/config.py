"""
Application configuration for astro_agents.

Purpose:
    Central env-driven settings so laptop → VPS migration is config-only.

Inputs:
    Environment variables (optional overrides).

Outputs:
    Settings values used by api/, shared/, telegram/.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine"
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache" / "charts"
SQLITE_DIR = DATA_DIR / "sqlite"
RAG_DIR = DATA_DIR / "rag"
N8N_ASTRO_ROOT = Path(os.getenv("ASTRO_N8N_ROOT", r"B:\n8n\astro"))

# Load E:\astro_agents\.env into process env (does not override already-set vars)
load_dotenv(ROOT / ".env")

ENGINE_VERSION = os.getenv("ASTRO_ENGINE_VERSION", "kpastro-v2")

# Cost governor (PRD): hard cap on paid LLM spend per calendar month
MONTHLY_BUDGET_USD = float(os.getenv("ASTRO_MONTHLY_BUDGET_USD", "5.0"))

# Allowlist: comma-separated Telegram user ids (and future web user ids).
# Empty means "dev open locally" for API; Telegram bot must still enforce.
_ALLOW = os.getenv("ASTRO_ALLOWLIST_IDS", "").strip()
ALLOWLIST_IDS: set[str] = {x.strip() for x in _ALLOW.split(",") if x.strip()}

DEFAULT_LLM = os.getenv("ASTRO_DEFAULT_LLM", "nvidia/muse-glimmer")
FALLBACK_LLM = os.getenv("ASTRO_FALLBACK_LLM", "gemini-flash")


def ensure_data_dirs() -> None:
    """Create on-disk data folders if missing."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    RAG_DIR.mkdir(parents=True, exist_ok=True)
