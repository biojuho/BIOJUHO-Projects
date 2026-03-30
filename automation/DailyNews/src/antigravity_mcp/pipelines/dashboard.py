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


def _cost_markdown(cost_stats: dict[str, object]) -> str:
    call_count = cost_stats.get("call_count", 0)
    cache_hits = cost_stats.get("cache_hit_count", 0)
    estimated = cost_stats.get("estimated_cost_usd", 0.0)
    avoided = cost_stats.get("estimated_cost_avoided_usd", 0.0)
    cost_by_model = cost_stats.get("cost_by_model", {})

    model_lines = "\n".join(
        f"  - {model}: ${cost:.6f}"
        for model, cost in (cost_by_model.items() if isinstance(cost_by_model, dict) else [])
    )
    if model_lines:
        model_lines = f"\n{model_lines}"

    hit_rate = f"{cache_hits / max(call_count, 1) * 100:.0f}%" if call_count else "N/A"

    return (
        "### LLM Cost (24h)\n"
        f"- API calls: {call_count} | Cache hits: {cache_hits} ({hit_rate})\n"
        f"- Estimated cost: ${estimated:.4f}\n"
        f"- Cost avoided (cache): ${avoided:.4f}{model_lines}\n"
    )


def _metrics_markdown(metrics_summary: dict[str, object]) -> str:
    total = metrics_summary.get("total_tweets", 0)
    if not total:
        return ""
    impressions = metrics_summary.get("total_impressions", 0)
    likes = metrics_summary.get("total_likes", 0)
    retweets = metrics_summary.get("total_retweets", 0)
    avg_imp = metrics_summary.get("avg_impressions", 0)
    avg_likes = metrics_summary.get("avg_likes", 0)
    days = metrics_summary.get("period_days", 7)
    return (
        f"### X Performance ({days}d)\n"
        f"- Tweets tracked: {total}\n"
        f"- Impressions: {impressions:,} (avg {avg_imp:.0f}/tweet)\n"
        f"- Likes: {likes:,} (avg {avg_likes:.1f}/tweet) | RT: {retweets:,}\n"
    )


def _governance_markdown(governance: dict[str, object]) -> str:
    quality_counts = governance.get("quality_counts", {})
    approval_counts = governance.get("approval_counts", {})
    fallback_x_drafts = governance.get("fallback_x_drafts", 0)
    considered = governance.get("reports_considered", 0)

    def _format_counts(value: object) -> str:
        if not isinstance(value, dict) or not value:
            return "none"
        return ", ".join(f"{key}={count}" for key, count in sorted(value.items()))

    return (
        "### Governance Snapshot\n"
        f"- Reports considered: {considered}\n"
        f"- Quality states: {_format_counts(quality_counts)}\n"
        f"- Approval states: {_format_counts(approval_counts)}\n"
        f"- Fallback X drafts: {fallback_x_drafts}\n"
    )


def _recent_reports_markdown(reports: list[dict[str, object]]) -> str:
    if not reports:
        return "### Recent Reports\n- No reports yet.\n"
    lines = [
        (
            f"- {report.get('category', 'unknown')} | {report.get('window_name', 'unknown')} | "
            f"quality={report.get('quality_state', 'ok')} | "
            f"mode={report.get('generation_mode', '') or 'unknown'} | "
            f"approval={report.get('approval_state', 'manual')}"
        )
        for report in reports
    ]
    return "### Recent Reports\n" + "\n".join(lines) + "\n"


def _dashboard_markdown(
    counts: dict[str, int],
    runs: list[dict[str, str]],
    reports: list[dict[str, object]],
    governance: dict[str, object],
    health: dict[str, object] | None = None,
    cost_stats: dict[str, object] | None = None,
    metrics_summary: dict[str, object] | None = None,
) -> str:
    run_lines = "\n".join(
        f"- {run['job_name']} | {run['status']} | {run['started_at']}"
        for run in runs
    ) or "- No recent runs."
    health_section = _health_markdown(health) if health else ""
    cost_section = _cost_markdown(cost_stats) if cost_stats else ""
    metrics_section = _metrics_markdown(metrics_summary) if metrics_summary else ""
    governance_section = _governance_markdown(governance)
    report_section = _recent_reports_markdown(reports)
    return (
        "## [AUTO_DASHBOARD] Antigravity Content Engine\n"
        f"- Reports stored: {counts['reports']}\n"
        f"- Pipeline runs tracked: {counts['runs']}\n"
        f"- Deduplicated articles: {counts['cached_articles']}\n"
        f"{health_section}"
        f"{cost_section}"
        f"{metrics_section}"
        f"{governance_section}"
        f"{report_section}"
        "### Recent Runs\n"
        f"{run_lines}\n"
        "### Governance\n"
        "- External publishing remains manual by default.\n"
        "- Reports marked needs_review or fallback should not be auto-published.\n"
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
    recent_reports = [report.to_dict() for report in state_store.list_reports(limit=5)]
    governance = state_store.get_report_governance_summary(limit=100)
    health = state_store.get_pipeline_health()
    cost_stats = state_store.get_token_usage_stats(hours=24)
    metrics_summary = state_store.get_metrics_summary(days=7)
    warnings: list[str] = []
    payload: dict[str, str | int | dict] = {
        "dashboard_page_id": settings.notion_dashboard_page_id,
        "reports": counts["reports"],
        "runs": counts["runs"],
        "cached_articles": counts["cached_articles"],
        "governance": governance,
        "recent_reports": recent_reports,
        "health": health,
        "cost_stats": cost_stats,
        "metrics_summary": metrics_summary,
    }

    if settings.notion_dashboard_page_id and notion_adapter.is_configured():
        appended = await notion_adapter.replace_auto_dashboard_blocks(
            page_id=settings.notion_dashboard_page_id,
            markdown=_dashboard_markdown(
                counts,
                recent_runs,
                recent_reports,
                governance,
                health,
                cost_stats,
                metrics_summary,
            ),
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
