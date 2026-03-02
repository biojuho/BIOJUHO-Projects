from __future__ import annotations

from datetime import datetime

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.canva_adapter import CanvaAdapter
from antigravity_mcp.integrations.notion_adapter import NotionAdapter, NotionAdapterError
from antigravity_mcp.integrations.x_adapter import XAdapter
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore


def _report_markdown(report: ContentReport) -> str:
    summary_lines = "\n".join(f"- {line}" for line in report.summary_lines)
    insight_lines = "\n".join(f"- {line}" for line in report.insights)
    draft_lines = "\n\n".join(
        f"## {draft.channel.upper()}\n{draft.content}"
        for draft in report.channel_drafts
    )
    return (
        f"# {report.category} {report.window_name.title()} Brief\n"
        "## Summary\n"
        f"{summary_lines}\n"
        "## Insights\n"
        f"{insight_lines}\n"
        "## Drafts\n"
        f"{draft_lines}\n"
        "## Approval\n"
        f"- Approval mode: {report.approval_state}\n"
        f"- Asset status: {report.asset_status}"
    )


async def publish_report(
    *,
    report_id: str,
    channels: list[str],
    approval_mode: str,
    state_store: PipelineStateStore,
    notion_adapter: NotionAdapter | None = None,
    x_adapter: XAdapter | None = None,
    canva_adapter: CanvaAdapter | None = None,
    run_id: str | None = None,
) -> tuple[str, dict[str, str], list[str], str]:
    settings = get_settings()
    notion_adapter = notion_adapter or NotionAdapter(settings=settings)
    x_adapter = x_adapter or XAdapter()
    canva_adapter = canva_adapter or CanvaAdapter()
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

    if settings.content_approval_mode != "manual" and approval_mode != "manual":
        warnings.append("Automatic publishing is disabled. Falling back to manual approval.")
        approval_mode = "manual"

    if notion_adapter.is_configured() and settings.notion_reports_database_id:
        properties = {
            "Name": {"title": [{"type": "text", "text": {"content": f"{report.category} Brief {datetime.now().date()}"}}]},
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
            x_result = x_adapter.publish(report, draft.content, approval_mode=approval_mode)
            state_store.set_channel_publication(report_id, draft.channel, x_result["status"])
            publication[f"{draft.channel}_status"] = x_result["status"]
            if x_result.get("message"):
                warnings.append(x_result["message"])
        else:
            state_store.set_channel_publication(report_id, draft.channel, "draft")
            publication[f"{draft.channel}_status"] = "draft"

    report.status = "published" if report.notion_page_id else "draft"
    report.approval_state = approval_mode
    state_store.save_report(report)
    state_store.record_job_finish(
        run_id,
        status="partial" if warnings else "success",
        summary=publication,
        processed_count=1,
        published_count=1 if report.notion_page_id else 0,
    )
    return run_id, publication, warnings, "partial" if warnings else "ok"
