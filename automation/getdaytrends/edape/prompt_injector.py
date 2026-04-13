"""
EDAPE Core — PromptInjector

PerformanceTracker로부터 실시간 성과 데이터를 읽어
프롬프트에 주입할 AdaptiveContext를 빌드한다.

핵심 원칙:
  1. 성과 데이터 → 프롬프트 주입은 항상 OPTIONAL. 데이터 없으면 빈 컨텍스트 반환.
  2. 토큰 예산을 초과하지 않도록 max_golden_refs, max_pattern_examples 제한.
  3. PerformanceTracker가 없거나 초기화 실패해도 파이프라인은 정상 동작.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime
from typing import Any

from loguru import logger as log


async def _maybe_await(value):
    """Support both async tracker APIs and older synchronous test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


# ══════════════════════════════════════════════════════
#  Data Structures
# ══════════════════════════════════════════════════════


@dataclasses.dataclass
class TopPattern:
    """성과 상위 패턴 한 건."""

    pattern_type: str  # "angle" | "hook" | "kick"
    name: str
    avg_engagement_rate: float = 0.0
    avg_impressions: float = 0.0
    total_tweets: int = 0
    weight: float = 0.0


@dataclasses.dataclass
class GoldenSnippet:
    """골든 레퍼런스에서 추출한 프롬프트 주입용 스니펫."""

    content: str
    angle_type: str = ""
    engagement_rate: float = 0.0
    category: str = ""


@dataclasses.dataclass
class AdaptiveContext:
    """
    프롬프트에 주입될 적응형 컨텍스트 데이터.
    prompt_builder.py가 이 객체를 받아 system prompt에 삽입한다.
    """

    # 성과 기반 추천 패턴 (상위 3개)
    top_angles: list[TopPattern] = dataclasses.field(default_factory=list)
    top_hooks: list[TopPattern] = dataclasses.field(default_factory=list)
    top_kicks: list[TopPattern] = dataclasses.field(default_factory=list)

    # 명시적 금지 패턴 (하위 20%)
    suppressed_angles: list[str] = dataclasses.field(default_factory=list)
    suppressed_hooks: list[str] = dataclasses.field(default_factory=list)
    suppressed_kicks: list[str] = dataclasses.field(default_factory=list)

    # 골든 레퍼런스 스니펫
    golden_snippets: list[GoldenSnippet] = dataclasses.field(default_factory=list)

    # 시간대별 페르소나 튜닝 힌트
    persona_hint: str = ""

    # 메타
    built_at: str = ""
    data_period_days: int = 7
    total_tracked_tweets: int = 0

    @property
    def is_empty(self) -> bool:
        """데이터가 충분한지 확인. 비어있으면 프롬프트 주입 스킵."""
        return (
            not self.top_angles
            and not self.golden_snippets
            and not self.persona_hint
        )

    def to_prompt_block(self) -> str:
        """
        System prompt에 삽입할 텍스트 블록 생성.
        비어있으면 빈 문자열 반환 → 기존 프롬프트 동작 유지.
        """
        if self.is_empty:
            return ""

        lines: list[str] = []
        lines.append("\n═══ [ADAPTIVE CONTEXT — 성과 기반 자동 튜닝] ═══")
        lines.append(f"분석 기간: 최근 {self.data_period_days}일 | 추적 트윗: {self.total_tracked_tweets}건\n")

        # 1. 추천 패턴
        if self.top_angles:
            lines.append("▶ 최근 고성과 앵글 패턴 (우선 사용):")
            for p in self.top_angles:
                lines.append(
                    f"  • {p.name} — ER {p.avg_engagement_rate:.4%}, "
                    f"노출 평균 {p.avg_impressions:.0f}, 가중치 {p.weight:.2f}"
                )

        if self.top_hooks:
            lines.append("\n▶ 최근 고성과 훅 패턴:")
            for p in self.top_hooks:
                lines.append(f"  • {p.name} — ER {p.avg_engagement_rate:.4%}")

        if self.top_kicks:
            lines.append("\n▶ 최근 고성과 킥 패턴:")
            for p in self.top_kicks:
                lines.append(f"  • {p.name} — ER {p.avg_engagement_rate:.4%}")

        # 2. 금지 패턴
        suppressed = []
        if self.suppressed_angles:
            suppressed.extend(f"[앵글] {a}" for a in self.suppressed_angles)
        if self.suppressed_hooks:
            suppressed.extend(f"[훅] {h}" for h in self.suppressed_hooks)
        if self.suppressed_kicks:
            suppressed.extend(f"[킥] {k}" for k in self.suppressed_kicks)

        if suppressed:
            lines.append("\n▶ 성과 부진 패턴 (사용 금지):")
            for s in suppressed:
                lines.append(f"  ✗ {s}")

        # 3. 골든 레퍼런스
        if self.golden_snippets:
            lines.append(f"\n▶ 과거 히트 트윗 레퍼런스 (문체·구조 참고, 복사 금지):")
            for i, gs in enumerate(self.golden_snippets, 1):
                preview = gs.content[:200].replace("\n", " ")
                lines.append(
                    f"  [{i}] ({gs.angle_type}, ER {gs.engagement_rate:.4%}) "
                    f'"{preview}..."'
                )

        # 4. 시간대 페르소나
        if self.persona_hint:
            lines.append(f"\n▶ 현재 시간대 페르소나: {self.persona_hint}")

        lines.append("═══════════════════════════════════════════════\n")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  PromptInjector
# ══════════════════════════════════════════════════════


class PromptInjector:
    """
    PerformanceTracker + GoldenReference에서 데이터를 읽어
    AdaptiveContext를 빌드하는 어댑터.
    """

    # 튜닝 상수
    DEFAULT_LOOKBACK_DAYS: int = 7
    MAX_TOP_PATTERNS: int = 3
    MAX_GOLDEN_REFS: int = 3
    SUPPRESSION_PERCENTILE: float = 0.20  # 하위 20%
    MIN_SAMPLES_FOR_CONFIDENCE: int = 5

    def __init__(self, config: Any) -> None:
        self._config = config
        self._db_path: str = getattr(config, "db_path", "data/getdaytrends.db")
        self._bearer_token: str = getattr(config, "twitter_bearer_token", "")
        self._lookback_days: int = getattr(
            config, "edape_lookback_days", self.DEFAULT_LOOKBACK_DAYS
        )
        self._max_golden: int = getattr(
            config, "edape_max_golden_refs", self.MAX_GOLDEN_REFS
        )

    async def build(self) -> AdaptiveContext:
        """
        메인 빌드 메서드. 실패 시 빈 AdaptiveContext 반환 (절대 파이프라인 중단 안 함).
        """
        ctx = AdaptiveContext(
            built_at=datetime.now().isoformat(),
            data_period_days=self._lookback_days,
        )

        try:
            tracker = await self._get_tracker()
            if tracker is None:
                log.debug("[EDAPE] PerformanceTracker 미사용 → 빈 컨텍스트")
                return ctx

            # 1. 앵글/훅/킥 패턴 분석
            await self._inject_pattern_weights(tracker, ctx)

            # 2. Anti-pattern 억제
            await self._inject_suppressions(tracker, ctx)

            # 3. 골든 레퍼런스
            await self._inject_golden_refs(tracker, ctx)

            # 4. 시간대 페르소나
            self._inject_temporal_persona(ctx)

            log.info(
                f"[EDAPE] 적응형 컨텍스트 빌드 완료 — "
                f"angles={len(ctx.top_angles)} hooks={len(ctx.top_hooks)} "
                f"golden={len(ctx.golden_snippets)} "
                f"suppressed={len(ctx.suppressed_angles)+len(ctx.suppressed_hooks)+len(ctx.suppressed_kicks)} "
                f"persona='{ctx.persona_hint[:30]}'"
            )

        except Exception as e:
            log.warning(f"[EDAPE] 컨텍스트 빌드 실패 (무시, 빈 컨텍스트 반환): {type(e).__name__}: {e}")

        return ctx

    # ── Internal ──

    async def _get_tracker(self):
        """PerformanceTracker 인스턴스 반환. import 실패 시 None."""
        try:
            from performance_tracker import PerformanceTracker
        except ImportError:
            try:
                from ..performance_tracker import PerformanceTracker
            except ImportError:
                return None

        tracker = PerformanceTracker(
            db_path=self._db_path,
            bearer_token=self._bearer_token,
        )
        await _maybe_await(tracker.init_table())
        return tracker

    async def _inject_pattern_weights(self, tracker, ctx: AdaptiveContext) -> None:
        """앵글/훅/킥 성과 상위 패턴을 ctx에 주입."""
        try:
            pattern_data = await _maybe_await(tracker.get_optimal_pattern_weights(
                days=self._lookback_days,
                min_samples=self.MIN_SAMPLES_FOR_CONFIDENCE,
            ))

            # 앵글
            angle_stats = await _maybe_await(tracker.get_angle_performance(self._lookback_days))
            angle_weights = pattern_data.get("angle_weights", {})
            ctx.top_angles = self._extract_top_patterns(
                angle_stats, angle_weights, "angle"
            )
            ctx.total_tracked_tweets = sum(
                s.total_tweets for s in angle_stats.values()
            )

            # 훅
            hook_stats = await _maybe_await(tracker.get_hook_performance(self._lookback_days))
            hook_weights = pattern_data.get("hook_weights", {})
            ctx.top_hooks = self._extract_top_patterns(
                hook_stats, hook_weights, "hook"
            )

            # 킥
            kick_stats = await _maybe_await(tracker.get_kick_performance(self._lookback_days))
            kick_weights = pattern_data.get("kick_weights", {})
            ctx.top_kicks = self._extract_top_patterns(
                kick_stats, kick_weights, "kick"
            )

        except Exception as e:
            log.debug(f"[EDAPE] 패턴 가중치 주입 실패: {e}")

    def _extract_top_patterns(
        self, stats: dict, weights: dict, pattern_type: str
    ) -> list[TopPattern]:
        """stats dict에서 engagement rate 상위 N개 패턴 추출."""
        candidates = []
        for name, stat in stats.items():
            if stat.total_tweets >= self.MIN_SAMPLES_FOR_CONFIDENCE:
                candidates.append(
                    TopPattern(
                        pattern_type=pattern_type,
                        name=name,
                        avg_engagement_rate=stat.avg_engagement_rate,
                        avg_impressions=stat.avg_impressions,
                        total_tweets=stat.total_tweets,
                        weight=weights.get(name, 0.0),
                    )
                )

        candidates.sort(key=lambda x: x.avg_engagement_rate, reverse=True)
        return candidates[: self.MAX_TOP_PATTERNS]

    async def _inject_suppressions(self, tracker, ctx: AdaptiveContext) -> None:
        """하위 20% 패턴을 금지 목록에 추가."""
        try:
            from .anti_pattern import AntiPatternSuppressor

            suppressor = AntiPatternSuppressor(
                lookback_days=self._lookback_days,
                suppression_percentile=self.SUPPRESSION_PERCENTILE,
                min_samples=self.MIN_SAMPLES_FOR_CONFIDENCE,
            )
            result = await suppressor.analyze(tracker)
            ctx.suppressed_angles = result.get("angles", [])
            ctx.suppressed_hooks = result.get("hooks", [])
            ctx.suppressed_kicks = result.get("kicks", [])
        except Exception as e:
            log.debug(f"[EDAPE] Anti-pattern 분석 실패: {e}")

    async def _inject_golden_refs(self, tracker, ctx: AdaptiveContext) -> None:
        """골든 레퍼런스 상위 N개를 스니펫으로 변환."""
        try:
            loader = getattr(tracker, "get_golden_references", None)
            if loader is None:
                loader = getattr(tracker, "get_top_golden_references", None)
            if loader is None:
                return

            refs = await _maybe_await(loader(limit=self._max_golden))
            for ref in refs:
                ctx.golden_snippets.append(
                    GoldenSnippet(
                        content=ref.content,
                        angle_type=ref.angle_type,
                        engagement_rate=ref.engagement_rate,
                        category=ref.category,
                    )
                )
        except (AttributeError, TypeError) as e:
            log.debug(f"[EDAPE] 골든 레퍼런스 주입 실패: {e}")

    def _inject_temporal_persona(self, ctx: AdaptiveContext) -> None:
        """시간대별 페르소나 튜닝 힌트 생성."""
        try:
            from .temporal_persona import TemporalPersonaTuner

            tuner = TemporalPersonaTuner()
            ctx.persona_hint = tuner.get_current_hint()
        except Exception as e:
            log.debug(f"[EDAPE] 시간대 페르소나 실패: {e}")
