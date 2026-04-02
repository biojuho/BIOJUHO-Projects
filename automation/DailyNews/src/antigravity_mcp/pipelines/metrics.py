"""Automated tweet metrics collection pipeline.

Fetches engagement metrics for recently published tweets and stores
them in the state store for performance analysis.
"""

from __future__ import annotations

import logging

from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


async def collect_recent_metrics(
    *,
    state_store: PipelineStateStore | None = None,
    hours: int = 48,
    run_id: str | None = None,
) -> tuple[str, int, list[str]]:
    """Fetch and store metrics for tweets published in the last *hours*.

    Returns (run_id, tweets_updated, warnings).
    """
    store = state_store or PipelineStateStore()
    owns_store = state_store is None
    try:
        run_id = run_id or generate_run_id("collect_metrics")
        warnings: list[str] = []

        store.record_job_start(run_id, "collect_metrics", summary={"hours": hours})

        tweet_ids = store.get_recent_tweet_ids(hours=hours)
        if not tweet_ids:
            store.record_job_finish(
                run_id,
                status="success",
                summary={"tweets_updated": 0, "reason": "no_recent_tweets"},
            )
            return run_id, 0, []

        adapter = XMetricsAdapter(state_store=store)
        if not adapter.is_available:
            warnings.append("X_BEARER_TOKEN not configured; skipping metrics collection.")
            store.record_job_finish(
                run_id,
                status="partial",
                summary={"tweets_updated": 0},
                error_text="no_bearer_token",
            )
            return run_id, 0, warnings

        try:
            count = await adapter.collect_and_store(tweet_ids)
        except Exception as exc:
            warnings.append(f"Metrics collection failed: {type(exc).__name__}: {exc}")
            store.record_job_finish(run_id, status="failed", error_text=str(exc))
            return run_id, 0, warnings

        store.record_job_finish(
            run_id,
            status="success",
            summary={"tweets_updated": count, "tweet_ids_checked": len(tweet_ids)},
            processed_count=len(tweet_ids),
        )
        return run_id, count, warnings
    finally:
        if owns_store:
            store.close()
