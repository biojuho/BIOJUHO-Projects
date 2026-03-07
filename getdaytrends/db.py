"""
getdaytrends v3.0 - Database Layer (aiosqlite + asyncpg)
트렌드 히스토리 저장, CRUD 헬퍼 함수.
콘텐츠 핑거프린트 기반 중복 제거 + 스코어 캐시 + 메타 테이블 지원.
DATABASE_URL 환경변수로 PostgreSQL 전환 가능.
v3.0: 트랜잭션 컨텍스트 매니저, asyncpg Pool, _ph() 정규식 개선.
"""

import hashlib
import json
import os
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator

import aiosqlite

from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend

from loguru import logger as log

# ── PostgreSQL 선택적 지원 ────────────────────────────
try:
    import asyncpg
    _PG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# asyncpg 커넥션 풀 (싱글턴)
_PG_POOL: "asyncpg.Pool | None" = None


# ── 트랜잭션 컨텍스트 매니저 ────────────────────────────

@asynccontextmanager
async def db_transaction(conn) -> AsyncIterator[None]:
    """
    aiosqlite / asyncpg 공용 트랜잭션 컨텍스트 매니저.
    예외 발생 시 자동 rollback, 정상 종료 시 commit.

    사용 예::
        async with db_transaction(conn):
            trend_id = await save_trend(conn, trend, run_id)
            await save_tweets_batch(conn, tweets, trend_id, run_id)
    """
    try:
        yield
        await conn.commit()
    except Exception:
        try:
            await conn.rollback()
        except Exception as _rb_err:
            log.debug(f"Rollback 실패 (무시): {_rb_err}")
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
        ? → $1, $2 ... PostgreSQL 플레이스홀더 변환.
        문자열 리터럴 내부의 ? 는 변환하지 않도록 정규식으로 처리.
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
                    async def fetchone(self): return row
                    async def fetchall(self): return [row] if row else []
                return DummyCursor()
            else:
                rows = await self._conn.fetch(sql_pg, *parameters)
                class DummyCursor:
                    lastrowid = None
                    rowcount = len(rows)
                    async def fetchone(self): return rows[0] if rows else None
                    async def fetchall(self): return rows
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
    """asyncpg 커넥션 풀 싱글턴 반환."""
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
            raise ImportError(
                "PostgreSQL 사용을 위해 asyncpg 설치 필요:\n"
                "  pip install asyncpg"
            )
        pool = await get_pg_pool(url)
        pg_conn = await pool.acquire()
        return _PgAdapter(pg_conn)

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db(conn) -> None:
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
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
            posted_at     TEXT DEFAULT NULL,
            impressions   INTEGER DEFAULT 0,
            engagements   INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0
        );

        CREATE INDEX IF NOT EXISTS idx_tweets_trend ON tweets(trend_id);
        CREATE INDEX IF NOT EXISTS idx_tweets_status ON tweets(status);
        CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type);

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

    # 기존 런타임 호환성 (마이그레이션)
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
        ("impressions", "INTEGER DEFAULT 0"),
        ("engagements", "INTEGER DEFAULT 0"),
        ("engagement_rate", "REAL DEFAULT 0.0"),
        # v3.0: A/B 변형 + 멀티언어
        ("variant_id", "TEXT DEFAULT ''"),
        ("language", "TEXT DEFAULT 'ko'"),
    ]:
        try:
            await conn.execute(f"SELECT {_col_name} FROM tweets LIMIT 1")
        except Exception:
            await conn.execute(f"ALTER TABLE tweets ADD COLUMN {_col_name} {_col_def}")
            await conn.commit()

    # v3.0: trends 테이블에 sentiment, safety_flag 컬럼 추가
    for _col_name, _col_def in [
        ("sentiment", "TEXT DEFAULT 'neutral'"),
        ("safety_flag", "INTEGER DEFAULT 0"),
        # v4.0: 트렌드 교차검증 & 중연 킥 컬럼
        ("cross_source_confidence", "INTEGER DEFAULT 0"),
        ("joongyeon_kick", "INTEGER DEFAULT 0"),
        ("joongyeon_angle", "TEXT DEFAULT ''"),
    ]:
        try:
            await conn.execute(f"SELECT {_col_name} FROM trends LIMIT 1")
        except Exception:
            await conn.execute(f"ALTER TABLE trends ADD COLUMN {_col_name} {_col_def}")
            await conn.commit()


async def _backfill_fingerprints(conn) -> None:
    cursor = await conn.execute("SELECT id, keyword, volume_numeric FROM trends WHERE fingerprint = '' OR fingerprint IS NULL")
    rows = await cursor.fetchall()
    if not rows: return
    for row in rows:
        fp = compute_fingerprint(row["keyword"], row["volume_numeric"])
        await conn.execute("UPDATE trends SET fingerprint = ? WHERE id = ?", (fp, row["id"]))
    await conn.commit()


def _normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = name.lower()
    return re.sub(r"[^a-z0-9\uAC00-\uD7A3\u1100-\u11FF]", "", name)


def _normalize_volume(volume: int, bucket: int = 5000) -> int:
    """볼륨을 bucket 크기로 버킷화. config.cache_volume_bucket으로 외부 제어 가능."""
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


async def save_run(conn, run: RunResult) -> int:
    cursor = await conn.execute(
        """INSERT INTO runs (run_uuid, started_at, country, trends_collected,
           trends_scored, tweets_generated, tweets_saved, alerts_sent, errors)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.run_id, run.started_at.isoformat(), run.country, run.trends_collected,
            run.trends_scored, run.tweets_generated, run.tweets_saved, run.alerts_sent,
            json.dumps(run.errors, ensure_ascii=False)
        )
    )
    await conn.commit()
    return cursor.lastrowid


async def update_run(conn, run: RunResult, row_id: int) -> None:
    await conn.execute(
        """UPDATE runs SET finished_at=?, trends_collected=?, trends_scored=?,
           tweets_generated=?, tweets_saved=?, alerts_sent=?, errors=? WHERE id=?""",
        (
            run.finished_at.isoformat() if run.finished_at else None,
            run.trends_collected, run.trends_scored, run.tweets_generated,
            run.tweets_saved, run.alerts_sent, json.dumps(run.errors, ensure_ascii=False), row_id
        )
    )
    await conn.commit()


async def save_trend(conn, trend: ScoredTrend, run_id: int, bucket: int = 5000) -> int:
    """트렌드 저장. bucket은 config.cache_volume_bucket에서 전달받아 fingerprint 정밀도 조정."""
    fingerprint = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket)
    cursor = await conn.execute(
        """INSERT INTO trends (run_id, keyword, rank, volume_raw, volume_numeric,
           viral_potential, trend_acceleration, top_insight, suggested_angles,
           best_hook_starter, country, sources, twitter_context, reddit_context,
           news_context, scored_at, fingerprint, sentiment, safety_flag,
           cross_source_confidence, joongyeon_kick, joongyeon_angle)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, trend.keyword, trend.rank, str(trend.volume_last_24h), trend.volume_last_24h,
            trend.viral_potential, trend.trend_acceleration, trend.top_insight,
            json.dumps(trend.suggested_angles, ensure_ascii=False), trend.best_hook_starter,
            trend.country, json.dumps([s.value for s in trend.sources], ensure_ascii=False),
            trend.context.twitter_insight if trend.context else "",
            trend.context.reddit_insight if trend.context else "",
            trend.context.news_insight if trend.context else "",
            trend.scored_at.isoformat(), fingerprint,
            trend.sentiment, int(trend.safety_flag),
            trend.cross_source_confidence, trend.joongyeon_kick, trend.joongyeon_angle,
        )
    )
    # commit은 호출자(db_transaction)가 담당 — 자체 commit 제거로 트랜잭션 중립 보장
    return cursor.lastrowid


async def save_tweet(conn, tweet: GeneratedTweet, trend_id: int, run_id: int, saved_to: list[str] | None = None) -> int:
    cursor = await conn.execute(
        """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
           is_thread, thread_order, status, saved_to, generated_at, content_type)
           VALUES (?, ?, ?, ?, ?, 0, 0, '대기중', ?, ?, ?)""",
        (
            trend_id, run_id, tweet.tweet_type, tweet.content, tweet.char_count,
            json.dumps(saved_to or ["sqlite"], ensure_ascii=False),
            datetime.now().isoformat(), tweet.content_type
        )
    )
    await conn.commit()
    return cursor.lastrowid


async def save_thread(conn, thread: GeneratedThread, trend_id: int, run_id: int) -> list[int]:
    ids = []
    for i, text in enumerate(thread.tweets):
        cursor = await conn.execute(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
               is_thread, thread_order, status, saved_to, generated_at)
               VALUES (?, ?, '쓰레드', ?, ?, 1, ?, '대기중', '["sqlite"]', ?)""",
            (trend_id, run_id, text, len(text), i, datetime.now().isoformat())
        )
        ids.append(cursor.lastrowid)
    await conn.commit()
    return ids


async def save_tweets_batch(
    conn,
    tweets: list,
    trend_id: int,
    run_id: int,
    is_thread: bool = False,
    saved_to: list[str] | None = None,
) -> None:
    """트윗 배치 저장. variant_id, language 컬럼 포함 (v3.0)."""
    saved_to_json = json.dumps(saved_to or ["sqlite"], ensure_ascii=False)
    now = datetime.now().isoformat()
    if is_thread:
        rows = [
            (trend_id, run_id, "쓰레드", text, len(text), 1, i, "대기중", '["sqlite"]', now, "short", "", "ko")
            for i, text in enumerate(tweets)
        ]
        await conn.executemany(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
                is_thread, thread_order, status, saved_to, generated_at, content_type,
                variant_id, language)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    else:
        rows = [
            (
                trend_id, run_id,
                getattr(t, "tweet_type", ""),
                getattr(t, "content", ""),
                getattr(t, "char_count", len(getattr(t, "content", ""))),
                saved_to_json, now,
                getattr(t, "content_type", "short"),
                getattr(t, "variant_id", ""),
                getattr(t, "language", "ko"),
            )
            for t in tweets
        ]
        await conn.executemany(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
                is_thread, thread_order, status, saved_to, generated_at, content_type,
                variant_id, language)
               VALUES (?, ?, ?, ?, ?, 0, 0, '대기중', ?, ?, ?, ?, ?)""",
            rows,
        )
    # commit은 호출자(db_transaction)가 담당


async def get_trend_history(conn, keyword: str, days: int = 7) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, scored_at FROM trends WHERE keyword = ? AND scored_at >= ? ORDER BY scored_at DESC",
        (keyword, cutoff)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_recent_trends(conn, days: int = 7, min_score: int = 0) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, country, scored_at FROM trends WHERE scored_at >= ? AND viral_potential >= ? ORDER BY viral_potential DESC",
        (cutoff, min_score)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_recently_processed_keywords(conn, hours: int = 3) -> set[str]:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT DISTINCT keyword FROM trends WHERE scored_at >= ?", (cutoff,))
    rows = await cursor.fetchall()
    return {row["keyword"] for row in rows}


async def get_recently_processed_fingerprints(conn, hours: int = 3) -> set[str]:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT DISTINCT fingerprint FROM trends WHERE scored_at >= ? AND fingerprint != ''", (cutoff,))
    rows = await cursor.fetchall()
    return {row["fingerprint"] for row in rows}


async def is_duplicate_trend(conn, name: str, volume: int, hours: int = 3) -> bool:
    fp = compute_fingerprint(name, volume)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT 1 FROM trends WHERE fingerprint = ? AND scored_at >= ? LIMIT 1", (fp, cutoff))
    row = await cursor.fetchone()
    return row is not None


async def cleanup_old_records(conn, days: int = 90) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute("DELETE FROM tweets WHERE generated_at < ?", (cutoff,))
    tweets_deleted = cursor.rowcount
    cursor = await conn.execute("DELETE FROM trends WHERE scored_at < ?", (cutoff,))
    trends_deleted = cursor.rowcount
    await conn.execute("DELETE FROM runs WHERE started_at < ? AND id NOT IN (SELECT DISTINCT run_id FROM trends)", (cutoff,))
    await conn.commit()
    await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    total = tweets_deleted + trends_deleted
    if total: log.info(f"DB 정리 완료: tweets {tweets_deleted}개 + trends {trends_deleted}개 삭제 ({days}일 초과)")
    return total


async def get_trend_stats(conn) -> dict:
    stats = {}
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM runs")
    row = await cursor.fetchone()
    stats["total_runs"] = row["cnt"]
    cursor = await conn.execute("SELECT COUNT(*) as cnt, AVG(viral_potential) as avg_score FROM trends")
    row = await cursor.fetchone()
    stats["total_trends"] = row["cnt"]
    stats["avg_viral_score"] = round(row["avg_score"] or 0, 1)
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM tweets")
    row = await cursor.fetchone()
    stats["total_tweets"] = row["cnt"]
    return stats


async def get_meta(conn, key: str) -> str | None:
    cursor = await conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_meta(conn, key: str, value: str) -> None:
    await conn.execute(
        "INSERT INTO meta (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, datetime.now().isoformat())
    )
    await conn.commit()


async def get_cached_score(conn, fingerprint: str, max_age_hours: int = 6) -> dict | None:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, viral_potential, trend_acceleration, top_insight, suggested_angles, best_hook_starter, scored_at FROM trends WHERE fingerprint = ? AND scored_at >= ? ORDER BY scored_at DESC LIMIT 1",
        (fingerprint, cutoff)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_cached_content(conn, fingerprint: str, max_age_hours: int = 24) -> list[dict] | None:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id WHERE tr.fingerprint = ? AND tr.scored_at >= ? ORDER BY tw.generated_at DESC",
        (fingerprint, cutoff)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows] if rows else None


async def get_recent_avg_viral_score(conn, lookback_hours: int = 3) -> float | None:
    cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()
    cursor = await conn.execute("SELECT AVG(viral_potential) as avg FROM trends WHERE scored_at >= ?", (cutoff,))
    row = await cursor.fetchone()
    if row and dict(row).get("avg") is not None:
        return round(float(row["avg"]), 1)
    return None


async def get_trend_history_batch(conn, keywords: list[str], days: int = 7) -> dict[str, list[dict]]:
    if not keywords: return {}
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(keywords))
    cursor = await conn.execute(
        f"SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, scored_at FROM trends WHERE keyword IN ({placeholders}) AND scored_at >= ? ORDER BY keyword, scored_at DESC",
        (*keywords, cutoff)
    )
    rows = await cursor.fetchall()
    result = {kw: [] for kw in keywords}
    for row in rows:
        result[row["keyword"]].append(dict(row))
    return result


async def record_source_quality(
    conn,
    source: str,
    success: bool,
    latency_ms: float,
    item_count: int = 0,
    quality_score: float = 0.0,
) -> None:
    """
    소스 수집 메트릭 기록.
    source: 'getdaytrends' | 'google_trends' | 'twitter' | 'reddit' | 'news' | 'youtube'
    quality_score: 0.0~1.0 (유용한 내용 비율)
    """
    try:
        await conn.execute(
            """INSERT INTO source_quality (source, recorded_at, success, latency_ms, item_count, quality_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, datetime.now().isoformat(), int(success), latency_ms, item_count, quality_score),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"source_quality 기록 실패 (무시): {e}")


async def get_source_quality_summary(conn, days: int = 7) -> dict:
    """소스별 품질 요약 (success_rate, avg_latency_ms, avg_quality_score, total_calls)."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        """SELECT source,
                  COUNT(*) as total_calls,
                  ROUND(AVG(success) * 100, 1) as success_rate,
                  ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                  ROUND(AVG(quality_score), 3) as avg_quality_score
           FROM source_quality
           WHERE recorded_at >= ?
           GROUP BY source
           ORDER BY source""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    return {row["source"]: dict(row) for row in rows}


async def get_volume_velocity(conn, keyword: str, lookback_runs: int = 3) -> float:
    """
    직전 N런의 볼륨 평균 증가율 반환 (런 당 배율).
    데이터 부족 시 0.0 반환.
    """
    cursor = await conn.execute(
        "SELECT volume_numeric, scored_at FROM trends WHERE keyword = ? "
        "ORDER BY scored_at DESC LIMIT ?",
        (keyword, lookback_runs + 1),
    )
    rows = await cursor.fetchall()
    if len(rows) < 2:
        return 0.0
    volumes = [r["volume_numeric"] for r in rows]
    if volumes[-1] == 0:
        return 0.0
    return (volumes[0] - volumes[-1]) / volumes[-1]


async def get_recent_tweet_contents(conn, keyword: str, hours: int = 24, limit: int = 5) -> list[str]:
    """
    최근 N시간 내 특정 키워드로 생성된 트윗 내용 목록 반환.
    콘텐츠 다양성 프롬프트 주입에 사용.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        """SELECT tw.content FROM tweets tw
           JOIN trends tr ON tw.trend_id = tr.id
           WHERE tr.keyword = ? AND tw.generated_at >= ?
             AND tw.content_type = 'short' AND tw.is_thread = 0
           ORDER BY tw.generated_at DESC LIMIT ?""",
        (keyword, cutoff, limit),
    )
    rows = await cursor.fetchall()
    return [r["content"] for r in rows]


async def record_posting_time_stat(
    conn, category: str, hour: int, engagement_label: str
) -> None:
    """
    게시 시간대별 참여도 학습 기록.
    engagement_label: '높음'=1.0 / '보통'=0.5 / '낮음'=0.2
    """
    score_map = {"높음": 1.0, "보통": 0.5, "낮음": 0.2}
    score = score_map.get(engagement_label, 0.5)
    try:
        await conn.execute(
            """INSERT INTO posting_time_stats (category, hour, total_score, sample_count, updated_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(category, hour) DO UPDATE SET
                   total_score = total_score + excluded.total_score,
                   sample_count = sample_count + 1,
                   updated_at = excluded.updated_at""",
            (category, hour, score, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"posting_time_stat 기록 실패 (무시): {e}")


async def get_best_posting_hours(conn, category: str, top_n: int = 3) -> list[int]:
    """
    카테고리별 평균 참여도 기준 상위 N개 게시 시간대 반환.
    데이터 없으면 빈 리스트 반환.
    """
    cursor = await conn.execute(
        """SELECT hour, total_score / sample_count AS avg_score
           FROM posting_time_stats
           WHERE category = ? AND sample_count >= 3
           ORDER BY avg_score DESC LIMIT ?""",
        (category, top_n),
    )
    rows = await cursor.fetchall()
    return [r["hour"] for r in rows]


async def record_watchlist_hit(
    conn, keyword: str, watchlist_item: str, viral_potential: int
) -> None:
    """Watchlist 키워드 등장 기록."""
    try:
        await conn.execute(
            """INSERT INTO watchlist_hits (keyword, watchlist_item, viral_potential, detected_at)
               VALUES (?, ?, ?, ?)""",
            (keyword, watchlist_item, viral_potential, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"watchlist_hit 기록 실패 (무시): {e}")


async def get_trend_history_patterns_batch(
    conn, keywords: list[str], days: int = 7
) -> dict[str, dict]:
    """
    여러 키워드의 히스토리 패턴을 1회 쿼리로 일괄 조회.
    반환: {keyword: {"seen_count", "avg_score", "score_trend", "is_recurring"}}
    """
    if not keywords:
        return {}
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(keywords))
    cursor = await conn.execute(
        f"SELECT keyword, viral_potential, scored_at FROM trends "
        f"WHERE keyword IN ({placeholders}) AND scored_at >= ? "
        f"ORDER BY keyword, scored_at DESC",
        (*keywords, cutoff),
    )
    rows = await cursor.fetchall()

    # 키워드별 그룹핑
    grouped: dict[str, list[int]] = {kw: [] for kw in keywords}
    for row in rows:
        grouped[row["keyword"]].append(row["viral_potential"])

    result: dict[str, dict] = {}
    for kw, scores in grouped.items():
        if not scores:
            result[kw] = {"seen_count": 0, "avg_score": 0.0, "score_trend": "new", "is_recurring": False}
            continue
        avg = sum(scores) / len(scores)
        if len(scores) >= 2:
            half = len(scores) // 2
            recent_avg = sum(scores[:half]) / max(half, 1)
            older_avg = sum(scores[half:]) / max(len(scores) - half, 1)
            if recent_avg > older_avg + 5:
                trend = "rising"
            elif recent_avg < older_avg - 5:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "new"
        result[kw] = {
            "seen_count": len(scores),
            "avg_score": round(avg, 1),
            "score_trend": trend,
            "is_recurring": len(scores) >= 3,
        }
    return result


async def record_content_feedback(
    conn,
    keyword: str,
    category: str = "",
    qa_score: float = 0.0,
    regenerated: bool = False,
    reason: str = "",
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> None:
    """v6.0/v6.1: 콘텐츠 QA 피드백 + 최신성 기록."""
    try:
        await conn.execute(
            """INSERT INTO content_feedback (keyword, category, qa_score, regenerated, reason, content_age_hours, freshness_grade, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (keyword, category, qa_score, int(regenerated), reason, content_age_hours, freshness_grade, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"content_feedback 기록 실패 (무시): {e}")


