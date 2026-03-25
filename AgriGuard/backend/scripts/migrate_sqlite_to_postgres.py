"""AgriGuard — SQLite → PostgreSQL Data Migration Script.

Usage:
    # Dry-run (read-only, counts rows only):
    python scripts/migrate_sqlite_to_postgres.py --dry-run

    # Actual migration:
    DATABASE_URL=postgresql://user:pw@host/db python scripts/migrate_sqlite_to_postgres.py

Requires: psycopg2-binary (or psycopg2), sqlalchemy
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


# Table migration order (respects FK dependencies)
TABLE_ORDER = [
    "users",
    "products",
    "tracking_events",
    "certificates",
    "sensor_readings",
]

BATCH_SIZE = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate AgriGuard data from SQLite to PostgreSQL.",
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "agriguard.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection URL (default: $DATABASE_URL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing to PostgreSQL.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Rows per INSERT batch (default: {BATCH_SIZE}).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE target tables before migration (DANGEROUS).",
    )
    return parser.parse_args()


def read_sqlite_table(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[tuple]]:
    """Read all rows from a SQLite table, returning (columns, rows)."""
    cursor = conn.execute(f'SELECT * FROM "{table}"')
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return columns, rows


def insert_batch_pg(session: Session, table: str, columns: list[str], rows: list[tuple]) -> int:
    """Insert a batch of rows into PostgreSQL. Returns inserted count."""
    if not rows:
        return 0

    col_list = ", ".join(f'"{c}"' for c in columns)
    param_list = ", ".join(f":{c}" for c in columns)
    stmt = text(f'INSERT INTO "{table}" ({col_list}) VALUES ({param_list})')

    row_dicts = [dict(zip(columns, row)) for row in rows]
    session.execute(stmt, row_dicts)
    return len(row_dicts)


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_engine,
    table: str,
    batch_size: int,
    dry_run: bool,
    truncate: bool,
) -> dict:
    """Migrate a single table. Returns stats dict."""
    columns, rows = read_sqlite_table(sqlite_conn, table)
    total = len(rows)

    result = {"table": table, "source_rows": total, "migrated": 0, "skipped": False, "error": None}

    if total == 0:
        print(f"  ⏭️  {table}: 0 rows — skipped")
        result["skipped"] = True
        return result

    if dry_run:
        print(f"  🔍 {table}: {total:,} rows (dry-run, no write)")
        result["migrated"] = total
        return result

    try:
        with pg_engine.begin() as conn:
            session = Session(bind=conn)

            if truncate:
                session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
                print(f"  🗑️  {table}: TRUNCATED")

            migrated = 0
            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                migrated += insert_batch_pg(session, table, columns, batch)

            result["migrated"] = migrated
            print(f"  ✅ {table}: {migrated:,}/{total:,} rows migrated")

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ {table}: FAILED — {e}")

    return result


def main() -> int:
    args = parse_args()

    # Validate SQLite source
    if not args.sqlite_db.exists():
        print(f"❌ SQLite database not found: {args.sqlite_db}")
        return 1

    # Validate PostgreSQL target
    if not args.dry_run and not args.pg_url:
        print("❌ DATABASE_URL not set. Use --pg-url or set DATABASE_URL environment variable.")
        print("   For dry-run: add --dry-run flag")
        return 1

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"AgriGuard SQLite → PostgreSQL Migration [{mode}]")
    print(f"{'='*60}")
    print(f"Source: {args.sqlite_db}")
    print(f"Target: {args.pg_url[:50]}..." if args.pg_url else "Target: (dry-run)")
    print(f"Batch size: {args.batch_size}")
    print()

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(str(args.sqlite_db))

    # Connect to PostgreSQL (skip for dry-run)
    pg_engine = None
    if not args.dry_run:
        try:
            pg_engine = create_engine(args.pg_url, pool_pre_ping=True)
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ PostgreSQL connection verified\n")
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            return 1

    # Migrate tables in FK-dependency order
    start = time.time()
    results = []
    for table in TABLE_ORDER:
        result = migrate_table(sqlite_conn, pg_engine, table, args.batch_size, args.dry_run, args.truncate)
        results.append(result)

    elapsed = time.time() - start

    # Summary
    total_source = sum(r["source_rows"] for r in results)
    total_migrated = sum(r["migrated"] for r in results)
    errors = [r for r in results if r["error"]]

    print(f"\n{'='*60}")
    print(f"Migration {'Preview' if args.dry_run else 'Complete'}")
    print(f"{'='*60}")
    print(f"Total rows: {total_source:,}")
    print(f"Migrated:   {total_migrated:,}")
    print(f"Errors:     {len(errors)}")
    print(f"Duration:   {elapsed:.2f}s")

    if errors:
        print("\n⚠️  Errors:")
        for r in errors:
            print(f"  - {r['table']}: {r['error']}")
        return 1

    sqlite_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
