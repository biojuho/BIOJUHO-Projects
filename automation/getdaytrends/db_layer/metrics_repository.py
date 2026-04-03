"""Metrics Repository"""

from datetime import datetime, timedelta

from . import log, sqlite_write_lock

async def _record_source_quality_unlocked(
    conn,
    source: str,
    success: bool,
    latency_ms: float,
    item_count: int = 0,
    quality_score: float = 0.0,
) -> None:
    """
    소스 수집 메트릭 기록.
    source: 'getdaytrends' | 'google_trends' | 'twitter' | 'reddit' | 'news' | 'youtube'
    quality_score: 0.0~1.0 (유용/무용 비율)
    """
    try:
        await conn.execute(
            """INSERT INTO source_quality (source, recorded_at, success, latency_ms, item_count, quality_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, datetime.now().isoformat(), int(success), latency_ms, item_count, quality_score),
        )
        await conn.commit()
    except Exception as e:
        log.warning(f"source_quality 기록 실패: {e}")

async def record_source_quality(
    conn,
    source: str,
    success: bool,
    latency_ms: float,
    item_count: int = 0,
    quality_score: float = 0.0,
) -> None:
    async with sqlite_write_lock(conn):
        await _record_source_quality_unlocked(
            conn,
            source,
            success,
            latency_ms,
            item_count=item_count,
            quality_score=quality_score,
        )

async def get_source_quality_summary(conn, days: int = 7) -> dict:
    """소스별 수집 요약 (success_rate, avg_latency_ms, avg_quality_score, total_calls)."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        """SELECT source,
                  COUNT(*) as total_calls,
                  ROUND(AVG(success) * 100, 1) as success_rate,
                  ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                  ROUND(AVG(quality_score), 3) as avg_quality_score
           FROM source_quality
           WHERE recorded_at >= ?
           GROUP BY source
           ORDER BY source""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    return {row["source"]: dict(row) for row in rows}
