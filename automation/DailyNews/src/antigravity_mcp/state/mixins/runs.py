from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentReport, PipelineRun
from antigravity_mcp.state.base import _DBProviderBase
from antigravity_mcp.state.events import utc_now_iso

try:
    from shared.llm.config import MODEL_COSTS as _SHARED_MODEL_COSTS
except ImportError:
    _SHARED_MODEL_COSTS: dict[str, tuple[float, float]] = {}

_DEFAULT_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "deepseek-chat": (0.14, 0.28),
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash-preview-04-17": (0.0, 0.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3-mini-fast": (0.3, 0.5),
}
_MODEL_COSTS = {**_DEFAULT_MODEL_COSTS, **_SHARED_MODEL_COSTS}

def _estimate_cached_response_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_cost, output_cost = _MODEL_COSTS.get(model_name, (0.25, 1.25))
    return (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000

def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, set):
        return list(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


class _RunMixin(_DBProviderBase):
    """Methods for the ``job_runs`` table."""

    def record_job_start(self, run_id: str, job_name: str, summary: dict[str, Any] | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO job_runs(
                    run_id, job_name, started_at, finished_at, status, summary_json, error_text, processed_count, published_count
                )
                VALUES (?, ?, ?, NULL, ?, ?, NULL, 0, 0)
                """,
                (run_id, job_name, utc_now_iso(), "running", json.dumps(summary or {}, ensure_ascii=False)),
            )

    def record_job_finish(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any] | None = None,
        error_text: str | None = None,
        processed_count: int = 0,
        published_count: int = 0,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE job_runs
                SET finished_at = ?, status = ?, summary_json = ?, error_text = ?, processed_count = ?, published_count = ?
                WHERE run_id = ?
                """,
                (
                    utc_now_iso(),
                    status,
                    json.dumps(summary or {}, ensure_ascii=False),
                    error_text,
                    processed_count,
                    published_count,
                    run_id,
                ),
            )

    def get_run(self, run_id: str) -> PipelineRun | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM job_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        summary = json.loads(row["summary_json"] or "{}")
        return PipelineRun(
            run_id=row["run_id"],
            job_name=row["job_name"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"] or "",
            processed_count=row["processed_count"] or 0,
            published_count=row["published_count"] or 0,
            error_text=row["error_text"] or "",
            summary=summary,
        )

    def list_runs(
        self, *, job_name: str | None = None, status: str | None = None, limit: int = 20
    ) -> list[PipelineRun]:
        query = "SELECT * FROM job_runs"
        clauses: list[str] = []
        params: list[Any] = []
        if job_name:
            clauses.append("job_name = ?")
            params.append(job_name)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            PipelineRun(
                run_id=row["run_id"],
                job_name=row["job_name"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"] or "",
                processed_count=row["processed_count"] or 0,
                published_count=row["published_count"] or 0,
                error_text=row["error_text"] or "",
                summary=json.loads(row["summary_json"] or "{}"),
            )
            for row in rows
        ]

    def get_pipeline_health(self) -> dict[str, Any]:
        """Return health metrics for pipeline runs in the last 24 hours."""
        cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        with self._connect() as connection:
            last_row = connection.execute(
                "SELECT started_at, status FROM job_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            rows_24h = connection.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM job_runs
                WHERE started_at >= ?
                GROUP BY status
                """,
                (cutoff,),
            ).fetchall()
            latency_row = connection.execute(
                """
                SELECT AVG(
                    (julianday(finished_at) - julianday(started_at)) * 86400.0
                ) AS avg_seconds
                FROM job_runs
                WHERE started_at >= ? AND finished_at IS NOT NULL AND finished_at != ''
                """,
                (cutoff,),
            ).fetchone()

        status_counts: dict[str, int] = {}
        for row in rows_24h:
            status_counts[row["status"]] = row["cnt"]

        success_count = status_counts.get("success", 0) + status_counts.get("partial", 0)
        failure_count = status_counts.get("failed", 0)
        total_runs = sum(status_counts.values())
        error_rate = (failure_count / total_runs) if total_runs > 0 else 0.0

        avg_latency = latency_row["avg_seconds"] if latency_row and latency_row["avg_seconds"] is not None else None
        if avg_latency is not None:
            avg_latency = round(avg_latency, 2)

        return {
            "last_run_at": last_row["started_at"] if last_row else None,
            "last_run_status": last_row["status"] if last_row else None,
            "success_count_24h": success_count,
            "failure_count_24h": failure_count,
            "total_runs_24h": total_runs,
            "avg_latency_seconds": avg_latency,
            "error_rate": round(error_rate, 4),
        }

    def cleanup_stale_runs(self, max_age_minutes: int = 30) -> int:
        """Mark runs stuck in 'running' status for > max_age_minutes as 'failed'.

        Call this at the start of each pipeline run to auto-clean zombie
        processes left by previous crashes (e.g. Task Scheduler killed mid-run,
        power loss, OOM). Returns the number of cleaned runs.
        """
        cutoff = (datetime.now(UTC) - timedelta(minutes=max_age_minutes)).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE job_runs
                SET status = 'failed',
                    finished_at = ?,
                    error_text = ?
                WHERE status = 'running' AND started_at < ?
                """,
                (
                    utc_now_iso(),
                    f"Stale run auto-cleaned (exceeded {max_age_minutes} min timeout)",
                    cutoff,
                ),
            )
        cleaned = cursor.rowcount
        if cleaned > 0:
            import logging

            logging.getLogger(__name__).warning(
                "Cleaned %d stale runs (>%d min)",
                cleaned,
                max_age_minutes,
            )
        return cleaned
