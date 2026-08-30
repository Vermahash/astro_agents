"""
Tests for SQLite chart field store, tool registry, ask agent, MCP catalog.

Purpose:
    Verify selective field reads and tool/agent wiring without live NVIDIA calls.

Inputs:
    Synthetic chart docs in tmp_path; mocked LLM for agent loop.

Outputs:
    pytest pass/fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import chart_store
from shared.ask_agent import run_tool_agent
from shared.chart_tools import run_tool, tool_names
from shared.pipeline_trace import PipelineTrace


@pytest.fixture()
def store_dir(tmp_path, monkeypatch):
    db_dir = tmp_path / "sqlite"
    db_dir.mkdir()
    db_path = db_dir / "charts.db"
    monkeypatch.setattr(chart_store, "DB_PATH", db_path)
    monkeypatch.setattr(chart_store, "SQLITE_DIR", db_dir)
    chart_store.init_db()
    return db_path


def _sample_doc(chart_key: str = "abc" * 20 + "0124") -> dict[str, Any]:
    return {
        "chart_key": chart_key,
        "engine_version": "test",
        "meta": {
            "name": "Sample",
            "datetime_iso": "1990-01-15T14:30:00+05:30",
            "lat": 28.6,
            "lon": 77.2,
            "gender": "Male",
            "lagna": "Taurus",
            "moon_nakshatra": "Rohini",
        },
        "structured_payload": {
            "natal_core": {"lagna": "Taurus"},
            "cusps": {"1": {"sign": "Taurus", "sub": "Saturn"}, "7": {"sign": "Scorpio"}},
            "planet_star_sub_lords": {"Moon": {"star": "Moon", "sub": "Venus"}},
            "kp_prediction": {"note": "sample"},
            "special_yogas": [],
        },
    }


def test_store_round_trip(store_dir):
    doc = _sample_doc()
    chart_store.upsert_chart_document(doc)
    assert chart_store.chart_exists(doc["chart_key"])
    meta = chart_store.get_meta(doc["chart_key"])
    assert meta["name"] == "Sample"
    fields = chart_store.list_fields(doc["chart_key"])
    names = {f["field"] for f in fields}
    assert "cusps" in names
    assert "natal_core" in names
    slice_ = chart_store.get_fields(doc["chart_key"], ["cusps", "natal_core"])
    assert set(slice_.keys()) == {"cusps", "natal_core"}
    with pytest.raises(KeyError, match="unknown fields"):
        chart_store.get_fields(doc["chart_key"], ["not_a_real_field"])


def test_tools_slice_only_requested(store_dir):
    doc = _sample_doc("key_tools_test_0001")
    chart_store.upsert_chart_document(doc)
    out = run_tool(
        "get_chart_slice",
        {"chart_key": doc["chart_key"], "fields": ["cusps", "kp_prediction"]},
    )
    assert out["ok"] is True
    data = out["result"]["data"]
    assert set(data.keys()) == {"cusps", "kp_prediction"}
    assert "natal_core" not in data


def test_tools_unknown_field_error(store_dir):
    doc = _sample_doc("key_tools_test_0002")
    chart_store.upsert_chart_document(doc)
    out = run_tool(
        "get_chart_slice",
        {"chart_key": doc["chart_key"], "fields": ["missing_field_xyz"]},
    )
    assert out["ok"] is False
    assert "unknown fields" in out["error"]


def test_get_cusp_and_planet(store_dir):
    doc = _sample_doc("key_tools_test_0003")
    chart_store.upsert_chart_document(doc)
    cusp = run_tool("get_cusp", {"chart_key": doc["chart_key"], "house": 7})
    assert cusp["ok"] is True
    assert cusp["result"]["cusp"]["sign"] == "Scorpio"
    planet = run_tool("get_planet", {"chart_key": doc["chart_key"], "planet": "Moon"})
    assert planet["ok"] is True
    assert planet["result"]["data"]["star"] == "Moon"


def test_mcp_catalog_parity():
    from mcp_server.chart_mcp import mcp_exposed_tool_names, registry_tool_names

    assert sorted(registry_tool_names()) == sorted(tool_names())
    assert sorted(mcp_exposed_tool_names()) == sorted(tool_names())


def test_ask_agent_mocked_tool_loop(store_dir):
    doc = _sample_doc("key_agent_loop_0001")
    chart_store.upsert_chart_document(doc)
    chart_key = doc["chart_key"]

    calls = {"n": 0}

    def fake_chat_messages(*, messages, tools=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "get_chart_slice",
                        "arguments": {
                            "chart_key": chart_key,
                            "fields": ["cusps", "kp_prediction"],
                        },
                    }
                ],
                "model": "mock-model",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "finish_reason": "tool_calls",
                "content_source": "content",
                "assistant_message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "get_chart_slice",
                                "arguments": json.dumps(
                                    {
                                        "chart_key": chart_key,
                                        "fields": ["cusps", "kp_prediction"],
                                    }
                                ),
                            },
                        }
                    ],
                },
            }
        return {
            "content": "KP verdict: sample answer from tools.",
            "tool_calls": [],
            "model": "mock-model",
            "prompt_tokens": 20,
            "completion_tokens": 15,
            "finish_reason": "stop",
            "content_source": "content",
            "assistant_message": {
                "role": "assistant",
                "content": "KP verdict: sample answer from tools.",
                "tool_calls": None,
            },
        }

    tr = PipelineTrace(trace_id="testtrace", kind="ask")
    with patch("shared.ask_agent.chat_messages", side_effect=fake_chat_messages):
        # prevent ensure_chart_in_store from importing real JSON cache
        with patch("shared.ask_agent.ensure_chart_in_store", return_value=True):
            out = run_tool_agent(
                chart_key=chart_key,
                question="Is marriage promised?",
                system_prompt="You are a KP tester.",
                max_tokens=500,
                tr=tr,
            )

    assert out["mode"] == "tools"
    assert "sample answer" in out["answer"]
    assert any(t["name"] == "get_chart_slice" and t["ok"] for t in out["tools_used"])
