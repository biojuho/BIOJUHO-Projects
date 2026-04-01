"""
getdaytrends Phase 3+ - Content Performance Tracker (Adaptive Feedback Loop)

X/Twitter 게시 트윗의 참여 지표(impressions, likes, retweets, replies, quotes)를
수집하고, 앵글 패턴별 성과를 집계하여 최적 앵글 가중치를 피드백합니다.
"""

import asyncio
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from loguru import logger as log

from perf_genealogy import TrendGenealogyMixin

# -- mixin imports (분리된 기능 모듈) --
from perf_golden_refs import GoldenReferenceMixin

# -- models import --
from perf_models import (  # noqa: F401
    _ANGLE_ALIASES,
    _HOOK_ALIASES,
    _KICK_ALIASES,
    ANGLE_TYPES,
    HOOK_PATTERNS,
    KICK_PATTERNS,
    AngleStats,
    GoldenReference,
    PatternStats,
    TweetMetrics,
    normalize_angle,
    normalize_hook,
    normalize_kick,
)
from perf_tiered import TieredCollectionMixin

# -- X API v2 Constants --

_X_API_BASE = "https://api.twitter.com/2"
_TWEET_FIELDS = "public_metrics"
# Rate limit: 300 requests / 15 min (App-level) for GET /2/tweets
_RATE_LIMIT_DELAY = 1.0  # seconds between batch items (conservative)
_BATCH_CHUNK_SIZE = 100  # X API max IDs per request


# -- PerformanceTracker --


class PerformanceTracker(GoldenReferenceMixin, TrendGenealogyMixin, TieredCollectionMixin):
    """
    X/Twitter 트윗 성과 지표를 수집하고
    앵글 유형별 가중치를 피드백하는 Phase 3 모듈.
    """

    def __init__(self, db_path: str = "data/getdaytrends.db", bearer_token: str = ""):
        self.db_path = db_path
        self.bearer_token = bearer_token
        self._initialized = False

    # -- DB Setup --

    def _get_conn(self) -> sqlite3.Connection:
        """동기 SQLite 연결 (성과 테이블 전용). 향후 Postgres 확장을 고려한 Adapter Point."""
        db_url = os.environ.get("DATABASE_URL")
        if db_url and db_url.startswith("postgresql"):
            # TODO(Phase 4): Implement psycopg2/asyncpg adapter for Supabase cloud migration
            log.warning("PostgreSQL DATABASE_URL detected, but PerformanceTracker still uses local SQLite as fallback.")

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_table(self) -> None:
        """tweet_performance + golden_references + trend_genealogy 관련 테이블 멱등적 생성."""
        if self._initialized:
            return
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tweet_performance (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id     TEXT NOT NULL UNIQUE,
                    impressions  INTEGER DEFAULT 0,
                    likes        INTEGER DEFAULT 0,
                    retweets     INTEGER DEFAULT 0,
                    replies      INTEGER DEFAULT 0,
                    quotes       INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    angle_type   TEXT DEFAULT '',
                    hook_pattern TEXT DEFAULT '',
                    kick_pattern TEXT DEFAULT '',
                    collection_tier TEXT DEFAULT '48h',
                    collected_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tp_angle ON tweet_performance(angle_type);
                CREATE INDEX IF NOT EXISTS idx_tp_collected ON tweet_performance(collected_at);
                CREATE INDEX IF NOT EXISTS idx_tp_tweet_id ON tweet_performance(tweet_id);
                CREATE INDEX IF NOT EXISTS idx_tp_hook ON tweet_performance(hook_pattern);
                CREATE INDEX IF NOT EXISTS idx_tp_kick ON tweet_performance(kick_pattern);

                -- [E] Golden References Schema
                CREATE TABLE IF NOT EXISTS golden_references (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id        TEXT NOT NULL UNIQUE,
                    content         TEXT NOT NULL,
                    angle_type      TEXT DEFAULT '',
                    hook_pattern    TEXT DEFAULT '',
                    kick_pattern    TEXT DEFAULT '',
                    engagement_rate REAL DEFAULT 0.0,
                    impressions     INTEGER DEFAULT 0,
                    category        TEXT DEFAULT '',
                    saved_at        TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_gr_angle ON golden_references(angle_type);
                CREATE INDEX IF NOT EXISTS idx_gr_er ON golden_references(engagement_rate);

                -- [A] Trend Genealogy Schema
                CREATE TABLE IF NOT EXISTS trend_genealogy (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword         TEXT NOT NULL,
                    parent_keyword  TEXT DEFAULT '',
                    predicted_children TEXT DEFAULT '[]',
                    genealogy_depth INTEGER DEFAULT 0,
                    first_seen_at   TEXT NOT NULL,
                    last_seen_at    TEXT NOT NULL,
                    total_appearances INTEGER DEFAULT 1,
                    peak_viral_score INTEGER DEFAULT 0,
                    UNIQUE(keyword, parent_keyword)
                );
                CREATE INDEX IF NOT EXISTS idx_tg_keyword ON trend_genealogy(keyword);
                CREATE INDEX IF NOT EXISTS idx_tg_parent ON trend_genealogy(parent_keyword);
                CREATE INDEX IF NOT EXISTS idx_tg_last_seen ON trend_genealogy(last_seen_at);
            """)
            try:
                conn.execute("SELECT x_tweet_id FROM tweets LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE tweets ADD COLUMN x_tweet_id TEXT DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id)")
            conn.commit()
            self._initialized = True
            log.debug("DB 테이블 설계 초기화 완료")
        finally:
            conn.close()

    # -- X API v2 Metric Collection --

    async def collect_metrics(self, tweet_id: str) -> TweetMetrics | None:
        """단일 트윗의 public_metrics를 X API v2에서 수집.

        Returns:
            TweetMetrics or None if API call fails.
        """
        if not self.bearer_token:
            log.warning("bearer_token 미설정 - X API 통신 불가")
            return None

        url = f"{_X_API_BASE}/tweets/{tweet_id}"
        params = {"tweet.fields": _TWEET_FIELDS}
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                metrics = data.get("public_metrics", {})

                tm = TweetMetrics(
                    tweet_id=tweet_id,
                    impressions=metrics.get("impression_count", 0),
                    likes=metrics.get("like_count", 0),
                    retweets=metrics.get("retweet_count", 0),
                    replies=metrics.get("reply_count", 0),
                    quotes=metrics.get("quote_count", 0),
                    collected_at=datetime.now(UTC),
                )
                tm.compute_engagement_rate()
                return tm

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("retry-after", "60"))
                log.warning(f"X API Rate Limit 초과 - {retry_after}초 후 재시도 필요")
            else:
                log.error(f"X API 응답 오류 [{e.response.status_code}]: tweet_id={tweet_id}")
            return None
        except Exception as e:
            log.error(f"X API 요청 자체 실패: tweet_id={tweet_id} - {type(e).__name__}: {e}")
            return None

    async def batch_collect(self, tweet_ids: list[str]) -> list[TweetMetrics]:
        """여러 트윗의 메트릭을 배치 수집 (Rate Limit 준수).

        X API v2 GET /2/tweets는 1요청당 100건 지원.
        """
        if not self.bearer_token:
            log.warning("bearer_token 미설정 - batch_collect 건너뜀")
            return []

        if not tweet_ids:
            return []

        results: list[TweetMetrics] = []
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        for i in range(0, len(tweet_ids), _BATCH_CHUNK_SIZE):
            chunk = tweet_ids[i : i + _BATCH_CHUNK_SIZE]
            ids_param = ",".join(chunk)
            url = f"{_X_API_BASE}/tweets"
            params = {"ids": ids_param, "tweet.fields": _TWEET_FIELDS}

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params, headers=headers)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", "60"))
                        log.warning(f"Rate Limit 감지 - {retry_after}초 대기 후 재시도")
                        await asyncio.sleep(retry_after)
                        resp = await client.get(url, params=params, headers=headers)

                    resp.raise_for_status()
                    data_list = resp.json().get("data", [])

                    for data in data_list:
                        metrics = data.get("public_metrics", {})
                        tm = TweetMetrics(
                            tweet_id=data["id"],
                            impressions=metrics.get("impression_count", 0),
                            likes=metrics.get("like_count", 0),
                            retweets=metrics.get("retweet_count", 0),
                            replies=metrics.get("reply_count", 0),
                            quotes=metrics.get("quote_count", 0),
                            collected_at=datetime.now(UTC),
                        )
                        tm.compute_engagement_rate()
                        results.append(tm)

            except Exception as e:
                log.error(f"batch_collect 청크 실패 (ids {i}~{i+len(chunk)}): {e}")

            if i + _BATCH_CHUNK_SIZE < len(tweet_ids):
                await asyncio.sleep(_RATE_LIMIT_DELAY)

        log.info(f"batch_collect 완료: {len(results)}/{len(tweet_ids)} 트윗 수집")
        return results

    # -- DB Persistence --

    _UPSERT_SQL = """INSERT INTO tweet_performance
           (tweet_id, impressions, likes, retweets, replies, quotes,
            engagement_rate, angle_type, hook_pattern, kick_pattern,
            collection_tier, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tweet_id) DO UPDATE SET
               impressions=excluded.impressions,
               likes=excluded.likes,
               retweets=excluded.retweets,
               replies=excluded.replies,
               quotes=excluded.quotes,
               engagement_rate=excluded.engagement_rate,
               collection_tier=excluded.collection_tier,
               collected_at=excluded.collected_at"""

    @staticmethod
    def _metrics_to_tuple(m: TweetMetrics) -> tuple:
        return (
            m.tweet_id,
            m.impressions,
            m.likes,
            m.retweets,
            m.replies,
            m.quotes,
            m.engagement_rate,
            m.angle_type,
            m.hook_pattern,
            m.kick_pattern,
            m.collection_tier,
            (m.collected_at or datetime.now(UTC)).isoformat(),
        )

    @staticmethod
    def _total_engagements(m: TweetMetrics) -> int:
        return int(m.likes + m.retweets + m.replies + m.quotes)

    def _sync_tweet_summary(self, conn: sqlite3.Connection, metrics: TweetMetrics) -> None:
        engagements = self._total_engagements(metrics)
        cursor = conn.execute(
            """UPDATE tweets
               SET impressions = ?,
                   engagements = ?,
                   engagement_rate = ?
               WHERE x_tweet_id = ?""",
            (metrics.impressions, engagements, metrics.engagement_rate, metrics.tweet_id),
        )
        if cursor.rowcount:
            return

        if metrics.tweet_id.isdigit():
            conn.execute(
                """UPDATE tweets
                   SET impressions = ?,
                       engagements = ?,
                       engagement_rate = ?
                   WHERE id = ?""",
                (metrics.impressions, engagements, metrics.engagement_rate, int(metrics.tweet_id)),
            )

    def save_metrics(self, metrics: TweetMetrics) -> None:
        """단일 TweetMetrics를 DB에 저장/갱신."""
        self.init_table()
        conn = self._get_conn()
        try:
            conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(metrics))
            self._sync_tweet_summary(conn, metrics)
            conn.commit()
        finally:
            conn.close()

    def save_metrics_batch(self, metrics_list: list[TweetMetrics]) -> int:
        """다수의 TweetMetrics를 일괄 저장. 성공 건수 반환."""
        if not metrics_list:
            return 0
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            for m in metrics_list:
                try:
                    conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(m))
                    self._sync_tweet_summary(conn, m)
                    saved += 1
                except Exception as e:
                    log.debug(f"save_metrics_batch 개별 오류 (건너뜀): {m.tweet_id} - {e}")
            conn.commit()
        finally:
            conn.close()
        return saved

    # -- Angle Performance Analytics --

    def get_angle_performance(self, days: int = 30) -> dict[str, AngleStats]:
        """앵글 유형별 성과 집계.

        Returns:
            {angle_type: AngleStats} - 최근 N일간의 성과 요약.
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT angle_type,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND angle_type != '' AND angle_type != 'unknown'
                   GROUP BY angle_type
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, AngleStats] = {}
            for row in rows:
                angle = row["angle_type"]
                result[angle] = AngleStats(
                    angle=angle,
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )

            for a in ANGLE_TYPES:
                if a not in result:
                    result[a] = AngleStats(angle=a)

            return result
        finally:
            conn.close()

    def get_optimal_angle_weights(
        self,
        days: int = 30,
        min_samples: int = 5,
        _precomputed_stats: dict[str, AngleStats] | None = None,
    ) -> dict[str, float]:
        """앵글 유형별 최적 가중치 계산.

        Returns:
            {angle_type: weight} - 확률 모델에 사용될 가중치 (합계 1.0).
        """
        stats = _precomputed_stats or self.get_angle_performance(days)
        n = len(ANGLE_TYPES)
        default_weight = 1.0 / n

        scored: dict[str, float] = {}
        unscorable: list[str] = []

        for angle in ANGLE_TYPES:
            s = stats.get(angle)
            if s and s.total_tweets >= min_samples:
                scored[angle] = max(s.avg_engagement_rate, 1e-8)
            else:
                unscorable.append(angle)

        if not scored:
            return {a: default_weight for a in ANGLE_TYPES}

        total_score = sum(scored.values())
        explore_budget = len(unscorable) * default_weight
        exploit_budget = 1.0 - explore_budget

        weights: dict[str, float] = {}
        for angle in ANGLE_TYPES:
            if angle in scored:
                weights[angle] = round(exploit_budget * (scored[angle] / total_score), 4)
            else:
                weights[angle] = round(default_weight, 4)

        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        for angle, w in weights.items():
            if angle in stats:
                stats[angle].weight = w

        return weights

    # -- Scheduler Integration --

    async def run_collection_cycle(self, lookback_hours: int = 48) -> int:
        """주기적 스케줄러 호출용. 미수집 트윗의 메트릭 업데이트 사이클 구성.

        Returns:
            업데이트된 DB 행수.
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()
            rows = conn.execute(
                """SELECT t.id, t.tweet_type, t.posted_at, t.x_tweet_id, t.content
                   FROM tweets t
                   WHERE t.posted_at IS NOT NULL
                     AND t.posted_at >= ?
                     AND (
                         (t.x_tweet_id IS NOT NULL AND t.x_tweet_id != '' AND t.x_tweet_id NOT IN (
                             SELECT tweet_id
                             FROM tweet_performance
                         ))
                         OR
                         ((t.x_tweet_id IS NULL OR t.x_tweet_id = '') AND t.id NOT IN (
                             SELECT CAST(tweet_id AS INTEGER)
                             FROM tweet_performance
                             WHERE tweet_id GLOB '[0-9]*'
                         ))
                     )
                   ORDER BY t.posted_at DESC
                   LIMIT 200""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return 0

        tweet_id_map: dict[str, dict] = {}
        local_only: list[dict] = []

        for row in rows:
            row_dict = dict(row)
            x_tweet_id = (row_dict.get("x_tweet_id", "") or "").strip()
            posted_at = (row_dict.get("posted_at", "") or "").strip()
            if x_tweet_id and re.match(r"^\d{10,}$", x_tweet_id):
                x_id = x_tweet_id
                tweet_id_map[x_id] = row_dict
            elif posted_at and re.match(r"^\d{10,}$", posted_at):
                x_id = posted_at
                tweet_id_map[x_id] = row_dict
            else:
                local_only.append(row_dict)

        collected_count = 0
        all_metrics: list[TweetMetrics] = []
        if tweet_id_map and self.bearer_token:
            x_ids = list(tweet_id_map.keys())
            metrics_list = await self.batch_collect(x_ids)

            for m in metrics_list:
                row_info = tweet_id_map.get(m.tweet_id, {})
                m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                all_metrics.append(m)

        for row_dict in local_only:
            db_id = str(row_dict["id"])
            angle = normalize_angle(row_dict.get("tweet_type", ""))
            all_metrics.append(
                TweetMetrics(
                    tweet_id=db_id,
                    angle_type=angle,
                    collected_at=datetime.now(UTC),
                )
            )

        collected_count = self.save_metrics_batch(all_metrics)
        return collected_count

    # -- [B] Hook/Kick Pattern Analytics --

    def get_hook_performance(self, days: int = 30) -> dict[str, PatternStats]:
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT hook_pattern,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND hook_pattern != '' AND hook_pattern != 'unknown'
                   GROUP BY hook_pattern
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, PatternStats] = {}
            for row in rows:
                p = row["hook_pattern"]
                result[p] = PatternStats(
                    pattern=p,
                    pattern_type="hook",
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )
            for p in HOOK_PATTERNS:
                if p not in result:
                    result[p] = PatternStats(pattern=p, pattern_type="hook")
            return result
        finally:
            conn.close()

    def get_kick_performance(self, days: int = 30) -> dict[str, PatternStats]:
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT kick_pattern,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND kick_pattern != '' AND kick_pattern != 'unknown'
                   GROUP BY kick_pattern
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, PatternStats] = {}
            for row in rows:
                p = row["kick_pattern"]
                result[p] = PatternStats(
                    pattern=p,
                    pattern_type="kick",
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )
            for p in KICK_PATTERNS:
                if p not in result:
                    result[p] = PatternStats(pattern=p, pattern_type="kick")
            return result
        finally:
            conn.close()

    def get_optimal_pattern_weights(
        self,
        days: int = 30,
        min_samples: int = 3,
    ) -> dict[str, dict[str, float]]:
        hook_stats = self.get_hook_performance(days)
        kick_stats = self.get_kick_performance(days)

        def _compute_weights(stats: dict[str, PatternStats], all_patterns: list[str]) -> dict[str, float]:
            n = len(all_patterns)
            default_w = 1.0 / n
            scored = {}
            for p in all_patterns:
                s = stats.get(p)
                if s and s.total_tweets >= min_samples:
                    scored[p] = max(s.avg_engagement_rate, 1e-8)
            if not scored:
                return {p: round(default_w, 4) for p in all_patterns}
            total = sum(scored.values())
            unscorable_count = n - len(scored)
            explore = unscorable_count * default_w
            exploit = 1.0 - explore
            weights = {}
            for p in all_patterns:
                if p in scored:
                    weights[p] = round(exploit * (scored[p] / total), 4)
                else:
                    weights[p] = round(default_w, 4)
            w_total = sum(weights.values())
            if w_total > 0:
                weights = {k: round(v / w_total, 4) for k, v in weights.items()}
            return weights

        angle_stats = self.get_angle_performance(days)
        angle_weights = self.get_optimal_angle_weights(days, min_samples=min_samples, _precomputed_stats=angle_stats)

        return {
            "hook_weights": _compute_weights(hook_stats, HOOK_PATTERNS),
            "kick_weights": _compute_weights(kick_stats, KICK_PATTERNS),
            "angle_weights": angle_weights,
        }

    # -- Utility --

    def get_summary(self, days: int = 30) -> dict:
        stats = self.get_angle_performance(days)
        weights = self.get_optimal_angle_weights(days, _precomputed_stats=stats)
        pattern_weights = self.get_optimal_pattern_weights(days)

        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            row = conn.execute(
                """SELECT COUNT(*) as total,
                          AVG(engagement_rate) as avg_er,
                          AVG(impressions) as avg_imp,
                          MAX(engagement_rate) as max_er
                   FROM tweet_performance
                   WHERE collected_at >= ?""",
                (cutoff,),
            ).fetchone()
            overview = dict(row) if row else {}
        finally:
            conn.close()

        return {
            "period_days": days,
            "total_tracked": overview.get("total", 0) or 0,
            "avg_engagement_rate": round(overview.get("avg_er", 0.0) or 0.0, 6),
            "avg_impressions": round(overview.get("avg_imp", 0.0) or 0.0, 1),
            "max_engagement_rate": round(overview.get("max_er", 0.0) or 0.0, 6),
            "angle_stats": {
                k: {
                    "total_tweets": v.total_tweets,
                    "avg_impressions": v.avg_impressions,
                    "avg_engagement_rate": v.avg_engagement_rate,
                    "weight": weights.get(k, 0.2),
                }
                for k, v in stats.items()
            },
            "optimal_weights": weights,
            "pattern_weights": pattern_weights,
        }
