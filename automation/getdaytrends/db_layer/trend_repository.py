"""Trend Repository"""

import json
from datetime import datetime, timedelta

from . import ScoredTrend, _REDIS_OK, compute_fingerprint, sqlite_write_lock

if _REDIS_OK:
    from . import get_cache

async def save_trend(conn, trend: ScoredTrend, run_id: int, bucket: int = 5000) -> int:
    """트렌드를 저장. bucket은 config.cache_volume_bucket에서 전달받아 fingerprint 정밀도 조정."""
    fingerprint = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket)
    cursor = await conn.execute(
        """INSERT INTO trends (run_id, keyword, rank, volume_raw, volume_numeric,
           viral_potential, trend_acceleration, top_insight, suggested_angles,
           best_hook_starter, country, sources, twitter_context, reddit_context,
           news_context, scored_at, fingerprint, sentiment, safety_flag,
           cross_source_confidence, joongyeon_kick, joongyeon_angle)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            trend.keyword,
            trend.rank,
            str(trend.volume_last_24h),
            trend.volume_last_24h,
            trend.viral_potential,
            trend.trend_acceleration,
            trend.top_insight,
            json.dumps(trend.suggested_angles, ensure_ascii=False),
            trend.best_hook_starter,
            trend.country,
            json.dumps([s.value for s in trend.sources], ensure_ascii=False),
            trend.context.twitter_insight if trend.context else "",
            trend.context.reddit_insight if trend.context else "",
            trend.context.news_insight if trend.context else "",
            trend.scored_at.isoformat(),
            fingerprint,
            trend.sentiment,
            int(trend.safety_flag),
            trend.cross_source_confidence,
            trend.joongyeon_kick,
            trend.joongyeon_angle,
        ),
    )
    # commit은 상위의 db_transaction이 담당 — 여기서는 commit 하지 않으므로 트랜잭션 중복 방지
    return cursor.lastrowid

async def get_trend_history(conn, keyword: str, days: int = 7) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, scored_at FROM trends WHERE keyword = ? AND scored_at >= ? ORDER BY scored_at DESC",
        (keyword, cutoff),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

async def get_recent_trends(conn, days: int = 7, min_score: int = 0) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, country, scored_at FROM trends WHERE scored_at >= ? AND viral_potential >= ? ORDER BY viral_potential DESC",
        (cutoff, min_score),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

async def get_recently_processed_keywords(conn, hours: int = 3) -> set[str]:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT DISTINCT keyword FROM trends WHERE scored_at >= ?", (cutoff,))
    rows = await cursor.fetchall()
    return {row["keyword"] for row in rows}

async def get_recently_processed_fingerprints(conn, hours: int = 3) -> set[str]:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        "SELECT DISTINCT fingerprint FROM trends WHERE scored_at >= ? AND fingerprint != ''", (cutoff,)
    )
    rows = await cursor.fetchall()
    return {row["fingerprint"] for row in rows}

async def is_duplicate_trend(conn, name: str, volume: int, hours: int = 3) -> bool:
    fp = compute_fingerprint(name, volume)

    # Redis SET-based dedup (O(1) vs O(n) DB scan at 100x scale)
    if _REDIS_OK:
        cache = get_cache()
        dedup_key = f"gdt:dedup:{fp}"
        if await cache.exists(dedup_key):
            return True

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT 1 FROM trends WHERE fingerprint = ? AND scored_at >= ? LIMIT 1", (fp, cutoff))
    row = await cursor.fetchone()
    is_dup = row is not None

    # Cache the fingerprint if it's a duplicate
    if is_dup and _REDIS_OK:
        await cache.set(dedup_key, True, ttl=hours * 3600)

    return is_dup

async def get_cached_score(conn, fingerprint: str, max_age_hours: int = 6) -> dict | None:
    # Redis cache first (avoids DB hit for repeated fingerprint lookups)
    if _REDIS_OK:
        cache = get_cache()
        cache_key = f"gdt:score:{fingerprint}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, viral_potential, trend_acceleration, top_insight, suggested_angles, best_hook_starter, scored_at FROM trends WHERE fingerprint = ? AND scored_at >= ? ORDER BY scored_at DESC LIMIT 1",
        (fingerprint, cutoff),
    )
    row = await cursor.fetchone()
    result = dict(row) if row else None

    # Cache result for 6 hours (match the natural TTL)
    if result and _REDIS_OK:
        await cache.set(cache_key, result, ttl=max_age_hours * 3600)

    return result

async def get_trend_history_batch(conn, keywords: list[str], days: int = 7) -> dict[str, list[dict]]:
    if not keywords:
        return {}
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(keywords))
    cursor = await conn.execute(
        f"SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, scored_at FROM trends WHERE keyword IN ({placeholders}) AND scored_at >= ? ORDER BY keyword, scored_at DESC",
        (*keywords, cutoff),
    )
    rows = await cursor.fetchall()
    result = {kw: [] for kw in keywords}
    for row in rows:
        result[row["keyword"]].append(dict(row))
    return result

async def get_volume_velocity(conn, keyword: str, lookback_runs: int = 3) -> float:
    """
    직전 N건의 볼륨 변화량 반환 (증감 비율).
    데이터 부족 시 0.0 반환.
    """
    cursor = await conn.execute(
        "SELECT volume_numeric, scored_at FROM trends WHERE keyword = ? " "ORDER BY scored_at DESC LIMIT ?",
        (keyword, lookback_runs + 1),
    )
    rows = await cursor.fetchall()
    if len(rows) < 2:
        return 0.0
    volumes = [r["volume_numeric"] for r in rows]
    if volumes[-1] == 0:
        return 0.0
    return (volumes[0] - volumes[-1]) / volumes[-1]

async def record_watchlist_hit(conn, keyword: str, watchlist_item: str, viral_potential: int) -> None:
    async with sqlite_write_lock(conn):
        await _record_watchlist_hit_unlocked(conn, keyword, watchlist_item, viral_potential)

async def get_trend_history_patterns_batch(conn, keywords: list[str], days: int = 7) -> dict[str, dict]:
    """
    여러 키워드의 히스토리 패턴을 1번 쿼리로 배치 조회.
    반환: {keyword: {"seen_count", "avg_score", "score_trend", "is_recurring"}}
    """
    if not keywords:
        return {}
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(keywords))
    cursor = await conn.execute(
        f"SELECT keyword, viral_potential, scored_at FROM trends "
        f"WHERE keyword IN ({placeholders}) AND scored_at >= ? "
        f"ORDER BY keyword, scored_at DESC",
        (*keywords, cutoff),
    )
    rows = await cursor.fetchall()

    # 카테고리별 그룹핑
    grouped: dict[str, list[int]] = {kw: [] for kw in keywords}
    for row in rows:
        grouped[row["keyword"]].append(row["viral_potential"])

    result: dict[str, dict] = {}
    for kw, scores in grouped.items():
        if not scores:
            result[kw] = {"seen_count": 0, "avg_score": 0.0, "score_trend": "new", "is_recurring": False}
            continue
        avg = sum(scores) / len(scores)
        if len(scores) >= 2:
            half = len(scores) // 2
            recent_avg = sum(scores[:half]) / max(half, 1)
            older_avg = sum(scores[half:]) / max(len(scores) - half, 1)
            if recent_avg > older_avg + 5:
                trend = "rising"
            elif recent_avg < older_avg - 5:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "new"
        result[kw] = {
            "seen_count": len(scores),
            "avg_score": round(avg, 1),
            "score_trend": trend,
            "is_recurring": len(scores) >= 3,
        }
    return result
