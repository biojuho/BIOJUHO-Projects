"""
getdaytrends - Tiered Collection Mixin

PerformanceTracker에서 분리된 실시간 시그널 수집 기능.
3단계(1h/6h/48h) 수집 전략으로 트윗 성과를 시간대별로 추적합니다.
"""


import re
from datetime import UTC, datetime, timedelta

from loguru import logger as log

from perf_models import TweetMetrics, normalize_angle
from db_layer.connection import db_transaction


class TieredCollectionMixin:
    """[D] Real-time Signal 3-Tier Collection (PerformanceTracker Mixin)."""

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
        """[D] 3단계 수집 스케줄러.

        - 1h tier: 발행 후 45분~90분 내 트윗
        - 6h tier: 발행 후 5~7시간 내 트윗
        - 48h tier: 발행 후 24~72시간 내 트윗

        Returns: {tier_1h: N, tier_6h: N, tier_48h: N}
        """
        conn = await self._get_conn()
        result = {"tier_1h": 0, "tier_6h": 0, "tier_48h": 0}

        try:
            now = datetime.now()
            t1h_start = (now - timedelta(minutes=90)).isoformat()
            t1h_end = (now - timedelta(minutes=45)).isoformat()
            t6h_start = (now - timedelta(hours=7)).isoformat()
            t6h_end = (now - timedelta(hours=5)).isoformat()
            t48h_start = (now - timedelta(hours=72)).isoformat()
            t48h_end = (now - timedelta(hours=24)).isoformat()

            for tier, start, end in [
                ("1h", t1h_start, t1h_end),
                ("6h", t6h_start, t6h_end),
                ("48h", t48h_start, t48h_end),
            ]:
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
                rows = await cursor.fetchall()

                if not rows:
                    continue

                tweet_ids = []
                id_map: dict[str, dict] = {}
                for r in rows:
                    x_tweet_id = (r["x_tweet_id"] or "").strip()
                    posted_at = (r["posted_at"] or "").strip()
                    if x_tweet_id and re.match(r"^\d{10,}$", x_tweet_id):
                        x_id = x_tweet_id
                        tweet_ids.append(x_id)
                        id_map[x_id] = dict(r)
                    elif posted_at and re.match(r"^\d{10,}$", posted_at):
                        x_id = posted_at
                        tweet_ids.append(x_id)
                        id_map[x_id] = dict(r)

                if tweet_ids and self.bearer_token:
                    metrics = await self.batch_collect(tweet_ids)
                    for m in metrics:
                        m.collection_tier = tier
                        row_info = id_map.get(m.tweet_id, {})
                        m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                    count = await self.save_metrics_batch(metrics)
                    result[f"tier_{tier}"] = count

            log.info(f"3단계 수집 완료: 1h={result['tier_1h']}, 6h={result['tier_6h']}, 48h={result['tier_48h']}")
        finally:
            await conn.close()

        return result
