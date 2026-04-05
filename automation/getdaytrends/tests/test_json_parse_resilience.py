"""JSON 파싱 실패 로깅 + generate_tweets_async 재시도 방어 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import AppConfig
from models import MultiSourceContext, ScoredTrend, TrendContext


def _make_trend() -> ScoredTrend:
    return ScoredTrend(
        keyword="테스트 트렌드",
        rank=1,
        viral_potential=75,
        trend_acceleration="+5%",
        top_insight="핵심 인사이트",
        suggested_angles=["앵글1"],
        best_hook_starter="훅",
        context=MultiSourceContext(
            twitter_insight="X 인사이트",
            reddit_insight="Reddit 인사이트",
            news_insight="뉴스 인사이트",
        ),
        trend_context=TrendContext(
            trigger_event="이벤트",
            why_now="이유",
        ),
    )


class TestParseJsonLogging:
    """_parse_json이 실패 시 경고 로그를 남기는지 검증."""

    def test_malformed_json_returns_none_and_logs(self):
        from analysis.parsing import _parse_json

        result = _parse_json("{broken json")
        assert result is None

    def test_valid_json_parses_correctly(self):
        from analysis.parsing import _parse_json

        result = _parse_json('{"tweets": []}')
        assert result == {"tweets": []}

    def test_empty_input_returns_none(self):
        from analysis.parsing import _parse_json

        assert _parse_json(None) is None
        assert _parse_json("") is None


class TestGenerateTweetsRetry:
    """generate_tweets_async: 첫 LLM 응답 JSON 파싱 실패 시 1회 재시도."""

    @pytest.mark.asyncio
    async def test_retry_on_first_json_failure(self):
        """첫 LLM 호출이 깨진 JSON → 재시도에서 정상 JSON → 배치 반환."""
        from generator import generate_tweets_async

        trend = _make_trend()
        cfg = AppConfig()

        broken_response = MagicMock()
        broken_response.text = "{broken"

        good_response = MagicMock()
        good_response.text = '{"tweets": [{"type": "insight", "content": "테스트 트윗"}]}'

        mock_client = MagicMock()
        mock_client.acreate = AsyncMock(side_effect=[broken_response, good_response])

        with patch("generator._INST_OK", False):
            result = await generate_tweets_async(trend, cfg, mock_client)

        assert result is not None
        assert len(result.tweets) == 1
        assert mock_client.acreate.call_count == 2  # 원본 + 재시도

    @pytest.mark.asyncio
    async def test_both_attempts_fail_returns_none(self):
        """첫 호출도 재시도도 깨진 JSON → None 반환 (크래시 아님)."""
        from generator import generate_tweets_async

        trend = _make_trend()
        cfg = AppConfig()

        broken_response = MagicMock()
        broken_response.text = "not json at all"

        mock_client = MagicMock()
        mock_client.acreate = AsyncMock(return_value=broken_response)

        with patch("generator._INST_OK", False):
            result = await generate_tweets_async(trend, cfg, mock_client)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_retry_when_first_parse_succeeds(self):
        """첫 파싱 성공 시 재시도하지 않는다."""
        from generator import generate_tweets_async

        trend = _make_trend()
        cfg = AppConfig()

        good_response = MagicMock()
        good_response.text = '{"tweets": [{"type": "hot_take", "content": "정상 트윗"}]}'

        mock_client = MagicMock()
        mock_client.acreate = AsyncMock(return_value=good_response)

        with patch("generator._INST_OK", False):
            result = await generate_tweets_async(trend, cfg, mock_client)

        assert result is not None
        assert mock_client.acreate.call_count == 1  # 재시도 없음
