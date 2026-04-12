import sys
import os
import asyncio
from pathlib import Path

# Add workspace root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from automation.getdaytrends.config import AppConfig
from automation.getdaytrends.db_schema import init_db
from automation.getdaytrends.db_layer import PgAdapter

import aiosqlite
import asyncpg
from loguru import logger as log

async def main():
    config = AppConfig.from_env()
    sqlite_db_path = str(Path(__file__).parent.parent / "data" / "getdaytrends.db")
    
    if not config.database_url:
        log.error("DATABASE_URL is not set in the environment. Cannot connect to Supabase.")
        sys.exit(1)
        
    log.info(f"Source SQLite DB: {sqlite_db_path}")
    masked_url = config.database_url.split('@')[-1] if '@' in config.database_url else "***"
    log.info(f"Target Postgres: {masked_url}")
    
    if not os.path.exists(sqlite_db_path):
        log.warning(f"SQLite DB not found at {sqlite_db_path}. Nothing to migrate.")
        return

    # Initialize PostgreSQL schema first via PgAdapter
    async with asyncpg.create_pool(config.database_url, min_size=1, max_size=2) as pg_pool:
        pg_adapter = PgAdapter(pg_pool, is_transaction=False)
        await init_db(pg_adapter)
        log.info("Initialized PostgreSQL schema.")
        
        # Connect to SQLite
        async with aiosqlite.connect(sqlite_db_path) as sqlite_conn:
            sqlite_conn.row_factory = aiosqlite.Row
            
            tables = [
                "schema_version",
                "runs",
                "trends", 
                "tweets", 
                "meta", 
                "source_quality", 
                "content_feedback", 
                "posting_time_stats", 
                "watchlist_hits"
            ]
            
            for table in tables:
                log.info(f"--- Migrating table '{table}' ---")
                
                # Get columns
                async with sqlite_conn.execute(f"PRAGMA table_info({table})") as cursor:
                    columns_data = await cursor.fetchall()
                    columns = [row["name"] for row in columns_data]
                    pk_cols = [row["name"] for row in columns_data if row["pk"] > 0]
                
                if not columns:
                    log.warning(f"Table '{table}' has no columns or doesn't exist.")
                    continue
                    
                # Read all data
                async with sqlite_conn.execute(f"SELECT * FROM {table}") as cursor:
                    rows = await cursor.fetchall()
                
                if not rows:
                    log.info(f"Table '{table}' is empty. Skipping.")
                    continue
                    
                # Insert to PostgreSQL
                col_names = ", ".join(columns)
                placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
                
                # Construct conflict clause based on PKs
                conflict_clause = ""
                if pk_cols:
                    pk_str = ", ".join(pk_cols)
                    conflict_clause = f"ON CONFLICT ({pk_str}) DO NOTHING"
                elif table == "runs":
                    conflict_clause = "ON CONFLICT (run_uuid) DO NOTHING"
                
                query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) {conflict_clause}"
                
                # Convert rows to plain tuples
                records = [tuple(row[col] for col in columns) for row in rows]
                
                try:
                    await pg_pool.executemany(query, records)
                    log.info(f"Successfully migrated {len(records)} rows into '{table}'.")
                    
                    # Update sequence if auto-increment 'id' column exists
                    if "id" in columns and "id" in pk_cols:
                        try:
                            # It's an integer primary key, safe to assume serial sequence pattern
                            await pg_pool.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
                            log.info(f"Updated sequence for {table}.id")
                        except Exception as seq_err:
                            log.warning(f"Could not update sequence for {table}.id: {seq_err}")
                            
                except Exception as e:
                    log.error(f"Error migrating table '{table}': {e}")
                    
    log.info("Migration complete.")

if __name__ == "__main__":
    asyncio.run(main())
