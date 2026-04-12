import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
respx = pytest.importorskip("respx")

from perf_models import GoldenReference, TweetMetrics
from performance_tracker import PerformanceTracker


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Provide a temporary database path for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)

@pytest.fixture
def tracker(temp_db: str) -> PerformanceTracker:
    """Create a PerformanceTracker instance connected to the temp database."""
    t = PerformanceTracker(db_path=temp_db, bearer_token="test_token")

    # We must ensure there is a `tweets` table for foreign keys and sync logic *before* init_table
    conn = t._get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x_tweet_id TEXT,
            content TEXT,
            score REAL,
            posted_at TEXT,
            impressions INTEGER DEFAULT 0,
            engagements INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0,
            tweet_type TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

    t.init_table()
    return t

    # We must ensure there is a `tweets` table for foreign keys and sync logic
    conn = t._get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x_tweet_id TEXT,
            content TEXT,
            score REAL,
            posted_at TEXT,
            impressions INTEGER DEFAULT 0,
            engagements INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0,
            tweet_type TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()
    return t


def test_init_table_idempotent(tracker: PerformanceTracker) -> None:
    """Test that init_table doesn't crash on multiple calls."""
    tracker.init_table()
    tracker.init_table()  # should be idempotent

    conn = tracker._get_conn()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "tweet_performance" in tables
    assert "golden_references" in tables
    assert "trend_genealogy" in tables
    conn.close()


def test_save_metrics(tracker: PerformanceTracker) -> None:
    """Test saving metrics to database."""
    metrics = TweetMetrics(
        tweet_id="123456",
        impressions=1000,
        likes=50,
        retweets=10,
        replies=5,
        quotes=2,
        angle_type="question",
        collected_at=datetime.now(UTC),
    )
    metrics.compute_engagement_rate()

    tracker.save_metrics(metrics)

    conn = tracker._get_conn()
    row = conn.execute("SELECT * FROM tweet_performance WHERE tweet_id = '123456'").fetchone()
    assert row is not None
    assert row["impressions"] == 1000
    assert row["likes"] == 50
    assert row["engagement_rate"] == metrics.engagement_rate
    conn.close()


def test_golden_references_crud(tracker: PerformanceTracker) -> None:
    """Test CRUD operations on Golden References via mixin."""
    ref = GoldenReference(
        tweet_id="999",
        content="Test golden tweet",
        angle_type="story",
        hook_pattern="question",
        kick_pattern="call_to_action",
        engagement_rate=0.08,
        impressions=5000,
        saved_at=datetime.now(UTC)
    )

    tracker.save_golden_reference(ref)

    refs = tracker.get_golden_references(limit=5)
    assert len(refs) == 1
    assert refs[0].tweet_id == "999"
    assert refs[0].content == "Test golden tweet"
    assert refs[0].engagement_rate == 0.08


@pytest.mark.asyncio
async def test_batch_collect_no_token() -> None:
    """Test that batch_collect exits gracefully without token."""
    t = PerformanceTracker(bearer_token="")
    result = await t.batch_collect(["1", "2"])
    assert result == []


@respx.mock
@pytest.mark.asyncio
async def test_batch_collect_success(tracker: PerformanceTracker) -> None:
    """Test batch collecting from X API."""
    respx.get("https://api.twitter.com/2/tweets").respond(
        status_code=200,
        json={
            "data": [
                {
                    "id": "111",
                    "public_metrics": {
                        "impression_count": 100,
                        "like_count": 5,
                        "retweet_count": 1,
                        "reply_count": 0,
                        "quote_count": 0
                    }
                }
            ]
        }
    )

    result = await tracker.batch_collect(["111"])
    assert len(result) == 1
    metrics = result[0]
    assert metrics.tweet_id == "111"
    assert metrics.impressions == 100
    assert metrics.likes == 5


def test_angle_performance_computation(tracker: PerformanceTracker) -> None:
    """Test that get_angle_performance correctly aggregates data."""
    now = datetime.now(UTC)
    # Insert dummy data
    m1 = TweetMetrics("1", impressions=1000, likes=100, angle_type="contrarian", collected_at=now)
    m1.compute_engagement_rate()
    m2 = TweetMetrics("2", impressions=1000, likes=150, angle_type="contrarian", collected_at=now)
    m2.compute_engagement_rate()
    m3 = TweetMetrics("3", impressions=1000, likes=50, angle_type="story", collected_at=now)
    m3.compute_engagement_rate()

    tracker.save_metrics_batch([m1, m2, m3])

    stats = tracker.get_angle_performance(days=7)
    assert stats["contrarian"].total_tweets == 2
    assert stats["contrarian"].avg_impressions == 1000.0
    # (0.1 + 0.15) / 2 = 0.125
    assert stats["contrarian"].avg_engagement_rate == pytest.approx(0.125)
    assert stats["story"].total_tweets == 1

def test_auto_update_golden_references(tracker: PerformanceTracker) -> None:
    """Test auto updating golden references from top tweets."""
    # To test this, we need tweets in `tweet_performance` and matching `tweets` table content.
    now = datetime.now(UTC)
    m1 = TweetMetrics("123", impressions=5000, likes=500, collected_at=now)
    m1.compute_engagement_rate()

    tracker.save_metrics(m1)

    # ensure it exists in tweets table
    conn = tracker._get_conn()
    conn.execute("INSERT INTO tweets (id, x_tweet_id, content) VALUES (123, '123', 'My viral tweet')")
    conn.commit()
    conn.close()

    saved_count = tracker.auto_update_golden_references(days=1, top_n=5)
    assert saved_count == 1

    refs = tracker.get_golden_references()
    assert len(refs) == 1
    assert refs[0].tweet_id == "123"
    assert refs[0].content == "My viral tweet"
