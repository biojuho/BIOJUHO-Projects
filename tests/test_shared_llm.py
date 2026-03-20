# -*- coding: utf-8 -*-
"""shared.llm module tests - fallback chain, bridge logic, cost tracking."""

import sys
from pathlib import Path
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

    def test_structured_tasks_prioritize_deepseek(self):
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="classification", enforce_korean_output=True),
        )
        assert chain[0][0] == "deepseek"

    def test_longform_chain_excludes_deepseek_by_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_DEEPSEEK_KO_LONGFORM", raising=False)
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="summary", enforce_korean_output=True),
        )
        assert all(backend != "deepseek" for backend, _ in chain)

    def test_longform_chain_can_include_deepseek_with_flag(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DEEPSEEK_KO_LONGFORM", "true")
        chain = get_routing_chain(
            TaskTier.MEDIUM,
            LLMPolicy(task_kind="summary", enforce_korean_output=True),
        )
        assert any(backend == "deepseek" for backend, _ in chain)

    def test_model_to_tier_mapping(self):
        assert MODEL_TO_TIER["claude-3-haiku-20240307"] == TaskTier.LIGHTWEIGHT
        assert MODEL_TO_TIER["claude-sonnet-4-20250514"] == TaskTier.HEAVY
        assert MODEL_TO_TIER["claude-3-5-haiku-20241022"] == TaskTier.MEDIUM


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
        assert stats.total_cost_usd > 0

    def test_reset(self):
        tracker = CostTracker()
        tracker.record("gemini", "gemini-2.0-flash", TaskTier.MEDIUM, 100, 100, True)
        tracker.reset()
        stats = tracker.get_stats()
        assert stats.total_calls == 0


class TestLLMClient:
    _DUMMY_KEYS = {"deepseek": "test-key", "gemini": "test-key", "openai": "test-key"}

    def setup_method(self):
        reset_client()
        LLMClient.reset()

    def test_no_keys_raises_value_error(self, monkeypatch):
        for var in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
                    "OPENAI_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY",
                    "XIAOMI_MIMO_API_KEY"):
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
            LLMResponse(text="정상 응답", model="gemini-2.0-flash", backend="gemini", tier=TaskTier.LIGHTWEIGHT),
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
    def test_quality_gate_repairs_deepseek_output(self, mock_call):
        mock_call.side_effect = [
            LLMResponse(text="\u7627\u6ed8\u8a0e\u8bba\u6587\u6863", model="deepseek-chat", backend="deepseek", tier=TaskTier.LIGHTWEIGHT),
            LLMResponse(text="한국어 정확하게 정리된 응답입니다", model="gemini-2.0-flash", backend="gemini", tier=TaskTier.LIGHTWEIGHT),
        ]
        client = LLMClient(**self._DUMMY_KEYS)
        resp = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "이 주제를 분석해줘"}],
            policy=LLMPolicy(task_kind="classification", output_language="ko"),
        )
        assert resp.backend == "gemini"
        assert resp.bridge_meta.fallback_reason == "deepseek_quality_gate_failed"
        assert "contains_excessive_hanzi" in resp.bridge_meta.quality_flags

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

    @patch("shared.llm.backends.BackendManager.call")
    def test_stats_include_bridge_metrics(self, mock_call):
        mock_call.side_effect = [
            LLMResponse(text="한국어 정상 응답입니다", model="deepseek-chat", backend="deepseek", tier=TaskTier.LIGHTWEIGHT, input_tokens=100, output_tokens=50),
            LLMResponse(text="\u7627\u6ed8\u8a0e\u8bba\u6587\u6863", model="deepseek-chat", backend="deepseek", tier=TaskTier.LIGHTWEIGHT, input_tokens=100, output_tokens=50),
            LLMResponse(text="수정된 정상 응답입니다", model="gemini-2.0-flash", backend="gemini", tier=TaskTier.LIGHTWEIGHT, input_tokens=100, output_tokens=50),
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
        assert stats["total_calls"] == 3
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
