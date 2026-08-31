"""
Classical-law lookup via Wikipedia / Wikisource (doctrine only).

Purpose:
    Let the Brain interpret the *meaning* of a named yoga, house formula, or
    KP rule. Never returns chart numbers; never replaces the Python packet.

Inputs:
    Query string (yoga name, "2nd house dhana", "cuspal sub lord", …).

Outputs:
    {ok, source, title, snippet, url} list (capped).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_UA = "astro-agents-harness/1.0 (classical-astrology-doctrine)"
_ALLOWED_HINT = "jyotisha OR vedic astrology OR BPHS OR Krishnamurti OR nadi OR ashtakavarga"


def _get(url: str, timeout: float = 8.0) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except Exception as exc:
        logger.info("web_law fetch failed: %s", exc)
        return None


def search_classical_law(query: str, limit: int = 3) -> dict[str, Any]:
    """
    Search Wikipedia for a classical astrology law / yoga / house formula.

    Returns:
        {ok, query, hits: [{title, snippet, url}]}
    """
    q = (query or "").strip()
    if len(q) < 3:
        return {"ok": False, "error": "query too short", "hits": []}
    search = f"{q} {_ALLOWED_HINT}"
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": search,
            "srlimit": min(max(limit, 1), 5),
            "format": "json",
        }
    )
    data = _get(f"https://en.wikipedia.org/w/api.php?{params}")
    hits: list[dict[str, str]] = []
    if isinstance(data, dict):
        for row in (data.get("query") or {}).get("search") or []:
            title = str(row.get("title") or "")
            snippet = str(row.get("snippet") or "")
            snippet = (
                snippet.replace("<span class=\"searchmatch\">", "")
                .replace("</span>", "")
                .replace("<span class='searchmatch'>", "")
            )
            if not title:
                continue
            hits.append(
                {
                    "title": title,
                    "snippet": snippet[:500],
                    "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                    "source": "wikipedia",
                }
            )
    return {"ok": True, "query": q, "hits": hits, "note": "Doctrine only — do not treat encyclopedia text as chart math."}
