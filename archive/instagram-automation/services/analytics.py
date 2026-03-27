"""Instagram performance analytics.

Collects Insights data from Meta API and generates performance reports.
Feeds back into content strategy for optimization.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from config import AppConfig
from models import PostInsights

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Analyze Instagram performance and generate insights."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._db = None
        self._meta_api = None

    def _get_db(self):
        if self._db is None:
            from services.database import Database
            self._db = Database(self.config.db_path)
        return self._db

    def _get_meta_api(self):
        if self._meta_api is None:
            from services.meta_api import MetaGraphAPI
            self._meta_api = MetaGraphAPI(self.config.meta)
        return self._meta_api

    async def collect_all_insights(self) -> int:
        """Collect insights for all published posts without recent data."""
        db = self._get_db()
        api = self._get_meta_api()
        published = db.get_published_posts(limit=50)
        collected = 0

        for post in published:
            if not post.media_id:
                continue
            try:
                metrics = await api.get_media_insights(post.media_id)
                # Also get like/comment counts from media object
                media_data = await api.get(
                    f"/{post.media_id}",
                    fields="like_count,comments_count",
                )

                insights = PostInsights(
                    media_id=post.media_id,
                    impressions=metrics.get("impressions", 0),
                    reach=metrics.get("reach", 0),
                    engagement=metrics.get("engagement", 0),
                    likes=media_data.get("like_count", 0),
                    comments=media_data.get("comments_count", 0),
                    saved=metrics.get("saved", 0),
                    shares=metrics.get("shares", 0),
                )
                db.save_insights(insights)
                collected += 1
            except Exception as e:
                logger.warning(
                    "Failed to collect insights for %s: %s",
                    post.media_id,
                    e,
                )

        logger.info("Collected insights for %d/%d posts", collected, len(published))
        return collected

    def get_performance_summary(self, days: int = 30) -> dict:
        """Generate a performance summary for the last N days."""
        db = self._get_db()
        published = db.get_published_posts(limit=100)

        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            p for p in published if p.published_at and p.published_at > cutoff
        ]

        if not recent:
            return {"period_days": days, "total_posts": 0}

        # Aggregate metrics
        total_reach = 0
        total_engagement = 0
        total_impressions = 0
        post_metrics = []

        for post in recent:
            if not post.media_id:
                continue
            insights_list = db.get_insights_for_post(post.media_id)
            if not insights_list:
                continue
            latest = insights_list[0]
            total_reach += latest.reach
            total_engagement += latest.engagement
            total_impressions += latest.impressions
            post_metrics.append(
                {
                    "media_id": post.media_id,
                    "type": post.post_type.value,
                    "reach": latest.reach,
                    "engagement": latest.engagement,
                    "engagement_rate": latest.engagement_rate,
                    "saved": latest.saved,
                    "published_at": post.published_at.isoformat()
                    if post.published_at
                    else None,
                }
            )

        # Sort by engagement rate
        post_metrics.sort(key=lambda x: x["engagement_rate"], reverse=True)

        avg_engagement_rate = 0.0
        if total_reach > 0:
            avg_engagement_rate = (total_engagement / total_reach) * 100

        return {
            "period_days": days,
            "total_posts": len(recent),
            "total_reach": total_reach,
            "total_impressions": total_impressions,
            "total_engagement": total_engagement,
            "avg_engagement_rate": round(avg_engagement_rate, 2),
            "top_posts": post_metrics[:5],
            "worst_posts": post_metrics[-3:] if len(post_metrics) > 3 else [],
        }

    def get_best_posting_time(self) -> dict[int, float]:
        """Analyze which posting hours perform best.

        Returns: {hour: avg_engagement_rate}
        """
        db = self._get_db()
        published = db.get_published_posts(limit=100)

        hour_data: dict[int, list[float]] = defaultdict(list)

        for post in published:
            if not post.published_at or not post.media_id:
                continue
            hour = post.published_at.hour
            insights_list = db.get_insights_for_post(post.media_id)
            if insights_list:
                hour_data[hour].append(insights_list[0].engagement_rate)

        return {
            hour: round(sum(rates) / len(rates), 2)
            for hour, rates in sorted(hour_data.items())
            if rates
        }

    def get_best_content_type(self) -> dict[str, float]:
        """Analyze which content types perform best.

        Returns: {post_type: avg_engagement_rate}
        """
        db = self._get_db()
        published = db.get_published_posts(limit=100)

        type_data: dict[str, list[float]] = defaultdict(list)

        for post in published:
            if not post.media_id:
                continue
            insights_list = db.get_insights_for_post(post.media_id)
            if insights_list:
                type_data[post.post_type.value].append(
                    insights_list[0].engagement_rate
                )

        return {
            ptype: round(sum(rates) / len(rates), 2)
            for ptype, rates in type_data.items()
            if rates
        }

    def generate_report_text(self, days: int = 7) -> str:
        """Generate a human-readable performance report."""
        summary = self.get_performance_summary(days)
        best_times = self.get_best_posting_time()
        best_types = self.get_best_content_type()

        lines = [
            f"Instagram Performance Report ({days}d)",
            f"{'=' * 40}",
            f"Total Posts: {summary['total_posts']}",
            f"Total Reach: {summary.get('total_reach', 0):,}",
            f"Total Impressions: {summary.get('total_impressions', 0):,}",
            f"Avg Engagement Rate: {summary.get('avg_engagement_rate', 0):.2f}%",
            "",
        ]

        if best_times:
            lines.append("Best Posting Times:")
            for hour, rate in sorted(
                best_times.items(), key=lambda x: x[1], reverse=True
            )[:3]:
                lines.append(f"  {hour:02d}:00 -> {rate:.2f}% engagement")
            lines.append("")

        if best_types:
            lines.append("Best Content Types:")
            for ptype, rate in sorted(
                best_types.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {ptype}: {rate:.2f}% engagement")
            lines.append("")

        top_posts = summary.get("top_posts", [])
        if top_posts:
            lines.append("Top 3 Posts:")
            for i, p in enumerate(top_posts[:3], 1):
                lines.append(
                    f"  {i}. {p['media_id']} "
                    f"(reach={p['reach']:,}, eng={p['engagement_rate']:.1f}%)"
                )

        return "\n".join(lines)
