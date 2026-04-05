"""_async_collect_contexts 글로벌 타임아웃 방어 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import AppConfig
from models import MultiSourceContext, RawTrend, TrendSource


def _make_raw_trend(name: str = "테스트 트렌드") -> RawTrend:
    return RawTrend(
        name=name,
        rank=1,
        source=TrendSource.GOOGLE_TRENDS,
        extra={},
    )


class TestContextGlobalTimeout:
    """_async_collect_contexts: 전체 수집 글로벌 타임아웃 방어."""

    @pytest.mark.asyncio
    async def test_global_timeout_returns_empty_contexts(self):
        """전체 수집이 타임아웃 초과 시 빈 컨텍스트 반환 (크래시 아님)."""
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 0.01  # 매우 짧은 타임아웃

        trend = _make_raw_trend()

        # 느린 소스 시뮬레이션
        async def _slow_fetch(*args, **kwargs):
            await asyncio.sleep(5)
            return ("테스트 트렌드", "twitter", "데이터")

        with patch("collectors.context._async_fetch_single_source", side_effect=_slow_fetch):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=None)

        # 타임아웃 시 빈 컨텍스트 반환
        assert isinstance(contexts, dict)
        # 비어 있거나 빈 필드를 가진 컨텍스트
        if "테스트 트렌드" in contexts:
            ctx = contexts["테스트 트렌드"]
            assert ctx.twitter_insight == ""

    @pytest.mark.asyncio
    async def test_normal_collection_succeeds(self):
        """정상 속도에서는 컨텍스트가 정상 반환된다."""
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 30

        trend = _make_raw_trend("정상 트렌드")

        async def _fast_fetch(session, keyword, source, bearer, extra, **kwargs):
            return (keyword, source, f"{source} 인사이트")

        with patch("collectors.context._async_fetch_single_source", side_effect=_fast_fetch):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=None)

        assert "정상 트렌드" in contexts
        ctx = contexts["정상 트렌드"]
        assert "인사이트" in ctx.twitter_insight

    @pytest.mark.asyncio
    async def test_partial_source_failure_preserves_others(self):
        """한 소스만 예외를 던져도 나머지 소스 데이터는 보존된다."""
        from collectors.context import _async_collect_contexts

        config = AppConfig()
        config.context_global_timeout = 30

        trend = _make_raw_trend("부분실패")

        call_count = 0

        async def _mixed_fetch(session, keyword, source, bearer, extra, **kwargs):
            nonlocal call_count
            call_count += 1
            if source == "twitter":
                raise ConnectionError("Twitter API down")
            return (keyword, source, f"{source} 데이터")

        with patch("collectors.context._async_fetch_single_source", side_effect=_mixed_fetch):
            contexts = await _async_collect_contexts([trend], config, session=None, conn=None)

        assert "부분실패" in contexts
        ctx = contexts["부분실패"]
        # twitter 실패 → 빈 문자열, 나머지 정상
        assert ctx.twitter_insight == ""
        assert "데이터" in ctx.reddit_insight or "데이터" in ctx.news_insight
