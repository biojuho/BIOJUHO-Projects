"""
getdaytrends Phase 3 - Content Performance Tracker (Feedback Loop)

X/Twitter 게시 트윗의 참여 지표(impressions, likes, retweets, replies, quotes)를
수집하고, 앵글 유형별 성과를 집계하여 최적 앵글 가중치를 피드백.

앵글 유형 (v10.0 기준):
  A. 반전 (reversal)
  B. 데이터 펀치 (data_punch)
  C. 공감 자조 (empathy)
  D. 꿀팁 (tips)
  E. 찬반 도발 (debate)
"""

import asyncio
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

from loguru import logger as log


# ── Data Models ──────────────────────────────────────────

ANGLE_TYPES = ["reversal", "data_punch", "empathy", "tips", "debate"]

# tweet_type(한글) → 정규화된 앵글 키 매핑
_ANGLE_ALIASES: dict[str, str] = {
    # A. 반전
    "반전": "reversal",
    "reversal": "reversal",
    # B. 데이터 펀치
    "데이터 펀치": "data_punch",
    "데이터": "data_punch",
    "data_punch": "data_punch",
    "data punch": "data_punch",
    # C. 공감 자조
    "공감 자조": "empathy",
    "공감": "empathy",
    "공감 유도형": "empathy",
    "empathy": "empathy",
    # D. 꿀팁
    "꿀팁": "tips",
    "꿀팁형": "tips",
    "실용": "tips",
    "tips": "tips",
    # E. 찬반 도발
    "찬반 도발": "debate",
    "찬반": "debate",
    "찬반 질문형": "debate",
    "debate": "debate",
    # 기타 (generator가 자유 생성하는 유형들)
    "딥다이브 분석": "data_punch",
    "핫테이크 오피니언": "reversal",
    "분석형": "data_punch",
    "동기부여형": "empathy",
    "유머/밈형": "empathy",
    "훅 포스트": "reversal",
    "참여형 포스트": "debate",
}


def normalize_angle(tweet_type: str) -> str:
    """tweet_type 문자열을 정규화된 앵글 키로 변환.
    매칭 실패 시 부분 매칭 시도 후 'unknown' 반환.
    """
    if not tweet_type:
        return "unknown"
    key = tweet_type.strip().lower()
    # 정확히 매칭
    if key in _ANGLE_ALIASES:
        return _ANGLE_ALIASES[key]
    # 부분 매칭: 앵글 키워드가 포함되어 있는지 확인
    for alias, angle in _ANGLE_ALIASES.items():
        if alias in key or key in alias:
            return angle
    return "unknown"


@dataclass
class TweetMetrics:
    tweet_id: str
    impressions: int = 0
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    engagement_rate: float = 0.0
    angle_type: str = ""
    collected_at: datetime | None = None

    def compute_engagement_rate(self) -> float:
        """engagement_rate = (likes + retweets + replies + quotes) / impressions."""
        if self.impressions <= 0:
            self.engagement_rate = 0.0
        else:
            total = self.likes + self.retweets + self.replies + self.quotes
            self.engagement_rate = round(total / self.impressions, 6)
        return self.engagement_rate


@dataclass
class AngleStats:
    angle: str
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0
    weight: float = 0.2  # default equal weight (5 angles)


# ── X API v2 Constants ───────────────────────────────────

_X_API_BASE = "https://api.twitter.com/2"
_TWEET_FIELDS = "public_metrics"
# Rate limit: 300 requests / 15 min (App-level) for GET /2/tweets
_RATE_LIMIT_DELAY = 1.0  # seconds between batch items (conservative)
_BATCH_CHUNK_SIZE = 100  # X API max IDs per request


# ── PerformanceTracker ───────────────────────────────────

class PerformanceTracker:
    """
    X/Twitter 게시 트윗의 성과 지표를 수집하고
    앵글 유형별 가중치를 피드백하는 Phase 3 모듈.
    """

    def __init__(self, db_path: str = "data/getdaytrends.db", bearer_token: str = ""):
        self.db_path = db_path
        self.bearer_token = bearer_token
        self._initialized = False

    # ── DB Setup ─────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """동기 SQLite 연결 (성과 테이블 전용)."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_table(self) -> None:
        """tweet_performance 테이블 생성 (멱등)."""
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
                    collected_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tp_angle ON tweet_performance(angle_type);
                CREATE INDEX IF NOT EXISTS idx_tp_collected ON tweet_performance(collected_at);
                CREATE INDEX IF NOT EXISTS idx_tp_tweet_id ON tweet_performance(tweet_id);
            """)
            conn.commit()
            self._initialized = True
            log.debug("tweet_performance 테이블 초기화 완료")
        finally:
            conn.close()

    # ── X API v2 Metric Collection ───────────────────────

    async def collect_metrics(self, tweet_id: str) -> TweetMetrics | None:
        """단일 트윗의 public_metrics를 X API v2에서 수집.

        Returns:
            TweetMetrics or None if API call fails.
        """
        if not self.bearer_token:
            log.warning("bearer_token 미설정 - X API 호출 불가")
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
                    collected_at=datetime.now(timezone.utc),
                )
                tm.compute_engagement_rate()
                return tm

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("retry-after", "60"))
                log.warning(f"X API rate limit hit - retry after {retry_after}s")
            else:
                log.error(f"X API 오류 [{e.response.status_code}]: tweet_id={tweet_id}")
            return None
        except Exception as e:
            log.error(f"X API 요청 실패: tweet_id={tweet_id} - {type(e).__name__}: {e}")
            return None

    async def batch_collect(self, tweet_ids: list[str]) -> list[TweetMetrics]:
        """여러 트윗의 메트릭을 배치 수집 (rate limit 준수).

        X API v2 GET /2/tweets는 최대 100개 ID를 한 번에 조회 가능.
        100개 단위로 청크 분할 후 순차 호출.
        """
        if not self.bearer_token:
            log.warning("bearer_token 미설정 - batch_collect 스킵")
            return []

        if not tweet_ids:
            return []

        results: list[TweetMetrics] = []
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        for i in range(0, len(tweet_ids), _BATCH_CHUNK_SIZE):
            chunk = tweet_ids[i:i + _BATCH_CHUNK_SIZE]
            ids_param = ",".join(chunk)
            url = f"{_X_API_BASE}/tweets"
            params = {"ids": ids_param, "tweet.fields": _TWEET_FIELDS}

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params, headers=headers)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", "60"))
                        log.warning(f"Rate limit - {retry_after}s 대기 후 재시도")
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
                            collected_at=datetime.now(timezone.utc),
                        )
                        tm.compute_engagement_rate()
                        results.append(tm)

            except Exception as e:
                log.error(f"batch_collect 청크 실패 (ids {i}~{i+len(chunk)}): {e}")

            # Rate limit spacing between chunks
            if i + _BATCH_CHUNK_SIZE < len(tweet_ids):
                await asyncio.sleep(_RATE_LIMIT_DELAY)

        log.info(f"batch_collect 완료: {len(results)}/{len(tweet_ids)} 트윗 수집")
        return results

    # ── DB Persistence ───────────────────────────────────

    _UPSERT_SQL = """INSERT INTO tweet_performance
           (tweet_id, impressions, likes, retweets, replies, quotes,
            engagement_rate, angle_type, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tweet_id) DO UPDATE SET
               impressions=excluded.impressions,
               likes=excluded.likes,
               retweets=excluded.retweets,
               replies=excluded.replies,
               quotes=excluded.quotes,
               engagement_rate=excluded.engagement_rate,
               collected_at=excluded.collected_at"""

    @staticmethod
    def _metrics_to_tuple(m: TweetMetrics) -> tuple:
        return (
            m.tweet_id, m.impressions, m.likes, m.retweets,
            m.replies, m.quotes, m.engagement_rate, m.angle_type,
            (m.collected_at or datetime.now(timezone.utc)).isoformat(),
        )

    def save_metrics(self, metrics: TweetMetrics) -> None:
        """단일 TweetMetrics를 tweet_performance 테이블에 저장/갱신."""
        self.init_table()
        conn = self._get_conn()
        try:
            conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(metrics))
            conn.commit()
        finally:
            conn.close()

    def save_metrics_batch(self, metrics_list: list[TweetMetrics]) -> int:
        """여러 TweetMetrics를 일괄 저장. 저장 건수 반환."""
        if not metrics_list:
            return 0
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            for m in metrics_list:
                try:
                    conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(m))
                    saved += 1
                except Exception as e:
                    log.debug(f"save_metrics_batch 개별 실패 (무시): {m.tweet_id} - {e}")
            conn.commit()
        finally:
            conn.close()
        return saved

    # ── Angle Performance Analytics ──────────────────────

    def get_angle_performance(self, days: int = 30) -> dict[str, AngleStats]:
        """앵글 유형별 성과 집계.

        Returns:
            {angle_type: AngleStats} - 최근 N일간 앵글별 평균 임프레션/참여율.
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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

            # 데이터 없는 앵글도 기본값으로 포함
            for a in ANGLE_TYPES:
                if a not in result:
                    result[a] = AngleStats(angle=a)

            return result
        finally:
            conn.close()

    def get_optimal_angle_weights(
        self, days: int = 30, min_samples: int = 5,
        _precomputed_stats: dict[str, AngleStats] | None = None,
    ) -> dict[str, float]:
        """앵글 유형별 최적 가중치 계산.

        engagement_rate 기반 소프트맥스 유사 정규화.
        min_samples 미만인 앵글은 기본 가중치(1/N) 유지.

        Returns:
            {angle_type: weight} - 합계 1.0 (확률 분포).
        """
        stats = _precomputed_stats or self.get_angle_performance(days)
        n = len(ANGLE_TYPES)
        default_weight = 1.0 / n

        # 충분한 샘플이 있는 앵글만 가중치 계산 대상
        scored: dict[str, float] = {}
        unscorable: list[str] = []

        for angle in ANGLE_TYPES:
            s = stats.get(angle)
            if s and s.total_tweets >= min_samples:
                # engagement_rate를 점수로 사용 (0 이상 보장)
                scored[angle] = max(s.avg_engagement_rate, 1e-8)
            else:
                unscorable.append(angle)

        if not scored:
            # 데이터 불충분 - 균등 분배
            return {a: default_weight for a in ANGLE_TYPES}

        # 점수 비례 가중치 계산
        total_score = sum(scored.values())
        # unscorable 앵글에 할당할 총 비중 (탐색 예산)
        explore_budget = len(unscorable) * default_weight
        exploit_budget = 1.0 - explore_budget

        weights: dict[str, float] = {}
        for angle in ANGLE_TYPES:
            if angle in scored:
                weights[angle] = round(exploit_budget * (scored[angle] / total_score), 4)
            else:
                weights[angle] = round(default_weight, 4)

        # 정규화 보정 (부동소수점 오차)
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        # AngleStats에 weight 반영
        for angle, w in weights.items():
            if angle in stats:
                stats[angle].weight = w

        return weights

    # ── Scheduler Integration ────────────────────────────

    async def run_collection_cycle(self, lookback_hours: int = 48) -> int:
        """스케줄러 호출용: 최근 게시되었으나 성과 미수집 트윗을 찾아 메트릭 수집.

        1. tweets 테이블에서 posted_at이 있고 tweet_performance에 없는 트윗 조회
        2. X API로 메트릭 수집
        3. angle_type 매핑 후 저장

        Returns:
            수집 완료 건수.
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()

            # posted_at이 있고 아직 수집되지 않은 트윗 조회
            # tweets.content에서 tweet_id를 추출하는 것이 아니라
            # posted_at이 설정된 트윗의 DB id + tweet_type을 가져옴
            rows = conn.execute(
                """SELECT t.id, t.tweet_type, t.posted_at, t.content
                   FROM tweets t
                   WHERE t.posted_at IS NOT NULL
                     AND t.posted_at >= ?
                     AND t.id NOT IN (
                         SELECT CAST(tweet_id AS INTEGER)
                         FROM tweet_performance
                         WHERE tweet_id GLOB '[0-9]*'
                     )
                   ORDER BY t.posted_at DESC
                   LIMIT 200""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            log.debug("run_collection_cycle: 미수집 트윗 없음")
            return 0

        log.info(f"run_collection_cycle: {len(rows)}개 미수집 트윗 발견")

        # posted_at 필드에 X tweet_id가 저장되어 있다고 가정하는 대신
        # tweets 테이블의 id를 tweet_id로 사용 (로컬 DB 추적)
        # 실제 X tweet_id가 별도 컬럼에 있다면 그 컬럼을 사용해야 함
        # 여기서는 DB id 기준으로 로컬 성과 추적

        # X API를 통한 실제 메트릭 수집 시도
        # posted_at 필드 값이 실제 X tweet_id를 포함하는 경우를 처리
        tweet_id_map: dict[str, dict] = {}  # x_tweet_id -> row info
        local_only: list[dict] = []

        for row in rows:
            row_dict = dict(row)
            posted_at = row_dict.get("posted_at", "")
            # posted_at이 숫자로만 구성되면 X tweet ID로 간주
            if posted_at and re.match(r"^\d{10,}$", posted_at.strip()):
                x_id = posted_at.strip()
                tweet_id_map[x_id] = row_dict
            else:
                local_only.append(row_dict)

        collected_count = 0

        # X API 배치 수집
        all_metrics: list[TweetMetrics] = []
        if tweet_id_map and self.bearer_token:
            x_ids = list(tweet_id_map.keys())
            metrics_list = await self.batch_collect(x_ids)

            for m in metrics_list:
                row_info = tweet_id_map.get(m.tweet_id, {})
                m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                all_metrics.append(m)

        # 로컬 트윗 (X API 없이 DB 기록만)
        for row_dict in local_only:
            db_id = str(row_dict["id"])
            angle = normalize_angle(row_dict.get("tweet_type", ""))
            all_metrics.append(TweetMetrics(
                tweet_id=db_id,
                angle_type=angle,
                collected_at=datetime.now(timezone.utc),
            ))

        # 일괄 저장 (N+1 방지)
        collected_count = self.save_metrics_batch(all_metrics)

        log.info(
            f"run_collection_cycle 완료: {collected_count}건 수집 "
            f"(X API: {len(tweet_id_map)}건, 로컬: {len(local_only)}건)"
        )
        return collected_count

    # ── Utility ──────────────────────────────────────────

    def get_summary(self, days: int = 30) -> dict:
        """대시보드/로깅용 성과 요약."""
        stats = self.get_angle_performance(days)
        weights = self.get_optimal_angle_weights(days, _precomputed_stats=stats)

        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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
            "angle_stats": {k: {
                "total_tweets": v.total_tweets,
                "avg_impressions": v.avg_impressions,
                "avg_engagement_rate": v.avg_engagement_rate,
                "weight": weights.get(k, 0.2),
            } for k, v in stats.items()},
            "optimal_weights": weights,
        }
