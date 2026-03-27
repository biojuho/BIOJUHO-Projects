"""
getdaytrends v3.0 - Database Layer (CRUD Functions)
?몃젋???덉뒪?좊━ ??? CRUD ?ы띁 ?⑥닔.
"""

import json
import os
from datetime import datetime, timedelta

import aiosqlite

from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend

from loguru import logger as log

# -- schema/connection imports --
from db_schema import (  # noqa: F401
    _PgAdapter,
    close_pg_pool,
    compute_fingerprint,
    db_transaction,
    get_connection,
    get_pg_pool,
    init_db,
    _normalize_name,
    _normalize_volume,
    _backfill_fingerprints,
    sqlite_write_lock,
)

async def save_run(conn, run: RunResult) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO runs (run_uuid, started_at, country, trends_collected,
               trends_scored, tweets_generated, tweets_saved, alerts_sent, errors)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id, run.started_at.isoformat(), run.country, run.trends_collected,
                run.trends_scored, run.tweets_generated, run.tweets_saved, run.alerts_sent,
                json.dumps(run.errors, ensure_ascii=False)
            )
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
                run.trends_collected, run.trends_scored, run.tweets_generated,
                run.tweets_saved, run.alerts_sent, json.dumps(run.errors, ensure_ascii=False), row_id
            )
        )
        await conn.commit()


async def save_trend(conn, trend: ScoredTrend, run_id: int, bucket: int = 5000) -> int:
    """?몃젋????? bucket? config.cache_volume_bucket?먯꽌 ?꾨떖諛쏆븘 fingerprint ?뺣???議곗젙."""
    fingerprint = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket)
    cursor = await conn.execute(
        """INSERT INTO trends (run_id, keyword, rank, volume_raw, volume_numeric,
           viral_potential, trend_acceleration, top_insight, suggested_angles,
           best_hook_starter, country, sources, twitter_context, reddit_context,
           news_context, scored_at, fingerprint, sentiment, safety_flag,
           cross_source_confidence, joongyeon_kick, joongyeon_angle)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, trend.keyword, trend.rank, str(trend.volume_last_24h), trend.volume_last_24h,
            trend.viral_potential, trend.trend_acceleration, trend.top_insight,
            json.dumps(trend.suggested_angles, ensure_ascii=False), trend.best_hook_starter,
            trend.country, json.dumps([s.value for s in trend.sources], ensure_ascii=False),
            trend.context.twitter_insight if trend.context else "",
            trend.context.reddit_insight if trend.context else "",
            trend.context.news_insight if trend.context else "",
            trend.scored_at.isoformat(), fingerprint,
            trend.sentiment, int(trend.safety_flag),
            trend.cross_source_confidence, trend.joongyeon_kick, trend.joongyeon_angle,
        )
    )
    # commit? ?몄텧??db_transaction)媛 ?대떦 ???먯껜 commit ?쒓굅濡??몃옖??뀡 以묐┰ 蹂댁옣
    return cursor.lastrowid


async def _save_tweet_unlocked(conn, tweet: GeneratedTweet, trend_id: int, run_id: int, saved_to: list[str] | None = None) -> int:
    cursor = await conn.execute(
        """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
           is_thread, thread_order, status, saved_to, generated_at, content_type)
           VALUES (?, ?, ?, ?, ?, 0, 0, 'queued', ?, ?, ?)""",
        (
            trend_id, run_id, tweet.tweet_type, tweet.content, tweet.char_count,
            json.dumps(saved_to or ["sqlite"], ensure_ascii=False),
            datetime.now().isoformat(), tweet.content_type
        )
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
            (trend_id, run_id, text, len(text), i, datetime.now().isoformat())
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
    """?몄쐵 諛곗튂 ??? variant_id, language 而щ읆 ?ы븿 (v3.0)."""
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
                trend_id, run_id,
                getattr(t, "tweet_type", ""),
                getattr(t, "content", ""),
                getattr(t, "char_count", len(getattr(t, "content", ""))),
                saved_to_json, now,
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
    # commit? ?몄텧??db_transaction)媛 ?대떦


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

    query = (
        "SELECT id FROM tweets "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY generated_at DESC, id DESC LIMIT 1"
    )
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
        (keyword, cutoff)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_recent_trends(conn, days: int = 7, min_score: int = 0) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, country, scored_at FROM trends WHERE scored_at >= ? AND viral_potential >= ? ORDER BY viral_potential DESC",
        (cutoff, min_score)
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
    cursor = await conn.execute("SELECT DISTINCT fingerprint FROM trends WHERE scored_at >= ? AND fingerprint != ''", (cutoff,))
    rows = await cursor.fetchall()
    return {row["fingerprint"] for row in rows}


async def is_duplicate_trend(conn, name: str, volume: int, hours: int = 3) -> bool:
    fp = compute_fingerprint(name, volume)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute("SELECT 1 FROM trends WHERE fingerprint = ? AND scored_at >= ? LIMIT 1", (fp, cutoff))
    row = await cursor.fetchone()
    return row is not None


async def _cleanup_old_records_unlocked(conn, days: int = 90) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute("DELETE FROM tweets WHERE generated_at < ?", (cutoff,))
    tweets_deleted = cursor.rowcount
    cursor = await conn.execute("DELETE FROM trends WHERE scored_at < ?", (cutoff,))
    trends_deleted = cursor.rowcount
    await conn.execute("DELETE FROM runs WHERE started_at < ? AND id NOT IN (SELECT DISTINCT run_id FROM trends)", (cutoff,))
    await conn.commit()
    await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    total = tweets_deleted + trends_deleted
    if total: log.info(f"DB ?뺣━ ?꾨즺: tweets {tweets_deleted}媛?+ trends {trends_deleted}媛???젣 ({days}??珥덇낵)")
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
        (key, value, datetime.now().isoformat())
    )
    await conn.commit()


async def set_meta(conn, key: str, value: str) -> None:
    async with sqlite_write_lock(conn):
        await _set_meta_unlocked(conn, key, value)


async def get_cached_score(conn, fingerprint: str, max_age_hours: int = 6) -> dict | None:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT keyword, viral_potential, trend_acceleration, top_insight, suggested_angles, best_hook_starter, scored_at FROM trends WHERE fingerprint = ? AND scored_at >= ? ORDER BY scored_at DESC LIMIT 1",
        (fingerprint, cutoff)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_cached_content(conn, fingerprint: str, max_age_hours: int = 24) -> list[dict] | None:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    cursor = await conn.execute(
        "SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id WHERE tr.fingerprint = ? AND tr.scored_at >= ? ORDER BY tw.generated_at DESC",
        (fingerprint, cutoff)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows] if rows else None


async def get_recent_avg_viral_score(conn, lookback_hours: int = 3) -> float | None:
    cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()
    cursor = await conn.execute("SELECT AVG(viral_potential) as avg FROM trends WHERE scored_at >= ?", (cutoff,))
    row = await cursor.fetchone()
    if row and dict(row).get("avg") is not None:
        return round(float(row["avg"]), 1)
    return None


async def get_trend_history_batch(conn, keywords: list[str], days: int = 7) -> dict[str, list[dict]]:
    if not keywords: return {}
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(keywords))
    cursor = await conn.execute(
        f"SELECT keyword, rank, viral_potential, trend_acceleration, top_insight, scored_at FROM trends WHERE keyword IN ({placeholders}) AND scored_at >= ? ORDER BY keyword, scored_at DESC",
        (*keywords, cutoff)
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
    ?뚯뒪 ?섏쭛 硫뷀듃由?湲곕줉.
    source: 'getdaytrends' | 'google_trends' | 'twitter' | 'reddit' | 'news' | 'youtube'
    quality_score: 0.0~1.0 (?좎슜???댁슜 鍮꾩쑉)
    """
    try:
        await conn.execute(
            """INSERT INTO source_quality (source, recorded_at, success, latency_ms, item_count, quality_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, datetime.now().isoformat(), int(success), latency_ms, item_count, quality_score),
        )
        await conn.commit()
    except Exception as e:
        log.warning(f"source_quality 湲곕줉 ?ㅽ뙣: {e}")


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
    """?뚯뒪蹂??덉쭏 ?붿빟 (success_rate, avg_latency_ms, avg_quality_score, total_calls)."""
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
    吏곸쟾 N?곗쓽 蹂쇰ⅷ ?됯퇏 利앷???諛섑솚 (????諛곗쑉).
    ?곗씠??遺議???0.0 諛섑솚.
    """
    cursor = await conn.execute(
        "SELECT volume_numeric, scored_at FROM trends WHERE keyword = ? "
        "ORDER BY scored_at DESC LIMIT ?",
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
    理쒓렐 N?쒓컙 ???뱀젙 ?ㅼ썙?쒕줈 ?앹꽦???몄쐵 ?댁슜 紐⑸줉 諛섑솚.
    肄섑뀗痢??ㅼ뼇???꾨＼?꾪듃 二쇱엯???ъ슜.
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


async def _record_posting_time_stat_unlocked(
    conn, category: str, hour: int, engagement_label: str
) -> None:
    """
    寃뚯떆 ?쒓컙?蹂?李몄뿬???숈뒿 湲곕줉.
    engagement_label: '?믪쓬'=1.0 / '蹂댄넻'=0.5 / '??쓬'=0.2
    """
    score_map = {"?믪쓬": 1.0, "蹂댄넻": 0.5, "??쓬": 0.2}
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
        log.warning(f"posting_time_stat 湲곕줉 ?ㅽ뙣: {e}")


async def record_posting_time_stat(
    conn, category: str, hour: int, engagement_label: str
) -> None:
    async with sqlite_write_lock(conn):
        await _record_posting_time_stat_unlocked(conn, category, hour, engagement_label)


async def get_best_posting_hours(conn, category: str, top_n: int = 3) -> list[int]:
    """
    移댄뀒怨좊━蹂??됯퇏 李몄뿬??湲곗? ?곸쐞 N媛?寃뚯떆 ?쒓컙? 諛섑솚.
    ?곗씠???놁쑝硫?鍮?由ъ뒪??諛섑솚.
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


async def _record_watchlist_hit_unlocked(
    conn, keyword: str, watchlist_item: str, viral_potential: int
) -> None:
    """Watchlist ?ㅼ썙???깆옣 湲곕줉."""
    try:
        await conn.execute(
            """INSERT INTO watchlist_hits (keyword, watchlist_item, viral_potential, detected_at)
               VALUES (?, ?, ?, ?)""",
            (keyword, watchlist_item, viral_potential, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"watchlist_hit 湲곕줉 ?ㅽ뙣 (臾댁떆): {e}")


async def record_watchlist_hit(
    conn, keyword: str, watchlist_item: str, viral_potential: int
) -> None:
    async with sqlite_write_lock(conn):
        await _record_watchlist_hit_unlocked(conn, keyword, watchlist_item, viral_potential)


async def get_trend_history_patterns_batch(
    conn, keywords: list[str], days: int = 7
) -> dict[str, dict]:
    """
    ?щ윭 ?ㅼ썙?쒖쓽 ?덉뒪?좊━ ?⑦꽩??1??荑쇰━濡??쇨큵 議고쉶.
    諛섑솚: {keyword: {"seen_count", "avg_score", "score_trend", "is_recurring"}}
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

    # ?ㅼ썙?쒕퀎 洹몃９??
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
    """v6.0/v6.1: 肄섑뀗痢?QA ?쇰뱶諛?+ 理쒖떊??湲곕줉."""
    try:
        await conn.execute(
            """INSERT INTO content_feedback (keyword, category, qa_score, regenerated, reason, content_age_hours, freshness_grade, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (keyword, category, qa_score, int(regenerated), reason, content_age_hours, freshness_grade, datetime.now().isoformat()),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"content_feedback 湲곕줉 ?ㅽ뙣 (臾댁떆): {e}")


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
    v15.0 Phase B: QA 硫뷀듃由??붿빟.
    諛섑솚: {total_feedbacks, avg_qa_score, regeneration_rate, by_category, recent_scores}
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # ?꾩껜 吏묎퀎
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

    # 移댄뀒怨좊━蹂?遺꾩꽍
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
    by_category = {
        r["category"]: {"count": r["count"], "avg_score": r["avg_score"]}
        for r in cat_rows
    }

    # 理쒓렐 ?먯닔 (理쒕? 10嫄?
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
    v15.0 Phase B: 理쒓렐 N?쒓컙 ???앹꽦??肄섑뀗痢좎쓽 ?묎굅?꾨┛???댁떆 吏묓빀 諛섑솚.
    肄섑뀗痢??ㅼ뼇??寃利앹뿉 ?ъ슜.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        """SELECT DISTINCT fingerprint FROM trends
           WHERE scored_at >= ? AND fingerprint != ''""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    return {r["fingerprint"] for r in rows}

