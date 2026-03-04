from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ChannelDraft, ContentReport, PipelineRun
from antigravity_mcp.state.events import utc_now_iso


class PipelineStateStore:
    def __init__(self, path: Path | None = None) -> None:
        settings = get_settings()
        self.path = path or settings.pipeline_state_db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    summary_json TEXT,
                    error_text TEXT,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    published_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS article_cache (
                    link TEXT NOT NULL,
                    category TEXT NOT NULL,
                    window_name TEXT NOT NULL,
                    source TEXT,
                    first_seen_at TEXT NOT NULL,
                    notion_page_id TEXT,
                    last_run_id TEXT,
                    PRIMARY KEY (link, category, window_name)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS content_reports (
                    report_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    window_name TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    insights_json TEXT NOT NULL,
                    drafts_json TEXT NOT NULL,
                    notion_page_id TEXT,
                    asset_status TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    source_links_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_publications (
                    report_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_url TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (report_id, channel)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_article_cache_category_window
                ON article_cache(category, window_name)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_article_cache_link
                ON article_cache(link)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_content_reports_fingerprint
                ON content_reports(fingerprint)
                """
            )

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

    def list_runs(self, *, job_name: str | None = None, status: str | None = None, limit: int = 20) -> list[PipelineRun]:
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

    def find_report_by_fingerprint(self, fingerprint: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return self._row_to_report(row) if row else None

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
                    approval_state, source_links_json, status, fingerprint, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.category,
                    report.window_name,
                    report.window_start,
                    report.window_end,
                    json.dumps(report.summary_lines, ensure_ascii=False),
                    json.dumps(report.insights, ensure_ascii=False),
                    json.dumps([draft.to_dict() for draft in report.channel_drafts], ensure_ascii=False),
                    report.notion_page_id,
                    report.asset_status,
                    report.approval_state,
                    json.dumps(report.source_links, ensure_ascii=False),
                    report.status,
                    report.fingerprint,
                    created_at,
                    updated_at,
                ),
            )

    def get_report(self, report_id: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        return self._row_to_report(row) if row else None

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

    def get_pipeline_health(self) -> dict[str, Any]:
        """Return health metrics for pipeline runs in the last 24 hours.

        Returns a dict with:
          - last_run_at: ISO timestamp of the most recent run (or None)
          - last_run_status: status of the most recent run (or None)
          - success_count_24h: successful runs in the last 24h
          - failure_count_24h: failed runs in the last 24h
          - total_runs_24h: total runs in the last 24h
          - avg_latency_seconds: average duration of completed runs in 24h (or None)
          - error_rate: fraction of failed runs in 24h (0.0 - 1.0)
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with self._connect() as connection:
            # Most recent run overall
            last_row = connection.execute(
                "SELECT started_at, status FROM job_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

            # Counts by status in the last 24h
            rows_24h = connection.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM job_runs
                WHERE started_at >= ?
                GROUP BY status
                """,
                (cutoff,),
            ).fetchall()

            # Average latency for runs that have both started_at and finished_at
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

        # Parse counts
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

    def _row_to_report(self, row: sqlite3.Row | None) -> ContentReport | None:
        if row is None:
            return None
        drafts = [
            ChannelDraft(
                channel=item.get("channel", ""),
                status=item.get("status", ""),
                content=item.get("content", ""),
                external_url=item.get("external_url", ""),
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
        )
