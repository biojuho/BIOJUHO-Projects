"""FastAPI routes for the local creator reference library."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    from .live_reference_collector import DEFAULT_LIVE_KEYWORDS, YouTubeLiveReferenceCollector
    from .reference_library import (
        DuplicateReferenceError,
        ReferenceItemCreate,
        ReferenceItemPatch,
        ReferenceLibraryStore,
    )
except ImportError:
    from live_reference_collector import DEFAULT_LIVE_KEYWORDS, YouTubeLiveReferenceCollector
    from reference_library import (
        DuplicateReferenceError,
        ReferenceItemCreate,
        ReferenceItemPatch,
        ReferenceLibraryStore,
    )


router = APIRouter(prefix="/api/reference-library", tags=["reference-library"])
_store: ReferenceLibraryStore | None = None
_collector: YouTubeLiveReferenceCollector | None = None


class LiveRefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    keywords: list[str] = Field(default_factory=lambda: list(DEFAULT_LIVE_KEYWORDS), min_length=1, max_length=5)
    per_keyword: int = Field(default=5, ge=1, le=10)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one keyword is required")
        if any(len(value) > 100 for value in cleaned):
            raise ValueError("keywords must be 100 characters or fewer")
        return cleaned


def init_reference_router(
    store: ReferenceLibraryStore,
    collector: YouTubeLiveReferenceCollector | None = None,
) -> None:
    global _collector, _store
    _store = store
    _collector = collector


def _reference_store() -> ReferenceLibraryStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="reference library is not initialized")
    return _store


@router.get("")
def list_references(
    q: str = Query(default="", max_length=200),
    platform: str = Query(default="", pattern="^(|youtube|instagram|tiktok|threads|x|other)$"),
    content_format: str = Query(default="", pattern="^(|short|long|reel|carousel|post|thread|other)$"),
    saved: bool | None = None,
    read: bool | None = None,
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
):
    return {
        "items": _reference_store().list(
            query=q,
            platform=platform,
            content_format=content_format,
            saved=saved,
            read=read,
            min_score=min_score,
            limit=limit,
        )
    }


@router.get("/stats")
def reference_stats():
    return _reference_store().stats()


@router.get("/live/status")
def live_reference_status():
    payload = _reference_store().get_live_status()
    if _collector is not None:
        payload["capabilities"] = _collector.capabilities()
    return payload


@router.post("/live/refresh")
async def refresh_live_references(payload: LiveRefreshRequest):
    if _collector is None:
        raise HTTPException(status_code=503, detail="live reference collector is not initialized")
    return await _collector.refresh(payload.keywords, payload.per_keyword)


@router.get("/{item_id}")
def get_reference(item_id: str):
    try:
        return _reference_store().get(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="reference not found") from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_reference(payload: ReferenceItemCreate):
    try:
        return _reference_store().create(payload)
    except DuplicateReferenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{item_id}")
def update_reference(item_id: str, payload: ReferenceItemPatch):
    try:
        return _reference_store().update(item_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="reference not found") from exc
