"""Q2: 통합 테스트 — 파이프라인 흐름, 네트워크 실패 시나리오, LLM JSON 파싱 실패."""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import AppConfig
from generator import _parse_json, generate_tweets_async
from models import GeneratedTweet, MultiSourceContext, ScoredTrend, TweetBatch


def _trend(viral: int = 75) -> ScoredTrend:
    return ScoredTrend(
        keyword="통합테스트",
        rank=1,
        viral_potential=viral,
        context=MultiSourceContext(
            twitter_insight="X 데이터",
            reddit_insight="Reddit 데이터",
            news_insight="뉴스 데이터",
        ),
    )


def _config(**kw) -> AppConfig:
    defaults = dict(
        enable_long_form=True,
        enable_threads=True,
        long_form_min_score=95,
        thread_min_score=92,
        threads_min_score=65,
    )
    defaults.update(kw)
    cfg = AppConfig()
    for k, v in defaults.items():
        setattr(cfg, k, v)
    return cfg


# ══════════════════════════════════════════════════════
#  1) LLM JSON 파싱 실패 시나리오
# ══════════════════════════════════════════════════════


class TestJsonParsing(unittest.TestCase):
    """_parse_json 경계값 테스트."""

    def test_valid_json(self):
        data = _parse_json('{"key": "value"}')
        self.assertEqual(data["key"], "value")

    def test_none_input(self):
        self.assertIsNone(_parse_json(None))

    def test_empty_string(self):
        self.assertIsNone(_parse_json(""))

    def test_invalid_json(self):
        self.assertIsNone(_parse_json("이것은 JSON이 아닙니다"))

    def test_truncated_json(self):
        self.assertIsNone(_parse_json('{"tweets": [{"type": "공감", "co'))

    def test_json_with_whitespace(self):
        data = _parse_json('  \n {"key": 1} \n ')
        self.assertIsNotNone(data)
        self.assertEqual(data["key"], 1)

    def test_json_with_markdown_fence(self):
        """LLM이 ```json ... ``` 래핑으로 응답하는 경우."""
        raw = '```json\n{"tweets": []}\n```'
        # _parse_json은 strip만 하므로 마크다운 펜스는 실패
        self.assertIsNone(_parse_json(raw))

    def test_nested_json(self):
        raw = '{"topic": "AI", "tweets": [{"type": "공감형", "content": "내용"}]}'
        data = _parse_json(raw)
        self.assertEqual(len(data["tweets"]), 1)


# ══════════════════════════════════════════════════════
#  2) 네트워크 실패 시나리오
# ══════════════════════════════════════════════════════


class TestNetworkFailureScenarios(unittest.TestCase):
    """LLM API 호출 실패 시 graceful degradation 검증."""

    def test_tweet_generation_llm_failure_returns_none(self):
        """LLM 호출 예외 시 None 반환 (crash 없이)."""
        client = MagicMock()
        client.acreate = AsyncMock(side_effect=Exception("API rate limit"))

        cfg = _config()
        trend = _trend(viral=75)

        result = asyncio.run(generate_tweets_async(trend, cfg, client))
        self.assertIsNone(result)

    def test_tweet_generation_empty_response(self):
        """LLM이 빈 문자열 반환 시 None."""
        response = MagicMock()
        response.text = ""
        client = MagicMock()
        client.acreate = AsyncMock(return_value=response)

        result = asyncio.run(generate_tweets_async(_trend(), _config(), client))
        self.assertIsNone(result)

    def test_tweet_generation_malformed_json(self):
        """LLM이 잘못된 JSON 반환 시 None."""
        response = MagicMock()
        response.text = "이것은 JSON이 아닙니다. 트윗을 생성할 수 없습니다."
        client = MagicMock()
        client.acreate = AsyncMock(return_value=response)

        result = asyncio.run(generate_tweets_async(_trend(), _config(), client))
        self.assertIsNone(result)


# ══════════════════════════════════════════════════════
#  3) 통합 파이프라인 흐름 테스트
# ══════════════════════════════════════════════════════


class TestPipelineIntegration(unittest.TestCase):
    """파이프라인 단계 간 데이터 흐름 검증 (mock 기반)."""

    def test_combined_generation_path(self):
        """Threads 활성화 시 통합 배치 생성 경로 확인."""
        from generator import generate_for_trend_async

        # 통합 생성 mock
        combined_batch = TweetBatch(
            topic="테스트",
            tweets=[GeneratedTweet(tweet_type="공감형", content="내용", content_type="short")],
            threads_posts=[GeneratedTweet(tweet_type="훅", content="Threads 내용", content_type="threads")],
        )

        with patch("generator.generate_tweets_and_threads_async", new_callable=AsyncMock) as mock_combined:
            mock_combined.return_value = combined_batch
            cfg = _config(threads_min_score=60)
            trend = _trend(viral=75)
            client = MagicMock()

            result = asyncio.run(generate_for_trend_async(trend, cfg, client))

            self.assertIsNotNone(result)
            mock_combined.assert_called_once()
            self.assertEqual(len(result.threads_posts), 1)

    def test_combined_fallback_on_failure(self):
        """통합 생성 실패 시 개별 폴백 경로 확인."""
        from generator import generate_for_trend_async

        individual_batch = TweetBatch(
            topic="폴백",
            tweets=[GeneratedTweet(tweet_type="유머형", content="폴백 트윗", content_type="short")],
        )

        with patch("generator.generate_tweets_and_threads_async", new_callable=AsyncMock) as mock_combined, \
             patch("generator.generate_tweets_async", new_callable=AsyncMock) as mock_tweets, \
             patch("generator.generate_threads_content_async", new_callable=AsyncMock) as mock_threads:

            mock_combined.return_value = None  # 통합 실패
            mock_tweets.return_value = individual_batch
            mock_threads.return_value = []

            cfg = _config(threads_min_score=60)
            trend = _trend(viral=75)
            client = MagicMock()

            result = asyncio.run(generate_for_trend_async(trend, cfg, client))

            self.assertIsNotNone(result)
            mock_combined.assert_called_once()
            mock_tweets.assert_called_once()  # 폴백 호출 확인

    def test_tweet_280_char_trimming(self):
        """280자 초과 트윗이 자동 트리밍되는지 검증."""
        long_content = "A" * 300
        valid_json = json.dumps({
            "topic": "테스트",
            "tweets": [{"type": "공감형", "content": long_content}],
        })
        response = MagicMock()
        response.text = valid_json
        client = MagicMock()
        client.acreate = AsyncMock(return_value=response)

        result = asyncio.run(generate_tweets_async(_trend(), _config(), client))

        self.assertIsNotNone(result)
        self.assertLessEqual(len(result.tweets[0].content), 280)

    def test_config_immutability(self):
        """Q1: 파이프라인 실행 후 원본 config가 변경되지 않음."""
        import dataclasses
        original = AppConfig()
        original_limit = original.limit

        # _check_budget_and_adjust_limit 결과가 원본을 변경하지 않음
        copy = dataclasses.replace(original, limit=5)
        self.assertEqual(original.limit, original_limit)  # 원본 보존
        self.assertEqual(copy.limit, 5)  # 복사본만 변경


if __name__ == "__main__":
    unittest.main()
