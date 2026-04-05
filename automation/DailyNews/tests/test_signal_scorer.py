"""Unit tests for signal_scorer — cross-source verification and scoring."""

from __future__ import annotations

import pytest

from antigravity_mcp.integrations.signal_collector import TrendSignal
from antigravity_mcp.integrations.signal_scorer import (
    ScoredSignal,
    SignalScorer,
    _keywords_match,
    _normalise_keyword,
)


# ---------------------------------------------------------------------------
# Keyword Normalisation Tests
# ---------------------------------------------------------------------------


class TestKeywordNormalisation:
    def test_normalise_basic(self) -> None:
        assert _normalise_keyword("  Hello World ") == "hello world"

    def test_normalise_korean_particles(self) -> None:
        assert _normalise_keyword("비트코인은") == "비트코인"
        assert _normalise_keyword("삼성전자가") == "삼성전자"
        assert _normalise_keyword("환율을") == "환율"

    def test_normalise_strip_punctuation(self) -> None:
        assert _normalise_keyword("trend!") == "trend"
        assert _normalise_keyword("topic...") == "topic"

    def test_keywords_match_exact(self) -> None:
        assert _keywords_match("비트코인", "비트코인")

    def test_keywords_match_with_particle(self) -> None:
        assert _keywords_match("비트코인은", "비트코인")

    def test_keywords_match_substring(self) -> None:
        assert _keywords_match("AI 반도체", "AI 반도체 전쟁")

    def test_keywords_no_match(self) -> None:
        assert not _keywords_match("비트코인", "삼성전자")

    def test_keywords_empty(self) -> None:
        assert not _keywords_match("", "test")
        assert not _keywords_match("test", "")


# ---------------------------------------------------------------------------
# Signal Scorer Tests
# ---------------------------------------------------------------------------


def _make_signal(
    keyword: str = "test",
    score: float = 0.5,
    source: str = "google_trends",
    velocity: float = 0.3,
    category: str = "",
) -> TrendSignal:
    return TrendSignal(
        keyword=keyword,
        score=score,
        source=source,
        velocity=velocity,
        category_hint=category,
    )


class TestSignalScorer:
    def test_empty_signals(self) -> None:
        scorer = SignalScorer()
        result = scorer.score_signals([])
        assert result == []

    def test_single_source_scoring(self) -> None:
        scorer = SignalScorer()
        signals = [_make_signal("비트코인", 0.8, "google_trends")]
        result = scorer.score_signals(signals, min_score=0.0)
        assert len(result) == 1
        assert result[0].keyword == "비트코인"
        assert result[0].source_count == 1

    def test_multi_source_boost(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("비트코인", 0.8, "google_trends"),
            _make_signal("비트코인", 0.7, "getdaytrends"),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        assert len(result) == 1
        # Multi-source should boost composite score
        assert result[0].composite_score > 0.8
        assert result[0].source_count == 2

    def test_fuzzy_matching_groups(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("비트코인", 0.8, "google_trends"),
            _make_signal("비트코인은", 0.7, "getdaytrends"),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        # Should be grouped as one
        assert len(result) == 1
        assert result[0].source_count == 2

    def test_different_keywords_not_grouped(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("비트코인", 0.8, "google_trends"),
            _make_signal("삼성전자", 0.7, "getdaytrends"),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        assert len(result) == 2

    def test_sorted_by_score_desc(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("low", 0.3, "google_trends"),
            _make_signal("high", 0.9, "google_trends"),
            _make_signal("mid", 0.6, "google_trends"),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        scores = [r.composite_score for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("high", 0.9, "google_trends"),
            _make_signal("low", 0.1, "google_trends"),
        ]
        result = scorer.score_signals(signals, min_score=0.5)
        # Only high should pass
        assert len(result) == 1
        assert result[0].keyword == "high"

    def test_velocity_bonus(self) -> None:
        scorer = SignalScorer()
        slow = [_make_signal("slow", 0.7, "google_trends", velocity=0.1)]
        fast = [_make_signal("fast", 0.7, "google_trends", velocity=0.8)]

        slow_result = scorer.score_signals(slow, min_score=0.0)
        fast_result = scorer.score_signals(fast, min_score=0.0)

        assert fast_result[0].composite_score > slow_result[0].composite_score

    def test_category_affinity_boost(self) -> None:
        scorer = SignalScorer(target_categories=["Tech"])
        no_cat = [_make_signal("test", 0.7, "google_trends", category="")]
        with_cat = [_make_signal("test2", 0.7, "google_trends", category="Tech")]

        r1 = scorer.score_signals(no_cat, min_score=0.0)
        r2 = scorer.score_signals(with_cat, min_score=0.0)

        assert r2[0].composite_score >= r1[0].composite_score


# ---------------------------------------------------------------------------
# Arbitrage Classification Tests
# ---------------------------------------------------------------------------


class TestArbitrageClassification:
    def test_major_classification(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("big_trend", 0.9, "google_trends", velocity=0.8),
            _make_signal("big_trend", 0.8, "getdaytrends", velocity=0.7),
            _make_signal("big_trend", 0.7, "reddit", velocity=0.6),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        assert result[0].arbitrage_type == "major"
        assert result[0].recommended_action == "series"

    def test_early_wave_two_sources(self) -> None:
        scorer = SignalScorer()
        signals = [
            _make_signal("emerging", 0.8, "google_trends", velocity=0.3),
            _make_signal("emerging", 0.7, "getdaytrends", velocity=0.2),
        ]
        result = scorer.score_signals(signals, min_score=0.0)
        assert result[0].arbitrage_type == "early_wave"
        assert result[0].recommended_action == "draft_now"

    def test_single_x_noise(self) -> None:
        scorer = SignalScorer()
        signals = [_make_signal("noise", 0.5, "x_trending")]
        result = scorer.score_signals(signals, min_score=0.0)
        assert result[0].arbitrage_type == "noise"
        assert result[0].recommended_action == "skip"

    def test_single_google_high_score_early_wave(self) -> None:
        scorer = SignalScorer()
        signals = [_make_signal("breaking", 0.9, "google_trends")]
        result = scorer.score_signals(signals, min_score=0.0)
        assert result[0].arbitrage_type == "early_wave"
        assert result[0].recommended_action == "draft_now"

    def test_scored_signal_source_count(self) -> None:
        s = ScoredSignal(
            keyword="test",
            composite_score=0.8,
            sources=["google_trends", "getdaytrends"],
        )
        assert s.source_count == 2
