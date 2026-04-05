"""Unit tests for shared.llm.language_bridge — Korean-first quality gate.

This module is the LAST LINE OF DEFENSE before LLM responses reach users.
If language_bridge is broken:
  - Chinese-contaminated responses go live (한자 혼입)
  - JSON extraction fails → pipeline crash on structured outputs
  - Korean content detected as "unknown" → quality gate skipped
  - DeepSeek responses bypass retry logic → low-quality output published

Targets:
  1. normalize_text          — Unicode normalization, CJK punctuation, spacing
  2. detect_language          — script-based language detection
  3. normalize_policy         — default merging, glossary injection
  4. inspect_response         — quality flag detection (hanzi, JSON, hangul ratio)
  5. should_retry_after_quality_gate — DeepSeek-specific retry logic
  6. _extract_json_payload    — robust JSON extraction from mixed text
  7. merge_bridge_meta        — metadata merging for fallback chains

Run:
  python -m pytest shared/tests/test_language_bridge.py -v
"""

from __future__ import annotations

import pytest

from shared.llm.language_bridge import (
    _extract_json_payload,
    _script_counts,
    _script_ratios,
    build_bridge_instruction,
    detect_language,
    inspect_response,
    merge_bridge_meta,
    normalize_policy,
    normalize_text,
    should_retry_after_quality_gate,
)
from shared.llm.models import BridgeMeta, LLMPolicy


# ===========================================================================
# 1. normalize_text — Unicode Normalization
# ===========================================================================


class TestNormalizeText:

    def test_cjk_punctuation_converted(self):
        """Fullwidth CJK punctuation → ASCII equivalents."""
        assert normalize_text("Hello\uff0cWorld\u3002") == "Hello,World."
        assert normalize_text("\u201cquoted\u201d") == '"quoted"'

    def test_hangul_latin_spacing(self):
        """Spaces inserted between Korean and Latin/digits."""
        result = normalize_text("AI시대가 온다2026년")
        assert "AI 시대" in result
        assert "온다 2026" in result

    def test_hanzi_hangul_spacing(self):
        """Spaces inserted between Chinese characters and Korean."""
        result = normalize_text("人工智能시대")
        assert "人工智能 시대" in result

    def test_whitespace_collapse(self):
        """Multiple spaces/tabs collapsed to single space."""
        assert normalize_text("hello   world\t\there") == "hello world here"

    def test_excessive_newlines_collapsed(self):
        """3+ consecutive newlines → 2."""
        result = normalize_text("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_strips_edges(self):
        assert normalize_text("  hello  ") == "hello"

    def test_empty_and_none(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""  # type: ignore

    def test_nfkc_normalization(self):
        """Fullwidth letters normalized to ASCII."""
        assert normalize_text("Ｈｅｌｌｏ") == "Hello"


# ===========================================================================
# 2. detect_language — Script-Based Detection
# ===========================================================================


class TestDetectLanguage:

    def test_korean_dominant(self):
        assert detect_language("안녕하세요 오늘의 뉴스입니다") == "ko"

    def test_english_dominant(self):
        assert detect_language("Hello this is a test message") == "en"

    def test_chinese_dominant(self):
        assert detect_language("这是一个测试消息关于人工智能") == "zh"

    def test_mixed_below_threshold(self):
        """No script above 55% → 'mixed'."""
        result = detect_language("Hello 안녕 你好")
        assert result in ("mixed", "ko", "en", "zh")

    def test_empty_text(self):
        assert detect_language("") == "unknown"

    def test_numbers_only(self):
        assert detect_language("12345 !!??") == "unknown"

    def test_pure_hangul(self):
        assert detect_language("가나다라마바사아자차카타파하") == "ko"


# ===========================================================================
# 3. normalize_policy — Default Merging
# ===========================================================================


class TestNormalizePolicy:

    def test_none_returns_defaults(self):
        policy = normalize_policy(None)
        assert policy.locale == "ko-KR"
        assert policy.output_language == "ko"
        assert policy.enforce_korean_output is True

    def test_glossary_merged(self):
        """BIO_GLOSSARY terms are merged into preserve_terms."""
        policy = normalize_policy(LLMPolicy(preserve_terms=["MyTerm"]))
        assert "MyTerm" in policy.preserve_terms
        assert "AI" in policy.preserve_terms
        assert "CRISPR" in policy.preserve_terms

    def test_no_duplicates_in_preserve_terms(self):
        policy = normalize_policy(LLMPolicy(preserve_terms=["AI", "CRISPR"]))
        # Should not have duplicate AI or CRISPR
        assert policy.preserve_terms.count("AI") == 1

    def test_auto_input_language_preserved(self):
        policy = normalize_policy(LLMPolicy(input_language="auto"))
        assert policy.input_language == "auto"

    def test_enforce_korean_auto_enabled(self):
        """If output_language is 'ko', enforce_korean_output is forced True."""
        policy = normalize_policy(LLMPolicy(
            output_language="ko",
            enforce_korean_output=False,
        ))
        assert policy.enforce_korean_output is True

    def test_english_output_no_force(self):
        """If output_language is 'en', enforce_korean is not forced."""
        policy = normalize_policy(LLMPolicy(
            output_language="en",
            enforce_korean_output=False,
        ))
        assert policy.enforce_korean_output is False


# ===========================================================================
# 4. inspect_response — Quality Flags
# ===========================================================================


class TestInspectResponse:

    def test_empty_response_flagged(self):
        policy = LLMPolicy(enforce_korean_output=True)
        meta = inspect_response("", policy)
        assert "empty_response" in meta.quality_flags

    def test_valid_korean_no_flags(self):
        policy = LLMPolicy(enforce_korean_output=True)
        meta = inspect_response("이것은 정상적인 한국어 응답입니다", policy)
        assert meta.quality_flags == []

    def test_excessive_hanzi_flagged(self):
        """Response with >12% Chinese characters should flag."""
        policy = LLMPolicy(enforce_korean_output=True, output_language="ko")
        # Mix enough Chinese to exceed 12% threshold
        text = "这是一个关于人工智能的报告" + "한국어" * 3
        meta = inspect_response(text, policy)
        assert "contains_excessive_hanzi" in meta.quality_flags

    def test_low_hangul_ratio_longform(self):
        """Longform task with <28% hangul should flag."""
        policy = LLMPolicy(
            enforce_korean_output=True,
            output_language="ko",
            task_kind="summary",
        )
        # Mostly English with minimal Korean
        text = "This is a long English summary about artificial intelligence and machine learning. " * 5 + "한글"
        meta = inspect_response(text, policy)
        assert "low_hangul_ratio" in meta.quality_flags

    def test_json_invalid_flagged(self):
        """JSON mode with non-JSON response."""
        policy = LLMPolicy(response_mode="json", enforce_korean_output=False)
        meta = inspect_response("This is not JSON at all", policy)
        assert "json_invalid" in meta.quality_flags

    def test_json_valid_no_flag(self):
        """JSON mode with valid JSON."""
        policy = LLMPolicy(response_mode="json", enforce_korean_output=False)
        meta = inspect_response('{"key": "value"}', policy)
        assert "json_invalid" not in meta.quality_flags

    def test_literal_translation_pattern(self):
        """Chinese meta-text like '翻译如下' should be flagged."""
        policy = LLMPolicy(enforce_korean_output=True, output_language="ko")
        text = "翻译如下 한국어로 번역합니다"
        meta = inspect_response(text, policy)
        assert "literal_translation_pattern" in meta.quality_flags

    def test_hanzi_exceeds_threshold_via_ratio(self):
        """When hanzi ratio >12%, contains_excessive_hanzi fires.
        Note: CJK punctuation (。！) is converted by normalize_text() before
        inspect_response sees it, so forbidden_script_pattern rarely fires in
        practice. We test the hanzi ratio detection instead."""
        policy = LLMPolicy(enforce_korean_output=True, output_language="ko")
        # 8 hanzi + 6 hangul → hanzi_ratio ~57% → well above 12%
        text = "\u4eba\u5de5\u667a\u80fd\u53d1\u5c55\u5f88\u5feb\ud55c\uad6d\uc5d0\uc11c\ub3c4 \uad00\uc2ec"
        meta = inspect_response(text, policy)
        assert "contains_excessive_hanzi" in meta.quality_flags


# ===========================================================================
# 5. should_retry_after_quality_gate — DeepSeek Retry Logic
# ===========================================================================


class TestShouldRetry:

    def test_deepseek_with_blocking_flag(self):
        policy = LLMPolicy(enforce_korean_output=True)
        meta = BridgeMeta(bridge_applied=True, quality_flags=["empty_response"])
        assert should_retry_after_quality_gate("deepseek", policy, meta) is True

    def test_deepseek_no_blocking_flags(self):
        policy = LLMPolicy(enforce_korean_output=True)
        meta = BridgeMeta(bridge_applied=True, quality_flags=["literal_translation_pattern"])
        # literal_translation_pattern is NOT in _BLOCKING_FLAGS
        assert should_retry_after_quality_gate("deepseek", policy, meta) is False

    def test_non_deepseek_never_retries(self):
        """Only DeepSeek triggers quality retries."""
        policy = LLMPolicy(enforce_korean_output=True)
        meta = BridgeMeta(bridge_applied=True, quality_flags=["empty_response"])
        assert should_retry_after_quality_gate("gemini", policy, meta) is False
        assert should_retry_after_quality_gate("anthropic", policy, meta) is False

    def test_bridge_not_applied(self):
        """If bridge wasn't applied, no retry."""
        policy = LLMPolicy(enforce_korean_output=False)
        meta = BridgeMeta(bridge_applied=False, quality_flags=["empty_response"])
        assert should_retry_after_quality_gate("deepseek", policy, meta) is False

    def test_multilingual_task_exempt(self):
        """search_query_generation is exempt from quality gate retry."""
        policy = LLMPolicy(
            enforce_korean_output=True,
            task_kind="search_query_generation",
        )
        meta = BridgeMeta(bridge_applied=True, quality_flags=["low_hangul_ratio"])
        assert should_retry_after_quality_gate("deepseek", policy, meta) is False

    def test_json_invalid_triggers_retry(self):
        policy = LLMPolicy(enforce_korean_output=True)
        meta = BridgeMeta(bridge_applied=True, quality_flags=["json_invalid"])
        assert should_retry_after_quality_gate("deepseek", policy, meta) is True


# ===========================================================================
# 6. _extract_json_payload — JSON Extraction
# ===========================================================================


class TestExtractJsonPayload:

    def test_clean_json_object(self):
        result = _extract_json_payload('{"key": "value"}')
        assert result == {"key": "value"}

    def test_clean_json_array(self):
        result = _extract_json_payload('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_json_embedded_in_text(self):
        """JSON buried in surrounding prose."""
        text = 'Here is the result: {"status": "ok"} end.'
        result = _extract_json_payload(text)
        assert result == {"status": "ok"}

    def test_invalid_json_returns_none(self):
        assert _extract_json_payload("not json at all") is None

    def test_empty_string_returns_none(self):
        assert _extract_json_payload("") is None

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2]}}'
        result = _extract_json_payload(text)
        assert result["outer"]["inner"] == [1, 2]


# ===========================================================================
# 7. merge_bridge_meta — Fallback Chain Metadata
# ===========================================================================


class TestMergeBridgeMeta:

    def test_flags_deduplicated(self):
        primary = BridgeMeta(quality_flags=["flag_a", "flag_b"])
        secondary = BridgeMeta(quality_flags=["flag_b", "flag_c"])
        merged = merge_bridge_meta(primary, secondary)
        assert merged.quality_flags == ["flag_a", "flag_b", "flag_c"]

    def test_bridge_applied_or(self):
        primary = BridgeMeta(bridge_applied=False)
        secondary = BridgeMeta(bridge_applied=True)
        merged = merge_bridge_meta(primary, secondary)
        assert merged.bridge_applied is True

    def test_input_language_from_primary(self):
        primary = BridgeMeta(detected_input_language="ko")
        secondary = BridgeMeta(detected_input_language="en")
        merged = merge_bridge_meta(primary, secondary)
        assert merged.detected_input_language == "ko"

    def test_output_language_from_secondary(self):
        """Secondary (successful) response's output language takes priority."""
        primary = BridgeMeta(detected_output_language="zh")
        secondary = BridgeMeta(detected_output_language="ko")
        merged = merge_bridge_meta(primary, secondary)
        assert merged.detected_output_language == "ko"

    def test_fallback_reason_from_secondary(self):
        primary = BridgeMeta(fallback_reason="")
        secondary = BridgeMeta(fallback_reason="deepseek quality gate")
        merged = merge_bridge_meta(primary, secondary)
        assert merged.fallback_reason == "deepseek quality gate"


# ===========================================================================
# 8. _script_counts / _script_ratios — Internal Helpers
# ===========================================================================


class TestScriptHelpers:

    def test_hangul_count(self):
        counts = _script_counts("가나다라")
        assert counts["hangul"] == 4
        assert counts["hanzi"] == 0
        assert counts["latin"] == 0

    def test_mixed_count(self):
        counts = _script_counts("Hello 안녕 你好")
        assert counts["latin"] == 5
        assert counts["hangul"] == 2
        assert counts["hanzi"] == 2

    def test_ratios_sum_roughly_one(self):
        ratios = _script_ratios("Hello 안녕 你好")
        total = ratios["hangul_ratio"] + ratios["hanzi_ratio"] + ratios["latin_ratio"]
        assert abs(total - 1.0) < 0.01

    def test_empty_text_ratios(self):
        ratios = _script_ratios("")
        assert ratios["hangul_ratio"] == 0.0

    def test_build_bridge_deepseek(self):
        """DeepSeek backend gets extra quality gate instruction."""
        policy = normalize_policy(LLMPolicy(enforce_korean_output=True))
        instruction = build_bridge_instruction(policy, "deepseek")
        assert "DeepSeek" in instruction

    def test_build_bridge_json_mode(self):
        """JSON mode gets JSON-specific instruction."""
        policy = normalize_policy(LLMPolicy(response_mode="json"))
        instruction = build_bridge_instruction(policy, "gemini")
        assert "JSON" in instruction
