"""
EDAPE Unit Tests — PromptInjector, AntiPattern, TemporalPersona

파이프라인 중단 없이 모든 경로가 graceful하게 동작하는지 검증.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════


@dataclasses.dataclass
class FakeConfig:
    db_path: str = "data/getdaytrends.db"
    twitter_bearer_token: str = ""
    edape_lookback_days: int = 7
    edape_max_golden_refs: int = 3


@dataclasses.dataclass
class FakeAngleStats:
    angle: str = ""
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0
    weight: float = 0.0


@dataclasses.dataclass
class FakePatternStats:
    pattern: str = ""
    pattern_type: str = "hook"
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0


@dataclasses.dataclass
class FakeGoldenRef:
    content: str = "이것은 골든 레퍼런스 텍스트입니다."
    angle_type: str = "hot_take"
    engagement_rate: float = 0.05
    category: str = "경제"


# ══════════════════════════════════════════════════════
#  TemporalPersonaTuner Tests
# ══════════════════════════════════════════════════════


class TestTemporalPersonaTuner:
    def test_weekday_morning(self):
        from edape.temporal_persona import TemporalPersonaTuner

        # 월요일 오전 9시
        now = datetime(2026, 4, 6, 9, 30)  # 월요일
        tuner = TemporalPersonaTuner(now=now)
        hint = tuner.get_current_hint()
        assert "팩트" in hint or "데이터" in hint
        assert "주중" in hint

    def test_weekend_afternoon(self):
        from edape.temporal_persona import TemporalPersonaTuner

        # 토요일 오후 3시
        now = datetime(2026, 4, 4, 15, 0)  # 토요일
        tuner = TemporalPersonaTuner(now=now)
        hint = tuner.get_current_hint()
        assert "주말" in hint

    def test_slot_name(self):
        from edape.temporal_persona import TemporalPersonaTuner

        now = datetime(2026, 4, 6, 22, 0)  # 월요일 저녁
        tuner = TemporalPersonaTuner(now=now)
        assert tuner.get_slot_name() == "weekday_evening"

    def test_night_slot(self):
        from edape.temporal_persona import TemporalPersonaTuner

        now = datetime(2026, 4, 6, 3, 0)
        tuner = TemporalPersonaTuner(now=now)
        hint = tuner.get_current_hint()
        assert "야간" in hint


# ══════════════════════════════════════════════════════
#  AntiPatternSuppressor Tests
# ══════════════════════════════════════════════════════


class TestAntiPatternSuppressor:
    def test_find_bottom_patterns(self):
        from edape.anti_pattern import AntiPatternSuppressor

        suppressor = AntiPatternSuppressor(
            lookback_days=7,
            suppression_percentile=0.30,
            min_samples=3,
        )

        # 5개 패턴, 각각 충분한 샘플
        stats = {
            "hot_take": FakeAngleStats(total_tweets=10, avg_engagement_rate=0.05),
            "paradox": FakeAngleStats(total_tweets=8, avg_engagement_rate=0.04),
            "hidden_tip": FakeAngleStats(total_tweets=12, avg_engagement_rate=0.03),
            "sharp_obs": FakeAngleStats(total_tweets=6, avg_engagement_rate=0.01),
            "empathy": FakeAngleStats(total_tweets=7, avg_engagement_rate=0.001),
        }

        bottom = suppressor._find_bottom(stats)
        assert len(bottom) >= 1
        # 최하위는 empathy (0.001)
        assert "empathy" in bottom

    def test_insufficient_data_no_suppression(self):
        from edape.anti_pattern import AntiPatternSuppressor

        suppressor = AntiPatternSuppressor(min_samples=5)

        stats = {
            "hot_take": FakeAngleStats(total_tweets=2, avg_engagement_rate=0.05),
            "paradox": FakeAngleStats(total_tweets=1, avg_engagement_rate=0.01),
        }

        bottom = suppressor._find_bottom(stats)
        assert bottom == []

    @pytest.mark.asyncio
    async def test_analyze_with_mock_tracker(self):
        from edape.anti_pattern import AntiPatternSuppressor

        tracker = MagicMock()
        tracker.get_angle_performance = AsyncMock(return_value={
            "a": FakeAngleStats(total_tweets=10, avg_engagement_rate=0.05),
            "b": FakeAngleStats(total_tweets=10, avg_engagement_rate=0.03),
            "c": FakeAngleStats(total_tweets=10, avg_engagement_rate=0.01),
            "d": FakeAngleStats(total_tweets=10, avg_engagement_rate=0.02),
        })
        tracker.get_hook_performance = AsyncMock(return_value={})
        tracker.get_kick_performance = AsyncMock(return_value={})

        suppressor = AntiPatternSuppressor(min_samples=3)
        result = await suppressor.analyze(tracker)

        assert isinstance(result, dict)
        assert "angles" in result
        assert "hooks" in result
        assert "kicks" in result


# ══════════════════════════════════════════════════════
#  AdaptiveContext Tests
# ══════════════════════════════════════════════════════


class TestAdaptiveContext:
    def test_empty_context_returns_empty_prompt(self):
        from edape.prompt_injector import AdaptiveContext

        ctx = AdaptiveContext()
        assert ctx.is_empty
        assert ctx.to_prompt_block() == ""

    def test_non_empty_context_produces_block(self):
        from edape.prompt_injector import AdaptiveContext, GoldenSnippet, TopPattern

        ctx = AdaptiveContext(
            top_angles=[
                TopPattern(
                    pattern_type="angle",
                    name="hot_take",
                    avg_engagement_rate=0.05,
                    avg_impressions=1500.0,
                    total_tweets=20,
                    weight=0.35,
                )
            ],
            golden_snippets=[
                GoldenSnippet(
                    content="이것은 테스트 골든 레퍼런스입니다.",
                    angle_type="hot_take",
                    engagement_rate=0.08,
                )
            ],
            persona_hint="[주중 09시] 팩트 중심 — 데이터/통계",
            total_tracked_tweets=50,
        )

        block = ctx.to_prompt_block()
        assert "ADAPTIVE CONTEXT" in block
        assert "hot_take" in block
        assert "골든" in block or "레퍼런스" in block
        assert "팩트" in block


# ══════════════════════════════════════════════════════
#  PromptInjector Integration Tests
# ══════════════════════════════════════════════════════


class TestPromptInjector:
    @pytest.mark.asyncio
    async def test_build_without_tracker_returns_empty(self):
        """PerformanceTracker import 실패 시 빈 컨텍스트 반환."""
        from edape.prompt_injector import PromptInjector

        config = FakeConfig()
        injector = PromptInjector(config)

        with patch.object(injector, "_get_tracker", return_value=None):
            ctx = await injector.build()

        assert ctx.is_empty

    @pytest.mark.asyncio
    async def test_build_with_mock_tracker(self):
        """Mock tracker로 전체 빌드 경로 검증."""
        from edape.prompt_injector import PromptInjector

        config = FakeConfig()
        injector = PromptInjector(config)

        mock_tracker = MagicMock()
        mock_tracker.get_angle_performance = AsyncMock(return_value={
            "hot_take": FakeAngleStats(
                total_tweets=20,
                avg_engagement_rate=0.05,
                avg_impressions=1500.0,
            ),
            "empathy": FakeAngleStats(
                total_tweets=15,
                avg_engagement_rate=0.03,
                avg_impressions=800.0,
            ),
        })
        mock_tracker.get_hook_performance = AsyncMock(return_value={})
        mock_tracker.get_kick_performance = AsyncMock(return_value={})
        mock_tracker.get_optimal_pattern_weights = AsyncMock(return_value={
            "angle_weights": {"hot_take": 0.6, "empathy": 0.4},
            "hook_weights": {},
            "kick_weights": {},
        })
        mock_tracker.get_golden_references = AsyncMock(return_value=[
            FakeGoldenRef(),
        ])

        mock_tracker.get_angle_performance = AsyncMock(side_effect=RuntimeError("DB 이상"))
        mock_tracker.get_hook_performance = AsyncMock(side_effect=RuntimeError("DB 이상"))
        mock_tracker.get_kick_performance = AsyncMock(side_effect=RuntimeError("DB 이상"))
        mock_tracker.get_optimal_pattern_weights = AsyncMock(side_effect=RuntimeError("DB 이상"))
        mock_tracker.get_golden_references = AsyncMock(side_effect=RuntimeError("DB 이상"))

        mock_tracker.get_angle_performance = AsyncMock(return_value={
            "hot_take": FakeAngleStats(
                total_tweets=20,
                avg_engagement_rate=0.05,
                avg_impressions=1500.0,
            ),
            "empathy": FakeAngleStats(
                total_tweets=15,
                avg_engagement_rate=0.03,
                avg_impressions=800.0,
            ),
        })
        mock_tracker.get_hook_performance = AsyncMock(return_value={})
        mock_tracker.get_kick_performance = AsyncMock(return_value={})
        mock_tracker.get_optimal_pattern_weights = AsyncMock(return_value={
            "angle_weights": {"hot_take": 0.6, "empathy": 0.4},
            "hook_weights": {},
            "kick_weights": {},
        })
        mock_tracker.get_golden_references = AsyncMock(return_value=[
            FakeGoldenRef(),
        ])

        with patch.object(injector, "_get_tracker", return_value=mock_tracker):
            ctx = await injector.build()

        assert not ctx.is_empty
        assert len(ctx.top_angles) >= 1
        assert ctx.top_angles[0].name == "hot_take"
        assert len(ctx.golden_snippets) == 1
        assert ctx.persona_hint  # 시간대별 힌트가 존재

    @pytest.mark.asyncio
    async def test_build_survives_tracker_exception(self):
        """Tracker가 예외를 던져도 파이프라인은 중단되지 않는다."""
        from edape.prompt_injector import PromptInjector

        config = FakeConfig()
        injector = PromptInjector(config)

        mock_tracker = MagicMock()
        mock_tracker.get_angle_performance.side_effect = RuntimeError("DB 손상")
        mock_tracker.get_hook_performance.side_effect = RuntimeError("DB 손상")
        mock_tracker.get_kick_performance.side_effect = RuntimeError("DB 손상")
        mock_tracker.get_optimal_pattern_weights.side_effect = RuntimeError("DB 손상")
        mock_tracker.get_top_golden_references.side_effect = RuntimeError("DB 손상")

        with patch.object(injector, "_get_tracker", return_value=mock_tracker):
            ctx = await injector.build()

        # 실패해도 빈 컨텍스트 반환 (파이프라인 중단 없음)
        assert isinstance(ctx.built_at, str)


# ══════════════════════════════════════════════════════
#  build_adaptive_context Entry Point Test
# ══════════════════════════════════════════════════════


class TestBuildAdaptiveContext:
    def test_entry_point(self):
        from edape import build_adaptive_context

        config = FakeConfig()

        with patch("edape.prompt_injector.PromptInjector._get_tracker", return_value=None):
            ctx = build_adaptive_context(config)

        assert ctx.is_empty
        assert ctx.built_at  # 타임스탬프는 있어야 함
