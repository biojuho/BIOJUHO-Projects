"""Tweet Repository"""

import json
from datetime import datetime, timedelta

from . import GeneratedThread, GeneratedTweet, _REDIS_OK, log, sqlite_write_lock

if _REDIS_OK:
    from . import get_cache

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
