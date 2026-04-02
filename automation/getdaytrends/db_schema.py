"""
getdaytrends - Database Schema & Connection Layer
PostgreSQL 어댑터, DB 연결, 스키마 초기화 및 마이그레이션.
db.py에서 분리됨.
"""

import hashlib
import os
import re
import threading
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, UTC

import aiosqlite
from loguru import logger as log

# === PostgreSQL 선택적 지원 ===
try:
    import asyncpg

    _PG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# asyncpg 커넥션 풀 (싱글톤)
_PG_POOL: "asyncpg.Pool | None" = None
_SQLITE_WRITE_LOCK = threading.RLock()


# === 트랜잭션 컨텍스트 매니저 ===


@asynccontextmanager
async def sqlite_write_lock(conn) -> AsyncIterator[None]:
    """Serialize SQLite writes across worker threads while leaving Postgres untouched."""
    if isinstance(conn, _PgAdapter):
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
        try:
            yield
            await conn.commit()
        except Exception:
            try:
                await conn.rollback()
            except Exception as _rb_err:
                log.debug(f"Rollback \uc2e4\ud328 (\ubb34\uc2dc): {_rb_err}")
            raise


class _PgAdapter:
    """
    asyncpg 연결을 aiosqlite.Connection 인터페이스와 유사하게 래핑.
    """

    def __init__(self, conn: "asyncpg.Connection") -> None:
        self._conn = conn

    @staticmethod
    def _ph(sql: str) -> str:
        """
        ? 를 $1, $2 ... PostgreSQL 플레이스홀더로 변환.
        문자열 리터럴 내부의 ?는 변환하지 않도록 처리.
        """
        # 문자열 밖에 있는 ? 만 순서대로 $N 으로 교체
        result = []
        counter = 0
        in_str = False
        str_char = ""
        i = 0
        while i < len(sql):
            ch = sql[i]
            if in_str:
                result.append(ch)
                if ch == str_char and (i == 0 or sql[i - 1] != "\\"):
                    in_str = False
            elif ch in ("'", '"'):
                in_str = True
                str_char = ch
                result.append(ch)
            elif ch == "?":
                counter += 1
                result.append(f"${counter}")
            else:
                result.append(ch)
            i += 1
        return "".join(result)

    async def execute(self, sql: str, parameters=()):
        sql_pg = self._ph(sql).rstrip()
        is_insert = sql_pg.lstrip().upper().startswith("INSERT")

        if is_insert and "RETURNING" not in sql_pg.upper():
            sql_pg = sql_pg.rstrip(";") + " RETURNING id"

        try:
            if is_insert:
                row = await self._conn.fetchrow(sql_pg, *parameters)

                class DummyCursor:
                    lastrowid = dict(row).get("id") if row else None
                    rowcount = 1

                    async def fetchone(self):
                        return row

                    async def fetchall(self):
                        return [row] if row else []

                return DummyCursor()
            else:
                rows = await self._conn.fetch(sql_pg, *parameters)

                class DummyCursor:
                    lastrowid = None
                    rowcount = len(rows)

                    async def fetchone(self):
                        return rows[0] if rows else None

                    async def fetchall(self):
                        return rows

                return DummyCursor()
        except Exception as e:
            log.error(f"PG Execute Error: {e} | SQL: {sql_pg}")
            raise

    async def executemany(self, sql: str, parameters):
        sql_pg = self._ph(sql)
        await self._conn.executemany(sql_pg, parameters)

    async def executescript(self, sql: str):
        sql_pg = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
            sql,
            flags=re.IGNORECASE,
        )
        stmts = [s.strip() for s in sql_pg.split(";") if s.strip()]
        for stmt in stmts:
            if stmt.upper().startswith("PRAGMA"):
                continue
            try:
                await self._conn.execute(stmt)
            except Exception as e:
                if "already exists" in str(e).lower():
                    log.debug(f"PostgreSQL DDL 스킵 (이미 존재): {stmt[:60]}...")
                else:
                    raise

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        await self._conn.close()


async def get_pg_pool(url: str, min_size: int = 2, max_size: int = 10) -> "asyncpg.Pool":
    """asyncpg 커넥션 풀 싱글톤 반환."""
    global _PG_POOL
    if _PG_POOL is None or _PG_POOL._closed:  # type: ignore[union-attr]
        _PG_POOL = await asyncpg.create_pool(url, min_size=min_size, max_size=max_size)
        log.info(f"asyncpg Pool 생성: min={min_size} max={max_size} @ {url.split('@')[-1]}")
    return _PG_POOL


async def close_pg_pool() -> None:
    """앱 종료 시 asyncpg Pool 정리."""
    global _PG_POOL
    if _PG_POOL and not _PG_POOL._closed:  # type: ignore[union-attr]
        await _PG_POOL.close()
        _PG_POOL = None


async def get_connection(
    db_path: str = "data/getdaytrends.db",
    database_url: str = "",
):
    """DB 연결 반환. DATABASE_URL 설정 시 asyncpg Pool에서 연결 획득."""
    url = database_url or os.getenv("DATABASE_URL", "")
    if url.startswith(("postgresql://", "postgres://")):
        if not _PG_AVAILABLE:
            raise ImportError("PostgreSQL 사용을 위해 asyncpg 설치 필요:\n  pip install asyncpg")
        pool = await get_pg_pool(url)
        pg_conn = await pool.acquire()
        return _PgAdapter(pg_conn)

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def _init_db_unlocked(conn) -> None:
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass

    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_uuid      TEXT NOT NULL UNIQUE,
            started_at    TEXT NOT NULL,
            finished_at   TEXT,
            country       TEXT NOT NULL DEFAULT 'korea',
            trends_collected  INTEGER DEFAULT 0,
            trends_scored     INTEGER DEFAULT 0,
            tweets_generated  INTEGER DEFAULT 0,
            tweets_saved      INTEGER DEFAULT 0,
            alerts_sent       INTEGER DEFAULT 0,
            errors        TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS trends (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id             INTEGER NOT NULL REFERENCES runs(id),
            keyword            TEXT NOT NULL,
            rank               INTEGER,
            volume_raw         TEXT DEFAULT 'N/A',
            volume_numeric     INTEGER DEFAULT 0,
            viral_potential    INTEGER DEFAULT 0,
            trend_acceleration TEXT DEFAULT '+0%',
            top_insight        TEXT DEFAULT '',
            suggested_angles   TEXT DEFAULT '[]',
            best_hook_starter  TEXT DEFAULT '',
            country            TEXT DEFAULT 'korea',
            sources            TEXT DEFAULT '[]',
            twitter_context    TEXT DEFAULT '',
            reddit_context     TEXT DEFAULT '',
            news_context       TEXT DEFAULT '',
            scored_at          TEXT NOT NULL,
            fingerprint        TEXT DEFAULT '',
            sentiment          TEXT DEFAULT 'neutral',
            safety_flag        INTEGER DEFAULT 0,
            cross_source_confidence INTEGER DEFAULT 0,
            joongyeon_kick     INTEGER DEFAULT 0,
            joongyeon_angle    TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_trends_keyword ON trends(keyword);
        CREATE INDEX IF NOT EXISTS idx_trends_scored_at ON trends(scored_at);
        CREATE INDEX IF NOT EXISTS idx_trends_viral ON trends(viral_potential);
        CREATE INDEX IF NOT EXISTS idx_trends_keyword_scored ON trends(keyword, scored_at);
        CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint);

        CREATE TABLE IF NOT EXISTS tweets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id      INTEGER NOT NULL REFERENCES trends(id),
            run_id        INTEGER NOT NULL REFERENCES runs(id),
            tweet_type    TEXT NOT NULL,
            content       TEXT NOT NULL,
            char_count    INTEGER DEFAULT 0,
            is_thread     INTEGER DEFAULT 0,
            thread_order  INTEGER DEFAULT 0,
            status        TEXT DEFAULT '대기중',
            saved_to      TEXT DEFAULT '[]',
            generated_at  TEXT NOT NULL,
            content_type  TEXT DEFAULT 'short',
            variant_id    TEXT DEFAULT '',
            language      TEXT DEFAULT 'ko',
            posted_at     TEXT DEFAULT NULL,
            x_tweet_id    TEXT DEFAULT '',
            impressions   INTEGER DEFAULT 0,
            engagements   INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0
        );

        CREATE INDEX IF NOT EXISTS idx_tweets_trend ON tweets(trend_id);
        CREATE INDEX IF NOT EXISTS idx_tweets_status ON tweets(status);
        CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type);
        CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id);

        CREATE INDEX IF NOT EXISTS idx_trends_run_keyword ON trends(run_id, keyword);
        CREATE INDEX IF NOT EXISTS idx_trends_country_scored ON trends(country, scored_at);

        CREATE TABLE IF NOT EXISTS meta (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_quality (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source        TEXT NOT NULL,
            recorded_at   TEXT NOT NULL,
            success       INTEGER DEFAULT 1,
            latency_ms    REAL DEFAULT 0,
            item_count    INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_sq_source ON source_quality(source, recorded_at);

        CREATE TABLE IF NOT EXISTS content_feedback (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword       TEXT NOT NULL,
            category      TEXT DEFAULT '',
            qa_score      REAL DEFAULT 0.0,
            regenerated   INTEGER DEFAULT 0,
            reason        TEXT DEFAULT '',
            content_age_hours REAL DEFAULT 0.0,
            freshness_grade   TEXT DEFAULT 'unknown',
            created_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cf_keyword ON content_feedback(keyword, created_at);

        CREATE TABLE IF NOT EXISTS posting_time_stats (
            category    TEXT NOT NULL,
            hour        INTEGER NOT NULL,
            total_score REAL DEFAULT 0.0,
            sample_count INTEGER DEFAULT 0,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (category, hour)
        );

        CREATE TABLE IF NOT EXISTS watchlist_hits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword         TEXT NOT NULL,
            watchlist_item  TEXT NOT NULL,
            viral_potential INTEGER DEFAULT 0,
            detected_at     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wh_keyword ON watchlist_hits(keyword, detected_at);

        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            applied_at  TEXT NOT NULL
        );
    """)
    await conn.commit()

    # ── 버전 기반 마이그레이션 ──
    await _run_migrations(conn)


# ══════════════════════════════════════════════════════
#  Schema Migration Infrastructure
# ══════════════════════════════════════════════════════

_CURRENT_SCHEMA_VERSION = 5


async def _get_schema_version(conn) -> int:
    """현재 DB 스키마 버전 조회. schema_version 테이블 없으면 0."""
    try:
        cursor = await conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        )
        row = await cursor.fetchone()
        v = row["v"] if row else None
        return v if v is not None else 0
    except Exception:
        return 0


async def _set_schema_version(conn, version: int, description: str) -> None:
    await conn.execute(
        "INSERT OR REPLACE INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)",
        (version, description, datetime.now(UTC).isoformat()),
    )
    await conn.commit()


async def _table_columns(conn, table: str) -> set[str]:
    """테이블의 컬럼 이름 목록 반환 (SQLite PRAGMA / PostgreSQL information_schema 호환)."""
    if isinstance(conn, _PgAdapter):
        cursor = await conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        )
        rows = await cursor.fetchall()
        return {r["column_name"] if isinstance(r, dict) else r[0] for r in rows}
    # SQLite
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return {(row["name"] if isinstance(row, dict) else row[1]) for row in rows}


async def _migrate_v1(conn) -> None:
    """v1: tweets.content_type 추가 (단문/장문 구분)."""
    cols = await _table_columns(conn, "tweets")
    if "content_type" not in cols:
        await conn.execute("ALTER TABLE tweets ADD COLUMN content_type TEXT DEFAULT 'short'")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type)")
        await conn.commit()


async def _migrate_v2(conn) -> None:
    """v2: trends.fingerprint 추가 (캐시 키)."""
    cols = await _table_columns(conn, "trends")
    if "fingerprint" not in cols:
        await conn.execute("ALTER TABLE trends ADD COLUMN fingerprint TEXT DEFAULT ''")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint)")
        await conn.commit()
        await _backfill_fingerprints(conn)


async def _migrate_v3(conn) -> None:
    """v3: tweets 성과추적 + A/B 변형 + 다국어 컬럼."""
    cols = await _table_columns(conn, "tweets")
    for col_name, col_def in [
        ("posted_at", "TEXT DEFAULT NULL"),
        ("x_tweet_id", "TEXT DEFAULT ''"),
        ("impressions", "INTEGER DEFAULT 0"),
        ("engagements", "INTEGER DEFAULT 0"),
        ("engagement_rate", "REAL DEFAULT 0.0"),
        ("variant_id", "TEXT DEFAULT ''"),
        ("language", "TEXT DEFAULT 'ko'"),
    ]:
        if col_name not in cols:
            await conn.execute(f"ALTER TABLE tweets ADD COLUMN {col_name} {col_def}")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id)")
    await conn.commit()


async def _migrate_v4(conn) -> None:
    """v4: trends 감성필터 + 교차검증 + 중연킥."""
    cols = await _table_columns(conn, "trends")
    for col_name, col_def in [
        ("sentiment", "TEXT DEFAULT 'neutral'"),
        ("safety_flag", "INTEGER DEFAULT 0"),
        ("cross_source_confidence", "INTEGER DEFAULT 0"),
        ("joongyeon_kick", "INTEGER DEFAULT 0"),
        ("joongyeon_angle", "TEXT DEFAULT ''"),
    ]:
        if col_name not in cols:
            await conn.execute(f"ALTER TABLE trends ADD COLUMN {col_name} {col_def}")
    await conn.commit()


async def _migrate_v5(conn) -> None:
    """v5: schema_version 테이블 자체 (이미 CREATE TABLE로 생성됨). 마커 전용."""
    pass


# 마이그레이션 레지스트리: (버전, 설명, 함수)
_MIGRATIONS: list[tuple[int, str, any]] = [
    (1, "tweets.content_type 컬럼", _migrate_v1),
    (2, "trends.fingerprint 컬럼 + 백필", _migrate_v2),
    (3, "tweets 성과추적 + A/B + 다국어", _migrate_v3),
    (4, "trends 감성필터 + 교차검증 + 중연킥", _migrate_v4),
    (5, "schema_version 인프라 도입", _migrate_v5),
]


async def _reconcile_latest_schema(conn) -> None:
    """Backfill required columns when the schema marker drifted from actual columns."""
    await _migrate_v1(conn)
    await _migrate_v2(conn)
    await _migrate_v3(conn)
    await _migrate_v4(conn)


async def _run_migrations(conn) -> None:
    """현재 버전 확인 후 미적용 마이그레이션 순차 실행."""
    current = await _get_schema_version(conn)

    if current >= _CURRENT_SCHEMA_VERSION:
        await _reconcile_latest_schema(conn)
        return

    # 기존 DB (schema_version 없이 이미 컬럼이 있는 경우) → 상태 감지
    if current == 0:
        try:
            cols = await _table_columns(conn, "trends")
            if "joongyeon_angle" in cols:
                # v4까지 이미 적용된 기존 DB → v4로 점프
                current = 4
                for v in range(1, 5):
                    desc = next(d for ver, d, _ in _MIGRATIONS if ver == v)
                    await _set_schema_version(conn, v, f"{desc} (기존 감지)")
        except Exception:
            pass

    pending = [(v, d, fn) for v, d, fn in _MIGRATIONS if v > current]
    if not pending:
        # 최신인데 schema_version 레코드만 없는 경우
        if current == 0:
            await _set_schema_version(conn, _CURRENT_SCHEMA_VERSION, "초기 설치")
        await _reconcile_latest_schema(conn)
        return

    for version, description, migrate_fn in pending:
        log.info(f"[DB Migration] v{version}: {description}")
        await migrate_fn(conn)
        await _set_schema_version(conn, version, description)

    await _reconcile_latest_schema(conn)

    log.info(f"[DB Migration] 완료: v{current} → v{_CURRENT_SCHEMA_VERSION}")


async def init_db(conn) -> None:
    async with sqlite_write_lock(conn):
        await _init_db_unlocked(conn)


async def _backfill_fingerprints(conn) -> None:
    cursor = await conn.execute(
        "SELECT id, keyword, volume_numeric FROM trends WHERE fingerprint = '' OR fingerprint IS NULL"
    )
    rows = await cursor.fetchall()
    if not rows:
        return
    for row in rows:
        fp = compute_fingerprint(row["keyword"], row["volume_numeric"])
        await conn.execute("UPDATE trends SET fingerprint = ? WHERE id = ?", (fp, row["id"]))
    await conn.commit()


def _normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = name.lower()
    return re.sub(r"[^a-z0-9\uAC00-\uD7A3\u1100-\u11FF]", "", name)


def _normalize_volume(volume: int, bucket: int = 5000) -> int:
    """볼륨을 bucket 크기로 버킷팅. config.cache_volume_bucket으로 단위 제어 가능"""
    if bucket <= 0:
        return volume
    return (volume // bucket) * bucket


def compute_fingerprint(name: str, volume: int, bucket: int = 5000) -> str:
    """
    트렌드 핑거프린트 계산.
    bucket: 볼륨 버킷 크기 (config.cache_volume_bucket). 작을수록 정밀.
    """
    normalized_name = _normalize_name(name)
    normalized_volume = _normalize_volume(volume, bucket)
    raw = f"{normalized_name}:{normalized_volume}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
