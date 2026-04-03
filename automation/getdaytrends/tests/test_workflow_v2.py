from __future__ import annotations

import pytest

from db import (
    get_draft_bundle,
    promote_draft_to_ready,
    record_feedback_summary,
    record_publish_receipt,
    save_draft_bundle,
    save_qa_report,
    save_review_decision,
    save_run,
    save_trend,
    save_validated_trend,
)
from models import RunResult
from tests.conftest import make_batch, make_scored_trend
from workflow_v2 import build_draft_bundles, build_qa_report, build_scoring_axes, validate_trend_candidate


@pytest.mark.asyncio
async def test_validate_trend_candidate_rejects_malformed_stale_and_duplicate():
    malformed = make_scored_trend(keyword="")
    validated, quarantine = validate_trend_candidate(malformed, dedup_fingerprint="fp-1")
    assert validated is None
    assert quarantine["reason_code"] == "malformed_record"

    stale = make_scored_trend(keyword="stale-topic")
    stale.content_age_hours = 36
    validated, quarantine = validate_trend_candidate(stale, dedup_fingerprint="fp-2")
    assert validated is None
    assert quarantine["reason_code"] == "stale_record"

    duplicate = make_scored_trend(keyword="dup-topic")
    validated, quarantine = validate_trend_candidate(
        duplicate,
        dedup_fingerprint="dup-fp",
        recent_fingerprints={"dup-fp"},
    )
    assert validated is None
    assert quarantine["reason_code"] == "duplicate_record"


def test_build_scoring_axes_is_deterministic():
    trend = make_scored_trend(keyword="deterministic-topic", viral=88)
    trend.cross_source_confidence = 3
    trend.source_credibility = 0.91
    trend.velocity = 2.5

    axes_a, reasons_a = build_scoring_axes(trend)
    axes_b, reasons_b = build_scoring_axes(trend)

    assert axes_a == axes_b
    assert reasons_a == reasons_b


@pytest.mark.asyncio
async def test_blocking_reasons_prevent_ready(memory_db):
    await save_validated_trend(
        memory_db,
        trend_id="trend-1",
        keyword="blocked-topic",
        evidence_refs=["source:getdaytrends"],
        dedup_fingerprint="fp-blocked",
        lifecycle_status="scored",
    )
    await save_draft_bundle(
        memory_db,
        draft_id="draft-blocked",
        trend_id="trend-1",
        platform="x",
        content_type="short",
        body="blocked body",
        prompt_version="",
        source_evidence_ref="source:getdaytrends",
    )
    await save_qa_report(
        memory_db,
        draft_id="draft-blocked",
        total_score=30,
        passed=False,
        blocking_reasons=["qa_below_threshold:30<50", "missing_prompt_version"],
    )

    with pytest.raises(ValueError):
        await promote_draft_to_ready(memory_db, "draft-blocked")


@pytest.mark.asyncio
async def test_publish_requires_approval(memory_db):
    await save_validated_trend(
        memory_db,
        trend_id="trend-2",
        keyword="approval-topic",
        evidence_refs=["source:getdaytrends"],
        dedup_fingerprint="fp-approval",
        lifecycle_status="scored",
    )
    await save_draft_bundle(
        memory_db,
        draft_id="draft-approval",
        trend_id="trend-2",
        platform="x",
        content_type="short",
        body="body",
        prompt_version="v2",
        source_evidence_ref="source:getdaytrends",
    )
    await save_qa_report(memory_db, draft_id="draft-approval", total_score=90, passed=True)
    await promote_draft_to_ready(memory_db, "draft-approval")

    with pytest.raises(ValueError):
        await record_publish_receipt(
            memory_db,
            draft_id="draft-approval",
            platform="x",
            success=True,
            published_url="https://x.com/i/status/1",
        )


@pytest.mark.asyncio
async def test_feedback_requires_receipt(memory_db):
    await save_validated_trend(
        memory_db,
        trend_id="trend-3",
        keyword="feedback-topic",
        evidence_refs=["source:getdaytrends"],
        dedup_fingerprint="fp-feedback",
        lifecycle_status="scored",
    )
    await save_draft_bundle(
        memory_db,
        draft_id="draft-feedback",
        trend_id="trend-3",
        platform="x",
        content_type="short",
        body="body",
        prompt_version="v2",
        source_evidence_ref="source:getdaytrends",
    )

    with pytest.raises(ValueError):
        await record_feedback_summary(
            memory_db,
            draft_id="draft-feedback",
            metric_window="48h",
            impressions=100,
            engagements=10,
            clicks=2,
        )


@pytest.mark.asyncio
async def test_closed_loop_workflow(memory_db):
    run = RunResult(run_id="v2-closed-loop", country="korea")
    run_id = await save_run(memory_db, run)
    trend = make_scored_trend(keyword="closed-loop-topic", viral=84)
    trend.cross_source_confidence = 3
    trend.source_credibility = 0.76
    trend.velocity = 1.8
    trend_id = await save_trend(memory_db, trend, run_id)

    validated, quarantine = validate_trend_candidate(
        trend,
        dedup_fingerprint="closed-loop-fp",
        trend_id=f"trend-{trend_id}",
    )
    assert quarantine is None
    assert validated is not None

    await save_validated_trend(
        memory_db,
        trend_id=validated.trend_id,
        trend_row_id=trend_id,
        run_id=run_id,
        keyword=validated.keyword,
        confidence_score=validated.confidence_score,
        source_count=validated.source_count,
        evidence_refs=validated.evidence_refs,
        freshness_minutes=validated.freshness_minutes,
        dedup_fingerprint=validated.dedup_fingerprint,
        lifecycle_status="scored",
        scoring_axes=validated.scoring_axes,
        scoring_reasons=validated.scoring_reasons,
    )

    batch = make_batch("closed-loop-topic", viral_score=84)
    batch.metadata["prompt_version"] = "getdaytrends-v2.4.1"
    batch.metadata["generator_provider"] = "shared.llm"
    batch.metadata["generator_model"] = "shared.llm.default"
    bundles = build_draft_bundles(trend_id=validated.trend_id, trend=trend, batch=batch, prompt_version=batch.metadata["prompt_version"])
    bundle = bundles[0]

    await save_draft_bundle(
        memory_db,
        draft_id=bundle.draft_id,
        trend_id=bundle.trend_id,
        trend_row_id=trend_id,
        platform=bundle.platform,
        content_type=bundle.content_type,
        body=bundle.body,
        hashtags=bundle.hashtags,
        prompt_version=bundle.prompt_version,
        generator_provider=bundle.generator_provider,
        generator_model=bundle.generator_model,
        source_evidence_ref=bundle.source_evidence_ref,
    )

    report = build_qa_report(bundle, total_score=84, threshold=50)
    await save_qa_report(
        memory_db,
        draft_id=report.draft_id,
        total_score=report.total_score,
        passed=report.passed,
        warnings=report.warnings,
        blocking_reasons=report.blocking_reasons,
    )
    await promote_draft_to_ready(memory_db, bundle.draft_id)
    await save_review_decision(memory_db, draft_id=bundle.draft_id, decision="approved", reviewed_by="tester")
    receipt_id = await record_publish_receipt(
        memory_db,
        draft_id=bundle.draft_id,
        platform="x",
        success=True,
        published_url="https://x.com/i/status/4242",
    )
    await record_feedback_summary(
        memory_db,
        draft_id=bundle.draft_id,
        receipt_id=receipt_id,
        metric_window="48h",
        impressions=1200,
        engagements=130,
        clicks=41,
        collector_status="manual",
        strategy_notes="Lead with the stronger hook earlier.",
    )

    row = await get_draft_bundle(memory_db, bundle.draft_id)
    assert row is not None
    assert row["lifecycle_status"] == "learned"
    assert row["review_status"] == "Published"
    assert row["receipt_id"] == receipt_id
