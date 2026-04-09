"""
getdaytrends - Database Schema & Connection Layer
PostgreSQL 대응 DB 연결, 스키마 초기화 및 마이그레이션.

모듈 분리 구조:
  - db_layer/pg_adapter.py  : PostgreSQL 어댑터 (PgAdapter)
  - db_layer/connection.py  : 연결 관리 (get_connection, get_pg_pool, ...)
  - db_layer/migrations.py  : 스키마 마이그레이션 (v1~v11)
  - db_schema.py (이 파일)  : DDL 스키마, init_db, fingerprint 유틸 + re-exports
"""

import hashlib
import re
import unicodedata

from loguru import logger as log


# ── Lazy re-exports for backward compat ──
# These are imported at module level but from submodules that do NOT
# import db_schema back (breaking the circular chain).

def __getattr__(name):
    """Lazy import to avoid circular dependency with db_layer/__init__.py."""
    _CONNECTION_NAMES = {
        "sqlite_write_lock", "db_transaction", "get_pg_pool",
        "close_pg_pool", "get_connection",
    }
    _PG_ADAPTER_NAMES = {"_PgAdapter"}

    if name in _CONNECTION_NAMES:
        try:
            from .db_layer.connection import (
                sqlite_write_lock, db_transaction, get_pg_pool,
                close_pg_pool, get_connection,
            )
        except ImportError:
            from db_layer.connection import (
                sqlite_write_lock, db_transaction, get_pg_pool,
                close_pg_pool, get_connection,
            )
        return locals()[name]
    if name in _PG_ADAPTER_NAMES:
        try:
            from .db_layer.pg_adapter import PgAdapter
        except ImportError:
            from db_layer.pg_adapter import PgAdapter
        return PgAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# === DDL 스키마 초기화 ===

async def _init_db_unlocked(conn) -> None:
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout=30000")
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
        CREATE INDEX IF NOT EXISTS idx_trends_fp_scored ON trends(fingerprint, scored_at);

        CREATE TABLE IF NOT EXISTS tweets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id      INTEGER NOT NULL REFERENCES trends(id),
            run_id        INTEGER NOT NULL REFERENCES runs(id),
            tweet_type    TEXT NOT NULL,
            content       TEXT NOT NULL,
            char_count    INTEGER DEFAULT 0,
            is_thread     INTEGER DEFAULT 0,
            thread_order  INTEGER DEFAULT 0,
            status        TEXT DEFAULT '\ub300\uae30\uc911',
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
        CREATE INDEX IF NOT EXISTS idx_tweets_generated_at ON tweets(generated_at);
        CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at);

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

    # 버전 기반 마이그레이션 실행
    try:
        from .db_layer.migrations import run_migrations
    except ImportError:
        from db_layer.migrations import run_migrations
    await run_migrations(conn)


async def init_db(conn) -> None:
    try:
        from .db_layer.connection import sqlite_write_lock
    except ImportError:
        from db_layer.connection import sqlite_write_lock
    async with sqlite_write_lock(conn):
        await _init_db_unlocked(conn)


# === Fingerprint 유틸리티 ===


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
    """Round volume down to nearest bucket size for cache dedup."""
    if bucket <= 0:
        return volume
    return (volume // bucket) * bucket


def compute_fingerprint(name: str, volume: int, bucket: int = 5000) -> str:
    """Compute trend dedup fingerprint. bucket: volume bucketing size."""
    normalized_name = _normalize_name(name)
    normalized_volume = _normalize_volume(volume, bucket)
    raw = f"{normalized_name}:{normalized_volume}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
