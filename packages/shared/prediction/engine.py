"""
Prediction Engine — 예측 오케스트레이터.

사용 흐름:
    engine = PredictionEngine(gdt_db=..., cie_db=..., dn_db=...)
    await engine.initialize()           # 모델 로드 또는 자동 학습
    result = await engine.predict(...)  # 성과 예측
    report = await engine.batch_predict(...)  # 배치 예측 + 순위 매기기
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from .features import ContentFeatures, FeatureExtractor
from .model import EngagementModel, ModelMetrics, PredictionResult

log = logging.getLogger(__name__)


# ── Batch Prediction Report ────────────────────────────────


@dataclass
class ContentCandidate:
    """예측 대상 콘텐츠."""
    content: str
    trend_keyword: str
    viral_potential: float = 50.0
    qa_scores: dict[str, float] = field(default_factory=dict)
    category: str = "other"
    content_type: str = "tweet"
    language: str = "ko"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankedPrediction:
    """순위가 매겨진 예측 결과."""
    rank: int
    candidate: ContentCandidate
    prediction: PredictionResult
    score: float  # 종합 스코어 (ER × viral_prob × QA)


@dataclass
class BatchReport:
    """배치 예측 리포트."""
    predictions: list[RankedPrediction]
    best_candidate: RankedPrediction | None
    model_metrics: ModelMetrics | None
    generated_at: str
    total_candidates: int


# ── Prediction Engine ──────────────────────────────────────


class PredictionEngine:
    """
    Predictive Engagement Engine 메인 오케스트레이터.

    기능:
        1. 자동 모델 관리 (학습/로드/갱신)
        2. 단일 콘텐츠 예측
        3. 배치 예측 + 자동 순위 매기기
        4. 최적 발행 시간 추천
        5. A/B 변형 비교 예측
    """

    MIN_TRAINING_SAMPLES = 30
    AUTO_RETRAIN_DAYS = 7

    def __init__(
        self,
        gdt_db: Path | None = None,
        cie_db: Path | None = None,
        dn_db: Path | None = None,
        model_dir: Path | None = None,
    ):
        self._extractor = FeatureExtractor(gdt_db, cie_db, dn_db)
        self._model = EngagementModel(model_dir)
        self._initialized = False
        self._init_lock = asyncio.Lock()

    # ── Lifecycle ──────────────────────────────────────────

    async def initialize(self, force_retrain: bool = False) -> ModelMetrics | None:
        """
        엔진 초기화: 기존 모델 로드 또는 자동 학습.
        asyncio.Lock으로 동시 초기화 방지.

        Returns:
            모델 메트릭스 (학습/로드 성공 시)
        """
        async with self._init_lock:
            if self._initialized and not force_retrain:
                return self._model.metrics

            if not force_retrain and self._model.load():
                self._initialized = True
                log.info("기존 모델 로드 완료")
                return self._model.metrics

            # 자동 학습 시도
            log.info("학습 데이터 추출 중...")
            X, y = await asyncio.to_thread(
                self._extractor.extract_training_set,
                min_impressions=10,
                days_back=90,
            )

            if X.shape[0] < self.MIN_TRAINING_SAMPLES:
                log.warning(
                    "학습 데이터 부족: %d건 (최소 %d건). 규칙 기반 fallback 사용.",
                    X.shape[0], self.MIN_TRAINING_SAMPLES,
                )
                self._initialized = True  # fallback 모드로 동작
                return None

            metrics = await asyncio.to_thread(self._model.train, X, y)
            await asyncio.to_thread(self._model.save)
            self._initialized = True

            log.info("모델 학습 완료: R²=%.4f, N=%d", metrics.r2, metrics.sample_count)
            return metrics

    # ── Single Prediction ──────────────────────────────────

    async def predict(
        self,
        content: str,
        trend_keyword: str,
        viral_potential: float = 50.0,
        qa_scores: dict[str, float] | None = None,
        category: str = "other",
        publish_hour: int | None = None,
        content_type: str = "tweet",
        language: str = "ko",
    ) -> PredictionResult:
        """
        단일 콘텐츠 성과 예측.

        Returns:
            PredictionResult (ER, impression, 신뢰구간, 바이럴확률, 최적시간, 추천)
        """
        if not self._initialized:
            await self.initialize()

        features = await asyncio.to_thread(
            self._extractor.extract_for_prediction,
            content=content,
            trend_keyword=trend_keyword,
            viral_potential=viral_potential,
            qa_scores=qa_scores,
            category=category,
            publish_hour=publish_hour,
            content_type=content_type,
            language=language,
        )

        # ML 모델 사용 가능한 경우
        if self._model.is_fitted is not None:
            return await asyncio.to_thread(
                self._model.predict,
                features.to_array(),
            )

        # Fallback: 규칙 기반 예측
        return self._rule_based_predict(features)

    # ── Batch Prediction ───────────────────────────────────

    async def batch_predict(
        self,
        candidates: list[ContentCandidate],
    ) -> BatchReport:
        """
        복수 콘텐츠 배치 예측 + 자동 순위 매기기.

        콘텐츠 생성 후 "어떤 변형이 가장 성과 좋을지" 비교할 때 사용.
        """
        if not self._initialized:
            await self.initialize()

        ranked: list[RankedPrediction] = []

        for candidate in candidates:
            prediction = await self.predict(
                content=candidate.content,
                trend_keyword=candidate.trend_keyword,
                viral_potential=candidate.viral_potential,
                qa_scores=candidate.qa_scores,
                category=candidate.category,
                content_type=candidate.content_type,
                language=candidate.language,
            )

            # 종합 스코어 = ER × (1 + viral_prob) × (QA/100)
            qa_factor = max(0.1, candidate.qa_scores.get("total", 70) / 100)
            score = (
                prediction.predicted_engagement_rate
                * (1 + prediction.viral_probability)
                * qa_factor
            )

            ranked.append(RankedPrediction(
                rank=0,
                candidate=candidate,
                prediction=prediction,
                score=score,
            ))

        # 스코어 내림차순 정렬 + rank 부여
        ranked.sort(key=lambda r: r.score, reverse=True)
        for i, item in enumerate(ranked):
            item.rank = i + 1

        return BatchReport(
            predictions=ranked,
            best_candidate=ranked[0] if ranked else None,
            model_metrics=self._model.metrics,
            generated_at=datetime.now(UTC).isoformat(),
            total_candidates=len(candidates),
        )

    # ── Optimal Timing ─────────────────────────────────────

    async def find_optimal_publish_time(
        self,
        content: str,
        trend_keyword: str,
        viral_potential: float = 50.0,
        qa_scores: dict[str, float] | None = None,
        category: str = "other",
    ) -> dict[int, float]:
        """
        24시간 슬롯별 예측 ER 맵 반환.

        Returns:
            {hour: predicted_engagement_rate} (0~23시)
        """
        results: dict[int, float] = {}

        for hour in range(24):
            pred = await self.predict(
                content=content,
                trend_keyword=trend_keyword,
                viral_potential=viral_potential,
                qa_scores=qa_scores,
                category=category,
                publish_hour=hour,
            )
            results[hour] = pred.predicted_engagement_rate

        return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))

    # ── A/B Comparison ─────────────────────────────────────

    async def compare_variants(
        self,
        variants: list[str],
        trend_keyword: str,
        viral_potential: float = 50.0,
        qa_scores: dict[str, float] | None = None,
        category: str = "other",
    ) -> list[tuple[int, str, PredictionResult]]:
        """
        A/B 변형 비교. 각 변형의 예측 성과를 내림차순으로 반환.

        Returns:
            [(rank, content, prediction), ...]
        """
        candidates = [
            ContentCandidate(
                content=v,
                trend_keyword=trend_keyword,
                viral_potential=viral_potential,
                qa_scores=qa_scores or {},
                category=category,
            )
            for v in variants
        ]

        report = await self.batch_predict(candidates)
        return [
            (rp.rank, rp.candidate.content, rp.prediction)
            for rp in report.predictions
        ]

    # ── Fallback ───────────────────────────────────────────

    def _rule_based_predict(self, features: ContentFeatures) -> PredictionResult:
        """
        ML 모델 없을 때 규칙 기반 fallback.

        경험적 가중치:
            viral_potential 40% + QA 30% + 타이밍 20% + 구조 10%
        """
        # 바이럴 점수 기여
        viral_score = features.viral_potential / 100 * 0.4

        # QA 점수 기여
        qa_score = features.qa_total_score / 100 * 0.3

        # 타이밍 기여 (골든타임: 9, 12, 18, 21시)
        golden_hours = {9: 1.0, 12: 0.9, 18: 1.0, 21: 0.8}
        time_score = golden_hours.get(features.hour_of_day, 0.5) * 0.2

        # 구조 기여
        struct_score = 0.0
        if features.has_numbers:
            struct_score += 0.3
        if features.has_question:
            struct_score += 0.2
        if 100 <= features.char_count <= 200:
            struct_score += 0.3
        if features.has_hashtags:
            struct_score += 0.2
        struct_score *= 0.1

        estimated_er = viral_score + qa_score + time_score + struct_score
        estimated_er = max(0.001, min(0.15, estimated_er))

        return PredictionResult(
            predicted_engagement_rate=round(estimated_er, 6),
            predicted_impressions=int(1000 * (1 + estimated_er * 5)),
            confidence_interval=(
                round(max(0, estimated_er * 0.5), 6),
                round(min(1, estimated_er * 1.5), 6),
            ),
            viral_probability=min(1.0, (features.viral_potential / 100) * estimated_er * 10),
            optimal_hours=[9, 18, 12],
            risk_level="medium",
            feature_importance={"viral_potential": 0.4, "qa_total_score": 0.3},
            recommendation="규칙 기반 예측 (데이터 축적 후 ML 모델 전환 예정).",
        )
