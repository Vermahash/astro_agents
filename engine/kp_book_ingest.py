from __future__ import annotations

"""
Ingest KP textbook PDF into structured rule chunks + formula references.

Outputs (in `.extracted/`):
- `kp_book_chunks.json`      : page-scoped text chunks with headings/topics
- `kp_formula_candidates.json`: likely formula/rule lines with page refs
- `kp_book_index.json`       : lightweight index used by runtime loaders
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Iterable

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "docs" / "books" / "Astrology-for-Beginners-Vol-1-6.pdf"
OUT_DIR = ROOT / ".extracted"


@dataclass
class Chunk:
    page: int
    heading: str
    topic: str
    text: str


def _normalize(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _topic_for(text: str) -> str:
    t = text.lower()
    if "sub-lord" in t or "sub lord" in t:
        return "sub_lord"
    if "ruling planet" in t:
        return "ruling_planets"
    if "dasa" in t or "dasha" in t:
        return "dasha"
    if "nakshatra" in t:
        return "nakshatra"
    if "cusp" in t or "placidus" in t:
        return "cusps"
    if "rahu" in t or "ketu" in t:
        return "nodes"
    return "general"


def _extract_chunks(text: str, page_no: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    parts = re.split(r"\n(?=[A-Z][A-Z0-9 \-]{5,}$)", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        heading = lines[0].strip() if lines else "UNTITLED"
        topic = _topic_for(part)
        chunks.append(Chunk(page=page_no, heading=heading, topic=topic, text=part))
    if not chunks and text:
        chunks.append(Chunk(page=page_no, heading="PAGE_TEXT", topic=_topic_for(text), text=text))
    return chunks


FORMULA_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d+\s*°\s*\d+'\s*\d+\""),
    re.compile(r"\b\d+(?:\.\d+)?\s*[/x*+\-]\s*\d+(?:\.\d+)?"),
    re.compile(r"\b(start|end|span|interval|half-open|inclusive|exclusive)\b", re.I),
    re.compile(r"\b(vimshottari|nakshatra|sub-?lord|sub-?sub)\b", re.I),
)


def _iter_formula_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(p.search(s) for p in FORMULA_PATTERNS):
            yield s


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing PDF: {PDF_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(PDF_PATH))

    chunks: list[dict] = []
    formulas: list[dict] = []

    for idx, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = _normalize(raw)
        if not text:
            continue

        for c in _extract_chunks(text, idx):
            chunks.append(asdict(c))

        for line in _iter_formula_lines(text):
            formulas.append({"page": idx, "line": line, "topic": _topic_for(line)})

    chunk_path = OUT_DIR / "kp_book_chunks.json"
    formula_path = OUT_DIR / "kp_formula_candidates.json"
    index_path = OUT_DIR / "kp_book_index.json"

    chunk_path.write_text(json.dumps(chunks, ensure_ascii=True, indent=2), encoding="utf-8")
    formula_path.write_text(json.dumps(formulas, ensure_ascii=True, indent=2), encoding="utf-8")
    index = {
        "pdf": str(PDF_PATH.name),
        "chunks_file": chunk_path.name,
        "formula_file": formula_path.name,
        "chunk_count": len(chunks),
        "formula_count": len(formulas),
    }
    index_path.write_text(json.dumps(index, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Extracted {len(chunks)} chunks and {len(formulas)} formula lines.")
    print(f"Wrote: {chunk_path}")
    print(f"Wrote: {formula_path}")
    print(f"Wrote: {index_path}")


if __name__ == "__main__":
    main()

