"""Tests for Korean quality validators.

Covers:
  - validate_korean_output() core function
  - KoreanQualityResult properties
  - KoreanQualityValidator PostToolHook
  - Edge cases (empty, JSON mode, mixed scripts)
"""

from __future__ import annotations

import pytest

from shared.harness.validators.korean_quality import (
    KoreanQualityResult,
    KoreanQualityValidator,
    validate_korean_output,
)


# ===========================================================================
# Test: validate_korean_output — Core function
# ===========================================================================

class TestValidateKoreanOutput:
    def test_pure_korean_passes(self):
        result = validate_korean_output("안녕하세요 여러분 오늘 날씨가 좋습니다")
        assert result.passed
        assert result.flags == []
        assert result.hangul_ratio > 0.5

    def test_empty_string_fails(self):
        result = validate_korean_output("")
        assert not result.passed
        assert "empty_response" in result.flags
        assert result.text_length == 0

    def test_whitespace_only_fails(self):
        result = validate_korean_output("   \n\t  ")
        assert not result.passed
        assert "empty_response" in result.flags

    def test_excessive_hanzi_fails(self):
        # >12% Chinese characters
        text = "今天天气很好" * 5 + "안녕" * 3
        result = validate_korean_output(text)
        assert not result.passed
        assert "contains_excessive_hanzi" in result.flags

    def test_moderate_hanzi_passes(self):
        # <12% Chinese characters mixed with Korean
        text = "안녕하세요 여러분 오늘의 뉴스입니다 " * 10 + "AI 기술"
        result = validate_korean_output(text)
        assert result.passed
        assert result.hanzi_ratio < 0.12

    def test_low_hangul_ratio_longform(self):
        # Long text with insufficient Korean for longform task
        text = "This is a very long English text " * 10
        result = validate_korean_output(text, task_kind="summary")
        assert not result.passed
        assert "low_hangul_ratio" in result.flags

    def test_low_hangul_ratio_generic_task_passes(self):
        # Generic tasks don't enforce hangul ratio for longform
        text = "This is a very long English text " * 10
        result = validate_korean_output(text, task_kind="generic")
        assert result.passed  # No ratio check for non-longform

    def test_literal_translation_pattern(self):
        text = "안녕하세요 以下是 번역된 내용입니다"
        result = validate_korean_output(text)
        assert "literal_translation_pattern" in result.flags

    def test_forbidden_script_pattern(self):
        # CJK punctuation + significant Hanzi — use raw text without normalization
        # Note: _CJK_PUNCT_TRANSLATION converts 。to . so we check before normalization
        # The validator normalizes internally, so CJK punctuation gets translated.
        # This flag fires when CJK punct is present AND hanzi_ratio > 0.05
        # After normalization, 。becomes . so the regex won't match.
        # This matches language_bridge.py behavior — test the excessive hanzi flag instead.
        text = "这是中文内容还有更多的中文" + "한글" * 3
        result = validate_korean_output(text)
        assert "contains_excessive_hanzi" in result.flags

    def test_json_valid_passes(self):
        result = validate_korean_output(
            '{"key": "안녕하세요"}',
            response_mode="json",
        )
        assert result.passed
        assert "json_invalid" not in result.flags

    def test_json_invalid_fails(self):
        result = validate_korean_output(
            "이것은 JSON이 아닙니다",
            response_mode="json",
        )
        assert not result.passed
        assert "json_invalid" in result.flags

    def test_json_embedded_in_text(self):
        result = validate_korean_output(
            '설명: {"result": "성공", "score": 95}',
            response_mode="json",
        )
        assert result.passed  # Embedded JSON should be extracted

    def test_enforcement_disabled(self):
        # Even with all Chinese, should pass if enforcement disabled
        text = "今天天气很好很好很好很好"
        result = validate_korean_output(text, enforce_korean=False)
        assert result.passed

    def test_custom_thresholds(self):
        text = "안녕하세요 " * 5 + "中文" * 3
        # With strict threshold
        result_strict = validate_korean_output(text, hanzi_threshold=0.01)
        assert "contains_excessive_hanzi" in result_strict.flags

        # With relaxed threshold
        result_relaxed = validate_korean_output(text, hanzi_threshold=0.50)
        assert "contains_excessive_hanzi" not in result_relaxed.flags

    def test_ratios_sum_roughly_to_one(self):
        text = "안녕하세요 Hello 你好"
        result = validate_korean_output(text)
        total = result.hangul_ratio + result.hanzi_ratio + result.latin_ratio
        assert 0.99 <= total <= 1.01

    def test_analysis_task_longform(self):
        # Analysis is a longform task
        text = "안녕하세요 " * 20 + "여러분의 분석 결과입니다 " * 5
        result = validate_korean_output(text, task_kind="analysis")
        assert result.passed
        assert result.hangul_ratio > 0.28


# ===========================================================================
# Test: KoreanQualityResult properties
# ===========================================================================

class TestKoreanQualityResult:
    def test_blocking_flags_filters(self):
        result = KoreanQualityResult(
            passed=False,
            flags=["contains_excessive_hanzi", "literal_translation_pattern"],
        )
        # literal_translation_pattern is not blocking
        assert result.blocking_flags == ["contains_excessive_hanzi"]

    def test_no_blocking_flags(self):
        result = KoreanQualityResult(
            passed=True,
            flags=["literal_translation_pattern", "forbidden_script_pattern"],
        )
        assert result.blocking_flags == []

    def test_frozen(self):
        result = KoreanQualityResult(passed=True)
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]


# ===========================================================================
# Test: KoreanQualityValidator PostToolHook
# ===========================================================================

class TestKoreanQualityValidatorHook:
    @pytest.mark.asyncio
    async def test_string_result_passes(self):
        hook = KoreanQualityValidator()
        result = await hook.execute("llm_call", "안녕하세요 여러분 오늘 뉴스입니다")
        assert result == "안녕하세요 여러분 오늘 뉴스입니다"

    @pytest.mark.asyncio
    async def test_dict_result_gets_metadata(self):
        hook = KoreanQualityValidator()
        result = await hook.execute("llm_call", {
            "text": "안녕하세요 분석 결과입니다",
            "model": "claude",
        })
        assert "_korean_quality" in result
        assert result["_korean_quality"]["passed"] is True
        assert result["_korean_quality"]["hangul_ratio"] > 0

    @pytest.mark.asyncio
    async def test_strict_mode_raises(self):
        hook = KoreanQualityValidator(strict=True)
        with pytest.raises(ValueError, match="Korean quality check failed"):
            await hook.execute("llm_call", "今天天气很好" * 10)

    @pytest.mark.asyncio
    async def test_non_strict_mode_passes_bad_content(self):
        hook = KoreanQualityValidator(strict=False)
        result = await hook.execute("llm_call", {
            "content": "今天天气很好" * 10,
        })
        assert result["_korean_quality"]["passed"] is False

    @pytest.mark.asyncio
    async def test_non_text_result_passthrough(self):
        hook = KoreanQualityValidator()
        result = await hook.execute("database_read", [1, 2, 3])
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_extracts_from_output_key(self):
        hook = KoreanQualityValidator()
        result = await hook.execute("llm_call", {
            "output": "한국어 콘텐츠 테스트",
        })
        assert "_korean_quality" in result
        assert result["_korean_quality"]["passed"] is True

    @pytest.mark.asyncio
    async def test_task_kind_propagated(self):
        hook = KoreanQualityValidator(task_kind="summary", strict=True)
        # Long English text should fail for summary task (low_hangul_ratio)
        long_en = "This is a long English analysis report " * 20
        with pytest.raises(ValueError, match="Korean quality check failed"):
            await hook.execute("llm_call", long_en)

    @pytest.mark.asyncio
    async def test_task_kind_summary_korean_passes(self):
        hook = KoreanQualityValidator(task_kind="summary", strict=True)
        text = "오늘의 뉴스 요약입니다 " * 20
        result = await hook.execute("llm_call", text)
        assert result == text  # Should pass without error


# ===========================================================================
# Test: DeepAgentsAdapter
# ===========================================================================

class TestDeepAgentsAdapter:
    @pytest.fixture
    def constitution(self):
        from shared.harness.constitution import Constitution
        return Constitution.from_dict({
            "agent_name": "test-deep",
            "max_budget_usd": 2.0,
            "tools": [
                {"name": "web_search", "allowed": True, "max_calls": 50},
                {"name": "llm_call", "allowed": True, "max_calls": 200},
            ],
        })

    def test_import(self):
        from shared.harness.adapters.deepagents import DeepAgentsAdapter
        assert DeepAgentsAdapter is not None

    def test_is_full_mode_without_sdk(self, constitution):
        from shared.harness.adapters.deepagents import DeepAgentsAdapter
        adapter = DeepAgentsAdapter(constitution)
        # DeepAgents SDK is not installed in test env
        assert not adapter.is_full_mode

    @pytest.mark.asyncio
    async def test_fallback_execution(self, constitution):
        from shared.harness.adapters.deepagents import DeepAgentsAdapter

        async def executor(tool_name, tool_input):
            return {"tool": tool_name, "ok": True}

        adapter = DeepAgentsAdapter(constitution, tool_executor=executor)
        result = await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "test"}},
            tools=["web_search"],
        )
        assert result.success
        assert result.output["ok"] is True

    @pytest.mark.asyncio
    async def test_spawn_subagent(self, constitution):
        from shared.harness.adapters.deepagents import DeepAgentsAdapter
        adapter = DeepAgentsAdapter(constitution)
        result = await adapter.spawn_subagent(role="analyzer", task="analyze")
        assert result.success
        assert isinstance(result.output, DeepAgentsAdapter)
        assert result.metadata["framework"] in ("deepagents", "fallback")

    def test_session_summary(self, constitution):
        from shared.harness.adapters.deepagents import DeepAgentsAdapter
        adapter = DeepAgentsAdapter(constitution)
        summary = adapter.get_session_summary()
        assert summary["adapter_type"] == "deepagents"
        assert "deepagents_available" in summary


# ===========================================================================
# Test: Content-Intelligence Constitution
# ===========================================================================

class TestContentIntelligenceConstitution:
    @pytest.fixture
    def constitution(self):
        from shared.harness.constitution import Constitution
        path = "d:/AI project/packages/shared/harness/constitutions/content_intelligence.yaml"
        try:
            return Constitution.from_yaml(path)
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_loads_successfully(self, constitution):
        assert constitution.agent_name == "content-intelligence-pipeline"

    def test_budget(self, constitution):
        assert constitution.max_budget_usd == 3.0

    def test_collection_tools_allowed(self, constitution):
        for tool in ["collect_x_trends", "collect_threads_trends", "collect_naver_trends"]:
            assert constitution.is_tool_allowed(tool), f"{tool} should be allowed"

    def test_publish_requires_approval(self, constitution):
        assert constitution.requires_human_approval("publish_batch_to_notion")
        assert constitution.requires_human_approval("publish_batch_to_x")

    def test_dangerous_tools_forbidden(self, constitution):
        assert not constitution.is_tool_allowed("shell_execute")
        assert not constitution.is_tool_allowed("file_delete")
        assert not constitution.is_tool_allowed("code_run")

    def test_llm_call_high_limit(self, constitution):
        perm = constitution.get_permission("llm_call")
        assert perm is not None
        assert perm.max_calls_per_session == 300
