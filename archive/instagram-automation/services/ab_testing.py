"""A/B testing framework for Instagram content optimization.

Supports:
- Caption variant testing (hooks, CTAs, tone)
- Hashtag set comparison
- Posting time optimization
- Statistical significance calculation
"""

from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class ExperimentStatus(str):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ABTestEngine:
    """A/B testing engine for Instagram content optimization."""

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
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                test_type TEXT NOT NULL,
                hypothesis TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                variant_label TEXT NOT NULL,
                content TEXT NOT NULL,
                post_id INTEGER,
                media_id TEXT,
                impressions INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0,
                engagement INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                saved INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            );

            CREATE INDEX IF NOT EXISTS idx_variants_experiment ON variants(experiment_id);
        """)
        conn.commit()
        conn.close()

    def create_experiment(
        self,
        name: str,
        test_type: str,
        hypothesis: str = "",
    ) -> int:
        """Create a new A/B experiment. Returns experiment ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO experiments (name, test_type, hypothesis) VALUES (?, ?, ?)",
            (name, test_type, hypothesis),
        )
        exp_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info("Created experiment #%d: %s (%s)", exp_id, name, test_type)
        return exp_id

    def add_variant(
        self,
        experiment_id: int,
        label: str,
        content: str,
        post_id: int | None = None,
    ) -> int:
        """Add a variant to an experiment. Returns variant ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO variants (experiment_id, variant_label, content, post_id)
               VALUES (?, ?, ?, ?)""",
            (experiment_id, label, content, post_id),
        )
        var_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return var_id

    def record_results(
        self,
        variant_id: int,
        *,
        media_id: str | None = None,
        impressions: int = 0,
        reach: int = 0,
        engagement: int = 0,
        likes: int = 0,
        comments: int = 0,
        saved: int = 0,
        shares: int = 0,
    ) -> None:
        """Record performance metrics for a variant."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE variants SET
                 media_id = COALESCE(?, media_id),
                 impressions = ?,
                 reach = ?,
                 engagement = ?,
                 likes = ?,
                 comments = ?,
                 saved = ?,
                 shares = ?
               WHERE id = ?""",
            (media_id, impressions, reach, engagement, likes, comments, saved, shares, variant_id),
        )
        conn.commit()
        conn.close()

    def get_experiment_results(self, experiment_id: int) -> dict:
        """Get experiment results with winner determination."""
        conn = self._get_conn()
        exp = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        if not exp:
            conn.close()
            return {"error": "Experiment not found"}

        variants = conn.execute(
            "SELECT * FROM variants WHERE experiment_id = ? ORDER BY variant_label",
            (experiment_id,),
        ).fetchall()
        conn.close()

        if not variants:
            return {"experiment": dict(exp), "variants": [], "winner": None}

        variant_data = []
        for v in variants:
            eng_rate = (v["engagement"] / v["reach"] * 100) if v["reach"] > 0 else 0
            save_rate = (v["saved"] / v["reach"] * 100) if v["reach"] > 0 else 0
            variant_data.append({
                "id": v["id"],
                "label": v["variant_label"],
                "content_preview": v["content"][:100],
                "impressions": v["impressions"],
                "reach": v["reach"],
                "engagement": v["engagement"],
                "engagement_rate": round(eng_rate, 2),
                "likes": v["likes"],
                "comments": v["comments"],
                "saved": v["saved"],
                "save_rate": round(save_rate, 2),
                "shares": v["shares"],
            })

        # Determine winner by engagement rate
        winner = max(variant_data, key=lambda x: x["engagement_rate"])

        # Check statistical significance (simplified z-test)
        significance = None
        if len(variant_data) == 2:
            significance = self._check_significance(variant_data[0], variant_data[1])

        return {
            "experiment": dict(exp),
            "variants": variant_data,
            "winner": winner["label"],
            "significance": significance,
        }

    def _check_significance(self, a: dict, b: dict, confidence: float = 0.95) -> dict:
        """Simplified two-proportion z-test for engagement rates.

        Returns significance assessment.
        """
        n_a = max(a["reach"], 1)
        n_b = max(b["reach"], 1)
        p_a = a["engagement"] / n_a
        p_b = b["engagement"] / n_b

        if n_a < 30 or n_b < 30:
            return {
                "is_significant": False,
                "reason": "Insufficient sample size (need 30+ reach per variant)",
                "p_a": round(p_a, 4),
                "p_b": round(p_b, 4),
                "lift": round((p_b - p_a) / max(p_a, 0.001) * 100, 1),
            }

        # Pooled proportion
        p_pool = (a["engagement"] + b["engagement"]) / (n_a + n_b)
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b)) if p_pool > 0 else 0.001

        z = abs(p_a - p_b) / max(se, 0.001)
        # z > 1.96 → significant at 95%
        z_threshold = 1.96

        lift = (p_b - p_a) / max(p_a, 0.001) * 100

        return {
            "is_significant": z > z_threshold,
            "z_score": round(z, 3),
            "z_threshold": z_threshold,
            "p_a": round(p_a, 4),
            "p_b": round(p_b, 4),
            "lift": round(lift, 1),
            "confidence": f"{confidence * 100:.0f}%",
        }

    def create_caption_test(
        self,
        topic: str,
        variant_a: str,
        variant_b: str,
        hypothesis: str = "",
    ) -> int:
        """Convenience: create a caption A/B test."""
        exp_id = self.create_experiment(
            name=f"Caption test: {topic[:30]}",
            test_type="caption",
            hypothesis=hypothesis or f"Testing two caption approaches for '{topic}'",
        )
        self.add_variant(exp_id, "A", variant_a)
        self.add_variant(exp_id, "B", variant_b)
        return exp_id

    def create_hashtag_test(
        self,
        topic: str,
        set_a: list[str],
        set_b: list[str],
    ) -> int:
        """Convenience: create a hashtag set A/B test."""
        exp_id = self.create_experiment(
            name=f"Hashtag test: {topic[:30]}",
            test_type="hashtag",
            hypothesis=f"Comparing hashtag effectiveness for '{topic}'",
        )
        self.add_variant(exp_id, "A", " ".join(set_a))
        self.add_variant(exp_id, "B", " ".join(set_b))
        return exp_id

    def complete_experiment(self, experiment_id: int) -> None:
        """Mark an experiment as completed."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE experiments SET status = 'completed', completed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), experiment_id),
        )
        conn.commit()
        conn.close()

    def get_active_experiments(self) -> list[dict]:
        """Get all active experiments."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM experiments WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_learnings(self, test_type: str | None = None) -> list[dict]:
        """Get insights from completed experiments."""
        conn = self._get_conn()
        query = "SELECT * FROM experiments WHERE status = 'completed'"
        params: list = []
        if test_type:
            query += " AND test_type = ?"
            params.append(test_type)
        query += " ORDER BY completed_at DESC LIMIT 20"

        exps = conn.execute(query, params).fetchall()
        conn.close()

        learnings = []
        for exp in exps:
            results = self.get_experiment_results(exp["id"])
            if results.get("winner"):
                learnings.append({
                    "experiment": exp["name"],
                    "test_type": exp["test_type"],
                    "hypothesis": exp["hypothesis"],
                    "winner": results["winner"],
                    "significance": results.get("significance"),
                })
        return learnings
