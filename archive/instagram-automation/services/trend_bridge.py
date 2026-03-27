"""Bridge between GetDayTrends and Instagram content pipeline.

Reads trending topics from getdaytrends SQLite DB and transforms
them into Instagram-optimized topic suggestions.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# GetDayTrends DB path (relative to workspace root)
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "getdaytrends" / "data" / "getdaytrends.db"


class TrendBridge:
    """Read and filter trends from GetDayTrends for Instagram content."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or _DEFAULT_DB_PATH)
        if not Path(self.db_path).exists():
            logger.warning("GetDayTrends DB not found: %s", self.db_path)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def get_trending_topics(
        self,
        *,
        max_topics: int = 8,
        min_viral_score: int = 50,
        hours: int = 12,
        exclude_categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent high-viral-score trends suitable for Instagram.

        Returns list of dicts with: keyword, viral_potential, category,
        suggested_angles, why_trending, relevance_score.
        """
        if not Path(self.db_path).exists():
            logger.warning("DB not found, returning empty trends")
            return []

        try:
            conn = self._get_conn()
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            exclude = exclude_categories or []

            query = """
                SELECT keyword, viral_potential, category,
                       suggested_angles, why_trending, relevance_score,
                       sentiment, safety_flag, publishable
                FROM scored_trends
                WHERE scored_at > ?
                  AND viral_potential >= ?
                  AND (safety_flag = 0 OR safety_flag IS NULL)
                  AND (publishable = 1 OR publishable IS NULL)
                ORDER BY viral_potential DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (cutoff, min_viral_score, max_topics * 3))
            rows = cursor.fetchall()
            conn.close()

            topics = []
            for row in rows:
                cat = row["category"] or ""
                if cat.lower() in [c.lower() for c in exclude]:
                    continue
                topics.append({
                    "keyword": row["keyword"],
                    "viral_potential": row["viral_potential"],
                    "category": cat,
                    "suggested_angles": row["suggested_angles"] or "",
                    "why_trending": row["why_trending"] or "",
                    "relevance_score": row["relevance_score"] or 0,
                    "sentiment": row["sentiment"] or "neutral",
                })
                if len(topics) >= max_topics:
                    break

            logger.info(
                "Fetched %d trending topics (from %d rows, min_viral=%d)",
                len(topics), len(rows), min_viral_score,
            )
            return topics

        except sqlite3.OperationalError as e:
            logger.error("Failed to read trends DB: %s", e)
            return []

    def topics_to_instagram_topics(
        self,
        trends: list[dict] | None = None,
        max_topics: int = 4,
    ) -> list[str]:
        """Convert trending topics to Instagram-ready topic strings.

        Enriches topic keywords with context about why they're trending,
        making them more suitable for LLM content generation.
        """
        if trends is None:
            trends = self.get_trending_topics(max_topics=max_topics)

        ig_topics = []
        for trend in trends[:max_topics]:
            topic = trend["keyword"]
            why = trend.get("why_trending", "")
            category = trend.get("category", "")

            # Build enriched topic string
            parts = [topic]
            if category:
                parts.append(f"(카테고리: {category})")
            if why:
                parts.append(f"— {why}")

            ig_topics.append(" ".join(parts))

        return ig_topics

    def get_default_fallback_topics(self) -> list[str]:
        """Fallback topics when GetDayTrends is unavailable."""
        return [
            "AI 기술이 바꾸는 일상",
            "2026년 주목할 테크 트렌드",
            "생산성을 높이는 습관",
            "디지털 워크플로 자동화 팁",
        ]
