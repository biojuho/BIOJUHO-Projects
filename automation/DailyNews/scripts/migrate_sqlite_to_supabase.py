"""
DailyNews — SQLite -> Supabase PostgreSQL Migration Script.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import aiosqlite
import asyncpg
from dotenv import load_dotenv
from loguru import logger as log

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

_PIPELINE_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS job_runs (run_id TEXT PRIMARY KEY, job_name TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, summary_json TEXT, error_text TEXT, processed_count INTEGER NOT NULL DEFAULT 0, published_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS article_cache (link TEXT NOT NULL, category TEXT NOT NULL DEFAULT '', window_name TEXT NOT NULL DEFAULT '', source TEXT, first_seen_at TEXT NOT NULL, notion_page_id TEXT, last_run_id TEXT, PRIMARY KEY (link, category, window_name));
CREATE TABLE IF NOT EXISTS content_reports (report_id TEXT PRIMARY KEY, category TEXT NOT NULL, window_name TEXT NOT NULL, window_start TEXT NOT NULL, window_end TEXT NOT NULL, summary_json TEXT NOT NULL, insights_json TEXT NOT NULL, drafts_json TEXT NOT NULL, notion_page_id TEXT, asset_status TEXT NOT NULL, approval_state TEXT NOT NULL, source_links_json TEXT NOT NULL, status TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notebooklm_metadata_json TEXT NOT NULL DEFAULT '{}', fact_check_score REAL NOT NULL DEFAULT 0, quality_state TEXT NOT NULL DEFAULT 'ok', generation_mode TEXT NOT NULL DEFAULT '', analysis_meta_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS channel_publications (report_id TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, external_url TEXT, updated_at TEXT NOT NULL, PRIMARY KEY (report_id, channel));
CREATE TABLE IF NOT EXISTS llm_cache (prompt_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL, model_name TEXT, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, cache_hits INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, expires_at TEXT);
CREATE TABLE IF NOT EXISTS x_daily_posts (post_date TEXT PRIMARY KEY, post_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS topic_timeline (topic_id TEXT PRIMARY KEY, topic_label TEXT NOT NULL, category TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, occurrence_count INTEGER NOT NULL DEFAULT 1, report_ids_json TEXT NOT NULL DEFAULT '[]', embedding_json TEXT);
CREATE TABLE IF NOT EXISTS x_tweet_metrics (tweet_id TEXT PRIMARY KEY, report_id TEXT, content_preview TEXT, impressions INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, retweets INTEGER DEFAULT 0, replies INTEGER DEFAULT 0, quotes INTEGER DEFAULT 0, bookmarks INTEGER DEFAULT 0, published_at TEXT NOT NULL, last_fetched_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feed_etag_cache (url TEXT PRIMARY KEY, etag TEXT, last_modified TEXT, last_fetched_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fact_fragments (fact_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, fact_text TEXT NOT NULL, why_question TEXT NOT NULL, category TEXT NOT NULL, source_title TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hypotheses (hypothesis_id TEXT PRIMARY KEY, hypothesis_text TEXT NOT NULL, based_on_facts_json TEXT NOT NULL DEFAULT '[]', related_pattern TEXT, status TEXT NOT NULL DEFAULT 'pending', counter_evidence TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reasoning_patterns (pattern_id TEXT PRIMARY KEY, pattern_text TEXT NOT NULL, category TEXT NOT NULL, evidence_facts_json TEXT NOT NULL DEFAULT '[]', survival_count INTEGER NOT NULL DEFAULT 1, strength TEXT NOT NULL DEFAULT 'emerging', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS digest_queue (digest_id TEXT PRIMARY KEY, report_ids_json TEXT NOT NULL DEFAULT '[]', summary_text TEXT, serial_number TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_article_cache_category_window ON article_cache(category, window_name);
CREATE INDEX IF NOT EXISTS idx_article_cache_link ON article_cache(link);
CREATE INDEX IF NOT EXISTS idx_content_reports_fingerprint ON content_reports(fingerprint);
CREATE INDEX IF NOT EXISTS idx_llm_cache_expires ON llm_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_topic_timeline_category ON topic_timeline(category, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_x_tweet_metrics_report ON x_tweet_metrics(report_id);
CREATE INDEX IF NOT EXISTS idx_fact_fragments_report ON fact_fragments(report_id);
CREATE INDEX IF NOT EXISTS idx_fact_fragments_category ON fact_fragments(category, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_reasoning_patterns_category ON reasoning_patterns(category, survival_count DESC);
CREATE INDEX IF NOT EXISTS idx_digest_queue_status ON digest_queue(status);
"""

_CHECKPOINTS_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    job_id TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    current_step TEXT NOT NULL,
    state_json JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'running',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_SIGNAL_DDL = """
CREATE TABLE IF NOT EXISTS signal_history (
    id            SERIAL PRIMARY KEY,
    keyword       TEXT NOT NULL,
    composite_score DOUBLE PRECISION NOT NULL,
    sources       TEXT NOT NULL,
    source_count  INTEGER NOT NULL,
    arbitrage_type TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    velocity      DOUBLE PRECISION DEFAULT 0.0,
    category_hint TEXT DEFAULT '',
    detected_at   TEXT NOT NULL,
    raw_data      TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sh_keyword_detected ON signal_history(keyword, detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_detected ON signal_history(detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_score ON signal_history(composite_score);
"""

# Tables matched to DB files
_PIPELINE_TABLES = [
    "schema_version",
    "job_runs",
    "article_cache",
    "content_reports",
    "channel_publications",
    "llm_cache",
    "x_daily_posts",
    "topic_timeline",
    "x_tweet_metrics",
    "feed_etag_cache",
    "fact_fragments",
    "hypotheses",
    "reasoning_patterns",
    "digest_queue",
    "pipeline_checkpoints" # also in pipeline_state.db
]

_SIGNAL_TABLES = [
    "signal_history"
]

async def _init_pg_schema(pg_pool: asyncpg.Pool) -> None:
    conn = await pg_pool.acquire()
    try:
        combined_ddl = _PIPELINE_DDL + "\n" + _CHECKPOINTS_DDL + "\n" + _SIGNAL_DDL
        for stmt in combined_ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        log.warning(f"DDL issue: {e}")
        log.info("PG Schema initialized.")
    finally:
        await pg_pool.release(conn)

async def _get_sqlite_table_info(sqlite_conn, table: str) -> tuple[list[str], list[str]]:
    async with sqlite_conn.execute(f"PRAGMA table_info({table})") as cursor:
        rows = await cursor.fetchall()
    columns = [row["name"] for row in rows]
    pk_cols = [row["name"] for row in rows if row["pk"] > 0]
    return columns, pk_cols

async def _migrate_table(pg_pool: asyncpg.Pool, sqlite_conn: aiosqlite.Connection, table: str) -> int:
    try:
        columns, pk_cols = await _get_sqlite_table_info(sqlite_conn, table)
        if not columns:
            return 0

        async with sqlite_conn.execute(f"SELECT * FROM [{table}]") as cursor:
            rows = await cursor.fetchall()
            
        if not rows:
            return 0

        col_names = ", ".join(columns)
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))

        conflict_clause = ""
        if pk_cols:
            pk_str = ", ".join(pk_cols)
            conflict_clause = f"ON CONFLICT ({pk_str}) DO NOTHING"
        elif table == "schema_version":
            # No PK for schema_version
            pass

        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) {conflict_clause}"
        records = [tuple(str(row[col]) if isinstance(row[col], (dict, list)) else row[col] for col in columns) for row in rows]

        await pg_pool.executemany(query, records)
        log.info(f"  [{table}] Migrated {len(records)} rows.")

        if "id" in columns and "id" in pk_cols:
            try:
                await pg_pool.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
            except Exception:
                pass
        return len(records)
    except Exception as e:
        log.error(f"  [{table}] Migration error: {e}")
        return 0

async def _verify_migration(pg_pool: asyncpg.Pool, sqlite_db, tables: list[str]) -> None:
    mismatches = []
    async with aiosqlite.connect(sqlite_db) as sqlite_conn:
        for table in tables:
            try:
                async with sqlite_conn.execute(f"SELECT count(1) FROM [{table}]") as cursor:
                    sqlite_row = await cursor.fetchone()
                sqlite_count = sqlite_row[0] if sqlite_row else 0
            except Exception:
                sqlite_count = 0

            try:
                pg_row = await pg_pool.fetchrow(f"SELECT count(1) FROM {table}")
                pg_count = pg_row[0] if pg_row else 0
            except Exception:
                pg_count = -1

            match = "OK" if sqlite_count == pg_count else "MISMATCH"
            if match == "MISMATCH":
                mismatches.append(table)
            log.info(f"  {table}: SQLite={sqlite_count} | PG={pg_count} [{match}]")

    return mismatches

async def main():
    database_url = os.getenv("DATABASE_URL", os.getenv("SUPABASE_DATABASE_URL", ""))
    if not database_url:
        log.error("DATABASE_URL / SUPABASE_DATABASE_URL is not set in the environment.")
        sys.exit(1)

    data_dir = Path(__file__).parent.parent / "data"
    pipeline_db = str(data_dir / "pipeline_state.db")
    signal_db = str(data_dir / "signal_watch.db")

    log.info(f"Target PG: {database_url.split('@')[-1] if '@' in database_url else '***'}")
    log.info(f"Source SQLite (Pipeline): {pipeline_db}")
    log.info(f"Source SQLite (Signal):   {signal_db}")

    async with asyncpg.create_pool(database_url, min_size=1, max_size=5, statement_cache_size=0) as pg_pool:
        log.info("\n=== Phase 1: Schema Initialization ===")
        await _init_pg_schema(pg_pool)

        log.info("\n=== Phase 2: Pipeline Data Migration ===")
        if os.path.exists(pipeline_db):
            async with aiosqlite.connect(pipeline_db) as sqlite_conn:
                sqlite_conn.row_factory = aiosqlite.Row
                for table in _PIPELINE_TABLES:
                    await _migrate_table(pg_pool, sqlite_conn, table)
        else:
            log.info("pipeline_state.db not found. Skipping.")

        log.info("\n=== Phase 3: Signal Data Migration ===")
        if os.path.exists(signal_db):
            async with aiosqlite.connect(signal_db) as sqlite_conn:
                sqlite_conn.row_factory = aiosqlite.Row
                for table in _SIGNAL_TABLES:
                    await _migrate_table(pg_pool, sqlite_conn, table)
        else:
            log.info("signal_watch.db not found. Skipping.")

        log.info("\n=== Phase 4: Verification ===")
        m1 = []
        if os.path.exists(pipeline_db):
            m1 = await _verify_migration(pg_pool, pipeline_db, _PIPELINE_TABLES)
        
        m2 = []
        if os.path.exists(signal_db):
            m2 = await _verify_migration(pg_pool, signal_db, _SIGNAL_TABLES)
        
        mismatches = m1 + m2
        if mismatches:
            log.warning(f"Table(s) with row count mismatches: {mismatches}")
        else:
            log.info("All tables verified: row counts match!")

if __name__ == "__main__":
    asyncio.run(main())
