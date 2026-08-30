"""
FastAPI application for chart compute/cache (M1).

Purpose:
    Expose KP chart generation for the future web app and Telegram bot without
    touching the frozen Streamlit app on B:\\.

Inputs:
    HTTP JSON (see API.md).

Outputs:
    Chart documents with structured_payload; usage budget stub.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from dateutil.parser import isoparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.schemas import AskRequest, AskResponse, ChartCreateRequest, ChartResponse, PlaceHit, UsageResponse
from shared.ask_service import ask_chart
from shared.chart_service import compute_or_get_chart, get_cached_chart
from shared.config import (
    ALLOWLIST_IDS,
    DEFAULT_LLM,
    FALLBACK_LLM,
    MONTHLY_BUDGET_USD,
    ensure_data_dirs,
)
from shared.places import search_places
from shared.usage import get_usage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api")

app = FastAPI(
    title="astro_agents chart API",
    version="0.1.0",
    description="KP chart service wrapping engine.astro_kp.calculate_vedic_charts",
)

# Laptop-local web (Vite) + future VPS — tighten origins in production via env later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_data_dirs()
    key_ok = bool(os.getenv("NVIDIA_API_KEY", "").strip())
    logger.info(
        "api startup budget_usd=%s allowlist=%s nvidia_key=%s model=%s",
        MONTHLY_BUDGET_USD,
        len(ALLOWLIST_IDS),
        "SET" if key_ok else "MISSING",
        os.getenv("NVIDIA_MODEL", ""),
    )


@app.get("/")
def root() -> RedirectResponse:
    """Browsers hitting the base URL land on interactive OpenAPI docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/places")
def places(q: str = "", limit: int = 20) -> dict[str, list[PlaceHit]]:
    """Typeahead place search (same logic as Streamlit KP v2 city search)."""
    try:
        hits = search_places(q, limit=min(max(limit, 1), 30))
    except Exception as exc:
        logger.exception("place search failed")
        raise HTTPException(status_code=500, detail=f"place search failed: {exc}") from exc
    return {"results": [PlaceHit(**h) for h in hits]}


@app.post("/v1/charts", response_model=ChartResponse)
def create_chart(body: ChartCreateRequest) -> dict[str, Any]:
    try:
        dt = isoparse(body.datetime_iso)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid datetime_iso: {exc}") from exc

    if dt.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="datetime_iso must include timezone offset (e.g. +05:30)",
        )

    try:
        doc = compute_or_get_chart(
            name=body.name,
            dt_aware=dt,
            lat=body.lat,
            lon=body.lon,
            gender=body.gender,
            force_recompute=body.force_recompute,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # engine / ephemeris failures
        logger.exception("chart compute failed")
        raise HTTPException(status_code=500, detail=f"chart compute failed: {exc}") from exc

    return doc


@app.get("/v1/charts/{chart_key}", response_model=ChartResponse)
def get_chart(chart_key: str) -> dict[str, Any]:
    doc = get_cached_chart(chart_key)
    if doc is None:
        raise HTTPException(status_code=404, detail="chart not found")
    doc = dict(doc)
    doc["cached"] = True
    return doc


@app.get("/v1/usage", response_model=UsageResponse)
def usage() -> UsageResponse:
    u = get_usage()
    return UsageResponse(
        monthly_budget_usd=u["monthly_budget_usd"],
        spent_usd=u["spent_usd"],
        remaining_usd=u["remaining_usd"],
        default_llm=DEFAULT_LLM,
        fallback_llm=FALLBACK_LLM,
        allowlist_count=len(ALLOWLIST_IDS),
    )


@app.get("/v1/models")
def models() -> dict[str, Any]:
    """List allowlisted NIM models for A/B testing in the web UI."""
    from shared.models_catalog import default_model, list_models

    return {"default": default_model(), "models": list_models()}


@app.post("/v1/ask", response_model=AskResponse)
def ask(body: AskRequest) -> dict[str, Any]:
    """Interpretive Q&A using Gem/KP or planet_taste prompt + NVIDIA NIM model."""
    try:
        return ask_chart(
            chart_key=body.chart_key,
            question=body.question,
            history=body.history,
            max_tokens=body.max_tokens,
            model=body.model,
            prompt_profile=body.prompt_profile,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "rate limit" in msg or "429" in msg:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        # budget or missing API key
        raise HTTPException(status_code=402 if "budget" in msg else 503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("ask failed")
        raise HTTPException(status_code=500, detail=f"ask failed: {exc}") from exc
