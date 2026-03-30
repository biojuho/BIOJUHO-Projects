from __future__ import annotations

from collections import defaultdict
from typing import Any

from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations.embedding_adapter import EmbeddingAdapter
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
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

__all__ = ["ReportAssemblyContext", "build_report_fingerprint", "generate_briefs"]


async def generate_briefs(
    *,
    items: list[ContentItem],
    window_name: str,
    window_start: str,
    window_end: str,
    state_store: PipelineStateStore,
    llm_adapter: LLMAdapter | None = None,
    run_id: str | None = None,
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
    llm_adapter = llm_adapter or LLMAdapter(state_store=state_store)
    embedding_adapter = embedding_adapter or EmbeddingAdapter()
    if insight_adapter is None and hasattr(llm_adapter, "generate_text"):
        insight_adapter = InsightAdapter(llm_adapter=llm_adapter, state_store=state_store)
    run_id = run_id or generate_run_id("generate_brief")

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

    cluster_meta, cluster_warnings = await build_cluster_meta(grouped, embedding_adapter)
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

        await generate_base_payload(ctx, llm_adapter)
        await apply_proofreading(ctx, proofreader_adapter)
        await apply_enrichments(
            ctx,
            sentiment_adapter=sentiment_adapter,
            brain_adapter=brain_adapter,
            skill_adapter=skill_adapter,
            notebooklm_adapter=notebooklm_adapter,
            reasoning_adapter=reasoning_adapter,
            insight_adapter=insight_adapter if hasattr(insight_adapter, "generate_insights") else None,
        )
        await finalize_quality(ctx)

        report = persist_report(ctx)
        maybe_enqueue_digest(ctx=ctx, report=report, digest_adapter=digest_adapter)
        record_topics_and_articles(ctx=ctx, cluster_meta=cluster_meta, run_id=run_id)

        warnings.extend(ctx.warnings)
        reports.append(report)

    state_store.record_job_finish(
        run_id,
        status="partial" if warnings else "success",
        summary={"report_ids": [report.report_id for report in reports], "window_name": window_name},
        processed_count=len(items),
        published_count=0,
    )
    return run_id, reports, warnings, "partial" if warnings else "ok"
