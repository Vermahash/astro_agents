"""
MCP stdio server exposing the shared chart tool registry.

Purpose:
    Let Cursor / external MCP clients discover and call the same deterministic
    KP chart tools used by the FastAPI ask agent (in-process).

Inputs:
    MCP JSON-RPC over stdin/stdout.

Outputs:
    Tool list + tool call results from shared.chart_tools.

Run:
    python -m mcp_server.chart_mcp
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure repo root on path when launched as script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.mcpserver import MCPServer

from shared.chart_tools import TOOLS, TOOLS_BY_NAME, run_tool, tool_names

mcp = MCPServer(
    name="astro-chart-tools",
    instructions=(
        "Deterministic KP chart field tools. Math is precomputed by the Python engine. "
        "Use list_chart_fields then get_chart_slice / get_cusp / get_planet. Never invent longitudes."
    ),
)


def _unwrap(name: str, **kwargs: Any) -> Any:
    out = run_tool(name, kwargs)
    if not out.get("ok"):
        return {"error": out.get("error"), "name": name}
    return out.get("result")


@mcp.tool(description=TOOLS[0].description)
def list_chart_fields(chart_key: str) -> Any:
    return _unwrap("list_chart_fields", chart_key=chart_key)


@mcp.tool(description=TOOLS[1].description)
def get_chart_meta(chart_key: str) -> Any:
    return _unwrap("get_chart_meta", chart_key=chart_key)


@mcp.tool(description=TOOLS[2].description)
def get_chart_slice(chart_key: str, fields: list[str]) -> Any:
    return _unwrap("get_chart_slice", chart_key=chart_key, fields=fields)


@mcp.tool(description=TOOLS[3].description)
def get_cusp(chart_key: str, house: int) -> Any:
    return _unwrap("get_cusp", chart_key=chart_key, house=house)


@mcp.tool(description=TOOLS[4].description)
def get_planet(chart_key: str, planet: str) -> Any:
    return _unwrap("get_planet", chart_key=chart_key, planet=planet)


@mcp.tool(description=TOOLS[5].description)
def search_places(q: str, limit: int = 10) -> Any:
    return _unwrap("search_places", q=q, limit=limit)


@mcp.tool(description=TOOLS_BY_NAME["get_harness_plan"].description)
def get_harness_plan(question: str) -> Any:
    return _unwrap("get_harness_plan", question=question)


@mcp.tool(description=TOOLS_BY_NAME["search_books"].description)
def search_books(q: str, k: int = 5) -> Any:
    return _unwrap("search_books", q=q, k=k)


@mcp.tool(description=TOOLS_BY_NAME["search_classical_law"].description)
def search_classical_law(q: str, limit: int = 3) -> Any:
    return _unwrap("search_classical_law", q=q, limit=limit)


@mcp.tool(description=TOOLS_BY_NAME["run_chart_query"].description)
def run_chart_query(
    chart_key: str,
    op: str,
    house: int | None = None,
    planet: str | None = None,
    division: int | None = None,
    houses: list[int] | None = None,
) -> Any:
    args: dict[str, Any] = {"chart_key": chart_key, "op": op}
    if house is not None:
        args["house"] = house
    if planet is not None:
        args["planet"] = planet
    if division is not None:
        args["division"] = division
    if houses is not None:
        args["houses"] = houses
    return _unwrap("run_chart_query", **args)


def registry_tool_names() -> list[str]:
    """Names from the shared registry (for catalog parity tests)."""
    return tool_names()


def mcp_exposed_tool_names() -> list[str]:
    """Names registered on this MCP server."""
    return [
        "list_chart_fields",
        "get_chart_meta",
        "get_chart_slice",
        "get_cusp",
        "get_planet",
        "search_places",
        "get_harness_plan",
        "search_books",
        "search_classical_law",
        "run_chart_query",
    ]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
