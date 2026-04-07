"""
Engagement Prediction Model — LightGBM 기반 경량 ML 모델.

학습: 기존 tweet_metrics + QA scores + trend context → engagement_rate 예측
추론: 새 콘텐츠 피처 → 예측 성과 + 신뢰 구간 + 최적 시간대

Dependencies:
    pip install lightgbm scikit-learn joblib
    (fallback: sklearn GradientBoostingRegressor if lightgbm unavailable)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

# HMAC secret for model integrity verification (환경변수로 오버라이드 가능)
import os as _os
_MODEL_HMAC_KEY = (_os.environ.get("PEE_MODEL_HMAC_KEY") or "pee-default-integrity-key-2026").encode()

# LightGBM optional — fallback to sklearn
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False


# ── Prediction Result ──────────────────────────────────────


@dataclass
class PredictionResult:
    """예측 결과."""
    predicted_engagement_rate: float     # 예측 engagement rate (0.0~1.0)
    predicted_impressions: int           # 예측 impression 수
    confidence_interval: tuple[float, float]  # 95% 신뢰 구간
    viral_probability: float             # 바이럴 확률 (상위 10% 성과)
    optimal_hours: list[int]             # 추천 발행 시간 top-3
    risk_level: str                      # "low" | "medium" | "high"
    feature_importance: dict[str, float] # 주요 영향 피처 top-5
    recommendation: str                  # 자연어 추천 메시지


@dataclass
class ModelMetrics:
    """모델 성능 지표."""
    mae: float          # Mean Absolute Error
    r2: float           # R² score
    cv_score: float     # 5-fold CV mean
    sample_count: int   # 학습 샘플 수
    trained_at: str     # ISO timestamp


# ── Engagement Model ───────────────────────────────────────


class EngagementModel:
    """
    콘텐츠 성과 예측 모델.

    학습 파이프라인:
        1. FeatureExtractor.extract_training_set() → X, y
        2. model.train(X, y)
        3. model.save(path)

    추론 파이프라인:
        1. model.load(path) 또는 model.train(X, y)
        2. model.predict(features_array) → PredictionResult
    """

    MODEL_FILE = "engagement_model.bin"
    META_FILE = "engagement_model_meta.json"

    HMAC_FILE = "engagement_model.sig"

    def __init__(self, model_dir: Path | None = None):
        self._model_dir = model_dir or Path(".data/models")
        self._model: Any = None
        self._metrics: ModelMetrics | None = None
        self._n_features: int = 0  # 학습 시 feature 수 기록
        self._hour_engagement_map: dict[int, float] = {}  # 시간대별 평균 ER
        self._viral_threshold: float = 0.05  # 상위 10% engagement rate

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    @property
    def metrics(self) -> ModelMetrics | None:
        return self._metrics

    # ── Training ───────────────────────────────────────────

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> ModelMetrics:
        """
        학습 실행.

        Args:
            X: (N, 21) feature matrix
            y: (N,) engagement_rate targets
            feature_names: 피처 이름 리스트 (importance 리포트용)
        """
        if X.shape[0] < 10:
            raise ValueError(f"학습 데이터 부족: {X.shape[0]}건 (최소 10건 필요)")

        self._n_features = X.shape[1]

        # 바이럴 기준선 산출 (상위 10%)
        self._viral_threshold = max(0.001, float(np.percentile(y, 90)))

        # 시간대별 평균 ER 맵 구성 (hour_of_day = index 14)
        if X.shape[1] > 14:
            for hour in range(24):
                mask = X[:, 14].astype(int) == hour
                if mask.any():
                    self._hour_engagement_map[hour] = float(np.mean(y[mask]))

        # 모델 선택 & 학습
        if HAS_LIGHTGBM:
            log.info("LightGBM 사용")
            self._model = lgb.LGBMRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=5,
                reg_alpha=0.1,
                reg_lambda=0.1,
                random_state=42,
                verbose=-1,
            )
        else:
            log.info("sklearn GradientBoosting fallback")
            self._model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=5,
                random_state=42,
            )

        self._model.fit(X, y)

        # 평가
        y_pred = self._model.predict(X)
        # CV는 30건 이상일 때만 (소규모에서 LOO 방지)
        if X.shape[0] >= 30:
            cv_scores = cross_val_score(self._model, X, y, cv=5, scoring="r2")
        else:
            cv_scores = np.array([0.0])  # 데이터 부족 시 CV 스킵

        from datetime import datetime, UTC
        self._metrics = ModelMetrics(
            mae=float(mean_absolute_error(y, y_pred)),
            r2=float(r2_score(y, y_pred)),
            cv_score=float(np.mean(cv_scores)),
            sample_count=X.shape[0],
            trained_at=datetime.now(UTC).isoformat(),
        )

        log.info(
            "모델 학습 완료: MAE=%.4f, R²=%.4f, CV=%.4f, N=%d",
            self._metrics.mae, self._metrics.r2,
            self._metrics.cv_score, self._metrics.sample_count,
        )

        return self._metrics

    # ── Prediction ─────────────────────────────────────────

    def predict(
        self,
        features: np.ndarray,
        feature_names: list[str] | None = None,
        base_impressions: int = 1000,
    ) -> PredictionResult:
        """
        단일 콘텐츠 성과 예측.

        Args:
            features: (21,) feature vector
            feature_names: importance 리포트용
            base_impressions: 기본 impression 추정 베이스
        """
        if self._model is None:
            raise RuntimeError("모델 미학습 상태. train() 또는 load()를 먼저 실행하세요.")

        if self._n_features and features.shape[0] != self._n_features:
            raise ValueError(
                f"Feature 수 불일치: 모델={self._n_features}, 입력={features.shape[0]}"
            )

        X = features.reshape(1, -1)
        predicted_er = float(self._model.predict(X)[0])
        predicted_er = max(0.0, min(1.0, predicted_er))  # clamp

        # 신뢰 구간 (bootstrap approx — 트리 기반 variance 추정)
        ci_low, ci_high = self._estimate_confidence(X, predicted_er)

        # 바이럴 확률
        viral_prob = self._estimate_viral_probability(predicted_er)

        # 최적 시간대 top-3
        optimal_hours = self._get_optimal_hours()

        # impression 추정 (keyword_prev_impressions가 있으면 활용)
        keyword_imp = features[19] if len(features) > 19 else 0
        est_impressions = int(keyword_imp) if keyword_imp > 0 else base_impressions
        predicted_impressions = max(1, int(est_impressions * (1 + predicted_er * 5)))

        # 리스크 판단
        risk = "low" if predicted_er > 0.03 else ("medium" if predicted_er > 0.01 else "high")

        # Feature importance top-5
        importance = self._get_feature_importance(feature_names or [])

        # 자연어 추천
        recommendation = self._generate_recommendation(
            predicted_er, viral_prob, optimal_hours, risk,
        )

        return PredictionResult(
            predicted_engagement_rate=round(predicted_er, 6),
            predicted_impressions=predicted_impressions,
            confidence_interval=(round(ci_low, 6), round(ci_high, 6)),
            viral_probability=round(viral_prob, 4),
            optimal_hours=optimal_hours[:3],
            risk_level=risk,
            feature_importance=importance,
            recommendation=recommendation,
        )

    # ── Persistence ────────────────────────────────────────

    def save(self, path: Path | None = None) -> Path:
        """모델 + 메타데이터 + HMAC 서명 저장."""
        if self._model is None:
            raise RuntimeError("모델 미학습 상태에서 save() 호출 불가.")

        save_dir = path or self._model_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        model_path = save_dir / self.MODEL_FILE
        meta_path = save_dir / self.META_FILE
        sig_path = save_dir / self.HMAC_FILE

        if HAS_JOBLIB:
            joblib.dump(self._model, model_path)
        else:
            import pickle
            with open(model_path, "wb") as f:
                pickle.dump(self._model, f)

        # HMAC 서명 생성 (모델 파일 무결성 검증)
        model_bytes = model_path.read_bytes()
        sig = hmac.new(_MODEL_HMAC_KEY, model_bytes, hashlib.sha256).hexdigest()
        sig_path.write_text(sig)

        meta = {
            "metrics": {
                "mae": self._metrics.mae if self._metrics else 0,
                "r2": self._metrics.r2 if self._metrics else 0,
                "cv_score": self._metrics.cv_score if self._metrics else 0,
                "sample_count": self._metrics.sample_count if self._metrics else 0,
                "trained_at": self._metrics.trained_at if self._metrics else "",
            },
            "n_features": self._n_features,
            "viral_threshold": self._viral_threshold,
            "hour_engagement_map": self._hour_engagement_map,
            "has_lightgbm": HAS_LIGHTGBM,
        }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

        log.info("모델 저장: %s", save_dir)
        return save_dir

    def load(self, path: Path | None = None) -> bool:
        """저장된 모델 로드 + HMAC 무결성 검증. 성공 시 True."""
        load_dir = path or self._model_dir
        model_path = load_dir / self.MODEL_FILE
        meta_path = load_dir / self.META_FILE
        sig_path = load_dir / self.HMAC_FILE

        if not model_path.exists():
            log.warning("모델 파일 없음: %s", model_path)
            return False

        # HMAC 무결성 검증 (서명 파일 있을 때만 — 레거시 호환)
        if sig_path.exists():
            model_bytes = model_path.read_bytes()
            expected_sig = sig_path.read_text().strip()
            actual_sig = hmac.new(_MODEL_HMAC_KEY, model_bytes, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, actual_sig):
                log.error("모델 HMAC 검증 실패: %s (변조 의심)", model_path)
                return False

        if HAS_JOBLIB:
            self._model = joblib.load(model_path)
        else:
            import pickle
            with open(model_path, "rb") as f:
                self._model = pickle.load(f)  # noqa: S301

        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            m = meta.get("metrics", {})
            self._metrics = ModelMetrics(**m) if m.get("trained_at") else None
            self._n_features = meta.get("n_features", 0)
            self._viral_threshold = max(0.001, meta.get("viral_threshold", 0.05))
            self._hour_engagement_map = {
                int(k): v for k, v in meta.get("hour_engagement_map", {}).items()
            }

        log.info("모델 로드 완료: %s", load_dir)
        return True

    # ── Private helpers ────────────────────────────────────

    def _estimate_confidence(
        self, X: np.ndarray, predicted: float,
    ) -> tuple[float, float]:
        """트리 앙상블 기반 간이 신뢰 구간 (~95%)."""
        if self._metrics and self._metrics.mae > 0:
            # MAE → sigma 변환: sigma ≈ MAE / 0.7979 (정규분포 가정)
            sigma = self._metrics.mae / 0.7979
            margin = sigma * 1.96  # 95% CI
        else:
            margin = max(predicted * 0.3, 0.005)  # 최소 마진 보장
        return (max(0.0, predicted - margin), min(1.0, predicted + margin))

    def _estimate_viral_probability(self, predicted_er: float) -> float:
        """바이럴 확률 추정 (로지스틱 근사)."""
        if self._viral_threshold <= 0:
            return 0.0
        ratio = predicted_er / self._viral_threshold
        # 시그모이드: ratio=1이면 50%, ratio=2이면 ~88%
        import math
        return 1.0 / (1.0 + math.exp(-3 * (ratio - 1)))

    def _get_optimal_hours(self) -> list[int]:
        """시간대별 평균 ER 기준 상위 시간대."""
        if not self._hour_engagement_map:
            return [9, 12, 18]  # 기본값
        sorted_hours = sorted(
            self._hour_engagement_map.items(), key=lambda x: x[1], reverse=True,
        )
        return [h for h, _ in sorted_hours[:5]]

    def _get_feature_importance(self, names: list[str]) -> dict[str, float]:
        """모델 feature importance 추출."""
        if self._model is None:
            return {}

        if hasattr(self._model, "feature_importances_"):
            importances = self._model.feature_importances_
        else:
            return {}

        if not names:
            from .features import ContentFeatures
            names = ContentFeatures.feature_names()

        pairs = sorted(
            zip(names, importances), key=lambda x: x[1], reverse=True,
        )
        return {name: round(float(imp), 4) for name, imp in pairs[:5]}

    def _generate_recommendation(
        self,
        er: float,
        viral_prob: float,
        hours: list[int],
        risk: str,
    ) -> str:
        """자연어 추천 생성."""
        parts = []

        if er >= 0.05:
            parts.append("높은 engagement 예상. 즉시 발행 권장.")
        elif er >= 0.02:
            parts.append("양호한 engagement 예상.")
        else:
            parts.append("engagement 낮을 수 있음. 훅/앵글 보강 고려.")

        if viral_prob > 0.5:
            parts.append(f"바이럴 확률 {viral_prob:.0%} — 타이밍 잡아서 빠르게 발행.")
        elif viral_prob > 0.2:
            parts.append(f"바이럴 가능성 {viral_prob:.0%}.")

        if hours:
            hour_str = ", ".join(f"{h}시" for h in hours[:3])
            parts.append(f"최적 발행 시간: {hour_str} (KST).")

        if risk == "high":
            parts.append("리스크 높음: QA 점수 개선 또는 다른 앵글 시도 권장.")

        return " ".join(parts)
