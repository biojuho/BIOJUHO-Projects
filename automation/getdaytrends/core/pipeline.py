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

try:
    from ..alerts import check_and_alert, check_watchlist
    from ..analyzer import analyze_trends
    from ..config import AppConfig
    from ..db import (
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
    from ..models import RunResult
    from ..scraper import collect_contexts, collect_trends
    from ..utils import run_async
except ImportError:
    from alerts import check_and_alert, check_watchlist
    from analyzer import analyze_trends
    from config import AppConfig
    from db import (
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
    from models import RunResult
    from scraper import collect_contexts, collect_trends
    from utils import run_async

_PY314_SERIAL_GENERATION = sys.version_info >= (3, 14)

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
            from shared.llm.stats import _DB_PATH as _llm_db
            from shared.llm.stats import CostTracker

            if _llm_db.exists():
                _tracker = CostTracker(persist=True)
                _daily = _tracker.get_daily_stats(1)
                _tracker.close()
                from datetime import date as _date

                _today = str(_date.today())
                _today_cost = sum(r["cost_usd"] for r in _daily if r.get("date") == _today)
                if _today_cost >= effective_budget:
                    overrides["enable_long_form"] = False
                    overrides["thread_min_score"] = 999
                    budget_disabled = True
                    print(
                        f"\n  [예산 상한] 오늘 누적 ${_today_cost:.4f} ≥ ${config.daily_budget_usd:.2f} → Sonnet 비활성화"
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


def _step_collect(config: AppConfig, conn, run: RunResult) -> tuple:
    """Step 1: 멀티소스 트렌드 수집 + 심층 컨텍스트 조건부 수집."""
    print("\n[1/4] 멀티소스 트렌드 수집 중...")
    raw_trends, contexts = collect_trends(config, conn)
    run.trends_collected = len(raw_trends)
    print(f"  수집 완료: {len(raw_trends)}개 트렌드")

    # 심층 컨텍스트 조건부 수집
    if raw_trends:
        _MIN_CTX_LEN = 100
        needs_deep = [
            t
            for t in raw_trends
            if not contexts.get(t.name) or len(contexts[t.name].to_combined_text().strip()) < _MIN_CTX_LEN
        ]

        if needs_deep:
            print(f"  심층 컨텍스트 수집 중 ({len(needs_deep)}/{len(raw_trends)}개 부족)...")
            deep_contexts = collect_contexts(needs_deep, config, conn)
            for name, deep_ctx in deep_contexts.items():
                base = contexts.get(name)
                if base:
                    if deep_ctx.twitter_insight and len(deep_ctx.twitter_insight) > len(base.twitter_insight):
                        base.twitter_insight = deep_ctx.twitter_insight
                    if deep_ctx.reddit_insight and len(deep_ctx.reddit_insight) > len(base.reddit_insight):
                        base.reddit_insight = deep_ctx.reddit_insight
                    if deep_ctx.news_insight and len(deep_ctx.news_insight) > len(base.news_insight):
                        base.news_insight = deep_ctx.news_insight
                else:
                    contexts[name] = deep_ctx
        else:
            log.info(f"  [Deep Research] 전체 {len(raw_trends)}개 컨텍스트 충분 → 재수집 스킵")

        # 컨텍스트 필수화 경고
        if getattr(config, "require_context", True):
            empty_ctx = [
                t.name
                for t in raw_trends
                if not contexts.get(t.name) or not contexts[t.name].to_combined_text().strip()
            ]
            if empty_ctx:
                log.warning(
                    f"  [컨텍스트 부족] {len(empty_ctx)}개 트렌드 컨텍스트 비어있음: {', '.join(empty_ctx[:3])}"
                )

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


def _filter_unsafe_trends(scored_trends: list, config: AppConfig, min_score: int, min_count: int) -> list:
    """안전/게시가능/카테고리 필터 적용 + Zero Content Prevention."""
    safe = [t for t in scored_trends if not (config.enable_sentiment_filter and getattr(t, "safety_flag", False))]

    before_pub = len(safe)
    safe = [t for t in safe if getattr(t, "publishable", True)]
    if before_pub - len(safe):
        log.warning(f"  [게시불가 필터] {before_pub - len(safe)}개 제거 (의미 없는 키워드/문장 조각)")

    excluded_cats = set(getattr(config, "exclude_categories", []))
    all_before_exclusion = list(safe)
    if excluded_cats:
        before = len(safe)
        safe = [t for t in safe if (getattr(t, "category", "기타") or "기타") not in excluded_cats]
        if before - len(safe):
            log.info(f"  [카테고리 제외] {before - len(safe)}개 제거 ({', '.join(excluded_cats)})")

    if safe or not getattr(config, "enable_zero_content_prevention", True):
        return safe

    safe_candidates = sorted(
        [t for t in all_before_exclusion if not (config.enable_sentiment_filter and getattr(t, "safety_flag", False))],
        key=lambda x: x.viral_potential,
        reverse=True,
    )
    return _zero_content_restore(safe_candidates, min_score, min_count)


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
    """3-pass 다양성 선택: 카테고리 시드 → 잔여 채우기 → 최소 수 보장."""
    cat_best: dict[str, list] = {}
    for t in safe_trends:
        cat_best.setdefault(getattr(t, "category", "기타") or "기타", []).append(t)
    for cats in cat_best.values():
        cats.sort(key=lambda x: x.viral_potential, reverse=True)

    selected: list = []
    selected_set: set = set()
    cat_count: dict[str, int] = {}

    # Pass 1: 카테고리별 최고 점수 1개
    for cat in sorted(cat_best, key=lambda c: cat_best[c][0].viral_potential if cat_best[c] else 0, reverse=True):
        best = cat_best[cat][0] if cat_best[cat] else None
        if best and best.viral_potential >= min_score and id(best) not in selected_set:
            selected.append(best)
            selected_set.add(id(best))
            cat_count[cat] = cat_count.get(cat, 0) + 1
    log.debug(f"  [다양성 Pass1] 카테고리별 시드: {len(selected)}개 ({len(cat_best)}개 카테고리)")

    # Pass 2: 남은 슬롯 채우기 (score 순, 카테고리 상한 준수)
    _fill_slots(safe_trends, selected, selected_set, cat_count, min_score, max_same)

    # Pass 3: 최소 기사 수 보장 (floor_score로 기준 완화)
    if len(selected) < min_count:
        _ensure_min_count(safe_trends, selected, selected_set, cat_count, min_score, min_count, max_same)

    return selected


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

    safe_trends = _filter_unsafe_trends(scored_trends, config, min_score, min_count)
    if not safe_trends:
        return []

    _assign_freshness_grades(safe_trends, config)
    min_count = min(min_count, len(safe_trends))
    selected = _select_diverse_trends(safe_trends, min_score, max_same, min_count)
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

        tracker = PerformanceTracker(db_path=config.db_path)
        history = tracker.get_trend_history(keyword="", hours=getattr(config, "genealogy_history_hours", 72))
        genealogy = await analyze_trend_genealogy(quality_trends, history, get_client(), config)
        if not genealogy:
            return quality_trends
        quality_trends = enrich_trends_with_genealogy(quality_trends, genealogy)
        min_conf = getattr(config, "genealogy_min_confidence", 0.5)
        for g in genealogy:
            if g.get("confidence", 0) >= min_conf:
                tracker.save_trend_genealogy(
                    keyword=g["keyword"],
                    parent_keyword=g.get("parent_keyword", ""),
                    predicted_children=g.get("predicted_children", []),
                    viral_score=next((t.viral_potential for t in quality_trends if t.keyword == g["keyword"]), 0),
                )
        log.info(f"  [Genealogy] 계보 저장 완료 ({len(genealogy)}개)")
    except (ImportError, RuntimeError, ValueError) as _e:
        log.debug(f"  [Genealogy] 분석 실패 (무시): {type(_e).__name__}: {_e}")
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
    # 3단계 수집 + 골든 레퍼런스 자동 갱신
    if getattr(pipeline_config, "enable_tiered_collection", False) or getattr(
        pipeline_config, "enable_golden_reference_qa", False
    ):
        try:
            try:
                from ..performance_tracker import PerformanceTracker
            except ImportError:
                from performance_tracker import PerformanceTracker

            pt = PerformanceTracker(db_path=pipeline_config.db_path, bearer_token=pipeline_config.twitter_bearer_token)
            if getattr(pipeline_config, "enable_tiered_collection", False):
                log.info(f"  [Tiered Collection] {await pt.run_tiered_collection()}")
            if getattr(pipeline_config, "enable_golden_reference_qa", False):
                count = pt.auto_update_golden_references(
                    days=getattr(pipeline_config, "golden_reference_auto_update_days", 7)
                )
                log.info(f"  [Golden Ref] 자동 갱신: {count}건")
        except (ImportError, RuntimeError, ValueError) as _e:
            log.debug(f"  성과 수집/갱신 실패 (무시): {type(_e).__name__}: {_e}")

    # 구조화 메트릭 로깅
    total_cost = 0.0
    if pipeline_config.enable_structured_metrics:
        try:
            from datetime import date as _date

            from shared.llm.stats import _DB_PATH as _llm_db
            from shared.llm.stats import CostTracker

            if _llm_db.exists():
                tracker = CostTracker(persist=True)
                daily = tracker.get_daily_stats(1)
                tracker.close()
                today = str(_date.today())
                total_cost = sum(r["cost_usd"] for r in daily if r.get("date") == today)
        except (ImportError, ValueError, KeyError, OSError):
            pass
        log.info(
            f"pipeline_metrics | run_id={run.run_id[:8]} country={run.country} "
            f"collected={run.trends_collected} scored={run.trends_scored} "
            f"generated={run.tweets_generated} saved={run.tweets_saved} "
            f"errors={len(run.errors)} cost_usd={total_cost:.4f} duration_s={elapsed:.1f}"
        )

    await _adjust_schedule(scored_trends, orig_config, schedule_callback)

    try:
        try:
            from ..alerts import send_daily_cost_alert
        except ImportError:
            from alerts import send_daily_cost_alert

        send_daily_cost_alert(pipeline_config)
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError):
        pass

    print(separator)

    try:
        from shared.notifications import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send_heartbeat(
                "GetDayTrends",
                status="alive",
                details=(
                    f"수집={run.trends_collected} 스코어링={run.trends_scored} "
                    f"생성={run.tweets_generated} 저장={run.tweets_saved} 소요={elapsed:.0f}초"
                ),
            )
            if total_cost > 0:
                notifier.send_cost_alert(total_cost, getattr(pipeline_config, "daily_budget_usd", 2.0))
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as _e:
        log.debug(f"Heartbeat 전송 실패 (무시): {type(_e).__name__}: {_e}")


async def _step_score_and_alert(raw_trends, contexts, config: AppConfig, conn, run: RunResult) -> tuple:
    """Step 2-3: 바이럴 스코어링 + 품질 필터 + 알림."""
    print("\n[2/4] 바이럴 스코어링 중 (병렬)...")
    scored_trends = analyze_trends(raw_trends, contexts, config, conn)
    run.trends_scored = len(scored_trends)

    quality_trends = _ensure_quality_and_diversity(scored_trends, config)
    filtered_count = len(scored_trends) - len(quality_trends)
    if filtered_count:
        print(f"\n  ⚡ 품질 필터: {filtered_count}개 제외 (다양성+바이럴 기반)")

    # 카테고리 분포 로깅
    cat_dist: dict[str, int] = {}
    for t in quality_trends:
        cat = getattr(t, "category", "기타") or "기타"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
    run.category_distribution = cat_dist
    if cat_dist:
        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(cat_dist.items(), key=lambda x: -x[1]))
        print(f"  📊 카테고리 분포: {dist_str}")

    # verbose 모드: 배치 히스토리
    history_map = {}
    if config.verbose:
        history_map = await get_trend_history_batch(conn, [st.keyword for st in scored_trends])

    # 스코어 미리보기
    for st in scored_trends:
        marker = " ✓" if st in quality_trends else " ✗"
        score_bar = "█" * (st.viral_potential // 10) + "░" * (10 - st.viral_potential // 10)
        print(f"  #{st.rank} [{score_bar}] {st.viral_potential:3d}점 | {st.keyword}{marker}")

        if config.verbose:
            history = history_map.get(st.keyword, [])
            if history:
                avg = round(sum(h["viral_potential"] for h in history) / len(history), 1)
                print(f"       ↳ 히스토리: {len(history)}회 등장, 평균 {avg}점")

    # Watchlist 모니터링
    if config.watchlist_keywords:
        wl_count = check_watchlist(scored_trends, config)
        if wl_count:
            print(f"\n  [WATCHLIST] 관심 키워드 {wl_count}건 감지 — 알림 전송")

    # 알림 전송
    if not config.no_alerts:
        alerts_sent = check_and_alert(scored_trends, config)
        run.alerts_sent = alerts_sent
        if alerts_sent:
            print(f"\n  알림 전송: {alerts_sent}건")

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


async def async_run_pipeline(config: AppConfig, schedule_callback: Callable[..., Any] | None = None) -> RunResult:
    """전체 파이프라인 (비동기): 수집 → 스코어링 → 알림 → 병렬생성 → 저장."""
    conn = await get_connection(config.db_path, database_url=config.database_url)
    try:
        await init_db(conn)
        run = RunResult(run_id=str(uuid.uuid4()), country=config.country)
        run_row_id = await save_run(conn, run)

        separator = "=" * 55
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{separator}")
        print(f"  작업 시작: {now_str}")
        print(separator)

        # Pre: 예산 + 적응형 limit 조정
        pipeline_config, _budget_disabled = await _check_budget_and_adjust_limit(config, conn)

        # Step 1: 수집
        _t0 = time.time()
        raw_trends, contexts = _step_collect(pipeline_config, conn, run)
        _t1 = time.time()
        log.info(f"  [타이밍] 수집: {_t1 - _t0:.1f}초")
        if not raw_trends:
            run.errors.append("트렌드 수집 실패")
            run.finished_at = datetime.now()
            await update_run(conn, run, run_row_id)
            return run

        # Step 2-3: 스코어링 + 알림
        scored_trends, quality_trends = await _step_score_and_alert(raw_trends, contexts, pipeline_config, conn, run)
        _t2 = time.time()
        log.info(f"  [타이밍] 스코어링+알림: {_t2 - _t1:.1f}초")

        # Step 3.5: Trend Genealogy (선택적)
        if getattr(pipeline_config, "enable_trend_genealogy", False) and quality_trends:
            quality_trends = await _step_genealogy(quality_trends, pipeline_config)

        # Step 4: 생성
        batch_results = await _step_generate(quality_trends, pipeline_config, conn)
        _t3 = time.time()
        log.info(f"  [타이밍] 생성: {_t3 - _t2:.1f}초")

        # Step 4.5: Canva 비주얼 자동 생성 (조건부)
        if getattr(pipeline_config, "enable_canva_visuals", False) and pipeline_config.canva_api_key:
            await _step_canva_visuals(quality_trends, batch_results, pipeline_config)

        # Step 4.6: Cross-Trend Inductive Reasoning (optional)
        await _step_reasoning(quality_trends, pipeline_config, conn, run)

        # Step 5: 저장
        success_count = await _step_save(quality_trends, batch_results, pipeline_config, conn, run, run_row_id)
        _t4 = time.time()
        log.info(f"  [타이밍] 저장: {_t4 - _t3:.1f}초")

        # Post: 완료 기록
        run.finished_at = datetime.now()
        await update_run(conn, run, run_row_id)

        elapsed = (run.finished_at - run.started_at).total_seconds()
        print(f"\n{separator}")
        print(f"  완료: {success_count}/{len(quality_trends)}개 저장")
        print(f"  소요: {elapsed:.1f}초")

        await _step_post_run(pipeline_config, run, elapsed, scored_trends, config, schedule_callback, separator)

        return run
    except Exception as _pipeline_err:
        try:
            from shared.notifications import Notifier

            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_error(f"파이프라인 실패: {_pipeline_err}", error=_pipeline_err, source="GetDayTrends")
        except Exception:
            pass
        raise
    finally:
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
