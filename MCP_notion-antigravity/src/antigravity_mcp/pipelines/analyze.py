from __future__ import annotations

import hashlib
from collections import defaultdict

from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore


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
) -> tuple[str, list[ContentReport], list[str], str]:
    llm_adapter = llm_adapter or LLMAdapter()
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

        report_id = generate_run_id(f"report-{category.lower().replace(' ', '-')}")
        payload, llm_warnings = await llm_adapter.build_report_payload(
            category=category,
            items=category_items,
            window_name=window_name,
        )
        summary_lines, insights, drafts = payload
        warnings.extend(llm_warnings)
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
