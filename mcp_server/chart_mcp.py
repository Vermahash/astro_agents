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

from shared.chart_tools import TOOLS, run_tool, tool_names

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
    ]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
