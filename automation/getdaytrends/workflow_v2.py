"""Helpers for the getdaytrends V2.0 workflow."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

try:
    from .models import (
        DraftBundle,
        GeneratedTweet,
        QAReport,
        ReviewQueueStatus,
        ScoredTrend,
        TweetBatch,
        ValidatedTrend,
        WorkflowLifecycleStatus,
    )
except ImportError:
    from models import (
        DraftBundle,
        GeneratedTweet,
        QAReport,
        ReviewQueueStatus,
        ScoredTrend,
        TweetBatch,
        ValidatedTrend,
        WorkflowLifecycleStatus,
    )

DEFAULT_PROMPT_VERSION = "getdaytrends-v2"
DEFAULT_GENERATOR_PROVIDER = "shared.llm"
DEFAULT_GENERATOR_MODEL = "shared.llm.default"
DEFAULT_MAX_FRESHNESS_HOURS = 24.0


def _hash_id(prefix: str, *parts: str) -> str:
    raw = "::".join(part.strip() for part in parts if part is not None)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_scoring_axes(trend: ScoredTrend) -> tuple[dict[str, float], dict[str, str]]:
    axes = {
        "viral_potential": float(getattr(trend, "viral_potential", 0) or 0),
        "confidence": float(getattr(trend, "cross_source_confidence", 0) or 0),
        "source_quality": round(float(getattr(trend, "source_credibility", 0.0) or 0.0) * 100, 2),
        "velocity": float(getattr(trend, "velocity", 0.0) or 0.0),
    }
    reasons = {
        "viral_potential": f"viral={axes['viral_potential']:.1f}",
        "confidence": f"cross_source_confidence={axes['confidence']:.1f}",
        "source_quality": f"source_credibility={axes['source_quality']:.2f}",
        "velocity": f"velocity={axes['velocity']:.2f}",
    }
    return axes, reasons


def collect_evidence_refs(trend: ScoredTrend) -> list[str]:
    refs: list[str] = []
    for source in getattr(trend, "sources", []) or []:
        refs.append(f"source:{getattr(source, 'value', str(source))}")
    context = getattr(trend, "context", None)
    if context:
        if getattr(context, "twitter_insight", ""):
            refs.append("context:twitter")
        if getattr(context, "reddit_insight", ""):
            refs.append("context:reddit")
        if getattr(context, "news_insight", ""):
            refs.append("context:news")
    trend_context = getattr(trend, "trend_context", None)
    if trend_context and getattr(trend_context, "why_now", ""):
        refs.append("context:why_now")
    return list(dict.fromkeys(refs))


def validate_trend_candidate(
    trend: ScoredTrend,
    *,
    dedup_fingerprint: str,
    recent_fingerprints: Iterable[str] | None = None,
    max_freshness_hours: float = DEFAULT_MAX_FRESHNESS_HOURS,
    trend_id: str | None = None,
) -> tuple[ValidatedTrend | None, dict[str, Any] | None]:
    keyword = (getattr(trend, "keyword", "") or "").strip()
    recent = set(recent_fingerprints or [])
    freshness_hours = float(getattr(trend, "content_age_hours", 0.0) or 0.0)
    freshness_minutes = max(0, int(round(freshness_hours * 60)))
    evidence_refs = collect_evidence_refs(trend)

    if not keyword:
        return None, {
            "reason_code": "malformed_record",
            "reason_detail": "keyword is empty",
        }
    if not evidence_refs:
        return None, {
            "reason_code": "missing_evidence",
            "reason_detail": "trend has no evidence refs",
        }
    if freshness_hours > max_freshness_hours or getattr(trend, "freshness_grade", "") == "expired":
        return None, {
            "reason_code": "stale_record",
            "reason_detail": f"freshness_hours={freshness_hours:.2f}",
        }
    if dedup_fingerprint and dedup_fingerprint in recent:
        return None, {
            "reason_code": "duplicate_record",
            "reason_detail": dedup_fingerprint,
        }

    axes, reasons = build_scoring_axes(trend)
    validated = ValidatedTrend(
        trend_id=trend_id or _hash_id("trend", keyword, dedup_fingerprint or keyword),
        keyword=keyword,
        confidence_score=float(getattr(trend, "cross_source_confidence", 0) or 0),
        source_count=len(getattr(trend, "sources", []) or []),
        evidence_refs=evidence_refs,
        freshness_minutes=freshness_minutes,
        dedup_fingerprint=dedup_fingerprint,
        lifecycle_status=WorkflowLifecycleStatus.VALIDATED,
        scoring_axes=axes,
        scoring_reasons=reasons,
    )
    return validated, None


def _bundle_group(bundle: DraftBundle) -> str:
    if bundle.platform == "threads":
        return "threads_posts"
    if bundle.platform == "naver_blog":
        return "blog_posts"
    if bundle.content_type == "long":
        return "long_posts"
    return "tweets"


def _iter_platform_content(batch: TweetBatch) -> list[tuple[str, GeneratedTweet]]:
    rows: list[tuple[str, GeneratedTweet]] = []
    rows.extend(("x", item) for item in batch.tweets)
    rows.extend(("x", item) for item in batch.long_posts)
    rows.extend(("threads", item) for item in batch.threads_posts)
    rows.extend(("naver_blog", item) for item in batch.blog_posts)
    return rows


def build_draft_bundles(
    *,
    trend_id: str,
    trend: ScoredTrend,
    batch: TweetBatch,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    generator_provider: str = DEFAULT_GENERATOR_PROVIDER,
    generator_model: str = DEFAULT_GENERATOR_MODEL,
) -> list[DraftBundle]:
    evidence_ref = ", ".join(collect_evidence_refs(trend))
    degraded_mode = bool((batch.metadata or {}).get("degraded_mode", False))
    bundles: list[DraftBundle] = []

    for idx, (platform, item) in enumerate(_iter_platform_content(batch), start=1):
        hashtags = [part for part in item.content.split() if part.startswith("#")]
        bundles.append(
            DraftBundle(
                draft_id=_hash_id("draft", trend_id, platform, item.content_type, str(idx), item.content),
                trend_id=trend_id,
                platform=platform,
                content_type=item.content_type,
                body=item.content,
                hashtags=hashtags,
                prompt_version=prompt_version,
                generator_provider=generator_provider,
                generator_model=generator_model,
                source_evidence_ref=evidence_ref,
                degraded_mode=degraded_mode,
                lifecycle_status=WorkflowLifecycleStatus.DRAFTED,
                review_status=ReviewQueueStatus.DRAFT,
            )
        )

    if batch.thread and batch.thread.tweets:
        body = "\n\n".join(batch.thread.tweets)
        bundles.append(
            DraftBundle(
                draft_id=_hash_id("draft", trend_id, "x", "thread_sequence", body),
                trend_id=trend_id,
                platform="x",
                content_type="thread_sequence",
                body=body,
                hashtags=[part for part in body.split() if part.startswith("#")],
                prompt_version=prompt_version,
                generator_provider=generator_provider,
                generator_model=generator_model,
                source_evidence_ref=evidence_ref,
                degraded_mode=degraded_mode,
                lifecycle_status=WorkflowLifecycleStatus.DRAFTED,
                review_status=ReviewQueueStatus.DRAFT,
            )
        )

    return bundles


def build_qa_report(
    bundle: DraftBundle,
    *,
    total_score: float,
    threshold: float,
    warnings: Iterable[str] | None = None,
    failed_groups: Iterable[str] | None = None,
) -> QAReport:
    failed_group_set = set(failed_groups or [])
    warnings_list = list(warnings or [])
    blocking_reasons: list[str] = []
    if total_score < threshold:
        blocking_reasons.append(f"qa_below_threshold:{total_score:.1f}<{threshold:.1f}")
    if not bundle.prompt_version:
        blocking_reasons.append("missing_prompt_version")
    if not bundle.source_evidence_ref:
        blocking_reasons.append("missing_source_evidence_ref")
    if _bundle_group(bundle) in failed_group_set:
        blocking_reasons.append("qa_group_failed")

    return QAReport(
        draft_id=bundle.draft_id,
        total_score=round(float(total_score), 2),
        passed=not blocking_reasons,
        warnings=warnings_list,
        blocking_reasons=blocking_reasons,
    )


def review_status_for_lifecycle(status: WorkflowLifecycleStatus) -> ReviewQueueStatus:
    mapping = {
        WorkflowLifecycleStatus.DRAFTED: ReviewQueueStatus.DRAFT,
        WorkflowLifecycleStatus.READY: ReviewQueueStatus.READY,
        WorkflowLifecycleStatus.APPROVED: ReviewQueueStatus.APPROVED,
        WorkflowLifecycleStatus.PUBLISHED: ReviewQueueStatus.PUBLISHED,
        WorkflowLifecycleStatus.MEASURED: ReviewQueueStatus.PUBLISHED,
        WorkflowLifecycleStatus.LEARNED: ReviewQueueStatus.PUBLISHED,
    }
    return mapping.get(status, ReviewQueueStatus.DRAFT)
