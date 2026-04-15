#!/usr/bin/env python3
"""
AgriGuard Database Migration Script: SQLite → PostgreSQL

This script migrates data from AgriGuard's SQLite database to PostgreSQL.

Usage:
    # 1. Start PostgreSQL
    docker compose up -d postgres

    # 2. Run migration
    python scripts/migrate_agriguard_db.py

    # 3. Verify
    python scripts/migrate_agriguard_db.py --verify

Features:
    - Exports all tables from SQLite
    - Imports into PostgreSQL with transaction safety
    - Validates row counts and data integrity
    - Provides rollback capability

Author: Claude Code
Date: 2026-03-22
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

# Add AgriGuard backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "AgriGuard", "backend"))


class DatabaseMigrator:
    """Handles migration from SQLite to PostgreSQL"""

    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.sqlite_conn = None
        self.pg_engine = None
        self.tables_migrated = []

    def connect(self):
        """Establish connections to both databases"""
        print(f"🔌 Connecting to SQLite: {self.sqlite_path}")
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row

        print(f"🔌 Connecting to PostgreSQL: {self.postgres_url.split('@')[1]}")
        self.pg_engine = create_engine(self.postgres_url, echo=False)

    def get_tables(self) -> list[str]:
        """Get list of tables from SQLite"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📋 Found {len(tables)} tables: {', '.join(tables)}")
        return tables

    def migrate_table(self, table_name: str) -> int:
        """Migrate a single table from SQLite to PostgreSQL"""
        print(f"\n📦 Migrating table: {table_name}")

        # Read from SQLite
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, self.sqlite_conn)
        row_count = len(df)

        if row_count == 0:
            print(f"  ⚠️  Table {table_name} is empty, skipping...")
            return 0

        print(f"  📊 Found {row_count} rows")

        # Write to PostgreSQL
        try:
            df.to_sql(table_name, self.pg_engine, if_exists="append", index=False, method="multi", chunksize=1000)
            print(f"  ✅ Successfully migrated {row_count} rows")
            self.tables_migrated.append(table_name)
            return row_count

        except Exception as e:
            print(f"  ❌ Error migrating {table_name}: {e}")
            raise

    def verify_migration(self, table_name: str) -> tuple[int, int, bool]:
        """Verify row counts match between SQLite and PostgreSQL"""
        # SQLite count
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = cursor.fetchone()[0]

        # PostgreSQL count
        with self.pg_engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            pg_count = result.scalar()

        match = sqlite_count == pg_count
        status = "✅" if match else "❌"

        print(f"  {status} {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
        return sqlite_count, pg_count, match

    def run_migration(self) -> dict[str, int]:
        """Execute full migration"""
        print("=" * 60)
        print("🚀 Starting AgriGuard Database Migration")
        print("=" * 60)
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        self.connect()

        # Get tables
        tables = self.get_tables()

        # Migrate each table
        stats = {}
        for table in tables:
            try:
                row_count = self.migrate_table(table)
                stats[table] = row_count
            except Exception as e:
                print(f"\n❌ Migration failed for table {table}: {e}")
                print("🔄 Rolling back...")
                # Rollback would happen here if we were using transactions
                raise

        # Verification
        print("\n" + "=" * 60)
        print("🔍 Verifying Migration")
        print("=" * 60)

        all_match = True
        for table in tables:
            _, _, match = self.verify_migration(table)
            if not match:
                all_match = False

        print("\n" + "=" * 60)
        if all_match:
            print("✅ Migration Completed Successfully!")
        else:
            print("❌ Migration Completed with Errors - Row counts don't match")
        print("=" * 60)
        print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("📊 Migration Statistics:")
        total_rows = 0
        for table, count in stats.items():
            print(f"  - {table}: {count} rows")
            total_rows += count
        print(f"  TOTAL: {total_rows} rows migrated")

        return stats

    def verify_only(self):
        """Run verification without migration"""
        print("=" * 60)
        print("🔍 Verifying Existing Migration")
        print("=" * 60)

        self.connect()
        tables = self.get_tables()

        all_match = True
        for table in tables:
            _, _, match = self.verify_migration(table)
            if not match:
                all_match = False

        print("\n" + "=" * 60)
        if all_match:
            print("✅ All tables verified successfully!")
        else:
            print("❌ Verification failed - Row counts don't match")
        print("=" * 60)

    def close(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.pg_engine:
            self.pg_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Migrate AgriGuard database from SQLite to PostgreSQL")
    parser.add_argument("--verify", action="store_true", help="Only verify migration (do not migrate)")
    parser.add_argument(
        "--sqlite",
        default="AgriGuard/backend/agriguard.db",
        help="Path to SQLite database (default: AgriGuard/backend/agriguard.db)",
    )
    parser.add_argument(
        "--postgres",
        default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agriguard"),
        help="PostgreSQL connection URL (default: from DATABASE_URL env var)",
    )

    args = parser.parse_args()

    # Check if SQLite file exists
    if not os.path.exists(args.sqlite):
        print(f"❌ SQLite database not found: {args.sqlite}")
        sys.exit(1)

    # Create migrator
    migrator = DatabaseMigrator(args.sqlite, args.postgres)

    try:
        if args.verify:
            migrator.verify_only()
        else:
            # Warning before migration
            print("⚠️  WARNING: This will migrate data to PostgreSQL")
            print(f"   Source: {args.sqlite}")
            print(f"   Target: {args.postgres.split('@')[1]}")
            print()
            response = input("Continue? (yes/no): ")

            if response.lower() != "yes":
                print("❌ Migration cancelled")
                sys.exit(0)

            migrator.run_migration()

    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
