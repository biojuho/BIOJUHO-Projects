"""Tests for Phase 5: HITL Approval, ML Prediction, Research Integration."""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---- Approval Gate Tests ----


class TestApprovalStatus:
    def test_status_values(self):
        from services.approval_gate import ApprovalStatus

        assert ApprovalStatus.PENDING == "pending"
        assert ApprovalStatus.APPROVED == "approved"
        assert ApprovalStatus.REJECTED == "rejected"
        assert ApprovalStatus.AUTO_APPROVED == "auto_approved"


class TestApprovalRequest:
    def test_creation(self):
        from services.approval_gate import ApprovalRequest

        req = ApprovalRequest(
            post_id="123",
            caption_preview="Test caption",
            topic="AI",
        )
        assert req.post_id == "123"
        assert req.status.value == "pending"


class TestApprovalGate:
    def _make_gate(self, timeout=10):
        from services.approval_gate import ApprovalGate

        return ApprovalGate(
            bot_token="test_token",
            chat_id="test_chat",
            auto_approve_timeout=timeout,
        )

    def test_is_configured(self):
        gate = self._make_gate()
        assert gate.is_configured is True

    def test_not_configured(self):
        from services.approval_gate import ApprovalGate

        gate = ApprovalGate()
        assert gate.is_configured is False

    def test_approve(self):
        from services.approval_gate import ApprovalRequest, ApprovalStatus

        gate = self._make_gate()
        gate._pending["123"] = ApprovalRequest(post_id="123", caption_preview="test", topic="AI")
        assert gate.approve("123") is True
        assert gate.check_approval("123") == ApprovalStatus.APPROVED

    def test_reject(self):
        from services.approval_gate import ApprovalRequest, ApprovalStatus

        gate = self._make_gate()
        gate._pending["123"] = ApprovalRequest(post_id="123", caption_preview="test", topic="AI")
        assert gate.reject("123") is True
        assert gate.check_approval("123") == ApprovalStatus.REJECTED

    def test_auto_approve_timeout(self):
        from services.approval_gate import ApprovalRequest, ApprovalStatus

        gate = self._make_gate(timeout=0)  # Instant timeout
        gate._pending["123"] = ApprovalRequest(
            post_id="123",
            caption_preview="test",
            topic="AI",
            created_at=time.time() - 100,
        )
        assert gate.check_approval("123") == ApprovalStatus.AUTO_APPROVED

    def test_unknown_post_defaults_approved(self):
        from services.approval_gate import ApprovalStatus

        gate = self._make_gate()
        assert gate.check_approval("unknown") == ApprovalStatus.APPROVED

    def test_get_pending(self):
        from services.approval_gate import ApprovalRequest

        gate = self._make_gate(timeout=99999)
        gate._pending["a"] = ApprovalRequest(post_id="a", caption_preview="", topic="")
        gate._pending["b"] = ApprovalRequest(post_id="b", caption_preview="", topic="")
        assert len(gate.get_pending()) == 2

    def test_stats(self):
        from services.approval_gate import ApprovalRequest, ApprovalStatus

        gate = self._make_gate()
        gate._pending["a"] = ApprovalRequest(post_id="a", caption_preview="", topic="")
        gate._pending["b"] = ApprovalRequest(
            post_id="b",
            caption_preview="",
            topic="",
            status=ApprovalStatus.APPROVED,
        )
        stats = gate.get_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 1
        assert stats["approved"] == 1

    @pytest.mark.asyncio
    async def test_send_for_approval(self):
        gate = self._make_gate()
        gate._send_telegram = AsyncMock(return_value=42)
        req = await gate.send_for_approval("p1", "caption", "topic")
        assert req.post_id == "p1"
        assert req.telegram_message_id == 42


# ---- Engagement Predictor Tests ----


class TestPredictionInput:
    def test_from_post(self):
        from services.engagement_predictor import PredictionInput

        inp = PredictionInput.from_post(
            caption="이것은 테스트입니다. 여러분 댓글로 알려주세요?",
            hashtags="#test #ai #tech",
        )
        assert inp.caption_length > 0
        assert inp.hashtag_count == 3
        assert inp.has_cta is True  # "댓글"
        assert inp.has_question is True  # ends with ?

    def test_to_features(self):
        from services.engagement_predictor import PredictionInput

        inp = PredictionInput(
            caption_length=500,
            hashtag_count=10,
            posting_hour=12,
            posting_day=2,
        )
        features = inp.to_features()
        assert len(features) == 7
        assert all(0 <= f <= 1 for f in features)


class TestEngagementPredictor:
    def test_predict_without_training(self):
        from services.engagement_predictor import EngagementPredictor, PredictionInput

        pred = EngagementPredictor()
        inp = PredictionInput(caption_length=500, hashtag_count=10)
        result = pred.predict(inp)
        assert result.predicted_engagement_rate == 3.5  # Default
        assert result.confidence == "low"

    def test_predict_suggestions_short_caption(self):
        from services.engagement_predictor import EngagementPredictor, PredictionInput

        pred = EngagementPredictor()
        inp = PredictionInput(caption_length=50, hashtag_count=2)
        result = pred.predict(inp)
        assert any("짧습니다" in s for s in result.suggestions)
        assert any("해시태그" in s for s in result.suggestions)

    def test_predict_suggestions_no_cta(self):
        from services.engagement_predictor import EngagementPredictor, PredictionInput

        pred = EngagementPredictor()
        inp = PredictionInput(caption_length=500, hashtag_count=10, has_cta=False)
        result = pred.predict(inp)
        assert any("CTA" in s for s in result.suggestions)

    def test_suggest_best_time_no_training(self):
        from services.engagement_predictor import EngagementPredictor

        pred = EngagementPredictor()
        result = pred.suggest_best_time()
        assert result["confidence"] == "low"
        assert result["best_day"] == "수요일"

    def test_get_status(self):
        from services.engagement_predictor import EngagementPredictor

        pred = EngagementPredictor()
        status = pred.get_status()
        assert status["trained"] is False
        assert status["min_samples"] == 10

    def test_train_no_data(self):
        from services.engagement_predictor import EngagementPredictor

        pred = EngagementPredictor(db_path="nonexistent.db")
        assert pred.train() is False


class TestPredictionResult:
    def test_defaults(self):
        from services.engagement_predictor import PredictionResult

        result = PredictionResult()
        assert result.predicted_engagement_rate == 0.0
        assert result.confidence == "low"
        assert result.suggestions == []
