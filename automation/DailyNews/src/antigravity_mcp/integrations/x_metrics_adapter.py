"""X (Twitter) API v2 metrics collection adapter.

Fetches public engagement metrics for published tweets using the
Bearer token (app-only auth).

Required env var:
  X_BEARER_TOKEN  — needed for read-only lookups
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from antigravity_mcp.config import get_settings
from antigravity_mcp.integrations.x_token_store import load_token
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)

# X API v2 tweet fields for public metrics
_TWEET_FIELDS = "public_metrics,created_at,text"
_MAX_IDS_PER_REQUEST = 100  # X API limit


class XMetricsAdapter:
    """Collects tweet engagement metrics from X API v2."""

    def __init__(self, *, state_store: PipelineStateStore | None = None) -> None:
        self.settings = get_settings()
        self._state_store = state_store
        self._bearer_token = load_token("X_BEARER_TOKEN") or self.settings.x_bearer_token

    @property
    def is_available(self) -> bool:
        return bool(self._bearer_token)

    async def fetch_metrics(self, tweet_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch metrics for a batch of tweet IDs from X API v2.

        Returns a list of dicts with tweet_id, impressions, likes, retweets, etc.
        """
        if not self._bearer_token:
            logger.warning("X_BEARER_TOKEN not configured; cannot fetch metrics.")
            return []

        results: list[dict[str, Any]] = []

        # Process in batches of 100 (API limit)
        for i in range(0, len(tweet_ids), _MAX_IDS_PER_REQUEST):
            batch = tweet_ids[i : i + _MAX_IDS_PER_REQUEST]
            ids_param = ",".join(batch)

            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://api.twitter.com/2/tweets",
                        params={"ids": ids_param, "tweet.fields": _TWEET_FIELDS},
                        headers={"Authorization": f"Bearer {self._bearer_token}"},
                    )
                    if resp.status_code == 429:
                        logger.warning("X API rate limited during metrics fetch.")
                        break
                    resp.raise_for_status()
                    data = resp.json()

                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    results.append(
                        {
                            "tweet_id": tweet["id"],
                            "text": tweet.get("text", ""),
                            "created_at": tweet.get("created_at", ""),
                            "impressions": metrics.get("impression_count", 0),
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                            "quotes": metrics.get("quote_count", 0),
                            "bookmarks": metrics.get("bookmark_count", 0),
                        }
                    )
            except Exception as exc:
                logger.error("Failed to fetch X metrics for batch: %s", exc)

        return results

    async def collect_and_store(self, tweet_ids: list[str], report_id: str = "") -> int:
        """Fetch metrics and store them in the state store.

        Returns the number of tweets successfully updated.
        """
        if not self._state_store:
            logger.warning("No state_store provided; metrics not persisted.")
            return 0

        metrics_list = await self.fetch_metrics(tweet_ids)
        for m in metrics_list:
            self._state_store.upsert_tweet_metrics(
                tweet_id=m["tweet_id"],
                report_id=report_id,
                content_preview=m.get("text", "")[:200],
                impressions=m["impressions"],
                likes=m["likes"],
                retweets=m["retweets"],
                replies=m["replies"],
                quotes=m["quotes"],
                bookmarks=m["bookmarks"],
                published_at=m.get("created_at", ""),
            )
        return len(metrics_list)
