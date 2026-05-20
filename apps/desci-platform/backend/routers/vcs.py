"""
BioLinker - VC firms router.

Public read-only endpoints over the curated VC dataset. Backed by
``VCRepository`` which transparently uses the Postgres ``vc_firms``
table when ``DATABASE_URL`` is set, otherwise the in-memory JSON seed.

Endpoints:
- ``GET /vcs``              List/filter VC firms (country, stage, keyword).
- ``GET /vcs/{vc_id}``      Fetch one VC firm by id.
- ``GET /vcs/meta/backend`` Diagnostic: which backend the runtime selected.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from limiter import limiter
from models import VCFirm
from services.logging_config import get_logger

log = get_logger("biolinker.routers.vcs")

router = APIRouter(prefix="/vcs", tags=["VCs"])


def _get_repository():
    from services.vc_repository import get_vc_repository

    return get_vc_repository()


@router.get(
    "",
    response_model=list[VCFirm],
    summary="List VC firms",
    response_description="Filtered list of VC firm profiles",
)
@limiter.limit("60/minute")
async def list_vcs(
    request: Request,
    country: str | None = Query(None, description="ISO 3166-1 alpha-2 country code (e.g. KR, US)"),
    stage: str | None = Query(None, description="Preferred investment stage (e.g. 'Series A')"),
    keyword: str | None = Query(None, description="Keyword to match against name/thesis"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows returned"),
) -> list[VCFirm]:
    repo = _get_repository()
    try:
        return await repo.list_vcs(country=country, stage=stage, keyword=keyword, limit=limit)
    except Exception as exc:
        log.error("vc_list_failed", error=str(exc), backend=getattr(repo, "backend", "?"))
        raise HTTPException(status_code=503, detail="VC repository unavailable") from exc


@router.get(
    "/meta/backend",
    summary="VC repository backend",
    response_description="Diagnostic info for the selected VC backend",
)
async def vcs_backend() -> dict:
    repo = _get_repository()
    return {"backend": getattr(repo, "backend", "unknown")}


@router.get(
    "/{vc_id}",
    response_model=VCFirm,
    summary="Get a single VC firm",
    response_description="Full VC firm profile",
)
@limiter.limit("60/minute")
async def get_vc(request: Request, vc_id: str) -> VCFirm:
    repo = _get_repository()
    try:
        vc = await repo.get_vc(vc_id)
    except Exception as exc:
        log.error("vc_get_failed", error=str(exc), vc_id=vc_id)
        raise HTTPException(status_code=503, detail="VC repository unavailable") from exc
    if vc is None:
        raise HTTPException(status_code=404, detail=f"VC firm '{vc_id}' not found")
    return vc
