from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport, GeneratedPayload
from antigravity_mcp.integrations.embedding_adapter import ArticleCluster, EmbeddingAdapter
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.integrations.llm_prompts import resolve_prompt_mode
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

from antigravity_mcp.pipelines.assembly_context import ReportAssemblyContext, _normalize_brief_body
from antigravity_mcp.pipelines.enrichment_steps import apply_enrichments, apply_proofreading
from antigravity_mcp.pipelines.qa_steps import finalize_quality

logger = logging.getLogger(__name__)

def _coerce_generated_payload(
    payload: GeneratedPayload | tuple[list[str], list[str], list[ChannelDraft]],
    *,
    generation_mode: str,
) -> GeneratedPayload:
    if isinstance(payload, GeneratedPayload):
        if not payload.generation_mode:
            payload.generation_mode = generation_mode
        return payload
    summary_lines, insights, channel_drafts = payload
    return GeneratedPayload(
        summary_lines=list(summary_lines),
        insights=list(insights),
        channel_drafts=list(channel_drafts),
        generation_mode=generation_mode,
        parse_meta={"used_fallback": False, "missing_sections": [], "sections_found": {}},
        quality_state="ok",
    )


def _normalize_text_for_fingerprint(text: str) -> str:
    # Strip Jina deep context so fingerprint stays stable across re-runs
    base = text.split("\n\n[Deep Context (Jina.ai)]")[0] if "[Deep Context (Jina.ai)]" in text else text
    return re.sub(r"\s+", " ", base).strip().lower()


def build_report_fingerprint(
    category: str,
    window_name: str,
    generation_mode: str,
    items: list[ContentItem],
) -> str:
    digest = hashlib.sha256()
    digest.update(category.encode("utf-8"))
    digest.update(window_name.encode("utf-8"))
    digest.update(generation_mode.encode("utf-8"))
    for item in sorted(items, key=lambda value: (value.link, value.title)):
        digest.update(_normalize_text_for_fingerprint(item.title).encode("utf-8"))
        digest.update(_normalize_text_for_fingerprint(item.summary).encode("utf-8"))
        digest.update(item.link.encode("utf-8"))
    return digest.hexdigest()


async def build_cluster_meta(
    grouped: dict[str, list[ContentItem]],
    embedding_adapter: EmbeddingAdapter,
) -> tuple[dict[str, list[ArticleCluster]], list[str]]:
    warnings: list[str] = []
    cluster_meta: dict[str, list[ArticleCluster]] = {}
    if not embedding_adapter.is_available:
        return cluster_meta, warnings

    for category, category_items in grouped.items():
        try:
            clusters = await embedding_adapter.cluster_articles(category_items)
            cluster_meta[category] = clusters
            multi_source = [cluster for cluster in clusters if cluster.is_multi_source]
            if multi_source:
                warnings.append(
                    f"{category}: {len(multi_source)} multi-source topic(s) detected "
                    f"({', '.join(cluster.topic_label[:40] for cluster in multi_source[:3])})"
                )
        except Exception as exc:
            logger.warning("Clustering failed for %s: %s", category, exc)
    return cluster_meta, warnings


def prepare_category_batch(
    *,
    category: str,
    category_items: list[ContentItem],
    cluster_meta: dict[str, list[ArticleCluster]],
    window_name: str,
    window_start: str,
    window_end: str,
    state_store: PipelineStateStore,
) -> tuple[ReportAssemblyContext, ContentReport | None]:
    generation_mode = resolve_prompt_mode(window_name, len(category_items))
    fingerprint = build_report_fingerprint(category, window_name, generation_mode, category_items)
    existing = state_store.find_report_by_fingerprint(fingerprint)

    enriched_items = category_items
    clusters = cluster_meta.get(category)
    if clusters:
        ordered: list[ContentItem] = []
        for cluster in clusters:
            ordered.extend(cluster.articles)
        enriched_items = ordered if ordered else category_items

    ctx = ReportAssemblyContext(
        category=category,
        items=category_items,
        window_name=window_name,
        window_start=window_start,
        window_end=window_end,
        state_store=state_store,
        report_id=generate_run_id(f"report-{category.lower().replace(' ', '-')}"),
        generation_mode=generation_mode,
        fingerprint=fingerprint,
        source_links=[item.link for item in category_items],
        enriched_items=enriched_items,
        analysis_meta={"generation_mode": generation_mode},
    )
    return ctx, existing


async def generate_base_payload(
    ctx: ReportAssemblyContext,
    llm_adapter: LLMAdapter,
    *,
    quality_feedback: dict[str, Any] | None = None,
    overlapping_drafts: list[str] | None = None,
) -> GeneratedPayload:
    if not ctx.enriched_items:
        logger.warning("generate_base_payload: enriched_items 비어있음, LLM 호출 스킵")
        ctx.warnings.append(f"No enriched items for {ctx.category}")
        return GeneratedPayload(
            summary_lines=[], insights=[], channel_drafts=[],
            generation_mode=ctx.generation_mode,
            parse_meta={"used_fallback": True, "missing_sections": [], "sections_found": {}},
            quality_state="empty",
        )
    try:
        payload, warnings = await llm_adapter.build_report_payload(
            category=ctx.category,
            items=ctx.enriched_items,
            window_name=ctx.window_name,
            quality_feedback=quality_feedback,
            overlapping_drafts=overlapping_drafts,
        )
    except Exception as exc:
        # LLM 타임아웃/JSON 파싱 실패 등 — 파이프라인 크래시 대신 빈 페이로드로 graceful degradation
        logger.error(f"generate_base_payload LLM 호출 실패: {type(exc).__name__}: {exc}")
        ctx.warnings.append(f"LLM generation failed for {ctx.category}: {type(exc).__name__}")
        # Notifier 연동 (약결합, fire-and-forget)
        try:
            from shared.notifications import Notifier
            notifier = Notifier.from_env()
            if notifier.has_channels:
                notifier.send_error(
                    f"DailyNews LLM 호출 실패 ({ctx.category}): {type(exc).__name__}",
                    error=exc,
                    source="DailyNews",
                )
        except Exception:
            pass
        return GeneratedPayload(
            summary_lines=[], insights=[], channel_drafts=[],
            generation_mode=ctx.generation_mode,
            parse_meta={"used_fallback": True, "missing_sections": [], "sections_found": {}},
            quality_state="llm_error",
        )
    payload = _coerce_generated_payload(payload, generation_mode=ctx.generation_mode)
    ctx.warnings.extend(warnings)
    ctx.summary_lines = getattr(payload, "summary_lines", None) or []
    ctx.insights = getattr(payload, "insights", None) or []
    ctx.channel_drafts = getattr(payload, "channel_drafts", None) or []
    ctx.generation_mode = payload.generation_mode or ctx.generation_mode
    ctx.quality_state = getattr(payload, "quality_state", "ok") or "ok"
    ctx.analysis_meta["parser"] = getattr(payload, "parse_meta", {}) or {}
    brief_body = _normalize_brief_body(str((ctx.analysis_meta["parser"]).get("brief_body", "") or ""))
    if brief_body:
        payload.parse_meta["brief_body"] = brief_body
        ctx.analysis_meta["parser"]["brief_body"] = brief_body
        ctx.analysis_meta["brief_body"] = brief_body
    return payload


def persist_report(ctx: ReportAssemblyContext) -> ContentReport:
    report = ContentReport(
        report_id=ctx.report_id,
        category=ctx.category,
        window_name=ctx.window_name,
        window_start=ctx.window_start,
        window_end=ctx.window_end,
        summary_lines=ctx.summary_lines,
        insights=ctx.insights,
        channel_drafts=ctx.channel_drafts,
        asset_status="draft",
        approval_state="manual",
        source_links=ctx.source_links,
        status="draft",
        fingerprint=ctx.fingerprint,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        notebooklm_metadata=ctx.notebooklm_metadata,
        fact_check_score=ctx.fact_check_score,
        generation_mode=ctx.generation_mode,
        quality_state=ctx.quality_state,
        analysis_meta=ctx.analysis_meta,
    )
    ctx.state_store.save_report(report)
    return report


def maybe_enqueue_digest(
    *,
    ctx: ReportAssemblyContext,
    report: ContentReport,
    digest_adapter: Any | None,
) -> None:
    if not digest_adapter or not hasattr(digest_adapter, "enqueue"):
        return
    try:
        digest_adapter.enqueue(report.report_id)
    except Exception as exc:
        ctx.warnings.append(f"Digest enqueue failed for {ctx.category}: {type(exc).__name__}")


def record_topics_and_articles(
    *,
    ctx: ReportAssemblyContext,
    cluster_meta: dict[str, list[ArticleCluster]],
    run_id: str,
) -> None:
    for cluster in cluster_meta.get(ctx.category, []):
        topic_id = hashlib.sha256(f"{ctx.category}:{cluster.topic_label}".encode()).hexdigest()[:16]
        ctx.state_store.upsert_topic(
            topic_id=topic_id,
            topic_label=cluster.topic_label,
            category=ctx.category,
            report_id=ctx.report_id,
        )

    for item in ctx.items:
        ctx.state_store.record_article(
            link=item.link,
            source=item.source_name,
            category=item.category,
            window_name=ctx.window_name,
            notion_page_id=None,
            run_id=run_id,
        )
