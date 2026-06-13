"""
getdaytrends — SQLite → Supabase PostgreSQL Migration Script.

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_sqlite_to_supabase.py

Features:
    - Initializes PG schema via init_db + supplementary DDL
    - Copies all tables with FK-dependency-aware ordering
    - ON CONFLICT DO NOTHING (idempotent, safe re-runs)
    - Auto-updates SERIAL sequences after bulk insert
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

# Add workspace root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import aiosqlite
import asyncpg
from dotenv import load_dotenv
from loguru import logger as log

# Load root .env for DATABASE_URL
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")


# Supplementary DDL for tables created outside migrations.py
# (trend_reasoning.py tables — uses TEXT primary keys, no AUTOINCREMENT)
_SUPPLEMENTARY_DDL = """
CREATE TABLE IF NOT EXISTS trend_facts (
    fact_id TEXT PRIMARY KEY,
    run_id TEXT,
    fact_text TEXT,
    why_question TEXT,
    category TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS trend_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    hypothesis_text TEXT,
    based_on TEXT,
    related_pattern TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS trend_patterns (
    pattern_id TEXT PRIMARY KEY,
    pattern_text TEXT,
    category TEXT,
    strength TEXT DEFAULT 'emerging',
    survival_count INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
"""


# Tables in FK-dependency order (parents before children)
_MIGRATION_TABLES = [
    # Core (no FK dependencies)
    "schema_version",
    "meta",
    "source_quality",
    "content_feedback",
    "posting_time_stats",
    "watchlist_hits",
    # Reasoning (TEXT PKs, no FKs)
    "trend_facts",
    "trend_hypotheses",
    "trend_patterns",
    # Core chain: runs -> trends -> tweets
    "runs",
    "trends",
    "tweets",
    # Workflow V2 (depends on runs/trends)
    "trend_quarantine",
    "validated_trends",
    "draft_bundles",
    "qa_reports",
    "review_decisions",
    "publish_receipts",
    "feedback_summaries",
    # TAP chain
    "tap_snapshots",
    "tap_snapshot_items",
    "tap_alert_queue",
    "tap_deal_room_events",
    "tap_checkout_sessions",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate getdaytrends SQLite data to Supabase PostgreSQL.")
    parser.add_argument(
        "--database-url",
        default="",
        help="PostgreSQL DATABASE_URL. Defaults to the DATABASE_URL environment variable.",
    )
    parser.add_argument(
        "--sqlite-db-path",
        default=str(Path(__file__).parent.parent / "data" / "getdaytrends.db"),
        help="Source SQLite database path.",
    )
    return parser.parse_args(argv)


async def _init_pg_schema(pg_pool: asyncpg.Pool) -> None:
    """Run init_db + supplementary DDL on PostgreSQL."""
    from automation.getdaytrends.db_layer.pg_adapter import PgAdapter
    from automation.getdaytrends.db_schema import init_db

    conn = await pg_pool.acquire()
    try:
        adapter = PgAdapter(conn, pool=pg_pool)
        await init_db(adapter)
        log.info("Core PG schema initialized via init_db.")

        # Supplementary tables (trend_reasoning)
        for stmt in _SUPPLEMENTARY_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        log.warning(f"Supplementary DDL issue: {e}")
        log.info("Supplementary DDL applied (trend_reasoning tables).")
    finally:
        await pg_pool.release(conn)


async def _get_sqlite_table_info(sqlite_conn, table: str) -> tuple[list[str], list[str]]:
    """Return (column_names, pk_columns) for a SQLite table."""
    async with sqlite_conn.execute(f"PRAGMA table_info({table})") as cursor:
        rows = await cursor.fetchall()
    columns = [row["name"] for row in rows]
    pk_cols = [row["name"] for row in rows if row["pk"] > 0]
    return columns, pk_cols


async def _migrate_table(
    pg_pool: asyncpg.Pool,
    sqlite_conn: aiosqlite.Connection,
    table: str,
) -> int:
    """Migrate a single table from SQLite to PostgreSQL. Returns row count."""
    columns, pk_cols = await _get_sqlite_table_info(sqlite_conn, table)
    if not columns:
        log.warning(f"  [{table}] No columns or doesn't exist in SQLite. Skipping.")
        return 0

    # Read all data
    async with sqlite_conn.execute(f"SELECT * FROM [{table}]") as cursor:
        rows = await cursor.fetchall()
    if not rows:
        log.info(f"  [{table}] Empty. Skipping.")
        return 0

    query = _insert_query(table, columns, pk_cols)
    records = [tuple(row[col] for col in columns) for row in rows]

    try:
        await pg_pool.executemany(query, records)
        log.info(f"  [{table}] Migrated {len(records)} rows.")
        await _update_serial_sequence(pg_pool, table, columns, pk_cols)
        return len(records)
    except Exception as e:
        log.error(f"  [{table}] Migration error: {e}")
        return 0


def _insert_query(table: str, columns: list[str], pk_cols: list[str]) -> str:
    col_names = ", ".join(columns)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    conflict_clause = _conflict_clause(table, pk_cols)
    return f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) {conflict_clause}"


def _conflict_clause(table: str, pk_cols: list[str]) -> str:
    if pk_cols:
        return f"ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
    if table == "runs":
        return "ON CONFLICT (run_uuid) DO NOTHING"
    return ""


async def _update_serial_sequence(
    pg_pool: asyncpg.Pool,
    table: str,
    columns: list[str],
    pk_cols: list[str],
) -> None:
    if "id" not in columns or "id" not in pk_cols:
        return
    try:
        await pg_pool.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
        log.info(f"  [{table}] Sequence updated.")
    except Exception as seq_err:
        log.debug(f"  [{table}] Sequence update skipped: {seq_err}")


async def _verify_migration(pg_pool: asyncpg.Pool, sqlite_conn: aiosqlite.Connection) -> None:
    """Compare row counts between SQLite and PostgreSQL."""
    log.info("\n=== Migration Verification ===")
    mismatches = []
    for table in _MIGRATION_TABLES:
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

    if mismatches:
        log.warning(f"\n{len(mismatches)} table(s) have row count mismatches: {mismatches}")
    else:
        log.info("\nAll tables verified: row counts match!")


async def _run_migration(database_url: str, sqlite_db_path: str) -> None:
    masked_url = database_url.split("@")[-1] if "@" in database_url else "***"
    log.info(f"Source SQLite: {sqlite_db_path}")
    log.info(f"Target PG:    {masked_url}")

    if not os.path.exists(sqlite_db_path):
        log.warning(f"SQLite DB not found at {sqlite_db_path}. Nothing to migrate.")
        return

    # Create backup
    backup_path = sqlite_db_path + ".bak"
    if not os.path.exists(backup_path):
        import shutil

        shutil.copy2(sqlite_db_path, backup_path)
        log.info(f"SQLite backup created: {backup_path}")

    async with asyncpg.create_pool(database_url, min_size=1, max_size=5, statement_cache_size=0) as pg_pool:
        # Phase 1: Initialize PG schema
        log.info("\n=== Phase 1: Schema Initialization ===")
        await _init_pg_schema(pg_pool)

        # Phase 2: Migrate data
        log.info("\n=== Phase 2: Data Migration ===")
        async with aiosqlite.connect(sqlite_db_path) as sqlite_conn:
            sqlite_conn.row_factory = aiosqlite.Row

            total_rows = 0
            for table in _MIGRATION_TABLES:
                count = await _migrate_table(pg_pool, sqlite_conn, table)
                total_rows += count

            log.info(f"\nTotal rows migrated: {total_rows}")

            # Phase 3: Verify
            log.info("\n=== Phase 3: Verification ===")
            await _verify_migration(pg_pool, sqlite_conn)

    log.info("\nMigration complete!")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    database_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not database_url:
        log.error("DATABASE_URL is not set in the environment. Cannot connect to Supabase.")
        return 1
    asyncio.run(_run_migration(database_url, args.sqlite_db_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
