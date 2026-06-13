"""
getdaytrends — Pipeline Step Functions (facade)
생성(Step 3) + 저장(Step 4) + 적응형 스케줄링.
core/pipeline.py에서 분리됨.

Implementation modules:
    steps_generate.py  — Step 3: Content Generation + QA + FactCheck
    steps_save.py      — Step 4: DB Save + External Save + PEE Predictions
"""

import schedule

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


def _schedule_decision(scored_trends, schedule_minutes: int) -> tuple[int, str, float, int]:
    hot = [t for t in scored_trends if t.viral_potential >= 90 and _is_accelerating(t.trend_acceleration)]
    avg_score = sum(t.viral_potential for t in scored_trends) / len(scored_trends) if scored_trends else 0
    if hot:
        return max(schedule_minutes // 4, 15), "hot", avg_score, len(hot)
    if avg_score >= 75:
        return max(int(schedule_minutes * 0.85), 30), "high_average", avg_score, 0
    if 0 < avg_score < 55:
        return min(int(schedule_minutes * 1.25), 180), "low_average", avg_score, 0
    return schedule_minutes, "default", avg_score, 0


def _schedule_message(reason: str, interval: int, avg_score: float, hot_count: int) -> str:
    if reason == "hot":
        return f"  Hot trends detected: {hot_count}; next run in {interval} minutes"
    if reason == "high_average":
        return f"  Average score {avg_score:.0f}; next run in {interval} minutes"
    if reason == "low_average":
        return f"  Average score {avg_score:.0f}; next run in {interval} minutes"
    return f"  Next run: {interval} minutes"


def _schedule_next_run(interval: int, callback) -> None:
    schedule.clear()
    schedule.every(interval).minutes.do(callback)


async def _adjust_schedule(scored_trends, config: AppConfig, schedule_callback=None) -> object:
    """Adjust the next run interval from current trend scores."""
    if not (config.smart_schedule and not config.one_shot):
        if not config.one_shot:
            print(f"  Next run: {config.schedule_minutes} minutes")
        return

    callback = schedule_callback or (lambda: None)
    interval, reason, avg_score, hot_count = _schedule_decision(scored_trends, config.schedule_minutes)
    print(_schedule_message(reason, interval, avg_score, hot_count))
    _schedule_next_run(interval, callback)

# ══════════════════════════════════════════════════════
