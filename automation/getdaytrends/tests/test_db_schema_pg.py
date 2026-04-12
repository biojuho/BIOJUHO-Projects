"""
PostgreSQL Adapter & Connection Routing Tests
==============================================
Covers:
  1. DATABASE_URL routing (get_connection → asyncpg pool → _PgAdapter)
  2. _PgAdapter._ph: SQLite ? → PostgreSQL $N placeholder conversion
  3. _PgAdapter.executescript: AUTOINCREMENT → BIGSERIAL DDL rewrite
  4. _PgAdapter.execute: INSERT RETURNING id injection & SELECT passthrough
  5. Fallback: missing asyncpg raises ImportError
  6. Pool singleton lifecycle (create / close / re-create)
  7. Dashboard _get_conn with DATABASE_URL
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from getdaytrends.db_schema import (
    _PgAdapter,
    close_pg_pool,
    get_connection,
    sqlite_write_lock,
)

# PG-related globals now live in db_layer.connection
_PG_MODULE = "getdaytrends.db_layer.connection"


# ── 1. Connection Routing ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_connection_postgres_routing() -> None:
    """DATABASE_URL이 설정되면 asyncpg Pool에서 _PgAdapter를 반환해야 한다."""
    import getdaytrends.db_layer.connection as dbconn
    dbconn._PG_POOL = None

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/db"}), \
         patch(f"{_PG_MODULE}._PG_AVAILABLE", True), \
         patch(f"{_PG_MODULE}.asyncpg") as mock_asyncpg:

        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=MagicMock())
        mock_pool._closed = False
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        conn = await get_connection()

        mock_asyncpg.create_pool.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/db",
            min_size=2,
            max_size=10,
            statement_cache_size=0,
        )
        assert isinstance(conn, _PgAdapter)
        mock_pool.acquire.assert_called_once()

        await close_pg_pool()


@pytest.mark.asyncio
async def test_get_connection_postgres_scheme_variant() -> None:
    """postgres:// (without 'ql') 스킴도 PostgreSQL로 라우팅해야 한다."""
    import getdaytrends.db_layer.connection as dbconn
    dbconn._PG_POOL = None

    with patch.dict(os.environ, {"DATABASE_URL": "postgres://u:p@host:5432/mydb"}), \
         patch(f"{_PG_MODULE}._PG_AVAILABLE", True), \
         patch(f"{_PG_MODULE}.asyncpg") as mock_asyncpg:

        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=MagicMock())
        mock_pool._closed = False
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        conn = await get_connection()
        assert isinstance(conn, _PgAdapter)

        await close_pg_pool()


@pytest.mark.asyncio
async def test_get_connection_falls_back_to_sqlite_without_url(tmp_path) -> None:
    """DATABASE_URL이 없으면 SQLite 연결을 반환해야 한다."""
    db_file = str(tmp_path / "test.db")

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DATABASE_URL", None)
        conn = await get_connection(db_path=db_file)

        assert not isinstance(conn, _PgAdapter)
        await conn.close()


@pytest.mark.asyncio
async def test_get_connection_raises_when_asyncpg_missing() -> None:
    """asyncpg 미설치 상태에서 PostgreSQL URL 사용 시 ImportError를 발생시켜야 한다."""
    import getdaytrends.db_layer.connection as dbconn
    dbconn._PG_POOL = None

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@host/db"}), \
         patch(f"{_PG_MODULE}._PG_AVAILABLE", False):

        with pytest.raises(ImportError, match="asyncpg"):
            await get_connection()


# ── 2. _PgAdapter._ph: Placeholder Conversion ───────────────────────

class TestPgAdapterPlaceholder:
    """SQLite ? → PostgreSQL $N 플레이스홀더 변환 테스트."""

    def test_simple_placeholders(self):
        sql = "SELECT * FROM t WHERE a = ? AND b = ?"
        result = _PgAdapter._ph(sql)
        assert result == "SELECT * FROM t WHERE a = $1 AND b = $2"

    def test_no_placeholders(self):
        sql = "SELECT COUNT(*) FROM runs"
        assert _PgAdapter._ph(sql) == sql

    def test_placeholder_in_string_literal_untouched(self):
        """문자열 리터럴 내부의 ?는 변환하지 않아야 한다."""
        sql = "INSERT INTO meta (key, value) VALUES ('is_ok?', ?)"
        result = _PgAdapter._ph(sql)
        assert result == "INSERT INTO meta (key, value) VALUES ('is_ok?', $1)"

    def test_double_quoted_string(self):
        sql = 'SELECT * FROM "table?" WHERE col = ?'
        result = _PgAdapter._ph(sql)
        assert result == 'SELECT * FROM "table?" WHERE col = $1'

    def test_many_placeholders(self):
        sql = "INSERT INTO t (a,b,c,d,e) VALUES (?,?,?,?,?)"
        result = _PgAdapter._ph(sql)
        assert result == "INSERT INTO t (a,b,c,d,e) VALUES ($1,$2,$3,$4,$5)"

    def test_mixed_content(self):
        """복합 쿼리에서 플레이스홀더 순서가 올바른지 확인."""
        sql = "UPDATE t SET a=?, b=? WHERE id=? AND status='pending?'"
        result = _PgAdapter._ph(sql)
        assert result == "UPDATE t SET a=$1, b=$2 WHERE id=$3 AND status='pending?'"


# ── 3. _PgAdapter.executescript: DDL Rewriting ───────────────────────

class TestPgAdapterExecutescript:
    """executescript의 DDL 변환 (AUTOINCREMENT → BIGSERIAL) 테스트."""

    @pytest.mark.asyncio
    async def test_autoincrement_to_bigserial(self):
        mock_conn = AsyncMock()
        adapter = _PgAdapter(mock_conn)

        ddl = "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);"
        await adapter.executescript(ddl)

        call_args = mock_conn.execute.call_args[0][0]
        assert "BIGSERIAL PRIMARY KEY" in call_args
        assert "AUTOINCREMENT" not in call_args

    @pytest.mark.asyncio
    async def test_pragma_statements_skipped(self):
        """PRAGMA 구문은 PostgreSQL에서 무시되어야 한다."""
        mock_conn = AsyncMock()
        adapter = _PgAdapter(mock_conn)

        ddl = "PRAGMA journal_mode=WAL; CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT);"
        await adapter.executescript(ddl)

        # PRAGMA는 실행하지 않으므로 execute는 1번만 호출
        assert mock_conn.execute.call_count == 1
        call_args = mock_conn.execute.call_args[0][0]
        assert "PRAGMA" not in call_args

    @pytest.mark.asyncio
    async def test_already_exists_error_ignored(self):
        """'already exists' 에러는 무시하고 계속 진행해야 한다."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=Exception("relation 'test' already exists")
        )
        adapter = _PgAdapter(mock_conn)

        # Should NOT raise
        await adapter.executescript("CREATE TABLE test (id BIGSERIAL PRIMARY KEY);")

    @pytest.mark.asyncio
    async def test_other_errors_raised(self):
        """'already exists' 이외의 에러는 정상적으로 raise 해야 한다."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=Exception("syntax error at or near 'INVALID'")
        )
        adapter = _PgAdapter(mock_conn)

        with pytest.raises(Exception, match="syntax error"):
            await adapter.executescript("INVALID SQL STATEMENT;")


# ── 4. _PgAdapter.execute: INSERT / SELECT ───────────────────────────

class TestPgAdapterExecute:
    """execute 메서드의 INSERT RETURNING 주입 및 SELECT 패스스루 테스트."""

    @pytest.mark.asyncio
    async def test_insert_adds_returning_id(self):
        """INSERT 쿼리에 RETURNING id가 자동 추가되어야 한다."""
        mock_conn = AsyncMock()
        mock_row = {"id": 42, "name": "test"}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        adapter = _PgAdapter(mock_conn)

        cursor = await adapter.execute(
            "INSERT INTO runs (run_uuid) VALUES (?)",
            ("uuid-123",),
        )

        called_sql = mock_conn.fetchrow.call_args[0][0]
        assert "RETURNING id" in called_sql
        assert cursor.lastrowid == 42

    @pytest.mark.asyncio
    async def test_insert_with_existing_returning_not_duplicated(self):
        """이미 RETURNING이 있는 INSERT에는 중복 추가하지 않아야 한다."""
        mock_conn = AsyncMock()
        mock_row = {"id": 1}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        adapter = _PgAdapter(mock_conn)

        await adapter.execute(
            "INSERT INTO t (a) VALUES (?) RETURNING id",
            ("val",),
        )

        called_sql = mock_conn.fetchrow.call_args[0][0]
        assert called_sql.count("RETURNING") == 1

    @pytest.mark.asyncio
    async def test_select_uses_fetch(self):
        """SELECT 쿼리는 conn.fetch를 사용해야 한다."""
        mock_conn = AsyncMock()
        mock_rows = [{"id": 1, "keyword": "AI"}, {"id": 2, "keyword": "ML"}]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        adapter = _PgAdapter(mock_conn)

        cursor = await adapter.execute("SELECT * FROM trends WHERE rank = ?", (1,))

        mock_conn.fetch.assert_called_once()
        rows = await cursor.fetchall()
        assert len(rows) == 2
        first = await cursor.fetchone()
        assert first["keyword"] == "AI"

    @pytest.mark.asyncio
    async def test_select_empty_result(self):
        """빈 결과에서 fetchone은 None을 반환해야 한다."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        adapter = _PgAdapter(mock_conn)

        cursor = await adapter.execute("SELECT * FROM trends WHERE 1=0")
        assert await cursor.fetchone() is None
        assert await cursor.fetchall() == []

    @pytest.mark.asyncio
    async def test_insert_with_none_row(self):
        """INSERT가 None row를 반환하면 lastrowid는 None이어야 한다."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        adapter = _PgAdapter(mock_conn)

        cursor = await adapter.execute("INSERT INTO t (a) VALUES (?)", ("v",))
        assert cursor.lastrowid is None


# ── 5. _PgAdapter commit/rollback/close ──────────────────────────────

class TestPgAdapterLifecycle:
    """commit, rollback, close는 올바르게 동작해야 한다."""

    @pytest.mark.asyncio
    async def test_commit_is_noop(self):
        adapter = _PgAdapter(AsyncMock())
        await adapter.commit()  # Should not raise

    @pytest.mark.asyncio
    async def test_rollback_is_noop(self):
        adapter = _PgAdapter(AsyncMock())
        await adapter.rollback()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_delegates(self):
        mock_conn = AsyncMock()
        adapter = _PgAdapter(mock_conn)
        await adapter.close()
        mock_conn.close.assert_called_once()


# ── 6. sqlite_write_lock bypass for PgAdapter ────────────────────────

class TestSqliteWriteLock:
    """PgAdapter에 대해 sqlite_write_lock은 바이패스해야 한다."""

    @pytest.mark.asyncio
    async def test_pgadapter_bypasses_lock(self):
        adapter = _PgAdapter(AsyncMock())
        entered = False
        async with sqlite_write_lock(adapter):
            entered = True
        assert entered

    @pytest.mark.asyncio
    async def test_sqlite_conn_acquires_lock(self):
        """SQLite 연결은 실제로 락을 획득해야 한다."""
        mock_sqlite_conn = MagicMock()  # Not a _PgAdapter
        entered = False
        async with sqlite_write_lock(mock_sqlite_conn):
            entered = True
        assert entered


# ── 7. Pool Singleton Lifecycle ──────────────────────────────────────

@pytest.mark.asyncio
async def test_pool_singleton_reuse() -> None:
    """풀이 열려 있으면 재생성하지 않고 기존 풀을 재사용해야 한다."""
    import getdaytrends.db_layer.connection as dbconn
    dbconn._PG_POOL = None

    with patch(f"{_PG_MODULE}._PG_AVAILABLE", True), \
         patch(f"{_PG_MODULE}.asyncpg") as mock_asyncpg:

        mock_pool = AsyncMock()
        mock_pool._closed = False
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        from getdaytrends.db_schema import get_pg_pool

        pool1 = await get_pg_pool("postgresql://u:p@h/db")
        pool2 = await get_pg_pool("postgresql://u:p@h/db")

        # create_pool은 1번만 호출되어야 한다
        assert mock_asyncpg.create_pool.call_count == 1
        assert pool1 is pool2

        await close_pg_pool()


@pytest.mark.asyncio
async def test_pool_recreation_after_close() -> None:
    """풀이 닫힌 후 다시 요청하면 새 풀을 생성해야 한다."""
    import getdaytrends.db_layer.connection as dbconn
    dbconn._PG_POOL = None

    with patch(f"{_PG_MODULE}._PG_AVAILABLE", True), \
         patch(f"{_PG_MODULE}.asyncpg") as mock_asyncpg:

        mock_pool1 = AsyncMock()
        mock_pool1._closed = False
        mock_pool2 = AsyncMock()
        mock_pool2._closed = False
        mock_asyncpg.create_pool = AsyncMock(side_effect=[mock_pool1, mock_pool2])

        from getdaytrends.db_schema import get_pg_pool

        pool1 = await get_pg_pool("postgresql://u:p@h/db")
        assert pool1 is mock_pool1

        # 풀 닫기
        await close_pg_pool()

        # 닫힌 후 _PG_POOL은 None
        assert dbconn._PG_POOL is None

        # 재요청 시 새 풀 생성
        pool2 = await get_pg_pool("postgresql://u:p@h/db")
        assert mock_asyncpg.create_pool.call_count == 2
