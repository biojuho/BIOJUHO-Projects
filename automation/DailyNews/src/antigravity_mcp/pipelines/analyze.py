from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from antigravity_mcp.config import emit_metric
from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations.embedding_adapter import EmbeddingAdapter
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.integrations.jina_adapter import JinaAdapter
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
    jina: JinaAdapter | None = None


def _resolve_adapters(
    state_store: PipelineStateStore,
    adapters: BriefAdapters | None,
    llm_adapter: LLMAdapter | None,
    embedding_adapter: EmbeddingAdapter | None,
    insight_adapter: Any,
    sentiment_adapter: Any,
    brain_adapter: Any,
    proofreader_adapter: Any,
    notebooklm_adapter: Any,
    skill_adapter: Any,
    reasoning_adapter: Any,
    digest_adapter: Any,
) -> BriefAdapters:
    """Merge legacy kwargs into a BriefAdapters bag (explicit kwargs win over bag defaults)."""
    a = adapters or BriefAdapters()
    llm = llm_adapter or a.llm or LLMAdapter(state_store=state_store)
    emb = embedding_adapter or a.embedding or EmbeddingAdapter()
    insight = insight_adapter or a.insight
    if insight is None and hasattr(llm, "generate_text"):
        try:
            insight = InsightAdapter(llm_adapter=llm, state_store=state_store)
        except Exception as e:
            logger.warning("InsightAdapter 초기화 실패 — insight 기능 비활성: %s", e)
            insight = None
    return BriefAdapters(
        llm=llm,
        embedding=emb,
        insight=insight,
        sentiment=sentiment_adapter or a.sentiment,
        brain=brain_adapter or a.brain,
        proofreader=proofreader_adapter or a.proofreader,
        notebooklm=notebooklm_adapter or a.notebooklm,
        skill=skill_adapter or a.skill,
        reasoning=reasoning_adapter or a.reasoning,
        digest=digest_adapter or a.digest,
        jina=a.jina or JinaAdapter(),
    )


async def _process_category(
    category: str,
    category_items: list,
    cluster_meta: dict,
    window_name: str,
    window_start: str,
    window_end: str,
    state_store: PipelineStateStore,
    run_id: str,
    resolved: BriefAdapters,
    reports: list,
    warnings: list[str],
) -> None:
    """단일 카테고리 브리프 생성 → reports/warnings에 인플레이스 추가."""

    # Fingerprint must be computed BEFORE Jina enrichment to ensure
    # idempotent dedup (Jina mutates item.summary, changing the hash).
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
        return

    # 🌟 Jina AI Deep Research Fetching (after fingerprint, before LLM)
    if resolved.jina:
        urls_to_fetch = [item.link for item in category_items if item.link and str(item.link).startswith("http")]
        if urls_to_fetch:
            logger.info("Fetching deep context via Jina.ai for %d URLs in %s", len(urls_to_fetch), category)
            contexts = await resolved.jina.fetch_contexts_for_urls(urls_to_fetch)
            for item in category_items:
                if item.link in contexts and "[Deep Context (Jina.ai)]" not in item.summary:
                    deep_text = contexts[item.link]
                    item.summary = f"{item.summary}\n\n[Deep Context (Jina.ai)]\n{deep_text}"

    await generate_base_payload(ctx, resolved.llm)
    await apply_proofreading(ctx, resolved.proofreader)
    await apply_enrichments(
        ctx,
        sentiment_adapter=resolved.sentiment,
        brain_adapter=resolved.brain,
        skill_adapter=resolved.skill,
        notebooklm_adapter=resolved.notebooklm,
        reasoning_adapter=resolved.reasoning,
        insight_adapter=resolved.insight if hasattr(resolved.insight, "generate_insights") else None,
    )
    await finalize_quality(ctx)

    report = persist_report(ctx)
    maybe_enqueue_digest(ctx=ctx, report=report, digest_adapter=resolved.digest)
    record_topics_and_articles(ctx=ctx, cluster_meta=cluster_meta, run_id=run_id)
    warnings.extend(ctx.warnings)
    reports.append(report)


async def _alert_blocked_reports(blocked_reports: list, run_id: str) -> None:
    """블록된 리포트에 대한 Telegram fire-and-forget 알림."""
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
    resolved = _resolve_adapters(
        state_store, adapters,
        llm_adapter, embedding_adapter, insight_adapter,
        sentiment_adapter, brain_adapter, proofreader_adapter,
        notebooklm_adapter, skill_adapter, reasoning_adapter, digest_adapter,
    )
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

        cluster_meta, cluster_warnings = await build_cluster_meta(grouped, resolved.embedding)
        warnings.extend(cluster_warnings)

        for category, category_items in grouped.items():
            await _process_category(
                category, category_items, cluster_meta,
                window_name, window_start, window_end,
                state_store, run_id, resolved, reports, warnings,
            )

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

        if blocked_reports:
            await _alert_blocked_reports(blocked_reports, run_id)

    return run_id, reports, warnings, "partial" if warnings else "ok"
