"""
getdaytrends Core Pipeline Orchestrator
전체 파이프라인 실행 로직: 수집 → 스코어링 → 생성 → 저장
"""

from __future__ import annotations

import dataclasses
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger as log

from shared.llm import get_client

# ── Harness Governance (optional, graceful fallback) ──
try:
    from getdaytrends.harness_integration import (
        get_pipeline_harness,
        governed_step,
        print_harness_summary,
    )

    _HARNESS_AVAILABLE = True
except ImportError:
    _HARNESS_AVAILABLE = False
    get_pipeline_harness = None  # type: ignore
    governed_step = None  # type: ignore
    print_harness_summary = None  # type: ignore

from getdaytrends.alerts import check_and_alert, check_watchlist
from getdaytrends.analysis.scoring import _count_usable_context_sources, _has_usable_source_text
from getdaytrends.analyzer import _analyze_trends_async
from getdaytrends.config import AppConfig
from getdaytrends.db import (
    cleanup_old_records,
    get_connection,
    get_meta,
    get_recent_avg_viral_score,
    get_trend_history_batch,
    init_db,
    save_run,
    set_meta,
    update_run,
)
from getdaytrends.models import RunResult
from getdaytrends.scraper import _async_collect_contexts, _async_collect_trends
from getdaytrends.utils import run_async

_PY314_SERIAL_GENERATION = sys.version_info >= (3, 14)

_PERSONA_AXIS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bio": (
        "bio",
        "biotech",
        "biology",
        "genomics",
        "pharma",
        "drug",
        "clinical",
        "healthcare",
        "바이오",
        "생명과학",
        "유전자",
        "제약",
        "신약",
        "임상",
        "헬스케어",
    ),
    "systems": (
        "system",
        "systems",
        "workflow",
        "pipeline",
        "automation",
        "operations",
        "ops",
        "governance",
        "infrastructure",
        "process",
        "시스템",
        "구조",
        "워크플로",
        "자동화",
        "운영",
        "파이프라인",
        "프로세스",
    ),
    "content_engineering": (
        "content",
        "creator",
        "audience",
        "distribution",
        "media",
        "brand",
        "seo",
        "copy",
        "format",
        "콘텐츠",
        "크리에이터",
        "미디어",
        "브랜딩",
        "배포",
        "유통",
        "에디터",
        "카피",
        "포맷",
        "블로그",
    ),
    "investing": (
        "invest",
        "investment",
        "investor",
        "market",
        "stock",
        "equity",
        "fund",
        "capital",
        "valuation",
        "macro",
        "ipo",
        "trading",
        "투자",
        "주식",
        "증시",
        "금리",
        "밸류",
        "펀드",
        "자본",
        "매크로",
    ),
    "saju": (
        "saju",
        "fortune",
        "astrology",
        "zodiac",
        "tarot",
        "사주",
        "운세",
        "점성",
        "명리",
        "팔자",
        "타로",
    ),
}


def _normalize_axis_name(axis: str) -> str:
    return axis.strip().lower().replace("-", "_").replace(" ", "_")


def _trend_persona_text(trend) -> str:
    parts: list[str] = [
        getattr(trend, "keyword", ""),
        getattr(trend, "category", ""),
        getattr(trend, "top_insight", ""),
        getattr(trend, "why_trending", ""),
        getattr(trend, "best_hook_starter", ""),
    ]
    parts.extend(getattr(trend, "suggested_angles", []) or [])
    context = getattr(trend, "context", None)
    if context:
        parts.append(context.to_combined_text())
    trend_context = getattr(trend, "trend_context", None)
    if trend_context:
        parts.append(trend_context.to_prompt_text())
    return "\n".join(part for part in parts if part).lower()


def _trend_topic_surface_text(trend) -> str:
    parts: list[str] = [
        getattr(trend, "keyword", ""),
        getattr(trend, "corrected_keyword", ""),
        getattr(trend, "category", ""),
    ]
    return "\n".join(part for part in parts if part).lower()


def _matched_persona_axes(trend, axes: list[str]) -> list[str]:
    if not axes:
        return []
    haystack = _trend_persona_text(trend)
    matched: list[str] = []
    for raw_axis in axes:
        axis = _normalize_axis_name(raw_axis)
        keywords = _PERSONA_AXIS_KEYWORDS.get(axis, ())
        if keywords and any(keyword.lower() in haystack for keyword in keywords):
            matched.append(axis)
    return matched


def _matched_hard_drop_keyword(trend, hard_drop_keywords: list[str]) -> str:
    if not hard_drop_keywords:
        return ""
    haystack = _trend_topic_surface_text(trend)
    for keyword in hard_drop_keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized in haystack:
            return normalized
    return ""


def _usable_source_types(context) -> list[str]:
    if not context:
        return []
    source_map = {
        "twitter": getattr(context, "twitter_insight", ""),
        "reddit": getattr(context, "reddit_insight", ""),
        "news": getattr(context, "news_insight", ""),
    }
    return [source_name for source_name, text in source_map.items() if _has_usable_source_text(text)]


def _normalize_source_combo(combo: str) -> frozenset[str]:
    return frozenset(part.strip().lower() for part in combo.split("+") if part.strip())


def _has_required_source_diversity(source_types: list[str], required_combinations: list[str]) -> bool:
    if not required_combinations:
        return True
    source_set = frozenset(source_types)
    normalized_required = [
        combo_set for combo_set in (_normalize_source_combo(combo) for combo in required_combinations) if combo_set
    ]
    return any(combo_set.issubset(source_set) for combo_set in normalized_required)


def _annotate_persona_and_signal(scored_trends: list, config: AppConfig) -> None:
    axes = list(getattr(config, "persona_axes", []) or [])
    min_matches = max(0, int(getattr(config, "persona_min_matches", 1) or 0))
    required_source_combinations = list(getattr(config, "required_source_combinations", []) or [])
    hard_drop_keywords = list(getattr(config, "hard_drop_topic_keywords", []) or [])
    for trend in scored_trends:
        usable_sources = _count_usable_context_sources(getattr(trend, "context", None))
        usable_source_types = _usable_source_types(getattr(trend, "context", None))
        matched_axes = _matched_persona_axes(trend, axes)
        hard_drop_keyword = _matched_hard_drop_keyword(trend, hard_drop_keywords)
        trend.usable_source_count = usable_sources
        trend.usable_source_types = usable_source_types
        trend.matched_axes = matched_axes
        trend.persona_fit = len(matched_axes) >= min_matches if axes else False
        trend.persona_score = min(100, len(matched_axes) * 30 + usable_sources * 10)
        trend.source_diversity_fit = _has_required_source_diversity(
            usable_source_types,
            required_source_combinations,
        )
        trend.hard_drop = bool(hard_drop_keyword)
        trend.hard_drop_reason = f"hard_drop_keyword:{hard_drop_keyword}" if hard_drop_keyword else ""


def _log_filter_result(label: str, before: int, filtered: list, extra: str = "") -> None:
    removed = before - len(filtered)
    if removed:
        suffix = f" {extra}" if extra else ""
        log.info(f"  [{label}] removed={removed} kept={len(filtered)}{suffix}")


def _apply_hard_drop_filter(trends: list, config: AppConfig) -> list:
    if not getattr(config, "enforce_hard_drop_policy", False):
        return trends
    before = len(trends)
    filtered = [trend for trend in trends if not getattr(trend, "hard_drop", False)]
    _log_filter_result("Hard Drop Policy", before, filtered)
    return filtered


def _apply_persona_filter(trends: list, config: AppConfig) -> list:
    if not (getattr(config, "enable_persona_filter", False) and getattr(config, "persona_axes", [])):
        return trends
    before = len(trends)
    filtered = [trend for trend in trends if getattr(trend, "persona_fit", False)]
    _log_filter_result("Persona Filter", before, filtered)
    return filtered


def _apply_min_source_filter(trends: list, config: AppConfig) -> list:
    min_sources = max(0, int(getattr(config, "min_context_sources", 0) or 0))
    if not (getattr(config, "enforce_min_context_sources", False) and min_sources > 0):
        return trends
    before = len(trends)
    filtered = [trend for trend in trends if getattr(trend, "usable_source_count", 0) >= min_sources]
    _log_filter_result("Signal Filter", before, filtered, f"min_sources={min_sources}")
    return filtered


def _apply_source_diversity_filter(trends: list, config: AppConfig) -> list:
    if not getattr(config, "enforce_source_diversity_gate", False):
        return trends
    before = len(trends)
    filtered = [trend for trend in trends if getattr(trend, "source_diversity_fit", False)]
    combos = ",".join(getattr(config, "required_source_combinations", []) or [])
    _log_filter_result("Source Diversity Gate", before, filtered, f"combos={combos}")
    return filtered


def _filter_persona_and_source_fit(trends: list, config: AppConfig) -> list:
    filtered = list(trends)
    filtered = _apply_hard_drop_filter(filtered, config)
    filtered = _apply_persona_filter(filtered, config)
    filtered = _apply_min_source_filter(filtered, config)
    return _apply_source_diversity_filter(filtered, config)


def _apply_source_diversity_restore_floor(trends: list, config: AppConfig, min_score: int) -> list:
    if not getattr(config, "enforce_source_diversity_gate", False):
        return trends
    if not getattr(config, "required_source_combinations", None):
        return trends
    return [
        trend
        for trend in trends
        if getattr(trend, "source_diversity_fit", False)
        or int(getattr(trend, "viral_potential", 0) or 0) < min_score
    ]


def _restore_after_persona_source_gates(safe_trends: list, config: AppConfig, min_score: int, min_count: int) -> list:
    if not getattr(config, "enable_zero_content_prevention", True):
        return []
    fallback_pool = _apply_hard_drop_filter(list(safe_trends), config)
    fallback_pool = _apply_source_diversity_restore_floor(fallback_pool, config, min_score)
    if not fallback_pool:
        return []
    log.warning("  [Zero Content Prevention] persona/source gates removed all candidates; restoring best safe candidate")
    return _zero_content_restore(
        sorted(fallback_pool, key=lambda trend: trend.viral_potential, reverse=True),
        min_score,
        min_count,
    )


def _restore_after_selection_floor(safe_trends: list, config: AppConfig, min_score: int, min_count: int) -> list:
    if not getattr(config, "enable_zero_content_prevention", True):
        return []
    if not safe_trends:
        return []
    log.warning("  [Zero Content Prevention] final score floor removed all candidates; restoring best safe candidate")
    return _zero_content_restore(
        sorted(safe_trends, key=lambda trend: trend.viral_potential, reverse=True),
        min_score,
        min_count,
    )


async def _step_refresh_tap_products(conn, config: AppConfig) -> dict:
    """Refresh TAP snapshots/alert queue after a multi-country run."""

    countries = list(getattr(config, "countries", []) or [])
    if not getattr(config, "enable_tap", True) or len(countries) < 2:
        return {}

    try:
        try:
            from ..tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces
        except ImportError:
            from tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces

        summary = await refresh_tap_market_surfaces(conn, config, snapshot_source="pipeline")
        payload = summary.to_dict()
        if payload["alerts_queued"] and getattr(config, "enable_tap_alert_dispatch", False):
            dispatch_summary = await dispatch_tap_alert_queue(
                conn,
                config,
                limit=max(1, int(getattr(config, "tap_alert_dispatch_batch_size", 5) or 5)),
            )
            payload["dispatch"] = dispatch_summary.to_dict()
        if payload["snapshots_built"]:
            log.info(
                f"  [TAP Refresh] snapshots={payload['snapshots_built']} "
                f"alerts_queued={payload['alerts_queued']} detected={payload['total_detected']}"
            )
        return payload
    except Exception as tap_err:
        log.warning(f"  [TAP Refresh] 실패 (무시): {type(tap_err).__name__}: {tap_err}")
        return {}


# ══════════════════════════════════════════════════════
#  Helper Functions
#  NOTE: _should_skip_qa, _is_accelerating, _batch_from_cache
#        are defined in core/pipeline_steps.py (canonical location).
# ══════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════
#  Pipeline Sub-steps
# ══════════════════════════════════════════════════════


async def _check_budget_and_adjust_limit(config: AppConfig, conn) -> tuple[AppConfig, bool]:
    """
    예산 상한 체크 + 적응형 limit 조정.
    Returns: (pipeline_config, budget_disabled_sonnet)
    """
    budget_disabled = False
    overrides: dict = {}

    # 시간대별 유효 예산 적용
    effective_budget = config.get_effective_budget()
    if effective_budget > 0:
        try:
            from shared.llm.stats import CostTracker

            _tracker = CostTracker(persist=True)
            _today_cost = _tracker.get_today_cost()
            _tracker.close()
            # 동시 실행 시 예산 초과 방지: 90% 도달 시 Sonnet 비활성화
            # (두 프로세스가 동시에 읽을 경우 각각 최대 ~10% 오버런 가능)
            _BUDGET_SAFETY_RATIO = 0.90
            if _today_cost >= effective_budget * _BUDGET_SAFETY_RATIO:
                overrides["enable_long_form"] = False
                overrides["thread_min_score"] = 999
                budget_disabled = True
                print(
                    f"\n  [예산 상한] 오늘 누적 ${_today_cost:.4f} ≥ ${effective_budget * _BUDGET_SAFETY_RATIO:.2f}"
                    f" (일 예산 ${config.daily_budget_usd:.2f}의 90%) → Sonnet 비활성화"
                )
        except (ImportError, ValueError, OSError) as _e:
            log.debug(f"예산 체크 실패 (무시): {type(_e).__name__}: {_e}")

    # 적응형 limit
    prev_avg = await get_recent_avg_viral_score(conn, lookback_hours=3)
    if prev_avg is not None:
        if prev_avg < 60:
            overrides["limit"] = max(5, config.limit // 2)
            print(f"\n  [적응형 limit] 직전 평균 {prev_avg}점 → limit {overrides['limit']}개 (저품질 절약)")
        elif prev_avg >= 80:
            overrides["limit"] = min(15, config.limit + 2)
            print(f"\n  [적응형 limit] 직전 평균 {prev_avg}점 → limit {overrides['limit']}개 (고품질 확장)")

    pipeline_config = dataclasses.replace(config, **overrides) if overrides else config
    return pipeline_config, budget_disabled


def _needs_deep_context(raw_trends: list, contexts: dict, min_context_len: int = 100) -> list:
    return [
        trend
        for trend in raw_trends
        if not contexts.get(trend.name) or len(contexts[trend.name].to_combined_text().strip()) < min_context_len
    ]


def _merge_deep_contexts(contexts: dict, deep_contexts: dict) -> None:
    for name, deep_ctx in deep_contexts.items():
        base = contexts.get(name)
        if not base:
            contexts[name] = deep_ctx
            continue
        if deep_ctx.twitter_insight and len(deep_ctx.twitter_insight) > len(base.twitter_insight):
            base.twitter_insight = deep_ctx.twitter_insight
        if deep_ctx.reddit_insight and len(deep_ctx.reddit_insight) > len(base.reddit_insight):
            base.reddit_insight = deep_ctx.reddit_insight
        if deep_ctx.news_insight and len(deep_ctx.news_insight) > len(base.news_insight):
            base.news_insight = deep_ctx.news_insight


async def _collect_deep_contexts_if_needed(raw_trends: list, contexts: dict, config: AppConfig, conn) -> None:
    if not raw_trends:
        return
    needs_deep = _needs_deep_context(raw_trends, contexts)
    if not needs_deep:
        log.info(f"  [Deep Research] all {len(raw_trends)} trend contexts are sufficient; skipping recursive collection")
        return
    print(f"  recursive context collection needed ({len(needs_deep)}/{len(raw_trends)} trends)...")
    try:
        deep_contexts = await _async_collect_contexts(needs_deep, config, conn=conn)
    except Exception as exc:
        log.warning(f"  [Recursive Context Failure] collect_contexts exception: {type(exc).__name__}: {exc}")
        return
    _merge_deep_contexts(contexts, deep_contexts)


def _warn_missing_context(raw_trends: list, contexts: dict, config: AppConfig) -> None:
    if not (raw_trends and getattr(config, "require_context", True)):
        return
    empty_ctx = [
        trend.name
        for trend in raw_trends
        if not contexts.get(trend.name) or not contexts[trend.name].to_combined_text().strip()
    ]
    if empty_ctx:
        log.warning(f"  [Context Missing] {len(empty_ctx)} trend contexts are empty: {', '.join(empty_ctx[:3])}")


async def _step_collect(config: AppConfig, conn, run: RunResult) -> tuple:
    """Collect raw trends and fill missing/weak context without failing the whole run."""
    print("\n[1/4] collecting metadata trends...")
    try:
        raw_trends, contexts = await _async_collect_trends(config, conn)
    except Exception as exc:
        log.error(f"  [Collect Failure] collect_trends exception: {type(exc).__name__}: {exc}")
        run.errors.append(f"collect_trends 예외: {type(exc).__name__}: {exc}")
        return [], {}
    run.trends_collected = len(raw_trends)
    print(f"  collection complete: {len(raw_trends)} trends")
    await _collect_deep_contexts_if_needed(raw_trends, contexts, config, conn)
    _warn_missing_context(raw_trends, contexts, config)
    return raw_trends, contexts

def _zero_content_restore(candidates: list, min_score: int, min_count: int) -> list:
    """모든 트렌드가 필터링된 경우 ZCP 3단계로 최소 복원."""
    for threshold, label in [
        (min_score, f"바이럴≥{min_score}"),
        (int(min_score * 0.6), f"기준 완화→{int(min_score * 0.6)}점"),
    ]:
        restored = [t for t in candidates if t.viral_potential >= threshold]
        if restored:
            result = restored[: min_count or 1]
            log.warning(f"  [Zero Content Prevention] 모든 트렌드 제외됨 → {len(result)}개 복원 ({label})")
            return result
    if candidates:
        log.warning(
            f"  [Zero Content Prevention Step 3] 점수 무관 1개 복원: '{candidates[0].keyword}' ({candidates[0].viral_potential}점)"
        )
        return candidates[:1]
    return []


def _filter_sentiment_safe_trends(scored_trends: list, config: AppConfig) -> list:
    if not config.enable_sentiment_filter:
        return list(scored_trends)
    return [trend for trend in scored_trends if not getattr(trend, "safety_flag", False)]


def _filter_publishable_trends(trends: list) -> tuple[list, int]:
    before = len(trends)
    return [trend for trend in trends if getattr(trend, "publishable", True)], before


def _log_publishability_filter(before: int, filtered: list) -> None:
    removed = before - len(filtered)
    if removed:
        log.warning(f"  [Publishability Filter] removed={removed}")


def _filter_excluded_categories(trends: list, config: AppConfig) -> tuple[list, list]:
    excluded_cats = set(getattr(config, "exclude_categories", []))
    candidates_before_exclusion = list(trends)
    if not excluded_cats:
        return trends, candidates_before_exclusion

    before = len(trends)
    filtered = [
        trend for trend in trends if (getattr(trend, "category", "기타") or "기타") not in excluded_cats
    ]
    removed = before - len(filtered)
    if removed:
        log.info(f"  [Category Exclusion] removed={removed} ({', '.join(excluded_cats)})")
    return filtered, candidates_before_exclusion


def _zero_content_candidates(trends: list, config: AppConfig) -> list:
    return sorted(
        _filter_sentiment_safe_trends(trends, config),
        key=lambda trend: trend.viral_potential,
        reverse=True,
    )


def _filter_unsafe_trends(scored_trends: list, config: AppConfig, min_score: int, min_count: int) -> list:
    """Apply safety/publishability/category filters with zero-content recovery."""
    publishable, before_publishable = _filter_publishable_trends(_filter_sentiment_safe_trends(scored_trends, config))
    _log_publishability_filter(before_publishable, publishable)
    safe, all_before_exclusion = _filter_excluded_categories(publishable, config)
    if safe or not getattr(config, "enable_zero_content_prevention", True):
        return safe
    return _zero_content_restore(_zero_content_candidates(all_before_exclusion, config), min_score, min_count)

def _assign_freshness_grades(trends: list, config: AppConfig) -> None:
    """최신성 등급 부여 + 패널티 인플레이스 적용."""
    _FRESHNESS_GRADES = [(0, 6, "fresh"), (6, 12, "recent"), (12, 24, "stale"), (24, float("inf"), "expired")]
    penalty_map = {
        "fresh": 1.0,
        "recent": 1.0,
        "stale": getattr(config, "freshness_penalty_stale", 0.85),
        "expired": getattr(config, "freshness_penalty_expired", 0.7),
        "unknown": 0.95,
    }
    for t in trends:
        age = getattr(t, "content_age_hours", 0.0)
        grade = next((g for lo, hi, g in _FRESHNESS_GRADES if lo <= age < hi), "unknown")
        t.freshness_grade = grade
        mult = penalty_map.get(grade, 0.95)
        if mult < 1.0:
            original = t.viral_potential
            t.viral_potential = int(t.viral_potential * mult)
            log.debug(
                f"  [최신성 패널티] '{t.keyword}' {grade} ({age:.1f}h) ×{mult} → {original}→{t.viral_potential}점"
            )


def _select_diverse_trends(safe_trends: list, min_score: int, max_same: int, min_count: int) -> list:
    """Select high-scoring trends while limiting category concentration."""
    cat_best = _trends_by_category(safe_trends)
    selected: list = []
    selected_set: set = set()
    cat_count: dict[str, int] = {}

    _select_category_leaders(cat_best, selected, selected_set, cat_count, min_score)
    _fill_slots(safe_trends, selected, selected_set, cat_count, min_score, max_same)
    if len(selected) < min_count:
        _ensure_min_count(safe_trends, selected, selected_set, cat_count, min_score, min_count, max_same)
    return selected


def _trends_by_category(safe_trends: list) -> dict[str, list]:
    cat_best: dict[str, list] = {}
    for trend in safe_trends:
        cat_best.setdefault(_trend_category(trend), []).append(trend)
    for category_trends in cat_best.values():
        category_trends.sort(key=lambda item: item.viral_potential, reverse=True)
    return cat_best


def _trend_category(trend) -> str:
    return getattr(trend, "category", "기타") or "기타"


def _select_category_leaders(
    cat_best: dict[str, list],
    selected: list,
    selected_set: set,
    cat_count: dict[str, int],
    min_score: int,
) -> None:
    for category in _categories_by_top_score(cat_best):
        best = cat_best[category][0] if cat_best[category] else None
        if best and best.viral_potential >= min_score and id(best) not in selected_set:
            selected.append(best)
            selected_set.add(id(best))
            cat_count[category] = cat_count.get(category, 0) + 1
    log.debug(f"  [Diversity Pass1] category leaders: {len(selected)} from {len(cat_best)} categories")


def _categories_by_top_score(cat_best: dict[str, list]) -> list[str]:
    return sorted(
        cat_best,
        key=lambda category: cat_best[category][0].viral_potential if cat_best[category] else 0,
        reverse=True,
    )


def _fill_slots(pool: list, selected: list, selected_set: set, cat_count: dict, min_score: int, max_same: int) -> None:
    """Pass 2: 점수 순으로 남은 슬롯을 채움 (카테고리 상한 max_same 준수)."""
    for t in sorted([t for t in pool if id(t) not in selected_set], key=lambda x: x.viral_potential, reverse=True):
        if t.viral_potential < min_score:
            break
        cat = getattr(t, "category", "기타") or "기타"
        if cat_count.get(cat, 0) >= max_same:
            log.debug(f"  [다양성] '{t.keyword}' ({cat}) 스킵 — 카테고리 상한 {max_same}개 도달")
            continue
        selected.append(t)
        selected_set.add(id(t))
        cat_count[cat] = cat_count.get(cat, 0) + 1


def _ensure_min_count(
    pool: list,
    selected: list,
    selected_set: set,
    cat_count: dict,
    min_score: int,
    min_count: int,
    max_same: int,
) -> None:
    """Pass 3: floor_score로 기준 완화하여 최소 기사 수 보장."""
    floor_score = int(min_score * 0.75)
    log.info(f"  [최소 기사] {len(selected)}개 < {min_count}개 → 기준 {min_score}점 → {floor_score}점 하향")
    for t in sorted([t for t in pool if id(t) not in selected_set], key=lambda x: x.viral_potential, reverse=True):
        if len(selected) >= min_count or t.viral_potential < floor_score:
            break
        cat = getattr(t, "category", "기타") or "기타"
        if cat_count.get(cat, 0) >= max_same + 1:
            continue
        selected.append(t)
        selected_set.add(id(t))
        cat_count[cat] = cat_count.get(cat, 0) + 1
        log.debug(f"  [최소 기사 보충] '{t.keyword}' ({t.viral_potential}점, {cat}) 추가")
    if len(selected) < min_count:
        log.warning(f"  [최소 기사] floor({floor_score}점) 후에도 {len(selected)}/{min_count}개 → 가용 트렌드 부족")


def _ensure_quality_and_diversity(scored_trends: list, config: AppConfig) -> list:
    """[v6.0] 카테고리 다양성 + 최소 기사 수 보장 (3-pass 선택 알고리즘)."""
    min_score = config.min_viral_score
    min_count = getattr(config, "min_article_count", 3)
    max_same = getattr(config, "max_same_category", 2)

    _annotate_persona_and_signal(scored_trends, config)
    safe_trends = _filter_unsafe_trends(scored_trends, config, min_score, min_count)
    if not safe_trends:
        return []

    filtered_trends = _filter_persona_and_source_fit(safe_trends, config)
    if not filtered_trends:
        filtered_trends = _restore_after_persona_source_gates(safe_trends, config, min_score, min_count)
    if not filtered_trends:
        return []
    safe_trends = filtered_trends

    _assign_freshness_grades(safe_trends, config)
    min_count = min(min_count, len(safe_trends))
    selected = _select_diverse_trends(safe_trends, min_score, max_same, min_count)
    if not selected:
        selected = _restore_after_selection_floor(safe_trends, config, min_score, min_count)
    selected.sort(key=lambda x: x.viral_potential, reverse=True)
    return selected


async def _step_genealogy(quality_trends: list, config: AppConfig) -> list:
    """Trend Genealogy 분석 — 실패 시 원본 리스트 반환."""
    try:
        try:
            from ..analyzer import analyze_trend_genealogy, enrich_trends_with_genealogy
            from ..performance_tracker import PerformanceTracker
        except ImportError:
            from analyzer import analyze_trend_genealogy, enrich_trends_with_genealogy
            from performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(
            db_path=config.db_path,
            database_url=config.database_url,
            allow_sqlite_fallback=config.allow_sqlite_fallback,
        )
        history = await tracker.get_trend_history(
            keyword="",
            hours=getattr(config, "genealogy_history_hours", 72),
        )
        genealogy = await analyze_trend_genealogy(quality_trends, history, get_client(), config)
        if not genealogy:
            return quality_trends
        quality_trends = enrich_trends_with_genealogy(quality_trends, genealogy)
        min_conf = getattr(config, "genealogy_min_confidence", 0.5)
        for g in genealogy:
            if g.get("confidence", 0) >= min_conf:
                await tracker.save_trend_genealogy(
                    keyword=g["keyword"],
                    parent_keyword=g.get("parent_keyword", ""),
                    predicted_children=g.get("predicted_children", []),
                    viral_score=next((t.viral_potential for t in quality_trends if t.keyword == g["keyword"]), 0),
                )
        log.info(f"  [Genealogy] 계보 저장 완료 ({len(genealogy)}개)")
    except Exception as _e:
        log.warning(f"  [Genealogy] 건너뜀: {type(_e).__name__}: {_e}")
    return quality_trends


async def _step_canva_visuals(quality_trends: list, batch_results: list, config: AppConfig) -> None:
    """Canva 비주얼 자동 생성 — 실패 시 무시."""
    try:
        from canva import generate_visual_assets

        min_score = getattr(config, "canva_min_score", 90)
        count = 0
        for trend, batch in zip(quality_trends, batch_results, strict=False):
            if trend.viral_potential >= min_score:
                visual_urls = await generate_visual_assets(trend, config)
                if visual_urls:
                    batch.visual_urls = visual_urls
                    count += 1
        if count:
            log.info(f"  [Canva] {count}개 트렌드 비주얼 생성 완료")
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as _e:
        log.debug(f"  [Canva] 비주얼 생성 실패 (무시): {type(_e).__name__}: {_e}")


async def _step_reasoning(quality_trends: list, config: AppConfig, conn, run: RunResult) -> None:
    """Cross-Trend Inductive Reasoning — 실패 시 무시."""
    try:
        try:
            from ..trend_reasoning import TrendReasoningAdapter
        except ImportError:
            from trend_reasoning import TrendReasoningAdapter

        reasoner = TrendReasoningAdapter()
        if not (reasoner.is_available() and quality_trends):
            return
        trend_data_text = "\n".join(
            f"[{t.keyword}] viral={t.viral_potential} | "
            f"category={getattr(t, 'category', '기타')} | "
            f"why={getattr(t, 'why_trending', '')} | "
            f"insight={getattr(t, 'top_insight', '')}"
            for t in quality_trends
        )
        result = await reasoner.run_full_reasoning(
            conn=conn,
            run_id=run.run_id[:8],
            category=config.country,
            trend_data=trend_data_text,
        )
        patterns = result.get("new_patterns", [])
        print(
            f"\n  🧠 Trend Reasoning: {len(result.get('facts', []))} facts → "
            f"{len(result.get('hypotheses', []))} hyp → {result.get('survived_count', 0)} survived"
        )
        for p in patterns[:3]:
            print(f"     → {p[:70]}...")
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as _e:
        log.debug(f"  [Reasoning] 추론 실패 (무시): {type(_e).__name__}: {_e}")


async def _refresh_performance_artifacts(pipeline_config: AppConfig) -> None:
    if pipeline_config.dry_run:
        log.debug("  Performance refresh skipped in dry-run mode")
        return
    if not (
        getattr(pipeline_config, "enable_tiered_collection", False)
        or getattr(pipeline_config, "enable_golden_reference_qa", False)
    ):
        return
    try:
        try:
            from ..performance_tracker import PerformanceTracker
        except ImportError:
            from performance_tracker import PerformanceTracker

        pt = PerformanceTracker(
            db_path=pipeline_config.db_path,
            bearer_token=pipeline_config.twitter_bearer_token,
            database_url=pipeline_config.database_url,
            allow_sqlite_fallback=pipeline_config.allow_sqlite_fallback,
        )
        if getattr(pipeline_config, "enable_tiered_collection", False):
            log.info(f"  [Tiered Collection] {await pt.run_tiered_collection()}")
        if getattr(pipeline_config, "enable_golden_reference_qa", False):
            count = await pt.auto_update_golden_references(
                days=getattr(pipeline_config, "golden_reference_auto_update_days", 7)
            )
            log.info(f"  [Golden Ref] auto update: {count}")
    except Exception as _e:
        log.debug(f"  Performance refresh failed (ignored): {type(_e).__name__}: {_e}")


def _log_structured_pipeline_metrics(pipeline_config: AppConfig, run: RunResult, elapsed: float) -> float:
    total_cost = 0.0
    if not pipeline_config.enable_structured_metrics:
        return total_cost
    try:
        from shared.llm.stats import CostTracker

        tracker = CostTracker(persist=True)
        total_cost = tracker.get_today_cost()
        tracker.close()
    except (ImportError, ValueError, KeyError, OSError):
        pass
    log.info(
        f"pipeline_metrics | run_id={run.run_id[:8]} country={run.country} "
        f"collected={run.trends_collected} scored={run.trends_scored} "
        f"generated={run.tweets_generated} saved={run.tweets_saved} "
        f"errors={len(run.errors)} cost_usd={total_cost:.4f} duration_s={elapsed:.1f}"
    )
    return total_cost


def _send_cost_alerts(pipeline_config: AppConfig) -> None:
    try:
        try:
            from ..alerts import send_daily_cost_alert
        except ImportError:
            from alerts import send_daily_cost_alert

        send_daily_cost_alert(pipeline_config)
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError):
        pass


def _send_pipeline_heartbeat(pipeline_config: AppConfig, run: RunResult, elapsed: float, total_cost: float) -> None:
    try:
        from shared.notifications import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send_heartbeat(
                "GetDayTrends",
                status="alive",
                details=(
                    f"collected={run.trends_collected} scored={run.trends_scored} "
                    f"generated={run.tweets_generated} saved={run.tweets_saved} elapsed={elapsed:.0f}s"
                ),
            )
            if total_cost > 0:
                notifier.send_cost_alert(total_cost, getattr(pipeline_config, "daily_budget_usd", 2.0))
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as _e:
        log.debug(f"Heartbeat send failed (ignored): {type(_e).__name__}: {_e}")


async def _maybe_retrain_prediction_model() -> None:
    try:
        from shared.prediction.retrain import maybe_retrain

        retrain_result = await maybe_retrain()
        if retrain_result.get("retrained"):
            log.info(f"  [PEE] model retrain complete: R2={retrain_result['metrics']['r2']:.4f}")
    except (ImportError, RuntimeError, ValueError, OSError):
        pass


async def _step_post_run(
    pipeline_config: AppConfig,
    run: RunResult,
    elapsed: float,
    scored_trends: list,
    orig_config: AppConfig,
    schedule_callback,
    separator: str,
) -> None:
    """파이프라인 완료 후 후처리: 성과 갱신, 메트릭 로깅, 스케줄링, Heartbeat."""
    """파이프라인 완료 후 후처리: 성과 갱신, 메트릭 로깅, 스케줄링, Heartbeat."""
    await _refresh_performance_artifacts(pipeline_config)
    total_cost = _log_structured_pipeline_metrics(pipeline_config, run, elapsed)
    await _adjust_schedule(scored_trends, orig_config, schedule_callback)
    _send_cost_alerts(pipeline_config)
    print(separator)
    _send_pipeline_heartbeat(pipeline_config, run, elapsed, total_cost)
    await _maybe_retrain_prediction_model()


def _category_distribution(quality_trends: list) -> dict[str, int]:
    cat_dist: dict[str, int] = {}
    for trend in quality_trends:
        category = getattr(trend, "category", "기타") or "기타"
        cat_dist[category] = cat_dist.get(category, 0) + 1
    return cat_dist


def _print_category_distribution(cat_dist: dict[str, int]) -> None:
    if cat_dist:
        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(cat_dist.items(), key=lambda x: -x[1]))
        print(f"  category distribution: {dist_str}")


async def _trend_history_for_preview(config: AppConfig, conn, scored_trends: list) -> dict:
    if not config.verbose:
        return {}
    return await get_trend_history_batch(conn, [st.keyword for st in scored_trends])


def _print_score_preview(scored_trends: list, quality_trends: list, history_map: dict, verbose: bool) -> None:
    for st in scored_trends:
        marker = " ✓" if st in quality_trends else " ✗"
        score_bar = "█" * (st.viral_potential // 10) + "░" * (10 - st.viral_potential // 10)
        print(f"  #{st.rank} [{score_bar}] {st.viral_potential:3d} | {st.keyword}{marker}")
        if verbose:
            history = history_map.get(st.keyword, [])
            if history:
                avg = round(sum(h["viral_potential"] for h in history) / len(history), 1)
                print(f"       history: {len(history)} records, avg {avg}")


def _run_watchlist_alerts(scored_trends: list, config: AppConfig) -> None:
    if not config.watchlist_keywords:
        return
    wl_count = check_watchlist(scored_trends, config)
    if wl_count:
        print(f"\n  [WATCHLIST] matched keywords: {wl_count}")


def _send_score_alerts(scored_trends: list, config: AppConfig, run: RunResult) -> None:
    if config.no_alerts:
        return
    alerts_sent = check_and_alert(scored_trends, config)
    run.alerts_sent = alerts_sent
    if alerts_sent:
        print(f"\n  alerts sent: {alerts_sent}")


async def _step_score_and_alert(raw_trends, contexts, config: AppConfig, conn, run: RunResult) -> tuple:
    """Step 2-3: 바이럴 스코어링 + 품질 필터 + 알림."""
    print("\n[2/4] 바이럴 스코어링 중 (병렬)...")
    scored_trends = await _analyze_trends_async(raw_trends, contexts, config, conn=conn)
    run.trends_scored = len(scored_trends)

    quality_trends = _ensure_quality_and_diversity(scored_trends, config)
    filtered_count = len(scored_trends) - len(quality_trends)
    if filtered_count:
        print(f"\n  quality filter excluded: {filtered_count}")

    run.category_distribution = _category_distribution(quality_trends)
    _print_category_distribution(run.category_distribution)

    history_map = await _trend_history_for_preview(config, conn, scored_trends)
    _print_score_preview(scored_trends, quality_trends, history_map, config.verbose)
    _run_watchlist_alerts(scored_trends, config)
    _send_score_alerts(scored_trends, config, run)
    return scored_trends, quality_trends

# -- step functions import --
try:
    from .pipeline_steps import (  # noqa: E402
        _adjust_schedule,
        _step_generate,
        _step_save,
    )
except ImportError:
    from core.pipeline_steps import (  # noqa: E402
        _adjust_schedule,
        _step_generate,
        _step_save,
    )

#  Pipeline Orchestrator
# ══════════════════════════════════════════════════════


def _pipeline_harness(config: AppConfig) -> object:
    if not (_HARNESS_AVAILABLE and get_pipeline_harness is not None):
        return None
    harness = get_pipeline_harness(config)
    if harness:
        effective_budget = getattr(config, "daily_budget_usd", 2.0)
        log.info(f"[Harness] Pipeline governance active - budget=${effective_budget:.2f}")
    return harness


async def _open_pipeline_run(config: AppConfig) -> tuple[Any, RunResult, int]:
    conn = await get_connection(
        config.db_path,
        database_url=config.database_url,
        allow_sqlite_fallback=config.dry_run or config.allow_sqlite_fallback,
    )
    await init_db(conn)
    run = RunResult(run_id=str(uuid.uuid4()), country=config.country)
    run.started_at = datetime.now()
    run_row_id = await save_run(conn, run)
    return conn, run, run_row_id


def _print_pipeline_start(separator: str) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{separator}")
    print(f"  작업 시작: {now_str}")
    print(separator)


async def _run_pipeline_step(name: str, func, *args, harness=None, governed_kwargs: dict | None = None, **kwargs) -> object:
    if harness and governed_step:
        return await governed_step(name, func, *args, harness=harness, **(governed_kwargs or {}), **kwargs)
    return await func(*args, **kwargs)


async def _finalize_empty_pipeline(conn, run: RunResult, run_row_id: int) -> RunResult:
    run.errors.append("트렌드 수집 실패")
    run.finished_at = datetime.now()
    await update_run(conn, run, run_row_id)
    return run


def _print_pipeline_completion(separator: str, success_count: int, quality_trends: list, elapsed: float) -> None:
    print(f"\n{separator}")
    print(f"  완료: {success_count}/{len(quality_trends)} saved")
    print(f"  소요: {elapsed:.1f}s")


def _notify_pipeline_error(error: Exception) -> None:
    try:
        from shared.notifications import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send_error(f"Pipeline failed: {error}", error=error, source="GetDayTrends")
    except Exception:
        pass


async def async_run_pipeline(config: AppConfig, schedule_callback: Callable[..., Any] | None = None) -> RunResult:
    """전체 파이프라인: 수집 -> 스코어링 -> 생성 -> 저장."""
    harness = _pipeline_harness(config)
    conn = None
    try:
        conn, run, run_row_id = await _open_pipeline_run(config)
        separator = "=" * 55
        _print_pipeline_start(separator)

        pipeline_config, _budget_disabled = await _check_budget_and_adjust_limit(config, conn)

        t0 = time.time()
        raw_trends, contexts = await _run_pipeline_step(
            "collect_trends", _step_collect, pipeline_config, conn, run, harness=harness
        )
        t1 = time.time()
        log.info(f"  [timing] collect: {t1 - t0:.1f}s")
        if not raw_trends:
            return await _finalize_empty_pipeline(conn, run, run_row_id)

        scored_trends, quality_trends = await _run_pipeline_step(
            "score_trends", _step_score_and_alert, raw_trends, contexts, pipeline_config, conn, run, harness=harness
        )
        t2 = time.time()
        log.info(f"  [timing] score+alert: {t2 - t1:.1f}s")

        if getattr(pipeline_config, "enable_trend_genealogy", False) and quality_trends:
            quality_trends = await _step_genealogy(quality_trends, pipeline_config)

        batch_results = await _run_pipeline_step(
            "generate_content",
            _step_generate,
            quality_trends,
            pipeline_config,
            conn,
            harness=harness,
            governed_kwargs={"cost_estimate": 0.01 * len(quality_trends)},
        )
        t3 = time.time()
        log.info(f"  [timing] generate: {t3 - t2:.1f}s")

        if getattr(pipeline_config, "enable_canva_visuals", False) and pipeline_config.canva_api_key:
            await _step_canva_visuals(quality_trends, batch_results, pipeline_config)
        await _step_reasoning(quality_trends, pipeline_config, conn, run)

        success_count = await _run_pipeline_step(
            "save_results", _step_save, quality_trends, batch_results, pipeline_config, conn, run, run_row_id, harness=harness
        )
        t4 = time.time()
        log.info(f"  [timing] save: {t4 - t3:.1f}s")

        await _step_refresh_tap_products(conn, pipeline_config)
        run.finished_at = datetime.now()
        await update_run(conn, run, run_row_id)

        elapsed = (run.finished_at - run.started_at).total_seconds()
        _print_pipeline_completion(separator, success_count, quality_trends, elapsed)
        await _step_post_run(pipeline_config, run, elapsed, scored_trends, config, schedule_callback, separator)
        if harness and print_harness_summary:
            print_harness_summary(harness)
        return run
    except Exception as pipeline_err:
        _notify_pipeline_error(pipeline_err)
        raise
    finally:
        if conn is not None:
            await conn.close()

def run_pipeline(config: AppConfig, schedule_callback: Callable[..., Any] | None = None) -> RunResult:
    """동기 래퍼 (schedule 호환). 내부적으로 비동기 파이프라인 실행."""
    return run_async(async_run_pipeline(config, schedule_callback))


# ══════════════════════════════════════════════════════
#  Cleanup & Maintenance
# ══════════════════════════════════════════════════════


async def maybe_cleanup(conn, days: int = 90) -> None:
    """마지막 정리 후 7일 이상 경과했을 때만 cleanup_old_records 실행."""
    last = await get_meta(conn, "last_cleanup")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).days
        if elapsed < 7:
            return
    count = await cleanup_old_records(conn, days=days)
    await set_meta(conn, "last_cleanup", datetime.now().isoformat())
    if count:
        log.info(f"자동 DB 정리: {count}개 레코드 삭제 ({days}일 초과)")


async def maybe_send_weekly_cost_report(conn, config) -> None:
    """마지막 주간 비용 리포트 전송 후 7일 이상 경과했을 때만 전송."""
    if not (config.telegram_bot_token and config.telegram_chat_id):
        return
    last = await get_meta(conn, "last_weekly_cost_report")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).days
        if elapsed < 7:
            return
    try:
        from ..alerts import send_weekly_cost_report
    except ImportError:
        from alerts import send_weekly_cost_report

    if send_weekly_cost_report(config):
        await set_meta(conn, "last_weekly_cost_report", datetime.now().isoformat())
