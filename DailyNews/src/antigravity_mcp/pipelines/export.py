"""Analytics export pipeline — structured JSON and CSV exports."""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def export_daily_report_json(
    *,
    date: str = "",
    output_dir: Path | None = None,
    state_store: PipelineStateStore | None = None,
) -> dict[str, Any]:
    """Export all reports, metrics, and costs for a given date as structured JSON.

    Args:
        date: Date string (YYYY-MM-DD). Defaults to today UTC.
        output_dir: Directory to write the JSON file. Defaults to settings output dir.

    Returns:
        Summary dict with file_path and counts.
    """
    store = state_store or PipelineStateStore()
    settings = get_settings()
    output_dir = output_dir or settings.output_dir

    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"daily_report_{date}.json"

    # Collect data
    runs = store.list_runs(limit=100)
    day_runs = [r.to_dict() for r in runs if r.started_at.startswith(date)]
    token_stats = store.get_token_usage_stats(hours=24)
    metrics_summary = store.get_metrics_summary(days=1)
    top_tweets = store.get_top_tweets(days=1, limit=10)
    health = store.get_pipeline_health()

    export_data = {
        "date": date,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_runs": day_runs,
        "token_usage": token_stats,
        "tweet_metrics": {
            "summary": metrics_summary,
            "top_tweets": top_tweets,
        },
        "health": health,
    }

    file_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported daily report to %s", file_path)

    return {
        "file_path": str(file_path),
        "date": date,
        "runs_count": len(day_runs),
        "tweets_count": metrics_summary.get("total_tweets", 0),
    }


def export_performance_csv(
    *,
    days: int = 30,
    output_path: Path | None = None,
    state_store: PipelineStateStore | None = None,
) -> dict[str, Any]:
    """Export tweet performance metrics as CSV.

    Returns:
        Summary dict with file_path and row count.
    """
    store = state_store or PipelineStateStore()
    settings = get_settings()
    output_path = output_path or settings.output_dir / f"tweet_performance_{days}d.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    top_tweets = store.get_top_tweets(days=days, limit=500, sort_by="impressions")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "tweet_id", "report_id", "impressions", "likes",
            "retweets", "replies", "quotes", "bookmarks",
            "published_at", "content_preview",
        ])
        for tw in top_tweets:
            writer.writerow([
                tw.get("tweet_id", ""),
                tw.get("report_id", ""),
                tw.get("impressions", 0),
                tw.get("likes", 0),
                tw.get("retweets", 0),
                tw.get("replies", 0),
                tw.get("quotes", 0),
                tw.get("bookmarks", 0),
                tw.get("published_at", ""),
                tw.get("content_preview", "")[:100],
            ])

    logger.info("Exported %d tweet metrics to %s", len(top_tweets), output_path)
    return {"file_path": str(output_path), "rows": len(top_tweets), "days": days}
