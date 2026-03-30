"""Post scheduling and automated publishing engine.

Manages the content queue and publishes posts at optimal times.
Uses APScheduler for cron-like job scheduling.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import AppConfig
from models import PostStatus

logger = logging.getLogger(__name__)


class PostScheduler:
    """Manages the post queue and triggers publishing."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._meta_api = None
        self._db = None
        self._content_gen = None
        self._analytics = None
        self._notifier = None

    def _get_meta_api(self):
        if self._meta_api is None:
            from services.meta_api import MetaGraphAPI

            self._meta_api = MetaGraphAPI(self.config.meta)
        return self._meta_api

    def _get_db(self):
        if self._db is None:
            from services.database import Database

            self._db = Database(self.config.db_path)
        return self._db

    def _get_content_gen(self):
        if self._content_gen is None:
            from services.content_generator import ContentGenerator

            self._content_gen = ContentGenerator(self.config.content)
        return self._content_gen

    def _get_notifier(self):
        if self._notifier is None:
            try:
                from shared.notifications import Notifier

                self._notifier = Notifier.from_env()
            except Exception:
                self._notifier = None
        return self._notifier

    async def publish_next(self) -> bool:
        """Publish the next post in the queue if due."""
        db = self._get_db()

        # Check daily post limit
        today_count = db.get_post_count_today()
        if today_count >= self.config.scheduler.max_posts_per_day:
            logger.info("Daily post limit reached (%d)", today_count)
            return False

        post = db.get_next_scheduled()
        if post is None:
            logger.debug("No posts due for publishing")
            return False

        api = self._get_meta_api()
        logger.info("Publishing post #%d (type=%s)", post.id, post.post_type.value)
        db.update_post_status(post.id, PostStatus.PUBLISHING)

        try:
            if not post.image_url and not post.video_url:
                raise ValueError("Post has no media URL — set image_url or video_url")

            if post.post_type.value == "IMAGE":
                media_id = await api.publish_image(post.image_url, post.full_caption)
            elif post.post_type.value == "REELS":
                media_id = await api.publish_reel(post.video_url, post.full_caption)
            elif post.post_type.value == "CAROUSEL_ALBUM":
                media_id = await api.publish_carousel(post.carousel_urls, post.full_caption)
            elif post.post_type.value == "STORIES":
                media_id = await api.publish_story(image_url=post.image_url, video_url=post.video_url)
            else:
                raise ValueError(f"Unknown post type: {post.post_type}")

            db.update_post_status(post.id, PostStatus.PUBLISHED, media_id=media_id)
            logger.info("Published post #%d -> media_id=%s", post.id, media_id)

            notifier = self._get_notifier()
            if notifier:
                notifier.send(
                    f"[IG] Post #{post.id} published\n" f"Type: {post.post_type.value}\n" f"Media ID: {media_id}"
                )
            return True

        except Exception as e:
            logger.error("Failed to publish post #%d: %s", post.id, e)
            db.update_post_status(post.id, PostStatus.FAILED, error_message=str(e))
            notifier = self._get_notifier()
            if notifier:
                notifier.send(f"[IG ERROR] Post #{post.id} failed: {e}")
            return False

    async def generate_daily_content(self, topics: list[str] | None = None) -> int:
        """Generate daily content batch and enqueue.

        If topics is None, pulls from GetDayTrends.
        Falls back to default topics if trend data unavailable.
        Returns number of posts enqueued.
        """
        if not topics:
            # Try to get trending topics from GetDayTrends
            try:
                from services.trend_bridge import TrendBridge

                bridge = TrendBridge()
                topics = bridge.topics_to_instagram_topics(max_topics=len(self.config.scheduler.posting_hours))
                if topics:
                    logger.info("Using %d trending topics from GetDayTrends", len(topics))
                else:
                    topics = TrendBridge().get_default_fallback_topics()
                    logger.info("No trends available, using default topics")
            except Exception as e:
                logger.warning("TrendBridge failed (%s), using defaults", e)
                topics = [
                    "AI 기술 트렌드",
                    "생산성 향상 팁",
                    "디지털 노마드 라이프",
                    "자기계발 인사이트",
                ]

        gen = self._get_content_gen()
        db = self._get_db()

        posts = await gen.generate_daily_batch(
            topics=topics,
            posting_hours=self.config.scheduler.posting_hours,
        )

        count = 0
        for post in posts:
            db.enqueue_post(post)
            count += 1

        logger.info("Enqueued %d posts for today", count)

        notifier = self._get_notifier()
        if notifier and count > 0:
            notifier.send(
                f"[IG] Daily content generated: {count} posts queued\n" f"Topics: {', '.join(topics[:count])}"
            )
        return count

    async def collect_insights(self) -> int:
        """Collect insights for all published posts."""
        db = self._get_db()
        api = self._get_meta_api()
        published = db.get_published_posts(limit=25)
        collected = 0

        for post in published:
            if not post.media_id:
                continue
            try:
                from models import PostInsights

                metrics = await api.get_media_insights(post.media_id)
                insights = PostInsights(
                    media_id=post.media_id,
                    impressions=metrics.get("impressions", 0),
                    reach=metrics.get("reach", 0),
                    engagement=metrics.get("engagement", 0),
                    saved=metrics.get("saved", 0),
                    shares=metrics.get("shares", 0),
                )
                db.save_insights(insights)
                collected += 1
            except Exception as e:
                logger.warning("Failed to collect insights for %s: %s", post.media_id, e)

        logger.info("Collected insights for %d posts", collected)
        return collected

    async def send_daily_report(self) -> None:
        """Send daily performance report via Telegram."""
        db = self._get_db()
        notifier = self._get_notifier()
        if not notifier:
            logger.warning("No notifier configured, skipping report")
            return

        published_today = db.get_post_count_today()
        queued = db.get_queued_posts()

        report = (
            f"[IG Daily Report] {datetime.now().strftime('%Y-%m-%d')}\n"
            f"Published today: {published_today}\n"
            f"Queued for tomorrow: {len(queued)}\n"
        )

        # Add top performing post if available
        published = db.get_published_posts(limit=5)
        if published:
            best = None
            best_engagement = 0
            for p in published:
                if p.media_id:
                    insights_list = db.get_insights_for_post(p.media_id)
                    if insights_list:
                        latest = insights_list[0]
                        if latest.engagement > best_engagement:
                            best = latest
                            best_engagement = latest.engagement

            if best:
                report += (
                    f"\nTop post: {best.media_id}\n"
                    f"  Reach: {best.reach}\n"
                    f"  Engagement: {best.engagement}\n"
                    f"  Engagement Rate: {best.engagement_rate:.1f}%\n"
                    f"  Saved: {best.saved}"
                )

        notifier.send(report)
        logger.info("Daily report sent")
