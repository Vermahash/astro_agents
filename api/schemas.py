"""
Pydantic request/response models for the chart API.

Purpose:
    Validate birth inputs and document response shapes for web/Telegram clients.

Inputs / Outputs:
    Used by FastAPI route handlers in api/app.py.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChartCreateRequest(BaseModel):
    """Birth data required to compute or fetch a KP chart."""

    name: str = Field(..., min_length=1)
    datetime_iso: str = Field(
        ...,
        description="ISO-8601 datetime with timezone offset, e.g. 1990-01-15T14:30:00+05:30",
    )
    lat: float
    lon: float
    gender: str = "Unknown"
    force_recompute: bool = False


class ChartMeta(BaseModel):
    name: str
    datetime_iso: str
    lat: float
    lon: float
    gender: str
    lagna: str | None = None
    moon_nakshatra: str | None = None


class ChartResponse(BaseModel):
    chart_key: str
    cached: bool
    engine_version: str
    meta: ChartMeta
    structured_payload: dict[str, Any]


class UsageResponse(BaseModel):
    monthly_budget_usd: float
    spent_usd: float
    remaining_usd: float
    default_llm: str
    fallback_llm: str
    allowlist_count: int


class PlaceHit(BaseModel):
    label: str
    lat: float
    lon: float


class HarnessAuditRequest(BaseModel):
    """Python-only PRE-AUDIT inspection (no LLM)."""

    chart_key: str
    question: str = Field(..., min_length=1)
    use_rag: bool = False


class AskRequest(BaseModel):
    chart_key: str
    question: str = Field(..., min_length=1)
    history: list[dict[str, str]] = Field(default_factory=list)
    max_tokens: int = Field(default=4096, ge=200, le=8192)
    model: str | None = Field(
        default=None,
        description="NIM model id or alias: muse | minimax | deepseek | meta/muse-glimmer-30b",
    )
    prompt_profile: str = Field(
        default="pre_audit",
        description="pre_audit (PRE-AUDIT Brain), default (Gem+KP), or planet_taste",
    )
    use_web_law: bool = Field(
        default=False,
        description="If true, Brain may fetch Wikipedia snippets for named yogas/laws (doctrine only)",
    )


class AskResponse(BaseModel):
    answer: str
    model: str
    chart_key: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    trace_id: str | None = None
    pipeline_trace: dict[str, Any] | None = None
    packet_plan: dict[str, Any] | None = None
    tools_used: list[dict[str, Any]] = Field(default_factory=list)
    mode: str | None = None
    prompt_profile: str | None = None
    harness_plan: dict[str, Any] | None = None
    specialist_audit: list[dict[str, Any]] | None = None
    rag_hits: list[dict[str, Any]] | None = None
    critic: dict[str, Any] | None = None
