from __future__ import annotations

import logging
import re
from pathlib import Path

from antigravity_mcp.evals.frozen_eval import run_frozen_eval
from antigravity_mcp.integrations.llm_adapter import _SHARED_LLM_IMPORT_ERROR, _get_llm_client
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter
from antigravity_mcp.state.events import error_response, ok, partial, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


async def refresh_dashboard(*args, **kwargs):
    from antigravity_mcp.pipelines.dashboard import refresh_dashboard as _refresh_dashboard

    return await _refresh_dashboard(*args, **kwargs)


async def resync_report_publication(*args, **kwargs):
    from antigravity_mcp.pipelines.publish import resync_report_publication as _resync_report_publication

    return await _resync_report_publication(*args, **kwargs)


async def ops_get_run_status_tool(run_id: str) -> dict:
    store = PipelineStateStore()
    try:
        run = store.get_run(run_id)
        if run is None:
            return error_response("run_not_found", f"Unknown run_id: {run_id}")
        return ok({"run": run.to_dict()})
    finally:
        store.close()


async def ops_list_runs_tool(job_name: str = "", status: str = "", limit: int = 20) -> dict:
    store = PipelineStateStore()
    try:
        runs = store.list_runs(job_name=job_name or None, status=status or None, limit=limit)
        return ok({"runs": [run.to_dict() for run in runs]})
    finally:
        store.close()


async def ops_refresh_dashboard_tool() -> dict:
    store = PipelineStateStore()
    try:
        run_id, payload, warnings, status = await refresh_dashboard(state_store=store)
        if status == "partial":
            return partial(payload, warnings=warnings, meta={"run_id": run_id})
        return ok(payload, meta={"run_id": run_id})
    finally:
        store.close()


async def ops_resync_report_tool(report_id: str) -> dict:
    store = PipelineStateStore()
    try:
        run_id, payload, warnings, status = await resync_report_publication(
            report_id=report_id,
            state_store=store,
        )
        if status == "error":
            return error_response("report_not_found", f"Unknown report_id: {report_id}", data={"run_id": run_id})
        if status == "partial":
            return partial(payload, warnings=warnings, meta={"run_id": run_id})
        return ok(payload, meta={"run_id": run_id})
    finally:
        store.close()


def _extract_tweet_id(post_url: str) -> str:
    match = re.search(r"/status/(\d+)", post_url or "")
    return match.group(1) if match else ""


async def ops_record_manual_x_post_tool(report_id: str, post_url: str, posted_at: str = "") -> dict:
    """Record a manually published X post URL in local report/state metadata.

    This keeps ``content_reports.drafts_json`` and ``channel_publications`` in
    sync so later resync jobs do not overwrite the manual post URL.
    """
    normalized_url = str(post_url or "").strip()
    if not normalized_url:
        return error_response("post_url_missing", "post_url is required.")

    store = PipelineStateStore()
    try:
        report = store.get_report(report_id)
        if report is None:
            return error_response("report_not_found", f"Unknown report_id: {report_id}")

        x_draft = next((draft for draft in report.channel_drafts if draft.channel == "x"), None)
        if x_draft is None:
            return error_response("x_draft_not_found", f"Report {report_id} does not include an X draft.")

        x_draft.status = "published"
        x_draft.external_url = normalized_url

        report.analysis_meta = dict(report.analysis_meta or {})
        manual_meta = dict(report.analysis_meta.get("manual_update", {}))
        manual_meta["x_manual_publish_url"] = normalized_url
        manual_meta["x_manual_publish_recorded_at"] = utc_now_iso()
        if posted_at:
            manual_meta["x_manual_published_at"] = posted_at
        report.analysis_meta["manual_update"] = manual_meta

        store.save_report(report)
        store.set_channel_publication(report_id, "x", "published", normalized_url)

        tweet_id = _extract_tweet_id(normalized_url)
        if tweet_id:
            store.upsert_tweet_metrics(
                tweet_id=tweet_id,
                report_id=report_id,
                content_preview=x_draft.content[:200],
                published_at=posted_at,
            )

        return ok(
            {
                "report_id": report_id,
                "channel": "x",
                "status": "published",
                "post_url": normalized_url,
                "tweet_id": tweet_id,
                "posted_at": posted_at,
            }
        )
    finally:
        store.close()


async def ops_run_frozen_eval_tool(
    dataset_path: str = "",
    output_path: str = "",
    state_db_path: str = "",
) -> dict:
    try:
        result = await run_frozen_eval(
            dataset_path=Path(dataset_path) if dataset_path else None,
            output_path=Path(output_path) if output_path else None,
            state_db_path=Path(state_db_path) if state_db_path else None,
        )
    except FileNotFoundError as exc:
        return error_response("dataset_not_found", str(exc))
    except ValueError as exc:
        return error_response("invalid_dataset", str(exc))
    except Exception as exc:
        logger.exception("Frozen eval run failed: %s", exc)
        return error_response("frozen_eval_failed", f"Frozen eval failed: {exc}")

    warnings = list(result.get("warnings", []))
    meta = {
        "run_id": result.get("run_id", ""),
        "output_path": result.get("output_path", ""),
        "markdown_path": result.get("markdown_path", ""),
    }
    if warnings:
        return partial(result, warnings=warnings, meta=meta)
    return ok(result, meta=meta)


async def ops_cleanup_tool(dry_run: bool = False) -> dict:
    """Prune expired LLM cache entries and old article cache rows (30+ days).

    Pass dry_run=True to preview counts without deleting.
    """
    store = PipelineStateStore()
    try:
        if dry_run:
            return ok({"dry_run": True, "message": "No deletions performed in dry_run mode."})

        llm_pruned = store.prune_llm_cache()
        articles_pruned = store.prune_old_articles(days=30)
        return ok(
            {
                "dry_run": False,
                "llm_cache_entries_pruned": llm_pruned,
                "article_cache_entries_pruned": articles_pruned,
            }
        )
    finally:
        store.close()


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

    return ok(
        {
            "health": health,
            "llm_available": llm_available,
            "alerts": alerts,
            "status": "degraded" if alerts else "healthy",
        }
    )


async def ops_auto_collect_metrics_tool(hours: int = 48) -> dict:
    """Automatically fetch and store metrics for all recently published tweets.

    No tweet_ids needed — discovers them from the state store.
    """
    from antigravity_mcp.pipelines.metrics import collect_recent_metrics

    store = PipelineStateStore()
    try:
        run_id, count, warnings = await collect_recent_metrics(state_store=store, hours=hours)
        payload = {"run_id": run_id, "tweets_updated": count, "hours_window": hours}
        if warnings:
            return partial(payload, warnings=warnings, meta={"run_id": run_id})
        return ok(payload, meta={"run_id": run_id})
    finally:
        store.close()


async def ops_collect_tweet_metrics_tool(tweet_ids: list[str], report_id: str = "") -> dict:
    """Fetch and store engagement metrics for published tweets.

    Requires X_BEARER_TOKEN to be configured.
    """
    store = PipelineStateStore()
    try:
        adapter = XMetricsAdapter(state_store=store)
        if not adapter.is_available:
            return error_response(
                "x_bearer_missing",
                "X_BEARER_TOKEN not configured. Cannot fetch tweet metrics.",
            )
        count = await adapter.collect_and_store(tweet_ids, report_id=report_id)
        return ok({"tweets_updated": count, "tweet_ids": tweet_ids})
    finally:
        store.close()


async def ops_get_cost_report_tool(days: int = 7) -> dict:
    """Get LLM cost breakdown by model for the last N days."""
    store = PipelineStateStore()
    try:
        stats = store.get_token_usage_stats(hours=days * 24)
        try:
            from shared.llm import export_usage_csv, get_daily_stats

            daily = get_daily_stats(days=days)
            stats["daily_breakdown"] = daily
        except ImportError:
            pass
        return ok(stats)
    finally:
        store.close()


async def ops_export_analytics_tool(date: str = "", days: int = 30) -> dict:
    """Export daily report JSON and tweet performance CSV."""
    from antigravity_mcp.pipelines.export import export_daily_report_json, export_performance_csv

    store = PipelineStateStore()
    try:
        json_result = export_daily_report_json(date=date, state_store=store)
        csv_result = export_performance_csv(days=days, state_store=store)
        return ok(
            {
                "json_export": json_result,
                "csv_export": csv_result,
            }
        )
    finally:
        store.close()


async def ops_get_content_calendar_tool(days: int = 7) -> dict:
    """Get optimal posting times for the next N days."""
    from antigravity_mcp.integrations.scheduler_adapter import SchedulerAdapter

    store = PipelineStateStore()
    try:
        scheduler = SchedulerAdapter(state_store=store)
        optimal = scheduler.get_optimal_hours(count=6)
        should_post = scheduler.should_post_now()
        next_slot = scheduler.get_next_posting_slot()
        return ok(
            {
                "optimal_hours_today": optimal,
                "should_post_now": should_post,
                "next_slot": next_slot,
            }
        )
    finally:
        store.close()


async def ops_get_tweet_performance_tool(days: int = 7, limit: int = 10, sort_by: str = "impressions") -> dict:
    """Get top-performing tweets and aggregate metrics summary."""
    store = PipelineStateStore()
    try:
        top_tweets = store.get_top_tweets(days=days, limit=limit, sort_by=sort_by)
        summary = store.get_metrics_summary(days=days)
        return ok(
            {
                "summary": summary,
                "top_tweets": top_tweets,
            }
        )
    finally:
        store.close()
