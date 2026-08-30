"""
Pipeline tracer — LangGraph-style step visibility in the terminal + log file.

Purpose:
    Print real-time nodes for chart/ask flows so you can see where the packet
    is, how long each step took, and where agents fail while debugging.

Inputs:
    Step name, optional detail dict, success/error.

Outputs:
    Lines on stdout (API terminal) and append-only file data/logs/pipeline.log
    plus a structured steps list for API responses.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from shared.config import ensure_data_dirs

logger = logging.getLogger("pipeline")

_LOG_FILE: Path | None = None


def _log_path() -> Path:
    global _LOG_FILE
    if _LOG_FILE is None:
        ensure_data_dirs()
        root = Path(__file__).resolve().parents[1]
        log_dir = root / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _LOG_FILE = log_dir / "pipeline.log"
    return _LOG_FILE


def _emit(line: str) -> None:
    """Write one line to stdout, logger, and pipeline.log (always flushed)."""
    print(line, flush=True, file=sys.stdout)
    logger.info("%s", line)
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
    except OSError:
        pass


@dataclass
class PipelineTrace:
    """One request's step timeline (chart compute or ask)."""

    trace_id: str
    kind: str
    started: float = field(default_factory=time.perf_counter)
    steps: list[dict[str, Any]] = field(default_factory=list)

    def mark(
        self,
        node: str,
        *,
        status: str = "ok",
        detail: dict[str, Any] | None = None,
        ms: float | None = None,
    ) -> None:
        row = {
            "node": node,
            "status": status,
            "ms": round(ms, 1) if ms is not None else None,
            "detail": detail or {},
        }
        self.steps.append(row)
        icon = "OK" if status == "ok" else (".." if status == "start" else "FAIL")
        ms_s = f"{ms:.0f}ms" if ms is not None else "-"
        extra = ""
        if detail:
            bits = []
            for k, v in list(detail.items())[:6]:
                bits.append(f"{k}={v}")
            extra = " | " + ", ".join(bits)
        line = f"[trace:{self.trace_id[:8]}] [{self.kind}] {icon} {node} ({ms_s}){extra}"
        _emit(line)

    def summary(self) -> dict[str, Any]:
        total = (time.perf_counter() - self.started) * 1000
        return {
            "trace_id": self.trace_id,
            "kind": self.kind,
            "total_ms": round(total, 1),
            "steps": self.steps,
        }


@contextmanager
def pipeline(kind: str) -> Iterator[PipelineTrace]:
    """Context manager that opens/closes a traced pipeline run."""
    tr = PipelineTrace(trace_id=uuid.uuid4().hex, kind=kind)
    _emit(f"\n======== PIPELINE START [{kind}] id={tr.trace_id[:8]} ========")
    tr.mark("pipeline.start", status="start")
    try:
        yield tr
        total = (time.perf_counter() - tr.started) * 1000
        tr.mark("pipeline.end", status="ok", ms=total)
        _emit(f"======== PIPELINE END   [{kind}] id={tr.trace_id[:8]} total={total:.0f}ms ========\n")
    except Exception as exc:
        total = (time.perf_counter() - tr.started) * 1000
        tr.mark(
            "pipeline.error",
            status="error",
            detail={"error": type(exc).__name__, "msg": str(exc)[:200]},
            ms=total,
        )
        _emit(
            f"======== PIPELINE FAIL  [{kind}] id={tr.trace_id[:8]} "
            f"error={type(exc).__name__}: {exc} ========\n"
        )
        raise


@contextmanager
def step(tr: PipelineTrace, node: str, **detail: Any) -> Iterator[None]:
    """Time a single node inside a pipeline."""
    t0 = time.perf_counter()
    tr.mark(node, status="start", detail=detail or None)
    try:
        yield
        tr.mark(node, status="ok", ms=(time.perf_counter() - t0) * 1000, detail=detail or None)
    except Exception as exc:
        tr.mark(
            node,
            status="error",
            ms=(time.perf_counter() - t0) * 1000,
            detail={**(detail or {}), "error": type(exc).__name__, "msg": str(exc)[:200]},
        )
        raise
