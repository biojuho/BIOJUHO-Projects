"""
generator.py 테스트: 점수 조건별 생성 분기, 프롬프트 빌더, retry 래퍼, 멀티언어/AB.
v3.0: _retry_generate, safety_flag 통합 테스트 추가.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


from config import AppConfig
from generator import (
    _build_context_section,
    _build_scoring_section,
    _resolve_language,
)
from models import GeneratedTweet, MultiSourceContext, ScoredTrend, TweetBatch


def _make_trend(viral: int = 75, acc: str = "+5%") -> ScoredTrend:
    return ScoredTrend(
        keyword="테스트 트렌드",
        rank=1,
        viral_potential=viral,
        trend_acceleration=acc,
        top_insight="핵심 인사이트",
        suggested_angles=["앵글1", "앵글2"],
        best_hook_starter="최고의 훅",
        context=MultiSourceContext(
            twitter_insight="X 인사이트",
            reddit_insight="Reddit 인사이트",
            news_insight="뉴스 인사이트",
        ),
    )


def _make_config(**kwargs) -> AppConfig:
    cfg = AppConfig()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestResolveLanguage(unittest.TestCase):
    def test_korea(self):
        cfg = _make_config(country="korea")
        self.assertIn("한국어", _resolve_language(cfg))

    def test_us(self):
        cfg = _make_config(country="us")
        self.assertIn("English", _resolve_language(cfg))

    def test_japan(self):
        cfg = _make_config(country="japan")
        self.assertIn("Japanese", _resolve_language(cfg))

    def test_unknown_defaults_to_korean(self):
        cfg = _make_config(country="unknown")
        self.assertIn("한국어", _resolve_language(cfg))


class TestBuildContextSection(unittest.TestCase):
    def test_with_context(self):
        trend = _make_trend()
        section = _build_context_section(trend)
        self.assertIn("X 인사이트", section)
        self.assertIn("Reddit 인사이트", section)

    def test_no_context(self):
        trend = _make_trend()
        trend.context = None
        self.assertEqual(_build_context_section(trend), "")


class TestBuildScoringSection(unittest.TestCase):
    def test_includes_score(self):
        trend = _make_trend(viral=82)
        section = _build_scoring_section(trend)
        self.assertIn("82", section)
        self.assertIn("앵글1", section)

    def test_zero_score_empty(self):
        trend = _make_trend(viral=0)
        self.assertEqual(_build_scoring_section(trend), "")


class TestGenerationTierGating(unittest.TestCase):
    """generate_for_trend_async의 조건부 생성 분기 검증 (mock)."""

    def _make_batch(self) -> TweetBatch:
        return TweetBatch(
            topic="테스트",
            tweets=[GeneratedTweet(tweet_type="공감 유도형", content="트윗 내용", content_type="short")],
        )

    @patch("generator.generate_tweets_async", new_callable=AsyncMock)
    @patch("generator.generate_long_form_async", new_callable=AsyncMock)
    @patch("generator.generate_thread_async", new_callable=AsyncMock)
    @patch("generator.generate_tweets_and_threads_async", new_callable=AsyncMock)
    def test_low_score_only_tweets(self, mock_combined, mock_thread, mock_long, mock_tweets):
        """60점 트렌드 → 단문 트윗만 생성 (Threads 미달, Sonnet 미달)."""
        import asyncio
        mock_tweets.return_value = self._make_batch()

        cfg = _make_config(
            enable_long_form=True,
            long_form_min_score=95,
            thread_min_score=92,
            threads_min_score=65,
            enable_threads=True,
        )
        trend = _make_trend(viral=60)
        client = MagicMock()

        from generator import generate_for_trend_async
        result = asyncio.run(generate_for_trend_async(trend, cfg, client))

        self.assertIsNotNone(result)
        mock_tweets.assert_called_once()   # 개별 트윗 생성
        mock_combined.assert_not_called()  # 65점 미달 → 통합 안 함
        mock_long.assert_not_called()      # 95점 미달
        mock_thread.assert_not_called()    # 92점 미달

    @patch("generator.generate_tweets_and_threads_async", new_callable=AsyncMock)
    @patch("generator.generate_long_form_async", new_callable=AsyncMock)
    @patch("generator.generate_thread_async", new_callable=AsyncMock)
    def test_high_score_all_generated(self, mock_thread, mock_long, mock_combined):
        """96점 트렌드 → 통합(트윗+Threads) + Sonnet 장문 + 쓰레드 전체 생성."""
        import asyncio
        mock_combined.return_value = self._make_batch()
        mock_long.return_value = []
        mock_thread.return_value = None

        cfg = _make_config(
            enable_long_form=True,
            long_form_min_score=95,
            thread_min_score=92,
            threads_min_score=65,
            enable_threads=True,
        )
        trend = _make_trend(viral=96)
        client = MagicMock()

        from generator import generate_for_trend_async
        result = asyncio.run(generate_for_trend_async(trend, cfg, client))

        self.assertIsNotNone(result)
        mock_combined.assert_called_once()  # C1: 통합 호출
        mock_long.assert_called_once()      # 96 >= 95
        mock_thread.assert_called_once()    # 96 >= 92


class TestRetryGenerate(unittest.IsolatedAsyncioTestCase):
    """_retry_generate 래퍼 동작 검증."""

    async def test_success_on_first_try(self):
        """첫 시도에 성공하면 재시도 없이 결과 반환."""
        from generator import _retry_generate

        called = 0

        async def _factory():
            nonlocal called
            called += 1
            return "결과"

        result = await _retry_generate(_factory, "테스트")
        self.assertEqual(result, "결과")
        self.assertEqual(called, 1)

    async def test_retry_on_none_result(self):
        """None 반환 시 재시도 후 성공값 반환."""
        from generator import _retry_generate

        results = [None, None, "성공"]
        idx = 0

        async def _factory():
            nonlocal idx
            val = results[idx]
            idx += 1
            return val

        result = await _retry_generate(_factory, "테스트", max_retries=2, base_delay=0.0)
        self.assertEqual(result, "성공")
        self.assertEqual(idx, 3)

    async def test_returns_none_after_all_retries(self):
        """모든 재시도 실패 시 None 반환."""
        from generator import _retry_generate

        async def _factory():
            raise RuntimeError("API 오류")

        result = await _retry_generate(_factory, "실패테스트", max_retries=1, base_delay=0.0)
        self.assertIsNone(result)

    async def test_exception_then_success(self):
        """첫 시도 예외 → 재시도 성공."""
        from generator import _retry_generate

        attempt = 0

        async def _factory():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise ValueError("첫 번째 실패")
            return "재시도 성공"

        result = await _retry_generate(_factory, "테스트", max_retries=1, base_delay=0.0)
        self.assertEqual(result, "재시도 성공")
        self.assertEqual(attempt, 2)


class TestSafetyFlagIntegration(unittest.TestCase):
    """safety_flag 필드가 ScoredTrend에 올바르게 반영되는지 테스트."""

    def test_safety_flag_default_false(self):
        from models import ScoredTrend
        trend = ScoredTrend(keyword="정상", rank=1)
        self.assertFalse(trend.safety_flag)
        self.assertEqual(trend.sentiment, "neutral")

    def test_safety_flag_true(self):
        from models import ScoredTrend
        trend = ScoredTrend(keyword="재난", rank=1, safety_flag=True, sentiment="harmful")
        self.assertTrue(trend.safety_flag)
        self.assertEqual(trend.sentiment, "harmful")


class TestVariantAndLanguageFields(unittest.TestCase):
    """GeneratedTweet의 v3.0 신규 필드 테스트."""

    def test_default_variant_and_language(self):
        from models import GeneratedTweet
        t = GeneratedTweet(tweet_type="공감형", content="내용")
        self.assertEqual(t.variant_id, "")
        self.assertEqual(t.language, "ko")

    def test_custom_variant_and_language(self):
        from models import GeneratedTweet
        t = GeneratedTweet(tweet_type="공감형", content="content", variant_id="B", language="en")
        self.assertEqual(t.variant_id, "B")
        self.assertEqual(t.language, "en")


if __name__ == "__main__":
    unittest.main()
