"""
Dashboard — Database Utilities

Centralized SQLite and PostgreSQL read helpers extracted from api.py.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

log = logging.getLogger("dashboard")

# ── DB Paths ──
WORKSPACE = Path(__file__).resolve().parents[2]
GDT_DB = WORKSPACE / "automation" / "getdaytrends" / "data" / "getdaytrends.db"
CIE_DB = WORKSPACE / "automation" / "content-intelligence" / "data" / "cie.db"
DN_DB = WORKSPACE / "automation" / "DailyNews" / "data" / "pipeline_state.db"
AG_PG_URL = os.environ.get(
    "AGRIGUARD_DATABASE_URL",
    "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard",
)


def _sqlite_read(db_path: Path, query: str, params: tuple = ()) -> list[dict]:
    """SQLite에서 읽어 dict 리스트로 반환."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("SQLite read failed (%s): %s", db_path.name, e)
        return []
    finally:
        conn.close()


def _sqlite_scalar(db_path: Path, query: str, params: tuple = ()) -> Any:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(query, params).fetchone()[0]
    except Exception as e:
        log.warning("SQLite scalar failed (%s): %s", db_path.name, e)
        return None
    finally:
        conn.close()


# ── PostgreSQL ──
_pg_engine = None


def _get_pg_engine():
    """Lazy singleton SQLAlchemy engine."""
    global _pg_engine
    if _pg_engine is None:
        try:
            from sqlalchemy import create_engine

            _pg_engine = create_engine(AG_PG_URL, pool_pre_ping=True, pool_size=3)
        except Exception as e:
            log.warning("PostgreSQL engine creation failed: %s", e)
            return None
    return _pg_engine


def _pg_read(query: str) -> list[dict]:
    """PostgreSQL에서 읽어 dict 리스트로 반환."""
    try:
        from sqlalchemy import text

        engine = _get_pg_engine()
        if engine is None:
            return [{"error": "PostgreSQL not available"}]
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = result.keys()
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    except Exception as e:
        log.warning("PostgreSQL read failed: %s", e)
        return [{"error": str(e)}]


def _pg_scalar(query: str) -> Any:
    try:
        from sqlalchemy import text

        engine = _get_pg_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            return conn.execute(text(query)).scalar()
    except Exception as e:
        log.warning("PostgreSQL scalar failed: %s", e)
        return None
