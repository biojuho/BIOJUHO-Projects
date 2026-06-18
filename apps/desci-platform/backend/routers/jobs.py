"""
BioLinker job API.

These endpoints expose long-running workflows through a create/read/stream
contract that the frontend can poll or consume through server-sent events.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from limiter import limiter
from models import (
    JobAcceptedResponse,
    JobSnapshot,
    JobType,
    PaperIndexJobRequest,
    PaperMatchJobRequest,
    ProposalGenerationJobRequest,
)
from services.auth import get_current_user, get_optional_current_user
from services.job_manager import JobContext, get_job_manager
from services.logging_config import get_logger
from services.usage_middleware import TierRequired, UsageGuard
from services.user_tier import UserTier

log = get_logger("biolinker.routers.jobs")

router = APIRouter()


def get_scheduler():
    from services.scheduler import get_scheduler as _get_scheduler

    return _get_scheduler()


def get_asset_manager():
    from services.asset_manager import get_asset_manager as _get_asset_manager

    return _get_asset_manager()


def get_rfp_matcher():
    from services.matcher import get_rfp_matcher as _get_rfp_matcher

    return _get_rfp_matcher()


def get_proposal_generator():
    from services.proposal_generator import get_proposal_generator as _get_proposal_generator

    return _get_proposal_generator()


def get_vector_store():
    from services.vector_store import get_vector_store as _get_vector_store

    return _get_vector_store()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _assert_owned_paper(paper_id: str, user: dict[str, Any], *, require_indexed_record: bool) -> dict[str, Any] | None:
    manager = get_asset_manager()
    if not manager.has_paper(paper_id):
        raise HTTPException(status_code=404, detail="Paper not found")

    owner_uid = manager.get_paper_owner_uid(paper_id)
    if not owner_uid:
        raise HTTPException(status_code=403, detail="Paper ownership could not be verified")
    if owner_uid != user.get("uid"):
        raise HTTPException(status_code=403, detail="You do not have access to this paper")

    paper_record = get_vector_store().get_notice(paper_id)
    if require_indexed_record and paper_record is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper_record


def _require_job_access(job_id: str, user: dict[str, Any] | None):
    manager = get_job_manager()
    record = manager.get_record(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.access != "public":
        if user is None:
            raise _unauthorized()
        if not record.owner_uid or record.owner_uid != user.get("uid"):
            raise HTTPException(status_code=403, detail="You do not have access to this job")

    return record


async def _run_notice_collection_job(context: JobContext) -> dict[str, Any]:
    scheduler = get_scheduler()
    if scheduler is None:
        raise RuntimeError("Notice scheduler is unavailable")

    await context.update(15, "Collecting notices from configured sources")
    notices = await scheduler.collect_all_notices()
    await context.update(85, f"Collected {len(notices)} notices")
    return {"collected": len(notices), "notices": notices[:10]}


async def _run_paper_index_job(context: JobContext) -> dict[str, Any]:
    payload = context.payload
    await context.update(20, "Loading uploaded paper")
    result = await get_asset_manager().reindex_paper(
        paper_id=str(payload["paper_id"]),
        user=dict(payload.get("user", {}) or {}),
    )
    await context.update(85, "Paper index refreshed")
    return result


async def _run_paper_match_job(context: JobContext) -> dict[str, Any]:
    payload = context.payload
    matcher = get_rfp_matcher()
    paper_id = str(payload["paper_id"])
    limit = int(payload.get("limit", 5) or 5)
    target_trl = payload.get("target_trl")
    enrich = bool(payload.get("enrich", False))

    await context.update(20, "Loading paper context")
    await context.update(55, "Searching matching RFPs")
    try:
        result = await matcher.match_paper(
            paper_id=paper_id,
            limit=limit,
            target_trl=target_trl,
            enrich=enrich,
        )
    except TypeError:
        if target_trl is not None:
            try:
                result = await matcher.match_paper(paper_id=paper_id, limit=limit, target_trl=target_trl)
            except TypeError:
                result = await matcher.match_paper(paper_id=paper_id, limit=limit)
        else:
            result = await matcher.match_paper(paper_id=paper_id, limit=limit)
    await context.update(85, "Ranking match results")
    if isinstance(result, dict):
        return result
    return {"matches": result}


async def _run_proposal_generation_job(context: JobContext) -> dict[str, Any]:
    payload = context.payload
    vector_store = get_vector_store()
    paper_id = str(payload["paper_id"])
    rfp_id = str(payload["rfp_id"])

    await context.update(20, "Loading paper and RFP context")
    paper = vector_store.get_notice(paper_id)
    if not paper:
        raise RuntimeError("Paper not found")

    rfp = vector_store.get_notice(rfp_id)
    if not rfp:
        raise RuntimeError("RFP not found")

    generator = get_proposal_generator()
    await context.update(50, "Generating proposal draft")
    draft = await generator.generate_draft(rfp, paper)
    await context.update(80, "Reviewing proposal quality")
    critique = await generator.review_draft(rfp, paper, draft)
    await context.update(95, "Finalizing proposal result")
    return {"draft": draft, "critique": critique}


@router.post(
    "/jobs/notices/collect",
    response_model=JobAcceptedResponse,
    summary="Create a notice collection job",
    tags=["Jobs"],
)
@limiter.limit("10/minute")
async def create_notice_collection_job(request: Request):
    manager = get_job_manager()
    return await manager.create_job(
        job_type=JobType.NOTICE_COLLECTION,
        payload={},
        runner=_run_notice_collection_job,
        message="Queued notice collection",
        access="public",
    )


@router.post(
    "/jobs/papers/index",
    response_model=JobAcceptedResponse,
    summary="Create a paper reindexing job",
    tags=["Jobs"],
)
@limiter.limit("10/minute")
async def create_paper_index_job(
    request: Request,
    body: PaperIndexJobRequest,
    user: dict = Depends(get_current_user),
):
    _assert_owned_paper(body.paper_id, user, require_indexed_record=False)
    manager = get_job_manager()
    return await manager.create_job(
        job_type=JobType.PAPER_INDEX,
        payload={"paper_id": body.paper_id, "user": user},
        runner=_run_paper_index_job,
        message="Queued paper indexing",
        owner_uid=user.get("uid"),
    )


@router.post(
    "/jobs/match/paper",
    response_model=JobAcceptedResponse,
    summary="Create a paper-to-RFP matching job",
    tags=["Jobs"],
)
@limiter.limit("20/minute")
async def create_paper_match_job(
    request: Request,
    body: PaperMatchJobRequest,
    user: dict = Depends(get_current_user),
):
    _assert_owned_paper(body.paper_id, user, require_indexed_record=True)
    manager = get_job_manager()
    return await manager.create_job(
        job_type=JobType.PAPER_MATCH,
        payload=body.model_dump(),
        runner=_run_paper_match_job,
        message="Queued paper matching",
        owner_uid=user.get("uid"),
    )


@router.post(
    "/jobs/proposal/generate",
    response_model=JobAcceptedResponse,
    summary="Create a proposal generation job",
    tags=["Jobs"],
)
@limiter.limit("10/minute")
async def create_proposal_generation_job(
    request: Request,
    body: ProposalGenerationJobRequest,
    user: dict = Depends(get_current_user),
    _tier=Depends(TierRequired(UserTier.PRO)),
    _usage=Depends(UsageGuard("proposal_generation")),
):
    _assert_owned_paper(body.paper_id, user, require_indexed_record=True)
    if get_vector_store().get_notice(body.rfp_id) is None:
        raise HTTPException(status_code=404, detail="RFP not found")

    manager = get_job_manager()
    return await manager.create_job(
        job_type=JobType.PROPOSAL_GENERATION,
        payload=body.model_dump(),
        runner=_run_proposal_generation_job,
        message="Queued proposal generation",
        owner_uid=user.get("uid"),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobSnapshot,
    summary="Get the latest snapshot for a job",
    tags=["Jobs"],
)
@limiter.limit("60/minute")
async def get_job(
    request: Request,
    job_id: str,
    user: dict | None = Depends(get_optional_current_user),
):
    record = _require_job_access(job_id, user)
    return record.snapshot()


@router.get(
    "/jobs/{job_id}/events",
    summary="Stream job progress as server-sent events",
    tags=["Jobs"],
)
async def stream_job_events(
    job_id: str,
    user: dict | None = Depends(get_optional_current_user),
):
    _require_job_access(job_id, user)
    manager = get_job_manager()

    async def event_stream():
        async for snapshot in manager.stream(job_id):
            yield f"data: {snapshot.model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
