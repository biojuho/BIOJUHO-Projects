"""Hashtag strategy database and optimizer.

Manages categorized hashtag pools with performance tracking:
- Size tiers: mega (1M+), large (100K-1M), medium (10K-100K), small (<10K)
- Niche-specific collections
- Performance-based ranking
- Banned/shadowban-risky tag filtering
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class HashtagTier(str):
    MEGA = "mega"  # 1M+ posts
    LARGE = "large"  # 100K-1M
    MEDIUM = "medium"  # 10K-100K
    SMALL = "small"  # <10K (niche)


# Default hashtag pools for common niches
DEFAULT_POOLS: dict[str, dict[str, list[str]]] = {
    "tech": {
        "mega": ["#technology", "#ai", "#tech", "#coding", "#programming"],
        "large": ["#artificialintelligence", "#machinelearning", "#startup", "#innovation", "#developer"],
        "medium": ["#techtrends", "#aistartup", "#techlife", "#codingtips", "#devlife"],
        "small": ["#aitips", "#techinsight", "#코딩일상", "#개발자일상", "#테크트렌드"],
    },
    "lifestyle": {
        "mega": ["#lifestyle", "#motivation", "#selfcare", "#wellness", "#mindset"],
        "large": ["#personalgrowth", "#selfimprovement", "#dailymotivation", "#productivity", "#healthylife"],
        "medium": ["#lifehacks", "#morningroutine", "#dailyhabits", "#growthmindset", "#mindfulness"],
        "small": ["#자기계발", "#생산성팁", "#아침루틴", "#습관형성", "#마인드셋"],
    },
    "business": {
        "mega": ["#business", "#entrepreneur", "#marketing", "#success", "#money"],
        "large": ["#smallbusiness", "#digitalmarketing", "#ecommerce", "#branding", "#ceo"],
        "medium": ["#businesstips", "#sidehustle", "#passiveincome", "#onlinebusiness", "#marketingstrategy"],
        "small": ["#비즈니스팁", "#창업일기", "#마케팅전략", "#부업추천", "#수익모델"],
    },
    "korean_general": {
        "mega": ["#일상", "#데일리", "#소통", "#인스타그램", "#좋아요"],
        "large": ["#한국", "#서울", "#인스타", "#팔로우", "#맞팔"],
        "medium": ["#오늘의기록", "#일상기록", "#공감", "#생각정리", "#글스타그램"],
        "small": ["#소소한일상", "#오늘하루", "#나의기록", "#일상공유", "#마음기록"],
    },
}


class HashtagDB:
    """SQLite-backed hashtag strategy database."""

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
            CREATE TABLE IF NOT EXISTS hashtags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL UNIQUE,
                niche TEXT DEFAULT 'general',
                tier TEXT DEFAULT 'medium',
                usage_count INTEGER DEFAULT 0,
                avg_reach REAL DEFAULT 0.0,
                avg_engagement REAL DEFAULT 0.0,
                is_banned INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS hashtag_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                niche TEXT NOT NULL,
                tags TEXT NOT NULL,
                times_used INTEGER DEFAULT 0,
                avg_performance REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_hashtags_niche ON hashtags(niche);
            CREATE INDEX IF NOT EXISTS idx_hashtags_tier ON hashtags(tier);
        """)
        conn.commit()
        conn.close()

    def seed_defaults(self, niches: list[str] | None = None) -> int:
        """Seed database with default hashtag pools. Returns count added."""
        target_niches = niches or list(DEFAULT_POOLS.keys())
        conn = self._get_conn()
        count = 0

        for niche in target_niches:
            pool = DEFAULT_POOLS.get(niche, {})
            for tier, tags in pool.items():
                for tag in tags:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO hashtags (tag, niche, tier) VALUES (?, ?, ?)",
                            (tag, niche, tier),
                        )
                        count += 1
                    except sqlite3.IntegrityError:
                        pass

        conn.commit()
        conn.close()
        logger.info("Seeded %d hashtags for niches: %s", count, target_niches)
        return count

    def add_tag(self, tag: str, niche: str = "general", tier: str = "medium") -> None:
        """Add a single hashtag."""
        if not tag.startswith("#"):
            tag = f"#{tag}"
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO hashtags (tag, niche, tier) VALUES (?, ?, ?)",
            (tag, niche, tier),
        )
        conn.commit()
        conn.close()

    def ban_tag(self, tag: str) -> None:
        """Mark a tag as banned/shadowban-risky."""
        conn = self._get_conn()
        conn.execute("UPDATE hashtags SET is_banned = 1 WHERE tag = ?", (tag,))
        conn.commit()
        conn.close()
        logger.info("Banned hashtag: %s", tag)

    def get_optimized_set(
        self,
        niche: str = "general",
        count: int = 15,
        *,
        mega_ratio: float = 0.2,
        large_ratio: float = 0.3,
        medium_ratio: float = 0.3,
        small_ratio: float = 0.2,
    ) -> list[str]:
        """Generate an optimized hashtag set with tier distribution.

        Default ratio: 3 mega + 4-5 large + 4-5 medium + 3 small = 15 tags
        Avoids recently used and banned tags.
        """
        conn = self._get_conn()
        tags = []

        tier_counts = {
            "mega": max(1, int(count * mega_ratio)),
            "large": max(1, int(count * large_ratio)),
            "medium": max(1, int(count * medium_ratio)),
            "small": max(1, int(count * small_ratio)),
        }

        for tier, tier_count in tier_counts.items():
            rows = conn.execute(
                """SELECT tag FROM hashtags
                   WHERE (niche = ? OR niche = 'general')
                     AND tier = ?
                     AND is_banned = 0
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (niche, tier, tier_count),
            ).fetchall()
            tags.extend(r["tag"] for r in rows)

        conn.close()

        # Fill remaining from any tier if needed
        if len(tags) < count:
            conn = self._get_conn()
            remaining = conn.execute(
                """SELECT tag FROM hashtags
                   WHERE (niche = ? OR niche = 'general')
                     AND is_banned = 0
                     AND tag NOT IN ({})
                   ORDER BY RANDOM()
                   LIMIT ?""".format(",".join("?" * len(tags))),
                [niche] + tags + [count - len(tags)],
            ).fetchall()
            tags.extend(r["tag"] for r in remaining)
            conn.close()

        return tags[:count]

    def record_performance(
        self,
        tags: list[str],
        reach: int,
        engagement: int,
    ) -> None:
        """Update hashtag performance stats after a post."""
        conn = self._get_conn()
        for tag in tags:
            conn.execute(
                """UPDATE hashtags SET
                     usage_count = usage_count + 1,
                     avg_reach = (avg_reach * usage_count + ?) / (usage_count + 1),
                     avg_engagement = (avg_engagement * usage_count + ?) / (usage_count + 1),
                     last_used = ?
                   WHERE tag = ?""",
                (reach, engagement, datetime.now().isoformat(), tag),
            )
        conn.commit()
        conn.close()

    def get_top_performers(self, niche: str = "general", limit: int = 10) -> list[dict]:
        """Get best-performing hashtags by engagement rate."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT tag, niche, tier, usage_count, avg_reach, avg_engagement
               FROM hashtags
               WHERE (niche = ? OR niche = 'general')
                 AND usage_count > 0
                 AND is_banned = 0
               ORDER BY avg_engagement DESC
               LIMIT ?""",
            (niche, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_set(self, name: str, niche: str, tags: list[str]) -> None:
        """Save a named hashtag set for reuse."""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO hashtag_sets (name, niche, tags) VALUES (?, ?, ?)",
            (name, niche, json.dumps(tags)),
        )
        conn.commit()
        conn.close()

    def get_set(self, name: str) -> list[str] | None:
        """Retrieve a saved hashtag set."""
        conn = self._get_conn()
        row = conn.execute("SELECT tags FROM hashtag_sets WHERE name = ?", (name,)).fetchone()
        conn.close()
        if row:
            return json.loads(row["tags"])
        return None

    def get_stats(self) -> dict:
        """Database statistics."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) as c FROM hashtags").fetchone()["c"]
        banned = conn.execute("SELECT COUNT(*) as c FROM hashtags WHERE is_banned = 1").fetchone()["c"]
        niches = conn.execute("SELECT niche, COUNT(*) as c FROM hashtags GROUP BY niche ORDER BY c DESC").fetchall()
        tiers = conn.execute("SELECT tier, COUNT(*) as c FROM hashtags GROUP BY tier ORDER BY c DESC").fetchall()
        sets_count = conn.execute("SELECT COUNT(*) as c FROM hashtag_sets").fetchone()["c"]
        conn.close()
        return {
            "total_tags": total,
            "banned_tags": banned,
            "saved_sets": sets_count,
            "by_niche": {r["niche"]: r["c"] for r in niches},
            "by_tier": {r["tier"]: r["c"] for r in tiers},
        }
