"""
getdaytrends ??Database Schema & Connection Layer
PostgreSQL ?대뙌?? DB ?곌껐, ?ㅽ궎留?珥덇린?? 留덉씠洹몃젅?댁뀡.
db.py?먯꽌 遺꾨━??
"""

import hashlib
import os
import re
import threading
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
from loguru import logger as log

# ?? PostgreSQL ?좏깮??吏??????????????????????????????
try:
    import asyncpg

    _PG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# asyncpg 而ㅻ꽖??? (?깃???
_PG_POOL: "asyncpg.Pool | None" = None
_SQLITE_WRITE_LOCK = threading.RLock()


# ?? ?몃옖??뀡 而⑦뀓?ㅽ듃 留ㅻ땲? ????????????????????????????


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
    aiosqlite / asyncpg 怨듭슜 ?몃옖??뀡 而⑦뀓?ㅽ듃 留ㅻ땲?.
    ?덉쇅 諛쒖깮 ???먮룞 rollback, ?뺤긽 醫낅즺 ??commit.

    ?ъ슜 ??:
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
    asyncpg ?곌껐??aiosqlite.Connection ?명꽣?섏씠?ㅼ? ?좎궗?섍쾶 ?섑븨.
    """

    def __init__(self, conn: "asyncpg.Connection") -> None:
        self._conn = conn

    @staticmethod
    def _ph(sql: str) -> str:
        """
        ? ??$1, $2 ... PostgreSQL ?뚮젅?댁뒪???蹂??
        臾몄옄??由ы꽣???대???? ??蹂?섑븯吏 ?딅룄濡??뺢퇋?앹쑝濡?泥섎━.
        """
        # 臾몄옄??諛뽰뿉 ?덈뒗 ? 留??쒖꽌?濡?$N ?쇰줈 援먯껜
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
                    log.debug(f"PostgreSQL DDL ?ㅽ궢 (?대? 議댁옱): {stmt[:60]}...")
                else:
                    raise

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        await self._conn.close()


async def get_pg_pool(url: str, min_size: int = 2, max_size: int = 10) -> "asyncpg.Pool":
    """asyncpg 而ㅻ꽖??? ?깃???諛섑솚."""
    global _PG_POOL
    if _PG_POOL is None or _PG_POOL._closed:  # type: ignore[union-attr]
        _PG_POOL = await asyncpg.create_pool(url, min_size=min_size, max_size=max_size)
        log.info(f"asyncpg Pool ?앹꽦: min={min_size} max={max_size} @ {url.split('@')[-1]}")
    return _PG_POOL


async def close_pg_pool() -> None:
    """??醫낅즺 ??asyncpg Pool ?뺣━."""
    global _PG_POOL
    if _PG_POOL and not _PG_POOL._closed:  # type: ignore[union-attr]
        await _PG_POOL.close()
        _PG_POOL = None


async def get_connection(
    db_path: str = "data/getdaytrends.db",
    database_url: str = "",
):
    """DB ?곌껐 諛섑솚. DATABASE_URL ?ㅼ젙 ??asyncpg Pool?먯꽌 ?곌껐 ?띾뱷."""
    url = database_url or os.getenv("DATABASE_URL", "")
    if url.startswith(("postgresql://", "postgres://")):
        if not _PG_AVAILABLE:
            raise ImportError("PostgreSQL ?ъ슜???꾪빐 asyncpg ?ㅼ튂 ?꾩슂:\n" "  pip install asyncpg")
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
            status        TEXT DEFAULT '?湲곗쨷',
            saved_to      TEXT DEFAULT '[]',
            generated_at  TEXT NOT NULL,
            content_type  TEXT DEFAULT 'short',
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
    """)
    await conn.commit()

    # 湲곗〈 ?고????명솚??(留덉씠洹몃젅?댁뀡)
    try:
        await conn.execute("SELECT content_type FROM tweets LIMIT 1")
    except Exception:
        await conn.execute("ALTER TABLE tweets ADD COLUMN content_type TEXT DEFAULT 'short'")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type)")
        await conn.commit()

    try:
        await conn.execute("SELECT fingerprint FROM trends LIMIT 1")
    except Exception:
        await conn.execute("ALTER TABLE trends ADD COLUMN fingerprint TEXT DEFAULT ''")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint)")
        await conn.commit()
        await _backfill_fingerprints(conn)

    for _col_name, _col_def in [
        ("posted_at", "TEXT DEFAULT NULL"),
        ("x_tweet_id", "TEXT DEFAULT ''"),
        ("impressions", "INTEGER DEFAULT 0"),
        ("engagements", "INTEGER DEFAULT 0"),
        ("engagement_rate", "REAL DEFAULT 0.0"),
        # v3.0: A/B 蹂??+ 硫?곗뼵??
        ("variant_id", "TEXT DEFAULT ''"),
        ("language", "TEXT DEFAULT 'ko'"),
    ]:
        try:
            await conn.execute(f"SELECT {_col_name} FROM tweets LIMIT 1")
        except Exception:
            await conn.execute(f"ALTER TABLE tweets ADD COLUMN {_col_name} {_col_def}")
            await conn.commit()
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id)")
    await conn.commit()

    # v3.0: trends ?뚯씠釉붿뿉 sentiment, safety_flag 而щ읆 異붽?
    for _col_name, _col_def in [
        ("sentiment", "TEXT DEFAULT 'neutral'"),
        ("safety_flag", "INTEGER DEFAULT 0"),
        # v4.0: ?몃젋??援먯감寃利?& 以묒뿰 ??而щ읆
        ("cross_source_confidence", "INTEGER DEFAULT 0"),
        ("joongyeon_kick", "INTEGER DEFAULT 0"),
        ("joongyeon_angle", "TEXT DEFAULT ''"),
    ]:
        try:
            await conn.execute(f"SELECT {_col_name} FROM trends LIMIT 1")
        except Exception:
            await conn.execute(f"ALTER TABLE trends ADD COLUMN {_col_name} {_col_def}")
            await conn.commit()


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
    """蹂쇰ⅷ??bucket ?ш린濡?踰꾪궥?? config.cache_volume_bucket?쇰줈 ?몃? ?쒖뼱 媛??"""
    if bucket <= 0:
        return volume
    return (volume // bucket) * bucket


def compute_fingerprint(name: str, volume: int, bucket: int = 5000) -> str:
    """
    ?몃젋???묎굅?꾨┛??怨꾩궛.
    bucket: 蹂쇰ⅷ 踰꾪궥 ?ш린 (config.cache_volume_bucket). ?묒쓣?섎줉 ?뺣?.
    """
    normalized_name = _normalize_name(name)
    normalized_volume = _normalize_volume(volume, bucket)
    raw = f"{normalized_name}:{normalized_volume}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
