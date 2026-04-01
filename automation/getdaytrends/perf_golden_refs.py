"""
getdaytrends - Golden Reference Management Mixin

PerformanceTracker에서 분리된 골든 레퍼런스 CRUD 기능.
고성과 트윗을 자동으로 감지/저장하여 QA 벤치마크로 활용합니다.
"""


from datetime import UTC, datetime, timedelta

from loguru import logger as log

from perf_models import GoldenReference


class GoldenReferenceMixin:
    """[E] Golden Reference 관리 기능 (PerformanceTracker Mixin)."""

    def save_golden_reference(self, ref: GoldenReference) -> None:
        """[E] 골든 레퍼런스 저장. 최대 20개 유지 (최저 ER 자동 교체)."""
        self.init_table()
        conn = self._get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM golden_references").fetchone()[0]
            if count >= 20:
                conn.execute(
                    """DELETE FROM golden_references WHERE id = (
                        SELECT id FROM golden_references ORDER BY engagement_rate ASC LIMIT 1
                    )"""
                )
            conn.execute(
                """INSERT INTO golden_references
                   (tweet_id, content, angle_type, hook_pattern, kick_pattern,
                    engagement_rate, impressions, category, saved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tweet_id) DO UPDATE SET
                       engagement_rate=excluded.engagement_rate,
                       impressions=excluded.impressions,
                       saved_at=excluded.saved_at""",
                (
                    ref.tweet_id,
                    ref.content,
                    ref.angle_type,
                    ref.hook_pattern,
                    ref.kick_pattern,
                    ref.engagement_rate,
                    ref.impressions,
                    ref.category,
                    (ref.saved_at or datetime.now(UTC)).isoformat(),
                ),
            )
            conn.commit()
            log.debug(f"골든 레퍼런스 저장: tweet_id={ref.tweet_id}, ER={ref.engagement_rate}")
        finally:
            conn.close()

    def get_golden_references(self, limit: int = 5, category: str = "") -> list[GoldenReference]:
        """[E] 상위 골든 레퍼런스 조회 (QA 벤치마크)."""
        self.init_table()
        conn = self._get_conn()
        try:
            if category:
                rows = conn.execute(
                    """SELECT * FROM golden_references
                       WHERE category = ?
                       ORDER BY engagement_rate DESC LIMIT ?""",
                    (category, limit),
                ).fetchall()
                if not rows:
                    rows = conn.execute(
                        "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            return [
                GoldenReference(
                    tweet_id=r["tweet_id"],
                    content=r["content"],
                    angle_type=r["angle_type"],
                    hook_pattern=r["hook_pattern"],
                    kick_pattern=r["kick_pattern"],
                    engagement_rate=r["engagement_rate"],
                    impressions=r["impressions"],
                    category=dict(r).get("category", ""),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def auto_update_golden_references(self, days: int = 7, top_n: int = 10) -> int:
        """[E] 최근 N일간 상위 트윗을 자동으로 골든 레퍼런스에 등록.

        Returns: 새로 등록된 건수.
        """
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT tp.tweet_id, tp.angle_type, tp.hook_pattern, tp.kick_pattern,
                          tp.engagement_rate, tp.impressions,
                          t.content, t.tweet_type
                   FROM tweet_performance tp
                   LEFT JOIN tweets t ON CAST(tp.tweet_id AS TEXT) = CAST(t.id AS TEXT)
                   WHERE tp.collected_at >= ?
                     AND tp.impressions > 0
                     AND tp.engagement_rate > 0
                   ORDER BY tp.engagement_rate DESC
                   LIMIT ?""",
                (cutoff, top_n),
            ).fetchall()

            for r in rows:
                content = r["content"] if r["content"] else ""
                if not content:
                    continue
                ref = GoldenReference(
                    tweet_id=r["tweet_id"],
                    content=content,
                    angle_type=r["angle_type"] or "",
                    hook_pattern=r["hook_pattern"] or "",
                    kick_pattern=r["kick_pattern"] or "",
                    engagement_rate=r["engagement_rate"],
                    impressions=r["impressions"],
                    saved_at=datetime.now(UTC),
                )
                self.save_golden_reference(ref)
                saved += 1

            log.info(f"Golden references auto-updated: {saved}/{len(rows)}")
        finally:
            conn.close()
        return saved
