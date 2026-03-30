"""Mixin classes for logical grouping of PipelineStateStore responsibilities.

Each mixin handles a single domain concern (SRP):
  - _RunMixin:      job_runs table CRUD
  - _ArticleMixin:  article_cache deduplication
  - _ReportMixin:   content_reports + channel_publications lifecycle
  - _CacheMixin:    llm_cache, feed_etag_cache, token usage stats
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentReport, PipelineRun
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
    "gemini-2.5-flash-lite": (0.10, 0.40),  # Free 1,000RPD, 초저비용
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


# ── Run tracking ──────────────────────────────────────────────────────────


class _RunMixin:
    """Methods for the ``job_runs`` table."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError  # provided by PipelineStateStore

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


# ── Article deduplication ─────────────────────────────────────────────────


class _ArticleMixin:
    """Methods for the ``article_cache`` table."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def has_seen_article(self, *, link: str, category: str, window_name: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM article_cache
                WHERE link = ? AND category = ? AND window_name = ?
                LIMIT 1
                """,
                (link, category, window_name),
            ).fetchone()
        return row is not None

    def prune_old_articles(self, days: int = 30) -> int:
        """Delete article_cache entries older than *days*. Returns count of removed rows."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM article_cache WHERE first_seen_at < ?", (cutoff,))
        return cursor.rowcount

    def record_article(
        self,
        *,
        link: str,
        source: str,
        category: str,
        window_name: str,
        notion_page_id: str | None,
        run_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO article_cache(
                    link, category, window_name, source, first_seen_at, notion_page_id, last_run_id
                )
                VALUES(
                    ?, ?, ?, ?,
                    COALESCE((SELECT first_seen_at FROM article_cache WHERE link = ? AND category = ? AND window_name = ?), ?),
                    ?, ?
                )
                """,
                (
                    link,
                    category,
                    window_name,
                    source,
                    link,
                    category,
                    window_name,
                    utc_now_iso(),
                    notion_page_id,
                    run_id,
                ),
            )


# ── Report lifecycle ──────────────────────────────────────────────────────


class _ReportMixin:
    """Methods for the ``content_reports`` and ``channel_publications`` tables."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def find_report_by_fingerprint(self, fingerprint: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return self._row_to_report(row) if row else None  # type: ignore[attr-defined]

    def save_report(self, report: ContentReport) -> None:
        now = utc_now_iso()
        created_at = report.created_at or now
        updated_at = now
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO content_reports(
                    report_id, category, window_name, window_start, window_end,
                    summary_json, insights_json, drafts_json, notion_page_id, asset_status,
                    approval_state, source_links_json, status, fingerprint, created_at, updated_at,
                    notebooklm_metadata_json, fact_check_score, quality_state, generation_mode, analysis_meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.category,
                    report.window_name,
                    report.window_start,
                    report.window_end,
                    json.dumps(report.summary_lines, ensure_ascii=False, default=_json_default),
                    json.dumps(report.insights, ensure_ascii=False, default=_json_default),
                    json.dumps(
                        [draft.to_dict() for draft in report.channel_drafts], ensure_ascii=False, default=_json_default
                    ),
                    report.notion_page_id,
                    report.asset_status,
                    report.approval_state,
                    json.dumps(report.source_links, ensure_ascii=False, default=_json_default),
                    report.status,
                    report.fingerprint,
                    created_at,
                    updated_at,
                    json.dumps(report.notebooklm_metadata, ensure_ascii=False, default=_json_default),
                    float(report.fact_check_score),
                    report.quality_state,
                    report.generation_mode,
                    json.dumps(report.analysis_meta, ensure_ascii=False, default=_json_default),
                ),
            )

    def get_report(self, report_id: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        return self._row_to_report(row) if row else None  # type: ignore[attr-defined]

    def list_reports(self, *, limit: int = 20, category: str | None = None) -> list[ContentReport]:
        query = "SELECT * FROM content_reports"
        params: list[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [report for report in (self._row_to_report(row) for row in rows) if report is not None]

    def get_report_governance_summary(self, *, limit: int = 100) -> dict[str, Any]:
        reports = self.list_reports(limit=limit)
        quality_counts: dict[str, int] = {}
        approval_counts: dict[str, int] = {}
        fallback_x_drafts = 0
        for report in reports:
            quality_counts[report.quality_state] = quality_counts.get(report.quality_state, 0) + 1
            approval_counts[report.approval_state] = approval_counts.get(report.approval_state, 0) + 1
            if any(draft.channel == "x" and draft.is_fallback for draft in report.channel_drafts):
                fallback_x_drafts += 1
        return {
            "reports_considered": len(reports),
            "quality_counts": quality_counts,
            "approval_counts": approval_counts,
            "fallback_x_drafts": fallback_x_drafts,
        }

    def set_report_publication(self, report_id: str, *, notion_page_id: str, status: str) -> None:
        report = self.get_report(report_id)
        if report is None:
            return
        report.notion_page_id = notion_page_id
        report.status = status
        self.save_report(report)

    def set_channel_publication(self, report_id: str, channel: str, status: str, external_url: str = "") -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO channel_publications(report_id, channel, status, external_url, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, channel, status, external_url, utc_now_iso()),
            )

    def report_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            total_reports = connection.execute("SELECT COUNT(*) FROM content_reports").fetchone()[0]
            total_runs = connection.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
            total_cached = connection.execute("SELECT COUNT(*) FROM article_cache").fetchone()[0]
        return {
            "reports": int(total_reports),
            "runs": int(total_runs),
            "cached_articles": int(total_cached),
        }

    @staticmethod
    def _row_to_report(row: sqlite3.Row | None) -> ContentReport | None:
        if row is None:
            return None
        drafts = [
            ChannelDraft(
                channel=item.get("channel", ""),
                status=item.get("status", ""),
                content=item.get("content", ""),
                external_url=item.get("external_url", ""),
                source=item.get("source", "llm"),
                is_fallback=bool(item.get("is_fallback", False)),
            )
            for item in json.loads(row["drafts_json"] or "[]")
        ]
        return ContentReport(
            report_id=row["report_id"],
            category=row["category"],
            window_name=row["window_name"],
            window_start=row["window_start"],
            window_end=row["window_end"],
            summary_lines=json.loads(row["summary_json"] or "[]"),
            insights=json.loads(row["insights_json"] or "[]"),
            channel_drafts=drafts,
            notion_page_id=row["notion_page_id"] or "",
            asset_status=row["asset_status"],
            approval_state=row["approval_state"],
            source_links=json.loads(row["source_links_json"] or "[]"),
            status=row["status"],
            fingerprint=row["fingerprint"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            notebooklm_metadata=json.loads(row["notebooklm_metadata_json"] or "{}"),
            fact_check_score=float(row["fact_check_score"] or 0.0),
            quality_state=row["quality_state"] or "ok",
            generation_mode=row["generation_mode"] or "",
            analysis_meta=json.loads(row["analysis_meta_json"] or "{}"),
        )


# ── LLM / Feed caching ───────────────────────────────────────────────────


class _CacheMixin:
    """Methods for ``llm_cache``, ``feed_etag_cache``, and token usage stats."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def get_cached_llm_response(self, prompt_hash: str) -> str | None:
        """Return cached LLM response text or None if cache miss / expired."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT response_text
                FROM llm_cache
                WHERE prompt_hash = ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (prompt_hash, now),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE llm_cache SET cache_hits = COALESCE(cache_hits, 0) + 1 WHERE prompt_hash = ?",
                (prompt_hash,),
            )
        return row["response_text"]

    def increment_llm_cache_hits(self, prompt_hash: str) -> None:
        """Increment cache_hits counter for a prompt_hash (e.g. when L1 in-memory cache is hit)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE llm_cache SET cache_hits = COALESCE(cache_hits, 0) + 1 WHERE prompt_hash = ?",
                (prompt_hash,),
            )

    def put_llm_cache(
        self,
        prompt_hash: str,
        response_text: str,
        model_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        ttl_hours: int = 24,
    ) -> None:
        """Store an LLM response in cache with optional TTL."""
        now = datetime.now(UTC)
        expires = (now + timedelta(hours=ttl_hours)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO llm_cache
                   (prompt_hash, response_text, model_name, input_tokens, output_tokens, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (prompt_hash, response_text, model_name, input_tokens, output_tokens, now.isoformat(), expires),
            )

    def prune_llm_cache(self) -> int:
        """Remove expired cache entries. Returns count of deleted rows."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM llm_cache WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,))
        return cursor.rowcount

    def get_feed_etag(self, url: str) -> tuple[str | None, str | None]:
        """Return (etag, last_modified) for a cached feed URL."""
        with self._connect() as conn:
            row = conn.execute("SELECT etag, last_modified FROM feed_etag_cache WHERE url = ?", (url,)).fetchone()
        if row:
            return row["etag"], row["last_modified"]
        return None, None

    def put_feed_etag(self, url: str, etag: str | None, last_modified: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO feed_etag_cache (url, etag, last_modified, last_fetched_at)
                   VALUES (?, ?, ?, ?)""",
                (url, etag, last_modified, utc_now_iso()),
            )

    def get_token_usage_stats(self, hours: int = 24) -> dict:
        """Aggregate token usage from LLM cache entries within the given time window."""
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT model_name, input_tokens, output_tokens, COALESCE(cache_hits, 0) AS cache_hits
                FROM llm_cache
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchall()
        total_input = sum(int(row["input_tokens"] or 0) for row in rows)
        total_output = sum(int(row["output_tokens"] or 0) for row in rows)
        cache_hits = sum(int(row["cache_hits"] or 0) for row in rows)
        estimated_cost = 0.0
        avoided_cost = 0.0
        cost_by_model: dict[str, float] = {}
        for row in rows:
            model_name = row["model_name"] or "unknown"
            row_cost = _estimate_cached_response_cost(
                model_name,
                int(row["input_tokens"] or 0),
                int(row["output_tokens"] or 0),
            )
            estimated_cost += row_cost
            avoided_cost += row_cost * int(row["cache_hits"] or 0)
            cost_by_model[model_name] = cost_by_model.get(model_name, 0.0) + row_cost
        return {
            "period_hours": hours,
            "call_count": len(rows),
            "cache_hit_count": cache_hits,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost_usd": round(estimated_cost, 6),
            "estimated_cost_avoided_usd": round(avoided_cost, 6),
            "cost_by_model": {model: round(cost, 6) for model, cost in sorted(cost_by_model.items())},
        }


# ── X daily post counter ─────────────────────────────────────────────────


class _XPostMixin:
    """Persistent daily post counter for X (Twitter) publishing."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def get_x_post_count(self, post_date: str) -> int:
        """Return the number of posts made on the given date (YYYY-MM-DD)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT post_count FROM x_daily_posts WHERE post_date = ?",
                (post_date,),
            ).fetchone()
        return int(row["post_count"]) if row else 0

    def increment_x_post_count(self, post_date: str) -> int:
        """Increment and return the post count for the given date."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO x_daily_posts (post_date, post_count)
                VALUES (?, 1)
                ON CONFLICT(post_date) DO UPDATE SET post_count = post_count + 1
                """,
                (post_date,),
            )
            row = conn.execute(
                "SELECT post_count FROM x_daily_posts WHERE post_date = ?",
                (post_date,),
            ).fetchone()
        return int(row["post_count"]) if row else 1

    def prune_old_x_posts(self, keep_days: int = 7) -> int:
        """Remove post count entries older than *keep_days*."""
        cutoff = (datetime.now(UTC) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM x_daily_posts WHERE post_date < ?", (cutoff,))
        return cursor.rowcount


# ── Topic timeline tracking ───────────────────────────────────────────────


class _TopicMixin:
    """Persistent topic timeline for continuity tracking across briefs."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def upsert_topic(
        self,
        *,
        topic_id: str,
        topic_label: str,
        category: str,
        report_id: str,
        embedding: list[float] | None = None,
    ) -> None:
        """Insert a new topic or update an existing one with a new occurrence."""
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT report_ids_json, occurrence_count FROM topic_timeline WHERE topic_id = ?",
                (topic_id,),
            ).fetchone()

            if existing:
                report_ids = json.loads(existing["report_ids_json"] or "[]")
                if report_id not in report_ids:
                    report_ids.append(report_id)
                conn.execute(
                    """
                    UPDATE topic_timeline
                    SET last_seen_at = ?, occurrence_count = occurrence_count + 1,
                        report_ids_json = ?
                    WHERE topic_id = ?
                    """,
                    (now, json.dumps(report_ids, ensure_ascii=False), topic_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO topic_timeline
                        (topic_id, topic_label, category, first_seen_at, last_seen_at,
                         occurrence_count, report_ids_json, embedding_json)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_label,
                        category,
                        now,
                        now,
                        json.dumps([report_id], ensure_ascii=False),
                        json.dumps(embedding, ensure_ascii=False) if embedding else None,
                    ),
                )

    def get_recent_topics(self, category: str, *, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent topics for a category, sorted by last_seen_at desc."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT topic_id, topic_label, category, first_seen_at, last_seen_at,
                       occurrence_count, report_ids_json
                FROM topic_timeline
                WHERE category = ? AND last_seen_at >= ?
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (category, cutoff, limit),
            ).fetchall()
        return [
            {
                "topic_id": row["topic_id"],
                "topic_label": row["topic_label"],
                "category": row["category"],
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "occurrence_count": row["occurrence_count"],
                "report_ids": json.loads(row["report_ids_json"] or "[]"),
            }
            for row in rows
        ]

    def find_continuing_topics(self, category: str, current_titles: list[str]) -> list[dict[str, Any]]:
        """Find topics from previous briefs that appear to continue in current content.

        Uses simple keyword overlap matching (embedding-based matching is done
        at the adapter level when available).
        """
        recent = self.get_recent_topics(category, days=3)
        continuing: list[dict[str, Any]] = []
        current_words = set()
        for title in current_titles:
            current_words.update(w.lower() for w in title.split() if len(w) > 2)

        for topic in recent:
            topic_words = set(w.lower() for w in topic["topic_label"].split() if len(w) > 2)
            overlap = current_words & topic_words
            if len(overlap) >= 2:
                topic["continuing_keywords"] = list(overlap)[:5]
                continuing.append(topic)
        return continuing


# ── X tweet metrics ───────────────────────────────────────────────────────


class _MetricsMixin:
    """Methods for tracking X tweet performance metrics."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError

    def upsert_tweet_metrics(
        self,
        *,
        tweet_id: str,
        report_id: str = "",
        content_preview: str = "",
        impressions: int = 0,
        likes: int = 0,
        retweets: int = 0,
        replies: int = 0,
        quotes: int = 0,
        bookmarks: int = 0,
        published_at: str = "",
    ) -> None:
        """Insert or update tweet metrics."""
        now = utc_now_iso()
        published = published_at or now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO x_tweet_metrics
                    (tweet_id, report_id, content_preview, impressions, likes,
                     retweets, replies, quotes, bookmarks, published_at, last_fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tweet_id) DO UPDATE SET
                    impressions = excluded.impressions,
                    likes = excluded.likes,
                    retweets = excluded.retweets,
                    replies = excluded.replies,
                    quotes = excluded.quotes,
                    bookmarks = excluded.bookmarks,
                    last_fetched_at = excluded.last_fetched_at
                """,
                (
                    tweet_id,
                    report_id,
                    content_preview[:200],
                    impressions,
                    likes,
                    retweets,
                    replies,
                    quotes,
                    bookmarks,
                    published,
                    now,
                ),
            )

    def get_tweet_metrics(self, tweet_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM x_tweet_metrics WHERE tweet_id = ?", (tweet_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_top_tweets(self, *, days: int = 30, limit: int = 10, sort_by: str = "impressions") -> list[dict[str, Any]]:
        """Return top-performing tweets sorted by a given metric."""
        valid_sorts = {"impressions", "likes", "retweets", "replies", "quotes", "bookmarks"}
        if sort_by not in valid_sorts:
            sort_by = "impressions"
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM x_tweet_metrics
                WHERE published_at >= ?
                ORDER BY {sort_by} DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_published_tweet_id(self, report_id: str, tweet_id: str, content_preview: str = "") -> None:
        """Record a published tweet ID for later metrics collection."""
        self.upsert_tweet_metrics(
            tweet_id=tweet_id,
            report_id=report_id,
            content_preview=content_preview,
        )

    def get_recent_tweet_ids(self, *, hours: int = 48) -> list[str]:
        """Return tweet IDs published within the given time window."""
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tweet_id FROM x_tweet_metrics WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            ).fetchall()
        return [row["tweet_id"] for row in rows]

    def get_metrics_summary(self, *, days: int = 7) -> dict[str, Any]:
        """Aggregate tweet metrics over the given period."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total_tweets,
                       SUM(impressions) AS total_impressions,
                       SUM(likes) AS total_likes,
                       SUM(retweets) AS total_retweets,
                       SUM(replies) AS total_replies,
                       AVG(impressions) AS avg_impressions,
                       AVG(likes) AS avg_likes
                FROM x_tweet_metrics
                WHERE published_at >= ?
                """,
                (cutoff,),
            ).fetchone()
        if row is None:
            return {"period_days": days, "total_tweets": 0}
        return {
            "period_days": days,
            "total_tweets": int(row["total_tweets"] or 0),
            "total_impressions": int(row["total_impressions"] or 0),
            "total_likes": int(row["total_likes"] or 0),
            "total_retweets": int(row["total_retweets"] or 0),
            "total_replies": int(row["total_replies"] or 0),
            "avg_impressions": round(float(row["avg_impressions"] or 0), 1),
            "avg_likes": round(float(row["avg_likes"] or 0), 1),
        }
