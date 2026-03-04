from __future__ import annotations

from antigravity_mcp.config import get_settings
from antigravity_mcp.integrations.notion_adapter import NotionAdapter
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore


def _health_markdown(health: dict[str, object]) -> str:
    last_run = health.get("last_run_at") or "N/A"
    last_status = health.get("last_run_status") or "N/A"
    success = health.get("success_count_24h", 0)
    failure = health.get("failure_count_24h", 0)
    total = health.get("total_runs_24h", 0)
    latency = health.get("avg_latency_seconds")
    latency_str = f"{latency}s" if latency is not None else "N/A"
    error_rate = health.get("error_rate", 0)
    error_pct = f"{error_rate * 100:.1f}%"
    return (
        "### Pipeline Health (24h)\n"
        f"- Last run: {last_run} ({last_status})\n"
        f"- Runs: {total} total | {success} success | {failure} failed\n"
        f"- Avg latency: {latency_str}\n"
        f"- Error rate: {error_pct}\n"
    )


def _dashboard_markdown(counts: dict[str, int], runs: list[dict[str, str]], health: dict[str, object] | None = None) -> str:
    run_lines = "\n".join(
        f"- {run['job_name']} | {run['status']} | {run['started_at']}"
        for run in runs
    ) or "- No recent runs."
    health_section = _health_markdown(health) if health else ""
    return (
        "## [AUTO_DASHBOARD] Antigravity Content Engine\n"
        f"- Reports stored: {counts['reports']}\n"
        f"- Pipeline runs tracked: {counts['runs']}\n"
        f"- Deduplicated articles: {counts['cached_articles']}\n"
        f"{health_section}"
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
    health = state_store.get_pipeline_health()
    warnings: list[str] = []
    payload: dict[str, str | int | dict] = {
        "dashboard_page_id": settings.notion_dashboard_page_id,
        "reports": counts["reports"],
        "runs": counts["runs"],
        "cached_articles": counts["cached_articles"],
        "health": health,
    }

    if settings.notion_dashboard_page_id and notion_adapter.is_configured():
        appended = await notion_adapter.replace_auto_dashboard_blocks(
            page_id=settings.notion_dashboard_page_id,
            markdown=_dashboard_markdown(counts, recent_runs, health),
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
