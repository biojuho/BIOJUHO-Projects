"""
getdaytrends — Database Connection Management.
PostgreSQL/SQLite 연결 관리, 트랜잭션 컨텍스트 매니저.
db_schema.py에서 분리됨.
"""

import os
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
from loguru import logger as log

from .pg_adapter import PgAdapter

# === PostgreSQL 선택적 지원 ===
try:
    import asyncpg

    _PG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# asyncpg 커넥션 풀 (싱글턴)
_PG_POOL: "asyncpg.Pool | None" = None
_SQLITE_WRITE_LOCK = threading.RLock()


def _mask_db_error(value: object) -> str:
    text = str(value)
    text = re.sub(r"((?:postgresql|postgres)://)[^@\s]+@", r"\1***:***@", text)
    text = re.sub(r"(tenant/user\s+)[^\s)]+", r"\1***", text, flags=re.IGNORECASE)
    return text


def _uses_in_memory_sqlite(db_path: str) -> bool:
    normalized = (db_path or "").strip().lower()
    return normalized == ":memory:" or normalized.startswith("file::memory:")


# === 트랜잭션 컨텍스트 매니저 ===


@asynccontextmanager
async def sqlite_write_lock(conn) -> AsyncIterator[None]:
    """Serialize SQLite writes across worker threads while leaving Postgres untouched."""
    if isinstance(conn, PgAdapter):
        yield
        return

    _SQLITE_WRITE_LOCK.acquire()
    try:
        yield
    finally:
        _SQLITE_WRITE_LOCK.release()


@asynccontextmanager
async def db_transaction(conn) -> AsyncIterator[None]:
    """
    aiosqlite / asyncpg 공용 트랜잭션 컨텍스트 매니저.
    예외 발생 시 자동 rollback, 정상 종료 시 commit.

    사용 예:
        async with db_transaction(conn):
            trend_id = await save_trend(conn, trend, run_id)
            await save_tweets_batch(conn, tweets, trend_id, run_id)
    """
    async with sqlite_write_lock(conn):
        # C-03 fix: PgAdapter에서 실제 트랜잭션을 시작
        if isinstance(conn, PgAdapter) and conn._txn is None:
            conn._txn = conn._conn.transaction()
            async with conn._lock:
                await conn._txn.start()
        try:
            yield
            await conn.commit()
        except Exception:
            try:
                await conn.rollback()
            except Exception as _rb_err:
                log.debug(f"Rollback \uc2e4\ud328 (\ubb34\uc2dc): {_rb_err}")
            raise


# === 커넥션 풀 관리 ===


async def get_pg_pool(url: str, min_size: int = 2, max_size: int = 10) -> "asyncpg.Pool":
    """asyncpg 커넥션 풀 반환. Event Loop 종속성 문제를 위해 loop 객체에 바인딩."""
    import asyncio

    loop = asyncio.get_running_loop()
    pool = getattr(loop, "_pg_pool", None)
    if pool is None or pool._closed:
        pool = await asyncpg.create_pool(
            url,
            min_size=min_size,
            max_size=max_size,
            statement_cache_size=0,  # required for Supabase transaction-mode pooler
        )
        loop._pg_pool = pool
        log.info(f"asyncpg Pool 생성 (loop_id={id(loop)}): min={min_size} max={max_size} @ {url.split('@')[-1]}")
    return pool


async def close_pg_pool() -> None:
    """앱 종료 시 asyncpg Pool 정리."""
    try:
        import asyncio

        loop = asyncio.get_running_loop()
        pool = getattr(loop, "_pg_pool", None)
        if pool and not pool._closed:
            await pool.close()
            loop._pg_pool = None
            log.info(f"asyncpg Pool 정상 종료 (loop_id={id(loop)})")
    except RuntimeError:
        pass  # No running loop


async def get_connection(
    db_path: str = "data/getdaytrends.db",
    database_url: str = "",
    *,
    allow_sqlite_fallback: bool = False,
) -> object:
    """DB 연결 반환. DATABASE_URL 설정 시 asyncpg Pool에서 연결 획득."""
    # Explicit in-memory SQLite requests should not be overridden by a
    # workspace-level DATABASE_URL leaking in from the shell environment.
    url = "" if _uses_in_memory_sqlite(db_path) else (database_url or os.getenv("DATABASE_URL", ""))
    if url.startswith(("postgresql://", "postgres://")):
        if not _PG_AVAILABLE:
            raise ImportError("PostgreSQL 사용을 위해 asyncpg 설치 필요:\n  pip install asyncpg")
        try:
            pool = await get_pg_pool(url)
            pg_conn = await pool.acquire()
            # BUG-005 fix: pass pool reference so close() can release
            return PgAdapter(pg_conn, pool=pool)
        except Exception as exc:
            if not allow_sqlite_fallback:
                raise
            log.warning(
                "PostgreSQL connection failed; falling back to local SQLite "
                f"for this run ({type(exc).__name__}: {_mask_db_error(exc)})"
            )

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn
