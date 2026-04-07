"""
Predictive Engagement Engine (PEE)
===================================
콘텐츠 발행 전 예상 성과를 예측하는 ML 엔진.

Architecture:
    features.py  → 기존 DB에서 feature 추출
    model.py     → LightGBM 기반 예측 모델 학습/추론
    engine.py    → 예측 오케스트레이터
    api.py       → FastAPI 라우터 (Dashboard 마운트용)

Usage:
    from shared.prediction import PredictionEngine
    engine = PredictionEngine()
    result = await engine.predict(content, trend_context)
"""

from .engine import PredictionEngine
from .features import FeatureExtractor
from .model import EngagementModel

__all__ = ["PredictionEngine", "FeatureExtractor", "EngagementModel"]
