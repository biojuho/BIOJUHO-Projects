"""Tests for shared.llm.context_condenser — Context compression module."""

from unittest.mock import MagicMock

import pytest

from shared.llm.context_condenser import ContextCondenser, CondensationResult
from shared.llm.models import LLMResponse, TaskTier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Mock LLMClient that returns predictable summaries."""
    client = MagicMock()
    client.create.return_value = LLMResponse(
        text="[요약] 사용자가 DailyNews 파이프라인 오류를 수정 중. 카테고리 3개 처리 완료.",
        model="gemini-2.5-flash-lite",
        backend="gemini",
        tier=TaskTier.LIGHTWEIGHT,
        cost_usd=0.0001,
    )
    return client


@pytest.fixture
def long_history():
    """Create a realistic long conversation history."""
    messages = [
        {"role": "user", "content": "DailyNews 파이프라인에서 Tech 카테고리 처리가 실패합니다."},
        {"role": "assistant", "content": "Tech 카테고리 로그를 확인하겠습니다. RSS 수집기에서 오류가 발생한 것 같습니다."},
        {"role": "user", "content": "네, RSS 수집 후 분석 단계에서 멈춥니다."},
        {"role": "assistant", "content": "분석 단계의 타임아웃 설정이 30초로 너무 짧습니다. 60초로 변경하겠습니다."},
        {"role": "user", "content": "타임아웃 수정 후에도 AI_Deep 카테고리에서 같은 오류가 발생합니다."},
        {"role": "assistant", "content": "AI_Deep 카테고리는 컨텍스트가 길어서 토큰 초과 문제입니다. max_tokens를 조정하겠습니다."},
        {"role": "user", "content": "좋습니다. 이제 Economy_KR도 확인해주세요."},
        {"role": "assistant", "content": "Economy_KR 카테고리를 처리 중입니다. 정상적으로 완료되었습니다."},
        {"role": "user", "content": "전체 파이프라인을 재실행해주세요."},
        {"role": "assistant", "content": "전체 6개 카테고리 파이프라인을 재실행합니다."},
    ]
    return messages


# ---------------------------------------------------------------------------
# Conversation condensation tests
# ---------------------------------------------------------------------------

class TestConversationCondensation:
    def test_skip_short_history(self, mock_client):
        condenser = ContextCondenser(mock_client)
        short = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = condenser.condense(short, keep_recent=3)

        assert result.original_count == 2
        assert result.condensed_count == 2
        assert result.messages == short
        # Should not have called the LLM
        mock_client.create.assert_not_called()

    def test_condense_long_history(self, mock_client, long_history):
        condenser = ContextCondenser(mock_client)
        result = condenser.condense(long_history, keep_recent=3)

        assert result.original_count == 10
        # Should be: 1 summary + 3 recent = 4
        assert result.condensed_count == 4
        assert result.compression_ratio < 1.0
        assert result.tokens_saved_estimate > 0
        assert result.summary_text != ""

        # The last 3 messages should be preserved verbatim
        assert result.messages[-3:] == long_history[-3:]

        # First message should be the summary
        assert result.messages[0]["role"] == "system"
        assert "[이전 대화 요약]" in result.messages[0]["content"]

        # LLM should have been called exactly once
        mock_client.create.assert_called_once()

    def test_condense_uses_lightweight_tier(self, mock_client, long_history):
        condenser = ContextCondenser(mock_client)
        condenser.condense(long_history, keep_recent=3)

        call_kwargs = mock_client.create.call_args
        assert call_kwargs.kwargs.get("tier") == TaskTier.LIGHTWEIGHT

    def test_condense_fallback_on_error(self, long_history):
        client = MagicMock()
        client.create.side_effect = RuntimeError("All backends failed")

        condenser = ContextCondenser(client)
        result = condenser.condense(long_history, keep_recent=3)

        # Should fall back to just keeping recent messages
        assert result.condensed_count == 3
        assert result.messages == long_history[-3:]

    def test_metrics_tracking(self, mock_client, long_history):
        condenser = ContextCondenser(mock_client)
        condenser.condense(long_history, keep_recent=3)
        condenser.condense(long_history, keep_recent=2)

        metrics = condenser.metrics
        assert metrics["total_condensations"] == 2
        assert metrics["total_tokens_saved"] > 0
        assert metrics["total_cost_usd"] > 0


# ---------------------------------------------------------------------------
# Pipeline condensation tests
# ---------------------------------------------------------------------------

class TestPipelineCondensation:
    def test_condense_pipeline_context(self, mock_client):
        condenser = ContextCondenser(mock_client)
        results = [
            {"category": "Tech", "result": "AI 반도체 관련 3개 뉴스 처리 완료"},
            {"category": "AI_Deep", "result": "GPT-5 출시 관련 분석 2건 생성"},
            {"category": "Economy_KR", "result": "한국 금리 동결 뉴스 1건"},
        ]
        summary = condenser.condense_pipeline_context(
            results, pipeline_goal="DailyNews 6카테고리 분석"
        )
        assert isinstance(summary, str)
        assert len(summary) > 0
        mock_client.create.assert_called_once()

    def test_empty_pipeline_results(self, mock_client):
        condenser = ContextCondenser(mock_client)
        summary = condenser.condense_pipeline_context([])
        assert summary == ""
        mock_client.create.assert_not_called()

    def test_pipeline_fallback_on_error(self):
        client = MagicMock()
        client.create.side_effect = RuntimeError("fail")

        condenser = ContextCondenser(client)
        results = [
            {"category": "Tech", "result": "Some result"},
        ]
        summary = condenser.condense_pipeline_context(results)
        # Should still return something (truncated fallback)
        assert "Tech" in summary


# ---------------------------------------------------------------------------
# CondensationResult tests
# ---------------------------------------------------------------------------

class TestCondensationResult:
    def test_compression_ratio(self):
        result = CondensationResult(
            messages=[], original_count=10, condensed_count=4
        )
        assert result.compression_ratio == 0.4

    def test_compression_ratio_zero(self):
        result = CondensationResult(
            messages=[], original_count=0, condensed_count=0
        )
        assert result.compression_ratio == 1.0
