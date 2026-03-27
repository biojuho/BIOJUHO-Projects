"""Tests for Reasoning Engine (shared.llm.reasoning)

Verifies all four reasoning modules:
1. SmartRouter — query complexity estimation and strategy selection
2. ChainOfThoughtEngine — multi-sample consensus + early stopping
3. ForestOfThoughtEngine — sub-task decomposition + synthesis
4. SAGEEngine — confidence-based adaptive reasoning depth

Also tests Ollama model detection and Qwen3-Coder routing placement.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure shared package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.llm.config import MODEL_COSTS, MODEL_TO_TIER, REASONING_CONFIG, TIER_CHAINS
from shared.llm.models import LLMResponse, TaskTier

# ---------------------------------------------------------------------------
# Phase 1: Config / Tier Chain Tests
# ---------------------------------------------------------------------------


class TestQwen3CoderRouting:
    """Verify Qwen3-Coder is correctly placed in tier chains."""

    def test_qwen3_in_heavy_chain(self):
        heavy = TIER_CHAINS[TaskTier.HEAVY]
        ollama_models = [(b, m) for b, m in heavy if b == "ollama"]
        assert any("qwen3-coder" in m for _, m in ollama_models), (
            "Qwen3-Coder should be in HEAVY chain"
        )

    def test_qwen3_in_medium_chain(self):
        medium = TIER_CHAINS[TaskTier.MEDIUM]
        ollama_models = [(b, m) for b, m in medium if b == "ollama"]
        assert any("qwen3-coder" in m for _, m in ollama_models), (
            "Qwen3-Coder should be in MEDIUM chain"
        )

    def test_deepseek_r1_in_lightweight_chain(self):
        light = TIER_CHAINS[TaskTier.LIGHTWEIGHT]
        ollama_models = [(b, m) for b, m in light if b == "ollama"]
        assert any("deepseek-r1" in m for _, m in ollama_models), (
            "DeepSeek-R1 should be in LIGHTWEIGHT chain"
        )

    def test_qwen3_cost_zero(self):
        assert MODEL_COSTS.get("qwen3-coder:30b-a3b-q4_K_M") == (0.0, 0.0)

    def test_deepseek_r1_cost_zero(self):
        assert MODEL_COSTS.get("deepseek-r1:14b") == (0.0, 0.0)

    def test_model_to_tier_mapping(self):
        assert MODEL_TO_TIER.get("qwen3-coder:30b-a3b-q4_K_M") == TaskTier.MEDIUM
        assert MODEL_TO_TIER.get("deepseek-r1:14b") == TaskTier.LIGHTWEIGHT

    def test_qwen3_before_openai_in_heavy(self):
        """Qwen3-Coder (free) should appear before OpenAI (paid) in HEAVY."""
        heavy = TIER_CHAINS[TaskTier.HEAVY]
        qwen_idx = next(
            (i for i, (b, m) in enumerate(heavy) if "qwen3-coder" in m),
            None,
        )
        openai_idx = next(
            (i for i, (b, m) in enumerate(heavy) if b == "openai"),
            None,
        )
        assert qwen_idx is not None and openai_idx is not None
        assert qwen_idx < openai_idx, (
            f"Qwen3-Coder (idx={qwen_idx}) should be before OpenAI (idx={openai_idx}) in HEAVY"
        )

    def test_reasoning_config_defaults(self):
        assert REASONING_CONFIG["enabled"] in (True, False)
        assert REASONING_CONFIG["cot_samples"] >= 1
        assert 0.0 <= REASONING_CONFIG["cot_consensus_threshold"] <= 1.0
        assert REASONING_CONFIG["sage_confidence_high"] > REASONING_CONFIG["sage_confidence_low"]


# ---------------------------------------------------------------------------
# Phase 1: Ollama Model Detection Tests
# ---------------------------------------------------------------------------


class TestOllamaModelDetection:
    """Verify Ollama model detection with mocked responses."""

    @patch("shared.llm.backends.urllib.request.urlopen")
    def test_ollama_list_models(self, mock_urlopen):
        import json
        from shared.llm.backends import _ollama_list_models, _ollama_models_cache

        # Reset cache
        import shared.llm.backends as backends_mod
        backends_mod._ollama_models_cache = None
        backends_mod._ollama_cache_ts = 0.0

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "models": [
                {"name": "qwen3-coder:30b-a3b-q4_K_M"},
                {"name": "phi3:3.8b"},
                {"name": "deepseek-r1:14b"},
            ]
        }).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        models = _ollama_list_models()
        assert "qwen3-coder:30b-a3b-q4_K_M" in models
        assert "phi3:3.8b" in models
        assert len(models) == 3

    @patch("shared.llm.backends.urllib.request.urlopen")
    def test_ollama_has_model(self, mock_urlopen):
        import json
        from shared.llm.backends import _ollama_has_model

        import shared.llm.backends as backends_mod
        backends_mod._ollama_models_cache = None
        backends_mod._ollama_cache_ts = 0.0

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "models": [{"name": "qwen3-coder:30b-a3b-q4_K_M"}]
        }).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert _ollama_has_model("qwen3-coder:30b-a3b-q4_K_M") is True
        assert _ollama_has_model("nonexistent:latest") is False

    @patch("shared.llm.backends.urllib.request.urlopen")
    def test_ollama_server_offline(self, mock_urlopen):
        import shared.llm.backends as backends_mod
        backends_mod._ollama_models_cache = None
        backends_mod._ollama_cache_ts = 0.0

        mock_urlopen.side_effect = ConnectionError("Connection refused")

        from shared.llm.backends import _ollama_list_models
        models = _ollama_list_models()
        assert models == []


# ---------------------------------------------------------------------------
# Phase 2: Smart Router Tests
# ---------------------------------------------------------------------------


class TestSmartRouter:
    """Verify complexity estimation and strategy selection."""

    def test_low_complexity(self):
        from shared.llm.reasoning.smart_router import estimate_complexity, QueryComplexity
        result = estimate_complexity("hello world")
        assert result == QueryComplexity.LOW

    def test_medium_complexity(self):
        from shared.llm.reasoning.smart_router import estimate_complexity, QueryComplexity
        result = estimate_complexity("REST API 엔드포인트를 추가하고, 클래스 구현을 생성해주세요")
        assert result in (QueryComplexity.MEDIUM, QueryComplexity.HIGH)

    def test_high_complexity(self):
        from shared.llm.reasoning.smart_router import estimate_complexity, QueryComplexity
        long_query = """
        이 코드에 복잡한 버그가 있습니다. 디버깅을 해주세요.
        성능 최적화도 필요합니다. 알고리즘을 분석해주세요.
        1. 첫 번째 문제
        2. 두 번째 문제
        3. 세 번째 문제
        """
        result = estimate_complexity(long_query)
        assert result in (QueryComplexity.HIGH, QueryComplexity.CRITICAL)

    def test_critical_complexity(self):
        from shared.llm.reasoning.smart_router import estimate_complexity, QueryComplexity
        query = """
        전체 시스템 아키텍처 리팩토링이 필요합니다.
        마이크로서비스로 마이그레이션하는 설계를 해주세요.
        분산 시스템의 각 컴포넌트를 설계하고 코드를 생성해주세요.
        1. 인증 서비스 재설계
        2. API 게이트웨이 구현
        3. 이벤트 버스 설계
        4. 데이터베이스 마이그레이션 계획
        5. 모니터링 시스템 구축
        6. CI/CD 파이프라인 재구성
        ```python
        # 기존 코드
        class MonolithApp:
            pass
        ```
        """
        result = estimate_complexity(query)
        assert result == QueryComplexity.CRITICAL

    def test_strategy_mapping(self):
        from shared.llm.reasoning.smart_router import SmartRouter, QueryComplexity
        client = MagicMock()
        router = SmartRouter(client)
        assert router._select_strategy(QueryComplexity.LOW) == "direct"
        assert router._select_strategy(QueryComplexity.MEDIUM) == "sage"
        assert router._select_strategy(QueryComplexity.HIGH) == "cot"
        assert router._select_strategy(QueryComplexity.CRITICAL) == "fot"


# ---------------------------------------------------------------------------
# Phase 2: Chain-of-Thought Tests
# ---------------------------------------------------------------------------


class TestChainOfThought:
    """Verify CoT multi-sample consensus and early stopping."""

    def test_consensus_with_similar_responses(self):
        from shared.llm.reasoning.chain_of_thought import ChainOfThoughtEngine

        client = MagicMock()
        client.create.side_effect = [
            LLMResponse(text="answer A is correct", model="m", backend="b",
                       tier=TaskTier.MEDIUM, cost_usd=0.0, latency_ms=10),
            LLMResponse(text="answer A is correct", model="m", backend="b",
                       tier=TaskTier.MEDIUM, cost_usd=0.0, latency_ms=10),
        ]

        engine = ChainOfThoughtEngine(client)
        result = engine.run(
            messages=[{"role": "user", "content": "test"}],
            n_samples=3,
            consensus_threshold=0.7,
        )

        assert result.early_stopped is True
        assert result.samples_used == 2
        assert result.text == "answer A is correct"
        assert result.confidence >= 0.7

    def test_no_early_stop_with_divergent_responses(self):
        from shared.llm.reasoning.chain_of_thought import ChainOfThoughtEngine

        client = MagicMock()
        client.create.side_effect = [
            LLMResponse(text="completely different response one about cats",
                       model="m", backend="b", tier=TaskTier.MEDIUM,
                       cost_usd=0.01, latency_ms=10),
            LLMResponse(text="XYZ another unrelated response about dogs here",
                       model="m", backend="b", tier=TaskTier.MEDIUM,
                       cost_usd=0.01, latency_ms=10),
            LLMResponse(text="third response about neither cats nor dogs",
                       model="m", backend="b", tier=TaskTier.MEDIUM,
                       cost_usd=0.01, latency_ms=10),
        ]

        engine = ChainOfThoughtEngine(client)
        result = engine.run(
            messages=[{"role": "user", "content": "test"}],
            n_samples=3,
        )

        assert result.samples_used == 3
        assert result.early_stopped is False
        assert result.total_cost_usd == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# Phase 2: SAGE Tests
# ---------------------------------------------------------------------------


class TestSAGE:
    """Verify SAGE confidence estimation and adaptive depth."""

    def test_heuristic_confidence_high(self):
        from shared.llm.reasoning.sage import _heuristic_confidence

        # Well-structured response with code block
        good_response = """
        Here is the solution:

        1. First step
        2. Second step
        3. Third step
        4. Fourth step

        ```python
        def solve():
            return 42
        ```

        ```python
        def test():
            assert solve() == 42
        ```

        This approach handles all edge cases correctly.
        """
        conf = _heuristic_confidence(good_response)
        assert conf >= 0.6, f"Expected high confidence, got {conf}"

    def test_heuristic_confidence_low(self):
        from shared.llm.reasoning.sage import _heuristic_confidence

        bad_response = "아마도 이렇게 하면 될 수도 있습니다. 확실하지 않습니다. TODO"
        conf = _heuristic_confidence(bad_response)
        assert conf < 0.6, f"Expected low confidence, got {conf}"

    def test_sage_high_confidence_returns_directly(self):
        from shared.llm.reasoning.sage import SAGEEngine

        client = MagicMock()
        # Return a high-quality structured response
        client.create.return_value = LLMResponse(
            text="""
            1. First step
            2. Second step
            3. Third step
            4. Fourth step

            ```python
            def solution():
                return True
            ```

            ```python
            def test():
                assert solution()
            ```

            This is a complete and tested solution.
            """,
            model="m", backend="b", tier=TaskTier.MEDIUM,
            cost_usd=0.01, latency_ms=50,
        )

        engine = SAGEEngine(client)
        result = engine.run(
            messages=[{"role": "user", "content": "test"}],
            confidence_high=0.5,  # Lower threshold to ensure it passes
        )

        assert result.was_enhanced is False
        assert result.stages_applied == 1

    def test_confidence_score_parsing(self):
        from shared.llm.reasoning.sage import _parse_confidence_score

        assert _parse_confidence_score("SCORE: 85\nREASON: good") == 0.85
        assert _parse_confidence_score("SCORE: 100\nREASON: perfect") == 1.0
        assert _parse_confidence_score("SCORE: 0\nREASON: bad") == 0.0
        assert _parse_confidence_score("some random text") == 0.6  # default


# ---------------------------------------------------------------------------
# Phase 2: Forest-of-Thought Tests
# ---------------------------------------------------------------------------


class TestForestOfThought:
    """Verify FoT sub-task decomposition and synthesis."""

    def test_parse_subtasks(self):
        from shared.llm.reasoning.forest_of_thought import _parse_subtasks

        text = """1. 인증 서비스 구현
2. 데이터베이스 설계
3. API 엔드포인트 작성"""

        subtasks = _parse_subtasks(text)
        assert len(subtasks) == 3
        assert "인증 서비스 구현" in subtasks[0]

    def test_parse_subtasks_with_dash(self):
        from shared.llm.reasoning.forest_of_thought import _parse_subtasks

        text = """- First task
- Second task
- Third task"""

        subtasks = _parse_subtasks(text)
        assert len(subtasks) == 3

    def test_fot_fallback_on_empty_decomposition(self):
        from shared.llm.reasoning.forest_of_thought import ForestOfThoughtEngine

        client = MagicMock()
        # First call (decompose) returns empty/unparseable text
        # Second call (direct fallback) returns the actual response
        client.create.side_effect = [
            LLMResponse(text="I can't decompose this.",
                       model="m", backend="b", tier=TaskTier.MEDIUM,
                       cost_usd=0.01, latency_ms=10),
            LLMResponse(text="Direct solution here.",
                       model="m", backend="b", tier=TaskTier.MEDIUM,
                       cost_usd=0.02, latency_ms=20),
        ]

        engine = ForestOfThoughtEngine(client)
        result = engine.run(
            messages=[{"role": "user", "content": "test"}],
        )

        assert result.text == "Direct solution here."
        assert result.subtask_count == 0


# ---------------------------------------------------------------------------
# Phase 3: Integration Tests
# ---------------------------------------------------------------------------


class TestClientReasoningIntegration:
    """Verify create_with_reasoning() integration in LLMClient."""

    def test_import_reasoning_modules(self):
        """Verify all reasoning modules import cleanly."""
        from shared.llm.reasoning import (
            ChainOfThoughtEngine,
            CoTResult,
            ForestOfThoughtEngine,
            FoTResult,
            QueryComplexity,
            ReasoningResult,
            SAGEEngine,
            SAGEResult,
            SmartRouter,
        )
        # If we get here, imports work
        assert SmartRouter is not None
        assert QueryComplexity.LOW is not None

    def test_top_level_reasoning_exports(self):
        """Verify SmartRouter is exported from shared.llm.__init__."""
        from shared.llm import SmartRouter, QueryComplexity
        assert SmartRouter is not None
        assert QueryComplexity is not None

    def test_model_patches_qwen3(self):
        """Verify Qwen3-Coder patch increases max_tokens limit."""
        from shared.llm.model_patches import apply_model_patch

        kwargs = {"max_tokens": 10000}
        patched = apply_model_patch("ollama", "qwen3-coder:30b-a3b-q4_K_M", kwargs)
        assert patched["max_tokens"] == 8192  # Clamped to 8192

    def test_model_patches_deepseek_r1(self):
        """Verify DeepSeek-R1 patch clamps appropriately."""
        from shared.llm.model_patches import apply_model_patch

        kwargs = {"max_tokens": 6000}
        patched = apply_model_patch("ollama", "deepseek-r1:14b", kwargs)
        assert patched["max_tokens"] == 4096

    def test_model_patches_small_model(self):
        """Verify small model patch stays conservative."""
        from shared.llm.model_patches import apply_model_patch

        kwargs = {"max_tokens": 5000}
        patched = apply_model_patch("ollama", "phi3:3.8b", kwargs)
        assert patched["max_tokens"] == 2048

    def test_model_info_qwen_family(self):
        """Verify Qwen models detected as 'qwen' family."""
        from shared.llm.model_patches import get_model_info

        info = get_model_info("ollama", "qwen3-coder:30b-a3b-q4_K_M")
        assert info["family"] == "qwen"
