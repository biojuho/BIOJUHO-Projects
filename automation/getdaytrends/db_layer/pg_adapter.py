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
