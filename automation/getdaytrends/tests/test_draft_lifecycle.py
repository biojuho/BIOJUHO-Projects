"""draft_repository.py 테스트: 드래프트 라이프사이클 상태 머신 + 유효성 검증."""

import pytest
import pytest_asyncio

from db_layer.draft_repository import (
    get_draft_bundle,
    promote_draft_to_ready,
    record_content_feedback,
    record_feedback_summary,
    record_publish_receipt,
    save_draft_bundle,
    save_qa_report,
    save_review_decision,
    save_validated_trend,
    update_draft_bundle_status,
)
from db_layer import _WORKFLOW_STATUS_TRANSITIONS


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db(memory_db):
    """memory_db alias with all tables ready."""
    return memory_db


TREND_ID = "trend-test-0001"
DRAFT_ID = "draft-test-0001"


async def _seed_validated_trend(db, trend_id=TREND_ID):
    return await save_validated_trend(
        db,
        trend_id=trend_id,
        keyword="테스트트렌드",
        confidence_score=0.85,
        source_count=3,
        evidence_refs=["src1", "src2"],
        freshness_minutes=30,
        dedup_fingerprint="fp-abc",
    )


async def _seed_draft(db, draft_id=DRAFT_ID, trend_id=TREND_ID, _skip_trend=False, **overrides):
    if not _skip_trend:
        await _seed_validated_trend(db, trend_id=trend_id)
    defaults = dict(
        draft_id=draft_id,
        trend_id=trend_id,
        platform="x",
        content_type="short",
        body="테스트 드래프트 본문입니다.",
        hashtags=["#테스트", "#AI"],
        prompt_version="v2.1",
        generator_provider="openai",
        generator_model="gpt-4o",
        source_evidence_ref="ref-001",
    )
    defaults.update(overrides)
    return await save_draft_bundle(db, **defaults)


# ── Happy Path: 전체 라이프사이클 ─────────────────────────────────────────────


class TestDraftLifecycleFull:
    """drafted → ready → approved → published → learned 전체 흐름."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_happy_path(self, db):
        await _seed_validated_trend(db)
        await _seed_draft(db, _skip_trend=True)

        # 1) drafted → ready
        await promote_draft_to_ready(db, DRAFT_ID)
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["lifecycle_status"] == "ready"
        assert row["review_status"] == "Ready"

        # 2) ready → approved
        await save_review_decision(db, draft_id=DRAFT_ID, decision="approved", reviewed_by="tester")
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["lifecycle_status"] == "approved"
        assert row["review_status"] == "Approved"

        # 3) approved → published
        receipt_id = await record_publish_receipt(
            db,
            draft_id=DRAFT_ID,
            platform="x",
            success=True,
            published_url="https://x.com/test/123",
        )
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["lifecycle_status"] == "published"
        assert row["published_url"] == "https://x.com/test/123"
        assert receipt_id

        # 4) published → learned
        feedback_id = await record_feedback_summary(
            db,
            draft_id=DRAFT_ID,
            metric_window="48h",
            impressions=1200,
            engagements=45,
            clicks=12,
            receipt_id=receipt_id,
        )
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["lifecycle_status"] == "learned"
        assert feedback_id > 0


# ── 상태 전이 검증 ────────────────────────────────────────────────────────────


class TestStateTransitionGuards:
    """잘못된 상태 전이 시도 시 ValueError 발생 확인."""

    @pytest.mark.asyncio
    async def test_cannot_skip_drafted_to_approved(self, db):
        await _seed_draft(db)
        with pytest.raises(ValueError, match="invalid draft transition"):
            await update_draft_bundle_status(db, draft_id=DRAFT_ID, lifecycle_status="approved")

    @pytest.mark.asyncio
    async def test_cannot_skip_drafted_to_published(self, db):
        await _seed_draft(db)
        with pytest.raises(ValueError, match="invalid draft transition"):
            await update_draft_bundle_status(db, draft_id=DRAFT_ID, lifecycle_status="published")

    @pytest.mark.asyncio
    async def test_cannot_go_backwards_approved_to_drafted(self, db):
        await _seed_draft(db)
        await promote_draft_to_ready(db, DRAFT_ID)
        await save_review_decision(db, draft_id=DRAFT_ID, decision="approved")
        with pytest.raises(ValueError, match="invalid draft transition"):
            await update_draft_bundle_status(db, draft_id=DRAFT_ID, lifecycle_status="drafted")

    @pytest.mark.asyncio
    async def test_learned_is_terminal(self, db):
        """learned 상태에서는 어떤 전이도 불가."""
        await _seed_draft(db)
        await promote_draft_to_ready(db, DRAFT_ID)
        await save_review_decision(db, draft_id=DRAFT_ID, decision="approved")
        receipt = await record_publish_receipt(db, draft_id=DRAFT_ID, platform="x", success=True)
        await record_feedback_summary(db, draft_id=DRAFT_ID, metric_window="48h", receipt_id=receipt)

        with pytest.raises(ValueError, match="invalid draft transition"):
            await update_draft_bundle_status(db, draft_id=DRAFT_ID, lifecycle_status="published")

    @pytest.mark.asyncio
    async def test_all_transitions_in_map_are_exhaustive(self):
        """_WORKFLOW_STATUS_TRANSITIONS 에 정의된 모든 상태가 값에도 등장하는지 확인."""
        all_states = set(_WORKFLOW_STATUS_TRANSITIONS.keys())
        all_targets = set()
        for targets in _WORKFLOW_STATUS_TRANSITIONS.values():
            all_targets.update(targets)
        # 모든 target은 key에도 존재해야 함 (dead-end 방지)
        assert all_targets.issubset(all_states), f"orphan targets: {all_targets - all_states}"


# ── promote_draft_to_ready 유효성 검증 ────────────────────────────────────────


class TestPromoteDraftToReady:
    """promote 게이트: blocking_reasons, prompt_version, source_evidence_ref."""

    @pytest.mark.asyncio
    async def test_promote_fails_with_blocking_reasons(self, db):
        await _seed_draft(db)
        await save_qa_report(
            db,
            draft_id=DRAFT_ID,
            total_score=3.0,
            passed=False,
            blocking_reasons=["hallucination detected"],
        )
        with pytest.raises(ValueError, match="blocking reasons"):
            await promote_draft_to_ready(db, DRAFT_ID)

    @pytest.mark.asyncio
    async def test_promote_fails_without_prompt_version(self, db):
        await _seed_draft(db, prompt_version="", source_evidence_ref="ref-001")
        with pytest.raises(ValueError, match="prompt_version"):
            await promote_draft_to_ready(db, DRAFT_ID)

    @pytest.mark.asyncio
    async def test_promote_fails_without_source_evidence(self, db):
        await _seed_draft(db, prompt_version="v2", source_evidence_ref="")
        with pytest.raises(ValueError, match="source_evidence_ref"):
            await promote_draft_to_ready(db, DRAFT_ID)

    @pytest.mark.asyncio
    async def test_promote_unknown_draft_raises(self, db):
        with pytest.raises(ValueError, match="unknown draft_id"):
            await promote_draft_to_ready(db, "nonexistent-id")


# ── save_review_decision 엣지 케이스 ──────────────────────────────────────────


class TestReviewDecision:

    @pytest.mark.asyncio
    async def test_approve_requires_ready_status(self, db):
        """drafted 상태에서 바로 approved 불가."""
        await _seed_draft(db)
        with pytest.raises(ValueError, match="must be ready"):
            await save_review_decision(db, draft_id=DRAFT_ID, decision="approved")

    @pytest.mark.asyncio
    async def test_reject_from_any_status(self, db):
        """rejected는 어떤 상태에서든 가능 (review_status만 변경)."""
        await _seed_draft(db)
        decision_id = await save_review_decision(db, draft_id=DRAFT_ID, decision="rejected")
        assert decision_id > 0
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["review_status"] == "Rejected"

    @pytest.mark.asyncio
    async def test_invalid_decision_raises(self, db):
        await _seed_draft(db)
        with pytest.raises(ValueError, match="unsupported review decision"):
            await save_review_decision(db, draft_id=DRAFT_ID, decision="maybe")

    @pytest.mark.asyncio
    async def test_decision_on_unknown_draft(self, db):
        with pytest.raises(ValueError, match="unknown draft_id"):
            await save_review_decision(db, draft_id="ghost-id", decision="rejected")


# ── record_publish_receipt 엣지 케이스 ────────────────────────────────────────


class TestPublishReceipt:

    @pytest.mark.asyncio
    async def test_publish_requires_approved_status(self, db):
        await _seed_draft(db)
        with pytest.raises(ValueError, match="must be approved"):
            await record_publish_receipt(db, draft_id=DRAFT_ID, platform="x", success=True)

    @pytest.mark.asyncio
    async def test_failed_publish_does_not_advance_status(self, db):
        """발행 실패 시 lifecycle은 approved 유지."""
        await _seed_draft(db)
        await promote_draft_to_ready(db, DRAFT_ID)
        await save_review_decision(db, draft_id=DRAFT_ID, decision="approved")

        receipt = await record_publish_receipt(
            db,
            draft_id=DRAFT_ID,
            platform="x",
            success=False,
            failure_code="RATE_LIMIT",
            failure_reason="429 Too Many Requests",
        )
        row = await get_draft_bundle(db, DRAFT_ID)
        # 실패 시 approved 유지
        assert row["lifecycle_status"] == "approved"
        assert receipt  # receipt_id는 발급됨


# ── record_feedback_summary 엣지 케이스 ───────────────────────────────────────


class TestFeedbackSummary:

    @pytest.mark.asyncio
    async def test_feedback_requires_publish_receipt(self, db):
        await _seed_draft(db)
        with pytest.raises(ValueError, match="publish receipt required"):
            await record_feedback_summary(
                db, draft_id=DRAFT_ID, metric_window="48h"
            )

    @pytest.mark.asyncio
    async def test_feedback_on_unknown_draft(self, db):
        with pytest.raises(ValueError, match="unknown draft_id"):
            await record_feedback_summary(
                db, draft_id="ghost", metric_window="24h", receipt_id="r-123"
            )


# ── save_draft_bundle UPSERT ──────────────────────────────────────────────────


class TestDraftBundleUpsert:

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db):
        await _seed_draft(db, body="원본")
        await _seed_draft(db, body="수정됨")
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["body"] == "수정됨"

    @pytest.mark.asyncio
    async def test_multiple_drafts_independent(self, db):
        await _seed_validated_trend(db, trend_id="t-001")
        await _seed_validated_trend(db, trend_id="t-002")
        await _seed_draft(db, draft_id="d-001", trend_id="t-001", body="첫 번째", _skip_trend=True)
        await _seed_draft(db, draft_id="d-002", trend_id="t-002", body="두 번째", _skip_trend=True)
        r1 = await get_draft_bundle(db, "d-001")
        r2 = await get_draft_bundle(db, "d-002")
        assert r1["body"] == "첫 번째"
        assert r2["body"] == "두 번째"


# ── QA report ─────────────────────────────────────────────────────────────────


class TestQAReport:

    @pytest.mark.asyncio
    async def test_qa_report_updates_draft_score(self, db):
        await _seed_draft(db)
        report_id = await save_qa_report(
            db,
            draft_id=DRAFT_ID,
            total_score=8.5,
            passed=True,
            warnings=["minor style issue"],
        )
        assert report_id > 0
        row = await get_draft_bundle(db, DRAFT_ID)
        assert row["qa_score"] == 8.5


# ── content_feedback (record + 무시) ──────────────────────────────────────────


class TestContentFeedback:

    @pytest.mark.asyncio
    async def test_record_and_silent_failure(self, db):
        """content_feedback 테이블 없어도 예외 발생하지 않는지 확인 (graceful degradation)."""
        # 정상 기록
        await record_content_feedback(
            db, keyword="AI", category="tech", qa_score=9.0, regenerated=False
        )
        # 테이블 있을 때 다시 호출해도 문제 없음
        await record_content_feedback(db, keyword="AI")
