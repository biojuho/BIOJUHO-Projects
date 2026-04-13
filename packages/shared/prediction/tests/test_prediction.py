"""
PEE 단위 테스트 — features, model, engine, api.

실행: pytest packages/shared/prediction/tests/ -v
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np
import pytest

from shared.prediction.features import ContentFeatures, FeatureExtractor, CATEGORY_MAP
from shared.prediction.model import EngagementModel, PredictionResult
from shared.prediction.engine import PredictionEngine, ContentCandidate


# ── Feature Tests ──────────────────────────────────────────


class TestContentFeatures:
    def test_to_array_shape(self):
        f = ContentFeatures(viral_potential=80, qa_total_score=90, char_count=150)
        arr = f.to_array()
        assert arr.shape == (21,)
        assert arr.dtype == np.float32

    def test_feature_names_match_array(self):
        names = ContentFeatures.feature_names()
        arr = ContentFeatures().to_array()
        assert len(names) == len(arr)

    def test_boolean_encoding(self):
        f = ContentFeatures(has_hashtags=True, has_numbers=True, has_question=False)
        arr = f.to_array()
        assert arr[11] == 1.0  # has_hashtags
        assert arr[12] == 1.0  # has_numbers
        assert arr[13] == 0.0  # has_question

    def test_category_map_coverage(self):
        assert "tech" in CATEGORY_MAP
        assert "crypto" in CATEGORY_MAP
        assert "other" in CATEGORY_MAP
        assert len(CATEGORY_MAP) >= 12


class TestFeatureExtractor:
    def test_init_without_dbs(self):
        ext = FeatureExtractor()
        assert ext._gdt_db is None

    def test_extract_for_prediction_defaults(self):
        ext = FeatureExtractor()
        features = ext.extract_for_prediction(
            content="테스트 트윗입니다 #AI",
            trend_keyword="AI",
            viral_potential=85.0,
            category="tech",
        )
        assert features.viral_potential == 85.0
        assert features.has_hashtags is True
        assert features.category_encoded == CATEGORY_MAP["tech"]

    def test_extract_training_set_empty(self):
        ext = FeatureExtractor()
        X, y = ext.extract_training_set()
        assert X.shape[0] == 0
        assert y.shape[0] == 0

    def test_safe_query_missing_table_is_logged_as_info(self, tmp_path, monkeypatch):
        import sqlite3

        db_path = tmp_path / "missing-table.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        ext = FeatureExtractor(gdt_db=db_path)
        events: list[tuple[str, str]] = []

        monkeypatch.setattr("shared.prediction.features.log.info", lambda msg, *args: events.append(("info", msg % args)))
        monkeypatch.setattr("shared.prediction.features.log.warning", lambda msg, *args: events.append(("warning", msg % args)))

        rows = ext._safe_query(db_path, "SELECT * FROM x_tweet_metrics")

        assert rows == []
        assert events[0][0] == "info"

    def test_safe_query_missing_column_is_logged_as_warning(self, tmp_path, monkeypatch):
        import sqlite3

        db_path = tmp_path / "missing-column.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        ext = FeatureExtractor(gdt_db=db_path)
        events: list[tuple[str, str]] = []

        monkeypatch.setattr("shared.prediction.features.log.info", lambda msg, *args: events.append(("info", msg % args)))
        monkeypatch.setattr("shared.prediction.features.log.warning", lambda msg, *args: events.append(("warning", msg % args)))

        rows = ext._safe_query(db_path, "SELECT missing_column FROM sample")

        assert rows == []
        assert events[0][0] == "warning"

    def test_safe_query_optional_schema_column_is_logged_as_info(self, tmp_path, monkeypatch):
        import sqlite3

        db_path = tmp_path / "missing-optional-column.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        ext = FeatureExtractor(gdt_db=db_path)
        events: list[tuple[str, str]] = []

        monkeypatch.setattr("shared.prediction.features.log.info", lambda msg, *args: events.append(("info", msg % args)))
        monkeypatch.setattr("shared.prediction.features.log.warning", lambda msg, *args: events.append(("warning", msg % args)))

        rows = ext._safe_query(db_path, "SELECT run_date FROM sample")

        assert rows == []
        assert events[0][0] == "info"


# ── Model Tests ────────────────────────────────────────────


class TestEngagementModel:
    @pytest.fixture
    def synthetic_data(self):
        rng = np.random.default_rng(42)
        N = 100
        X = rng.random((N, 21)).astype(np.float32)
        # ER ~ viral(col0) * 0.05 + noise
        y = (X[:, 0] * 0.05 + rng.normal(0, 0.005, N)).astype(np.float32)
        y = np.clip(y, 0, 1)
        return X, y

    def test_train_and_predict(self, synthetic_data):
        X, y = synthetic_data
        model = EngagementModel()
        metrics = model.train(X, y)

        assert metrics.mae > 0
        assert metrics.sample_count == 100

        result = model.predict(X[0])
        assert isinstance(result, PredictionResult)
        assert 0 <= result.predicted_engagement_rate <= 1
        assert result.predicted_impressions > 0
        assert result.risk_level in ("low", "medium", "high")
        assert len(result.optimal_hours) > 0
        assert result.recommendation

    def test_train_insufficient_data(self):
        model = EngagementModel()
        X = np.random.rand(5, 21).astype(np.float32)
        y = np.random.rand(5).astype(np.float32)
        with pytest.raises(ValueError, match="학습 데이터 부족"):
            model.train(X, y)

    def test_save_and_load(self, tmp_path, synthetic_data):
        X, y = synthetic_data
        model = EngagementModel(model_dir=tmp_path)
        model.train(X, y)
        model.save()

        model2 = EngagementModel(model_dir=tmp_path)
        assert model2.load() is True
        result = model2.predict(X[0])
        assert result.predicted_engagement_rate > 0

    def test_predict_without_training(self):
        model = EngagementModel()
        with pytest.raises(RuntimeError, match="모델 미학습"):
            model.predict(np.zeros(21, dtype=np.float32))

    def test_feature_importance(self, synthetic_data):
        X, y = synthetic_data
        model = EngagementModel()
        model.train(X, y)
        result = model.predict(X[0], feature_names=ContentFeatures.feature_names())
        assert len(result.feature_importance) > 0
        assert all(isinstance(v, float) for v in result.feature_importance.values())


# ── Engine Tests ───────────────────────────────────────────


class TestPredictionEngine:
    @pytest.fixture
    def engine(self):
        return PredictionEngine()

    def test_rule_based_fallback(self, engine):
        features = ContentFeatures(
            viral_potential=80,
            qa_total_score=85,
            char_count=150,
            has_numbers=True,
            hour_of_day=18,
        )
        result = engine._rule_based_predict(features)
        assert isinstance(result, PredictionResult)
        assert result.predicted_engagement_rate > 0
        assert "규칙 기반" in result.recommendation

    @pytest.mark.asyncio
    async def test_predict_without_db(self, engine):
        """DB 없이도 fallback으로 예측 가능."""
        result = await engine.predict(
            content="AI가 세상을 바꾸고 있다 #AI #트렌드",
            trend_keyword="AI",
            viral_potential=75.0,
            qa_scores={"total": 80, "hook": 16, "tone": 12},
            category="tech",
        )
        assert result.predicted_engagement_rate > 0
        assert result.predicted_impressions > 0

    @pytest.mark.asyncio
    async def test_batch_predict(self, engine):
        candidates = [
            ContentCandidate(
                content="AI 시대의 필수 도구 3가지 #AI",
                trend_keyword="AI",
                viral_potential=80,
                qa_scores={"total": 85},
                category="tech",
            ),
            ContentCandidate(
                content="오늘 날씨 좋네요",
                trend_keyword="날씨",
                viral_potential=20,
                qa_scores={"total": 40},
                category="other",
            ),
        ]
        report = await engine.batch_predict(candidates)
        assert report.total_candidates == 2
        assert report.best_candidate is not None
        assert report.predictions[0].rank == 1
        # AI 콘텐츠가 순위 높아야 함
        assert "AI" in report.predictions[0].candidate.content

    @pytest.mark.asyncio
    async def test_compare_variants(self, engine):
        results = await engine.compare_variants(
            variants=[
                "AI가 바꾸는 미래 3가지 시나리오 #AI",
                "인공지능 기술 발전 현황입니다",
            ],
            trend_keyword="AI",
            viral_potential=70,
            category="tech",
        )
        assert len(results) == 2
        assert results[0][0] == 1  # rank 1


# ── API Schema Tests ───────────────────────────────────────


class TestAPISchemas:
    @pytest.fixture(autouse=True)
    def _skip_no_fastapi(self):
        pytest.importorskip("fastapi")

    def test_predict_request_validation(self):
        from shared.prediction.api import PredictRequest
        req = PredictRequest(
            content="테스트",
            trend_keyword="AI",
            viral_potential=80,
        )
        assert req.content == "테스트"
        assert req.category == "other"

    def test_predict_request_bounds(self):
        from shared.prediction.api import PredictRequest
        with pytest.raises(Exception):
            PredictRequest(content="", trend_keyword="AI")  # min_length=1


# ── Retrain Tests ──────────────────────────────────────────


class TestRetrain:
    def test_needs_retrain_no_model(self, tmp_path):
        from shared.prediction.retrain import _needs_retrain
        import shared.prediction.retrain as retrain_mod

        original = retrain_mod._model_dir
        retrain_mod._model_dir = lambda: tmp_path
        try:
            needs, reason = _needs_retrain()
            assert needs is True
            assert "모델 파일 없음" in reason
        finally:
            retrain_mod._model_dir = original

    def test_needs_retrain_fresh_model(self, tmp_path):
        import json
        from datetime import datetime, UTC
        from shared.prediction.retrain import _needs_retrain
        import shared.prediction.retrain as retrain_mod

        # Write a fresh meta file
        meta = {
            "metrics": {"trained_at": datetime.now(UTC).isoformat()},
        }
        (tmp_path / "engagement_model_meta.json").write_text(json.dumps(meta))

        original = retrain_mod._model_dir
        retrain_mod._model_dir = lambda: tmp_path
        try:
            needs, reason = _needs_retrain()
            assert needs is False
            assert "재학습 불필요" in reason
        finally:
            retrain_mod._model_dir = original

    @pytest.mark.asyncio
    async def test_maybe_retrain_without_db(self):
        """DB 없이 retrain 호출 시 데이터 부족으로 fallback."""
        from shared.prediction.retrain import retrain
        result = await retrain(force=True)
        # 데이터 부족이므로 retrained=False
        assert result["retrained"] is False
