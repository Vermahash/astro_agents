"""
Domain harness — maps life domains to required chart payload slices.

Purpose:
    Join one or more life aspects (all 12 BPHS bhavas + compound areas) to
    Python-computed fields. Catalog lives in shared.life_aspects (book-grounded).

Inputs:
    User question text (keyword router) or explicit domain id.

Outputs:
    {domains, domain, inventory_title, keys, specialists, checkpoints,
     nadi_combos, kp_cusps, houses, planets, book_queries, book_sources}
"""

from __future__ import annotations

import re
from typing import Any

from shared.life_aspects import ASPECTS, DOMAIN_PATTERNS, PACKET_KEYS, SPECIALISTS

DOMAINS = tuple(ASPECTS.keys())

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pat, re.I), domain) for pat, domain in DOMAIN_PATTERNS
]


def classify_domains(question: str) -> list[str]:
    """Return all matching domain ids (catalog pattern order). Empty → general."""
    q = question or ""
    hits: list[str] = []
    for pat, domain in _COMPILED:
        if domain not in ASPECTS:
            continue
        if pat.search(q) and domain not in hits:
            hits.append(domain)
    return hits or ["general"]


def classify_domain(question: str) -> str:
    """Primary domain (first match) — kept for existing tests."""
    return classify_domains(question)[0]


def _merge_unique(seqs: list[list[Any] | tuple[Any, ...]]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for seq in seqs:
        for item in seq:
            key = str(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def build_harness_plan(question: str, available_keys: set[str] | None = None) -> dict[str, Any]:
    """
    Build harness fetch plan for a question (joins multiple life aspects).

    Returns:
        domains, domain (primary), inventory_title, keys, specialists,
        checkpoints, nadi_combos, kp_cusps, houses, planets, book_queries,
        book_sources, pre_audit_prompt
    """
    domains = classify_domains(question)
    primary = domains[0]
    recs = [ASPECTS[d] for d in domains if d in ASPECTS]
    wanted = _merge_unique([list(r.get("keys") or PACKET_KEYS) for r in recs]) or list(PACKET_KEYS)
    if available_keys is not None:
        keys = [k for k in wanted if k in available_keys]
    else:
        keys = list(wanted)

    nadi: dict[str, list[int]] = {}
    for r in recs:
        nadi.update(r.get("nadi") or {})

    checkpoints: list[dict[str, Any]] = []
    seen_cp: set[str] = set()
    for d, rec in zip(domains, recs):
        for cp in rec.get("checkpoints") or []:
            cid = f"{d}:{cp['id']}"
            if cid in seen_cp:
                continue
            seen_cp.add(cid)
            row = dict(cp)
            row["domain"] = d
            checkpoints.append(row)

    titles = [r.get("title") or "DOMAIN INVENTORY" for r in recs]
    specialists = _merge_unique([list(r.get("specialists") or SPECIALISTS) for r in recs]) or list(SPECIALISTS)

    return {
        "domains": domains,
        "domain": primary,
        "inventory_title": " + ".join(titles),
        "keys": keys,
        "specialists": specialists,
        "checkpoints": checkpoints,
        "nadi_combos": nadi,
        "kp_cusps": _merge_unique([r.get("kp_cusps") or [] for r in recs]),
        "houses": _merge_unique([r.get("houses") or [] for r in recs]),
        "planets": _merge_unique([r.get("planets") or [] for r in recs]),
        "book_queries": [r.get("book_query") or "" for r in recs if r.get("book_query")],
        "book_sources": [r.get("book_source") or "" for r in recs if r.get("book_source")],
        "pre_audit_prompt": "docs/prompts/PRE_AUDIT_DIRECTIVE.md",
    }
