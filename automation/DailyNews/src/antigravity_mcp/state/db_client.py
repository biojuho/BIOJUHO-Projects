"""Database client adapter for Cloud DB and Checkpoints."""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from antigravity_mcp.config import get_settings

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class CheckpointDBClient:
    """A minimal adapter that gives either a PostgreSQL connection or falls back to sqlite."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.use_postgres = bool(self.settings.supabase_database_url and PSYCOPG2_AVAILABLE)
        self._sqlite_connection: sqlite3.Connection | None = None
        self._sqlite_lock = threading.Lock()
        
        if self.use_postgres:
            logger.info("Using PostgreSQL (Supabase) for Checkpoint DB")
            self._init_pg_schema()
        else:
            if not self.settings.supabase_database_url:
                logger.warning("SUPABASE_DATABASE_URL not set. Falling back to local pipeline_state.db for checkpoints.")
            elif not PSYCOPG2_AVAILABLE:
                logger.warning("psycopg2-binary not installed. Falling back to local pipeline_state.db for checkpoints.")
            self._init_sqlite_schema()

    def _init_pg_schema(self) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
                        job_id TEXT PRIMARY KEY,
                        pipeline_name TEXT NOT NULL,
                        current_step TEXT NOT NULL,
                        state_json JSONB NOT NULL DEFAULT '{}',
                        status TEXT NOT NULL DEFAULT 'running',
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
            conn.commit()

    def _init_sqlite_schema(self) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
                    job_id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'running',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        # Return a unified connection object (either pg or sqlite)
        if self.use_postgres:
            conn = psycopg2.connect(self.settings.supabase_database_url, cursor_factory=RealDictCursor)
            try:
                yield conn
            finally:
                conn.close()
        else:
            path = str(self.settings.pipeline_state_db)
            if path == ":memory:":
                with self._sqlite_lock:
                    if self._sqlite_connection is None:
                        self._sqlite_connection = sqlite3.connect(":memory:", check_same_thread=False)
                        self._sqlite_connection.row_factory = sqlite3.Row
                    conn = self._sqlite_connection
                should_close = False
            else:
                conn = sqlite3.connect(self.settings.pipeline_state_db, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                should_close = True
            try:
                yield conn
            finally:
                if should_close:
                    conn.close()

    def close(self) -> None:
        if self._sqlite_connection is not None:
            try:
                self._sqlite_connection.close()
            except (sqlite3.Error, OSError):
                pass
            self._sqlite_connection = None

    def __del__(self) -> None:
        self.close()
