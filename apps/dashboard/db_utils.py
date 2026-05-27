"""
Dashboard — Database Utilities

Centralized SQLite and PostgreSQL read helpers extracted from api.py.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import aiosqlite

log = logging.getLogger("dashboard")

# ── DB Paths ──
WORKSPACE = Path(__file__).resolve().parents[2]
GDT_DB = WORKSPACE / "automation" / "getdaytrends" / "data" / "getdaytrends.db"
CIE_DB = WORKSPACE / "automation" / "content-intelligence" / "data" / "cie.db"
DN_DB = WORKSPACE / "automation" / "DailyNews" / "data" / "pipeline_state.db"

# asyncpg URL
_RAW_URL = os.environ.get(
    "AGRIGUARD_DATABASE_URL",
    "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard",
)
if _RAW_URL.startswith("postgresql://"):
    AG_PG_URL = _RAW_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    AG_PG_URL = _RAW_URL


async def _sqlite_read(db_path: Path, query: str, params: tuple = ()) -> list[dict]:
    """SQLite에서 비동기로 읽어 dict 리스트로 반환."""
    if not db_path.exists():
        return []
    try:
        async with aiosqlite.connect(str(db_path)) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        log.warning("SQLite read failed (%s): %s", db_path.name, e)
        return []


async def _sqlite_scalar(db_path: Path, query: str, params: tuple = ()) -> Any:
    """SQLite에서 비동기로 단일 스칼라값을 반환."""
    if not db_path.exists():
        return None
    try:
        async with aiosqlite.connect(str(db_path)) as conn, conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        log.warning("SQLite scalar failed (%s): %s", db_path.name, e)
        return None


# ── PostgreSQL ──
_pg_engine = None


def _get_pg_engine():
    """Lazy singleton Async SQLAlchemy engine.

    Under FastAPI TestClient each request runs in its own event loop. A
    pooled asyncpg connection bound to an earlier loop fails to close cleanly
    in the next loop, leaving an unawaited ``Connection._cancel`` task. We
    detect the test environment via ``PYTEST_CURRENT_TEST`` and use
    ``NullPool`` so each request opens + closes its own connection inside the
    same loop. Production runtime keeps the original pooled config.
    """
    global _pg_engine
    if _pg_engine is None:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine

            kwargs: dict[str, Any] = {"pool_pre_ping": True}
            if os.environ.get("PYTEST_CURRENT_TEST"):
                from sqlalchemy.pool import NullPool

                kwargs["poolclass"] = NullPool
            else:
                kwargs["pool_size"] = 3
            _pg_engine = create_async_engine(AG_PG_URL, **kwargs)
        except Exception as e:
            log.warning("PostgreSQL async engine creation failed: %s", e)
            return None
    return _pg_engine


async def dispose_pg_engine() -> None:
    """Dispose the module-level async engine and its asyncpg pool.

    Without this, asyncpg's ``Connection._cancel(waiter)`` task scheduled by
    ``_connection.close(timeout=2)`` can outlive the event loop on interpreter
    shutdown, producing ``RuntimeWarning: coroutine 'Connection._cancel' was
    never awaited`` at GC time. Call this from session teardown.
    """
    global _pg_engine
    if _pg_engine is not None:
        try:
            await _pg_engine.dispose()
        except Exception as e:  # pragma: no cover - cleanup best-effort
            log.warning("PostgreSQL async engine dispose failed: %s", e)
        finally:
            _pg_engine = None


async def _pg_read(query: str) -> list[dict]:
    """PostgreSQL에서 비동기로 읽어 dict 리스트로 반환."""
    try:
        from sqlalchemy import text

        engine = _get_pg_engine()
        if engine is None:
            return [{"error": "PostgreSQL not available"}]
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            columns = result.keys()
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    except Exception as e:
        log.warning("PostgreSQL async read failed: %s", e)
        return [{"error": str(e)}]


async def _pg_scalar(query: str) -> Any:
    """PostgreSQL에서 비동기로 단일 스칼라값을 반환."""
    try:
        from sqlalchemy import text

        engine = _get_pg_engine()
        if engine is None:
            return None
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            return result.scalar()
    except Exception as e:
        log.warning("PostgreSQL async scalar failed: %s", e)
        return None
