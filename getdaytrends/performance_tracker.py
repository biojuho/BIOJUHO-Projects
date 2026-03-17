"""
getdaytrends Phase 3+ - Content Performance Tracker (Adaptive Feedback Loop)

X/Twitter 게시 트윗의 참여 지표(impressions, likes, retweets, replies, quotes)를
수집하고, 앵글 유형별 성과를 집계하여 최적 앵글 가중치를 피드백.

v5.0 (2026-03-17) 강화:
  B. Adaptive Voice — 훅/킥 패턴별 성과 추적 + 골든 레퍼런스 자동 갱신
  D. Real-time Signal — 3단계 수집 (1h/6h/48h) + 초기 시그널 기반 후속 트리거
  E. Benchmark QA — 상위 트윗 골든 레퍼런스 저장/조회

앵글 유형 (v10.0 기준):
  A. 반전 (reversal)
  B. 데이터 펀치 (data_punch)
  C. 공감 자조 (empathy)
  D. 꿀팁 (tips)
  E. 찬반 도발 (debate)
"""

import asyncio
import json
import re
import sqlite3
from dataclasses import dataclass
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
    hook_pattern: str = ""   # [B] 훅 패턴: number_shock|relatable_math|reversal|insider|contrast|question
    kick_pattern: str = ""   # [B] 킥 패턴: mic_drop|self_deprecation|uncertainty|manifesto|twist
    collected_at: datetime | None = None
    collection_tier: str = ""  # [D] 수집 단계: "1h"|"6h"|"48h"

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


# [B] 훅/킥 패턴 정규화 매핑
HOOK_PATTERNS = ["number_shock", "relatable_math", "reversal", "insider", "contrast", "question"]
KICK_PATTERNS = ["mic_drop", "self_deprecation", "uncertainty", "manifesto", "twist"]

_HOOK_ALIASES: dict[str, str] = {
    "숫자충격": "number_shock", "숫자 충격": "number_shock", "number_shock": "number_shock",
    "체감환산": "relatable_math", "체감 환산": "relatable_math", "relatable_math": "relatable_math",
    "반전선언": "reversal", "반전 선언": "reversal",
    "내부자시선": "insider", "내부자 시선": "insider", "insider": "insider",
    "대조병치": "contrast", "대조 병치": "contrast", "contrast": "contrast",
    "질문도발": "question", "질문 도발": "question", "question": "question",
}

_KICK_ALIASES: dict[str, str] = {
    "뒤통수": "mic_drop", "mic_drop": "mic_drop",
    "자조형": "self_deprecation", "자조": "self_deprecation", "self_deprecation": "self_deprecation",
    "질문형": "uncertainty", "uncertainty": "uncertainty",
    "선언형": "manifesto", "manifesto": "manifesto",
    "반전형": "twist", "twist": "twist",
}


def normalize_hook(hook_type: str) -> str:
    """훅 패턴 정규화."""
    if not hook_type:
        return "unknown"
    key = hook_type.strip().lower()
    if key in _HOOK_ALIASES:
        return _HOOK_ALIASES[key]
    for alias, pattern in _HOOK_ALIASES.items():
        if alias in key or key in alias:
            return pattern
    return "unknown"


def normalize_kick(kick_type: str) -> str:
    """킥 패턴 정규화."""
    if not kick_type:
        return "unknown"
    key = kick_type.strip().lower()
    if key in _KICK_ALIASES:
        return _KICK_ALIASES[key]
    for alias, pattern in _KICK_ALIASES.items():
        if alias in key or key in alias:
            return pattern
    return "unknown"


@dataclass
class PatternStats:
    """[B] 훅/킥 패턴별 성과 통계."""
    pattern: str
    pattern_type: str  # "hook" | "kick"
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0
    weight: float = 0.0


@dataclass
class GoldenReference:
    """[E] 골든 레퍼런스 — 고성과 트윗을 QA 벤치마크로 저장."""
    tweet_id: str
    content: str
    angle_type: str
    hook_pattern: str
    kick_pattern: str
    engagement_rate: float
    impressions: int
    category: str = ""
    saved_at: datetime | None = None


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
        """tweet_performance + golden_references + trend_genealogy 테이블 생성 (멱등)."""
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

                -- [E] Golden References: 고성과 트윗 벤치마크
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

                -- [A] Trend Genealogy: 트렌드 계보 추적
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
            conn.commit()
            self._initialized = True
            log.debug("tweet_performance + golden_references + trend_genealogy 테이블 초기화 완료")
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
            m.tweet_id, m.impressions, m.likes, m.retweets,
            m.replies, m.quotes, m.engagement_rate, m.angle_type,
            m.hook_pattern, m.kick_pattern, m.collection_tier,
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

    # ── [B] Hook/Kick Pattern Analytics ──────────────────

    def get_hook_performance(self, days: int = 30) -> dict[str, PatternStats]:
        """[B] 훅 패턴별 성과 집계."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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
                    pattern=p, pattern_type="hook",
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
        """[B] 킥 패턴별 성과 집계."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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
                    pattern=p, pattern_type="kick",
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
        self, days: int = 30, min_samples: int = 3,
    ) -> dict[str, dict[str, float]]:
        """[B] 훅/킥 패턴별 최적 가중치 계산 — 생성 프롬프트에 주입."""
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

        return {
            "hook_weights": _compute_weights(hook_stats, HOOK_PATTERNS),
            "kick_weights": _compute_weights(kick_stats, KICK_PATTERNS),
        }

    # ── [E] Golden Reference Management ────────────────

    def save_golden_reference(self, ref: GoldenReference) -> None:
        """[E] 골든 레퍼런스 저장. 최대 20개 유지 (낮은 ER 자동 교체)."""
        self.init_table()
        conn = self._get_conn()
        try:
            # 현재 개수 확인
            count = conn.execute("SELECT COUNT(*) FROM golden_references").fetchone()[0]
            if count >= 20:
                # 가장 낮은 engagement_rate 제거
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
                (ref.tweet_id, ref.content, ref.angle_type, ref.hook_pattern,
                 ref.kick_pattern, ref.engagement_rate, ref.impressions,
                 ref.category, (ref.saved_at or datetime.now(timezone.utc)).isoformat()),
            )
            conn.commit()
            log.debug(f"골든 레퍼런스 저장: tweet_id={ref.tweet_id}, ER={ref.engagement_rate}")
        finally:
            conn.close()

    def get_golden_references(self, limit: int = 5, category: str = "") -> list[GoldenReference]:
        """[E] 상위 골든 레퍼런스 조회 (QA 벤치마크용)."""
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
                    tweet_id=r["tweet_id"], content=r["content"],
                    angle_type=r["angle_type"], hook_pattern=r["hook_pattern"],
                    kick_pattern=r["kick_pattern"], engagement_rate=r["engagement_rate"],
                    impressions=r["impressions"], category=r.get("category", ""),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def auto_update_golden_references(self, days: int = 7, top_n: int = 10) -> int:
        """[E] 최근 N일간 상위 트윗을 자동으로 골든 레퍼런스에 등록.
        tweets 테이블에서 content를 조인하여 가져옴.
        Returns: 새로 등록된 건수.
        """
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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
                    saved_at=datetime.now(timezone.utc),
                )
                self.save_golden_reference(ref)
                saved += 1

            log.info(f"골든 레퍼런스 자동 갱신: {saved}/{len(rows)}건")
        finally:
            conn.close()
        return saved

    # ── [D] Real-time Signal (3-Tier Collection) ───────

    async def collect_early_signal(self, tweet_ids: list[str], tier: str = "1h") -> list[TweetMetrics]:
        """[D] 초기 시그널 수집 (발행 1시간 후). 높은 초기 ER → 후속 콘텐츠 트리거."""
        metrics = await self.batch_collect(tweet_ids)
        for m in metrics:
            m.collection_tier = tier
        if metrics:
            self.save_metrics_batch(metrics)
        return metrics

    def get_early_signal_analysis(self, hours: int = 2) -> dict:
        """[D] 최근 N시간 내 수집된 초기 시그널 분석.
        Returns: {boost_candidates: [...], suppress_candidates: [...], avg_metrics: {...}}
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT tweet_id, impressions, engagement_rate, angle_type
                   FROM tweet_performance
                   WHERE collection_tier = '1h' AND collected_at >= ?
                   ORDER BY engagement_rate DESC""",
                (cutoff,),
            ).fetchall()

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
            conn.close()

    async def run_tiered_collection(self, lookback_hours: int = 48) -> dict:
        """[D] 3단계 수집 오케스트레이터.
        - 1h tier: 발행 후 45분~90분 된 트윗
        - 6h tier: 발행 후 5~7시간 된 트윗
        - 48h tier: 발행 후 24~72시간 된 트윗
        Returns: {tier_1h: N, tier_6h: N, tier_48h: N}
        """
        self.init_table()
        conn = self._get_conn()
        result = {"tier_1h": 0, "tier_6h": 0, "tier_48h": 0}

        try:
            now = datetime.now()
            # 1h tier: 45분~90분 전 발행
            t1h_start = (now - timedelta(minutes=90)).isoformat()
            t1h_end = (now - timedelta(minutes=45)).isoformat()
            # 6h tier: 5~7시간 전 발행
            t6h_start = (now - timedelta(hours=7)).isoformat()
            t6h_end = (now - timedelta(hours=5)).isoformat()
            # 48h tier: 24~72시간 전 발행 (기존 로직)
            t48h_start = (now - timedelta(hours=72)).isoformat()
            t48h_end = (now - timedelta(hours=24)).isoformat()

            for tier, start, end in [
                ("1h", t1h_start, t1h_end),
                ("6h", t6h_start, t6h_end),
                ("48h", t48h_start, t48h_end),
            ]:
                rows = conn.execute(
                    """SELECT t.id, t.tweet_type, t.posted_at
                       FROM tweets t
                       WHERE t.posted_at IS NOT NULL
                         AND t.posted_at >= ? AND t.posted_at <= ?
                         AND t.id NOT IN (
                             SELECT CAST(tweet_id AS INTEGER)
                             FROM tweet_performance
                             WHERE collection_tier = ? AND tweet_id GLOB '[0-9]*'
                         )
                       LIMIT 100""",
                    (start, end, tier),
                ).fetchall()

                if not rows:
                    continue

                tweet_ids = []
                id_map: dict[str, dict] = {}
                for r in rows:
                    posted_at = r["posted_at"] or ""
                    if posted_at and re.match(r"^\d{10,}$", posted_at.strip()):
                        x_id = posted_at.strip()
                        tweet_ids.append(x_id)
                        id_map[x_id] = dict(r)

                if tweet_ids and self.bearer_token:
                    metrics = await self.batch_collect(tweet_ids)
                    for m in metrics:
                        m.collection_tier = tier
                        row_info = id_map.get(m.tweet_id, {})
                        m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                    count = self.save_metrics_batch(metrics)
                    result[f"tier_{tier}"] = count

            log.info(f"3단계 수집 완료: 1h={result['tier_1h']}, 6h={result['tier_6h']}, 48h={result['tier_48h']}")
        finally:
            conn.close()

        return result

    # ── [A] Trend Genealogy ────────────────────────────

    def save_trend_genealogy(
        self, keyword: str, parent_keyword: str = "",
        predicted_children: list[str] | None = None,
        viral_score: int = 0,
    ) -> None:
        """[A] 트렌드 계보 저장/갱신."""
        self.init_table()
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        children_json = json.dumps(predicted_children or [], ensure_ascii=False)
        try:
            existing = conn.execute(
                "SELECT id, total_appearances, peak_viral_score FROM trend_genealogy WHERE keyword = ? AND parent_keyword = ?",
                (keyword, parent_keyword),
            ).fetchone()
            if existing:
                new_count = existing["total_appearances"] + 1
                new_peak = max(existing["peak_viral_score"], viral_score)
                conn.execute(
                    """UPDATE trend_genealogy
                       SET last_seen_at = ?, total_appearances = ?,
                           peak_viral_score = ?, predicted_children = ?
                       WHERE id = ?""",
                    (now, new_count, new_peak, children_json, existing["id"]),
                )
            else:
                depth = 0
                if parent_keyword:
                    parent = conn.execute(
                        "SELECT genealogy_depth FROM trend_genealogy WHERE keyword = ? LIMIT 1",
                        (parent_keyword,),
                    ).fetchone()
                    depth = (parent["genealogy_depth"] + 1) if parent else 1
                conn.execute(
                    """INSERT INTO trend_genealogy
                       (keyword, parent_keyword, predicted_children, genealogy_depth,
                        first_seen_at, last_seen_at, peak_viral_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (keyword, parent_keyword, children_json, depth, now, now, viral_score),
                )
            conn.commit()
        finally:
            conn.close()

    def get_trend_history(self, keyword: str, hours: int = 72) -> list[dict]:
        """[A] 최근 N시간 이내 트렌드 히스토리 (계보 연결용)."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT keyword, parent_keyword, predicted_children,
                          genealogy_depth, total_appearances, peak_viral_score,
                          first_seen_at, last_seen_at
                   FROM trend_genealogy
                   WHERE last_seen_at >= ?
                   ORDER BY last_seen_at DESC""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_predicted_children(self, keyword: str) -> list[str]:
        """[A] 특정 트렌드의 예측된 파생 트렌드 목록."""
        self.init_table()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT predicted_children FROM trend_genealogy WHERE keyword = ? ORDER BY last_seen_at DESC LIMIT 1",
                (keyword,),
            ).fetchone()
            if row and row["predicted_children"]:
                return json.loads(row["predicted_children"])
            return []
        finally:
            conn.close()

    # ── Utility ──────────────────────────────────────────

    def get_summary(self, days: int = 30) -> dict:
        """대시보드/로깅용 성과 요약 (훅/킥 패턴 포함)."""
        stats = self.get_angle_performance(days)
        weights = self.get_optimal_angle_weights(days, _precomputed_stats=stats)
        pattern_weights = self.get_optimal_pattern_weights(days)

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
            "pattern_weights": pattern_weights,
        }
