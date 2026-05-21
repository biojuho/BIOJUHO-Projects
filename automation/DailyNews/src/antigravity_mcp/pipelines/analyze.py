from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, cast

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


def _get_notifier() -> object:
    """Lazy-import shared Notifier (never raises)."""
    try:
        from shared.notifications import Notifier

        return Notifier.from_env()
    except Exception:
        return None


__all__ = ["BriefAdapters", "ReportAssemblyContext", "build_report_fingerprint", "generate_briefs"]

_CATEGORY_FAMILY: dict[str, frozenset[str]] = {
    "Economy_KR": frozenset({"Economy_KR"}),
    "Economy_Global": frozenset({"Economy_Global"}),
    "Crypto": frozenset({"Crypto"}),
    "Tech": frozenset({"Tech"}),
    "AI_Deep": frozenset({"AI_Deep", "Tech"}),
    "Global_Affairs": frozenset({"Global_Affairs"}),
}


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


def _resolve_llm_adapter(
    state_store: PipelineStateStore,
    adapters: BriefAdapters,
    llm_adapter: LLMAdapter | None,
) -> LLMAdapter:
    return llm_adapter or adapters.llm or LLMAdapter(state_store=state_store)


def _resolve_embedding_adapter(
    adapters: BriefAdapters,
    embedding_adapter: EmbeddingAdapter | None,
) -> EmbeddingAdapter:
    return embedding_adapter or adapters.embedding or EmbeddingAdapter()


def _build_insight_adapter(llm: LLMAdapter, state_store: PipelineStateStore) -> InsightAdapter | None:
    if not hasattr(llm, "generate_text"):
        return None
    try:
        return InsightAdapter(llm_adapter=llm, state_store=state_store)
    except Exception as exc:
        logger.warning("InsightAdapter initialization failed; insight disabled: %s", exc)
        return None


def _resolve_insight_adapter(
    state_store: PipelineStateStore,
    adapters: BriefAdapters,
    llm: LLMAdapter,
    insight_adapter: Any,
) -> Any:
    explicit = insight_adapter or adapters.insight
    if explicit is not None:
        return explicit
    return _build_insight_adapter(llm, state_store)


def _filter_category_items(category: str, category_items: list[ContentItem]) -> tuple[list[ContentItem], int]:
    allowed_categories = _CATEGORY_FAMILY.get(category, frozenset({category}))
    filtered_items = [
        item
        for item in category_items
        if not item.category or item.category in allowed_categories or item.category == "unknown"
    ]
    return filtered_items, len(category_items) - len(filtered_items)


def _record_category_filter_result(
    category: str,
    *,
    removed_count: int,
    original_count: int,
    remaining_count: int,
    warnings: list[str],
) -> bool:
    if removed_count:
        logger.info("Category purity filter: removed %d cross-category items from %s", removed_count, category)
        warnings.append(
            f"[CategoryFilter] {category}: {removed_count} cross-category item(s) removed "
            f"(total {original_count}, kept {remaining_count})"
        )
    if remaining_count:
        return True
    warnings.append(f"[CategoryFilter] {category}: no items remain after filtering; skipped.")
    return False


def _jina_urls(category_items: list[ContentItem]) -> list[str]:
    return [item.link for item in category_items if item.link and str(item.link).startswith("http")]


def _apply_jina_contexts(category_items: list[ContentItem], contexts: dict[str, str]) -> None:
    for item in category_items:
        if item.link in contexts and "[Deep Context (Jina.ai)]" not in item.summary:
            deep_text = contexts[item.link]
            item.summary = f"{item.summary}\n\n[Deep Context (Jina.ai)]\n{deep_text}"


async def _enrich_with_jina(category: str, category_items: list[ContentItem], jina: JinaAdapter | None) -> None:
    if not jina:
        return
    urls_to_fetch = _jina_urls(category_items)
    if not urls_to_fetch:
        return
    logger.info("Fetching deep context via Jina.ai for %d URLs in %s", len(urls_to_fetch), category)
    _apply_jina_contexts(category_items, await jina.fetch_contexts_for_urls(urls_to_fetch))


def _quality_feedback(state_store: PipelineStateStore, category: str) -> Any | None:
    try:
        return state_store.get_category_quality_history(category, days=7)
    except Exception as exc:
        logger.debug("Quality history fetch failed for %s: %s", category, exc)
        return None


def _recent_draft_previews(state_store: PipelineStateStore, category: str) -> list[str] | None:
    try:
        recent = state_store.get_recent_drafts(category, days=7, channel="x")
    except Exception as exc:
        logger.debug("Recent drafts fetch failed for %s: %s", category, exc)
        return None
    if not recent:
        return None
    return [draft["content"][:300] for draft in recent[:3]]


def _group_items_by_category(items: list[ContentItem]) -> dict[str, list[ContentItem]]:
    grouped: dict[str, list[ContentItem]] = defaultdict(list)
    for item in items:
        grouped[item.category].append(item)
    return grouped


def _cleanup_stale_run_warning(state_store: PipelineStateStore) -> str | None:
    cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
    if not cleaned:
        return None
    return f"Auto-cleaned {cleaned} stale run(s) stuck in 'running' state."


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
    llm = _resolve_llm_adapter(state_store, a, llm_adapter)
    emb = _resolve_embedding_adapter(a, embedding_adapter)
    insight = _resolve_insight_adapter(state_store, a, llm, insight_adapter)
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

    original_count = len(category_items)
    category_items, removed_count = _filter_category_items(category, category_items)
    if not _record_category_filter_result(
        category,
        removed_count=removed_count,
        original_count=original_count,
        remaining_count=len(category_items),
        warnings=warnings,
    ):
        return

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

    await _enrich_with_jina(category, category_items, resolved.jina)

    llm = cast("LLMAdapter", resolved.llm)
    await generate_base_payload(
        ctx,
        llm,
        quality_feedback=_quality_feedback(state_store, category),
        overlapping_drafts=_recent_draft_previews(state_store, category),
    )
    # Auto-heal에서 LLM 재호출할 수 있도록 ctx에 참조 저장
    ctx._llm_adapter = llm
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



def _send_generate_notifications(
    *,
    grouped: dict[str, list[ContentItem]],
    reports: list[ContentReport],
    items: list[ContentItem],
    window_name: str,
    blocked_reports: list[ContentReport],
) -> None:
    try:
        notifier = _get_notifier()
        if not notifier or not notifier.has_channels:
            return
        if blocked_reports:
            blocked_cats = ", ".join(report.category for report in blocked_reports)
            notifier.send_error(
                f"DailyNews 리포트 생성 실패: {len(blocked_reports)}건 blocked ({blocked_cats})",
                source="DailyNews",
            )
            return
        categories_done = ", ".join(grouped.keys())
        notifier.send_heartbeat(
            "DailyNews",
            status="alive",
            details=(
                f"window={window_name} | "
                f"카테고리={categories_done} | "
                f"리포트={len(reports)}건 | "
                f"아이템={len(items)}건"
            ),
        )
    except Exception as notifier_exc:
        logger.debug("Notifier send failed (ignored): %s", notifier_exc)
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
        state_store,
        adapters,
        llm_adapter,
        embedding_adapter,
        insight_adapter,
        sentiment_adapter,
        brain_adapter,
        proofreader_adapter,
        notebooklm_adapter,
        skill_adapter,
        reasoning_adapter,
        digest_adapter,
    )
    run_id = run_id or generate_run_id("generate_brief")

    with trace_context(run_id):
        grouped = _group_items_by_category(items)
        warnings: list[str] = []
        reports: list[ContentReport] = []

        # 빈 items 호출은 silent success가 되어 alive heartbeat만 가서 upstream
        # 수집 실패(피드 0건, 클러스터 필터 과도, signal_watch 트리거 미매칭 등)가
        # 묵음으로 묻힌다. warning을 추가해 status="partial"로 강등.
        if not items:
            warnings.append(
                f"generate_briefs called with no items for window {window_name}; "
                "no reports generated (upstream collect/signal/skill empty?)."
            )

        if stale_warning := _cleanup_stale_run_warning(state_store):
            warnings.append(stale_warning)

        state_store.record_job_start(
            run_id,
            "generate_brief",
            summary={"window_name": window_name, "categories": list(grouped), "max_items": len(items)},
        )

        cluster_meta, cluster_warnings = await build_cluster_meta(grouped, resolved.embedding)
        warnings.extend(cluster_warnings)

        for category, category_items in grouped.items():
            await _process_category(
                category,
                category_items,
                cluster_meta,
                window_name,
                window_start,
                window_end,
                state_store,
                run_id,
                resolved,
                reports,
                warnings,
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

        _send_generate_notifications(
            grouped=grouped,
            reports=reports,
            items=items,
            window_name=window_name,
            blocked_reports=blocked_reports,
        )

    return run_id, reports, warnings, "partial" if warnings else "ok"
