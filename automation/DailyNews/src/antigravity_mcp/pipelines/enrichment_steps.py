from __future__ import annotations

from typing import Any
import logging

from antigravity_mcp.domain.models import ChannelDraft
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.pipelines.assembly_context import ReportAssemblyContext, _is_concise_brief

logger = logging.getLogger(__name__)

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
        x_long_form = result.get("x_long_form", "")
        if x_long_form:
            ctx.analysis_meta["insight_generator"]["x_long_form"] = x_long_form
            _override_x_draft(ctx, x_long_form, source="insight_generator")

        if _is_concise_brief():
            return
        for idx, insight in enumerate(result.get("insights", []), 1):
            if not insight.get("validation_passed", False):
                continue
            evidence_tag = str(insight.get("evidence_tag", "") or "").strip()
            content = (insight.get("content", "") or "").strip()
            if evidence_tag and evidence_tag not in content:
                content = f"{content} {evidence_tag}".strip()
            ctx.insights.append(f"[인사이트 {idx}] {content}")
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
    token_budget: Any | None = None,
) -> None:
    # Token budget awareness: auto-skip expensive enrichments when budget is tight
    minimize = False
    if token_budget is not None and hasattr(token_budget, "should_minimize"):
        minimize = token_budget.should_minimize()
        ctx.detail_level = token_budget.get_detail_level().value if hasattr(token_budget, "get_detail_level") else "minimal"
        ctx.analysis_meta["token_budget_state"] = {
            "should_minimize": minimize,
            "detail_level": ctx.detail_level,
            "usage_ratio": round(token_budget.usage_ratio, 3) if hasattr(token_budget, "usage_ratio") else None,
        }

    await _apply_sentiment_enrichment(ctx, sentiment_adapter)
    await _apply_brain_enrichment(ctx, brain_adapter)
    await _apply_skill_enrichment(ctx, skill_adapter)

    # Expensive enrichments: skip when token budget is tight
    if minimize:
        ctx.warnings.append(f"[TokenBudget] Skipping expensive enrichments for {ctx.category} (detail_level={ctx.detail_level})")
    else:
        await _apply_notebooklm_enrichment(ctx, notebooklm_adapter)
        await _apply_reasoning_enrichment(ctx, reasoning_adapter)

    await _apply_insight_enrichment(ctx, insight_adapter)
    _apply_topic_continuity(ctx)

