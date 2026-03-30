"""Pipeline execution logger — tracks run history to SQLite for monitoring.

Usage:
    from notebooklm_automation.execution_log import ExecutionLogger

    logger = ExecutionLogger()
    run_id = logger.start_run("drive-to-notion", {"file": "report.pdf"})
    logger.complete_run(run_id, success=True, result={...})
    recent = logger.get_recent_runs(limit=20)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger as log

from .config import get_config

_DEFAULT_DB = "pipeline_runs.db"


class ExecutionLogger:
    """SQLite-based execution log for pipeline runs."""

    def __init__(self, db_path: str | Path | None = None):
        cfg = get_config()
        self._db_path = Path(db_path) if db_path else cfg.home_dir / _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL,
                    input_params TEXT,
                    result TEXT,
                    error TEXT,
                    file_name TEXT,
                    project TEXT,
                    article_title TEXT,
                    notion_url TEXT,
                    ai_model TEXT,
                    extracted_chars INTEGER DEFAULT 0,
                    article_chars INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_started
                ON pipeline_runs(started_at DESC)
            """)

    def start_run(self, pipeline_name: str, input_params: dict | None = None) -> str:
        """Record the start of a pipeline run. Returns run_id."""
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO pipeline_runs (id, pipeline_name, started_at, input_params, file_name, project)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    pipeline_name,
                    now,
                    json.dumps(input_params or {}, ensure_ascii=False),
                    (input_params or {}).get("file_name", ""),
                    (input_params or {}).get("project", ""),
                ),
            )

        log.info("[RunLog] started: %s (%s)", run_id, pipeline_name)
        return run_id

    def complete_run(
        self,
        run_id: str,
        *,
        success: bool,
        result: dict | None = None,
        error: str = "",
    ) -> None:
        """Record the completion of a pipeline run."""
        now = datetime.now().isoformat()
        result = result or {}

        with sqlite3.connect(str(self._db_path)) as conn:
            # Get start time for duration
            row = conn.execute("SELECT started_at FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()

            duration = 0.0
            if row:
                started = datetime.fromisoformat(row[0])
                duration = (datetime.now() - started).total_seconds()

            conn.execute(
                """UPDATE pipeline_runs
                   SET status = ?, completed_at = ?, duration_seconds = ?,
                       result = ?, error = ?, article_title = ?,
                       notion_url = ?, ai_model = ?,
                       extracted_chars = ?, article_chars = ?
                   WHERE id = ?""",
                (
                    "success" if success else "failed",
                    now,
                    duration,
                    json.dumps(result, ensure_ascii=False),
                    error,
                    result.get("article_title", ""),
                    result.get("notion_url", ""),
                    result.get("ai_model_used", ""),
                    result.get("extracted_text_length", 0),
                    result.get("article_length", 0),
                    run_id,
                ),
            )

        emoji = "✅" if success else "❌"
        log.info(
            "[RunLog] %s %s — %.1fs%s",
            emoji,
            run_id,
            duration,
            f" | error: {error}" if error else "",
        )

    def get_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent pipeline executions."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM pipeline_runs
                   ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """Get daily aggregated statistics."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT
                     DATE(started_at) as date,
                     COUNT(*) as total_runs,
                     SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                     SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as fail_count,
                     ROUND(AVG(duration_seconds), 1) as avg_duration,
                     SUM(article_chars) as total_chars
                   FROM pipeline_runs
                   WHERE started_at >= DATE('now', ?)
                   GROUP BY DATE(started_at)
                   ORDER BY date DESC""",
                (f"-{days} days",),
            ).fetchall()
        return [dict(r) for r in rows]
