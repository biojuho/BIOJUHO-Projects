"""db.py 테스트: SQLite 스키마, CRUD 헬퍼 함수."""

import asyncio
import os
import tempfile
import unittest
from datetime import datetime

import aiosqlite
import pytest
import db as db_module

from db import (
    compute_fingerprint,
    get_cached_content,
    get_cached_score,
    get_recent_avg_viral_score,
    get_recently_processed_keywords,
    get_trend_stats,
    init_db,
    is_duplicate_trend,
    mark_tweet_posted,
    save_run,
    save_thread,
    save_trend,
    save_tweet,
    sync_tweet_metrics,
    update_run,
)
from models import (
    GeneratedThread,
    GeneratedTweet,
    MultiSourceContext,
    RunResult,
    ScoredTrend,
    TrendSource,
)


class TestInitDb(unittest.IsolatedAsyncioTestCase):
    """DB 초기화 및 스키마 검증."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_tables_created(self):
        await init_db(self.conn)
        cursor = await self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        table_names = {row["name"] for row in tables}
        self.assertIn("runs", table_names)
        self.assertIn("trends", table_names)
        self.assertIn("tweets", table_names)

    @pytest.mark.asyncio
    async def test_idempotent(self):
        """두 번 호출해도 오류 없어야 함."""
        await init_db(self.conn)
        await init_db(self.conn)  # 두 번째 호출

    @pytest.mark.asyncio
    async def test_content_type_column_exists(self):
        await init_db(self.conn)
        cursor = await self.conn.execute("PRAGMA table_info(tweets)")
        row = await cursor.fetchall()
        columns = {r["name"] for r in row}
        self.assertIn("content_type", columns)

    @pytest.mark.asyncio
    async def test_variant_and_language_columns_exist(self):
        await init_db(self.conn)
        cursor = await self.conn.execute("PRAGMA table_info(tweets)")
        row = await cursor.fetchall()
        columns = {r["name"] for r in row}
        self.assertIn("variant_id", columns)
        self.assertIn("language", columns)

    @pytest.mark.asyncio
    async def test_hot_path_indexes_exist(self):
        await init_db(self.conn)

        trend_indexes_cursor = await self.conn.execute("PRAGMA index_list(trends)")
        trend_indexes = {row["name"] for row in await trend_indexes_cursor.fetchall()}

        tweet_indexes_cursor = await self.conn.execute("PRAGMA index_list(tweets)")
        tweet_indexes = {row["name"] for row in await tweet_indexes_cursor.fetchall()}

        self.assertIn("idx_trends_fp_scored", trend_indexes)
        self.assertIn("idx_tweets_generated_at", tweet_indexes)
        self.assertIn("idx_tweets_posted_at", tweet_indexes)


class TestSaveRun(unittest.IsolatedAsyncioTestCase):
    """실행 기록 저장/업데이트."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_save_and_retrieve(self):
        run = RunResult(run_id="test-uuid-123", country="korea")
        row_id = await save_run(self.conn, run)
        self.assertGreater(row_id, 0)

        cursor = await self.conn.execute("SELECT * FROM runs WHERE id=?", (row_id,))
        row = await cursor.fetchone()
        self.assertEqual(row["run_uuid"], "test-uuid-123")
        self.assertEqual(row["country"], "korea")

    @pytest.mark.asyncio
    async def test_update_run(self):
        run = RunResult(run_id="test-update", country="korea")
        row_id = await save_run(self.conn, run)

        run.trends_collected = 5
        run.tweets_generated = 10
        run.finished_at = datetime.now()
        await update_run(self.conn, run, row_id)

        cursor = await self.conn.execute("SELECT * FROM runs WHERE id=?", (row_id,))
        row = await cursor.fetchone()
        self.assertEqual(row["trends_collected"], 5)
        self.assertEqual(row["tweets_generated"], 10)
        self.assertIsNotNone(row["finished_at"])


class TestSaveTrend(unittest.IsolatedAsyncioTestCase):
    """트렌드 저장."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="trend-test")
        self.run_id = await save_run(self.conn, run)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_save_trend(self):
        trend = ScoredTrend(
            keyword="AI 규제",
            rank=1,
            viral_potential=85,
            top_insight="AI 규제 이슈",
            sources=[TrendSource.GETDAYTRENDS, TrendSource.REDDIT],
            context=MultiSourceContext(twitter_insight="hot topic"),
        )
        trend_id = await save_trend(self.conn, trend, self.run_id)
        self.assertGreater(trend_id, 0)

        cursor = await self.conn.execute("SELECT * FROM trends WHERE id=?", (trend_id,))
        row = await cursor.fetchone()
        self.assertEqual(row["keyword"], "AI 규제")
        self.assertEqual(row["viral_potential"], 85)


class TestSaveTweet(unittest.IsolatedAsyncioTestCase):
    """트윗 저장."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="tweet-test")
        self.run_id = await save_run(self.conn, run)
        trend = ScoredTrend(keyword="test", rank=1, sources=[TrendSource.GETDAYTRENDS])
        self.trend_id = await save_trend(self.conn, trend, self.run_id)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_save_short_tweet(self):
        tweet = GeneratedTweet(tweet_type="공감 유도형", content="테스트 트윗입니다")
        tweet_id = await save_tweet(self.conn, tweet, self.trend_id, self.run_id)
        self.assertGreater(tweet_id, 0)

        cursor = await self.conn.execute("SELECT * FROM tweets WHERE id=?", (tweet_id,))
        row = await cursor.fetchone()
        self.assertEqual(row["tweet_type"], "공감 유도형")
        self.assertEqual(row["content_type"], "short")

    @pytest.mark.asyncio
    async def test_save_long_tweet(self):
        tweet = GeneratedTweet(tweet_type="딥다이브", content="장문 포스트" * 100, content_type="long")
        tweet_id = await save_tweet(self.conn, tweet, self.trend_id, self.run_id)

        cursor = await self.conn.execute("SELECT * FROM tweets WHERE id=?", (tweet_id,))
        row = await cursor.fetchone()
        self.assertEqual(row["content_type"], "long")


class TestSaveThread(unittest.IsolatedAsyncioTestCase):
    """쓰레드 저장."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="thread-test")
        self.run_id = await save_run(self.conn, run)
        trend = ScoredTrend(keyword="thread-test", rank=1, sources=[TrendSource.GETDAYTRENDS])
        self.trend_id = await save_trend(self.conn, trend, self.run_id)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_save_thread(self):
        thread = GeneratedThread(tweets=["훅 트윗", "본문 1", "본문 2", "마무리"])
        ids = await save_thread(self.conn, thread, self.trend_id, self.run_id)
        self.assertEqual(len(ids), 4)

        cursor = await self.conn.execute(
            "SELECT * FROM tweets WHERE trend_id=? AND is_thread=1 ORDER BY thread_order",
            (self.trend_id,),
        )
        rows = await cursor.fetchall()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["content"], "훅 트윗")
        self.assertEqual(rows[3]["thread_order"], 3)


class TestGetRecentlyProcessed(unittest.IsolatedAsyncioTestCase):
    """중복 필터 함수."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="dedup-test")
        self.run_id = await save_run(self.conn, run)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_empty_db(self):
        keywords = await get_recently_processed_keywords(self.conn, hours=3)
        self.assertEqual(keywords, set())

    @pytest.mark.asyncio
    async def test_finds_recent(self):
        trend = ScoredTrend(keyword="최근키워드", rank=1, sources=[TrendSource.GETDAYTRENDS])
        await save_trend(self.conn, trend, self.run_id)

        keywords = await get_recently_processed_keywords(self.conn, hours=3)
        self.assertIn("최근키워드", keywords)


class TestGetTrendStats(unittest.IsolatedAsyncioTestCase):
    """통계 함수."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_empty_stats(self):
        stats = await get_trend_stats(self.conn)
        self.assertEqual(stats["total_runs"], 0)
        self.assertEqual(stats["total_trends"], 0)
        self.assertEqual(stats["total_tweets"], 0)

    @pytest.mark.asyncio
    async def test_with_data(self):
        run = RunResult(run_id="stats-test")
        run_id = await save_run(self.conn, run)
        trend = ScoredTrend(keyword="stat", rank=1, viral_potential=80, sources=[TrendSource.GETDAYTRENDS])
        trend_id = await save_trend(self.conn, trend, run_id)
        tweet = GeneratedTweet(tweet_type="test", content="hello")
        await save_tweet(self.conn, tweet, trend_id, run_id)

        stats = await get_trend_stats(self.conn)
        self.assertEqual(stats["total_runs"], 1)
        self.assertEqual(stats["total_trends"], 1)
        self.assertEqual(stats["total_tweets"], 1)
        self.assertEqual(stats["avg_viral_score"], 80.0)


class TestGetCachedContent(unittest.IsolatedAsyncioTestCase):
    """C2: 콘텐츠 캐시 조회."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="cache-test")
        self.run_id = await save_run(self.conn, run)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_no_cache_returns_none(self):
        fp = compute_fingerprint("없는키워드", 0)
        result = await get_cached_content(self.conn, fp)
        self.assertIsNone(result)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_rows(self):
        trend = ScoredTrend(keyword="AI 트렌드", rank=1, volume_last_24h=50000, sources=[TrendSource.GETDAYTRENDS])
        trend_id = await save_trend(self.conn, trend, self.run_id)
        tweet = GeneratedTweet(tweet_type="공감 유도형", content="캐시 테스트 트윗")
        await save_tweet(self.conn, tweet, trend_id, self.run_id)

        fp = compute_fingerprint("AI 트렌드", 50000)
        result = await get_cached_content(self.conn, fp, max_age_hours=24)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tweet_type"], "공감 유도형")

    @pytest.mark.asyncio
    async def test_expired_cache_returns_none(self):
        """max_age_hours=0 이면 캐시 미스."""
        trend = ScoredTrend(keyword="AI 트렌드", rank=1, volume_last_24h=50000, sources=[TrendSource.GETDAYTRENDS])
        trend_id = await save_trend(self.conn, trend, self.run_id)
        tweet = GeneratedTweet(tweet_type="공감 유도형", content="캐시 테스트")
        await save_tweet(self.conn, tweet, trend_id, self.run_id)

        fp = compute_fingerprint("AI 트렌드", 50000)
        result = await get_cached_content(self.conn, fp, max_age_hours=0)
        self.assertIsNone(result)


class TestGetRecentAvgViralScore(unittest.IsolatedAsyncioTestCase):
    """C4: 평균 바이럴 점수 조회."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="avg-test")
        self.run_id = await save_run(self.conn, run)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_empty_returns_none(self):
        result = await get_recent_avg_viral_score(self.conn, lookback_hours=3)
        self.assertIsNone(result)

    @pytest.mark.asyncio
    async def test_avg_score_calculated(self):
        for kw, score in [("A", 60), ("B", 80), ("C", 100)]:
            trend = ScoredTrend(keyword=kw, rank=1, viral_potential=score, sources=[TrendSource.GETDAYTRENDS])
            await save_trend(self.conn, trend, self.run_id)

        result = await get_recent_avg_viral_score(self.conn, lookback_hours=3)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 80.0, places=1)


class TestPerformanceTrackingColumns(unittest.IsolatedAsyncioTestCase):
    """P2-1: 성과 추적 컬럼 존재 확인."""

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_performance_columns_exist(self):
        cursor = await self.conn.execute("PRAGMA table_info(tweets)")
        rows = await cursor.fetchall()
        cols = {r["name"] for r in rows}
        for col in ("posted_at", "x_tweet_id", "impressions", "engagements", "engagement_rate"):
            self.assertIn(col, cols, f"missing column: {col}")

    @pytest.mark.asyncio
    async def test_mark_tweet_posted_and_sync_metrics(self):
        run = RunResult(run_id="publish-sync-test", country="korea")
        run_id = await save_run(self.conn, run)
        trend = ScoredTrend(
            keyword="실측 라벨 테스트",
            rank=1,
            volume_last_24h=12345,
            viral_potential=88,
            trend_acceleration="+12%",
            top_insight="test insight",
            suggested_angles=["angle"],
            best_hook_starter="hook",
            country="korea",
            sources=[TrendSource.GETDAYTRENDS],
            context=MultiSourceContext(),
        )
        trend_id = await save_trend(self.conn, trend, run_id)
        tweet = GeneratedTweet(
            tweet_type="short",
            content="실제 게시 후 성과 수집 테스트",
            char_count=18,
            content_type="short",
        )
        tweet_row_id = await save_tweet(self.conn, tweet, trend_id, run_id)

        resolved_row_id = await mark_tweet_posted(
            self.conn,
            x_tweet_id="1234567890123",
            tweet_row_id=tweet_row_id,
        )
        self.assertEqual(resolved_row_id, tweet_row_id)

        updated = await sync_tweet_metrics(
            self.conn,
            x_tweet_id="1234567890123",
            impressions=1500,
            engagements=105,
            engagement_rate=0.07,
        )
        self.assertEqual(updated, 1)

        cursor = await self.conn.execute(
            "SELECT posted_at, x_tweet_id, impressions, engagements, engagement_rate FROM tweets WHERE id = ?",
            (tweet_row_id,),
        )
        row = await cursor.fetchone()
        self.assertEqual(row["x_tweet_id"], "1234567890123")
        self.assertIsNotNone(row["posted_at"])
        self.assertEqual(row["impressions"], 1500)
        self.assertEqual(row["engagements"], 105)
        self.assertAlmostEqual(row["engagement_rate"], 0.07, places=6)

    @pytest.mark.asyncio
    async def test_migration_idempotent(self):
        """두 번 호출해도 오류 없어야 함."""
        await init_db(self.conn)
        await init_db(self.conn)


class TestParallelSQLiteWrites(unittest.IsolatedAsyncioTestCase):
    """Shared SQLite file should survive parallel init/save sequences."""

    @pytest.mark.asyncio
    async def test_parallel_init_and_save_run_on_shared_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "parallel-lock.db")

            def worker(index: int) -> int:
                async def _inner() -> int:
                    conn = await aiosqlite.connect(db_path)
                    conn.row_factory = aiosqlite.Row
                    try:
                        await init_db(conn)
                        return await save_run(conn, RunResult(run_id=f"parallel-{index}", country="korea"))
                    finally:
                        await conn.close()

                return asyncio.run(_inner())

            row_ids = await asyncio.gather(*(asyncio.to_thread(worker, index) for index in range(4)))

            self.assertEqual(len(row_ids), 4)

            verify_conn = await aiosqlite.connect(db_path)
            verify_conn.row_factory = aiosqlite.Row
            try:
                cursor = await verify_conn.execute("SELECT COUNT(*) AS cnt FROM runs")
                row = await cursor.fetchone()
                self.assertEqual(row["cnt"], 4)
            finally:
                await verify_conn.close()


class _FakeCache:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=60):
        self.store[key] = value

    async def exists(self, key):
        return key in self.store


class TestSharedCacheIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_redis_ok = db_module._REDIS_OK
        self._original_get_cache = getattr(db_module, "get_cache", None)
        self.cache = _FakeCache()
        db_module._REDIS_OK = True
        db_module.get_cache = lambda: self.cache

    async def asyncSetUp(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        await init_db(self.conn)
        run = RunResult(run_id="shared-cache-test")
        self.run_id = await save_run(self.conn, run)

    async def asyncTearDown(self):
        await self.conn.close()

    def tearDown(self):
        db_module._REDIS_OK = self._original_redis_ok
        if self._original_get_cache is None:
            delattr(db_module, "get_cache")
        else:
            db_module.get_cache = self._original_get_cache

    @pytest.mark.asyncio
    async def test_duplicate_trend_reads_cache_before_db(self):
        fingerprint = compute_fingerprint("cache-first", 12000)
        self.cache.store[f"gdt:dedup:{fingerprint}"] = True

        is_dup = await is_duplicate_trend(self.conn, "cache-first", 12000)
        self.assertTrue(is_dup)

    @pytest.mark.asyncio
    async def test_get_cached_score_populates_and_reuses_cache(self):
        trend = ScoredTrend(
            keyword="cache-score",
            rank=1,
            volume_last_24h=50000,
            viral_potential=92,
            top_insight="cache me",
            sources=[TrendSource.GETDAYTRENDS],
        )
        await save_trend(self.conn, trend, self.run_id)
        fingerprint = compute_fingerprint("cache-score", 50000)

        first = await get_cached_score(self.conn, fingerprint)
        self.assertIsNotNone(first)
        self.assertEqual(first["keyword"], "cache-score")
        self.assertIn(f"gdt:score:{fingerprint}", self.cache.store)

        await self.conn.execute("DELETE FROM trends")
        await self.conn.commit()

        second = await get_cached_score(self.conn, fingerprint)
        self.assertEqual(second, first)

    @pytest.mark.asyncio
    async def test_get_cached_content_populates_and_reuses_cache(self):
        trend = ScoredTrend(
            keyword="cache-content",
            rank=1,
            volume_last_24h=40000,
            sources=[TrendSource.GETDAYTRENDS],
        )
        trend_id = await save_trend(self.conn, trend, self.run_id)
        tweet = GeneratedTweet(tweet_type="short", content="cached body")
        await save_tweet(self.conn, tweet, trend_id, self.run_id)
        fingerprint = compute_fingerprint("cache-content", 40000)

        first = await get_cached_content(self.conn, fingerprint)
        self.assertIsNotNone(first)
        self.assertEqual(len(first), 1)
        self.assertIn(f"gdt:content:{fingerprint}", self.cache.store)

        await self.conn.execute("DELETE FROM tweets")
        await self.conn.commit()

        second = await get_cached_content(self.conn, fingerprint)
        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
