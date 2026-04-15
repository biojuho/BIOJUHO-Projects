"""
getdaytrends — Pipeline Step Functions (facade)
생성(Step 3) + 저장(Step 4) + 적응형 스케줄링.
core/pipeline.py에서 분리됨.

Implementation modules:
    steps_generate.py  — Step 3: Content Generation + QA + FactCheck
    steps_save.py      — Step 4: DB Save + External Save + PEE Predictions
"""

import schedule
from loguru import logger as log

try:
    from ..config import AppConfig
except ImportError:
    from config import AppConfig

# ── Re-export all public APIs so existing callers don't break ──
from .steps_generate import (  # noqa: F401
    _batch_from_cache,
    _build_empty_qa,
    _content_hub_enabled,
    _is_accelerating,
    _load_adaptive_voice,
    _load_recent_tweets,
    _run_cross_source_check,
    _run_diversity_rewrite_pass,
    _run_fact_check,
    _run_qa_pipeline,
    _should_skip_qa,
    _step_generate,
    _try_cache_hit,
)
from .steps_save import (  # noqa: F401
    _annotate_predictions,
    _attach_best_hours,
    _preview_and_record_stats,
    _record_v2_workflow_bundle,
    _save_external,
    _save_single_trend_db,
    _step_save,
)


# ══════════════════════════════════════════════════════
#  Adaptive Schedule
# ══════════════════════════════════════════════════════


async def _adjust_schedule(scored_trends, config: AppConfig, schedule_callback=None):
    """적응형 스케줄링 — 평균 점수 기반 간격 조정."""
    if not (config.smart_schedule and not config.one_shot):
        if not config.one_shot:
            print(f"  다음 실행: {config.schedule_minutes}분 후")
        return

    callback = schedule_callback or (lambda: None)
    hot = [t for t in scored_trends if t.viral_potential >= 90 and _is_accelerating(t.trend_acceleration)]
    avg_score = sum(t.viral_potential for t in scored_trends) / len(scored_trends) if scored_trends else 0

    if hot:
        fast_interval = max(config.schedule_minutes // 4, 15)
        print(f"  핫 트렌드 {len(hot)}건 감지 → 다음 실행 {fast_interval}분 후")
        schedule.clear()
        schedule.every(fast_interval).minutes.do(callback)
    elif avg_score >= 75:
        faster = max(int(config.schedule_minutes * 0.85), 30)
        print(f"  평균 {avg_score:.0f}점 (고품질) → 다음 실행 {faster}분 후")
        schedule.clear()
        schedule.every(faster).minutes.do(callback)
    elif 0 < avg_score < 55:
        slower = min(int(config.schedule_minutes * 1.25), 180)
        print(f"  평균 {avg_score:.0f}점 (저품질) → 다음 실행 {slower}분 후")
        schedule.clear()
        schedule.every(slower).minutes.do(callback)
    else:
        schedule.clear()
        schedule.every(config.schedule_minutes).minutes.do(callback)
        print(f"  다음 실행: {config.schedule_minutes}분 후")


# ══════════════════════════════════════════════════════
