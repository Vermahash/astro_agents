"""
Build a Graphify-compatible graph.json of Python module import links.

Purpose:
    Map how api / shared / mcp_server / tests / engine files import each other
    without requiring the graphify package.

Outputs:
    graphify-out/graph.json (node-link) and GRAPH_REPORT.md
"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphify-out"
SCAN = ("api", "shared", "mcp_server", "tests", "scripts")


def _module_id(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return "mod_" + "_".join(rel.parts)


def _iter_py() -> list[Path]:
    files: list[Path] = []
    for folder in SCAN:
        base = ROOT / folder
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            files.append(p)
    # engine entry points only (vendor file is huge)
    for name in ("astro_kp.py", "yoga_engine.py", "kp_logic.py", "kp_master_rules.py"):
        fp = ROOT / "engine" / name
        if fp.exists():
            files.append(fp)
    return files


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
    return names


def main() -> None:
    files = _iter_py()
    nodes = []
    edges = []
    local_tops = {"api", "shared", "mcp_server", "tests", "scripts", "engine"}
    degree: dict[str, int] = defaultdict(int)
    for fp in files:
        nid = _module_id(fp)
        nodes.append(
            {
                "id": nid,
                "label": str(fp.relative_to(ROOT)).replace("\\", "/"),
                "file_type": "code",
                "source_file": str(fp.relative_to(ROOT)).replace("\\", "/"),
            }
        )
        for imp in _imports(fp):
            if imp not in local_tops:
                continue
            # edge to package, plus to matching files
            for other in files:
                rel = other.relative_to(ROOT)
                if rel.parts[0] == imp or (imp == "engine" and rel.parts[0] == "engine"):
                    tid = _module_id(other)
                    if tid == nid:
                        continue
                    # only link to package __init__ or same first-level use: shared.X -> shared/X.py
                    if len(rel.parts) >= 2 and rel.parts[0] == imp:
                        # keep all files in that package as a coarse link would explode;
                        # link only if imported module stem matches filename
                        pass
            # finer: reconstruct shared.foo -> shared/foo.py
        text = fp.read_text(encoding="utf-8", errors="replace")
        for other in files:
            if other == fp:
                continue
            rel = other.relative_to(ROOT)
            if rel.suffix != ".py":
                continue
            # shared.ask_service imported from api.app
            mod_path = ".".join(rel.with_suffix("").parts)
            pkg = rel.parts[0]
            stem = rel.stem
            needle = f"{pkg}.{stem}" if stem != "__init__" else pkg
            if needle in text or f"from {pkg} import {stem}" in text:
                tid = _module_id(other)
                edges.append(
                    {
                        "source": nid,
                        "target": tid,
                        "relation": "imports",
                        "confidence": "EXTRACTED",
                        "confidence_score": 1.0,
                        "source_file": str(fp.relative_to(ROOT)).replace("\\", "/"),
                    }
                )
                degree[nid] += 1
                degree[tid] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    graph = {
        "directed": True,
        "multigraph": False,
        "graph": {"name": "astro_agents module links"},
        "nodes": nodes,
        "links": [
            {"source": e["source"], "target": e["target"], "relation": e["relation"], "confidence": e["confidence"]}
            for e in edges
        ],
    }
    (OUT / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    gods = sorted(degree.items(), key=lambda kv: kv[1], reverse=True)[:12]
    id_to_label = {n["id"]: n["label"] for n in nodes}
    lines = [
        "# GRAPH_REPORT",
        "",
        f"Nodes: {len(nodes)}  Edges: {len(edges)}",
        "",
        "## God Nodes",
        "",
    ]
    for nid, d in gods:
        lines.append(f"- {id_to_label.get(nid, nid)} (degree {d})")
    lines += ["", "## Surprising Connections", "", "- Ask path: `api/app.py` → `shared/ask_service.py` → `shared/harness_pipeline.py` → specialists + RAG.", ""]
    (OUT / "GRAPH_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT / 'graph.json'} nodes={len(nodes)} edges={len(edges)}")


if __name__ == "__main__":
    main()
