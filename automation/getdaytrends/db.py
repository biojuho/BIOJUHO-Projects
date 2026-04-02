"""
getdaytrends v3.0 - Database Layer (CRUD Functions)
트렌드 히스토리 및 CRUD 유틸리티 함수.
"""

import json
from datetime import datetime, timedelta

from loguru import logger as log

try:
    from shared.cache import get_cache
    _REDIS_OK = True
except ImportError:
    _REDIS_OK = False

try:
    # -- schema/connection imports --
    from .db_schema import (
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        _PgAdapter,
        close_pg_pool,
        compute_fingerprint,
        db_transaction,
        get_connection,
        get_pg_pool,
        init_db,
        sqlite_write_lock,
    )
    from .models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend
except ImportError:
    from db_schema import (  # noqa: F401
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        _PgAdapter,
        close_pg_pool,
        compute_fingerprint,
        db_transaction,
        get_connection,
        get_pg_pool,
        init_db,
        sqlite_write_lock,
    )
    from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend


async def save_run(conn, run: RunResult) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO runs (run_uuid, started_at, country, trends_collected,
               trends_scored, tweets_generated, tweets_saved, alerts_sent, errors)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id,
                run.started_at.isoformat(),
                run.country,
                run.trends_collected,
                run.trends_scored,
                run.tweets_generated,
                run.tweets_saved,
                run.alerts_sent,
                json.dumps(run.errors, ensure_ascii=False),
            ),
        )
        await conn.commit()
        return cursor.lastrowid


async def update_run(conn, run: RunResult, row_id: int) -> None:
    async with sqlite_write_lock(conn):
        await conn.execute(
            """UPDATE runs SET finished_at=?, trends_collected=?, trends_scored=?,
               tweets_generated=?, tweets_saved=?, alerts_sent=?, errors=? WHERE id=?""",
            (
                run.finished_at.isoformat() if run.finished_at else None,
                run.trends_collected,
                run.trends_scored,
                run.tweets_generated,
                run.tweets_saved,
                run.alerts_sent,
                json.dumps(run.errors, ensure_ascii=False),
                row_id,
            ),
        )
        await conn.commit()


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


async def _save_tweet_unlocked(
    conn, tweet: GeneratedTweet, trend_id: int, run_id: int, saved_to: list[str] | None = None
) -> int:
    cursor = await conn.execute(
        """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
           is_thread, thread_order, status, saved_to, generated_at, content_type)
           VALUES (?, ?, ?, ?, ?, 0, 0, 'queued', ?, ?, ?)""",
        (
            trend_id,
            run_id,
            tweet.tweet_type,
            tweet.content,
            tweet.char_count,
            json.dumps(saved_to or ["sqlite"], ensure_ascii=False),
            datetime.now().isoformat(),
            tweet.content_type,
        ),
    )
    await conn.commit()
    return cursor.lastrowid


async def save_tweet(conn, tweet: GeneratedTweet, trend_id: int, run_id: int, saved_to: list[str] | None = None) -> int:
    async with sqlite_write_lock(conn):
        return await _save_tweet_unlocked(conn, tweet, trend_id, run_id, saved_to=saved_to)


async def _save_thread_unlocked(conn, thread: GeneratedThread, trend_id: int, run_id: int) -> list[int]:
    ids = []
    for i, text in enumerate(thread.tweets):
        cursor = await conn.execute(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
               is_thread, thread_order, status, saved_to, generated_at)
               VALUES (?, ?, 'thread', ?, ?, 1, ?, 'queued', '["sqlite"]', ?)""",
            (trend_id, run_id, text, len(text), i, datetime.now().isoformat()),
        )
        ids.append(cursor.lastrowid)
    await conn.commit()
    return ids


async def save_thread(conn, thread: GeneratedThread, trend_id: int, run_id: int) -> list[int]:
    async with sqlite_write_lock(conn):
        return await _save_thread_unlocked(conn, thread, trend_id, run_id)


async def save_tweets_batch(
    conn,
    tweets: list,
    trend_id: int,
    run_id: int,
    is_thread: bool = False,
    saved_to: list[str] | None = None,
) -> None:
    """트윗 배치 저장. variant_id, language 컬럼 포함 (v3.0)."""
    saved_to_json = json.dumps(saved_to or ["sqlite"], ensure_ascii=False)
    now = datetime.now().isoformat()
    if is_thread:
        rows = [
            (trend_id, run_id, "thread", text, len(text), 1, i, "queued", '["sqlite"]', now, "short", "", "ko")
            for i, text in enumerate(tweets)
        ]
        await conn.executemany(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
                is_thread, thread_order, status, saved_to, generated_at, content_type,
                variant_id, language)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    else:
        rows = [
            (
                trend_id,
                run_id,
                getattr(t, "tweet_type", ""),
                getattr(t, "content", ""),
                getattr(t, "char_count", len(getattr(t, "content", ""))),
                saved_to_json,
                now,
                getattr(t, "content_type", "short"),
                getattr(t, "variant_id", ""),
                getattr(t, "language", "ko"),
            )
            for t in tweets
        ]
        await conn.executemany(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
                is_thread, thread_order, status, saved_to, generated_at, content_type,
                variant_id, language)
               VALUES (?, ?, ?, ?, ?, 0, 0, 'queued', ?, ?, ?, ?, ?)""",
            rows,
        )
    # commit은 상위의 db_transaction이 담당


async def _resolve_tweet_row_id_for_publish(
    conn,
    *,
    tweet_row_id: int | None = None,
    content: str = "",
    trend_id: int | None = None,
    run_id: int | None = None,
) -> int | None:
    if tweet_row_id:
        cursor = await conn.execute("SELECT id FROM tweets WHERE id = ? LIMIT 1", (tweet_row_id,))
        row = await cursor.fetchone()
        return int(row["id"]) if row else None

    if not content:
        return None

    conditions = ["content = ?", "(posted_at IS NULL OR posted_at = '')"]
    params: list[object] = [content]
    if trend_id:
        conditions.append("trend_id = ?")
        params.append(trend_id)
    if run_id:
        conditions.append("run_id = ?")
        params.append(run_id)

    query = "SELECT id FROM tweets " f"WHERE {' AND '.join(conditions)} " "ORDER BY generated_at DESC, id DESC LIMIT 1"
    cursor = await conn.execute(query, tuple(params))
    row = await cursor.fetchone()
    return int(row["id"]) if row else None


async def _mark_tweet_posted_unlocked(
    conn,
    *,
    x_tweet_id: str,
    tweet_row_id: int | None = None,
    content: str = "",
    trend_id: int | None = None,
    run_id: int | None = None,
    posted_at: str | None = None,
    status: str = "posted",
) -> int | None:
    resolved_row_id = await _resolve_tweet_row_id_for_publish(
        conn,
        tweet_row_id=tweet_row_id,
        content=content,
        trend_id=trend_id,
        run_id=run_id,
    )
    if resolved_row_id is None:
        return None

    await conn.execute(
        """UPDATE tweets
           SET status = ?,
               posted_at = ?,
               x_tweet_id = ?
           WHERE id = ?""",
        (status, posted_at or datetime.now().isoformat(), x_tweet_id, resolved_row_id),
    )
    await conn.commit()
    return resolved_row_id


async def mark_tweet_posted(
    conn,
    *,
    x_tweet_id: str,
    tweet_row_id: int | None = None,
    content: str = "",
    trend_id: int | None = None,
    run_id: int | None = None,
    posted_at: str | None = None,
    status: str = "posted",
) -> int | None:
    async with sqlite_write_lock(conn):
        return await _mark_tweet_posted_unlocked(
            conn,
            x_tweet_id=x_tweet_id,
            tweet_row_id=tweet_row_id,
            content=content,
            trend_id=trend_id,
            run_id=run_id,
            posted_at=posted_at,
            status=status,
        )


async def _sync_tweet_metrics_unlocked(
    conn,
    *,
    tweet_row_id: int | None = None,
    x_tweet_id: str = "",
    impressions: int = 0,
    engagements: int = 0,
    engagement_rate: float = 0.0,
) -> int:
    if tweet_row_id is not None:
        cursor = await conn.execute(
            """UPDATE tweets
               SET impressions = ?,
                   engagements = ?,
                   engagement_rate = ?
               WHERE id = ?""",
            (impressions, engagements, engagement_rate, tweet_row_id),
        )
        await conn.commit()
        return cursor.rowcount

    if x_tweet_id:
        cursor = await conn.execute(
            """UPDATE tweets
               SET impressions = ?,
                   engagements = ?,
                   engagement_rate = ?
               WHERE x_tweet_id = ?""",
            (impressions, engagements, engagement_rate, x_tweet_id),
        )
        await conn.commit()
        return cursor.rowcount

    return 0


async def sync_tweet_metrics(
    conn,
    *,
    tweet_row_id: int | None = None,
    x_tweet_id: str = "",
    impressions: int = 0,
    engagements: int = 0,
    engagement_rate: float = 0.0,
) -> int:
    async with sqlite_write_lock(conn):
        return await _sync_tweet_metrics_unlocked(
            conn,
            tweet_row_id=tweet_row_id,
            x_tweet_id=x_tweet_id,
            impressions=impressions,
            engagements=engagements,
            engagement_rate=engagement_rate,
        )


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


async def get_cached_content(conn, fingerprint: str, max_age_hours: int = 24) -> list[dict] | None:
    # Redis cache first
    if _REDIS_OK:
        cache = get_cache()
        cache_key = f"gdt:content:{fingerprint}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id WHERE tr.fingerprint = ? AND tr.scored_at >= ? ORDER BY tw.generated_at DESC",
        (fingerprint, cutoff),
    )
    rows = await cursor.fetchall()
    result = [dict(r) for r in rows] if rows else None

    # Cache for 6 hours (shorter than max_age to keep fresh)
    if result and _REDIS_OK:
        await cache.set(cache_key, result, ttl=6 * 3600)

    return result


async def get_recent_avg_viral_score(conn, lookback_hours: int = 3) -> float | None:
    cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()
    cursor = await conn.execute("SELECT AVG(viral_potential) as avg FROM trends WHERE scored_at >= ?", (cutoff,))
    row = await cursor.fetchone()
    if row and dict(row).get("avg") is not None:
        return round(float(row["avg"]), 1)
    return None


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


async def get_recent_tweet_contents(conn, keyword: str, hours: int = 24, limit: int = 5) -> list[str]:
    """
    최근 N시간 내 특정 키워드로 생성된 트윗 내용 목록 반환.
    콘텐츠 다양성 프롬프트 주입에 사용.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        """SELECT tw.content FROM tweets tw
           JOIN trends tr ON tw.trend_id = tr.id
           WHERE tr.keyword = ? AND tw.generated_at >= ?
             AND tw.content_type = 'short' AND tw.is_thread = 0
           ORDER BY tw.generated_at DESC LIMIT ?""",
        (keyword, cutoff, limit),
    )
    rows = await cursor.fetchall()
    return [r["content"] for r in rows]


async def _record_posting_time_stat_unlocked(conn, category: str, hour: int, engagement_label: str) -> None:
    """
    게시 시간대별 참여도 학습 기록.
    engagement_label: '높음'=1.0 / '보통'=0.5 / '낮음'=0.2
    """
    score_map = {"높음": 1.0, "보통": 0.5, "낮음": 0.2}
    score = score_map.get(engagement_label, 0.5)
    try:
        await conn.execute(
            """INSERT INTO posting_time_stats (category, hour, total_score, sample_count, updated_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(category, hour) DO UPDATE SET
                   total_score = total_score + excluded.total_score,
                   sample_count = sample_count + 1,
                   updated_at = excluded.updated_at""",
            (category, hour, score, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.warning(f"posting_time_stat 기록 실패: {e}")


async def record_posting_time_stat(conn, category: str, hour: int, engagement_label: str) -> None:
    async with sqlite_write_lock(conn):
        await _record_posting_time_stat_unlocked(conn, category, hour, engagement_label)


async def get_best_posting_hours(conn, category: str, top_n: int = 3) -> list[int]:
    """
    카테고리별 참여도 기준 상위 N개 게시 시간대 반환.
    데이터 없으면 빈 리스트 반환.
    """
    cursor = await conn.execute(
        """SELECT hour, total_score / sample_count AS avg_score
           FROM posting_time_stats
           WHERE category = ? AND sample_count >= 3
           ORDER BY avg_score DESC LIMIT ?""",
        (category, top_n),
    )
    rows = await cursor.fetchall()
    return [r["hour"] for r in rows]


async def _record_watchlist_hit_unlocked(conn, keyword: str, watchlist_item: str, viral_potential: int) -> None:
    """Watchlist 키워드 감지 기록."""
    try:
        await conn.execute(
            """INSERT INTO watchlist_hits (keyword, watchlist_item, viral_potential, detected_at)
               VALUES (?, ?, ?, ?)""",
            (keyword, watchlist_item, viral_potential, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"watchlist_hit 기록 실패 (무시): {e}")


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


async def _record_content_feedback_unlocked(
    conn,
    keyword: str,
    category: str = "",
    qa_score: float = 0.0,
    regenerated: bool = False,
    reason: str = "",
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> None:
    """v6.0/v6.1: 콘텐츠 QA 피드백 + 최신성 기록."""
    try:
        await conn.execute(
            """INSERT INTO content_feedback (keyword, category, qa_score, regenerated, reason, content_age_hours, freshness_grade, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                keyword,
                category,
                qa_score,
                int(regenerated),
                reason,
                content_age_hours,
                freshness_grade,
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"content_feedback 기록 실패 (무시): {e}")


async def record_content_feedback(
    conn,
    keyword: str,
    category: str = "",
    qa_score: float = 0.0,
    regenerated: bool = False,
    reason: str = "",
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> None:
    async with sqlite_write_lock(conn):
        await _record_content_feedback_unlocked(
            conn,
            keyword,
            category=category,
            qa_score=qa_score,
            regenerated=regenerated,
            reason=reason,
            content_age_hours=content_age_hours,
            freshness_grade=freshness_grade,
        )


async def get_qa_summary(conn, days: int = 7) -> dict:
    """
    v15.0 Phase B: QA 메트릭 요약.
    반환: {total_feedbacks, avg_qa_score, regeneration_rate, by_category, recent_scores}
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # 전체 집계
    cursor = await conn.execute(
        """SELECT COUNT(*) as total,
                  COALESCE(AVG(qa_score), 0.0) as avg_score,
                  COALESCE(SUM(regenerated), 0) as regen_count
           FROM content_feedback
           WHERE created_at >= ?""",
        (cutoff,),
    )
    row = await cursor.fetchone()
    total = dict(row).get("total", 0) if row else 0
    avg_score = dict(row).get("avg_score", 0.0) if row else 0.0
    regen_count = dict(row).get("regen_count", 0) if row else 0
    regen_rate = regen_count / total if total > 0 else 0.0

    # 카테고리별 분석
    cursor = await conn.execute(
        """SELECT category,
                  COUNT(*) as count,
                  ROUND(AVG(qa_score), 1) as avg_score
           FROM content_feedback
           WHERE created_at >= ? AND category != ''
           GROUP BY category""",
        (cutoff,),
    )
    cat_rows = await cursor.fetchall()
    by_category = {r["category"]: {"count": r["count"], "avg_score": r["avg_score"]} for r in cat_rows}

    # 최근 점수 (최대 10건)
    cursor = await conn.execute(
        """SELECT qa_score FROM content_feedback
           WHERE created_at >= ?
           ORDER BY created_at DESC LIMIT 10""",
        (cutoff,),
    )
    score_rows = await cursor.fetchall()
    recent_scores = [r["qa_score"] for r in score_rows]

    return {
        "total_feedbacks": total,
        "avg_qa_score": round(avg_score, 1),
        "regeneration_rate": round(regen_rate, 4),
        "by_category": by_category,
        "recent_scores": recent_scores,
    }


async def get_content_hashes(conn, hours: int = 24) -> set[str]:
    """
    v15.0 Phase B: 최근 N시간 내 생성된 콘텐츠의 핑거프린트 해시 집합 반환.
    콘텐츠 다양성 검증에 사용.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        """SELECT DISTINCT fingerprint FROM trends
           WHERE scored_at >= ? AND fingerprint != ''""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    return {r["fingerprint"] for r in rows}

_WORKFLOW_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "drafted": {"ready"},
    "ready": {"approved"},
    "approved": {"published"},
    "published": {"measured", "learned"},
    "measured": {"learned"},
    "learned": set(),
}

_REVIEW_STATUS_BY_LIFECYCLE = {
    "drafted": "Draft",
    "ready": "Ready",
    "approved": "Approved",
    "published": "Published",
    "measured": "Published",
    "learned": "Published",
}


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


async def record_trend_quarantine(
    conn,
    *,
    reason_code: str,
    reason_detail: str = "",
    keyword: str = "",
    fingerprint: str = "",
    source_count: int = 0,
    freshness_minutes: int = 0,
    payload: dict | None = None,
    run_id: int | None = None,
) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO trend_quarantine (
                   run_id, keyword, fingerprint, reason_code, reason_detail,
                   source_count, freshness_minutes, payload_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                keyword,
                fingerprint,
                reason_code,
                reason_detail,
                source_count,
                freshness_minutes,
                _json_text(payload or {}),
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
        return cursor.lastrowid


async def save_validated_trend(
    conn,
    *,
    trend_id: str,
    keyword: str,
    confidence_score: float = 0.0,
    source_count: int = 0,
    evidence_refs: list[str] | None = None,
    freshness_minutes: int = 0,
    dedup_fingerprint: str = "",
    lifecycle_status: str = "validated",
    scoring_axes: dict | None = None,
    scoring_reasons: dict | None = None,
    trend_row_id: int | None = None,
    run_id: int | None = None,
) -> str:
    now = datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO validated_trends (
                   trend_id, trend_row_id, run_id, keyword, confidence_score,
                   source_count, evidence_refs, freshness_minutes,
                   dedup_fingerprint, lifecycle_status, scoring_axes,
                   scoring_reasons, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(trend_id) DO UPDATE SET
                   trend_row_id=excluded.trend_row_id,
                   run_id=excluded.run_id,
                   keyword=excluded.keyword,
                   confidence_score=excluded.confidence_score,
                   source_count=excluded.source_count,
                   evidence_refs=excluded.evidence_refs,
                   freshness_minutes=excluded.freshness_minutes,
                   dedup_fingerprint=excluded.dedup_fingerprint,
                   lifecycle_status=excluded.lifecycle_status,
                   scoring_axes=excluded.scoring_axes,
                   scoring_reasons=excluded.scoring_reasons,
                   updated_at=excluded.updated_at""",
            (
                trend_id,
                trend_row_id,
                run_id,
                keyword,
                confidence_score,
                source_count,
                _json_text(evidence_refs or []),
                freshness_minutes,
                dedup_fingerprint,
                lifecycle_status,
                _json_text(scoring_axes or {}),
                _json_text(scoring_reasons or {}),
                now,
                now,
            ),
        )
        await conn.commit()
    return trend_id


async def save_draft_bundle(
    conn,
    *,
    draft_id: str,
    trend_id: str,
    platform: str,
    content_type: str,
    body: str,
    hashtags: list[str] | None = None,
    prompt_version: str = "",
    generator_provider: str = "",
    generator_model: str = "",
    source_evidence_ref: str = "",
    degraded_mode: bool = False,
    lifecycle_status: str = "drafted",
    review_status: str = "Draft",
    trend_row_id: int | None = None,
) -> str:
    now = datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO draft_bundles (
                   draft_id, trend_id, trend_row_id, platform, content_type,
                   body, hashtags, prompt_version, generator_provider,
                   generator_model, source_evidence_ref, degraded_mode,
                   lifecycle_status, review_status, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(draft_id) DO UPDATE SET
                   trend_id=excluded.trend_id,
                   trend_row_id=excluded.trend_row_id,
                   platform=excluded.platform,
                   content_type=excluded.content_type,
                   body=excluded.body,
                   hashtags=excluded.hashtags,
                   prompt_version=excluded.prompt_version,
                   generator_provider=excluded.generator_provider,
                   generator_model=excluded.generator_model,
                   source_evidence_ref=excluded.source_evidence_ref,
                   degraded_mode=excluded.degraded_mode,
                   updated_at=excluded.updated_at""",
            (
                draft_id,
                trend_id,
                trend_row_id,
                platform,
                content_type,
                body,
                _json_text(hashtags or []),
                prompt_version,
                generator_provider,
                generator_model,
                source_evidence_ref,
                int(degraded_mode),
                lifecycle_status,
                review_status,
                now,
                now,
            ),
        )
        await conn.commit()
    return draft_id


async def get_draft_bundle(conn, draft_id: str) -> dict | None:
    cursor = await conn.execute("SELECT * FROM draft_bundles WHERE draft_id = ? LIMIT 1", (draft_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_draft_bundle_status(
    conn,
    *,
    draft_id: str,
    lifecycle_status: str,
    review_status: str | None = None,
    notion_page_id: str | None = None,
    published_url: str | None = None,
    published_at: str | None = None,
    receipt_id: str | None = None,
) -> None:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")

    current = row.get("lifecycle_status", "drafted")
    if current != lifecycle_status:
        allowed = _WORKFLOW_STATUS_TRANSITIONS.get(current, set())
        if lifecycle_status not in allowed and current != lifecycle_status:
            raise ValueError(f"invalid draft transition: {current} -> {lifecycle_status}")

    async with sqlite_write_lock(conn):
        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = ?,
                   review_status = COALESCE(?, review_status),
                   notion_page_id = COALESCE(?, notion_page_id),
                   published_url = COALESCE(?, published_url),
                   published_at = COALESCE(?, published_at),
                   receipt_id = COALESCE(?, receipt_id),
                   updated_at = ?
               WHERE draft_id = ?""",
            (
                lifecycle_status,
                review_status,
                notion_page_id,
                published_url,
                published_at,
                receipt_id,
                datetime.now().isoformat(),
                draft_id,
            ),
        )
        await conn.commit()


async def save_qa_report(
    conn,
    *,
    draft_id: str,
    total_score: float,
    passed: bool,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    report_payload: dict | None = None,
) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO qa_reports (
                   draft_id, total_score, passed, warnings, blocking_reasons,
                   report_payload, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                draft_id,
                total_score,
                int(passed),
                _json_text(warnings or []),
                _json_text(blocking_reasons or []),
                _json_text(report_payload or {}),
                datetime.now().isoformat(),
            ),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET qa_score = ?,
                   blocking_reasons = ?,
                   updated_at = ?
               WHERE draft_id = ?""",
            (
                total_score,
                _json_text(blocking_reasons or []),
                datetime.now().isoformat(),
                draft_id,
            ),
        )
        await conn.commit()
        return cursor.lastrowid


async def promote_draft_to_ready(conn, draft_id: str) -> None:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")
    blockers = _json_list(row.get("blocking_reasons"))
    if blockers:
        raise ValueError(f"draft has blocking reasons: {', '.join(blockers)}")
    if not (row.get("prompt_version") or "").strip():
        raise ValueError("draft missing prompt_version")
    if not (row.get("source_evidence_ref") or "").strip():
        raise ValueError("draft missing source_evidence_ref")
    await update_draft_bundle_status(
        conn,
        draft_id=draft_id,
        lifecycle_status="ready",
        review_status="Ready",
    )


async def save_review_decision(
    conn,
    *,
    draft_id: str,
    decision: str,
    reviewed_by: str = "",
    review_note: str = "",
    reviewed_at: str | None = None,
    source: str = "manual",
) -> int:
    normalized = decision.strip().lower()
    if normalized not in {"approved", "rejected", "expired"}:
        raise ValueError(f"unsupported review decision: {decision}")

    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")

    next_lifecycle = row.get("lifecycle_status", "drafted")
    next_review_status = row.get("review_status", "Draft")
    if normalized == "approved":
        if next_lifecycle != "ready":
            raise ValueError("draft must be ready before approval")
        next_lifecycle = "approved"
        next_review_status = "Approved"
    elif normalized == "rejected":
        next_review_status = "Rejected"
    elif normalized == "expired":
        next_review_status = "Expired"

    ts = reviewed_at or datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO review_decisions (
                   draft_id, decision, reviewed_by, reviewed_at,
                   review_note, source, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (draft_id, normalized, reviewed_by, ts, review_note, source, datetime.now().isoformat()),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = ?, review_status = ?, updated_at = ?
               WHERE draft_id = ?""",
            (next_lifecycle, next_review_status, datetime.now().isoformat(), draft_id),
        )
        await conn.commit()
        return cursor.lastrowid


async def record_publish_receipt(
    conn,
    *,
    draft_id: str,
    platform: str,
    success: bool,
    published_url: str = "",
    published_at: str | None = None,
    failure_code: str = "",
    failure_reason: str = "",
    receipt_id: str = "",
) -> str:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")
    if row.get("lifecycle_status") != "approved":
        raise ValueError("draft must be approved before publish receipt is recorded")

    published_ts = published_at or datetime.now().isoformat()
    resolved_receipt_id = receipt_id or f"receipt-{draft_id[-8:]}-{int(datetime.now().timestamp())}"
    collector_due_at = (datetime.fromisoformat(published_ts) + timedelta(hours=48)).isoformat() if success else None

    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO publish_receipts (
                   receipt_id, draft_id, platform, success, published_url,
                   published_at, failure_code, failure_reason,
                   collector_due_at, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                resolved_receipt_id,
                draft_id,
                platform,
                int(success),
                published_url,
                published_ts if success else None,
                failure_code,
                failure_reason,
                collector_due_at,
                datetime.now().isoformat(),
            ),
        )
        if success:
            await conn.execute(
                """UPDATE draft_bundles
                   SET lifecycle_status = 'published',
                       review_status = 'Published',
                       published_url = ?,
                       published_at = ?,
                       receipt_id = ?,
                       updated_at = ?
                   WHERE draft_id = ?""",
                (
                    published_url,
                    published_ts,
                    resolved_receipt_id,
                    datetime.now().isoformat(),
                    draft_id,
                ),
            )
        await conn.commit()
    return resolved_receipt_id


async def record_feedback_summary(
    conn,
    *,
    draft_id: str,
    metric_window: str,
    impressions: int = 0,
    engagements: int = 0,
    clicks: int = 0,
    collector_status: str = "",
    strategy_notes: str = "",
    receipt_id: str = "",
) -> int:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")

    resolved_receipt_id = receipt_id or (row.get("receipt_id") or "")
    if not resolved_receipt_id:
        raise ValueError("publish receipt required before feedback summary")

    cursor = await conn.execute(
        "SELECT receipt_id FROM publish_receipts WHERE receipt_id = ? AND draft_id = ? LIMIT 1",
        (resolved_receipt_id, draft_id),
    )
    if await cursor.fetchone() is None:
        raise ValueError("publish receipt required before feedback summary")

    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO feedback_summaries (
                   draft_id, receipt_id, metric_window, impressions,
                   engagements, clicks, collector_status,
                   strategy_notes, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                draft_id,
                resolved_receipt_id,
                metric_window,
                impressions,
                engagements,
                clicks,
                collector_status,
                strategy_notes,
                datetime.now().isoformat(),
            ),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = 'learned',
                   updated_at = ?
               WHERE draft_id = ?""",
            (datetime.now().isoformat(), draft_id),
        )
        await conn.commit()
        return cursor.lastrowid


async def attach_draft_to_notion_page(conn, draft_id: str, notion_page_id: str, review_status: str = "Ready") -> None:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")
    async with sqlite_write_lock(conn):
        await conn.execute(
            """UPDATE draft_bundles
               SET notion_page_id = ?, review_status = ?, updated_at = ?
               WHERE draft_id = ?""",
            (notion_page_id, review_status, datetime.now().isoformat(), draft_id),
        )
        await conn.commit()


async def get_review_queue_snapshot(conn, limit: int = 50) -> dict:
    status_cursor = await conn.execute(
        "SELECT review_status, COUNT(*) as count FROM draft_bundles GROUP BY review_status"
    )
    counts = {row["review_status"]: row["count"] for row in await status_cursor.fetchall()}
    items_cursor = await conn.execute(
        """SELECT draft_id, trend_id, platform, content_type, lifecycle_status,
                  review_status, qa_score, notion_page_id, published_url,
                  created_at, updated_at
           FROM draft_bundles
           ORDER BY updated_at DESC, created_at DESC
           LIMIT ?""",
        (limit,),
    )
    items = [dict(row) for row in await items_cursor.fetchall()]
    return {"counts": counts, "items": items}
