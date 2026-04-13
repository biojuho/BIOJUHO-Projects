from __future__ import annotations

import pytest

from trend_reasoning import upsert_pattern


class _FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.commit_count = 0

    async def execute(self, sql: str, params: tuple) -> None:
        self.calls.append((sql, params))

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_upsert_pattern_qualifies_survival_count_for_postgres_compat() -> None:
    conn = _FakeConn()

    await upsert_pattern(conn, "pattern-1", "Digital fandom spillover", "korea")

    sql, params = conn.calls[0]
    assert "survival_count = trend_patterns.survival_count + 1" in sql
    assert "CASE WHEN trend_patterns.survival_count + 1 >= 3" in sql
    assert params[:3] == ("pattern-1", "Digital fandom spillover", "korea")
    assert conn.commit_count == 1
