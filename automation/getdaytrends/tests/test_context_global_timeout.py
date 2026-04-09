"""Tests for _async_collect_contexts timeout and metrics handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import AppConfig
from models import RawTrend, TrendSource


def _make_raw_trend(name: str = "test-trend") -> RawTrend:
    return RawTrend(
        name=name,
        rank=1,
        source=TrendSource.GOOGLE_TRENDS,
        extra={},
    )


class TestContextGlobalTimeout:
    @pytest.mark.asyncio
    async def test_partial_timeout_preserves_completed_results(self):
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 0.05
        trend = _make_raw_trend("partial-timeout")

        async def _mixed_fetch(session, keyword, source, bearer, extra, **kwargs):
            if source == "twitter":
                await asyncio.sleep(0)
                return (keyword, source, "twitter payload")
            await asyncio.sleep(0.2)
            return (keyword, source, f"{source} payload")

        with patch("collectors.context._async_fetch_single_source", side_effect=_mixed_fetch), patch(
            "news_scraper.enrich_news_context",
            side_effect=lambda keyword, text: text,
        ):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=None)

        assert "partial-timeout" in contexts
        ctx = contexts["partial-timeout"]
        assert ctx.twitter_insight == "twitter payload"
        assert ctx.reddit_insight == ""
        assert ctx.news_insight == ""

    @pytest.mark.asyncio
    async def test_source_quality_write_failure_does_not_drop_collected_context(self):
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 30
        trend = _make_raw_trend("quality-metrics")

        with patch(
            "collectors.context._async_fetch_twitter_trends",
            new_callable=AsyncMock,
            return_value="twitter insight payload",
        ), patch(
            "collectors.context._async_fetch_reddit_trends",
            new_callable=AsyncMock,
            return_value="reddit insight payload",
        ), patch(
            "collectors.context._async_fetch_google_news_trends",
            new_callable=AsyncMock,
            return_value="news insight payload",
        ), patch(
            "db.get_source_quality_summary",
            new_callable=AsyncMock,
            return_value={},
        ), patch(
            "db.record_source_quality",
            new_callable=AsyncMock,
            side_effect=RuntimeError("metrics db unavailable"),
        ) as mock_record_quality, patch(
            "news_scraper.enrich_news_context",
            side_effect=lambda keyword, text: text,
        ):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=MagicMock())

        assert "quality-metrics" in contexts
        ctx = contexts["quality-metrics"]
        assert ctx.twitter_insight == "twitter insight payload"
        assert ctx.reddit_insight == "reddit insight payload"
        assert ctx.news_insight == "news insight payload"
        assert mock_record_quality.await_count == 3

    @pytest.mark.asyncio
    async def test_source_quality_writes_are_serialized_after_parallel_fetch(self):
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 30
        trend = _make_raw_trend("serialized-metrics")

        in_flight = 0
        max_in_flight = 0

        async def _record_serialized(*args, **kwargs):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1

        with patch(
            "collectors.context._async_fetch_twitter_trends",
            new_callable=AsyncMock,
            return_value="twitter insight payload",
        ), patch(
            "collectors.context._async_fetch_reddit_trends",
            new_callable=AsyncMock,
            return_value="reddit insight payload",
        ), patch(
            "collectors.context._async_fetch_google_news_trends",
            new_callable=AsyncMock,
            return_value="news insight payload",
        ), patch(
            "db.get_source_quality_summary",
            new_callable=AsyncMock,
            return_value={},
        ), patch(
            "db.record_source_quality",
            side_effect=_record_serialized,
        ) as mock_record_quality, patch(
            "news_scraper.enrich_news_context",
            side_effect=lambda keyword, text: text,
        ):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=MagicMock())

        assert "serialized-metrics" in contexts
        assert mock_record_quality.await_count == 3
        assert max_in_flight == 1
