"""
Feature Extractor — 기존 DB에서 ML 피처 추출.

3개 데이터 소스 통합:
  - GDT: trends, tweets, x_tweet_metrics, posting_time_stats
  - CIE: content_actual_performance, generated_contents (QA scores)
  - DailyNews: x_tweet_metrics, content_reports
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

import logging

import numpy as np

log = logging.getLogger(__name__)

_OPTIONAL_SCHEMA_COLUMNS = {
    "run_date",
    "cross_source_confidence",
}


# ── Feature Schema ──────────────────────────────────────────


@dataclass
class ContentFeatures:
    """단일 콘텐츠의 ML 입력 피처 벡터."""

    # 트렌드 컨텍스트 (from GDT/CIE scoring)
    viral_potential: float = 0.0          # 0-100, 트렌드 바이럴 점수
    trend_velocity: float = 0.0           # 트렌드 가속도 (시간당 검색량 변화율)
    cross_source_confidence: float = 0.0  # 0-100, 멀티소스 검증 점수
    category_encoded: int = 0             # 카테고리 원핫 인코딩 인덱스
    source_count: int = 1                 # 트렌드 감지 소스 수

    # 콘텐츠 품질 (from QA pipeline)
    qa_total_score: float = 0.0           # 0-100, QA 종합 점수
    hook_score: float = 0.0              # 0-20, 첫줄 임팩트
    tone_score: float = 0.0             # 0-15, AI톤 탈피도
    fact_score: float = 0.0             # 0-15, 팩트 정확도
    kick_score: float = 0.0             # 0-15, 마무리 펀치

    # 콘텐츠 구조
    char_count: int = 0                  # 글자 수
    has_hashtags: bool = False           # 해시태그 포함 여부
    has_numbers: bool = False            # 숫자/통계 포함 여부
    has_question: bool = False           # 질문형 여부
    content_type: str = "tweet"          # tweet | long_form | thread | blog
    language: str = "ko"                 # ko | en | ja

    # 타이밍
    hour_of_day: int = 12               # 0-23, 발행 예정 시간
    day_of_week: int = 0                # 0-6 (Mon-Sun)
    is_weekend: bool = False
    hours_since_trend_peak: float = 0.0  # 트렌드 피크 이후 경과 시간

    # 과거 퍼포먼스 (같은 카테고리/키워드)
    category_avg_engagement: float = 0.0  # 해당 카테고리 평균 engagement rate
    keyword_prev_impressions: float = 0.0 # 동일 키워드 이전 impression
    author_avg_engagement: float = 0.0    # 발행자 평균 engagement rate

    def to_array(self) -> np.ndarray:
        """sklearn/LightGBM 입력용 1D numpy 배열."""
        return np.array([
            self.viral_potential,
            self.trend_velocity,
            self.cross_source_confidence,
            self.category_encoded,
            self.source_count,
            self.qa_total_score,
            self.hook_score,
            self.tone_score,
            self.fact_score,
            self.kick_score,
            self.char_count,
            int(self.has_hashtags),
            int(self.has_numbers),
            int(self.has_question),
            self.hour_of_day,
            self.day_of_week,
            int(self.is_weekend),
            self.hours_since_trend_peak,
            self.category_avg_engagement,
            self.keyword_prev_impressions,
            self.author_avg_engagement,
        ], dtype=np.float32)

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "viral_potential", "trend_velocity", "cross_source_confidence",
            "category_encoded", "source_count",
            "qa_total_score", "hook_score", "tone_score", "fact_score", "kick_score",
            "char_count", "has_hashtags", "has_numbers", "has_question",
            "hour_of_day", "day_of_week", "is_weekend",
            "hours_since_trend_peak",
            "category_avg_engagement", "keyword_prev_impressions",
            "author_avg_engagement",
        ]


@dataclass
class PerformanceLabel:
    """학습용 레이블 (실측 성과)."""
    impressions: int = 0
    engagements: int = 0
    engagement_rate: float = 0.0
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    is_viral: bool = False  # engagement_rate > threshold


# ── Category Encoding ──────────────────────────────────────

CATEGORY_MAP: dict[str, int] = {
    "politics": 0, "economy": 1, "tech": 2, "entertainment": 3,
    "sports": 4, "society": 5, "world": 6, "science": 7,
    "crypto": 8, "ai": 9, "culture": 10, "health": 11,
    "other": 12,
}


# ── Feature Extractor ─────────────────────────────────────


class FeatureExtractor:
    """3개 DB에서 학습/추론용 피처를 추출한다."""

    def __init__(
        self,
        gdt_db: Path | None = None,
        cie_db: Path | None = None,
        dn_db: Path | None = None,
    ):
        self._gdt_db = gdt_db
        self._cie_db = cie_db
        self._dn_db = dn_db

    # ── 학습 데이터 추출 ──

    def extract_training_set(
        self,
        min_impressions: int = 10,
        days_back: int = 90,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        기존 DB에서 (features, labels) 학습셋 추출.

        Returns:
            X: (N, 21) feature matrix
            y: (N,) engagement_rate array
        """
        rows = self._load_historical_performance(min_impressions, days_back)
        if not rows:
            return np.empty((0, 21), dtype=np.float32), np.empty((0,), dtype=np.float32)

        X_list, y_list = [], []
        for row in rows:
            features = self._row_to_features(row)
            X_list.append(features.to_array())
            y_list.append(float(row.get("engagement_rate") or 0.0))

        return np.vstack(X_list), np.array(y_list, dtype=np.float32)

    # ── 추론용 피처 구성 ──

    def extract_for_prediction(
        self,
        content: str,
        trend_keyword: str,
        viral_potential: float = 50.0,
        qa_scores: dict[str, float] | None = None,
        category: str = "other",
        publish_hour: int | None = None,
        content_type: str = "tweet",
        language: str = "ko",
    ) -> ContentFeatures:
        """
        새 콘텐츠에 대한 예측용 피처를 구성한다.
        """
        now = datetime.now(UTC)
        qa = qa_scores or {}

        features = ContentFeatures(
            viral_potential=viral_potential,
            trend_velocity=self._get_trend_velocity(trend_keyword),
            cross_source_confidence=self._get_cross_source_confidence(trend_keyword),
            category_encoded=CATEGORY_MAP.get(category.lower(), 12),
            source_count=self._get_source_count(trend_keyword),
            qa_total_score=qa.get("total", 0.0),
            hook_score=qa.get("hook", 0.0),
            tone_score=qa.get("tone", 0.0),
            fact_score=qa.get("fact", 0.0),
            kick_score=qa.get("kick", 0.0),
            char_count=len(content),
            has_hashtags="#" in content,
            has_numbers=any(c.isdigit() for c in content),
            has_question="?" in content,
            content_type=content_type,
            language=language,
            hour_of_day=publish_hour if publish_hour is not None else now.hour,
            day_of_week=now.weekday(),
            is_weekend=now.weekday() >= 5,
            hours_since_trend_peak=self._hours_since_peak(trend_keyword),
            category_avg_engagement=self._get_category_avg_engagement(category),
            keyword_prev_impressions=self._get_keyword_prev_impressions(trend_keyword),
            author_avg_engagement=self._get_author_avg_engagement(),
        )
        return features

    # ── Private: DB 쿼리 헬퍼 ──────────────────────────────

    def _safe_query(self, db_path: Path | None, query: str, params: tuple = ()) -> list[dict]:
        if not db_path or not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        except sqlite3.OperationalError as e:
            message = str(e).lower()
            if "no such table" in message:
                log.info("PEE DB query skipped (%s): %s", db_path.name, e)
            elif "no such column" in message:
                missing_column = message.split(":", 1)[-1].strip().split(".")[-1]
                if missing_column in _OPTIONAL_SCHEMA_COLUMNS:
                    log.info("PEE DB query skipped (%s): %s", db_path.name, e)
                else:
                    log.warning("PEE DB query failed (%s): %s", db_path.name, e)
            else:
                log.warning("PEE DB query failed (%s): %s", db_path.name, e)
            return []
        finally:
            conn.close()

    def _load_historical_performance(self, min_imp: int, days: int) -> list[dict]:
        """GDT의 tweet metrics + trend context를 INNER JOIN으로 추출.

        DailyNews는 trend context(viral_potential, category, content)가 없어
        training feature 분포가 달라지므로 제외 (inference와 일관성 유지).
        """
        gdt_rows = self._safe_query(self._gdt_db, """
            SELECT
                t.viral_potential, t.category,
                tw.content, tw.char_count, tw.tweet_type,
                m.impressions, m.engagement_count, m.likes, m.retweets, m.replies,
                CASE WHEN m.impressions > 0
                     THEN CAST(m.engagement_count AS REAL) / m.impressions
                     ELSE 0.0 END AS engagement_rate,
                tw.created_at
            FROM tweets tw
            INNER JOIN trends t ON tw.keyword = t.keyword AND tw.run_date = t.run_date
            INNER JOIN x_tweet_metrics m ON tw.tweet_id = m.tweet_id
            WHERE m.impressions >= ?
              AND tw.created_at >= datetime('now', ?)
        """, (min_imp, f"-{days} days"))

        return gdt_rows

    def _row_to_features(self, row: dict) -> ContentFeatures:
        """DB row → ContentFeatures 변환. None-safe."""
        content = row.get("content") or ""
        category = row.get("category") or "other"

        return ContentFeatures(
            viral_potential=float(row.get("viral_potential") or 50.0),
            category_encoded=CATEGORY_MAP.get(str(category).lower(), 12),
            qa_total_score=float(row.get("qa_score") or 0.0),
            char_count=int(row.get("char_count") or len(content) or 0),
            has_hashtags="#" in content,
            has_numbers=any(c.isdigit() for c in content),
            has_question="?" in content,
            hour_of_day=self._extract_hour(row.get("created_at")),
            day_of_week=self._extract_dow(row.get("created_at")),
            category_avg_engagement=self._get_category_avg_engagement(category),
        )

    def _get_trend_velocity(self, keyword: str) -> float:
        """GDT DB에서 트렌드 가속도 조회."""
        rows = self._safe_query(self._gdt_db, """
            SELECT viral_potential FROM trends
            WHERE keyword = ? ORDER BY run_date DESC LIMIT 2
        """, (keyword,))
        if len(rows) >= 2:
            return rows[0].get("viral_potential", 0) - rows[1].get("viral_potential", 0)
        return 0.0

    def _get_cross_source_confidence(self, keyword: str) -> float:
        rows = self._safe_query(self._gdt_db, """
            SELECT cross_source_confidence FROM validated_trends
            WHERE keyword = ? ORDER BY validated_at DESC LIMIT 1
        """, (keyword,))
        return rows[0].get("cross_source_confidence", 0.0) if rows else 0.0

    def _get_source_count(self, keyword: str) -> int:
        rows = self._safe_query(self._gdt_db, """
            SELECT COUNT(DISTINCT source) as cnt FROM raw_trends
            WHERE keyword = ? AND fetched_at >= datetime('now', '-24 hours')
        """, (keyword,))
        return rows[0].get("cnt", 1) if rows else 1

    def _hours_since_peak(self, keyword: str) -> float:
        rows = self._safe_query(self._gdt_db, """
            SELECT MAX(viral_potential) as peak_score, run_date
            FROM trends WHERE keyword = ?
            GROUP BY run_date ORDER BY peak_score DESC LIMIT 1
        """, (keyword,))
        if rows and rows[0].get("run_date"):
            try:
                peak_dt = datetime.fromisoformat(rows[0]["run_date"])
                if peak_dt.tzinfo is None:
                    peak_dt = peak_dt.replace(tzinfo=UTC)
                delta = datetime.now(UTC) - peak_dt
                return delta.total_seconds() / 3600
            except (ValueError, TypeError):
                pass
        return 0.0

    def _get_category_avg_engagement(self, category: str) -> float:
        rows = self._safe_query(self._gdt_db, """
            SELECT AVG(CAST(m.engagement_count AS REAL) / NULLIF(m.impressions, 0)) as avg_er
            FROM tweets tw
            JOIN trends t ON tw.keyword = t.keyword
            JOIN x_tweet_metrics m ON tw.tweet_id = m.tweet_id
            WHERE t.category = ? AND m.impressions > 0
        """, (category,))
        return float(rows[0].get("avg_er") or 0.0) if rows else 0.0

    def _get_keyword_prev_impressions(self, keyword: str) -> float:
        rows = self._safe_query(self._gdt_db, """
            SELECT AVG(m.impressions) as avg_imp
            FROM tweets tw
            JOIN x_tweet_metrics m ON tw.tweet_id = m.tweet_id
            WHERE tw.keyword = ?
        """, (keyword,))
        return float(rows[0].get("avg_imp") or 0.0) if rows else 0.0

    def _get_author_avg_engagement(self) -> float:
        rows = self._safe_query(self._gdt_db, """
            SELECT AVG(CAST(engagement_count AS REAL) / NULLIF(impressions, 0)) as avg_er
            FROM x_tweet_metrics WHERE impressions > 0
        """)
        return float(rows[0].get("avg_er") or 0.0) if rows else 0.0

    @staticmethod
    def _extract_hour(dt_str: str | None) -> int:
        if not dt_str:
            return 12
        try:
            return datetime.fromisoformat(str(dt_str)).hour
        except (ValueError, TypeError):
            return 12

    @staticmethod
    def _extract_dow(dt_str: str | None) -> int:
        if not dt_str:
            return 0
        try:
            return datetime.fromisoformat(str(dt_str)).weekday()
        except (ValueError, TypeError):
            return 0
