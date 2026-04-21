"""shared.llm module tests - fallback chain, bridge logic, cost tracking."""

import asyncio
from unittest.mock import patch

import pytest

from shared.llm import BridgeMeta, LLMClient, LLMPolicy, TaskTier, reset_client
from shared.llm.config import MODEL_TO_TIER, TIER_CHAINS, get_routing_chain, load_keys
from shared.llm.models import CostRecord, LLMResponse
from shared.llm.stats import CostTracker


class TestConfig:
    def test_load_keys_returns_all_providers(self):
        keys = load_keys()
        assert {"anthropic", "gemini", "openai", "grok", "deepseek", "moonshot"} <= set(keys)

    def test_tier_chains_exist_for_all_tiers(self):
        for tier in TaskTier:
            assert tier in TIER_CHAINS
            assert TIER_CHAINS[tier]

    def test_lightweight_chain_starts_with_gemini(self):
        first_backend, _ = TIER_CHAINS[TaskTier.LIGHTWEIGHT][0]
        assert first_backend == "gemini"

    def test_structured_tasks_prioritize_gemini(self):
        """DeepSeek removed from chain (2026-03-22), Gemini is now primary."""
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="classification", enforce_korean_output=True),
        )
        assert chain[0][0] == "gemini"
        assert chain[0][1] == "gemini-2.5-flash-lite"

    def test_json_extraction_prioritizes_anthropic(self):
        chain = get_routing_chain(
            TaskTier.LIGHTWEIGHT,
            LLMPolicy(task_kind="json_extraction", response_mode="json", enforce_korean_output=True),
        )
        assert chain[0][0] == "anthropic"
        assert chain[0][1] == "claude-haiku-4-5-20251001"

    def test_json_extraction_text_mode_still_prioritizes_anthropic(self):
        chain = get_routing_chain(
            TaskTier.LIGHTWEIGHT,
            LLMPolicy(task_kind="json_extraction", response_mode="text", enforce_korean_output=True),
        )
        assert chain[0][0] == "anthropic"
        assert chain[0][1] == "claude-haiku-4-5-20251001"

    def test_longform_chain_excludes_deepseek(self, monkeypatch):
        """DeepSeek completely removed from routing chain (2026-03-22)."""
        monkeypatch.delenv("ENABLE_DEEPSEEK_KO_LONGFORM", raising=False)
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="summary", enforce_korean_output=True),
        )
        # DeepSeek should not be in chain regardless of flags
        assert all(backend != "deepseek" for backend, _ in chain)
        # Gemini should be primary
        assert chain[0][0] == "gemini"

    def test_longform_chain_still_excludes_deepseek_even_with_flag(self, monkeypatch):
        """Even with flag enabled, DeepSeek is completely removed (2026-03-22)."""
        monkeypatch.setenv("ENABLE_DEEPSEEK_KO_LONGFORM", "true")
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="summary", enforce_korean_output=True),
        )
        # DeepSeek no longer exists in any chain
        assert all(backend != "deepseek" for backend, _ in chain)

    def test_model_to_tier_mapping(self):
        assert MODEL_TO_TIER["claude-3-haiku-20240307"] == TaskTier.LIGHTWEIGHT
        assert MODEL_TO_TIER["claude-sonnet-4-20250514"] == TaskTier.HEAVY
        assert MODEL_TO_TIER["claude-3-5-haiku-20241022"] == TaskTier.MEDIUM


class TestCostTracker:
    def test_record_and_get_stats(self):
        tracker = CostTracker()
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY, 1000, 500, True)
        tracker.record("gemini", "gemini-2.5-flash-lite", TaskTier.LIGHTWEIGHT, 500, 200, True)
        tracker.record("deepseek", "deepseek-chat", TaskTier.LIGHTWEIGHT, 1000, 1000, False, "quota exceeded")

        stats = tracker.get_stats()
        assert stats.total_calls == 3
        assert stats.total_errors == 1
        assert stats.success_rate == 66.7
        assert stats.total_cost_usd > 0

    def test_reset(self):
        tracker = CostTracker()
        tracker.record("gemini", "gemini-2.5-flash-lite", TaskTier.MEDIUM, 100, 100, True)
        tracker.reset()
        stats = tracker.get_stats()
        assert stats.total_calls == 0


class TestLLMClient:
    _DUMMY_KEYS = {"deepseek": "test-key", "gemini": "test-key", "openai": "test-key"}

    def setup_method(self):
        reset_client()
        LLMClient.reset()

    def test_no_keys_raises_value_error(self, monkeypatch):
        for var in (
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "MOONSHOT_API_KEY",
            "XIAOMI_MIMO_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        # Also disable local backends (Ollama server + BitNet binary)
        monkeypatch.setattr("shared.llm.backends._ollama_is_running", lambda: False)
        monkeypatch.setattr("shared.llm.backends.bitnet_runner.is_available", lambda: False)
        with pytest.raises(ValueError, match="No LLM API keys configured"):
            LLMClient()

    def test_resolve_tier_from_explicit(self):
        client = LLMClient(**self._DUMMY_KEYS)
        assert client._resolve_tier(TaskTier.HEAVY, None) == TaskTier.HEAVY

    def test_resolve_tier_from_model_name(self):
        client = LLMClient(**self._DUMMY_KEYS)
        assert client._resolve_tier(None, "claude-3-haiku-20240307") == TaskTier.LIGHTWEIGHT

    def test_resolve_tier_defaults_to_medium(self):
        client = LLMClient(**self._DUMMY_KEYS)
        assert client._resolve_tier(None, "unknown-model") == TaskTier.MEDIUM

    @patch("shared.llm.backends.BackendManager.call")
    def test_create_attaches_policy_and_meta(self, mock_call):
        mock_call.return_value = LLMResponse(
            text="한국어 정상 응답입니다",
            model="deepseek-chat",
            backend="deepseek",
            tier=TaskTier.LIGHTWEIGHT,
        )
        client = LLMClient(**self._DUMMY_KEYS)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "CRISPR 논문을 요약해줘"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )
        assert resp.backend == "deepseek"
        assert resp.policy.task_kind == "classification"
        assert resp.bridge_meta.bridge_applied is True
        assert resp.bridge_meta.detected_output_language in {"ko", "mixed"}

    @patch("shared.llm.backends.BackendManager.call")
    def test_fallback_on_quota_error(self, mock_call):
        mock_call.side_effect = [
            Exception("credit balance is too low"),
            LLMResponse(text="정상 응답", model="gemini-2.5-flash-lite", backend="gemini", tier=TaskTier.LIGHTWEIGHT),
        ]
        client = LLMClient(**self._DUMMY_KEYS)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "test"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )
        assert resp.backend == "gemini"
        assert mock_call.call_count == 2

    @patch("shared.llm.backends.BackendManager.call")
    def test_first_successful_response_returned(self, mock_call):
        """First successful response is returned (quality gate disabled after DeepSeek removal)."""
        mock_call.return_value = LLMResponse(
            text="한국어 정확하게 정리된 응답입니다",
            model="gemini-2.5-flash-lite",
            backend="gemini",
            tier=TaskTier.LIGHTWEIGHT,
        )
        client = LLMClient(**self._DUMMY_KEYS)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "이 주제를 분석해줘"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )
        assert resp.text == "한국어 정확하게 정리된 응답입니다"
        assert resp.backend == "gemini"
        assert mock_call.call_count == 1

    @patch("shared.llm.backends.BackendManager.call")
    def test_non_fallback_error_raises(self, mock_call):
        mock_call.side_effect = ValueError("unexpected error")
        client = LLMClient(**self._DUMMY_KEYS)
        with pytest.raises(ValueError, match="unexpected error"):
            client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": "test"}],
                policy=LLMPolicy(task_kind="classification", output_language="ko"),
            )

    @pytest.mark.asyncio
    async def test_async_timeout_falls_back_to_next_backend(self):
        async def fake_acall(*args, **kwargs):
            fake_acall.calls += 1
            if fake_acall.calls == 1:
                await asyncio.sleep(0.05)
            return LLMResponse(
                text="fallback response",
                model="claude-haiku-4-5-20251001",
                backend="anthropic",
                tier=TaskTier.LIGHTWEIGHT,
            )

        fake_acall.calls = 0
        client = LLMClient(**self._DUMMY_KEYS)

        with (
            patch("shared.llm.client._ASYNC_BACKEND_TIMEOUT_SECONDS", 0.01),
            patch("shared.llm.backends.BackendManager.acall", side_effect=fake_acall),
        ):
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": "test"}],
                policy=LLMPolicy(task_kind="classification", output_language="ko"),
            )

        assert response.backend == "anthropic"
        assert fake_acall.calls == 2

    @patch("shared.llm.backends.BackendManager.call")
    def test_stats_include_bridge_metrics(self, mock_call):
        """Stats tracking with Gemini-only chain (DeepSeek removed 2026-03-22)."""
        mock_call.side_effect = [
            # First call: normal response
            LLMResponse(
                text="한국어 정상 응답입니다",
                model="gemini-2.5-flash-lite",
                backend="gemini",
                tier=TaskTier.LIGHTWEIGHT,
                input_tokens=100,
                output_tokens=50,
            ),
            # Second call: normal response
            LLMResponse(
                text="두번째 정상 응답입니다",
                model="gemini-2.5-flash-lite",
                backend="gemini",
                tier=TaskTier.LIGHTWEIGHT,
                input_tokens=100,
                output_tokens=50,
            ),
        ]
        client = LLMClient(**self._DUMMY_KEYS)
        client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "첫번째 질문"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )
        client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "두번째 질문"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )

        stats = client.get_stats()
        assert stats["total_calls"] == 2  # 2 normal calls
        assert "ko_output_pass_rate" in stats
        assert "bridge_fallback_rate" in stats
        assert "per_task_latency_ms" in stats


class TestModels:
    def test_llm_response_defaults(self):
        resp = LLMResponse(text="hello", model="gpt-4o", backend="openai")
        assert resp.text == "hello"
        assert resp.tier == TaskTier.MEDIUM
        assert isinstance(resp.bridge_meta, BridgeMeta)

    def test_cost_record_fields(self):
        rec = CostRecord(backend="anthropic", model="claude-sonnet-4-20250514")
        assert rec.success is True
        assert rec.cost_usd == 0.0
