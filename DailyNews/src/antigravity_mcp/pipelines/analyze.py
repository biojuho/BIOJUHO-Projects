from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Any

from antigravity_mcp.domain.models import ContentItem, ContentReport
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
) -> tuple[str, list[ContentReport], list[str], str]:
    llm_adapter = llm_adapter or LLMAdapter(state_store=state_store)
    run_id = run_id or generate_run_id("generate_brief")
    grouped: dict[str, list[ContentItem]] = defaultdict(list)
    for item in items:
        grouped[item.category].append(item)

    warnings: list[str] = []
    reports: list[ContentReport] = []
    state_store.record_job_start(
        run_id,
        "generate_brief",
        summary={"window_name": window_name, "categories": list(grouped), "max_items": len(items)},
    )

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
        payload, llm_warnings = await llm_adapter.build_report_payload(
            category=category,
            items=category_items,
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
        )
        state_store.save_report(report)
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
