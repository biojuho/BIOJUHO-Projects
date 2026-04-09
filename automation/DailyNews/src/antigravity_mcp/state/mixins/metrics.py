from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentReport, PipelineRun
from antigravity_mcp.state.base import _DBProviderBase
from antigravity_mcp.state.events import utc_now_iso

try:
    from shared.llm.config import MODEL_COSTS as _SHARED_MODEL_COSTS
except ImportError:
    _SHARED_MODEL_COSTS: dict[str, tuple[float, float]] = {}

_DEFAULT_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "deepseek-chat": (0.14, 0.28),
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash-preview-04-17": (0.0, 0.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3-mini-fast": (0.3, 0.5),
}
_MODEL_COSTS = {**_DEFAULT_MODEL_COSTS, **_SHARED_MODEL_COSTS}

def _estimate_cached_response_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_cost, output_cost = _MODEL_COSTS.get(model_name, (0.25, 1.25))
    return (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000

def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, set):
        return list(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


class _MetricsMixin(_DBProviderBase):
    """Methods for tracking X tweet performance metrics."""

    def upsert_tweet_metrics(
        self,
        *,
        tweet_id: str,
        report_id: str = "",
        content_preview: str = "",
        impressions: int = 0,
        likes: int = 0,
        retweets: int = 0,
        replies: int = 0,
        quotes: int = 0,
        bookmarks: int = 0,
        published_at: str = "",
    ) -> None:
        """Insert or update tweet metrics."""
        now = utc_now_iso()
        published = published_at or now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO x_tweet_metrics
                    (tweet_id, report_id, content_preview, impressions, likes,
                     retweets, replies, quotes, bookmarks, published_at, last_fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tweet_id) DO UPDATE SET
                    impressions = excluded.impressions,
                    likes = excluded.likes,
                    retweets = excluded.retweets,
                    replies = excluded.replies,
                    quotes = excluded.quotes,
                    bookmarks = excluded.bookmarks,
                    last_fetched_at = excluded.last_fetched_at
                """,
                (
                    tweet_id,
                    report_id,
                    content_preview[:200],
                    impressions,
                    likes,
                    retweets,
                    replies,
                    quotes,
                    bookmarks,
                    published,
                    now,
                ),
            )

    def get_tweet_metrics(self, tweet_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM x_tweet_metrics WHERE tweet_id = ?", (tweet_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_top_tweets(self, *, days: int = 30, limit: int = 10, sort_by: str = "impressions") -> list[dict[str, Any]]:
        """Return top-performing tweets sorted by a given metric."""
        valid_sorts = {"impressions", "likes", "retweets", "replies", "quotes", "bookmarks"}
        if sort_by not in valid_sorts:
            sort_by = "impressions"
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM x_tweet_metrics
                WHERE published_at >= ?
                ORDER BY {sort_by} DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_published_tweet_id(self, report_id: str, tweet_id: str, content_preview: str = "") -> None:
        """Record a published tweet ID for later metrics collection."""
        self.upsert_tweet_metrics(
            tweet_id=tweet_id,
            report_id=report_id,
            content_preview=content_preview,
        )

    def get_recent_tweet_ids(self, *, hours: int = 48) -> list[str]:
        """Return tweet IDs published within the given time window."""
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tweet_id FROM x_tweet_metrics WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            ).fetchall()
        return [row["tweet_id"] for row in rows]

    def get_metrics_summary(self, *, days: int = 7) -> dict[str, Any]:
        """Aggregate tweet metrics over the given period."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total_tweets,
                       SUM(impressions) AS total_impressions,
                       SUM(likes) AS total_likes,
                       SUM(retweets) AS total_retweets,
                       SUM(replies) AS total_replies,
                       AVG(impressions) AS avg_impressions,
                       AVG(likes) AS avg_likes
                FROM x_tweet_metrics
                WHERE published_at >= ?
                """,
                (cutoff,),
            ).fetchone()
        if row is None:
            return {"period_days": days, "total_tweets": 0}
        return {
            "period_days": days,
            "total_tweets": int(row["total_tweets"] or 0),
            "total_impressions": int(row["total_impressions"] or 0),
            "total_likes": int(row["total_likes"] or 0),
            "total_retweets": int(row["total_retweets"] or 0),
            "total_replies": int(row["total_replies"] or 0),
            "avg_impressions": round(float(row["avg_impressions"] or 0), 1),
            "avg_likes": round(float(row["avg_likes"] or 0), 1),
        }
