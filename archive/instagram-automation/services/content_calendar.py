"""Content calendar system for Instagram automation.

Manages weekly/monthly content planning with:
- Theme-based daily planning
- Content mix balancing (IMAGE, REELS, CAROUSEL)
- Trend-reactive slot injection
- Performance-based topic recycling
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from enum import Enum

from models import PostType

logger = logging.getLogger(__name__)


class ContentTheme(str, Enum):
    """Weekly content themes for consistent branding."""
    EDUCATION = "education"        # 정보/인사이트 전달
    ENGAGEMENT = "engagement"      # 참여 유도 (질문, 투표)
    STORYTELLING = "storytelling"   # 스토리, 경험 공유
    TREND = "trend"                # 트렌드 반응
    PROMOTION = "promotion"        # 프로모션/CTA
    BEHIND_SCENES = "behind_scenes"  # 일상/비하인드
    USER_CONTENT = "user_content"  # UGC/리포스트


# Default weekly content template
DEFAULT_WEEKLY_PLAN = {
    0: {"theme": ContentTheme.EDUCATION, "post_type": PostType.CAROUSEL_ALBUM, "label": "월요일: 교육 카러셀"},
    1: {"theme": ContentTheme.TREND, "post_type": PostType.IMAGE, "label": "화요일: 트렌드 반응"},
    2: {"theme": ContentTheme.ENGAGEMENT, "post_type": PostType.IMAGE, "label": "수요일: 참여 유도"},
    3: {"theme": ContentTheme.STORYTELLING, "post_type": PostType.REELS, "label": "목요일: 스토리 릴스"},
    4: {"theme": ContentTheme.EDUCATION, "post_type": PostType.IMAGE, "label": "금요일: 꿀팁"},
    5: {"theme": ContentTheme.BEHIND_SCENES, "post_type": PostType.STORIES, "label": "토요일: 비하인드"},
    6: {"theme": ContentTheme.ENGAGEMENT, "post_type": PostType.IMAGE, "label": "일요일: 주간 회고"},
}


class CalendarEntry:
    """A single content calendar entry."""

    def __init__(
        self,
        date: str,
        theme: str,
        topic: str = "",
        post_type: str = "IMAGE",
        posting_hour: int = 12,
        notes: str = "",
        status: str = "planned",
        trend_source: str = "",
    ):
        self.date = date
        self.theme = theme
        self.topic = topic
        self.post_type = post_type
        self.posting_hour = posting_hour
        self.notes = notes
        self.status = status
        self.trend_source = trend_source

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "theme": self.theme,
            "topic": self.topic,
            "post_type": self.post_type,
            "posting_hour": self.posting_hour,
            "notes": self.notes,
            "status": self.status,
            "trend_source": self.trend_source,
        }


class ContentCalendar:
    """Manage content planning with weekly themes and trend injection."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                theme TEXT NOT NULL,
                topic TEXT DEFAULT '',
                post_type TEXT DEFAULT 'IMAGE',
                posting_hour INTEGER DEFAULT 12,
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'planned',
                trend_source TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(date, posting_hour)
            );
            CREATE INDEX IF NOT EXISTS idx_calendar_date ON content_calendar(date);
            CREATE INDEX IF NOT EXISTS idx_calendar_status ON content_calendar(status);
        """)
        conn.commit()
        conn.close()

    def generate_weekly_plan(
        self,
        start_date: datetime | None = None,
        posting_hours: list[int] | None = None,
    ) -> list[CalendarEntry]:
        """Generate a weekly content plan based on theme template.

        Does NOT overwrite existing entries.
        """
        start = start_date or datetime.now()
        # Align to next Monday
        days_ahead = -start.weekday()
        if days_ahead < 0:
            days_ahead += 7
        monday = start + timedelta(days=days_ahead)

        hours = posting_hours or [12]
        entries = []
        conn = self._get_conn()

        for day_offset in range(7):
            date = monday + timedelta(days=day_offset)
            date_str = date.strftime("%Y-%m-%d")
            weekday = date.weekday()

            plan = DEFAULT_WEEKLY_PLAN.get(weekday, DEFAULT_WEEKLY_PLAN[0])

            for hour in hours:
                # Check if already exists
                existing = conn.execute(
                    "SELECT id FROM content_calendar WHERE date = ? AND posting_hour = ?",
                    (date_str, hour),
                ).fetchone()
                if existing:
                    continue

                entry = CalendarEntry(
                    date=date_str,
                    theme=plan["theme"].value,
                    post_type=plan["post_type"].value,
                    posting_hour=hour,
                    notes=plan["label"],
                )
                conn.execute(
                    """INSERT INTO content_calendar
                       (date, theme, topic, post_type, posting_hour, notes, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (entry.date, entry.theme, entry.topic, entry.post_type,
                     entry.posting_hour, entry.notes, entry.status),
                )
                entries.append(entry)

        conn.commit()
        conn.close()
        logger.info("Generated %d calendar entries for week of %s", len(entries), monday.strftime("%Y-%m-%d"))
        return entries

    def inject_trend_topic(
        self,
        date: str,
        topic: str,
        trend_source: str = "getdaytrends",
        posting_hour: int = 12,
    ) -> bool:
        """Inject a trending topic into a calendar slot.

        Overrides planned topic if status is still 'planned'.
        """
        conn = self._get_conn()
        result = conn.execute(
            """UPDATE content_calendar
               SET topic = ?, trend_source = ?, theme = 'trend'
               WHERE date = ? AND posting_hour = ? AND status = 'planned'""",
            (topic, trend_source, date, posting_hour),
        )
        conn.commit()
        updated = result.rowcount > 0
        conn.close()
        if updated:
            logger.info("Injected trend topic '%s' for %s@%02d:00", topic, date, posting_hour)
        return updated

    def get_today_plan(self) -> list[dict]:
        """Get today's content plan entries."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM content_calendar WHERE date = ? ORDER BY posting_hour",
            (today,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_week_plan(self, start_date: str | None = None) -> list[dict]:
        """Get a week's content plan."""
        start = start_date or datetime.now().strftime("%Y-%m-%d")
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM content_calendar WHERE date >= ? AND date < ? ORDER BY date, posting_hour",
            (start, end),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_completed(self, date: str, posting_hour: int) -> None:
        """Mark a calendar entry as completed."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE content_calendar SET status = 'completed' WHERE date = ? AND posting_hour = ?",
            (date, posting_hour),
        )
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """Calendar statistics."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) as c FROM content_calendar").fetchone()["c"]
        planned = conn.execute(
            "SELECT COUNT(*) as c FROM content_calendar WHERE status = 'planned'"
        ).fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) as c FROM content_calendar WHERE status = 'completed'"
        ).fetchone()["c"]
        themes = conn.execute(
            "SELECT theme, COUNT(*) as c FROM content_calendar GROUP BY theme ORDER BY c DESC"
        ).fetchall()
        conn.close()
        return {
            "total": total,
            "planned": planned,
            "completed": completed,
            "theme_distribution": {r["theme"]: r["c"] for r in themes},
        }
