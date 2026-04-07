"""
getdaytrends - Database Schema & Connection Layer
PostgreSQL ?대뙌?? DB ?곌껐, ?ㅽ궎留?珥덇린??諛?留덉씠洹몃젅?댁뀡.
db.py?먯꽌 遺꾨━??
"""

import hashlib
import os
import re
import threading
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import aiosqlite
from loguru import logger as log

# === PostgreSQL ?좏깮??吏??===
try:
    import asyncpg

    _PG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# asyncpg 而ㅻ꽖??? (?깃???
_PG_POOL: "asyncpg.Pool | None" = None
_SQLITE_WRITE_LOCK = threading.RLock()


# === ?몃옖??뀡 而⑦뀓?ㅽ듃 留ㅻ땲? ===


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

    ?ъ슜 ??
        async with db_transaction(conn):
            trend_id = await save_trend(conn, trend, run_id)
            await save_tweets_batch(conn, tweets, trend_id, run_id)
    """
    async with sqlite_write_lock(conn):
        # C-03 fix: PgAdapter에서 실제 트랜잭션을 시작
        if isinstance(conn, _PgAdapter) and conn._txn is None:
            conn._txn = conn._conn.transaction()
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


class _PgAdapter:
    """
    asyncpg ?곌껐??aiosqlite.Connection ?명꽣?섏씠?ㅼ? ?좎궗?섍쾶 ?섑븨.
    """

    def __init__(self, conn: "asyncpg.Connection", pool: "asyncpg.Pool | None" = None) -> None:
        self._conn = conn
        self._pool = pool
        self._txn = None  # asyncpg transaction handle

    @staticmethod
    def _ph(sql: str) -> str:
        """
        ? 瑜?$1, $2 ... PostgreSQL ?뚮젅?댁뒪??붾줈 蹂??
        臾몄옄??由ы꽣???대??????蹂?섑븯吏 ?딅룄濡?泥섎━.
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
                if ch == str_char:
                    # BUG-018 fix: Handle '' (SQL standard doubled-quote escape)
                    if i + 1 < len(sql) and sql[i + 1] == str_char:
                        result.append(ch)
                        result.append(sql[i + 1])
                        i += 2
                        continue
                    in_str = False
                result.append(ch)
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
        # BUG-006 fix: commit the active transaction if one exists
        if self._txn is not None:
            await self._txn.commit()
            self._txn = None

    async def rollback(self):
        # BUG-006 fix: rollback the active transaction if one exists
        if self._txn is not None:
            await self._txn.rollback()
            self._txn = None

    async def close(self):
        # BUG-005 fix: release connection back to pool instead of closing it
        if self._txn is not None:
            try:
                await self._txn.rollback()
            except Exception:
                pass
            self._txn = None
        if self._pool is not None:
            await self._pool.release(self._conn)
        else:
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
            raise ImportError("PostgreSQL ?ъ슜???꾪빐 asyncpg ?ㅼ튂 ?꾩슂:\n  pip install asyncpg")
        pool = await get_pg_pool(url)
        pg_conn = await pool.acquire()
        # BUG-005 fix: pass pool reference so close() can release
        return _PgAdapter(pg_conn, pool=pool)

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
            status        TEXT DEFAULT '?湲곗쨷',
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

        CREATE TABLE IF NOT EXISTS trend_quarantine (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT DEFAULT '',
            fingerprint      TEXT DEFAULT '',
            reason_code      TEXT NOT NULL,
            reason_detail    TEXT DEFAULT '',
            source_count     INTEGER DEFAULT 0,
            freshness_minutes INTEGER DEFAULT 0,
            payload_json     TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tq_reason_created ON trend_quarantine(reason_code, created_at);

        CREATE TABLE IF NOT EXISTS validated_trends (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id         TEXT NOT NULL UNIQUE,
            trend_row_id     INTEGER REFERENCES trends(id),
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            source_count     INTEGER DEFAULT 0,
            evidence_refs    TEXT DEFAULT '[]',
            freshness_minutes INTEGER DEFAULT 0,
            dedup_fingerprint TEXT DEFAULT '',
            lifecycle_status TEXT DEFAULT 'validated',
            scoring_axes     TEXT DEFAULT '{}',
            scoring_reasons  TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vt_keyword_status ON validated_trends(keyword, lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_vt_fingerprint ON validated_trends(dedup_fingerprint);

        CREATE TABLE IF NOT EXISTS draft_bundles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL UNIQUE,
            trend_id         TEXT NOT NULL REFERENCES validated_trends(trend_id),
            trend_row_id     INTEGER REFERENCES trends(id),
            platform         TEXT NOT NULL,
            content_type     TEXT NOT NULL,
            body             TEXT NOT NULL,
            hashtags         TEXT DEFAULT '[]',
            prompt_version   TEXT DEFAULT '',
            generator_provider TEXT DEFAULT '',
            generator_model  TEXT DEFAULT '',
            source_evidence_ref TEXT DEFAULT '',
            degraded_mode    INTEGER DEFAULT 0,
            lifecycle_status TEXT DEFAULT 'drafted',
            review_status    TEXT DEFAULT 'Draft',
            qa_score         REAL DEFAULT 0.0,
            blocking_reasons TEXT DEFAULT '[]',
            notion_page_id   TEXT DEFAULT '',
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            receipt_id       TEXT DEFAULT '',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_db_status_platform ON draft_bundles(review_status, platform);
        CREATE INDEX IF NOT EXISTS idx_db_lifecycle ON draft_bundles(lifecycle_status, updated_at);

        CREATE TABLE IF NOT EXISTS qa_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            total_score      REAL DEFAULT 0.0,
            passed           INTEGER DEFAULT 0,
            warnings         TEXT DEFAULT '[]',
            blocking_reasons TEXT DEFAULT '[]',
            report_payload   TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qa_draft_created ON qa_reports(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS review_decisions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            decision         TEXT NOT NULL,
            reviewed_by      TEXT DEFAULT '',
            reviewed_at      TEXT NOT NULL,
            review_note      TEXT DEFAULT '',
            source           TEXT DEFAULT 'manual',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rd_draft_created ON review_decisions(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS publish_receipts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id       TEXT NOT NULL UNIQUE,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            platform         TEXT NOT NULL,
            success          INTEGER DEFAULT 0,
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            failure_code     TEXT DEFAULT '',
            failure_reason   TEXT DEFAULT '',
            collector_due_at TEXT DEFAULT NULL,
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pr_draft_created ON publish_receipts(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS feedback_summaries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            receipt_id       TEXT NOT NULL REFERENCES publish_receipts(receipt_id),
            metric_window    TEXT DEFAULT '',
            impressions      INTEGER DEFAULT 0,
            engagements      INTEGER DEFAULT 0,
            clicks           INTEGER DEFAULT 0,
            collector_status TEXT DEFAULT '',
            strategy_notes   TEXT DEFAULT '',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fs_receipt_created ON feedback_summaries(receipt_id, created_at);

        CREATE TABLE IF NOT EXISTS tap_snapshots (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id        TEXT NOT NULL UNIQUE,
            target_country     TEXT DEFAULT '',
            total_detected     INTEGER DEFAULT 0,
            teaser_count       INTEGER DEFAULT 0,
            generated_at       TEXT NOT NULL,
            future_dependencies TEXT DEFAULT '[]',
            source             TEXT DEFAULT 'tap_service',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshots_country_created ON tap_snapshots(target_country, created_at);

        CREATE TABLE IF NOT EXISTS tap_snapshot_items (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id           TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            item_order            INTEGER DEFAULT 0,
            keyword               TEXT NOT NULL,
            source_country        TEXT DEFAULT '',
            target_countries      TEXT DEFAULT '[]',
            viral_score           INTEGER DEFAULT 0,
            priority              REAL DEFAULT 0.0,
            time_gap_hours        REAL DEFAULT 0.0,
            paywall_tier          TEXT DEFAULT 'premium',
            public_teaser         TEXT DEFAULT '',
            recommended_platforms TEXT DEFAULT '[]',
            recommended_angle     TEXT DEFAULT '',
            execution_notes       TEXT DEFAULT '[]',
            publish_window_json   TEXT DEFAULT '{}',
            revenue_play_json     TEXT DEFAULT '{}',
            created_at            TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshot_items_snapshot_order ON tap_snapshot_items(snapshot_id, item_order);

        CREATE TABLE IF NOT EXISTS tap_alert_queue (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            dedupe_key         TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            source_country     TEXT DEFAULT '',
            paywall_tier       TEXT DEFAULT 'premium',
            priority           REAL DEFAULT 0.0,
            viral_score        INTEGER DEFAULT 0,
            alert_message      TEXT DEFAULT '',
            metadata_json      TEXT DEFAULT '{}',
            lifecycle_status   TEXT DEFAULT 'queued',
            queued_at          TEXT NOT NULL,
            dispatched_at      TEXT DEFAULT NULL,
            last_attempt_at    TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_status_country ON tap_alert_queue(lifecycle_status, target_country, queued_at);
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_dedupe ON tap_alert_queue(dedupe_key, queued_at);

        CREATE TABLE IF NOT EXISTS tap_deal_room_events (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            audience_segment   TEXT DEFAULT '',
            package_tier       TEXT DEFAULT 'premium_alert_bundle',
            offer_tier         TEXT DEFAULT 'premium',
            event_type         TEXT NOT NULL,
            price_anchor       TEXT DEFAULT '',
            checkout_handle    TEXT DEFAULT '',
            session_id         TEXT DEFAULT '',
            actor_id           TEXT DEFAULT '',
            revenue_value      REAL DEFAULT 0.0,
            metadata_json      TEXT DEFAULT '{}',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_keyword_type_created ON tap_deal_room_events(keyword, event_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_country_package_created ON tap_deal_room_events(target_country, package_tier, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_session_created ON tap_deal_room_events(session_id, created_at);

        CREATE TABLE IF NOT EXISTS tap_checkout_sessions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            checkout_session_id TEXT NOT NULL UNIQUE,
            checkout_handle     TEXT DEFAULT '',
            snapshot_id         TEXT DEFAULT '',
            keyword             TEXT NOT NULL,
            target_country      TEXT DEFAULT '',
            audience_segment    TEXT DEFAULT '',
            package_tier        TEXT DEFAULT 'premium_alert_bundle',
            offer_tier          TEXT DEFAULT 'premium',
            session_status      TEXT DEFAULT 'created',
            payment_status      TEXT DEFAULT '',
            currency            TEXT DEFAULT 'usd',
            quoted_price_value  REAL DEFAULT 0.0,
            revenue_value       REAL DEFAULT 0.0,
            checkout_url        TEXT DEFAULT '',
            actor_id            TEXT DEFAULT '',
            stripe_customer_id  TEXT DEFAULT '',
            stripe_event_id     TEXT DEFAULT '',
            metadata_json       TEXT DEFAULT '{}',
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            completed_at        TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_status_created ON tap_checkout_sessions(session_status, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_keyword_created ON tap_checkout_sessions(keyword, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_handle_created ON tap_checkout_sessions(checkout_handle, created_at);

        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            applied_at  TEXT NOT NULL
        );
    """)
    await conn.commit()

    # ?? 踰꾩쟾 湲곕컲 留덉씠洹몃젅?댁뀡 ??
    await _run_migrations(conn)


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Schema Migration Infrastructure
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧

_CURRENT_SCHEMA_VERSION = 11


async def _get_schema_version(conn) -> int:
    """?꾩옱 DB ?ㅽ궎留?踰꾩쟾 議고쉶. schema_version ?뚯씠釉??놁쑝硫?0."""
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
    """?뚯씠釉붿쓽 而щ읆 ?대쫫 紐⑸줉 諛섑솚 (SQLite PRAGMA / PostgreSQL information_schema ?명솚)."""
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
    """v1: tweets.content_type 異붽? (?⑤Ц/?λЦ 援щ텇)."""
    cols = await _table_columns(conn, "tweets")
    if "content_type" not in cols:
        await conn.execute("ALTER TABLE tweets ADD COLUMN content_type TEXT DEFAULT 'short'")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type)")
        await conn.commit()


async def _migrate_v2(conn) -> None:
    """v2: trends.fingerprint 異붽? (罹먯떆 ??."""
    cols = await _table_columns(conn, "trends")
    if "fingerprint" not in cols:
        await conn.execute("ALTER TABLE trends ADD COLUMN fingerprint TEXT DEFAULT ''")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint)")
        await conn.commit()
        await _backfill_fingerprints(conn)


async def _migrate_v3(conn) -> None:
    """v3: tweets ?깃낵異붿쟻 + A/B 蹂??+ ?ㅺ뎅??而щ읆."""
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
    """v4: trends 媛먯꽦?꾪꽣 + 援먯감寃利?+ 以묒뿰??"""
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
    """v5: schema_version ?뚯씠釉??먯껜 (?대? CREATE TABLE濡??앹꽦??. 留덉빱 ?꾩슜."""
    pass


async def _migrate_v6(conn) -> None:
    """v6: 100x ?ㅼ????鍮??꾨씫 ?몃뜳??異붽?."""
    # trends: 罹먯떆 議고쉶 理쒖쟻??(fingerprint + scored_at 蹂듯빀)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trends_fp_scored ON trends(fingerprint, scored_at)"
    )
    # tweets: cleanup/?뺣━ 荑쇰━ 理쒖쟻??
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tweets_generated_at ON tweets(generated_at)"
    )
    # tweets: 寃뚯떆 ?곹깭 異붿쟻 理쒖쟻??
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at)"
    )
    await conn.commit()


# 留덉씠洹몃젅?댁뀡 ?덉??ㅽ듃由? (踰꾩쟾, ?ㅻ챸, ?⑥닔)
async def _migrate_v7(conn) -> None:
    """v7: workflow V2 tables for review queue, manual publish, and feedback."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS trend_quarantine (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT DEFAULT '',
            fingerprint      TEXT DEFAULT '',
            reason_code      TEXT NOT NULL,
            reason_detail    TEXT DEFAULT '',
            source_count     INTEGER DEFAULT 0,
            freshness_minutes INTEGER DEFAULT 0,
            payload_json     TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tq_reason_created ON trend_quarantine(reason_code, created_at);

        CREATE TABLE IF NOT EXISTS validated_trends (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id         TEXT NOT NULL UNIQUE,
            trend_row_id     INTEGER REFERENCES trends(id),
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            source_count     INTEGER DEFAULT 0,
            evidence_refs    TEXT DEFAULT '[]',
            freshness_minutes INTEGER DEFAULT 0,
            dedup_fingerprint TEXT DEFAULT '',
            lifecycle_status TEXT DEFAULT 'validated',
            scoring_axes     TEXT DEFAULT '{}',
            scoring_reasons  TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vt_keyword_status ON validated_trends(keyword, lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_vt_fingerprint ON validated_trends(dedup_fingerprint);

        CREATE TABLE IF NOT EXISTS draft_bundles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL UNIQUE,
            trend_id         TEXT NOT NULL REFERENCES validated_trends(trend_id),
            trend_row_id     INTEGER REFERENCES trends(id),
            platform         TEXT NOT NULL,
            content_type     TEXT NOT NULL,
            body             TEXT NOT NULL,
            hashtags         TEXT DEFAULT '[]',
            prompt_version   TEXT DEFAULT '',
            generator_provider TEXT DEFAULT '',
            generator_model  TEXT DEFAULT '',
            source_evidence_ref TEXT DEFAULT '',
            degraded_mode    INTEGER DEFAULT 0,
            lifecycle_status TEXT DEFAULT 'drafted',
            review_status    TEXT DEFAULT 'Draft',
            qa_score         REAL DEFAULT 0.0,
            blocking_reasons TEXT DEFAULT '[]',
            notion_page_id   TEXT DEFAULT '',
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            receipt_id       TEXT DEFAULT '',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_db_status_platform ON draft_bundles(review_status, platform);
        CREATE INDEX IF NOT EXISTS idx_db_lifecycle ON draft_bundles(lifecycle_status, updated_at);

        CREATE TABLE IF NOT EXISTS qa_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            total_score      REAL DEFAULT 0.0,
            passed           INTEGER DEFAULT 0,
            warnings         TEXT DEFAULT '[]',
            blocking_reasons TEXT DEFAULT '[]',
            report_payload   TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qa_draft_created ON qa_reports(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS review_decisions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            decision         TEXT NOT NULL,
            reviewed_by      TEXT DEFAULT '',
            reviewed_at      TEXT NOT NULL,
            review_note      TEXT DEFAULT '',
            source           TEXT DEFAULT 'manual',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rd_draft_created ON review_decisions(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS publish_receipts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id       TEXT NOT NULL UNIQUE,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            platform         TEXT NOT NULL,
            success          INTEGER DEFAULT 0,
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            failure_code     TEXT DEFAULT '',
            failure_reason   TEXT DEFAULT '',
            collector_due_at TEXT DEFAULT NULL,
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pr_draft_created ON publish_receipts(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS feedback_summaries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            receipt_id       TEXT NOT NULL REFERENCES publish_receipts(receipt_id),
            metric_window    TEXT DEFAULT '',
            impressions      INTEGER DEFAULT 0,
            engagements      INTEGER DEFAULT 0,
            clicks           INTEGER DEFAULT 0,
            collector_status TEXT DEFAULT '',
            strategy_notes   TEXT DEFAULT '',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fs_receipt_created ON feedback_summaries(receipt_id, created_at);
    """)
    await conn.commit()


async def _migrate_v8(conn) -> None:
    """v8: TAP board snapshot tables for premium/public product feeds."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_snapshots (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id        TEXT NOT NULL UNIQUE,
            target_country     TEXT DEFAULT '',
            total_detected     INTEGER DEFAULT 0,
            teaser_count       INTEGER DEFAULT 0,
            generated_at       TEXT NOT NULL,
            future_dependencies TEXT DEFAULT '[]',
            source             TEXT DEFAULT 'tap_service',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshots_country_created ON tap_snapshots(target_country, created_at);

        CREATE TABLE IF NOT EXISTS tap_snapshot_items (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id           TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            item_order            INTEGER DEFAULT 0,
            keyword               TEXT NOT NULL,
            source_country        TEXT DEFAULT '',
            target_countries      TEXT DEFAULT '[]',
            viral_score           INTEGER DEFAULT 0,
            priority              REAL DEFAULT 0.0,
            time_gap_hours        REAL DEFAULT 0.0,
            paywall_tier          TEXT DEFAULT 'premium',
            public_teaser         TEXT DEFAULT '',
            recommended_platforms TEXT DEFAULT '[]',
            recommended_angle     TEXT DEFAULT '',
            execution_notes       TEXT DEFAULT '[]',
            publish_window_json   TEXT DEFAULT '{}',
            revenue_play_json     TEXT DEFAULT '{}',
            created_at            TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshot_items_snapshot_order ON tap_snapshot_items(snapshot_id, item_order);
    """)
    await conn.commit()


async def _migrate_v9(conn) -> None:
    """v9: TAP premium alert queue table for monetizable dispatch workflows."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_alert_queue (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            dedupe_key         TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            source_country     TEXT DEFAULT '',
            paywall_tier       TEXT DEFAULT 'premium',
            priority           REAL DEFAULT 0.0,
            viral_score        INTEGER DEFAULT 0,
            alert_message      TEXT DEFAULT '',
            metadata_json      TEXT DEFAULT '{}',
            lifecycle_status   TEXT DEFAULT 'queued',
            queued_at          TEXT NOT NULL,
            dispatched_at      TEXT DEFAULT NULL,
            last_attempt_at    TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_status_country ON tap_alert_queue(lifecycle_status, target_country, queued_at);
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_dedupe ON tap_alert_queue(dedupe_key, queued_at);
    """)
    await conn.commit()


async def _migrate_v10(conn) -> None:
    """v10: TAP deal-room funnel events for teaser/click/purchase learning."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_deal_room_events (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            audience_segment   TEXT DEFAULT '',
            package_tier       TEXT DEFAULT 'premium_alert_bundle',
            offer_tier         TEXT DEFAULT 'premium',
            event_type         TEXT NOT NULL,
            price_anchor       TEXT DEFAULT '',
            checkout_handle    TEXT DEFAULT '',
            session_id         TEXT DEFAULT '',
            actor_id           TEXT DEFAULT '',
            revenue_value      REAL DEFAULT 0.0,
            metadata_json      TEXT DEFAULT '{}',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_keyword_type_created ON tap_deal_room_events(keyword, event_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_country_package_created ON tap_deal_room_events(target_country, package_tier, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_session_created ON tap_deal_room_events(session_id, created_at);
    """)
    await conn.commit()


async def _migrate_v11(conn) -> None:
    """v11: TAP checkout session ops table for Stripe session tracking."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_checkout_sessions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            checkout_session_id TEXT NOT NULL UNIQUE,
            checkout_handle     TEXT DEFAULT '',
            snapshot_id         TEXT DEFAULT '',
            keyword             TEXT NOT NULL,
            target_country      TEXT DEFAULT '',
            audience_segment    TEXT DEFAULT '',
            package_tier        TEXT DEFAULT 'premium_alert_bundle',
            offer_tier          TEXT DEFAULT 'premium',
            session_status      TEXT DEFAULT 'created',
            payment_status      TEXT DEFAULT '',
            currency            TEXT DEFAULT 'usd',
            quoted_price_value  REAL DEFAULT 0.0,
            revenue_value       REAL DEFAULT 0.0,
            checkout_url        TEXT DEFAULT '',
            actor_id            TEXT DEFAULT '',
            stripe_customer_id  TEXT DEFAULT '',
            stripe_event_id     TEXT DEFAULT '',
            metadata_json       TEXT DEFAULT '{}',
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            completed_at        TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_status_created ON tap_checkout_sessions(session_status, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_keyword_created ON tap_checkout_sessions(keyword, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_handle_created ON tap_checkout_sessions(checkout_handle, created_at);
    """)
    await conn.commit()


_MIGRATIONS: list[tuple[int, str, any]] = [
    (1, "tweets.content_type column", _migrate_v1),
    (2, "trends.fingerprint column + index", _migrate_v2),
    (3, "tweets metrics + A/B + multi-country", _migrate_v3),
    (4, "trends sentiment filter + genealogy + dedup", _migrate_v4),
    (5, "schema_version table init", _migrate_v5),
    (6, "100x scale composite indexes", _migrate_v6),
    (7, "workflow V2 review queue tables", _migrate_v7),
    (8, "TAP product snapshot tables", _migrate_v8),
    (9, "TAP premium alert queue", _migrate_v9),
    (10, "TAP deal-room funnel events", _migrate_v10),
    (11, "TAP checkout session ops", _migrate_v11),
]


async def _reconcile_latest_schema(conn) -> None:
    """Backfill required columns when the schema marker drifted from actual columns."""
    await _migrate_v1(conn)
    await _migrate_v2(conn)
    await _migrate_v3(conn)
    await _migrate_v4(conn)
    await _migrate_v7(conn)
    await _migrate_v8(conn)
    await _migrate_v9(conn)
    await _migrate_v10(conn)
    await _migrate_v11(conn)


async def _run_migrations(conn) -> None:
    """?꾩옱 踰꾩쟾 ?뺤씤 ??誘몄쟻??留덉씠洹몃젅?댁뀡 ?쒖감 ?ㅽ뻾."""
    current = await _get_schema_version(conn)

    if current >= _CURRENT_SCHEMA_VERSION:
        await _reconcile_latest_schema(conn)
        return

    # 湲곗〈 DB (schema_version ?놁씠 ?대? 而щ읆???덈뒗 寃쎌슦) ???곹깭 媛먯?
    if current == 0:
        try:
            cols = await _table_columns(conn, "trends")
            if "joongyeon_angle" in cols:
                # v4源뚯? ?대? ?곸슜??湲곗〈 DB ??v4濡??먰봽
                current = 4
                for v in range(1, 5):
                    desc = next(d for ver, d, _ in _MIGRATIONS if ver == v)
                    await _set_schema_version(conn, v, f"{desc} (湲곗〈 媛먯?)")
        except Exception:
            pass

    pending = [(v, d, fn) for v, d, fn in _MIGRATIONS if v > current]
    if not pending:
        # 理쒖떊?몃뜲 schema_version ?덉퐫?쒕쭔 ?녿뒗 寃쎌슦
        if current == 0:
            await _set_schema_version(conn, _CURRENT_SCHEMA_VERSION, "珥덇린 ?ㅼ튂")
        await _reconcile_latest_schema(conn)
        return

    for version, description, migrate_fn in pending:
        log.info(f"[DB Migration] v{version}: {description}")
        await migrate_fn(conn)
        await _set_schema_version(conn, version, description)

    await _reconcile_latest_schema(conn)

    log.info(f"[DB Migration] ?꾨즺: v{current} ??v{_CURRENT_SCHEMA_VERSION}")


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

