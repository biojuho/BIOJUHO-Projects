from __future__ import annotations

from antigravity_mcp.config import get_settings
from antigravity_mcp.integrations.notion_adapter import NotionAdapter
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore


def _dashboard_markdown(counts: dict[str, int], runs: list[dict[str, str]]) -> str:
    run_lines = "\n".join(
        f"- {run['job_name']} | {run['status']} | {run['started_at']}"
        for run in runs
    ) or "- No recent runs."
    return (
        "## [AUTO_DASHBOARD] Antigravity Content Engine\n"
        f"- Reports stored: {counts['reports']}\n"
        f"- Pipeline runs tracked: {counts['runs']}\n"
        f"- Deduplicated articles: {counts['cached_articles']}\n"
        "### Recent Runs\n"
        f"{run_lines}\n"
        "### Governance\n"
        "- External publishing remains manual by default.\n"
        "- Notion is the system of record for curated reports.\n"
        "---"
    )


async def refresh_dashboard(
    *,
    state_store: PipelineStateStore,
    notion_adapter: NotionAdapter | None = None,
    run_id: str | None = None,
) -> tuple[str, dict[str, str | int], list[str], str]:
    settings = get_settings()
    run_id = run_id or generate_run_id("refresh_dashboard")
    notion_adapter = notion_adapter or NotionAdapter(settings=settings)
    state_store.record_job_start(run_id, "refresh_dashboard")

    counts = state_store.report_counts()
    recent_runs = [run.to_dict() for run in state_store.list_runs(limit=5)]
    warnings: list[str] = []
    payload = {
        "dashboard_page_id": settings.notion_dashboard_page_id,
        "reports": counts["reports"],
        "runs": counts["runs"],
        "cached_articles": counts["cached_articles"],
    }

    if settings.notion_dashboard_page_id and notion_adapter.is_configured():
        appended = await notion_adapter.replace_auto_dashboard_blocks(
            page_id=settings.notion_dashboard_page_id,
            markdown=_dashboard_markdown(counts, recent_runs),
        )
        payload["updated_blocks"] = appended
    else:
        warnings.append("Dashboard page or Notion API is not configured; local metrics only.")

    state_store.record_job_finish(
        run_id,
        status="partial" if warnings else "success",
        summary=payload,
        processed_count=len(recent_runs),
        published_count=1 if payload.get("updated_blocks") else 0,
    )
    return run_id, payload, warnings, "partial" if warnings else "ok"
