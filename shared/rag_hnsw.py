"""
Local RAG over classical texts with hashed embeddings + HNSW (or brute-force).

Purpose:
    Chunk books/prompts from B:\\n8n\\astro (and repo docs), embed them, store
    an HNSW index for fast retrieval. Doctrine only — never chart numbers.

Inputs:
    File roots (md/txt/extracted JSON chunks) and a query string.

Outputs:
    Ranked {text, source, score} hits. Index lives in data/rag/.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator

from shared.config import RAG_DIR, ROOT, ensure_data_dirs

logger = logging.getLogger(__name__)

RAG_DB = RAG_DIR / "chunks.db"
INDEX_BIN = RAG_DIR / "hnsw.bin"
IDS_JSON = RAG_DIR / "ids.json"
META_JSON = RAG_DIR / "meta.json"

DIM = 256
CHUNK_CHARS = 900
CHUNK_OVERLAP = 120

_TOKEN = re.compile(r"[a-z0-9]{3,}")

DEFAULT_ROOTS = (
    Path(os.getenv("ASTRO_N8N_ROOT", r"B:\n8n\astro")),
    ROOT / "docs" / "prompts",
)


def _connect() -> sqlite3.Connection:
    ensure_data_dirs()
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(RAG_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_rag_db() -> None:
    """Create chunks table."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                topic TEXT,
                text TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.commit()


def embed_text(text: str, dim: int = DIM) -> list[float]:
    """
    Deterministic hashed n-gram embedding (no model download).

    Inputs:
        text, vector size
    Outputs:
        L2-normalized float vector of length dim
    """
    vec = [0.0] * dim
    toks = _TOKEN.findall((text or "").lower())
    if not toks:
        vec[0] = 1.0
        return vec
    grams: list[str] = []
    for i, t in enumerate(toks):
        grams.append(t)
        if i + 1 < len(toks):
            grams.append(t + "_" + toks[i + 1])
    for g in grams:
        h = hashlib.md5(g.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "little") % dim
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[idx] += sign
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def _iter_text_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    skip = {".git", "node_modules", "__pycache__", "data", ".extracted", "archive"}
    # allow .extracted json chunks explicitly below
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        pdir = Path(dirpath)
        for name in filenames:
            suf = Path(name).suffix.lower()
            if suf in {".md", ".txt"}:
                yield pdir / name


def _chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out: list[str] = []
    i = 0
    while i < len(text):
        piece = text[i : i + size].strip()
        if piece:
            out.append(piece)
        i += size - overlap
    return out


def _topic_for(text: str) -> str:
    t = text.lower()
    if "sub-lord" in t or "cuspal" in t or " krishnamurti" in t or " kp " in t:
        return "kp"
    if "ashtakavarga" in t or " sav " in t:
        return "ashtakavarga"
    if "nadi" in t:
        return "nadi"
    if "navamsa" in t or "d10" in t or "hora" in t:
        return "varga"
    if "dasha" in t or "vimshottari" in t:
        return "dasha"
    if "bhrigu" in t or "bnn" in t:
        return "bnn"
    if "bphs" in t or "parashar" in t:
        return "bphs"
    return "general"


def _load_extracted_json(path: Path) -> Iterable[tuple[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    rows: list[tuple[str, str]] = []
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("chunk") or "")
                if text.strip():
                    src = f"{path}#p{item.get('page', i)}"
                    rows.append((src, text))
    return rows


def collect_documents(roots: list[Path] | None = None) -> list[tuple[str, str]]:
    """Return (source, text) pairs from roots + known extracted chunk JSON."""
    docs: list[tuple[str, str]] = []
    used = [Path(r) for r in (roots or list(DEFAULT_ROOTS))]
    for root in used:
        if not root.exists():
            logger.info("rag skip missing root %s", root)
            continue
        for fp in _iter_text_files(root):
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            docs.append((str(fp), raw))
        extracted = root / "kp-calculator" / ".extracted" / "kp_book_chunks.json"
        if extracted.exists():
            docs.extend(_load_extracted_json(extracted))
    extra = Path(os.getenv("ASTRO_N8N_ROOT", r"B:\n8n\astro")) / "kp-calculator" / ".extracted" / "kp_book_chunks.json"
    if extra.exists() and extra not in {Path(s) for s, _ in docs}:
        docs.extend(_load_extracted_json(extra))
    return docs


def build_index(roots: list[Path] | None = None) -> dict[str, Any]:
    """
    Chunk corpus, store SQLite rows, write HNSW (or numpy fallback) index.

    Returns:
        {chunks, roots, backend}
    """
    init_rag_db()
    docs = collect_documents(roots)
    inserted = 0
    with _connect() as conn:
        conn.execute("DELETE FROM chunks")
        for source, raw in docs:
            for piece in _chunk_text(raw):
                digest = hashlib.sha1(f"{source}\n{piece}".encode("utf-8")).hexdigest()
                try:
                    conn.execute(
                        "INSERT INTO chunks(source, topic, text, hash) VALUES (?,?,?,?)",
                        (source, _topic_for(piece), piece, digest),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue
        conn.commit()
        rows = list(conn.execute("SELECT id, text FROM chunks ORDER BY id"))

    ids = [int(r["id"]) for r in rows]
    vectors = [embed_text(r["text"]) for r in rows]
    backend = _write_index(ids, vectors)
    meta = {"chunks": len(ids), "dim": DIM, "backend": backend, "roots": [str(r) for r in (roots or DEFAULT_ROOTS)]}
    META_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    IDS_JSON.write_text(json.dumps(ids), encoding="utf-8")
    logger.info("rag index built chunks=%s backend=%s", len(ids), backend)
    return meta


def _write_index(ids: list[int], vectors: list[list[float]]) -> str:
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"ids": ids, "vectors": vectors}
    (RAG_DIR / "brute.json").write_text(json.dumps(payload), encoding="utf-8")
    try:
        import hnswlib  # type: ignore

        index = hnswlib.Index(space="cosine", dim=DIM)
        index.init_index(max_elements=max(len(vectors), 8), ef_construction=100, M=16)
        if vectors:
            index.add_items(vectors, ids)
        index.set_ef(64)
        index.save_index(str(INDEX_BIN))
        return "hnswlib"
    except Exception as exc:
        logger.info("hnswlib unavailable (%s); using brute-force cosine", exc)
        if INDEX_BIN.exists():
            INDEX_BIN.unlink()
        return "brute"


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _ensure_index() -> dict[str, Any] | None:
    if META_JSON.exists() and RAG_DB.exists():
        return json.loads(META_JSON.read_text(encoding="utf-8"))
    return None


def search_books(query: str, k: int = 5) -> dict[str, Any]:
    """
    Retrieve top-k doctrine chunks for a question.

    Returns:
        {ok, backend, hits: [{id, source, topic, score, text}]}
    """
    q = (query or "").strip()
    if len(q) < 3:
        return {"ok": False, "error": "query too short", "hits": []}
    if not _ensure_index():
        build_index()
    qv = embed_text(q)
    k = min(max(k, 1), 12)
    hits: list[dict[str, Any]] = []
    backend = "brute"
    meta = json.loads(META_JSON.read_text(encoding="utf-8")) if META_JSON.exists() else {}
    if INDEX_BIN.exists():
        try:
            import hnswlib  # type: ignore

            index = hnswlib.Index(space="cosine", dim=DIM)
            index.load_index(str(INDEX_BIN))
            count = int(index.get_current_count())
            if count <= 0:
                raise RuntimeError("empty hnsw index")
            labels, distances = index.knn_query([qv], k=min(k, count))
            backend = "hnswlib"
            pair = list(zip(labels[0].tolist(), distances[0].tolist()))
            with _connect() as conn:
                for cid, dist in pair:
                    row = conn.execute("SELECT id, source, topic, text FROM chunks WHERE id=?", (int(cid),)).fetchone()
                    if not row:
                        continue
                    hits.append(
                        {
                            "id": int(row["id"]),
                            "source": row["source"],
                            "topic": row["topic"],
                            "score": round(1.0 - float(dist), 4),
                            "text": row["text"][:1200],
                        }
                    )
            return {"ok": True, "backend": backend, "hits": hits, "chunks": meta.get("chunks")}
        except Exception as exc:
            logger.info("hnsw query failed, brute fallback: %s", exc)

    brute_path = RAG_DIR / "brute.json"
    if not brute_path.exists():
        return {"ok": False, "error": "no rag index; call build_index first", "hits": []}
    payload = json.loads(brute_path.read_text(encoding="utf-8"))
    scored: list[tuple[float, int]] = []
    for cid, vec in zip(payload.get("ids") or [], payload.get("vectors") or []):
        scored.append((_cosine(qv, vec), int(cid)))
    scored.sort(reverse=True)
    with _connect() as conn:
        for score, cid in scored[:k]:
            row = conn.execute("SELECT id, source, topic, text FROM chunks WHERE id=?", (cid,)).fetchone()
            if not row:
                continue
            hits.append(
                {
                    "id": int(row["id"]),
                    "source": row["source"],
                    "topic": row["topic"],
                    "score": round(float(score), 4),
                    "text": row["text"][:1200],
                }
            )
    return {"ok": True, "backend": backend, "hits": hits, "chunks": meta.get("chunks")}
