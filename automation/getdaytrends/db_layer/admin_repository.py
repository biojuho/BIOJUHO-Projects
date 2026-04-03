"""Admin Repository"""

from datetime import datetime, timedelta

from . import log, sqlite_write_lock

async def _cleanup_old_records_unlocked(conn, days: int = 90) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute("DELETE FROM tweets WHERE generated_at < ?", (cutoff,))
    tweets_deleted = cursor.rowcount
    cursor = await conn.execute("DELETE FROM trends WHERE scored_at < ?", (cutoff,))
    trends_deleted = cursor.rowcount
    await conn.execute(
        "DELETE FROM runs WHERE started_at < ? AND id NOT IN (SELECT DISTINCT run_id FROM trends)", (cutoff,)
    )
    await conn.commit()
    await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    total = tweets_deleted + trends_deleted
    if total:
        log.info(f"DB 정리 완료: tweets {tweets_deleted}건 + trends {trends_deleted}건 삭제 ({days}일 초과)")
    return total

async def cleanup_old_records(conn, days: int = 90) -> int:
    async with sqlite_write_lock(conn):
        return await _cleanup_old_records_unlocked(conn, days=days)

async def get_trend_stats(conn) -> dict:
    stats = {}
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM runs")
    row = await cursor.fetchone()
    stats["total_runs"] = row["cnt"]
    cursor = await conn.execute("SELECT COUNT(*) as cnt, AVG(viral_potential) as avg_score FROM trends")
    row = await cursor.fetchone()
    stats["total_trends"] = row["cnt"]
    stats["avg_viral_score"] = round(row["avg_score"] or 0, 1)
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM tweets")
    row = await cursor.fetchone()
    stats["total_tweets"] = row["cnt"]
    return stats

async def get_meta(conn, key: str) -> str | None:
    cursor = await conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None

async def _set_meta_unlocked(conn, key: str, value: str) -> None:
    await conn.execute(
        "INSERT INTO meta (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, datetime.now().isoformat()),
    )
    await conn.commit()

async def set_meta(conn, key: str, value: str) -> None:
    async with sqlite_write_lock(conn):
        await _set_meta_unlocked(conn, key, value)

async def get_recent_avg_viral_score(conn, lookback_hours: int = 3) -> float | None:
    cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()
    cursor = await conn.execute("SELECT AVG(viral_potential) as avg FROM trends WHERE scored_at >= ?", (cutoff,))
    row = await cursor.fetchone()
    if row and dict(row).get("avg") is not None:
        return round(float(row["avg"]), 1)
    return None
