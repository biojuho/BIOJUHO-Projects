"""shared.telemetry.workflow_trace - Structured workflow trace collection.

Captures execution traces from LLM pipelines for future AWO-style
meta-optimization. Each trace records:
- Pipeline name and stage
- Prompt template hash (for pattern detection)
- Token usage, cost, and latency
- Success/failure status
- Model and backend used

Traces are stored in SQLite (same DB as cost tracking) for lightweight,
zero-dependency persistence.

Usage:
    from shared.telemetry.workflow_trace import WorkflowTracer

    tracer = WorkflowTracer()
    with tracer.trace("DailyNews", "category_analysis", model="gemini-2.5-flash") as t:
        result = llm_client.create(...)
        t.record(
            prompt_hash=t.hash_prompt(system_prompt),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
        )

    # Later: analyze patterns
    patterns = tracer.find_repeated_patterns(min_count=5)
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Generator

log = logging.getLogger("shared.telemetry.workflow_trace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_TRACE_DB_PATH = Path(__file__).resolve().parent / "data" / "workflow_traces.db"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


def _utc_now_sqlite() -> str:
    """Return current UTC time in SQLite-compatible format (no timezone offset)."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class TraceRecord:
    """A single workflow execution trace."""

    pipeline: str
    stage: str
    timestamp: str = field(default_factory=_utc_now_sqlite)
    prompt_hash: str = ""
    model: str = ""
    backend: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""
    metadata: str = ""  # JSON string for extra data


@dataclass
class PromptPattern:
    """A detected repeated prompt pattern."""

    prompt_hash: str
    occurrence_count: int
    total_cost_usd: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_latency_ms: float
    pipelines: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""


# ---------------------------------------------------------------------------
# Database management
# ---------------------------------------------------------------------------


def _ensure_db(db_path: Path) -> sqlite3.Connection:
    """Create the trace database and table if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline TEXT NOT NULL,
            stage TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            prompt_hash TEXT,
            model TEXT,
            backend TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            latency_ms REAL DEFAULT 0.0,
            success BOOLEAN DEFAULT 1,
            error TEXT,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traces_prompt_hash
        ON workflow_traces(prompt_hash)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traces_pipeline
        ON workflow_traces(pipeline, stage)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traces_timestamp
        ON workflow_traces(timestamp)
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Trace context manager
# ---------------------------------------------------------------------------


class TraceContext:
    """Context for recording a single trace within a `with` block."""

    def __init__(self, pipeline: str, stage: str, model: str = "") -> None:
        self.pipeline = pipeline
        self.stage = stage
        self.model = model
        self._record = TraceRecord(pipeline=pipeline, stage=stage, model=model)
        self._t0 = time.perf_counter()

    def record(
        self,
        *,
        prompt_hash: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        backend: str = "",
        success: bool = True,
        error: str = "",
        metadata: str = "",
    ) -> None:
        """Record trace data. Call this inside the `with` block."""
        self._record.prompt_hash = prompt_hash
        self._record.input_tokens = input_tokens
        self._record.output_tokens = output_tokens
        self._record.cost_usd = cost_usd
        self._record.backend = backend
        self._record.success = success
        self._record.error = error
        self._record.metadata = metadata

    def mark_failed(self, error: str) -> None:
        """Mark the trace as failed."""
        self._record.success = False
        self._record.error = error

    def finalize(self) -> TraceRecord:
        """Finalize timing and return the trace record."""
        self._record.latency_ms = (time.perf_counter() - self._t0) * 1000
        return self._record

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Create a stable hash of a prompt for pattern detection.

        Uses SHA-256 truncated to 12 chars for readability while
        maintaining collision resistance for practical purposes.
        """
        normalized = prompt.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Main tracer
# ---------------------------------------------------------------------------


class WorkflowTracer:
    """Collects and analyzes workflow execution traces.

    Designed for AWO-style meta-optimization preparation:
    1. Records every LLM call with prompt hash + metrics
    2. Detects repeated patterns (same prompt hash, high frequency)
    3. Surfaces optimization candidates for template conversion

    Usage:
        tracer = WorkflowTracer()

        # Record a trace
        with tracer.trace("DailyNews", "scoring") as t:
            result = client.create(...)
            t.record(
                prompt_hash=t.hash_prompt(system_prompt),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
            )

        # Find patterns
        patterns = tracer.find_repeated_patterns(min_count=5)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _TRACE_DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._buffer: list[TraceRecord] = []
        self._buffer_size = 20  # flush every N records
        self._lock = threading.Lock()
        atexit.register(self.close)

    def _get_conn(self) -> sqlite3.Connection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = _ensure_db(self._db_path)
        return self._conn

    @contextmanager
    def trace(
        self,
        pipeline: str,
        stage: str,
        *,
        model: str = "",
    ) -> Generator[TraceContext, None, None]:
        """Context manager for recording a workflow trace.

        Args:
            pipeline: Pipeline name (e.g., "DailyNews", "GetDayTrends")
            stage: Stage name (e.g., "rss_collect", "scoring", "analysis")
            model: LLM model used (optional, can be set in record())
        """
        ctx = TraceContext(pipeline, stage, model)
        try:
            yield ctx
        except Exception as e:
            ctx.mark_failed(str(e))
            raise
        finally:
            record = ctx.finalize()
            with self._lock:
                self._buffer.append(record)
                needs_flush = len(self._buffer) >= self._buffer_size
            if needs_flush:
                self.flush()

    def record_direct(self, record: TraceRecord) -> None:
        """Record a trace directly without context manager."""
        with self._lock:
            self._buffer.append(record)
            needs_flush = len(self._buffer) >= self._buffer_size
        if needs_flush:
            self.flush()

    def flush(self) -> int:
        """Flush buffered traces to the database. Returns count flushed."""
        with self._lock:
            if not self._buffer:
                return 0
            # Swap buffer under lock to minimize hold time
            to_flush = list(self._buffer)
            self._buffer.clear()

        conn = self._get_conn()
        count = 0
        try:
            for rec in to_flush:
                conn.execute(
                    """INSERT INTO workflow_traces
                    (pipeline, stage, timestamp, prompt_hash, model, backend,
                     input_tokens, output_tokens, cost_usd, latency_ms,
                     success, error, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec.pipeline,
                        rec.stage,
                        rec.timestamp,
                        rec.prompt_hash,
                        rec.model,
                        rec.backend,
                        rec.input_tokens,
                        rec.output_tokens,
                        rec.cost_usd,
                        rec.latency_ms,
                        rec.success,
                        rec.error,
                        rec.metadata,
                    ),
                )
                count += 1
            conn.commit()
            log.debug("Flushed %d workflow traces to DB", count)
        except Exception as e:
            log.warning("Failed to flush %d traces: %s — re-queuing", len(to_flush), e)
            # Re-queue failed records so they aren't lost
            with self._lock:
                self._buffer = to_flush + self._buffer

        return count

    # -- Pattern analysis (AWO preparation) --------------------------------

    def find_repeated_patterns(
        self,
        *,
        min_count: int = 5,
        days: int = 7,
    ) -> list[PromptPattern]:
        """Find repeated prompt patterns across workflow traces.

        Returns patterns ordered by total cost (highest first),
        making them candidates for template conversion.
        """
        conn = self._get_conn()
        self.flush()  # ensure all buffered data is written

        try:
            cursor = conn.execute(
                """
                SELECT
                    prompt_hash,
                    COUNT(*) as cnt,
                    SUM(cost_usd) as total_cost,
                    AVG(input_tokens) as avg_in,
                    AVG(output_tokens) as avg_out,
                    AVG(latency_ms) as avg_lat,
                    GROUP_CONCAT(DISTINCT pipeline) as pipelines,
                    GROUP_CONCAT(DISTINCT stage) as stages,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM workflow_traces
                WHERE prompt_hash != ''
                  AND timestamp >= datetime('now', ?)
                GROUP BY prompt_hash
                HAVING cnt >= ?
                ORDER BY total_cost DESC
                """,
                (f"-{days} days", min_count),
            )

            patterns = []
            for row in cursor.fetchall():
                patterns.append(
                    PromptPattern(
                        prompt_hash=row[0],
                        occurrence_count=row[1],
                        total_cost_usd=round(row[2] or 0.0, 6),
                        avg_input_tokens=round(row[3] or 0, 1),
                        avg_output_tokens=round(row[4] or 0, 1),
                        avg_latency_ms=round(row[5] or 0, 1),
                        pipelines=(row[6] or "").split(","),
                        stages=(row[7] or "").split(","),
                        first_seen=row[8] or "",
                        last_seen=row[9] or "",
                    )
                )
            return patterns
        except Exception as e:
            log.warning("Pattern analysis failed: %s", e)
            return []

    def get_stage_summary(
        self,
        pipeline: str,
        *,
        days: int = 7,
    ) -> list[dict]:
        """Get per-stage cost and performance summary for a pipeline."""
        conn = self._get_conn()
        self.flush()

        try:
            cursor = conn.execute(
                """
                SELECT
                    stage,
                    COUNT(*) as calls,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures
                FROM workflow_traces
                WHERE pipeline = ?
                  AND timestamp >= datetime('now', ?)
                GROUP BY stage
                ORDER BY total_cost DESC
                """,
                (pipeline, f"-{days} days"),
            )

            return [
                {
                    "stage": row[0],
                    "calls": row[1],
                    "total_cost_usd": round(row[2] or 0.0, 6),
                    "avg_latency_ms": round(row[3] or 0, 1),
                    "failures": row[4],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            log.warning("Stage summary failed: %s", e)
            return []

    def close(self) -> None:
        """Flush remaining traces and close the database connection."""
        self.flush()
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> WorkflowTracer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
