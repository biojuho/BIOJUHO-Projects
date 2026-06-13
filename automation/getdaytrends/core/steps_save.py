"""
getdaytrends — Step 4: Save & Record
SQLite 원자적 트랜잭션 저장 + 외부 저장 병렬 처리 + PEE 예측.
core/pipeline_steps.py에서 분리됨.
"""

import asyncio
import contextlib
import sqlite3
from datetime import datetime

from loguru import logger as log

# Optional dependencies
try:
    from shared.business_metrics import biz as _biz
except ImportError:
    _biz = None  # type: ignore[assignment]

try:
    from shared.prediction import PredictionEngine as _PredictionEngine

    _PEE_AVAILABLE = True
except ImportError:
    _PredictionEngine = None  # type: ignore[assignment,misc]
    _PEE_AVAILABLE = False

try:
    from ..config import VERSION, AppConfig
    from ..db import (
        attach_draft_to_notion_page,
        compute_fingerprint,
        db_transaction,
        get_best_posting_hours,
        promote_draft_to_ready,
        record_posting_time_stat,
        record_trend_quarantine,
        save_draft_bundle,
        save_qa_report,
        save_trend,
        save_tweets_batch,
        save_validated_trend,
        update_draft_bundle_status,
    )
    from ..models import RunResult, TweetBatch
    from ..storage import save_to_content_hub, save_to_google_sheets, save_to_notion
    from ..workflow_v2 import build_draft_bundles, build_qa_report, validate_trend_candidate
except ImportError:
    from config import VERSION, AppConfig
    from db import (
        compute_fingerprint,
        db_transaction,
        get_best_posting_hours,
        promote_draft_to_ready,
        record_posting_time_stat,
        record_trend_quarantine,
        save_draft_bundle,
        save_qa_report,
        save_trend,
        save_tweets_batch,
        save_validated_trend,
        update_draft_bundle_status,
    )
    from models import RunResult, TweetBatch
    from storage import save_to_content_hub, save_to_google_sheets, save_to_notion
    from workflow_v2 import build_draft_bundles, build_qa_report, validate_trend_candidate

from .steps_generate import _content_hub_enabled

# ══════════════════════════════════════════════════════
#  Workflow V2 Bundle Recording
# ══════════════════════════════════════════════════════


def _qa_group_for_bundle(bundle) -> str:
    if bundle.platform == "threads":
        return "threads_posts"
    if bundle.platform == "naver_blog":
        return "blog_posts"
    if bundle.content_type == "long":
        return "long_posts"
    return "tweets"


async def _validate_or_quarantine_v2_trend(conn, trend, trend_row_id: int, run_row_id: int, config: AppConfig) -> object:
    fingerprint = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket=config.cache_volume_bucket)
    validated, quarantine = validate_trend_candidate(
        trend,
        dedup_fingerprint=fingerprint,
        trend_id=f"trend-{trend_row_id}",
    )
    if validated is not None:
        return validated

    await record_trend_quarantine(
        conn,
        run_id=run_row_id,
        keyword=trend.keyword,
        fingerprint=fingerprint,
        reason_code=quarantine.get("reason_code", "validation_failed"),
        reason_detail=quarantine.get("reason_detail", ""),
        source_count=len(getattr(trend, "sources", []) or []),
        freshness_minutes=int(round(float(getattr(trend, "content_age_hours", 0.0) or 0.0) * 60)),
        payload={"keyword": trend.keyword, "viral_potential": getattr(trend, "viral_potential", 0)},
    )
    return None


async def _save_scored_v2_trend(conn, validated, trend_row_id: int, run_row_id: int) -> None:
    await save_validated_trend(
        conn,
        trend_id=validated.trend_id,
        keyword=validated.keyword,
        confidence_score=validated.confidence_score,
        source_count=validated.source_count,
        evidence_refs=validated.evidence_refs,
        freshness_minutes=validated.freshness_minutes,
        dedup_fingerprint=validated.dedup_fingerprint,
        lifecycle_status="scored",
        scoring_axes=validated.scoring_axes,
        scoring_reasons=validated.scoring_reasons,
        trend_row_id=trend_row_id,
        run_id=run_row_id,
    )


async def _record_v2_workflow_bundle(
    conn,
    *,
    trend,
    batch: TweetBatch,
    trend_row_id: int,
    run_row_id: int,
    config: AppConfig,
) -> dict:
    validated = await _validate_or_quarantine_v2_trend(conn, trend, trend_row_id, run_row_id, config)
    if validated is None:
        return {"ready_platforms": set(), "drafts": []}

    validated.lifecycle_status = "scored"
    await _save_scored_v2_trend(conn, validated, trend_row_id, run_row_id)

    qa_meta = (batch.metadata or {}).get("qa_report", {}) or {}
    bundles = _build_v2_draft_bundles(validated.trend_id, trend, batch)
    ready_platforms, recorded = await _record_v2_draft_bundles(
        conn,
        bundles=bundles,
        qa_meta=qa_meta,
        config=config,
        trend_row_id=trend_row_id,
        batch=batch,
        trend=trend,
    )

    return {"ready_platforms": ready_platforms, "drafts": recorded, "trend_id": validated.trend_id}


def _build_v2_draft_bundles(trend_id: str, trend, batch: TweetBatch) -> object:
    return build_draft_bundles(
        trend_id=trend_id,
        trend=trend,
        batch=batch,
        prompt_version=(batch.metadata or {}).get("prompt_version", f"getdaytrends-v2.{VERSION}"),
        generator_provider=(batch.metadata or {}).get("generator_provider", "shared.llm"),
        generator_model=(batch.metadata or {}).get("generator_model", "shared.llm.default"),
    )


async def _record_v2_draft_bundles(
    conn,
    *,
    bundles,
    qa_meta: dict,
    config: AppConfig,
    trend_row_id: int,
    batch: TweetBatch,
    trend,
) -> tuple[set[str], list[dict]]:
    failed_groups = qa_meta.get("failed_groups", []) or []
    warnings = qa_meta.get("warnings", []) or []
    group_results = qa_meta.get("group_results", {}) or {}
    ready_platforms: set[str] = set()
    recorded: list[dict] = []
    for bundle in bundles:
        await save_draft_bundle(
            conn,
            draft_id=bundle.draft_id,
            trend_id=bundle.trend_id,
            trend_row_id=trend_row_id,
            platform=bundle.platform,
            content_type=bundle.content_type,
            body=bundle.body,
            hashtags=bundle.hashtags,
            prompt_version=bundle.prompt_version,
            generator_provider=bundle.generator_provider,
            generator_model=bundle.generator_model,
            source_evidence_ref=bundle.source_evidence_ref,
            degraded_mode=bundle.degraded_mode,
            lifecycle_status="drafted",
            review_status="Draft",
        )
        group_name = _qa_group_for_bundle(bundle)
        threshold = float(config.get_quality_threshold(group_name))
        total_score = float(
            group_results.get(group_name, {}).get(
                "total",
                qa_meta.get("total_score", batch.viral_score or getattr(trend, "viral_potential", 0)),
            )
        )
        report = build_qa_report(
            bundle,
            total_score=total_score,
            threshold=threshold,
            warnings=warnings,
            failed_groups=failed_groups,
        )
        await save_qa_report(
            conn,
            draft_id=report.draft_id,
            total_score=report.total_score,
            passed=report.passed,
            warnings=report.warnings,
            blocking_reasons=report.blocking_reasons,
            report_payload={"failed_groups": failed_groups, "group_name": group_name},
        )
        if report.passed:
            await promote_draft_to_ready(conn, report.draft_id)
            ready_platforms.add(bundle.platform)
        else:
            await update_draft_bundle_status(
                conn,
                draft_id=report.draft_id,
                lifecycle_status="drafted",
                review_status="Rejected",
            )
        recorded.append(
            {
                "draft_id": bundle.draft_id,
                "trend_id": bundle.trend_id,
                "platform": bundle.platform,
                "content_type": bundle.content_type,
                "passed": report.passed,
                "qa_score": report.total_score,
                "blocking_reasons": report.blocking_reasons,
                "prompt_version": bundle.prompt_version,
            }
        )

    return ready_platforms, recorded


# ══════════════════════════════════════════════════════
#  DB Save (single trend)
# ══════════════════════════════════════════════════════


async def _save_single_trend_db(
    batch: TweetBatch,
    trend,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> bool:
    """단일 트렌드를 SQLite 원자적 트랜잭션으로 저장."""
    try:
        async with db_transaction(conn):
            trend_id = await save_trend(conn, trend, run_row_id, bucket=config.cache_volume_bucket)
            if _biz is not None:
                _biz.trend_scored()
            saved_to: list[str] = []
            for content_list, _is_thread in [
                (batch.tweets, False),
                (batch.long_posts, False),
                (batch.threads_posts, False),
                (getattr(batch, "blog_posts", []), False),
            ]:
                if content_list:
                    await save_tweets_batch(conn, content_list, trend_id, run_row_id, saved_to=saved_to)
                    run.tweets_saved += len(content_list)
            if getattr(batch, "thread", None) and batch.thread.tweets:
                await save_tweets_batch(
                    conn,
                    batch.thread.tweets,
                    trend_id,
                    run_row_id,
                    is_thread=True,
                    saved_to=saved_to,
                )
                run.tweets_saved += len(batch.thread.tweets)
            workflow_v2 = await _record_v2_workflow_bundle(
                conn,
                trend=trend,
                batch=batch,
                trend_row_id=trend_id,
                run_row_id=run_row_id,
                config=config,
            )
            if not hasattr(batch, "metadata") or batch.metadata is None:
                batch.metadata = {}
            batch.metadata["workflow_v2"] = workflow_v2
    except (ImportError, sqlite3.Error, ValueError) as e:
        log.error(f"SQLite 저장 실패 ({trend.keyword}): {type(e).__name__}: {e}")
        run.errors.append(f"DB 저장 실패: {trend.keyword}")
        return False
    return True


# ══════════════════════════════════════════════════════
#  External Save (Notion/Sheets/Content Hub)
# ══════════════════════════════════════════════════════


async def _save_external_targets(batch: TweetBatch, trend, config: AppConfig, notion_sem: asyncio.Semaphore) -> dict[str, bool]:
    results: dict[str, bool] = {}
    if config.storage_type in ("notion", "both"):
        async with notion_sem:
            results["notion"] = await asyncio.to_thread(save_to_notion, batch, trend, config)
    if config.storage_type in ("google_sheets", "both"):
        results["google_sheets"] = await asyncio.to_thread(save_to_google_sheets, batch, trend, config)
    return results


def _record_external_save_result(keyword: str, result, run: RunResult) -> str:
    if isinstance(result, Exception):
        log.error(f"External save raised ({keyword}): {result}")
        run.errors.append(f"external save raised: {keyword}")
        return keyword

    failed_targets = sorted(name for name, ok in result.items() if not ok)
    if not failed_targets:
        return ""

    failed_label = ", ".join(failed_targets)
    log.error(f"External save failed ({keyword}): {failed_label}")
    run.errors.append(f"external save failed ({failed_label}): {keyword}")
    return f"{keyword}[{failed_label}]"


def _content_hub_ready_platforms(batch: TweetBatch) -> set:
    workflow_v2 = (getattr(batch, "metadata", {}) or {}).get("workflow_v2", {}) or {}
    return set(workflow_v2.get("ready_platforms", set()) or [])


def _content_hub_has_platform_content(batch: TweetBatch, platform: str) -> bool:
    platform_content = {
        "x": bool(batch.tweets),
        "threads": bool(batch.threads_posts),
        "naver_blog": bool(getattr(batch, "blog_posts", [])),
    }
    return platform_content.get(platform, False)


async def _save_content_hub_platform(
    batch: TweetBatch,
    trend,
    config: AppConfig,
    platform: str,
    notion_sem: asyncio.Semaphore,
    run: RunResult,
) -> None:
    try:
        async with notion_sem:
            hub_ok = await asyncio.to_thread(save_to_content_hub, batch, trend, config, platform)
    except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as hub_err:
        log.warning(f"Content Hub save raised [{platform}] ({trend.keyword}): {type(hub_err).__name__}: {hub_err}")
        run.errors.append(f"content hub raised ({platform}): {trend.keyword}")
        return

    if not hub_ok:
        log.warning(f"Content Hub save failed [{platform}] ({trend.keyword})")
        run.errors.append(f"content hub failed ({platform}): {trend.keyword}")


async def _save_content_hub_outputs(
    ext_pairs: list[tuple],
    config: AppConfig,
    notion_sem: asyncio.Semaphore,
    run: RunResult,
) -> None:
    if not _content_hub_enabled(config):
        return

    platforms = getattr(config, "target_platforms", ["x"])
    for batch, trend in ext_pairs:
        ready_platforms = _content_hub_ready_platforms(batch)
        for platform in platforms:
            if ready_platforms and platform not in ready_platforms:
                continue
            if not _content_hub_has_platform_content(batch, platform):
                continue
            await _save_content_hub_platform(batch, trend, config, platform, notion_sem, run)


async def _save_external(
    ext_pairs: list[tuple],
    config: AppConfig,
    run: RunResult,
) -> None:
    """Notion/Sheets + Content Hub parallel external save."""
    notion_sem = asyncio.Semaphore(config.notion_sem_limit)
    ext_results = await asyncio.gather(
        *[_save_external_targets(batch, trend, config, notion_sem) for batch, trend in ext_pairs],
        return_exceptions=True,
    )

    ext_failed: list[str] = []
    for index, result in enumerate(ext_results):
        failure = _record_external_save_result(ext_pairs[index][1].keyword, result, run)
        if failure:
            ext_failed.append(failure)
    if ext_failed:
        print(f"\n  External save failed for {len(ext_failed)} item(s): {', '.join(ext_failed)}")

    await _save_content_hub_outputs(ext_pairs, config, notion_sem, run)

async def _preview_and_record_stats(batch, category: str, conn) -> None:
    """배치 콘텐츠 미리보기 출력 + 게시 시간 통계 기록."""
    for t in batch.tweets:
        preview = t.content[:50] + "..." if len(t.content) > 50 else t.content
        print(f"    [{t.tweet_type}] {preview}")
        if t.best_posting_time and t.expected_engagement:
            with contextlib.suppress(ImportError, sqlite3.Error, ValueError):
                await record_posting_time_stat(conn, category, datetime.now().hour, t.expected_engagement)
    if batch.long_posts:
        print(f"    [Premium+ 장문] {len(batch.long_posts)}편")
    if batch.threads_posts:
        print(f"    [Threads] {len(batch.threads_posts)}편")
    if getattr(batch, "blog_posts", []):
        print(f"    [블로그] {len(batch.blog_posts)}편 ({sum(p.char_count for p in batch.blog_posts):,}자)")
    if batch.thread:
        print(f"    [쓰레드] {len(batch.thread.tweets)}개 트윗")


def _attach_best_hours(batch, category: str, best_hours: list[int]) -> None:
    """배치 메타데이터에 추천 게시 시간 기록."""
    if not best_hours:
        return
    if not hasattr(batch, "metadata") or batch.metadata is None:
        batch.metadata = {}
    batch.metadata["best_posting_hours"] = best_hours
    print(f"    추천 게시 시간 ({category}): {', '.join(f'{h}시' for h in best_hours)}")


# ══════════════════════════════════════════════════════
#  PEE Predictions
# ══════════════════════════════════════════════════════


def _prediction_workspace_paths() -> object:
    from pathlib import Path

    workspace = Path(__file__).resolve().parents[3]
    return {
        "gdt_db": workspace / "automation" / "getdaytrends" / "data" / "getdaytrends.db",
        "cie_db": workspace / "automation" / "content-intelligence" / "data" / "cie.db",
        "dn_db": workspace / "automation" / "DailyNews" / "data" / "pipeline_state.db",
        "model_dir": workspace / "var" / "models" / "prediction",
    }


def _prediction_candidate(trend, batch) -> object:
    if isinstance(batch, Exception) or not batch:
        return None
    best_tweet = batch.tweets[0] if batch.tweets else None
    if not best_tweet:
        return None
    metadata = getattr(batch, "metadata", None) or {}
    return {
        "content": best_tweet.content,
        "trend_keyword": trend.keyword,
        "viral_potential": trend.viral_potential,
        "qa_scores": metadata.get("qa_scores", {}),
        "category": getattr(trend, "category", "other") or "other",
        "content_type": "tweet",
    }


def _apply_prediction_metadata(batch, result) -> None:
    if not hasattr(batch, "metadata") or batch.metadata is None:
        batch.metadata = {}
    batch.metadata["predicted_er"] = result.predicted_engagement_rate
    batch.metadata["predicted_impressions"] = result.predicted_impressions
    batch.metadata["viral_probability"] = result.viral_probability
    batch.metadata["optimal_hours"] = result.optimal_hours
    batch.metadata["pee_risk"] = result.risk_level


async def _annotate_predictions(quality_trends: list, batch_results: list, config: AppConfig) -> None:
    """Annotate generated batches with prediction engine metadata."""
    try:
        engine = _PredictionEngine(**_prediction_workspace_paths())
        await engine.initialize()

        annotated = 0
        for trend, batch in zip(quality_trends, batch_results, strict=False):
            candidate = _prediction_candidate(trend, batch)
            if candidate is None:
                continue
            result = await engine.predict(**candidate)
            _apply_prediction_metadata(batch, result)
            annotated += 1

        if annotated:
            log.info(f"  [PEE] predictions annotated: {annotated}")
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        log.warning(f"  [PEE] prediction skipped: {type(e).__name__}: {e}")

# ══════════════════════════════════════════════════════
#  Main Step 4: Save
# ══════════════════════════════════════════════════════


async def _step_save(
    quality_trends: list,
    batch_results: list,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> int:
    """Step 4: persist generated content and queue external saves."""
    print("\n[4/4] 저장 중...")

    if _PEE_AVAILABLE and getattr(config, "enable_prediction", True):
        await _annotate_predictions(quality_trends, batch_results, config)

    success_count = 0
    ext_pairs: list[tuple] = []
    failed_saves: list[str] = []

    for trend, batch in zip(quality_trends, batch_results, strict=False):
        result = await _save_generated_trend_batch(trend, batch, config, conn, run, run_row_id)
        if result == "failed":
            failed_saves.append(trend.keyword)
            continue
        if result == "skipped":
            continue

        success_count += 1
        if result == "external":
            ext_pairs.append((batch, trend))

    if ext_pairs and not config.dry_run:
        await _save_external(ext_pairs, config, run)

    if failed_saves:
        print(f"\n  DB save failed for {len(failed_saves)} trend(s): {', '.join(failed_saves)}")

    return success_count


async def _save_generated_trend_batch(
    trend,
    batch,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> str:
    if _skip_safety_flagged_trend(trend, config, run):
        return "skipped"

    print(f"\n  '{trend.keyword}' (viral: {trend.viral_potential})")
    category = getattr(trend, "category", "other") or "other"
    best_hours = await _best_posting_hours(conn, category)
    if not _valid_generated_batch(trend, batch, run):
        return "skipped"

    _record_generated_content_count(run, batch)
    await _preview_and_record_stats(batch, category, conn)
    _attach_best_hours(batch, category, best_hours)

    if not await _save_single_trend_db(batch, trend, config, conn, run, run_row_id):
        return "failed"
    return "saved" if config.dry_run else "external"


def _skip_safety_flagged_trend(trend, config: AppConfig, run: RunResult) -> bool:
    if not (config.enable_sentiment_filter and getattr(trend, "safety_flag", False)):
        return False
    log.warning(f"Unsafe trend skipped: '{trend.keyword}' (sentiment={trend.sentiment})")
    run.errors.append(f"safety_flag skipped: {trend.keyword}")
    return True


async def _best_posting_hours(conn, category: str) -> list[int]:
    with contextlib.suppress(ImportError, sqlite3.Error, ValueError):
        return await get_best_posting_hours(conn, category, top_n=3)
    return []


def _valid_generated_batch(trend, batch, run: RunResult) -> bool:
    if isinstance(batch, Exception):
        log.error(f"Generation exception ({trend.keyword}): {type(batch).__name__}: {batch}")
        run.errors.append(f"generation exception: {trend.keyword}")
        return False
    if not batch:
        run.errors.append(f"generation failed: {trend.keyword}")
        return False
    return True


def _record_generated_content_count(run: RunResult, batch: TweetBatch) -> None:
    run.tweets_generated += (
        len(batch.tweets)
        + len(batch.long_posts)
        + len(batch.threads_posts)
        + len(getattr(batch, "blog_posts", []))
    )
