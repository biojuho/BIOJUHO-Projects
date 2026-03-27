"""External trigger API for n8n and other automation platforms.

Provides authenticated endpoints for external systems to:
- Trigger content generation and publishing
- Push trending topics for immediate posting
- Get system status for monitoring workflows
"""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Token-based auth for external triggers
EXTERNAL_API_TOKEN = os.getenv("EXTERNAL_API_TOKEN", "")


def verify_token(token: str) -> bool:
    """Verify the external API token."""
    if not EXTERNAL_API_TOKEN:
        logger.warning("EXTERNAL_API_TOKEN not set — external API disabled")
        return False
    return hmac.compare_digest(token, EXTERNAL_API_TOKEN)


# ---- Request/Response models ----


class TriggerPostRequest(BaseModel):
    """Request to trigger a post generation + publish."""

    topic: str
    caption: str | None = None
    hashtags: list[str] = []
    image_prompt: str | None = None
    image_url: str | None = None
    post_type: str = "IMAGE"
    publish_now: bool = False
    source: str = "n8n"  # Source identifier


class TriggerBatchRequest(BaseModel):
    """Request to trigger daily batch generation."""

    topics: list[str] = []
    count: int = 3
    source: str = "n8n"


class TrendPushRequest(BaseModel):
    """Push trending topics from external sources (e.g., GetDayTrends)."""

    trends: list[dict[str, Any]]
    source: str = "getdaytrends"
    auto_post: bool = False


class ExternalTriggerResult(BaseModel):
    """Standard response for external triggers."""

    success: bool
    action: str
    message: str
    data: dict[str, Any] = {}
    timestamp: str = ""

    def __init__(self, **kwargs):
        if "timestamp" not in kwargs or not kwargs["timestamp"]:
            kwargs["timestamp"] = datetime.now().isoformat()
        super().__init__(**kwargs)


# ---- Trigger handler ----


class ExternalTriggerHandler:
    """Handles external trigger requests."""

    def __init__(self, calendar, hashtag_db, ab_engine, db):
        self.calendar = calendar
        self.hashtag_db = hashtag_db
        self.ab_engine = ab_engine
        self.db = db
        self._trigger_log: list[dict] = []

    def log_trigger(self, action: str, source: str, details: str = "") -> None:
        """Log an external trigger event."""
        entry = {
            "action": action,
            "source": source,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self._trigger_log.append(entry)
        if len(self._trigger_log) > 200:
            self._trigger_log = self._trigger_log[-200:]
        logger.info("External trigger: %s from %s", action, source)

    def handle_post_trigger(self, req: TriggerPostRequest) -> ExternalTriggerResult:
        """Handle a single post trigger from external system."""
        self.log_trigger("post_trigger", req.source, req.topic)

        # Get optimized hashtags if none provided
        hashtags = req.hashtags
        if not hashtags:
            hashtags = self.hashtag_db.get_optimized_set(niche="tech", count=15)

        # Build caption
        caption = req.caption or req.topic
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        # Enqueue the post
        post_id = self.db.enqueue_post(
            caption=full_caption,
            image_url=req.image_url or "",
            post_type=req.post_type,
        )

        return ExternalTriggerResult(
            success=True,
            action="post_enqueued",
            message=f"Post enqueued (#{post_id}) from {req.source}",
            data={
                "post_id": post_id,
                "topic": req.topic,
                "hashtag_count": len(hashtags),
                "publish_now": req.publish_now,
            },
        )

    def handle_trend_push(self, req: TrendPushRequest) -> ExternalTriggerResult:
        """Handle trending topics push from GetDayTrends or similar."""
        self.log_trigger("trend_push", req.source, f"{len(req.trends)} trends")

        injected = 0
        today = datetime.now().strftime("%Y-%m-%d")

        for trend in req.trends[:5]:  # Max 5 trends
            topic = trend.get("topic") or trend.get("name", "")
            if topic:
                try:
                    self.calendar.inject_trend_topic(today, topic, posting_hour=15)
                    injected += 1
                except Exception as e:
                    logger.warning("Trend injection failed: %s", e)

        return ExternalTriggerResult(
            success=True,
            action="trends_injected",
            message=f"{injected} trends injected from {req.source}",
            data={
                "injected": injected,
                "total_received": len(req.trends),
            },
        )

    def get_status(self) -> dict:
        """Get status for external monitoring."""
        return {
            "service": "instagram-automation",
            "status": "operational",
            "calendar_stats": self.calendar.get_stats(),
            "hashtag_stats": self.hashtag_db.get_stats(),
            "active_experiments": len(self.ab_engine.get_active_experiments()),
            "recent_triggers": self._trigger_log[-10:],
            "timestamp": datetime.now().isoformat(),
        }
