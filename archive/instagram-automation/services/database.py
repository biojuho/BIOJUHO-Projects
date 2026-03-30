"""SQLite database layer for post queue, DM rules, and insights."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from models import DMTriggerRule, InstagramPost, PostInsights, PostStatus, PostType

logger = logging.getLogger(__name__)


class Database:
    """SQLite-based storage for Instagram automation."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def _cursor(self):
        conn = self._get_conn()
        try:
            yield conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._cursor() as cur:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    caption TEXT NOT NULL,
                    hashtags TEXT DEFAULT '',
                    image_url TEXT,
                    video_url TEXT,
                    carousel_urls TEXT DEFAULT '[]',
                    post_type TEXT DEFAULT 'IMAGE',
                    status TEXT DEFAULT 'draft',
                    scheduled_at TEXT,
                    published_at TEXT,
                    media_id TEXT,
                    container_id TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS dm_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    response_template TEXT NOT NULL,
                    is_llm_response INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id TEXT NOT NULL,
                    impressions INTEGER DEFAULT 0,
                    reach INTEGER DEFAULT 0,
                    engagement INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    saved INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    collected_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS dm_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    message_text TEXT,
                    response_text TEXT,
                    trigger_keyword TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
                CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts(scheduled_at);
                CREATE INDEX IF NOT EXISTS idx_insights_media ON insights(media_id);
            """)
        logger.info("Database initialized: %s", self.db_path)

    # ---- Posts ----

    def enqueue_post(self, post: InstagramPost) -> int:
        """Add a post to the queue. Returns post ID."""
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO posts
                   (caption, hashtags, image_url, video_url, carousel_urls,
                    post_type, status, scheduled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    post.caption,
                    post.hashtags,
                    post.image_url,
                    post.video_url,
                    json.dumps(post.carousel_urls),
                    post.post_type.value,
                    PostStatus.QUEUED.value,
                    post.scheduled_at.isoformat() if post.scheduled_at else None,
                ),
            )
            post_id = cur.lastrowid
            logger.info("Enqueued post #%d for %s", post_id, post.scheduled_at)
            return post_id

    def get_next_scheduled(self) -> InstagramPost | None:
        """Get the next post due for publishing."""
        now = datetime.now().isoformat()
        with self._cursor() as cur:
            cur.execute(
                """SELECT * FROM posts
                   WHERE status = 'queued' AND scheduled_at <= ?
                   ORDER BY scheduled_at ASC LIMIT 1""",
                (now,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_post(row)

    def get_queued_posts(self) -> list[InstagramPost]:
        """Get all queued posts."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM posts WHERE status = 'queued' ORDER BY scheduled_at ASC")
            return [self._row_to_post(r) for r in cur.fetchall()]

    def update_post_status(
        self,
        post_id: int,
        status: PostStatus,
        *,
        media_id: str | None = None,
        container_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update post status after publish attempt."""
        fields = ["status = ?"]
        values: list = [status.value]

        if media_id:
            fields.append("media_id = ?")
            values.append(media_id)
        if container_id:
            fields.append("container_id = ?")
            values.append(container_id)
        if error_message:
            fields.append("error_message = ?")
            values.append(error_message)
        if status == PostStatus.PUBLISHED:
            fields.append("published_at = ?")
            values.append(datetime.now().isoformat())

        values.append(post_id)
        with self._cursor() as cur:
            cur.execute(
                f"UPDATE posts SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    def get_published_posts(self, limit: int = 50) -> list[InstagramPost]:
        """Get recently published posts."""
        with self._cursor() as cur:
            cur.execute(
                """SELECT * FROM posts WHERE status = 'published'
                   ORDER BY published_at DESC LIMIT ?""",
                (limit,),
            )
            return [self._row_to_post(r) for r in cur.fetchall()]

    def _row_to_post(self, row: sqlite3.Row) -> InstagramPost:
        return InstagramPost(
            id=row["id"],
            caption=row["caption"],
            hashtags=row["hashtags"] or "",
            image_url=row["image_url"],
            video_url=row["video_url"],
            carousel_urls=json.loads(row["carousel_urls"] or "[]"),
            post_type=PostType(row["post_type"]),
            status=PostStatus(row["status"]),
            scheduled_at=datetime.fromisoformat(row["scheduled_at"]) if row["scheduled_at"] else None,
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            media_id=row["media_id"],
            container_id=row["container_id"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
        )

    # ---- DM Rules ----

    def add_dm_rule(self, rule: DMTriggerRule) -> None:
        with self._cursor() as cur:
            cur.execute(
                """INSERT OR REPLACE INTO dm_rules
                   (keyword, response_template, is_llm_response, enabled)
                   VALUES (?, ?, ?, ?)""",
                (rule.keyword, rule.response_template, int(rule.is_llm_response), int(rule.enabled)),
            )

    def get_dm_rules(self) -> list[DMTriggerRule]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM dm_rules WHERE enabled = 1")
            return [
                DMTriggerRule(
                    keyword=r["keyword"],
                    response_template=r["response_template"],
                    is_llm_response=bool(r["is_llm_response"]),
                    enabled=bool(r["enabled"]),
                )
                for r in cur.fetchall()
            ]

    def log_dm(self, sender_id: str, message: str, response: str, keyword: str = "") -> None:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO dm_log
                   (sender_id, message_text, response_text, trigger_keyword)
                   VALUES (?, ?, ?, ?)""",
                (sender_id, message, response, keyword),
            )

    # ---- Insights ----

    def save_insights(self, insights: PostInsights) -> None:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO insights
                   (media_id, impressions, reach, engagement, likes,
                    comments, saved, shares)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    insights.media_id,
                    insights.impressions,
                    insights.reach,
                    insights.engagement,
                    insights.likes,
                    insights.comments,
                    insights.saved,
                    insights.shares,
                ),
            )

    def get_insights_for_post(self, media_id: str) -> list[PostInsights]:
        with self._cursor() as cur:
            cur.execute(
                """SELECT * FROM insights WHERE media_id = ?
                   ORDER BY collected_at DESC""",
                (media_id,),
            )
            return [
                PostInsights(
                    media_id=r["media_id"],
                    impressions=r["impressions"],
                    reach=r["reach"],
                    engagement=r["engagement"],
                    likes=r["likes"],
                    comments=r["comments"],
                    saved=r["saved"],
                    shares=r["shares"],
                    collected_at=datetime.fromisoformat(r["collected_at"]),
                )
                for r in cur.fetchall()
            ]

    def get_post_count_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM posts WHERE published_at LIKE ? AND status = 'published'",
                (f"{today}%",),
            )
            return cur.fetchone()["cnt"]
