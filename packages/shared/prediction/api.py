"""
Prediction API — FastAPI 라우터.

Dashboard(apps/dashboard/api.py)에 마운트하거나 독립 실행 가능.

Usage:
    # Dashboard 마운트
    from shared.prediction.api import router as prediction_router
    app.include_router(prediction_router, prefix="/api/prediction")

    # 독립 실행
    python -m shared.prediction.api  # port 8090
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(tags=["prediction"])

# ── Lazy engine singleton ──────────────────────────────────

import asyncio as _asyncio
import threading as _threading

_engine = None
_engine_lock = _threading.Lock()


def _get_engine():
    """Thread-safe lazy singleton for PredictionEngine."""
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        from .engine import PredictionEngine

        workspace = Path(__file__).resolve().parents[3]  # packages/shared/prediction → workspace root
        _engine = PredictionEngine(
            gdt_db=Path(os.environ.get(
                "GDT_DB_PATH",
                str(workspace / "automation" / "getdaytrends" / "data" / "getdaytrends.db"),
            )),
            cie_db=Path(os.environ.get(
                "CIE_DB_PATH",
                str(workspace / "automation" / "content-intelligence" / "data" / "cie.db"),
            )),
            dn_db=Path(os.environ.get(
                "DN_DB_PATH",
                str(workspace / "automation" / "DailyNews" / "data" / "pipeline_state.db"),
            )),
            model_dir=Path(os.environ.get(
                "PEE_MODEL_DIR",
                str(workspace / "var" / "models" / "prediction"),
            )),
        )
    return _engine


def invalidate_engine() -> None:
    """Retrain 후 싱글톤을 무효화하여 다음 요청에서 새 모델 로드."""
    global _engine
    with _engine_lock:
        _engine = None


# ── Request / Response Models ──────────────────────────────


class PredictRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="예측 대상 콘텐츠")
    trend_keyword: str = Field(..., min_length=1, description="관련 트렌드 키워드")
    viral_potential: float = Field(50.0, ge=0, le=100, description="트렌드 바이럴 점수")
    qa_scores: dict[str, float] = Field(default_factory=dict, description="QA 점수 맵")
    category: str = Field("other", description="콘텐츠 카테고리")
    publish_hour: int | None = Field(None, ge=0, le=23, description="발행 예정 시간 (KST)")
    content_type: str = Field("tweet", description="콘텐츠 유형")
    language: str = Field("ko", description="언어 코드")


class PredictResponse(BaseModel):
    predicted_engagement_rate: float
    predicted_impressions: int
    confidence_interval: list[float]
    viral_probability: float
    optimal_hours: list[int]
    risk_level: str
    feature_importance: dict[str, float]
    recommendation: str


class BatchPredictRequest(BaseModel):
    candidates: list[PredictRequest] = Field(..., min_length=1, max_length=50)


class RankedItem(BaseModel):
    rank: int
    content: str
    prediction: PredictResponse
    score: float


class BatchPredictResponse(BaseModel):
    predictions: list[RankedItem]
    best_content: str | None
    best_engagement_rate: float | None
    total_candidates: int


class CompareRequest(BaseModel):
    variants: list[str] = Field(..., min_length=2, max_length=20, description="A/B 변형 리스트")
    trend_keyword: str
    viral_potential: float = 50.0
    qa_scores: dict[str, float] = Field(default_factory=dict)
    category: str = "other"


class OptimalTimeRequest(BaseModel):
    content: str
    trend_keyword: str
    viral_potential: float = 50.0
    qa_scores: dict[str, float] = Field(default_factory=dict)
    category: str = "other"


class ModelStatusResponse(BaseModel):
    initialized: bool
    has_ml_model: bool
    metrics: dict[str, Any] | None
    mode: str  # "ml" | "rule_based"


# ── Endpoints ──────────────────────────────────────────────


@router.post("/predict", response_model=PredictResponse)
async def predict_engagement(req: PredictRequest):
    """단일 콘텐츠 성과 예측."""
    engine = _get_engine()
    result = await engine.predict(
        content=req.content,
        trend_keyword=req.trend_keyword,
        viral_potential=req.viral_potential,
        qa_scores=req.qa_scores,
        category=req.category,
        publish_hour=req.publish_hour,
        content_type=req.content_type,
        language=req.language,
    )
    return PredictResponse(
        predicted_engagement_rate=result.predicted_engagement_rate,
        predicted_impressions=result.predicted_impressions,
        confidence_interval=list(result.confidence_interval),
        viral_probability=result.viral_probability,
        optimal_hours=result.optimal_hours,
        risk_level=result.risk_level,
        feature_importance=result.feature_importance,
        recommendation=result.recommendation,
    )


@router.post("/batch", response_model=BatchPredictResponse)
async def batch_predict(req: BatchPredictRequest):
    """배치 콘텐츠 예측 + 순위."""
    from .engine import ContentCandidate

    engine = _get_engine()
    candidates = [
        ContentCandidate(
            content=c.content,
            trend_keyword=c.trend_keyword,
            viral_potential=c.viral_potential,
            qa_scores=c.qa_scores,
            category=c.category,
            content_type=c.content_type,
            language=c.language,
        )
        for c in req.candidates
    ]

    report = await engine.batch_predict(candidates)

    items = []
    for rp in report.predictions:
        items.append(RankedItem(
            rank=rp.rank,
            content=rp.candidate.content,
            prediction=PredictResponse(
                predicted_engagement_rate=rp.prediction.predicted_engagement_rate,
                predicted_impressions=rp.prediction.predicted_impressions,
                confidence_interval=list(rp.prediction.confidence_interval),
                viral_probability=rp.prediction.viral_probability,
                optimal_hours=rp.prediction.optimal_hours,
                risk_level=rp.prediction.risk_level,
                feature_importance=rp.prediction.feature_importance,
                recommendation=rp.prediction.recommendation,
            ),
            score=rp.score,
        ))

    best = report.best_candidate
    return BatchPredictResponse(
        predictions=items,
        best_content=best.candidate.content if best else None,
        best_engagement_rate=best.prediction.predicted_engagement_rate if best else None,
        total_candidates=report.total_candidates,
    )


@router.post("/compare", response_model=BatchPredictResponse)
async def compare_variants(req: CompareRequest):
    """A/B 변형 비교 예측."""
    engine = _get_engine()
    results = await engine.compare_variants(
        variants=req.variants,
        trend_keyword=req.trend_keyword,
        viral_potential=req.viral_potential,
        qa_scores=req.qa_scores,
        category=req.category,
    )

    items = []
    for rank, content, pred in results:
        items.append(RankedItem(
            rank=rank,
            content=content,
            prediction=PredictResponse(
                predicted_engagement_rate=pred.predicted_engagement_rate,
                predicted_impressions=pred.predicted_impressions,
                confidence_interval=list(pred.confidence_interval),
                viral_probability=pred.viral_probability,
                optimal_hours=pred.optimal_hours,
                risk_level=pred.risk_level,
                feature_importance=pred.feature_importance,
                recommendation=pred.recommendation,
            ),
            score=pred.predicted_engagement_rate,
        ))

    best = items[0] if items else None
    return BatchPredictResponse(
        predictions=items,
        best_content=best.content if best else None,
        best_engagement_rate=best.prediction.predicted_engagement_rate if best else None,
        total_candidates=len(items),
    )


@router.post("/optimal-time")
async def find_optimal_time(req: OptimalTimeRequest):
    """24시간 슬롯별 예측 ER 맵."""
    engine = _get_engine()
    hour_map = await engine.find_optimal_publish_time(
        content=req.content,
        trend_keyword=req.trend_keyword,
        viral_potential=req.viral_potential,
        qa_scores=req.qa_scores,
        category=req.category,
    )
    top_3 = list(hour_map.items())[:3]
    return {
        "hour_map": hour_map,
        "top_3": [{"hour": h, "predicted_er": er} for h, er in top_3],
        "recommendation": f"최적 발행 시간: {top_3[0][0]}시 (예상 ER {top_3[0][1]:.4f})" if top_3 else "",
    }


@router.get("/status", response_model=ModelStatusResponse)
async def model_status():
    """모델 상태 확인."""
    engine = _get_engine()
    model = engine._model
    has_ml = model.is_fitted
    metrics = None
    m = model.metrics
    if m:
        metrics = {
            "mae": m.mae,
            "r2": m.r2,
            "cv_score": m.cv_score,
            "sample_count": m.sample_count,
            "trained_at": m.trained_at,
        }
    return ModelStatusResponse(
        initialized=engine._initialized,
        has_ml_model=has_ml,
        metrics=metrics,
        mode="ml" if has_ml else "rule_based",
    )


@router.post("/retrain")
async def retrain_model():
    """모델 재학습 트리거."""
    engine = _get_engine()
    metrics = await engine.initialize(force_retrain=True)
    if metrics:
        return {
            "status": "ok",
            "message": f"재학습 완료: R²={metrics.r2:.4f}, N={metrics.sample_count}",
            "metrics": {
                "mae": metrics.mae,
                "r2": metrics.r2,
                "sample_count": metrics.sample_count,
            },
        }
    return {
        "status": "fallback",
        "message": "학습 데이터 부족. 규칙 기반 모드로 동작 중.",
    }


# ── Standalone runner ──────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    app = FastAPI(title="Predictive Engagement Engine", version="1.0")
    app.include_router(router, prefix="/api/prediction")

    uvicorn.run(app, host="0.0.0.0", port=8090)
