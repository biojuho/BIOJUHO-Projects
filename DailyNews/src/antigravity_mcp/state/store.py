"""Unified pipeline state store backed by SQLite.

``PipelineStateStore`` composes four domain-focused mixin classes
(see :pymod:`antigravity_mcp.state.mixins`) while keeping the database
connection, locking and schema management in one place.

All existing call sites continue to work unchanged.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.mixins import (
    _ArticleMixin,
    _CacheMixin,
    _ReportMixin,
    _RunMixin,
)


class PipelineStateStore(_RunMixin, _ArticleMixin, _ReportMixin, _CacheMixin):
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
            self._conn.execute("PRAGMA cache_size=-65536")    # 64 MB page cache
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._conn.execute("PRAGMA mmap_size=268435456")  # 256 MB memory-mapped I/O
        return self._conn

    def close(self) -> None:
        """Explicitly close the underlying SQLite connection.

        Call this when the store is no longer needed (e.g. at the end of a
        script or inside a test fixture teardown) to avoid ResourceWarning
        about unclosed database connections.
        """
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
        """Best-effort cleanup when the object is garbage-collected."""
        self.close()

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # ── Schema bootstrap ──────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            # Migration: job_runs schema upgrade (add processed_count, published_count)
            cur = connection.execute("PRAGMA table_info(job_runs)")
            existing_cols = {row[1] for row in cur.fetchall()}
            if existing_cols and "processed_count" not in existing_cols:
                connection.execute(
                    "ALTER TABLE job_runs ADD COLUMN processed_count INTEGER NOT NULL DEFAULT 0"
                )
            if existing_cols and "published_count" not in existing_cols:
                connection.execute(
                    "ALTER TABLE job_runs ADD COLUMN published_count INTEGER NOT NULL DEFAULT 0"
                )

            # Migration: article_cache schema upgrade (add category, window_name, new PK)
            cur = connection.execute("PRAGMA table_info(article_cache)")
            existing_cols = {row[1] for row in cur.fetchall()}
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
            # --- Phase 4: LLM response cache ---
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
            self._ensure_column(connection, "llm_cache", "cache_hits", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_cache_expires
                ON llm_cache(expires_at)
                """
            )
            # --- Phase 4: Feed ETag/Last-Modified cache ---
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
