"""Unified pipeline state store backed by SQLite.

``PipelineStateStore`` composes domain-focused mixin classes while keeping
connection, locking, and schema management in one place.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.digest_mixin import _DigestMixin
from antigravity_mcp.state.mixins import (
    _ArticleMixin,
    _CacheMixin,
    _MetricsMixin,
    _ReportMixin,
    _RunMixin,
    _TopicMixin,
    _XPostMixin,
)
from antigravity_mcp.state.reasoning_mixin import _ReasoningMixin

LATEST_SCHEMA_VERSION = 2


class PipelineStateStore(
    _RunMixin,
    _ArticleMixin,
    _ReportMixin,
    _CacheMixin,
    _XPostMixin,
    _TopicMixin,
    _MetricsMixin,
    _ReasoningMixin,
    _DigestMixin,
):
    """Facade that owns the SQLite connection and delegates domain logic to mixins."""

    def __init__(self, path: Path | None = None) -> None:
        settings = get_settings()
        self.path = path or settings.pipeline_state_db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    # ── Connection management ─────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA cache_size=-65536")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._conn.execute("PRAGMA mmap_size=268435456")
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn = None

    # ── Context-manager support ───────────────────────────────────────────

    def __enter__(self) -> "PipelineStateStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    # ── Schema helpers ────────────────────────────────────────────────────

    def _table_exists(self, connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _ensure_schema_version_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
            """
        )

    def _get_schema_version(self, connection: sqlite3.Connection) -> int:
        self._ensure_schema_version_table(connection)
        row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return int(row["version"]) if row is not None else 0

    def _set_schema_version(self, connection: sqlite3.Connection, version: int) -> None:
        self._ensure_schema_version_table(connection)
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))

    def _ensure_base_schema(self, connection: sqlite3.Connection) -> None:
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
                category TEXT NOT NULL DEFAULT '',
                window_name TEXT NOT NULL DEFAULT '',
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
                updated_at TEXT NOT NULL,
                notebooklm_metadata_json TEXT NOT NULL DEFAULT '{}',
                fact_check_score REAL NOT NULL DEFAULT 0,
                quality_state TEXT NOT NULL DEFAULT 'ok',
                generation_mode TEXT NOT NULL DEFAULT '',
                analysis_meta_json TEXT NOT NULL DEFAULT '{}'
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
            CREATE TABLE IF NOT EXISTS llm_cache (
                prompt_hash TEXT PRIMARY KEY,
                response_text TEXT NOT NULL,
                model_name TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_hits INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS x_daily_posts (
                post_date TEXT PRIMARY KEY,
                post_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS topic_timeline (
                topic_id TEXT PRIMARY KEY,
                topic_label TEXT NOT NULL,
                category TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                report_ids_json TEXT NOT NULL DEFAULT '[]',
                embedding_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS x_tweet_metrics (
                tweet_id TEXT PRIMARY KEY,
                report_id TEXT,
                content_preview TEXT,
                impressions INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                quotes INTEGER DEFAULT 0,
                bookmarks INTEGER DEFAULT 0,
                published_at TEXT NOT NULL,
                last_fetched_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_etag_cache (
                url TEXT PRIMARY KEY,
                etag TEXT,
                last_modified TEXT,
                last_fetched_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fact_fragments (
                fact_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                fact_text TEXT NOT NULL,
                why_question TEXT NOT NULL,
                category TEXT NOT NULL,
                source_title TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                hypothesis_text TEXT NOT NULL,
                based_on_facts_json TEXT NOT NULL DEFAULT '[]',
                related_pattern TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                counter_evidence TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_text TEXT NOT NULL,
                category TEXT NOT NULL,
                evidence_facts_json TEXT NOT NULL DEFAULT '[]',
                survival_count INTEGER NOT NULL DEFAULT 1,
                strength TEXT NOT NULL DEFAULT 'emerging',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS digest_queue (
                digest_id TEXT PRIMARY KEY,
                report_ids_json TEXT NOT NULL DEFAULT '[]',
                summary_text TEXT,
                serial_number TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
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
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llm_cache_expires
            ON llm_cache(expires_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_topic_timeline_category
            ON topic_timeline(category, last_seen_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_x_tweet_metrics_report
            ON x_tweet_metrics(report_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fact_fragments_report
            ON fact_fragments(report_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fact_fragments_category
            ON fact_fragments(category, created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_hypotheses_status
            ON hypotheses(status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reasoning_patterns_category
            ON reasoning_patterns(category, survival_count DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_digest_queue_status
            ON digest_queue(status)
            """
        )

    def _migrate_to_v1(self, connection: sqlite3.Connection) -> None:
        if self._table_exists(connection, "job_runs"):
            existing_cols = {row[1] for row in connection.execute("PRAGMA table_info(job_runs)").fetchall()}
            if existing_cols and "processed_count" not in existing_cols:
                connection.execute(
                    "ALTER TABLE job_runs ADD COLUMN processed_count INTEGER NOT NULL DEFAULT 0"
                )
            if existing_cols and "published_count" not in existing_cols:
                connection.execute(
                    "ALTER TABLE job_runs ADD COLUMN published_count INTEGER NOT NULL DEFAULT 0"
                )

        if self._table_exists(connection, "article_cache"):
            existing_cols = {row[1] for row in connection.execute("PRAGMA table_info(article_cache)").fetchall()}
            if existing_cols and "category" not in existing_cols:
                connection.execute("ALTER TABLE article_cache RENAME TO article_cache_old")
                connection.execute(
                    """
                    CREATE TABLE article_cache (
                        link TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT '',
                        window_name TEXT NOT NULL DEFAULT '',
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
                    INSERT OR IGNORE INTO article_cache
                        (link, category, window_name, source, first_seen_at, notion_page_id, last_run_id)
                    SELECT link, '', '', source, first_seen_at, notion_page_id, last_run_id
                    FROM article_cache_old
                    """
                )
                connection.execute("DROP TABLE article_cache_old")

    def _migrate_to_v2(self, connection: sqlite3.Connection) -> None:
        if not self._table_exists(connection, "content_reports"):
            return
        self._ensure_column(connection, "content_reports", "notebooklm_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(connection, "content_reports", "fact_check_score", "REAL NOT NULL DEFAULT 0")
        self._ensure_column(connection, "content_reports", "quality_state", "TEXT NOT NULL DEFAULT 'ok'")
        self._ensure_column(connection, "content_reports", "generation_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(connection, "content_reports", "analysis_meta_json", "TEXT NOT NULL DEFAULT '{}'")

    # ── Schema bootstrap ──────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            self._ensure_base_schema(connection)
            current_version = self._get_schema_version(connection)

            if current_version < 1:
                self._migrate_to_v1(connection)
                current_version = 1
                self._set_schema_version(connection, current_version)

            if current_version < 2:
                self._migrate_to_v2(connection)
                current_version = 2
                self._set_schema_version(connection, current_version)

            self._ensure_column(connection, "llm_cache", "cache_hits", "INTEGER NOT NULL DEFAULT 0")
