"""ML-based engagement prediction using scikit-learn.

Predicts engagement rate for posts based on:
- Caption length, hashtag count, posting hour/day
- Post type, content angle
- Historical performance data

Uses local LinearRegression — no API cost.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PredictionInput:
    """Features for engagement prediction."""

    caption_length: int = 0
    hashtag_count: int = 0
    posting_hour: int = 12
    posting_day: int = 0  # 0=Mon, 6=Sun
    post_type: str = "IMAGE"  # IMAGE, REEL, CAROUSEL
    has_cta: bool = False
    has_question: bool = False

    @classmethod
    def from_post(cls, caption: str, hashtags: str, scheduled_at: datetime | None = None) -> PredictionInput:
        """Create input from post data."""
        dt = scheduled_at or datetime.now()
        return cls(
            caption_length=len(caption),
            hashtag_count=len([h for h in hashtags.split() if h.startswith("#")]),
            posting_hour=dt.hour,
            posting_day=dt.weekday(),
            has_cta=any(w in caption for w in ["댓글", "저장", "공유", "팔로우", "소통"]),
            has_question=caption.strip().endswith("?") or "?" in caption[:100],
        )

    def to_features(self) -> list[float]:
        """Convert to feature vector for ML model."""
        type_map = {"IMAGE": 0, "REEL": 1, "CAROUSEL": 2}
        return [
            self.caption_length / 2200,  # Normalize
            self.hashtag_count / 30,
            self.posting_hour / 24,
            self.posting_day / 7,
            type_map.get(self.post_type, 0) / 2,
            float(self.has_cta),
            float(self.has_question),
        ]


@dataclass
class PredictionResult:
    """Engagement prediction result."""

    predicted_engagement_rate: float = 0.0
    confidence: str = "low"  # low, medium, high
    best_hour: int = 12
    best_day: str = "수요일"
    suggestions: list[str] = field(default_factory=list)


class EngagementPredictor:
    """Predict and optimize post engagement using ML."""

    MIN_TRAINING_SAMPLES = 10
    DAY_NAMES = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

    # Optimal posting insights (based on industry data, before model trains)
    DEFAULT_BEST_HOURS = [7, 12, 17, 20]
    DEFAULT_BEST_DAYS = [1, 2, 3]  # Tue, Wed, Thu

    def __init__(self, db_path: str = ""):
        self.db_path = db_path
        self._model = None
        self._trained = False
        self._training_size = 0

    def _get_training_data(self) -> tuple[list[list[float]], list[float]]:
        """Load historical post data from analytics DB."""
        if not self.db_path or not Path(self.db_path).exists():
            return [], []

        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute("""
                SELECT caption, hashtags, scheduled_at, post_type,
                       likes, comments, saves, reach
                FROM posts
                WHERE status = 'published'
                    AND reach > 0
                ORDER BY created_at DESC
                LIMIT 500
            """).fetchall()
            conn.close()

            X, y = [], []
            for row in rows:
                caption, hashtags, sched, ptype, likes, comments, saves, reach = row
                dt = datetime.fromisoformat(sched) if sched else datetime.now()
                inp = PredictionInput.from_post(
                    caption or "", hashtags or "", dt
                )
                inp.post_type = ptype or "IMAGE"
                X.append(inp.to_features())
                engagement = (likes + comments * 2 + saves * 3) / max(reach, 1) * 100
                y.append(engagement)
            return X, y
        except Exception as e:
            logger.warning("Training data load failed: %s", e)
            return [], []

    def train(self) -> bool:
        """Train the engagement prediction model."""
        X, y = self._get_training_data()
        if len(X) < self.MIN_TRAINING_SAMPLES:
            logger.info(
                "Not enough data to train (%d/%d samples)",
                len(X), self.MIN_TRAINING_SAMPLES,
            )
            return False

        try:
            from sklearn.linear_model import LinearRegression
            self._model = LinearRegression()
            self._model.fit(X, y)
            self._trained = True
            self._training_size = len(X)
            logger.info("Model trained on %d samples", len(X))
            return True
        except ImportError:
            logger.warning("scikit-learn not installed — prediction disabled")
            return False
        except Exception as e:
            logger.error("Training failed: %s", e)
            return False

    def predict(self, inp: PredictionInput) -> PredictionResult:
        """Predict engagement rate for a post."""
        suggestions = []

        # Feature-based heuristic suggestions (always available)
        if inp.caption_length < 100:
            suggestions.append("캡션이 짧습니다 — 150~500자가 최적")
        elif inp.caption_length > 1500:
            suggestions.append("캡션이 깁니다 — 가독성을 위해 1000자 이하 권장")

        if inp.hashtag_count < 5:
            suggestions.append("해시태그 5~15개 사용 권장")
        elif inp.hashtag_count > 25:
            suggestions.append("해시태그 과다 — 15개 이하로 줄이세요")

        if not inp.has_cta:
            suggestions.append("CTA(행동유도) 추가 권장: '댓글로 알려주세요', '저장해두세요'")

        if not inp.has_question:
            suggestions.append("질문으로 참여 유도 고려: '여러분은 어떻게 생각하세요?'")

        if inp.posting_hour not in self.DEFAULT_BEST_HOURS:
            suggestions.append(
                f"최적 게시 시간: {', '.join(f'{h}시' for h in self.DEFAULT_BEST_HOURS)}"
            )

        # ML prediction (if model trained)
        predicted_rate = 3.5  # Default average
        confidence = "low"

        if self._trained and self._model is not None:
            try:
                features = [inp.to_features()]
                predicted_rate = max(0, self._model.predict(features)[0])
                confidence = "high" if self._training_size >= 50 else "medium"
            except Exception as e:
                logger.warning("Prediction failed: %s", e)

        return PredictionResult(
            predicted_engagement_rate=round(predicted_rate, 2),
            confidence=confidence,
            best_hour=self.DEFAULT_BEST_HOURS[0],
            best_day=self.DAY_NAMES[self.DEFAULT_BEST_DAYS[0]],
            suggestions=suggestions,
        )

    def suggest_best_time(self) -> dict:
        """Suggest best posting times based on data or defaults."""
        if self._trained:
            # Test all hour/day combinations
            best_score = 0
            best_hour, best_day = 12, 2
            for hour in range(6, 23):
                for day in range(7):
                    inp = PredictionInput(
                        caption_length=500,
                        hashtag_count=10,
                        posting_hour=hour,
                        posting_day=day,
                        has_cta=True,
                        has_question=True,
                    )
                    result = self.predict(inp)
                    if result.predicted_engagement_rate > best_score:
                        best_score = result.predicted_engagement_rate
                        best_hour = hour
                        best_day = day

            return {
                "best_hour": best_hour,
                "best_day": self.DAY_NAMES[best_day],
                "predicted_engagement": best_score,
                "confidence": "high" if self._training_size >= 50 else "medium",
                "based_on": f"{self._training_size} posts",
            }
        else:
            return {
                "best_hour": 12,
                "best_day": "수요일",
                "predicted_engagement": None,
                "confidence": "low",
                "based_on": "industry defaults",
            }

    def get_status(self) -> dict:
        """Get predictor status."""
        return {
            "trained": self._trained,
            "training_samples": self._training_size,
            "min_samples": self.MIN_TRAINING_SAMPLES,
            "model_type": "LinearRegression" if self._trained else None,
        }
