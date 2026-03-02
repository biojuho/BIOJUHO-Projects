"""db.py 테스트: SQLite 스키마, CRUD 헬퍼 함수."""

import os
import sqlite3
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import (
    get_recently_processed_keywords,
    get_trend_stats,
    init_db,
    save_run,
    save_thread,
    save_trend,
    save_tweet,
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


class TestInitDb(unittest.TestCase):
    """DB 초기화 및 스키마 검증."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_tables_created(self):
        init_db(self.conn)
        tables = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        self.assertIn("runs", table_names)
        self.assertIn("trends", table_names)
        self.assertIn("tweets", table_names)

    def test_idempotent(self):
        """두 번 호출해도 오류 없어야 함."""
        init_db(self.conn)
        init_db(self.conn)  # 두 번째 호출

    def test_content_type_column_exists(self):
        init_db(self.conn)
        row = self.conn.execute("PRAGMA table_info(tweets)").fetchall()
        columns = {r["name"] for r in row}
        self.assertIn("content_type", columns)


class TestSaveRun(unittest.TestCase):
    """실행 기록 저장/업데이트."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_save_and_retrieve(self):
        run = RunResult(run_id="test-uuid-123", country="korea")
        row_id = save_run(self.conn, run)
        self.assertGreater(row_id, 0)

        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (row_id,)).fetchone()
        self.assertEqual(row["run_uuid"], "test-uuid-123")
        self.assertEqual(row["country"], "korea")

    def test_update_run(self):
        run = RunResult(run_id="test-update", country="korea")
        row_id = save_run(self.conn, run)

        run.trends_collected = 5
        run.tweets_generated = 10
        run.finished_at = datetime.now()
        update_run(self.conn, run, row_id)

        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (row_id,)).fetchone()
        self.assertEqual(row["trends_collected"], 5)
        self.assertEqual(row["tweets_generated"], 10)
        self.assertIsNotNone(row["finished_at"])


class TestSaveTrend(unittest.TestCase):
    """트렌드 저장."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        run = RunResult(run_id="trend-test")
        self.run_id = save_run(self.conn, run)

    def tearDown(self):
        self.conn.close()

    def test_save_trend(self):
        trend = ScoredTrend(
            keyword="AI 규제",
            rank=1,
            viral_potential=85,
            top_insight="AI 규제 이슈",
            sources=[TrendSource.GETDAYTRENDS, TrendSource.REDDIT],
            context=MultiSourceContext(twitter_insight="hot topic"),
        )
        trend_id = save_trend(self.conn, trend, self.run_id)
        self.assertGreater(trend_id, 0)

        row = self.conn.execute("SELECT * FROM trends WHERE id=?", (trend_id,)).fetchone()
        self.assertEqual(row["keyword"], "AI 규제")
        self.assertEqual(row["viral_potential"], 85)


class TestSaveTweet(unittest.TestCase):
    """트윗 저장."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        run = RunResult(run_id="tweet-test")
        self.run_id = save_run(self.conn, run)
        trend = ScoredTrend(keyword="test", rank=1, sources=[TrendSource.GETDAYTRENDS])
        self.trend_id = save_trend(self.conn, trend, self.run_id)

    def tearDown(self):
        self.conn.close()

    def test_save_short_tweet(self):
        tweet = GeneratedTweet(tweet_type="공감 유도형", content="테스트 트윗입니다")
        tweet_id = save_tweet(self.conn, tweet, self.trend_id, self.run_id)
        self.assertGreater(tweet_id, 0)

        row = self.conn.execute("SELECT * FROM tweets WHERE id=?", (tweet_id,)).fetchone()
        self.assertEqual(row["tweet_type"], "공감 유도형")
        self.assertEqual(row["content_type"], "short")

    def test_save_long_tweet(self):
        tweet = GeneratedTweet(tweet_type="딥다이브", content="장문 포스트" * 100, content_type="long")
        tweet_id = save_tweet(self.conn, tweet, self.trend_id, self.run_id)

        row = self.conn.execute("SELECT * FROM tweets WHERE id=?", (tweet_id,)).fetchone()
        self.assertEqual(row["content_type"], "long")


class TestSaveThread(unittest.TestCase):
    """쓰레드 저장."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        run = RunResult(run_id="thread-test")
        self.run_id = save_run(self.conn, run)
        trend = ScoredTrend(keyword="thread-test", rank=1, sources=[TrendSource.GETDAYTRENDS])
        self.trend_id = save_trend(self.conn, trend, self.run_id)

    def tearDown(self):
        self.conn.close()

    def test_save_thread(self):
        thread = GeneratedThread(tweets=["훅 트윗", "본문 1", "본문 2", "마무리"])
        ids = save_thread(self.conn, thread, self.trend_id, self.run_id)
        self.assertEqual(len(ids), 4)

        rows = self.conn.execute(
            "SELECT * FROM tweets WHERE trend_id=? AND is_thread=1 ORDER BY thread_order",
            (self.trend_id,),
        ).fetchall()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["content"], "훅 트윗")
        self.assertEqual(rows[3]["thread_order"], 3)


class TestGetRecentlyProcessed(unittest.TestCase):
    """중복 필터 함수."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        run = RunResult(run_id="dedup-test")
        self.run_id = save_run(self.conn, run)

    def tearDown(self):
        self.conn.close()

    def test_empty_db(self):
        keywords = get_recently_processed_keywords(self.conn, hours=3)
        self.assertEqual(keywords, set())

    def test_finds_recent(self):
        trend = ScoredTrend(keyword="최근키워드", rank=1, sources=[TrendSource.GETDAYTRENDS])
        save_trend(self.conn, trend, self.run_id)

        keywords = get_recently_processed_keywords(self.conn, hours=3)
        self.assertIn("최근키워드", keywords)


class TestGetTrendStats(unittest.TestCase):
    """통계 함수."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_empty_stats(self):
        stats = get_trend_stats(self.conn)
        self.assertEqual(stats["total_runs"], 0)
        self.assertEqual(stats["total_trends"], 0)
        self.assertEqual(stats["total_tweets"], 0)

    def test_with_data(self):
        run = RunResult(run_id="stats-test")
        run_id = save_run(self.conn, run)
        trend = ScoredTrend(keyword="stat", rank=1, viral_potential=80, sources=[TrendSource.GETDAYTRENDS])
        trend_id = save_trend(self.conn, trend, run_id)
        tweet = GeneratedTweet(tweet_type="test", content="hello")
        save_tweet(self.conn, tweet, trend_id, run_id)

        stats = get_trend_stats(self.conn)
        self.assertEqual(stats["total_runs"], 1)
        self.assertEqual(stats["total_trends"], 1)
        self.assertEqual(stats["total_tweets"], 1)
        self.assertEqual(stats["avg_viral_score"], 80.0)


if __name__ == "__main__":
    unittest.main()
