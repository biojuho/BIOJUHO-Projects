from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Any

from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations.embedding_adapter import ArticleCluster, EmbeddingAdapter
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def build_report_fingerprint(category: str, window_name: str, source_links: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(category.encode("utf-8"))
    digest.update(window_name.encode("utf-8"))
    for link in sorted(source_links):
        digest.update(link.encode("utf-8"))
    return digest.hexdigest()


async def generate_briefs(
    *,
    items: list[ContentItem],
    window_name: str,
    window_start: str,
    window_end: str,
    state_store: PipelineStateStore,
    llm_adapter: LLMAdapter | None = None,
    run_id: str | None = None,
    # --- Phase 3: Enhanced pipeline hooks (all optional, backward-compatible) ---
    sentiment_adapter: Any | None = None,
    brain_adapter: Any | None = None,
    proofreader_adapter: Any | None = None,
    embedding_adapter: EmbeddingAdapter | None = None,
    # --- Phase 4: NotebookLM deep research (optional) ---
    notebooklm_adapter: Any | None = None,
    # --- Phase 5: Skill auto-invocation (optional) ---
    skill_adapter: Any | None = None,
    # --- Phase 6: DailyNews Insight Generator (optional) ---
    insight_adapter: Any | None = None,
) -> tuple[str, list[ContentReport], list[str], str]:
    llm_adapter = llm_adapter or LLMAdapter(state_store=state_store)
    embedding_adapter = embedding_adapter or EmbeddingAdapter()
    run_id = run_id or generate_run_id("generate_brief")
    grouped: dict[str, list[ContentItem]] = defaultdict(list)
    for item in items:
        grouped[item.category].append(item)

    warnings: list[str] = []
    reports: list[ContentReport] = []

    # Auto-clean zombie runs before starting new one (watchdog)
    cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
    if cleaned:
        warnings.append(f"Auto-cleaned {cleaned} stale run(s) stuck in 'running' state.")

    state_store.record_job_start(
        run_id,
        "generate_brief",
        summary={"window_name": window_name, "categories": list(grouped), "max_items": len(items)},
    )

    # --- Clustering: group similar articles within each category ---
    cluster_meta: dict[str, list[ArticleCluster]] = {}
    if embedding_adapter.is_available:
        for category, category_items in grouped.items():
            try:
                clusters = await embedding_adapter.cluster_articles(category_items)
                cluster_meta[category] = clusters
                multi_source = [c for c in clusters if c.is_multi_source]
                if multi_source:
                    warnings.append(
                        f"{category}: {len(multi_source)} multi-source topic(s) detected "
                        f"({', '.join(c.topic_label[:40] for c in multi_source[:3])})"
                    )
            except Exception as exc:
                logger.warning("Clustering failed for %s: %s", category, exc)

    for category, category_items in grouped.items():
        source_links = [item.link for item in category_items]
        fingerprint = build_report_fingerprint(category, window_name, source_links)
        existing = state_store.find_report_by_fingerprint(fingerprint)
        if existing:
            reports.append(existing)
            warnings.append(f"Reused existing report for {category}.")
            continue

        # --- Sentiment analysis (optional) ---
        sentiment_meta: dict[str, Any] = {}
        if sentiment_adapter and hasattr(sentiment_adapter, "analyze"):
            try:
                titles = [item.title for item in category_items]
                results = await sentiment_adapter.analyze(titles)
                sentiments = [r.sentiment for r in results if r.sentiment not in ("NEUTRAL", "Unknown")]
                if sentiments:
                    from collections import Counter
                    sentiment_meta["overall"] = Counter(sentiments).most_common(1)[0][0]
                    sentiment_meta["count"] = len(sentiments)
                all_topics = []
                for r in results:
                    all_topics.extend(t for t in r.topics if t != "Unknown")
                sentiment_meta["entities"] = list(set(all_topics))[:5]
            except Exception as exc:
                warnings.append(f"Sentiment analysis failed for {category}: {type(exc).__name__}")

        report_id = generate_run_id(f"report-{category.lower().replace(' ', '-')}")

        # Enrich items with cluster context if available
        enriched_items = category_items
        clusters = cluster_meta.get(category)
        if clusters:
            # Re-order: put multi-source cluster articles first for higher priority
            ordered: list[ContentItem] = []
            for c in clusters:
                ordered.extend(c.articles)
            enriched_items = ordered if ordered else category_items

        payload, llm_warnings = await llm_adapter.build_report_payload(
            category=category,
            items=enriched_items,
            window_name=window_name,
        )
        summary_lines, insights, drafts = payload
        warnings.extend(llm_warnings)

        # --- Proofreading (optional) ---
        if proofreader_adapter and hasattr(proofreader_adapter, "proofread"):
            try:
                proofed = []
                for line in summary_lines:
                    proofed.append(await proofreader_adapter.proofread(line))
                summary_lines = proofed
            except Exception as exc:
                warnings.append(f"Proofreading failed for {category}: {type(exc).__name__}")

        # --- Brain analysis (optional) ---
        brain_analysis: dict[str, Any] | None = None
        if brain_adapter and hasattr(brain_adapter, "analyze_news"):
            try:
                articles_data = [
                    {"title": item.title, "description": item.summary[:200]}
                    for item in category_items
                ]
                window_str = f"{window_start} ~ {window_end}"
                brain_analysis = await brain_adapter.analyze_news(category, articles_data, window_str)
                if brain_analysis:
                    # Merge brain insights into the report
                    brain_insights = brain_analysis.get("insights", [])
                    for bi in brain_insights[:3]:
                        insights.append(f"[{bi.get('topic', 'Issue')}] {bi.get('insight', '')}")
            except Exception as exc:
                warnings.append(f"Brain analysis failed for {category}: {type(exc).__name__}")

        # --- Skill auto-invocation (optional) ---
        if skill_adapter and hasattr(skill_adapter, "invoke"):
            _MARKET_CATEGORIES = {"Economy_KR", "Economy_Global", "Crypto"}
            try:
                if category in _MARKET_CATEGORIES:
                    market_result = await skill_adapter.invoke(
                        "market_snapshot",
                        {"keywords": [item.title.split()[0] for item in category_items[:3]]},
                    )
                    if market_result.get("status") == "ok":
                        snapshots = market_result.get("result", {}).get("snapshots", {})
                        for ticker, snap in list(snapshots.items())[:2]:
                            if isinstance(snap, dict) and snap.get("price"):
                                insights.append(f"[Market] {ticker}: ${snap['price']}")
            except Exception as exc:
                warnings.append(f"Skill market_snapshot failed for {category}: {type(exc).__name__}")
            try:
                summary_text = " ".join(item.title for item in category_items[:5])
                sentiment_result = await skill_adapter.invoke(
                    "sentiment_classify",
                    {"text": summary_text},
                )
                if sentiment_result.get("status") == "ok":
                    skill_sentiment = sentiment_result.get("result", {})
                    if isinstance(skill_sentiment, dict):
                        label = skill_sentiment.get("sentiment") or skill_sentiment.get("label", "")
                        if label:
                            insights.append(f"[Skill Sentiment] {category}: {label}")
            except Exception as exc:
                warnings.append(f"Skill sentiment_classify failed for {category}: {type(exc).__name__}")

        # --- NotebookLM deep research (optional) ---
        notebooklm_meta: dict[str, Any] = {}
        if notebooklm_adapter and hasattr(notebooklm_adapter, "research_category"):
            try:
                articles_data = [
                    {"title": item.title, "description": item.summary[:200], "link": item.link}
                    for item in category_items
                ]
                extra_ctx = "\n".join(insights) if insights else ""
                nlm_result = await notebooklm_adapter.research_category(
                    category=category,
                    articles=articles_data,
                    extra_context=extra_ctx,
                    generate_infographic=True,
                )
                notebooklm_meta = {
                    "notebook_id": nlm_result.get("notebook_id", ""),
                    "source_count": nlm_result.get("source_count", 0),
                    "infographic_path": nlm_result.get("infographic_path", ""),
                    "infographic_url": nlm_result.get("infographic_url", ""),
                }
                # Merge deep research insights into report
                for ri in nlm_result.get("research_insights", [])[:2]:
                    insights.append(f"[Deep Research] {ri[:300]}")
                deep_summary = nlm_result.get("deep_summary", "")
                if deep_summary:
                    insights.append(f"[NLM Synthesis] {deep_summary[:300]}")
                logger.info("NotebookLM enriched %s: %d insights", category, len(nlm_result.get("research_insights", [])))
            except Exception as exc:
                warnings.append(f"NotebookLM research failed for {category}: {type(exc).__name__}: {exc}")

        # --- PIL fallback infographic (when NotebookLM infographic missing) ---
        if not notebooklm_meta.get("infographic_path"):
            try:
                from antigravity_mcp.integrations.canva_adapter import CanvaAdapter
                canva = CanvaAdapter()
                if hasattr(canva, "generate_infographic"):
                    fallback_path = canva.generate_infographic(
                        category=category,
                        summary_lines=summary_lines[:3],
                        insight=insights[0] if insights else "",
                    )
                    if fallback_path:
                        notebooklm_meta.setdefault("infographic_path", str(fallback_path))
                        logger.info("PIL fallback infographic: %s", fallback_path)
            except Exception as exc:
                logger.debug("PIL fallback infographic skipped: %s", exc)

        # --- Fact-check verification (optional) ---
        fact_check_score = 0.0
        try:
            from antigravity_mcp.integrations.fact_check_adapter import FactCheckAdapter
            fc = FactCheckAdapter()
            if fc.is_available():
                drafts_text = "\n".join(d.content for d in drafts if d.content)
                source_articles = [
                    {"title": item.title, "description": item.summary[:200], "source_name": item.source_name}
                    for item in category_items
                ]
                fc_result = await fc.check_report(
                    summary_lines=summary_lines,
                    insights=insights,
                    drafts_text=drafts_text,
                    source_articles=source_articles,
                )
                fact_check_score = fc_result.get("fact_check_score", 0.0)
                if not fc_result.get("passed", True):
                    fc_issues = fc_result.get("issues", [])
                    for issue in fc_issues[:3]:
                        warnings.append(f"[FactCheck] {issue}")
        except Exception as exc:
            logger.debug("Fact-check skipped for %s: %s", category, exc)

        # --- DailyNews Insight Generator (optional) ---
        insight_report_x_form = ""
        if insight_adapter and hasattr(insight_adapter, "generate_insight_report"):
            try:
                articles_data = [
                    {"title": item.title, "summary": item.summary[:200], "link": item.link}
                    for item in category_items
                ]
                insight_summaries, insight_items, x_long_form = await insight_adapter.generate_insight_report(
                    category=category,
                    articles=articles_data,
                    window_name=window_name,
                )
                # Merge DailyNews insights into report
                for insight_item in insight_items[:3]:
                    insights.append(insight_item)
                # Store X long-form separately for later publishing
                insight_report_x_form = x_long_form
                logger.info("DailyNews Insight Generator enriched %s: %d insights", category, len(insight_items))
            except Exception as exc:
                warnings.append(f"DailyNews Insight Generator failed for {category}: {type(exc).__name__}: {exc}")

        # --- Topic continuity detection ---
        current_titles = [item.title for item in category_items]
        continuing = state_store.find_continuing_topics(category, current_titles)
        if continuing:
            for ct in continuing[:2]:
                insights.append(
                    f"[Continuing] '{ct['topic_label'][:50]}' (seen {ct['occurrence_count']}x since {ct['first_seen_at'][:10]})"
                )

        report = ContentReport(
            report_id=report_id,
            category=category,
            window_name=window_name,
            window_start=window_start,
            window_end=window_end,
            summary_lines=summary_lines,
            insights=insights,
            channel_drafts=drafts,
            asset_status="draft",
            approval_state="manual",
            source_links=source_links,
            status="draft",
            fingerprint=fingerprint,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
            notebooklm_metadata=notebooklm_meta,
            fact_check_score=fact_check_score,
        )
        state_store.save_report(report)

        # Record topics from clusters for future continuity tracking
        clusters = cluster_meta.get(category, [])
        for cluster in clusters:
            topic_id = hashlib.sha256(
                f"{category}:{cluster.topic_label}".encode("utf-8")
            ).hexdigest()[:16]
            state_store.upsert_topic(
                topic_id=topic_id,
                topic_label=cluster.topic_label,
                category=category,
                report_id=report_id,
            )
        for item in category_items:
            state_store.record_article(
                link=item.link,
                source=item.source_name,
                category=item.category,
                window_name=window_name,
                notion_page_id=None,
                run_id=run_id,
            )
        reports.append(report)

    state_store.record_job_finish(
        run_id,
        status="partial" if warnings else "success",
        summary={"report_ids": [report.report_id for report in reports], "window_name": window_name},
        processed_count=len(items),
        published_count=0,
    )
    return run_id, reports, warnings, "partial" if warnings else "ok"
