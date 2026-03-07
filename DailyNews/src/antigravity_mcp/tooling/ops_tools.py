from __future__ import annotations

import logging

from antigravity_mcp.integrations.llm_adapter import _SHARED_LLM_IMPORT_ERROR, _get_llm_client
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.pipelines.dashboard import refresh_dashboard
from antigravity_mcp.state.events import error_response, ok, partial
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


async def ops_get_run_status_tool(run_id: str) -> dict:
    store = PipelineStateStore()
    run = store.get_run(run_id)
    if run is None:
        return error_response("run_not_found", f"Unknown run_id: {run_id}")
    return ok({"run": run.to_dict()})


async def ops_list_runs_tool(job_name: str = "", status: str = "", limit: int = 20) -> dict:
    store = PipelineStateStore()
    runs = store.list_runs(job_name=job_name or None, status=status or None, limit=limit)
    return ok({"runs": [run.to_dict() for run in runs]})


async def ops_refresh_dashboard_tool() -> dict:
    store = PipelineStateStore()
    run_id, payload, warnings, status = await refresh_dashboard(state_store=store)
    if status == "partial":
        return partial(payload, warnings=warnings, meta={"run_id": run_id})
    return ok(payload, meta={"run_id": run_id})


async def ops_cleanup_tool(dry_run: bool = False) -> dict:
    """Prune expired LLM cache entries and old article cache rows (30+ days).

    Pass dry_run=True to preview counts without deleting.
    """
    store = PipelineStateStore()
    if dry_run:
        return ok({"dry_run": True, "message": "No deletions performed in dry_run mode."})

    llm_pruned = store.prune_llm_cache()
    articles_pruned = store.prune_old_articles(days=30)
    return ok({
        "dry_run": False,
        "llm_cache_entries_pruned": llm_pruned,
        "article_cache_entries_pruned": articles_pruned,
    })


async def ops_check_health_tool(
    error_rate_threshold: float = 0.20,
    alert_on_silence_hours: int = 24,
) -> dict:
    """Check pipeline health and send Telegram alert if thresholds are exceeded.

    Args:
        error_rate_threshold: Alert if error rate exceeds this fraction (default 0.20 = 20%).
        alert_on_silence_hours: Alert if no runs in the last N hours (default 24).
    """
    store = PipelineStateStore()
    health = store.get_pipeline_health()
    llm_available = _get_llm_client is not None and _SHARED_LLM_IMPORT_ERROR is None

    alerts: list[str] = []

    error_rate = health.get("error_rate", 0.0)
    if error_rate > error_rate_threshold:
        alerts.append(
            f"Error rate {error_rate:.1%} exceeds threshold {error_rate_threshold:.1%} "
            f"({health.get('failure_count_24h', 0)} failures in last 24h)"
        )

    if health.get("total_runs_24h", 0) == 0:
        alerts.append(f"No pipeline runs recorded in the last {alert_on_silence_hours} hours.")

    if not llm_available:
        alerts.append("LLM is unavailable — reports are using deterministic fallback summaries.")

    if alerts:
        try:
            tg = TelegramAdapter()
            alert_text = "⚠️ <b>Pipeline Health Alert</b>\n" + "\n".join(f"• {a}" for a in alerts)
            sent = await tg.send_message(alert_text)
            if not sent:
                logger.warning("Telegram health alert was not delivered (token/chat_id missing?).")
        except Exception as exc:
            logger.warning("Failed to send Telegram health alert: %s", exc)

    return ok({
        "health": health,
        "llm_available": llm_available,
        "alerts": alerts,
        "status": "degraded" if alerts else "healthy",
    })
