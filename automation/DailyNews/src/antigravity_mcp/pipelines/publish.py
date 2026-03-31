from __future__ import annotations

import logging
from datetime import datetime

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.canva_adapter import CanvaAdapter
from antigravity_mcp.integrations.notion_adapter import NotionAdapter, NotionAdapterError
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.integrations.x_adapter import XAdapter
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def _styled_brief_markdown(report: ContentReport) -> str:
    brief_body = str((report.analysis_meta or {}).get("brief_body", "") or "").strip()
    if not brief_body:
        return ""

    x_draft = next((draft.content for draft in report.channel_drafts if draft.channel == "x"), "")
    lines = [
        f"# {report.category} {report.window_name.title()} Brief",
        brief_body,
    ]
    if x_draft:
        lines.extend(
            [
                "## X Draft",
                x_draft,
            ]
        )
    lines.extend(
        [
            "## Approval",
            f"- Approval mode: {report.approval_state}",
            f"- Quality state: {report.quality_state}",
        ]
    )
    return "\n".join(lines)


def _analysis_meta_markdown(report: ContentReport) -> str:
    meta = report.analysis_meta or {}
    parser = meta.get("parser", {})
    quality_review = meta.get("quality_review", {})
    fact_check = meta.get("fact_check", {})
    insight_generator = meta.get("insight_generator", {})
    draft_overrides = meta.get("draft_overrides", {})

    lines = ["## Analysis Meta"]
    if parser:
        lines.append(f"- Parser fallback used: {'yes' if parser.get('used_fallback') else 'no'}")
        missing_sections = parser.get("missing_sections") or []
        if missing_sections:
            lines.append(f"- Missing sections: {', '.join(str(item) for item in missing_sections)}")
        evidence = parser.get("evidence", {})
        if evidence:
            lines.append(
                "- Evidence tags: "
                f"{evidence.get('tagged_line_count', 0)}/{evidence.get('line_count', 0)} analytic lines tagged"
            )
            if evidence.get("article_refs"):
                lines.append(
                    "- Direct article refs: " + ", ".join(str(item) for item in evidence.get("article_refs", []))
                )
    if draft_overrides:
        lines.append(
            "- Draft overrides: "
            + ", ".join(f"{channel}={source}" for channel, source in sorted(draft_overrides.items()))
        )
    if insight_generator:
        summary = insight_generator.get("validation_summary", {})
        if summary:
            lines.append(
                "- Insight validation: "
                f"passed={summary.get('passed', 0)} / failed={summary.get('failed', 0)} / total={summary.get('total_insights', 0)}"
            )
        if insight_generator.get("error"):
            lines.append(f"- Insight generator error: {insight_generator['error']}")
    if fact_check:
        lines.append(
            "- Fact check: "
            f"passed={'yes' if fact_check.get('passed', False) else 'no'}, "
            f"score={fact_check.get('fact_check_score', report.fact_check_score):.2f}"
        )
    warnings = quality_review.get("warnings", [])
    if warnings:
        lines.append("- Quality warnings:")
        lines.extend(f"  - {warning}" for warning in warnings[:5])
    return "\n".join(lines)


def _report_markdown(report: ContentReport) -> str:
    if report.generation_mode == "v1-brief":
        styled = _styled_brief_markdown(report)
        if styled:
            return styled

    summary_lines = "\n".join(f"- {line}" for line in report.summary_lines)
    insight_lines = "\n".join(f"- {line}" for line in report.insights)
    draft_lines = "\n\n".join(
        f"## {draft.channel.upper()}\n"
        f"- Source: {draft.source}\n"
        f"- Fallback: {'yes' if draft.is_fallback else 'no'}\n\n"
        f"{draft.content}"
        for draft in report.channel_drafts
    )
    return (
        f"# {report.category} {report.window_name.title()} Brief\n"
        "## Generation\n"
        f"- Generation mode: {report.generation_mode or 'unknown'}\n"
        f"- Quality state: {report.quality_state}\n"
        "## Summary\n"
        f"{summary_lines}\n"
        "## Insights\n"
        f"{insight_lines}\n"
        "## Drafts\n"
        f"{draft_lines}\n"
        f"{_analysis_meta_markdown(report)}\n"
        "## Approval\n"
        f"- Approval mode: {report.approval_state}\n"
        f"- Asset status: {report.asset_status}"
    )


def _build_telegram_message(report: ContentReport, publication: dict[str, str]) -> str:
    notion_url = publication.get("notion_url", "")
    summary = report.summary_lines[0] if report.summary_lines else "No summary."
    link_part = f'\n<a href="{notion_url}">Notion에서 보기</a>' if notion_url else ""
    return f"<b>[{report.category}] {report.window_name.title()} Brief 발행됨</b>\n" f"{summary}{link_part}"


def _has_notion_page_id(report: ContentReport) -> bool:
    return report.has_notion_sync()


async def publish_report(
    *,
    report_id: str,
    channels: list[str],
    approval_mode: str,
    state_store: PipelineStateStore,
    notion_adapter: NotionAdapter | None = None,
    x_adapter: XAdapter | None = None,
    canva_adapter: CanvaAdapter | None = None,
    telegram_adapter: TelegramAdapter | None = None,
    run_id: str | None = None,
) -> tuple[str, dict[str, str], list[str], str]:
    settings = get_settings()
    notion_adapter = notion_adapter or NotionAdapter(settings=settings)
    x_adapter = x_adapter or XAdapter(state_store=state_store)
    canva_adapter = canva_adapter or CanvaAdapter()
    telegram_adapter = telegram_adapter or TelegramAdapter()
    run_id = run_id or generate_run_id("publish_report")
    state_store.record_job_start(
        run_id,
        "publish_report",
        summary={"report_id": report_id, "channels": channels, "approval_mode": approval_mode},
    )

    report = state_store.get_report(report_id)
    if report is None:
        state_store.record_job_finish(run_id, status="failed", error_text=f"Unknown report_id: {report_id}")
        return run_id, {}, [f"Unknown report_id: {report_id}"], "error"

    warnings: list[str] = []
    publication: dict[str, str] = {"report_id": report_id}

    if settings.content_approval_mode == "manual" and approval_mode != "manual":
        warnings.append("Automatic publishing is disabled. Falling back to manual approval.")
        approval_mode = "manual"

    if report.quality_state == "blocked":
        warnings.append(
            "Publishing blocked: report was generated by fallback template due to total LLM failure. "
            "Manual review required."
        )
        state_store.record_job_finish(
            run_id, status="blocked", summary={"report_id": report_id, "reason": "quality_blocked"}
        )
        return run_id, {"report_id": report_id, "blocked": True}, warnings, "error"

    fallback_x_draft = any(draft.channel == "x" and draft.is_fallback for draft in report.channel_drafts)
    if approval_mode == "auto" and (report.quality_state != "ok" or fallback_x_draft):
        warnings.append(
            "Auto publishing downgraded to manual because the report quality state is not ok "
            "or the X draft is a fallback draft."
        )
        approval_mode = "manual"

    if notion_adapter.is_configured() and settings.notion_reports_database_id:
        properties = {
            "Name": {
                "title": [{"type": "text", "text": {"content": f"{report.category} Brief {datetime.now().date()}"}}]
            },
            "Date": {"date": {"start": datetime.now().date().isoformat()}},
        }
        try:
            created = await notion_adapter.create_record(
                database_id=settings.notion_reports_database_id,
                properties=properties,
                markdown=_report_markdown(report),
            )
            report.notion_page_id = created.get("id", "")
            publication["notion_page_id"] = report.notion_page_id
            publication["notion_url"] = created.get("url", "")
        except NotionAdapterError as exc:
            warnings.append(str(exc))
    else:
        warnings.append("Notion reports database is not configured; report saved only to local state.")

    canva_result = canva_adapter.create_draft(report)
    publication["canva_status"] = canva_result.get("status", "disabled")
    if canva_result.get("edit_url"):
        publication["canva_edit_url"] = canva_result["edit_url"]

    for draft in report.channel_drafts:
        if draft.channel not in channels:
            continue
        if draft.channel == "x":
            # Auto-detect thread mode: if content > 280 chars, split into thread
            if len(draft.content) > 280 and approval_mode == "auto":
                thread_tweets = XAdapter.split_to_thread(draft.content)
                thread_results = await x_adapter.post_thread(thread_tweets)
                published_ids = [r["tweet_id"] for r in thread_results if r.get("status") == "published"]
                if published_ids:
                    x_status = "published"
                    publication["x_thread_ids"] = ",".join(published_ids)
                    publication["x_url"] = f"https://twitter.com/i/web/status/{published_ids[0]}"
                    for tid in published_ids:
                        state_store.record_published_tweet_id(report_id, tid, draft.content[:200])
                else:
                    x_status = thread_results[0].get("status", "error") if thread_results else "error"
                    if thread_results and thread_results[0].get("message"):
                        warnings.append(thread_results[0]["message"])
                state_store.set_channel_publication(report_id, draft.channel, x_status)
                publication[f"{draft.channel}_status"] = x_status
            else:
                x_result = await x_adapter.publish(report, draft.content, approval_mode=approval_mode)
                state_store.set_channel_publication(report_id, draft.channel, x_result["status"])
                publication[f"{draft.channel}_status"] = x_result["status"]
                if x_result.get("tweet_url"):
                    publication["x_url"] = x_result["tweet_url"]
                    # Extract tweet ID from URL for metrics tracking
                    tweet_url = x_result["tweet_url"]
                    if "/status/" in tweet_url:
                        tid = tweet_url.rsplit("/status/", 1)[-1].split("?")[0]
                        state_store.record_published_tweet_id(report_id, tid, draft.content[:200])
                if x_result.get("message"):
                    warnings.append(x_result["message"])
        else:
            state_store.set_channel_publication(report_id, draft.channel, "draft")
            publication[f"{draft.channel}_status"] = "draft"

    # Send Telegram notification after publishing
    try:
        tg_message = _build_telegram_message(report, publication)
        await telegram_adapter.send_message(tg_message)
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)

    report.status = "published" if _has_notion_page_id(report) else "draft"
    publication["report_status"] = report.status
    publication["report_delivery_state"] = report.delivery_state
    report.approval_state = approval_mode
    state_store.save_report(report)
    state_store.record_job_finish(
        run_id,
        status="partial" if warnings else "success",
        summary=publication,
        processed_count=1,
        published_count=1 if _has_notion_page_id(report) else 0,
    )
    return run_id, publication, warnings, "partial" if warnings else "ok"
