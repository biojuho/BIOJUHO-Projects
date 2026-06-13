"""
getdaytrends - Tiered Collection Mixin

PerformanceTracker에서 분리된 실시간 시그널 수집 기능.
3단계(1h/6h/48h) 수집 전략으로 트윗 성과를 시간대별로 추적합니다.
"""

import re
from datetime import UTC, datetime, timedelta

from loguru import logger as log
from perf_models import TweetMetrics, normalize_angle


class TieredCollectionMixin:
    """[D] Real-time Signal 3-Tier Collection (PerformanceTracker Mixin)."""

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

    async def collect_early_signal(self, tweet_ids: list[str], tier: str = "1h") -> list[TweetMetrics]:
        """[D] 초기 시그널 수집 (발행 1시간 후). 높은 초기 ER 시 후속 콘텐츠 트리거."""
        metrics = await self.batch_collect(tweet_ids)
        for m in metrics:
            m.collection_tier = tier
        if metrics:
            await self.save_metrics_batch(metrics)
        return metrics

    async def get_early_signal_analysis(self, hours: int = 2) -> dict:
        """[D] 최근 N시간 내 수집된 초기 시그널 분석.

        Returns: {boost_candidates: [...], suppress_candidates: [...], avg_metrics: {...}}
        """
        conn = await self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
            cursor = await conn.execute(
                """SELECT tweet_id, impressions, engagement_rate, angle_type
                   FROM tweet_performance
                   WHERE collection_tier = '1h' AND collected_at >= ?
                   ORDER BY engagement_rate DESC""",
                (cutoff,),
            )
            rows = await cursor.fetchall()

            if not rows:
                return {"boost_candidates": [], "suppress_candidates": [], "avg_metrics": {}}

            avg_er = sum(r["engagement_rate"] for r in rows) / len(rows)
            avg_imp = sum(r["impressions"] for r in rows) / len(rows)

            boost = [dict(r) for r in rows if r["engagement_rate"] >= avg_er * 2.0]
            suppress = [dict(r) for r in rows if r["engagement_rate"] <= avg_er * 0.3]

            return {
                "boost_candidates": boost,
                "suppress_candidates": suppress,
                "avg_metrics": {
                    "avg_engagement_rate": round(avg_er, 6),
                    "avg_impressions": round(avg_imp, 1),
                    "total_collected": len(rows),
                },
            }
        finally:
            await conn.close()

    async def run_tiered_collection(self, lookback_hours: int = 48) -> dict:
        """Run scheduled 1h/6h/48h performance collection."""
        conn = await self._get_conn()
        result = {"tier_1h": 0, "tier_6h": 0, "tier_48h": 0}

        try:
            if not await self._table_exists(conn, "tweet_performance"):
                log.info("[Tiered Collection] skipped: tweet_performance table missing")
                return result

            for tier, start, end in _tier_windows(datetime.now()):
                result[f"tier_{tier}"] = await self._collect_one_tier(conn, tier, start, end)

            log.info(
                f"3-tier collection complete: 1h={result['tier_1h']}, "
                f"6h={result['tier_6h']}, 48h={result['tier_48h']}"
            )
        finally:
            await conn.close()

        return result

    async def _collect_one_tier(self, conn, tier: str, start: str, end: str) -> int:
        rows = await _tier_candidate_rows(conn, tier, start, end)
        tweet_ids, id_map = _tier_tweet_id_map(rows)
        if not tweet_ids or not self.bearer_token:
            return 0

        metrics = await self.batch_collect(tweet_ids)
        _annotate_tier_metrics(metrics, tier, id_map)
        return await self.save_metrics_batch(metrics)


def _tier_windows(now: datetime) -> list[tuple[str, str, str]]:
    return [
        ("1h", (now - timedelta(minutes=90)).isoformat(), (now - timedelta(minutes=45)).isoformat()),
        ("6h", (now - timedelta(hours=7)).isoformat(), (now - timedelta(hours=5)).isoformat()),
        ("48h", (now - timedelta(hours=72)).isoformat(), (now - timedelta(hours=24)).isoformat()),
    ]


async def _tier_candidate_rows(conn, tier: str, start: str, end: str) -> list:
    cursor = await conn.execute(
        """SELECT t.id, t.tweet_type, t.posted_at, t.x_tweet_id
           FROM tweets t
           WHERE t.posted_at IS NOT NULL
             AND t.posted_at >= ? AND t.posted_at <= ?
             AND (
                 (t.x_tweet_id IS NOT NULL AND t.x_tweet_id != '' AND t.x_tweet_id NOT IN (
                     SELECT tweet_id
                     FROM tweet_performance
                     WHERE collection_tier = ?
                 ))
                 OR
                 ((t.x_tweet_id IS NULL OR t.x_tweet_id = '') AND t.id NOT IN (
                     SELECT CAST(tweet_id AS INTEGER)
                     FROM tweet_performance
                     WHERE collection_tier = ? AND tweet_id GLOB '[0-9]*'
                 ))
             )
           LIMIT 100""",
        (start, end, tier, tier),
    )
    return await cursor.fetchall()


def _tier_tweet_id_map(rows: list) -> tuple[list[str], dict[str, dict]]:
    tweet_ids: list[str] = []
    id_map: dict[str, dict] = {}
    for row in rows:
        x_id = _tier_row_tweet_id(row)
        if x_id:
            tweet_ids.append(x_id)
            id_map[x_id] = dict(row)
    return tweet_ids, id_map


def _tier_row_tweet_id(row) -> str:
    x_tweet_id = (row["x_tweet_id"] or "").strip()
    posted_at = (row["posted_at"] or "").strip()
    if x_tweet_id and re.match(r"^\d{10,}$", x_tweet_id):
        return x_tweet_id
    if posted_at and re.match(r"^\d{10,}$", posted_at):
        return posted_at
    return ""


def _annotate_tier_metrics(metrics: list[TweetMetrics], tier: str, id_map: dict[str, dict]) -> None:
    for metric in metrics:
        metric.collection_tier = tier
        row_info = id_map.get(metric.tweet_id, {})
        metric.angle_type = normalize_angle(row_info.get("tweet_type", ""))
