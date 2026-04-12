import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
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

@pytest_asyncio.fixture
async def tracker(temp_db: str) -> PerformanceTracker:
    """Create a PerformanceTracker instance connected to the temp database."""
    # SQLite 락 충돌 방지를 위해 WAL 모드 강제 적용
    import sqlite3
    conn_sync = sqlite3.connect(temp_db)
    conn_sync.execute("PRAGMA journal_mode=WAL")
    conn_sync.close()

    t = PerformanceTracker(db_path=temp_db, bearer_token="test_token")
    
    conn = await t._get_conn()
    await conn.executescript("""
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
        );
        CREATE TABLE IF NOT EXISTS tweet_performance (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id     TEXT NOT NULL UNIQUE,
            impressions  INTEGER DEFAULT 0,
            likes        INTEGER DEFAULT 0,
            retweets     INTEGER DEFAULT 0,
            replies      INTEGER DEFAULT 0,
            quotes       INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0,
            angle_type   TEXT DEFAULT '',
            hook_pattern TEXT DEFAULT '',
            kick_pattern TEXT DEFAULT '',
            collection_tier TEXT DEFAULT '48h',
            collected_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS golden_references (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id        TEXT NOT NULL UNIQUE,
            content         TEXT NOT NULL,
            angle_type      TEXT DEFAULT '',
            hook_pattern    TEXT DEFAULT '',
            kick_pattern    TEXT DEFAULT '',
            engagement_rate REAL DEFAULT 0.0,
            impressions     INTEGER DEFAULT 0,
            category        TEXT DEFAULT '',
            saved_at        TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trend_genealogy (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword         TEXT NOT NULL,
            parent_keyword  TEXT DEFAULT '',
            predicted_children TEXT DEFAULT '[]',
            genealogy_depth INTEGER DEFAULT 0,
            first_seen_at   TEXT NOT NULL,
            last_seen_at    TEXT NOT NULL,
            total_appearances INTEGER DEFAULT 1,
            peak_viral_score INTEGER DEFAULT 0,
            UNIQUE(keyword, parent_keyword)
        );
    """)
    if hasattr(conn, "commit"):
        await conn.commit()
    await conn.close()

    return t

@pytest.mark.asyncio
async def test_init_table_idempotent(tracker: PerformanceTracker) -> None:
    """Test that init_table doesn't crash on multiple calls."""
    await tracker.init_table()
    await tracker.init_table()  # should be idempotent
    
    conn = await tracker._get_conn()
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    rows = await cursor.fetchall()
    tables = [r[0] for r in rows]
    assert "tweet_performance" in tables
    assert "golden_references" in tables
    assert "trend_genealogy" in tables
    await conn.close()

@pytest.mark.asyncio
async def test_save_metrics(tracker: PerformanceTracker) -> None:
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

    await tracker.save_metrics(metrics)

    conn = await tracker._get_conn()
    cursor = await conn.execute("SELECT * FROM tweet_performance WHERE tweet_id = '123456'")
    row = await cursor.fetchone()
    assert row is not None
    assert row["impressions"] == 1000
    assert row["likes"] == 50
    assert row["engagement_rate"] == metrics.engagement_rate
    await conn.close()

@pytest.mark.asyncio
async def test_golden_references_crud(tracker: PerformanceTracker) -> None:
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

    await tracker.save_golden_reference(ref)

    refs = await tracker.get_golden_references(limit=5)
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

@pytest.mark.asyncio
async def test_angle_performance_computation(tracker: PerformanceTracker) -> None:
    """Test that get_angle_performance correctly aggregates data."""
    now = datetime.now(UTC)
    # Insert dummy data
    m1 = TweetMetrics("1", impressions=1000, likes=100, angle_type="contrarian", collected_at=now)
    m1.compute_engagement_rate()
    m2 = TweetMetrics("2", impressions=1000, likes=150, angle_type="contrarian", collected_at=now)
    m2.compute_engagement_rate()
    m3 = TweetMetrics("3", impressions=1000, likes=50, angle_type="story", collected_at=now)
    m3.compute_engagement_rate()

    await tracker.save_metrics_batch([m1, m2, m3])

    stats = await tracker.get_angle_performance(days=7)
    assert stats["contrarian"].total_tweets == 2
    assert stats["contrarian"].avg_impressions == 1000.0
    # (0.1 + 0.15) / 2 = 0.125
    assert stats["contrarian"].avg_engagement_rate == pytest.approx(0.125)
    assert stats["story"].total_tweets == 1

@pytest.mark.asyncio
async def test_auto_update_golden_references(tracker: PerformanceTracker) -> None:
    """Test auto updating golden references from top tweets."""
    # To test this, we need tweets in `tweet_performance` and matching `tweets` table content.
    now = datetime.now(UTC)
    m1 = TweetMetrics("123", impressions=5000, likes=500, collected_at=now)
    m1.compute_engagement_rate()

    await tracker.save_metrics(m1)

    # ensure it exists in tweets table
    conn = await tracker._get_conn()
    await conn.execute("INSERT INTO tweets (id, x_tweet_id, content) VALUES (123, '123', 'My viral tweet')")
    if hasattr(conn, "commit"):
        await conn.commit()
    await conn.close()

    saved_count = await tracker.auto_update_golden_references(days=1, top_n=5)
    assert saved_count == 1

    refs = await tracker.get_golden_references()
    assert len(refs) == 1
    assert refs[0].tweet_id == "123"
    assert refs[0].content == "My viral tweet"
