"""
getdaytrends — PostgreSQL Adapter.
asyncpg 연결을 aiosqlite.Connection 인터페이스와 유사하게 래핑.
db_schema.py에서 분리됨.
"""

import re

from loguru import logger as log


class PgAdapter:
    """
    asyncpg 연결을 aiosqlite.Connection 인터페이스와 유사하게 래핑.
    """

    def __init__(self, conn: "asyncpg.Connection", pool: "asyncpg.Pool | None" = None) -> None:
        self._conn = conn
        self._pool = pool
        self._txn = None  # asyncpg transaction handle

    @staticmethod
    def _ph(sql: str) -> str:
        """
        ? 를 $1, $2 ... PostgreSQL 플레이스홀더로 변환.
        문자열 리터럴 내의 ?는 변환하지 않도록 처리.
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

    @staticmethod
    def _sqlite_compat(sql: str) -> str:
        """Convert SQLite-specific INSERT syntax to PostgreSQL equivalents."""
        upper = sql.lstrip().upper()
        if "INSERT OR REPLACE" in upper:
            # INSERT OR REPLACE INTO table (cols) VALUES (...)
            # → INSERT INTO table (cols) VALUES (...) ON CONFLICT DO UPDATE SET ...
            sql = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", sql, flags=re.IGNORECASE)
            # Extract column names for ON CONFLICT clause
            m = re.search(r"INTO\s+\w+\s*\(([^)]+)\)", sql, re.IGNORECASE)
            if m:
                cols = [c.strip() for c in m.group(1).split(",")]
                # Assume first column is the conflict target (PK)
                conflict_col = cols[0]
                update_parts = [f"{c} = EXCLUDED.{c}" for c in cols[1:]]
                if update_parts:
                    sql = sql.rstrip(";") + f" ON CONFLICT ({conflict_col}) DO UPDATE SET {', '.join(update_parts)}"
                else:
                    sql = sql.rstrip(";") + f" ON CONFLICT ({conflict_col}) DO NOTHING"
        elif "INSERT OR IGNORE" in upper:
            sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.IGNORECASE)
            sql = sql.rstrip(";") + " ON CONFLICT DO NOTHING"
        return sql

    async def execute(self, sql: str, parameters=()):
        # Skip SQLite-only PRAGMA statements
        if sql.strip().upper().startswith("PRAGMA"):
            class NoOpCursor:
                lastrowid = None
                rowcount = 0
                async def fetchone(self): return None
                async def fetchall(self): return []
            return NoOpCursor()

        sql_pg = self._sqlite_compat(self._ph(sql)).rstrip()
        is_insert = sql_pg.lstrip().upper().startswith("INSERT")

        # Only add RETURNING id when there's no ON CONFLICT and no existing RETURNING
        has_conflict = "ON CONFLICT" in sql_pg.upper()
        if is_insert and "RETURNING" not in sql_pg.upper() and not has_conflict:
            sql_pg_with_returning = sql_pg.rstrip(";") + " RETURNING id"
        else:
            sql_pg_with_returning = None

        try:
            if is_insert:
                # Try with RETURNING id first, fall back without if column doesn't exist
                if sql_pg_with_returning:
                    try:
                        row = await self._conn.fetchrow(sql_pg_with_returning, *parameters)
                    except Exception:
                        row = await self._conn.fetchrow(sql_pg, *parameters)
                else:
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
