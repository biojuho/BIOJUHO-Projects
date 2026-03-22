# -*- coding: utf-8 -*-
"""Tests for GiniGen-inspired LLM enhancements.

Phase 1: Error classification
Phase 2: Model patches
Phase 3: MARL pipeline
Phase 4: Tool schema validation
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from shared.llm.errors import (
    AuthError,
    ContentFilterError,
    ContextLengthError,
    LLMError,
    ModelNotFoundError,
    NetworkError,
    QuotaExhaustedError,
    RateLimitError,
    ServerError,
    classify_error,
    is_retryable,
    should_fallback_to_next_backend,
)
from shared.llm.marl import MARLConfig, MARLPipeline, MARLResult, MARLStageLog
from shared.llm.model_patches import apply_model_patch, get_model_info
from shared.llm.models import LLMPolicy, LLMResponse, TaskTier
from shared.llm.tool_schema import ToolDefinition, ToolRegistry, ToolResult, ToolValidationError


# ===================================================================
# Phase 1: Error Classification
# ===================================================================

class TestErrorClassification:
    """Test structured error classification."""

    def test_classify_network_error(self):
        err = classify_error(Exception("Connection refused by server"))
        assert isinstance(err, NetworkError)
        assert err.retryable is True
        assert err.error_type == "network_error"

    def test_classify_timeout(self):
        err = classify_error(Exception("Request timeout after 30s"))
        assert isinstance(err, NetworkError)
        assert err.retryable is True

    def test_classify_rate_limit(self):
        err = classify_error(Exception("rate_limit_exceeded: retry after 60s"))
        assert isinstance(err, RateLimitError)
        assert err.retryable is True
        assert err.error_type == "rate_limit"

    def test_classify_auth_error(self):
        err = classify_error(Exception("authentication_error: invalid api key"))
        assert isinstance(err, AuthError)
        assert err.retryable is False
        assert err.error_type == "auth_error"

    def test_classify_invalid_api_key(self):
        err = classify_error(Exception("Invalid API key provided"))
        assert isinstance(err, AuthError)
        assert err.retryable is False

    def test_classify_quota_exhausted(self):
        err = classify_error(Exception("credit balance is too low"))
        assert isinstance(err, QuotaExhaustedError)
        assert err.retryable is True  # retryable via different backend
        assert err.error_type == "quota_exhausted"

    def test_classify_insufficient_quota(self):
        err = classify_error(Exception("insufficient_quota"))
        assert isinstance(err, QuotaExhaustedError)

    def test_classify_context_length(self):
        err = classify_error(Exception("context_length exceeded max 128000"))
        assert isinstance(err, ContextLengthError)
        assert err.retryable is False
        assert err.error_type == "context_length"

    def test_classify_content_filter(self):
        err = classify_error(Exception("content_filter: blocked by safety"))
        assert isinstance(err, ContentFilterError)
        assert err.retryable is False
        assert err.error_type == "content_filter"

    def test_classify_model_not_found(self):
        err = classify_error(Exception("model not found: gpt-99"))
        assert isinstance(err, ModelNotFoundError)
        assert err.retryable is True  # retryable via fallback
        assert err.error_type == "model_not_found"

    def test_classify_server_error(self):
        err = classify_error(Exception("Internal server error 502"))
        assert isinstance(err, ServerError)
        assert err.retryable is True

    def test_classify_overloaded(self):
        err = classify_error(Exception("Server overloaded"))
        assert isinstance(err, ServerError)
        assert err.retryable is True

    def test_classify_unknown_error(self):
        err = classify_error(Exception("something completely unknown"))
        assert isinstance(err, LLMError)
        assert err.retryable is False

    def test_classify_already_typed(self):
        original = RateLimitError("already typed")
        result = classify_error(original)
        assert result is original

    def test_classify_preserves_original(self):
        original = ValueError("original error")
        err = classify_error(original)
        assert err.original is original

    def test_is_retryable_shortcut(self):
        assert is_retryable(Exception("rate_limit_exceeded")) is True
        assert is_retryable(Exception("authentication_error")) is False

    def test_should_fallback_to_next_backend(self):
        assert should_fallback_to_next_backend(Exception("credit balance is too low")) is True
        assert should_fallback_to_next_backend(Exception("context_length exceeded")) is False
        assert should_fallback_to_next_backend(Exception("unknown error")) is False

    def test_classify_deepseek_invalid_request(self):
        """DeepSeek Korean prompt errors should be retryable via fallback."""
        err = classify_error(Exception("invalid_request_error"))
        assert err.retryable is True


# ===================================================================
# Phase 2: Model Patches
# ===================================================================

class TestModelPatches:
    """Test model-specific parameter adjustments."""

    def test_patch_claude_temperature_clamping(self):
        kwargs = {"temperature": 1.5, "max_tokens": 1000}
        result = apply_model_patch("anthropic", "claude-sonnet-4-20250514", kwargs)
        assert result["temperature"] == 1.0

    def test_patch_claude_low_temperature_unchanged(self):
        kwargs = {"temperature": 0.5, "max_tokens": 1000}
        result = apply_model_patch("anthropic", "claude-sonnet-4-20250514", kwargs)
        assert result["temperature"] == 0.5

    def test_patch_deepseek_temperature_floor(self):
        kwargs = {"temperature": 0.1, "max_tokens": 1000}
        result = apply_model_patch("deepseek", "deepseek-chat", kwargs)
        assert result["temperature"] == 0.7

    def test_patch_deepseek_high_temp_unchanged(self):
        kwargs = {"temperature": 1.0, "max_tokens": 1000}
        result = apply_model_patch("deepseek", "deepseek-chat", kwargs)
        assert result["temperature"] == 1.0

    def test_patch_gemini_25_token_expansion(self):
        kwargs = {"max_tokens": 1000}
        result = apply_model_patch("gemini", "gemini-2.5-pro-preview-03-25", kwargs)
        assert result["max_tokens"] == 8192  # max(1000*4, 8192)

    def test_patch_gemini_25_lite_token_expansion(self):
        """Gemini 2.5 Flash-Lite also gets token expansion (2.5 family)."""
        kwargs = {"max_tokens": 1000}
        result = apply_model_patch("gemini", "gemini-2.5-flash-lite", kwargs)
        assert result["max_tokens"] == 8192  # Gemini 2.5 family gets expansion

    def test_patch_grok_json_mode(self):
        kwargs = {"response_mode": "json", "max_tokens": 1000}
        result = apply_model_patch("grok", "grok-3", kwargs)
        assert result["extra_params"]["reasoning"] is False

    def test_patch_grok_text_mode_no_change(self):
        kwargs = {"response_mode": "text", "max_tokens": 1000}
        result = apply_model_patch("grok", "grok-3", kwargs)
        assert "extra_params" not in result

    def test_patch_ollama_token_clamping(self):
        kwargs = {"max_tokens": 4096}
        result = apply_model_patch("ollama", "phi3:3.8b", kwargs)
        assert result["max_tokens"] == 2048

    def test_patch_unknown_backend_passthrough(self):
        kwargs = {"max_tokens": 1000, "temperature": 0.5}
        result = apply_model_patch("unknown_backend", "unknown-model", kwargs)
        assert result == kwargs

    def test_get_model_info(self):
        info = get_model_info("anthropic", "claude-sonnet-4-20250514")
        assert info["family"] == "claude"
        assert info["has_patch"] is True

    def test_get_model_info_unknown(self):
        info = get_model_info("custom", "my-model")
        assert info["family"] == "other"
        assert info["has_patch"] is False


# ===================================================================
# Phase 3: MARL Pipeline
# ===================================================================

class TestMARLConfig:
    """Test MARL configuration."""

    def test_default_config(self):
        cfg = MARLConfig()
        assert cfg.stages == 3
        assert cfg.critique_tier == TaskTier.LIGHTWEIGHT
        assert cfg.generation_tier == TaskTier.MEDIUM

    def test_custom_config(self):
        cfg = MARLConfig(stages=5, generation_tier=TaskTier.HEAVY)
        assert cfg.stages == 5
        assert cfg.generation_tier == TaskTier.HEAVY


class TestMARLResult:
    """Test MARL result structure."""

    def test_empty_result(self):
        result = MARLResult(final_text="hello", stages_completed=1)
        assert result.total_cost_usd == 0.0
        assert result.initial_text == "hello"

    def test_result_with_stages(self):
        stage1 = MARLStageLog(
            stage=1, name="generation", text="initial", tier=TaskTier.MEDIUM,
            cost_usd=0.01, input_tokens=100, output_tokens=50,
        )
        stage2 = MARLStageLog(
            stage=2, name="critique", text="critique text", tier=TaskTier.LIGHTWEIGHT,
            cost_usd=0.001, input_tokens=200, output_tokens=100,
        )
        result = MARLResult(
            final_text="revised output",
            stages_completed=2,
            stage_logs=[stage1, stage2],
            total_cost_usd=0.011,
            total_input_tokens=300,
            total_output_tokens=150,
        )
        assert result.initial_text == "initial"
        assert result.final_text == "revised output"
        assert result.stages_completed == 2


class TestMARLPipeline:
    """Test MARL pipeline execution with mocked LLM client."""

    def _make_mock_client(self, responses: list[str]):
        """Create a mock LLMClient that returns text sequentially."""
        client = MagicMock()
        side_effects = [
            LLMResponse(
                text=text,
                model="test-model",
                backend="test",
                tier=TaskTier.MEDIUM,
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
            )
            for text in responses
        ]
        client.create.side_effect = side_effects
        return client

    def test_single_stage(self):
        client = self._make_mock_client(["단일 응답"])
        pipeline = MARLPipeline(client)
        result = pipeline.run(
            messages=[{"role": "user", "content": "테스트"}],
            config=MARLConfig(stages=1),
        )
        assert result.final_text == "단일 응답"
        assert result.stages_completed == 1
        assert client.create.call_count == 1

    def test_three_stage_pipeline(self):
        client = self._make_mock_client([
            "초기 응답",      # Stage 1: Generation
            "비판 내용",      # Stage 2: Critique
            "수정된 응답",    # Stage 3: Revision
        ])
        pipeline = MARLPipeline(client)
        result = pipeline.run(
            messages=[{"role": "user", "content": "분석해줘"}],
            config=MARLConfig(stages=3),
        )
        assert result.final_text == "수정된 응답"
        assert result.stages_completed == 3
        assert client.create.call_count == 3

    def test_five_stage_pipeline(self):
        client = self._make_mock_client([
            "초기 응답",      # Stage 1
            "비판",          # Stage 2
            "수정된 응답",    # Stage 3
            "심화 응답",      # Stage 4
            "최종 합성",      # Stage 5
        ])
        pipeline = MARLPipeline(client)
        result = pipeline.run(
            messages=[{"role": "user", "content": "심층 분석"}],
            config=MARLConfig(stages=5),
        )
        assert result.final_text == "최종 합성"
        assert result.stages_completed == 5
        assert client.create.call_count == 5
        assert len(result.stage_logs) == 5

    def test_marl_cost_tracking(self):
        client = self._make_mock_client(["a", "b", "c"])
        pipeline = MARLPipeline(client)
        result = pipeline.run(
            messages=[{"role": "user", "content": "test"}],
            config=MARLConfig(stages=3),
        )
        assert result.total_cost_usd == pytest.approx(0.003, abs=0.0001)
        assert result.total_input_tokens == 300
        assert result.total_output_tokens == 150

    def test_marl_disabled_equivalent(self):
        """Single stage MARL should behave identically to direct call."""
        client = self._make_mock_client(["직접 호출과 동일"])
        pipeline = MARLPipeline(client)
        result = pipeline.run(
            messages=[{"role": "user", "content": "test"}],
            config=MARLConfig(stages=1),
        )
        assert result.final_text == "직접 호출과 동일"
        assert result.stages_completed == 1


# ===================================================================
# Phase 4: Tool Schema Validation
# ===================================================================

class WeatherInput(BaseModel):
    city: str = Field(description="도시 이름")
    unit: str = Field(default="celsius", description="온도 단위")


def _get_weather(args: WeatherInput) -> str:
    return f"{args.city}: 맑음"


class TestToolDefinition:
    """Test Pydantic-based tool definitions."""

    def _make_tool(self):
        return ToolDefinition(
            name="get_weather",
            description="날씨 조회",
            input_schema=WeatherInput,
            execute=_get_weather,
        )

    def test_to_openai_tool(self):
        tool = self._make_tool()
        result = tool.to_openai_tool()
        assert result["type"] == "function"
        assert result["function"]["name"] == "get_weather"
        assert result["function"]["description"] == "날씨 조회"
        params = result["function"]["parameters"]
        assert "city" in params["properties"]
        assert "unit" in params["properties"]
        assert "required" in params

    def test_validate_args_dict(self):
        tool = self._make_tool()
        validated = tool.validate_args({"city": "서울"})
        assert isinstance(validated, WeatherInput)
        assert validated.city == "서울"
        assert validated.unit == "celsius"  # default

    def test_validate_args_json_string(self):
        tool = self._make_tool()
        validated = tool.validate_args('{"city": "부산", "unit": "fahrenheit"}')
        assert validated.city == "부산"
        assert validated.unit == "fahrenheit"

    def test_validate_args_invalid(self):
        tool = self._make_tool()
        with pytest.raises(ToolValidationError):
            tool.validate_args({})  # missing required 'city'

    def test_validate_args_invalid_json(self):
        tool = self._make_tool()
        with pytest.raises(ToolValidationError):
            tool.validate_args("{bad json")

    def test_validate_and_execute_success(self):
        tool = self._make_tool()
        result = tool.validate_and_execute({"city": "서울"})
        assert result.success is True
        assert result.output == "서울: 맑음"

    def test_validate_and_execute_validation_failure(self):
        tool = self._make_tool()
        result = tool.validate_and_execute({})
        assert result.success is False
        assert "Validation failed" in result.error

    def test_validate_and_execute_runtime_error(self):
        def failing_fn(args):
            raise RuntimeError("boom")

        tool = ToolDefinition(
            name="fail_tool",
            description="always fails",
            input_schema=WeatherInput,
            execute=failing_fn,
        )
        result = tool.validate_and_execute({"city": "서울"})
        assert result.success is False
        assert "Execution error" in result.error


class TestToolRegistry:
    """Test tool registry management."""

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="test_tool",
            description="test",
            input_schema=WeatherInput,
            execute=_get_weather,
        )
        registry.register(tool)
        assert registry.get("test_tool") is tool
        assert len(registry) == 1

    def test_to_openai_tools(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="tool_a", description="A", input_schema=WeatherInput, execute=_get_weather,
        ))
        registry.register(ToolDefinition(
            name="tool_b", description="B", input_schema=WeatherInput, execute=_get_weather,
        ))
        tools = registry.to_openai_tools()
        assert len(tools) == 2
        names = {t["function"]["name"] for t in tools}
        assert names == {"tool_a", "tool_b"}

    def test_dispatch_success(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="weather", description="날씨", input_schema=WeatherInput, execute=_get_weather,
        ))
        result = registry.dispatch("weather", {"city": "인천"})
        assert result.success is True
        assert result.output == "인천: 맑음"

    def test_dispatch_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.dispatch("nonexistent", {"city": "서울"})
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_tool_names(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="a", description="A", input_schema=WeatherInput, execute=_get_weather,
        ))
        registry.register(ToolDefinition(
            name="b", description="B", input_schema=WeatherInput, execute=_get_weather,
        ))
        assert set(registry.tool_names) == {"a", "b"}
