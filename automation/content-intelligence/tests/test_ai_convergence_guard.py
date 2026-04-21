"""Tests for AI Convergence Guard v2."""

from __future__ import annotations

import pytest
from regulators.ai_convergence_guard import (
    AIConvergenceResult,
    _is_ai_keyword,
    _is_ai_trend,
    apply_ai_convergence_guard,
)
from storage.models import MergedTrendReport, PlatformTrend, PlatformTrendReport


# ── _is_ai_keyword ──


class TestIsAIKeyword:
    """AI 키워드 판별 테스트."""

    @pytest.mark.parametrize(
        "keyword",
        [
            "AI", "llm", "GPT", "ChatGPT", "claude", "Gemini",
            "openai", "anthropic", "deepmind", "transformer",
            "prompt engineering", "ai agent", "agentic",
            "MCP", "model context protocol",
        ],
    )
    def test_core_keywords_detected(self, keyword: str) -> None:
        assert _is_ai_keyword(keyword) is True

    @pytest.mark.parametrize(
        "keyword",
        [
            "bitcoin", "weather", "cooking", "k-pop",
            "soccer", "real estate", "shopping",
        ],
    )
    def test_non_ai_keywords_rejected(self, keyword: str) -> None:
        assert _is_ai_keyword(keyword) is False

    def test_compound_keyword_with_ai_token(self) -> None:
        assert _is_ai_keyword("GPT-4 업데이트") is True
        assert _is_ai_keyword("llm fine-tuning") is True

    def test_adjacent_pattern_korean(self) -> None:
        assert _is_ai_keyword("인공지능") is True
        assert _is_ai_keyword("생성형 AI") is True
        assert _is_ai_keyword("대규모 언어 모델") is True
        assert _is_ai_keyword("멀티모달") is True

    def test_adjacent_pattern_english(self) -> None:
        assert _is_ai_keyword("machine learning") is True
        assert _is_ai_keyword("deep learning trends") is True


# ── _is_ai_trend ──


class TestIsAITrend:
    """트렌드 항목의 AI 관련 여부 판별."""

    def test_ai_keyword_trend(self) -> None:
        trend = PlatformTrend(keyword="GPT-4o")
        assert _is_ai_trend(trend) is True

    def test_non_ai_trend(self) -> None:
        trend = PlatformTrend(keyword="부동산 시장")
        assert _is_ai_trend(trend) is False

    def test_indirect_ai_via_project_connection(self) -> None:
        """키워드는 AI가 아니지만 project_connection에 AI 언급."""
        trend = PlatformTrend(
            keyword="생산성 도구",
            project_connection="AI 자동화 파이프라인과 연결 가능",
        )
        assert _is_ai_trend(trend) is True

    def test_non_ai_project_connection(self) -> None:
        trend = PlatformTrend(
            keyword="날씨 앱",
            project_connection="모바일 UX 개선",
        )
        assert _is_ai_trend(trend) is False


# ── apply_ai_convergence_guard ──


def _make_report(keywords: list[str]) -> MergedTrendReport:
    """헬퍼: 키워드 리스트로 단일 플랫폼 MergedTrendReport 생성."""
    trends = [PlatformTrend(keyword=kw, volume=100) for kw in keywords]
    pr = PlatformTrendReport(platform="x", trends=trends)
    return MergedTrendReport(
        platform_reports=[pr],
        cross_platform_keywords=[],
        top_insights=[],
    )


class TestApplyAIConvergenceGuard:
    """AI Convergence Guard 통합 테스트."""

    def test_empty_report(self) -> None:
        report = MergedTrendReport()
        result = apply_ai_convergence_guard(report)
        assert result.total_trend_count == 0
        assert result.convergence_signal is False
        assert result.ai_density == 0.0

    def test_no_ai_trends(self) -> None:
        report = _make_report(["부동산", "날씨", "주식시장"])
        result = apply_ai_convergence_guard(report)
        assert result.ai_trend_count == 0
        assert result.convergence_signal is False

    def test_below_threshold(self) -> None:
        """AI 트렌드 1/5 = 20% → 임계값(30%) 미만."""
        report = _make_report(["GPT", "부동산", "날씨", "주식", "쇼핑"])
        result = apply_ai_convergence_guard(report)
        assert result.ai_trend_count == 1
        assert result.convergence_signal is False
        # Volume은 부스트되지 않음
        ai_trend = report.platform_reports[0].trends[0]
        assert ai_trend.volume == 100

    def test_above_threshold_triggers_boost(self) -> None:
        """AI 트렌드 2/4 = 50% → boost 작동."""
        report = _make_report(["GPT-4", "Claude", "부동산", "날씨"])
        result = apply_ai_convergence_guard(report)
        assert result.ai_trend_count == 2
        assert result.convergence_signal is True
        assert len(result.boosted_keywords) == 2
        # Volume 부스트 확인 (100 → 150)
        gpt_trend = report.platform_reports[0].trends[0]
        assert gpt_trend.volume == 150

    def test_cross_platform_keywords_injected(self) -> None:
        """Convergence 시 AI 키워드가 cross_platform_keywords에 추가."""
        report = _make_report(["LLM", "transformer", "날씨"])
        result = apply_ai_convergence_guard(report)
        assert result.convergence_signal is True
        assert "LLM" in report.cross_platform_keywords
        assert "transformer" in report.cross_platform_keywords

    def test_top_insights_signal_injected(self) -> None:
        """Convergence 시 top_insights에 신호 메시지 삽입."""
        report = _make_report(["AI agent", "MCP"])
        result = apply_ai_convergence_guard(report)
        assert result.convergence_signal is True
        assert any("Convergence" in ins for ins in report.top_insights)

    def test_no_duplicate_cross_platform(self) -> None:
        """이미 존재하는 키워드는 중복 추가하지 않음."""
        report = _make_report(["GPT", "Claude", "날씨"])
        report.cross_platform_keywords = ["gpt"]
        result = apply_ai_convergence_guard(report)
        # GPT는 이미 있으므로 추가 안 됨, Claude만 추가
        assert report.cross_platform_keywords.count("GPT") == 0  # 소문자만 있음
        gpt_count = sum(1 for kw in report.cross_platform_keywords if kw.lower() == "gpt")
        assert gpt_count == 1  # 원래 1개만 유지

    def test_custom_threshold(self) -> None:
        """커스텀 임계값 테스트."""
        report = _make_report(["GPT", "부동산", "날씨", "주식", "쇼핑"])
        # 기본 30%에서는 미달 (1/5 = 20%)
        result_default = apply_ai_convergence_guard(report, threshold=0.3)
        assert result_default.convergence_signal is False

        # 임계값 15%로 낮추면 통과
        report2 = _make_report(["GPT", "부동산", "날씨", "주식", "쇼핑"])
        result_low = apply_ai_convergence_guard(report2, threshold=0.15)
        assert result_low.convergence_signal is True

    def test_zero_volume_gets_minimum(self) -> None:
        """volume=0인 트렌드도 부스트 시 최소값(10) 부여."""
        trends = [PlatformTrend(keyword="GPT", volume=0), PlatformTrend(keyword="LLM", volume=0)]
        pr = PlatformTrendReport(platform="x", trends=trends)
        report = MergedTrendReport(platform_reports=[pr])

        result = apply_ai_convergence_guard(report)
        assert result.convergence_signal is True
        for t in report.platform_reports[0].trends:
            assert t.volume == 10

    def test_all_ai_trends(self) -> None:
        """100% AI 트렌드."""
        report = _make_report(["GPT", "Claude", "Gemini", "LLM", "transformer"])
        result = apply_ai_convergence_guard(report)
        assert result.ai_density == 1.0
        assert result.convergence_signal is True
        assert result.ai_trend_count == 5

    def test_result_summary(self) -> None:
        """결과 요약 문자열 형식."""
        result = AIConvergenceResult(
            ai_trend_count=3,
            total_trend_count=10,
            convergence_signal=True,
        )
        summary = result.summary()
        assert "3/10" in summary
        assert "CONVERGENCE" in summary

    def test_multi_platform_report(self) -> None:
        """멀티 플랫폼 리포트에서 전체 트렌드를 정확히 분석."""
        x_trends = [PlatformTrend(keyword="GPT", volume=100)]
        naver_trends = [PlatformTrend(keyword="Claude", volume=80), PlatformTrend(keyword="날씨", volume=50)]
        report = MergedTrendReport(
            platform_reports=[
                PlatformTrendReport(platform="x", trends=x_trends),
                PlatformTrendReport(platform="naver", trends=naver_trends),
            ],
        )
        result = apply_ai_convergence_guard(report)
        assert result.total_trend_count == 3
        assert result.ai_trend_count == 2
        assert result.convergence_signal is True  # 2/3 ≈ 67%
