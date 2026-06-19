"""Request-shape regression: per-tier reasoning effort + Gemini native system_instruction.

These pin the request SHAPE and SDK acceptance. The behavior shift — Gemini output changes
once system moves from the in-band '[System]' fold to native system_instruction, and reasoning
depth varies by tier — must still be confirmed against LIVE Gemini/OpenAI before production.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from shared.llm.backends import (
    BackendManager,
    _chat_completion_kwargs,
    _gemini_config,
    _gemini_prompt,
    _gemini_thinking_level,
    _openai_reasoning_effort,
)
from shared.llm.models import TaskTier

MESSAGES = [{"role": "user", "content": "hi"}]


class TestOpenAIReasoningEffort:
    def test_heavy_gpt5_non_mini_gets_high(self) -> None:
        assert _openai_reasoning_effort(TaskTier.HEAVY, "gpt-5.5") == "high"

    def test_mini_stays_default(self) -> None:
        # gpt-5.x-mini defaults to none / caps at high — raising it only adds cost.
        assert _openai_reasoning_effort(TaskTier.HEAVY, "gpt-5.4-mini") is None

    def test_medium_gpt5_no_effort(self) -> None:
        assert _openai_reasoning_effort(TaskTier.MEDIUM, "gpt-5.5") is None

    def test_non_reasoning_model_none(self) -> None:
        assert _openai_reasoning_effort(TaskTier.HEAVY, "gpt-4o") is None
        assert _openai_reasoning_effort(TaskTier.HEAVY, "openai/gpt-4o") is None

    def test_chat_kwargs_threads_effort(self) -> None:
        kw = _chat_completion_kwargs("gpt-5.5", MESSAGES, 100, "text", TaskTier.HEAVY)
        assert kw["reasoning_effort"] == "high"
        kw_mini = _chat_completion_kwargs("gpt-5.4-mini", MESSAGES, 100, "text", TaskTier.MEDIUM)
        assert "reasoning_effort" not in kw_mini


class TestGeminiThinkingLevel:
    def test_3x_tier_map(self) -> None:
        assert _gemini_thinking_level(TaskTier.HEAVY, "gemini-3.1-pro-preview") == "high"
        assert _gemini_thinking_level(TaskTier.MEDIUM, "gemini-3.5-flash") == "low"
        assert _gemini_thinking_level(TaskTier.LIGHTWEIGHT, "gemini-3.1-flash-lite") == "minimal"

    def test_25_returns_none(self) -> None:
        # 2.5 uses thinking_budget; mixing with thinking_level 400s.
        assert _gemini_thinking_level(TaskTier.HEAVY, "gemini-2.5-pro") is None


class TestGeminiConfigAndPrompt:
    def test_prompt_has_no_system_marker(self) -> None:
        out = _gemini_prompt([{"role": "user", "content": "body"}])
        assert "[System]" not in out
        assert out == "body"

    def test_config_sets_system_instruction_and_thinking(self) -> None:
        cfg = _gemini_config(100, "text", tier=TaskTier.HEAVY, model="gemini-3.1-pro-preview", system="be terse")
        assert cfg["system_instruction"] == "be terse"
        assert cfg["thinking_config"] == {"thinking_level": "high"}

    def test_config_25_omits_thinking(self) -> None:
        cfg = _gemini_config(100, "text", tier=TaskTier.HEAVY, model="gemini-2.5-pro", system="")
        assert "thinking_config" not in cfg

    def test_gemini_config_accepted_by_sdk(self) -> None:
        # SDK-acceptance: the dict shape must construct a real GenerateContentConfig,
        # catching a coercion/unknown-field problem here rather than at runtime.
        types = pytest.importorskip("google.genai.types")
        cfg = _gemini_config(100, "json", tier=TaskTier.HEAVY, model="gemini-3.1-pro-preview", system="sys")
        obj = types.GenerateContentConfig(**cfg)
        assert obj.system_instruction is not None
        assert obj.thinking_config is not None


class TestCallGeminiRequestShape:
    def test_call_gemini_uses_native_system_instruction(self) -> None:
        mgr = BackendManager(keys={"gemini": "g-test"})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = SimpleNamespace(text="ok")
        mgr._clients["gemini"] = mock_client

        mgr._call_gemini("gemini-3.1-pro-preview", MESSAGES, 100, "be terse", TaskTier.HEAVY)

        ckw = mock_client.models.generate_content.call_args.kwargs
        assert "[System]" not in ckw["contents"]
        assert ckw["config"]["system_instruction"] == "be terse"
        assert ckw["config"]["thinking_config"] == {"thinking_level": "high"}
