"""shared.llm 모듈 단위 테스트 - 키 로딩, 티어 라우팅, 폴백 로직, 비용 추적."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.llm import LLMClient, TaskTier, reset_client
from shared.llm.config import FALLBACK_ERRORS, MODEL_TO_TIER, TIER_CHAINS, load_keys
from shared.llm.models import CostRecord, LLMResponse
from shared.llm.stats import CostTracker


# ── Config Tests ──────────────────────────────────────


class TestConfig:
    def test_load_keys_returns_all_providers(self):
        keys = load_keys()
        assert "anthropic" in keys
        assert "gemini" in keys
        assert "openai" in keys
        assert "grok" in keys
        assert "deepseek" in keys
        assert "moonshot" in keys

    def test_tier_chains_exist_for_all_tiers(self):
        for tier in TaskTier:
            assert tier in TIER_CHAINS
            assert len(TIER_CHAINS[tier]) > 0

    def test_heavy_tier_excludes_deepseek(self):
        backends = [b for b, _ in TIER_CHAINS[TaskTier.HEAVY]]
        assert "deepseek" not in backends

    def test_medium_tier_excludes_deepseek(self):
        backends = [b for b, _ in TIER_CHAINS[TaskTier.MEDIUM]]
        assert "deepseek" not in backends

    def test_lightweight_tier_starts_with_deepseek(self):
        first_backend, _ = TIER_CHAINS[TaskTier.LIGHTWEIGHT][0]
        assert first_backend == "deepseek"

    def test_model_to_tier_mapping(self):
        assert MODEL_TO_TIER["claude-3-haiku-20240307"] == TaskTier.LIGHTWEIGHT
        assert MODEL_TO_TIER["claude-sonnet-4-20250514"] == TaskTier.HEAVY
        assert MODEL_TO_TIER["claude-3-5-haiku-20241022"] == TaskTier.MEDIUM


# ── Stats Tests ───────────────────────────────────────


class TestCostTracker:
    def test_record_and_get_stats(self):
        tracker = CostTracker()
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY, 1000, 500, True)
        tracker.record("gemini", "gemini-2.0-flash", TaskTier.LIGHTWEIGHT, 500, 200, True)
        tracker.record("deepseek", "deepseek-chat", TaskTier.LIGHTWEIGHT, 1000, 1000, False, "quota exceeded")

        stats = tracker.get_stats()
        assert stats.total_calls == 3
        assert stats.total_errors == 1
        assert stats.success_rate == 66.7
        assert "anthropic" in stats.calls_by_backend
        assert "heavy" in stats.calls_by_tier
        assert stats.total_cost_usd > 0

    def test_reset(self):
        tracker = CostTracker()
        tracker.record("gemini", "gemini-2.0-flash", TaskTier.MEDIUM, 100, 100, True)
        tracker.reset()
        stats = tracker.get_stats()
        assert stats.total_calls == 0


# ── Client Tests (mocked backends) ───────────────────


class TestLLMClient:
    """LLMClient tests — use dummy key to satisfy has_any_key() validation."""

    _DUMMY_KEY = {"gemini": "test-key"}

    def setup_method(self):
        reset_client()
        LLMClient.reset()

    def test_no_keys_raises_value_error(self, monkeypatch):
        for var in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
                     "OPENAI_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValueError, match="No LLM API keys configured"):
            LLMClient()

    def test_resolve_tier_from_explicit(self):
        client = LLMClient(**self._DUMMY_KEY)
        tier = client._resolve_tier(TaskTier.HEAVY, None)
        assert tier == TaskTier.HEAVY

    def test_resolve_tier_from_model_name(self):
        client = LLMClient(**self._DUMMY_KEY)
        tier = client._resolve_tier(None, "claude-3-haiku-20240307")
        assert tier == TaskTier.LIGHTWEIGHT

    def test_resolve_tier_defaults_to_medium(self):
        client = LLMClient(**self._DUMMY_KEY)
        tier = client._resolve_tier(None, "unknown-model")
        assert tier == TaskTier.MEDIUM

    @patch("shared.llm.backends.BackendManager.call")
    def test_create_returns_response(self, mock_call):
        mock_call.return_value = LLMResponse(
            text="Hello", model="deepseek-chat", backend="deepseek", tier=TaskTier.LIGHTWEIGHT
        )
        client = LLMClient(**self._DUMMY_KEY)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "test"}],
        )
        assert resp.text == "Hello"
        assert resp.backend == "deepseek"

    @patch("shared.llm.backends.BackendManager.call")
    def test_fallback_on_quota_error(self, mock_call):
        # First call fails with quota error, second succeeds
        mock_call.side_effect = [
            Exception("credit balance is too low"),
            LLMResponse(text="OK", model="gemini-2.0-flash", backend="gemini", tier=TaskTier.LIGHTWEIGHT),
        ]
        client = LLMClient(**self._DUMMY_KEY)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "test"}],
        )
        assert resp.text == "OK"
        assert resp.backend == "gemini"
        assert mock_call.call_count == 2

    @patch("shared.llm.backends.BackendManager.call")
    def test_non_fallback_error_raises(self, mock_call):
        mock_call.side_effect = ValueError("unexpected error")
        client = LLMClient(**self._DUMMY_KEY)
        with pytest.raises(ValueError, match="unexpected error"):
            client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": "test"}],
            )

    @patch("shared.llm.backends.BackendManager.call")
    def test_get_stats_after_calls(self, mock_call):
        mock_call.return_value = LLMResponse(
            text="OK", model="deepseek-chat", backend="deepseek",
            tier=TaskTier.LIGHTWEIGHT, input_tokens=100, output_tokens=50,
        )
        client = LLMClient(**self._DUMMY_KEY)
        client.create(tier=TaskTier.LIGHTWEIGHT, messages=[{"role": "user", "content": "a"}])
        client.create(tier=TaskTier.LIGHTWEIGHT, messages=[{"role": "user", "content": "b"}])

        stats = client.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_errors"] == 0
        assert stats["success_rate"] == 100.0


# ── Models Tests ──────────────────────────────────────


class TestModels:
    def test_llm_response_fields(self):
        resp = LLMResponse(text="hello", model="gpt-4o", backend="openai")
        assert resp.text == "hello"
        assert resp.tier == TaskTier.MEDIUM  # default

    def test_cost_record_fields(self):
        rec = CostRecord(backend="anthropic", model="claude-sonnet-4-20250514")
        assert rec.success is True
        assert rec.cost_usd == 0.0
