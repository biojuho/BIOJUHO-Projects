"""Tests for scripts/refresh_tweet_metrics.py — the measured-label pipeline glue."""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from scripts.refresh_tweet_metrics import (
    engagement_from_x_metrics,
    refresh_from_x,
    set_manual,
)


@pytest_asyncio.fixture
async def db(memory_db):
    return memory_db


async def _seed_trend(db) -> tuple[int, int]:
    """Insert a run + trend so tweets can satisfy the run_id/trend_id NOT NULL cols.

    Returns ``(run_id, trend_id)``.
    """
    from db_layer.trend_repository import save_trend
    from models import MultiSourceContext, ScoredTrend

    run_cursor = await db.execute(
        "INSERT INTO runs (run_uuid, started_at) VALUES (?, ?)",
        (str(uuid.uuid4()), datetime.now().isoformat()),
    )
    await db.commit()
    run_id = run_cursor.lastrowid
    trend = ScoredTrend(
        keyword="측정테스트트렌드",
        rank=1,
        viral_potential=75,
        trend_acceleration="+5%",
        top_insight="인사이트",
        suggested_angles=["앵글1"],
        best_hook_starter="훅",
        context=MultiSourceContext(twitter_insight="X", reddit_insight="R"),
        safety_flag=False,
        sentiment="neutral",
    )
    trend_id = await save_trend(db, trend, run_id)
    return run_id, trend_id


async def _seed_posted_tweet(db, *, x_tweet_id: str, impressions: int = 0) -> int:
    """Insert one posted tweet carrying an x_tweet_id and return its row id."""
    run_id, trend_id = await _seed_trend(db)
    cursor = await db.execute(
        """INSERT INTO tweets
               (trend_id, run_id, tweet_type, content, status, x_tweet_id, impressions, posted_at, generated_at)
           VALUES (?, ?, ?, ?, 'posted', ?, ?, ?, ?)""",
        (
            trend_id,
            run_id,
            "공감 유도형",
            "측정 테스트 트윗",
            x_tweet_id,
            impressions,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ),
    )
    await db.commit()
    return cursor.lastrowid


# ── engagement_from_x_metrics (pure) ──────────────────────────────────────────


class TestEngagementMapping:
    def test_maps_views_and_sums_interactions(self):
        metrics = {"views": 1000, "likes": 30, "retweets": 10, "quotes": 5, "replies": 5}
        impressions, engagements, rate = engagement_from_x_metrics(metrics)
        assert impressions == 1000
        assert engagements == 50
        assert rate == pytest.approx(0.05)

    def test_zero_impressions_yields_zero_rate_no_div_by_zero(self):
        impressions, engagements, rate = engagement_from_x_metrics(
            {"views": 0, "likes": 7, "retweets": 0, "quotes": 0, "replies": 0}
        )
        assert impressions == 0
        assert engagements == 7
        assert rate == 0.0

    def test_missing_keys_default_to_zero(self):
        assert engagement_from_x_metrics({}) == (0, 0, 0.0)


# ── refresh_from_x (orchestration with injected fetcher) ───────────────────────


class TestRefreshFromX:
    @pytest.mark.asyncio
    async def test_fetches_and_persists_metrics(self, db):
        row_id = await _seed_posted_tweet(db, x_tweet_id="x-123")

        async def fake_fetcher(tweet_id):
            assert tweet_id == "x-123"
            return {"views": 500, "likes": 20, "retweets": 5, "quotes": 0, "replies": 0}

        summary = await refresh_from_x(db, fetcher=fake_fetcher)
        assert summary["updated"] == 1
        assert summary["candidates"] == 1

        cursor = await db.execute(
            "SELECT impressions, engagements, engagement_rate FROM tweets WHERE id = ?",
            (row_id,),
        )
        impressions, engagements, rate = await cursor.fetchone()
        assert impressions == 500
        assert engagements == 25
        assert rate == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_dry_run_does_not_write(self, db):
        row_id = await _seed_posted_tweet(db, x_tweet_id="x-dry")

        async def fake_fetcher(_tweet_id):
            return {"views": 999, "likes": 1, "retweets": 0, "quotes": 0, "replies": 0}

        summary = await refresh_from_x(db, fetcher=fake_fetcher, dry_run=True)
        assert summary["updated"] == 0
        assert len(summary["details"]) == 1

        cursor = await db.execute("SELECT impressions FROM tweets WHERE id = ?", (row_id,))
        (impressions,) = await cursor.fetchone()
        assert impressions == 0  # unchanged

    @pytest.mark.asyncio
    async def test_only_missing_skips_already_measured(self, db):
        await _seed_posted_tweet(db, x_tweet_id="x-has", impressions=2000)

        async def fake_fetcher(_tweet_id):  # pragma: no cover - should not be called
            raise AssertionError("fetcher called for an already-measured tweet")

        summary = await refresh_from_x(db, fetcher=fake_fetcher, only_missing=True)
        assert summary["candidates"] == 0
        assert summary["updated"] == 0

    @pytest.mark.asyncio
    async def test_all_includes_already_measured(self, db):
        await _seed_posted_tweet(db, x_tweet_id="x-has", impressions=2000)

        async def fake_fetcher(_tweet_id):
            return {"views": 3000, "likes": 90, "retweets": 0, "quotes": 0, "replies": 0}

        summary = await refresh_from_x(db, fetcher=fake_fetcher, only_missing=False)
        assert summary["candidates"] == 1
        assert summary["updated"] == 1

    @pytest.mark.asyncio
    async def test_skips_when_fetcher_returns_none(self, db):
        await _seed_posted_tweet(db, x_tweet_id="x-none")

        async def fake_fetcher(_tweet_id):
            return None

        summary = await refresh_from_x(db, fetcher=fake_fetcher)
        assert summary["updated"] == 0
        assert summary["skipped_no_metrics"] == ["x-none"]


# ── set_manual ────────────────────────────────────────────────────────────────


class TestSetManual:
    @pytest.mark.asyncio
    async def test_manual_entry_by_row_id(self, db):
        row_id = await _seed_posted_tweet(db, x_tweet_id="x-manual")
        summary = await set_manual(db, tweet_row_id=row_id, impressions=400, engagements=40)
        assert summary["matched"] == 1
        assert summary["engagement_rate"] == pytest.approx(0.1)

        cursor = await db.execute(
            "SELECT impressions, engagements, engagement_rate FROM tweets WHERE id = ?",
            (row_id,),
        )
        impressions, engagements, rate = await cursor.fetchone()
        assert (impressions, engagements) == (400, 40)
        assert rate == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_manual_entry_by_x_tweet_id(self, db):
        await _seed_posted_tweet(db, x_tweet_id="x-bykey")
        summary = await set_manual(db, x_tweet_id="x-bykey", impressions=100, engagements=5)
        assert summary["matched"] == 1
