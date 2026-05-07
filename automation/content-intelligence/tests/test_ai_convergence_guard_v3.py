"""Tests for AI Convergence Guard v3 — multi-source + lifecycle + clustering."""

from __future__ import annotations

import pytest
from regulators.ai_convergence_guard_v3 import (
    AIConvergenceResultV3,
    KeywordLifecycle,
    KeywordPhase,
    TopicCluster,
    _calculate_confidence,
    _classify_phase,
    _find_cluster,
    apply_ai_convergence_guard_v3,
)
from storage.models import MergedTrendReport, PlatformTrend, PlatformTrendReport


# ── Helpers ──

def _make_multi_platform_report(
    platform_keywords: dict[str, list[tuple[str, int]]],
) -> MergedTrendReport:
    """Helper: create multi-platform report.

    Args:
        platform_keywords: {platform: [(keyword, volume), ...]}
    """
    prs = []
    for platform, kv_list in platform_keywords.items():
        trends = [PlatformTrend(keyword=kw, volume=vol) for kw, vol in kv_list]
        prs.append(PlatformTrendReport(platform=platform, trends=trends))
    return MergedTrendReport(
        platform_reports=prs,
        cross_platform_keywords=[],
        top_insights=[],
    )


# ── _classify_phase ──

class TestClassifyPhase:
    def test_peak(self) -> None:
        assert _classify_phase(3, 50000) == KeywordPhase.PEAK
        assert _classify_phase(5, 100000) == KeywordPhase.PEAK

    def test_growing(self) -> None:
        assert _classify_phase(2, 10000) == KeywordPhase.GROWING
        assert _classify_phase(2, 49999) == KeywordPhase.GROWING

    def test_emerging(self) -> None:
        assert _classify_phase(1, 1000) == KeywordPhase.EMERGING
        assert _classify_phase(2, 3000) == KeywordPhase.EMERGING

    def test_low_volume_single_platform(self) -> None:
        assert _classify_phase(1, 100) == KeywordPhase.EMERGING


# ── _find_cluster ──

class TestFindCluster:
    def test_llm_foundation(self) -> None:
        assert _find_cluster("GPT") == "LLM/Foundation"
        assert _find_cluster("claude") == "LLM/Foundation"
        assert _find_cluster("transformer") == "LLM/Foundation"

    def test_generative_ai(self) -> None:
        assert _find_cluster("midjourney") == "Generative AI"
        assert _find_cluster("stable diffusion") == "Generative AI"

    def test_ai_agents(self) -> None:
        assert _find_cluster("AI agent") == "AI Agents"
        assert _find_cluster("MCP") == "AI Agents"
        assert _find_cluster("agentic") == "AI Agents"

    def test_ml_infra(self) -> None:
        assert _find_cluster("fine-tuning") == "ML Infrastructure"
        assert _find_cluster("RAG") == "ML Infrastructure"
        assert _find_cluster("embedding") == "ML Infrastructure"

    def test_unknown_defaults_to_other(self) -> None:
        assert _find_cluster("some random AI thing") == "Other AI"


# ── _calculate_confidence ──

class TestCalculateConfidence:
    def test_perfect_confidence(self) -> None:
        conf = _calculate_confidence(
            ai_density=0.5, cross_platform_count=5,
            source_diversity=4, total_trends=20,
        )
        assert conf == pytest.approx(1.0)

    def test_zero_confidence(self) -> None:
        conf = _calculate_confidence(0.0, 0, 0, 0)
        assert conf == pytest.approx(0.0)

    def test_partial_confidence(self) -> None:
        conf = _calculate_confidence(0.25, 2, 2, 10)
        assert 0.0 < conf < 1.0


# ── apply_ai_convergence_guard_v3 ──

class TestApplyV3:
    def test_empty_report(self) -> None:
        report = MergedTrendReport()
        result = apply_ai_convergence_guard_v3(report)
        assert result.total_trend_count == 0
        assert result.convergence_signal is False
        assert result.confidence_score == 0.0

    def test_no_ai_trends(self) -> None:
        report = _make_multi_platform_report({
            "x": [("부동산", 100), ("날씨", 200)],
        })
        result = apply_ai_convergence_guard_v3(report)
        assert result.ai_trend_count == 0
        assert result.convergence_signal is False
        assert len(result.cross_platform_hits) == 0

    def test_cross_platform_detected(self) -> None:
        """Same AI keyword on two platforms → cross-platform hit."""
        report = _make_multi_platform_report({
            "x": [("GPT", 100), ("날씨", 200)],
            "naver": [("GPT", 150), ("쇼핑", 300)],
        })
        result = apply_ai_convergence_guard_v3(report)
        assert "gpt" in result.cross_platform_hits

    def test_cross_platform_gets_higher_boost(self) -> None:
        """Cross-platform keywords get 2.0x vs 1.5x for single."""
        report = _make_multi_platform_report({
            "x": [("GPT", 100)],
            "naver": [("GPT", 100), ("Claude", 100)],
        })
        result = apply_ai_convergence_guard_v3(report)
        if result.convergence_signal:
            # GPT is cross-platform → 2.0x = 200
            gpt_trends = [
                t for pr in report.platform_reports for t in pr.trends
                if t.keyword.lower() == "gpt"
            ]
            for t in gpt_trends:
                assert t.volume == 200
            # Claude is single-platform → 1.5x = 150
            claude = [
                t for pr in report.platform_reports for t in pr.trends
                if t.keyword.lower() == "claude"
            ]
            for t in claude:
                assert t.volume == 150

    def test_lifecycle_classification(self) -> None:
        report = _make_multi_platform_report({
            "x": [("GPT", 30000)],
            "naver": [("GPT", 30000)],
            "google": [("GPT", 20000)],
        })
        result = apply_ai_convergence_guard_v3(report)
        gpt_lc = [lc for lc in result.keyword_lifecycles if lc.keyword == "gpt"]
        assert len(gpt_lc) == 1
        # 3 platforms + 80000 volume → peak
        assert gpt_lc[0].phase == KeywordPhase.PEAK

    def test_topic_clusters_populated(self) -> None:
        report = _make_multi_platform_report({
            "x": [("GPT", 100), ("midjourney", 100), ("날씨", 100)],
        })
        result = apply_ai_convergence_guard_v3(report)
        cluster_names = [c.name for c in result.topic_clusters]
        assert "LLM/Foundation" in cluster_names
        assert "Generative AI" in cluster_names

    def test_confidence_reflects_diversity(self) -> None:
        """More platforms → higher confidence."""
        single = _make_multi_platform_report({
            "x": [("GPT", 100), ("Claude", 100)],
        })
        multi = _make_multi_platform_report({
            "x": [("GPT", 100)],
            "naver": [("Claude", 100)],
            "google": [("LLM", 100)],
        })
        r1 = apply_ai_convergence_guard_v3(single)
        r2 = apply_ai_convergence_guard_v3(multi)
        assert r2.confidence_score >= r1.confidence_score

    def test_summary_v3_format(self) -> None:
        result = AIConvergenceResultV3(
            ai_trend_count=5,
            total_trend_count=10,
            convergence_signal=True,
            confidence_score=0.8,
            cross_platform_hits=["gpt", "llm"],
        )
        s = result.summary()
        assert "v3" in s
        assert "conf=" in s
        assert "cross=2" in s

    def test_convergence_insight_injected(self) -> None:
        report = _make_multi_platform_report({
            "x": [("GPT", 100), ("Claude", 100), ("LLM", 100)],
        })
        result = apply_ai_convergence_guard_v3(report)
        assert result.convergence_signal is True
        assert any("v3" in ins for ins in report.top_insights)

    def test_below_threshold_no_boost(self) -> None:
        report = _make_multi_platform_report({
            "x": [("GPT", 100), ("날씨", 200), ("부동산", 300),
                   ("쇼핑", 400), ("스포츠", 500)],
        })
        result = apply_ai_convergence_guard_v3(report)
        assert result.convergence_signal is False
        assert len(result.boosted_keywords) == 0
        # GPT volume unchanged
        gpt = report.platform_reports[0].trends[0]
        assert gpt.volume == 100
