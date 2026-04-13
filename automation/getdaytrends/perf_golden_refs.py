"""
getdaytrends - Golden Reference Management Mixin

PerformanceTracker에서 분리된 골든 레퍼런스 CRUD 기능.
고성과 트윗을 자동으로 감지/저장하여 QA 벤치마크로 활용합니다.
"""


import json
from datetime import UTC, datetime, timedelta

from loguru import logger as log

from perf_models import GoldenReference
from db_layer.connection import db_transaction


class GoldenReferenceMixin:
    """[E] Golden Reference 관리 기능 (PerformanceTracker Mixin)."""

    async def _table_exists(self, conn, table_name: str) -> bool:
        if conn.__class__.__name__ == "PgAdapter":
            cursor = await conn.execute(
                "SELECT to_regclass(?) AS table_name",
                (f"public.{table_name}",),
            )
            row = await cursor.fetchone()
            return bool(row and row["table_name"])

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return await cursor.fetchone() is not None

    async def save_golden_reference(self, ref: GoldenReference) -> None:
        """[E] 골든 레퍼런스 저장. 최대 20개 유지 (최저 ER 자동 교체)."""
        conn = await self._get_conn()
        try:
            if not await self._table_exists(conn, "golden_references"):
                log.info("Golden reference save skipped: golden_references table missing")
                return

            async with db_transaction(conn):
                count_cursor = await conn.execute("SELECT COUNT(*) FROM golden_references")
                count = (await count_cursor.fetchone())[0]
                if count >= 20:
                    await conn.execute(
                        """DELETE FROM golden_references WHERE id = (
                            SELECT id FROM golden_references ORDER BY engagement_rate ASC LIMIT 1
                        )"""
                    )
                await conn.execute(
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
                log.debug(f"골든 레퍼런스 저장: tweet_id={ref.tweet_id}, ER={ref.engagement_rate}")
        finally:
            await conn.close()

    async def get_golden_references(self, limit: int = 5, category: str = "") -> list[GoldenReference]:
        """[E] 상위 골든 레퍼런스 조회 (QA 벤치마크)."""
        conn = await self._get_conn()
        try:
            if not await self._table_exists(conn, "golden_references"):
                log.info("Golden reference lookup skipped: golden_references table missing")
                return []

            if category:
                cursor = await conn.execute(
                    """SELECT * FROM golden_references
                       WHERE category = ?
                       ORDER BY engagement_rate DESC LIMIT ?""",
                    (category, limit),
                )
                rows = await cursor.fetchall()
                if not rows:
                    cursor = await conn.execute(
                        "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                        (limit,),
                    )
                    rows = await cursor.fetchall()
            else:
                cursor = await conn.execute(
                    "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                    (limit,),
                )
                rows = await cursor.fetchall()

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
            await conn.close()

    async def auto_update_golden_references(self, days: int = 7, top_n: int = 10) -> int:
        """[E] 최근 N일간 상위 트윗을 자동으로 골든 레퍼런스에 등록.

        Returns: 새로 등록된 건수.
        """
        conn = await self._get_conn()
        saved = 0
        try:
            if not await self._table_exists(conn, "tweet_performance"):
                log.info("Golden references auto-update skipped: tweet_performance table missing")
                return 0

            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            cursor = await conn.execute(
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
            )
            rows = await cursor.fetchall()

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
                # auto_update internally calls save_golden_reference which requests a separate connection pool resource
                await self.save_golden_reference(ref)
                saved += 1

            log.info(f"Golden references auto-updated: {saved}/{len(rows)}")
        finally:
            await conn.close()
        return saved
