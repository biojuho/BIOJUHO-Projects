from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport, GeneratedPayload
from antigravity_mcp.integrations.embedding_adapter import ArticleCluster, EmbeddingAdapter
from antigravity_mcp.integrations.fact_check_adapter import FactCheckAdapter
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.integrations.llm_prompts import resolve_brief_style, resolve_prompt_mode
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def _is_concise_brief() -> bool:
    return resolve_brief_style() == "concise"


def _normalize_brief_body(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for prefix in ("핵심 사실:", "배경/디테일:", "전망/의미:"):
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
                break
        lines.append(line)
    return "\n".join(lines).strip()


@dataclass(slots=True)
class ReportAssemblyContext:
    category: str
    items: list[ContentItem]
    window_name: str
    window_start: str
    window_end: str
    state_store: PipelineStateStore
    report_id: str
    generation_mode: str
    fingerprint: str
    source_links: list[str]
    enriched_items: list[ContentItem]
    summary_lines: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    channel_drafts: list[ChannelDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notebooklm_metadata: dict[str, Any] = field(default_factory=dict)
    fact_check_score: float = 0.0
    quality_state: str = "ok"
    analysis_meta: dict[str, Any] = field(default_factory=dict)


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
    return re.sub(r"\s+", " ", text).strip().lower()


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


async def generate_base_payload(ctx: ReportAssemblyContext, llm_adapter: LLMAdapter) -> GeneratedPayload:
    if not ctx.enriched_items:
        # 빈 아이템으로 LLM 호출 방지 — 빈 페이로드 반환
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
        )
    except Exception as exc:
        # LLM 타임아웃/JSON 파싱 실패 등 — 파이프라인 크래시 대신 빈 페이로드로 graceful degradation
        logger.error(f"generate_base_payload LLM 호출 실패: {type(exc).__name__}: {exc}")
        ctx.warnings.append(f"LLM generation failed for {ctx.category}: {type(exc).__name__}")
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


async def apply_proofreading(ctx: ReportAssemblyContext, proofreader_adapter: Any | None) -> None:
    if not proofreader_adapter or not hasattr(proofreader_adapter, "proofread"):
        return
    try:
        ctx.summary_lines = [await proofreader_adapter.proofread(line) for line in ctx.summary_lines]
    except Exception as exc:
        ctx.warnings.append(f"Proofreading failed for {ctx.category}: {type(exc).__name__}")


async def _apply_sentiment_enrichment(ctx: ReportAssemblyContext, sentiment_adapter: Any | None) -> None:
    if not sentiment_adapter or not hasattr(sentiment_adapter, "analyze"):
        return
    try:
        titles = [item.title for item in ctx.items]
        results = await sentiment_adapter.analyze(titles)
        sentiment_meta: dict[str, Any] = {}
        sentiments = [result.sentiment for result in results if result.sentiment not in ("NEUTRAL", "Unknown")]
        if sentiments:
            from collections import Counter

            sentiment_meta["overall"] = Counter(sentiments).most_common(1)[0][0]
            sentiment_meta["count"] = len(sentiments)
        topics = []
        for result in results:
            topics.extend(topic for topic in result.topics if topic != "Unknown")
        sentiment_meta["entities"] = list(set(topics))[:5]
        ctx.analysis_meta["sentiment"] = sentiment_meta
    except Exception as exc:
        ctx.warnings.append(f"Sentiment analysis failed for {ctx.category}: {type(exc).__name__}")


async def _apply_brain_enrichment(ctx: ReportAssemblyContext, brain_adapter: Any | None) -> None:
    if not brain_adapter or not hasattr(brain_adapter, "analyze_news"):
        return
    try:
        articles_data = [{"title": item.title, "description": item.summary[:200]} for item in ctx.items]
        window_str = f"{ctx.window_start} ~ {ctx.window_end}"
        result = await brain_adapter.analyze_news(ctx.category, articles_data, window_str)
        if result:
            ctx.analysis_meta["brain"] = result
            if not _is_concise_brief():
                for insight in result.get("insights", [])[:3]:
                    ctx.insights.append(f"[{insight.get('topic', 'Issue')}] {insight.get('insight', '')}")
    except Exception as exc:
        ctx.warnings.append(f"Brain analysis failed for {ctx.category}: {type(exc).__name__}")


async def _apply_skill_enrichment(ctx: ReportAssemblyContext, skill_adapter: Any | None) -> None:
    if not skill_adapter or not hasattr(skill_adapter, "invoke"):
        return
    skill_meta: dict[str, Any] = {}
    market_categories = {"Economy_KR", "Economy_Global", "Crypto"}
    try:
        if ctx.category in market_categories:
            market_result = await skill_adapter.invoke(
                "market_snapshot",
                {"keywords": [item.title.split()[0] for item in ctx.items[:3]]},
            )
            if market_result.get("status") == "ok":
                skill_meta["market_snapshot"] = market_result.get("result", {})
                snapshots = skill_meta["market_snapshot"].get("snapshots", {})
                if not _is_concise_brief():
                    for ticker, snapshot in list(snapshots.items())[:2]:
                        if isinstance(snapshot, dict) and snapshot.get("price"):
                            ctx.insights.append(f"[Market] {ticker}: ${snapshot['price']}")
    except Exception as exc:
        ctx.warnings.append(f"Skill market_snapshot failed for {ctx.category}: {type(exc).__name__}")
    try:
        sentiment_result = await skill_adapter.invoke(
            "sentiment_classify",
            {"text": " ".join(item.title for item in ctx.items[:5])},
        )
        if sentiment_result.get("status") == "ok":
            skill_meta["sentiment"] = sentiment_result.get("result", {})
            label = skill_meta["sentiment"].get("sentiment") or skill_meta["sentiment"].get("label", "")
            if label and not _is_concise_brief():
                ctx.insights.append(f"[Skill Sentiment] {ctx.category}: {label}")
    except Exception as exc:
        ctx.warnings.append(f"Skill sentiment_classify failed for {ctx.category}: {type(exc).__name__}")
    if skill_meta:
        ctx.analysis_meta["skill"] = skill_meta


async def _apply_notebooklm_enrichment(ctx: ReportAssemblyContext, notebooklm_adapter: Any | None) -> None:
    if not notebooklm_adapter or not hasattr(notebooklm_adapter, "research_category"):
        return
    try:
        articles_data = [
            {"title": item.title, "description": item.summary[:200], "link": item.link} for item in ctx.items
        ]
        result = await notebooklm_adapter.research_category(
            category=ctx.category,
            articles=articles_data,
            extra_context="\n".join(ctx.insights) if ctx.insights else "",
            generate_infographic=True,
        )
        ctx.notebooklm_metadata = {
            "notebook_id": result.get("notebook_id", ""),
            "source_count": result.get("source_count", 0),
            "infographic_path": result.get("infographic_path", ""),
            "infographic_url": result.get("infographic_url", ""),
        }
        ctx.analysis_meta["notebooklm"] = result
        if not _is_concise_brief():
            for insight in result.get("research_insights", [])[:2]:
                ctx.insights.append(f"[Deep Research] {insight[:300]}")
            deep_summary = result.get("deep_summary", "")
            if deep_summary:
                ctx.insights.append(f"[NLM Synthesis] {deep_summary[:300]}")
    except Exception as exc:
        ctx.warnings.append(f"NotebookLM research failed for {ctx.category}: {type(exc).__name__}: {exc}")


async def _apply_reasoning_enrichment(ctx: ReportAssemblyContext, reasoning_adapter: Any | None) -> None:
    if not reasoning_adapter or not hasattr(reasoning_adapter, "run_full_reasoning"):
        return
    try:
        content_text = "\n".join(f"{item.title}: {item.summary[:200]}" for item in ctx.items)
        result = await reasoning_adapter.run_full_reasoning(
            report_id=ctx.report_id,
            category=ctx.category,
            content_text=content_text,
            source_title=f"{ctx.category} brief",
        )
        ctx.analysis_meta["reasoning"] = result
        if not _is_concise_brief():
            for pattern in result.get("new_patterns", [])[:2]:
                ctx.insights.append(f"[Reasoning] {pattern[:200]}")
    except Exception as exc:
        ctx.warnings.append(f"Reasoning failed for {ctx.category}: {type(exc).__name__}: {exc}")


def _override_x_draft(ctx: ReportAssemblyContext, content: str, *, source: str) -> None:
    original_x = next((draft.content for draft in ctx.channel_drafts if draft.channel == "x"), "")
    ctx.analysis_meta.setdefault("draft_overrides", {})
    ctx.analysis_meta["draft_overrides"]["x"] = source
    if original_x:
        ctx.analysis_meta["original_x_draft"] = original_x

    for draft in ctx.channel_drafts:
        if draft.channel == "x":
            draft.content = content
            draft.source = source
            draft.is_fallback = False
            return
    ctx.channel_drafts.append(
        ChannelDraft(
            channel="x",
            status="draft",
            content=content,
            source=source,
            is_fallback=False,
        )
    )


async def _apply_insight_enrichment(ctx: ReportAssemblyContext, insight_adapter: InsightAdapter | None) -> None:
    if not insight_adapter:
        return
    try:
        articles_data = [{"title": item.title, "summary": item.summary[:200], "link": item.link} for item in ctx.items]
        result = await insight_adapter.generate_insights(
            category=ctx.category,
            articles=articles_data,
            window_name=ctx.window_name,
            max_insights=4,
        )
        ctx.analysis_meta["insight_generator"] = {
            "validation_summary": result.get("validation_summary", {}),
            "full_items": result.get("insights", []),
            "error": result.get("error", ""),
        }
        if _is_concise_brief():
            x_long_form = result.get("x_long_form", "")
            if x_long_form:
                ctx.analysis_meta["insight_generator"]["x_long_form"] = x_long_form
            return
        for idx, insight in enumerate(result.get("insights", []), 1):
            if not insight.get("validation_passed", False):
                continue
            evidence_tag = str(insight.get("evidence_tag", "") or "").strip()
            content = (insight.get("content", "") or "").strip()
            if evidence_tag and evidence_tag not in content:
                content = f"{content} {evidence_tag}".strip()
            ctx.insights.append(f"[인사이트 {idx}] {content}")
        x_long_form = result.get("x_long_form", "")
        if x_long_form:
            ctx.analysis_meta["insight_generator"]["x_long_form"] = x_long_form
            _override_x_draft(ctx, x_long_form, source="insight_generator")
    except Exception as exc:
        ctx.warnings.append(f"DailyNews Insight Generator failed for {ctx.category}: {type(exc).__name__}: {exc}")


def _apply_topic_continuity(ctx: ReportAssemblyContext) -> None:
    continuing = ctx.state_store.find_continuing_topics(ctx.category, [item.title for item in ctx.items])
    if continuing:
        ctx.analysis_meta["continuity"] = continuing[:2]
        if _is_concise_brief():
            return
        for topic in continuing[:2]:
            ctx.insights.append(
                f"[Continuing] '{topic['topic_label'][:50]}' (seen {topic['occurrence_count']}x since {topic['first_seen_at'][:10]})"
            )


async def apply_enrichments(
    ctx: ReportAssemblyContext,
    *,
    sentiment_adapter: Any | None,
    brain_adapter: Any | None,
    skill_adapter: Any | None,
    notebooklm_adapter: Any | None,
    reasoning_adapter: Any | None,
    insight_adapter: InsightAdapter | None,
) -> None:
    await _apply_sentiment_enrichment(ctx, sentiment_adapter)
    await _apply_brain_enrichment(ctx, brain_adapter)
    await _apply_skill_enrichment(ctx, skill_adapter)
    await _apply_notebooklm_enrichment(ctx, notebooklm_adapter)
    await _apply_reasoning_enrichment(ctx, reasoning_adapter)
    await _apply_insight_enrichment(ctx, insight_adapter)
    _apply_topic_continuity(ctx)


def _has_generic_cta(text: str) -> bool:
    generic_terms = ("검토", "고려", "관심", "주목", "모니터링")
    if not any(term in text for term in generic_terms):
        return False
    return not bool(re.search(r"(오늘|이번|주|개월|30일|48시간|까지)", text))


def _collect_evidence_quality_warnings(parser_meta: dict[str, Any]) -> list[str]:
    if parser_meta.get("format") != "v2":
        return []
    evidence = parser_meta.get("evidence", {})
    warnings: list[str] = []
    missing_line_count = int(evidence.get("missing_line_count", 0) or 0)
    if missing_line_count:
        warnings.append(f"Evidence tags missing on {missing_line_count} analytic line(s).")
    line_count = int(evidence.get("line_count", 0) or 0)
    background_line_count = int(evidence.get("background_line_count", 0) or 0)
    if line_count and background_line_count > max(1, line_count // 2):
        warnings.append("Too many [Background] claims in base LLM analysis.")
    article_ref_count = int(evidence.get("article_ref_count", 0) or 0)
    if line_count and article_ref_count == 0:
        warnings.append("Base LLM analysis does not cite any direct article tags.")
    return warnings


def _quality_review_warnings(ctx: ReportAssemblyContext, draft_text: str, parser_meta: dict) -> list[str]:
    """CTA, 잘린 인사이트, 증거 품질 경고 수집."""
    warnings: list[str] = []
    if _has_generic_cta("\n".join(ctx.insights) + "\n" + draft_text):
        warnings.append("Generic CTA detected without timeframe.")
    if any("..." in insight for insight in ctx.insights):
        warnings.append("Truncated insight text detected.")
    warnings.extend(_collect_evidence_quality_warnings(parser_meta))
    return warnings


async def _run_fact_check(ctx: ReportAssemblyContext, draft_text: str, review_warnings: list[str]) -> None:
    """팩트 체크 실행 — 실패 시 무시, 결과를 ctx에 인플레이스 기록."""
    try:
        adapter = FactCheckAdapter()
        if not adapter.is_available():
            return
        result = await adapter.check_report(
            summary_lines=ctx.summary_lines,
            insights=ctx.insights,
            drafts_text=draft_text,
            source_articles=[
                {"title": item.title, "description": item.summary[:200], "source_name": item.source_name}
                for item in ctx.items
            ],
        )
        ctx.fact_check_score = result.get("fact_check_score", 0.0)
        ctx.analysis_meta["fact_check"] = result
        if not result.get("passed", True):
            review_warnings.extend(result.get("issues", [])[:3])
    except Exception as exc:
        logger.debug("Final fact-check skipped for %s: %s", ctx.category, exc)


async def finalize_quality(ctx: ReportAssemblyContext) -> None:
    draft_text = "\n".join(draft.content for draft in ctx.channel_drafts if draft.content)
    parser_meta = ctx.analysis_meta.get("parser", {})

    review_warnings = _quality_review_warnings(ctx, draft_text, parser_meta)
    await _run_fact_check(ctx, draft_text, review_warnings)

    has_fallback_draft = any(draft.channel == "x" and draft.is_fallback for draft in ctx.channel_drafts)
    insight_error = ctx.analysis_meta.get("insight_generator", {}).get("error", "")

    if parser_meta.get("used_fallback") or has_fallback_draft or (insight_error and not ctx.summary_lines):
        ctx.quality_state = "fallback"
    elif review_warnings or (ctx.fact_check_score and ctx.fact_check_score < 0.45):
        ctx.quality_state = "needs_review"
    else:
        ctx.quality_state = "ok"

    ctx.analysis_meta["quality_review"] = {"warnings": review_warnings, "evidence": parser_meta.get("evidence", {})}
    if review_warnings:
        ctx.warnings.extend(f"[Quality] {warning}" for warning in review_warnings)


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
