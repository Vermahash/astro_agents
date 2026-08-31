"""
HTTP smoke tests for FastAPI routes used by the web app.

Purpose:
    Confirm health, models, usage, harness plan, validation, and 404s without NVIDIA.

Inputs:
    In-process TestClient (no live uvicorn required).

Outputs:
    pytest pass/fail.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_models_list_includes_deepseek():
    res = client.get("/v1/models")
    assert res.status_code == 200
    ids = {m["id"] for m in res.json()["models"]}
    assert "deepseek-ai/deepseek-v4-flash-0731" in ids


def test_usage_budget_shape():
    res = client.get("/v1/usage")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["monthly_budget_usd"], (int, float))
    assert body["monthly_budget_usd"] > 0
    assert "spent_usd" in body and "remaining_usd" in body


def test_harness_plan_requires_q():
    res = client.get("/v1/harness/plan", params={"q": ""})
    assert res.status_code == 422


def test_rag_search_rejects_short_q():
    res = client.get("/v1/rag/search", params={"q": "ab"})
    assert res.status_code == 422


def test_harness_audit_missing_chart():
    res = client.post(
        "/v1/harness/audit",
        json={"chart_key": "0" * 64, "question": "Tell me about his finances"},
    )
    assert res.status_code == 404


def test_get_chart_missing():
    res = client.get("/v1/charts/" + "f" * 64)
    assert res.status_code == 404


def test_create_chart_rejects_naive_datetime():
    res = client.post(
        "/v1/charts",
        json={
            "name": "X",
            "datetime_iso": "1990-01-15T14:30:00",
            "lat": 28.6,
            "lon": 77.2,
        },
    )
    assert res.status_code == 422


def test_places_short_query_empty():
    res = client.get("/v1/places", params={"q": "de"})
    assert res.status_code == 200
    assert res.json()["results"] == []


def test_harness_aspects_covers_twelve_bhavas():
    res = client.get("/v1/harness/aspects")
    assert res.status_code == 200
    body = res.json()
    assert len(body["bhavas"]) == 12
    ids = {a["id"] for a in body["aspects"]}
    assert {"finance", "health", "marriage", "career", "home", "siblings", "general"} <= ids
