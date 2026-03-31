from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import logging

from antigravity_mcp.config import emit_metric
from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations.embedding_adapter import EmbeddingAdapter
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.pipelines.analyze_steps import (
    ReportAssemblyContext,
    apply_enrichments,
    apply_proofreading,
    build_cluster_meta,
    build_report_fingerprint,
    finalize_quality,
    generate_base_payload,
    maybe_enqueue_digest,
    persist_report,
    prepare_category_batch,
    record_topics_and_articles,
)
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore
from antigravity_mcp.tracing import trace_context

logger = logging.getLogger(__name__)

__all__ = ["BriefAdapters", "ReportAssemblyContext", "build_report_fingerprint", "generate_briefs"]


@dataclass(slots=True)
class BriefAdapters:
    """Groups the optional adapter dependencies for generate_briefs."""

    llm: LLMAdapter | None = None
    embedding: EmbeddingAdapter | None = None
    sentiment: Any | None = None
    brain: Any | None = None
    proofreader: Any | None = None
    notebooklm: Any | None = None
    skill: Any | None = None
    insight: Any | None = None
    reasoning: Any | None = None
    digest: Any | None = None


async def generate_briefs(
    *,
    items: list[ContentItem],
    window_name: str,
    window_start: str,
    window_end: str,
    state_store: PipelineStateStore,
    adapters: BriefAdapters | None = None,
    run_id: str | None = None,
    # Legacy individual adapter kwargs — prefer `adapters` for new code.
    llm_adapter: LLMAdapter | None = None,
    sentiment_adapter: Any | None = None,
    brain_adapter: Any | None = None,
    proofreader_adapter: Any | None = None,
    embedding_adapter: EmbeddingAdapter | None = None,
    notebooklm_adapter: Any | None = None,
    skill_adapter: Any | None = None,
    insight_adapter: Any | None = None,
    reasoning_adapter: Any | None = None,
    digest_adapter: Any | None = None,
) -> tuple[str, list[ContentReport], list[str], str]:
    # Merge: explicit kwargs override adapters bag (backward compat).
    a = adapters or BriefAdapters()
    llm = llm_adapter or a.llm or LLMAdapter(state_store=state_store)
    emb = embedding_adapter or a.embedding or EmbeddingAdapter()
    insight = insight_adapter or a.insight
    if insight is None and hasattr(llm, "generate_text"):
        insight = InsightAdapter(llm_adapter=llm, state_store=state_store)
    sentiment = sentiment_adapter or a.sentiment
    brain = brain_adapter or a.brain
    proofreader = proofreader_adapter or a.proofreader
    notebooklm = notebooklm_adapter or a.notebooklm
    skill = skill_adapter or a.skill
    reasoning = reasoning_adapter or a.reasoning
    digest = digest_adapter or a.digest

    run_id = run_id or generate_run_id("generate_brief")

    with trace_context(run_id):
        grouped: dict[str, list[ContentItem]] = defaultdict(list)
        for item in items:
            grouped[item.category].append(item)

        warnings: list[str] = []
        reports: list[ContentReport] = []

        cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
        if cleaned:
            warnings.append(f"Auto-cleaned {cleaned} stale run(s) stuck in 'running' state.")

        state_store.record_job_start(
            run_id,
            "generate_brief",
            summary={"window_name": window_name, "categories": list(grouped), "max_items": len(items)},
        )

        cluster_meta, cluster_warnings = await build_cluster_meta(grouped, emb)
        warnings.extend(cluster_warnings)

        for category, category_items in grouped.items():
            ctx, existing = prepare_category_batch(
                category=category,
                category_items=category_items,
                cluster_meta=cluster_meta,
                window_name=window_name,
                window_start=window_start,
                window_end=window_end,
                state_store=state_store,
            )
            if existing:
                reports.append(existing)
                warnings.append(f"Reused existing report for {category}.")
                continue

            await generate_base_payload(ctx, llm)
            await apply_proofreading(ctx, proofreader)
            await apply_enrichments(
                ctx,
                sentiment_adapter=sentiment,
                brain_adapter=brain,
                skill_adapter=skill,
                notebooklm_adapter=notebooklm,
                reasoning_adapter=reasoning,
                insight_adapter=insight if hasattr(insight, "generate_insights") else None,
            )
            await finalize_quality(ctx)

            report = persist_report(ctx)
            maybe_enqueue_digest(ctx=ctx, report=report, digest_adapter=digest)
            record_topics_and_articles(ctx=ctx, cluster_meta=cluster_meta, run_id=run_id)

            warnings.extend(ctx.warnings)
            reports.append(report)

        blocked_reports = [r for r in reports if r.quality_state == "blocked"]
        final_status = "partial" if warnings else "success"

        emit_metric(
            "pipeline_run",
            stage="generate_briefs",
            run_id=run_id,
            window_name=window_name,
            item_count=len(items),
            report_count=len(reports),
            blocked_count=len(blocked_reports),
            warning_count=len(warnings),
            status=final_status,
        )

        state_store.record_job_finish(
            run_id,
            status=final_status,
            summary={"report_ids": [report.report_id for report in reports], "window_name": window_name},
            processed_count=len(items),
            published_count=0,
        )

        # Fire-and-forget Telegram alert for blocked reports or pipeline failures.
        if blocked_reports:
            try:
                telegram = TelegramAdapter()
                if telegram.is_configured:
                    categories = ", ".join(r.category for r in blocked_reports)
                    await telegram.send_error_alert(
                        pipeline_stage="generate_briefs",
                        error_type="LLM_BLOCKED",
                        error_message=f"{len(blocked_reports)} report(s) blocked (all LLM providers failed): {categories}",
                        run_id=run_id,
                        retryable=True,
                    )
            except Exception as exc:
                logger.warning("Telegram alert failed: %s", exc)

    return run_id, reports, warnings, "partial" if warnings else "ok"
