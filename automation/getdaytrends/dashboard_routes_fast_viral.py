"""FastAPI routes for direct-community early viral detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

if TYPE_CHECKING:
    try:
        from .fast_viral_collector import FastViralCollector
    except ImportError:
        from fast_viral_collector import FastViralCollector


router = APIRouter(prefix="/api/fast-viral", tags=["fast-viral"])
_collector: FastViralCollector | None = None


def init_fast_viral_router(collector: FastViralCollector) -> None:
    global _collector
    _collector = collector


def _fast_viral_collector() -> FastViralCollector:
    if _collector is None:
        raise HTTPException(status_code=503, detail="fast viral collector is not initialized")
    return _collector


@router.get("")
def get_fast_viral():
    return _fast_viral_collector().snapshot()


@router.post("/refresh")
async def refresh_fast_viral(limit: int = Query(default=12, ge=5, le=30)):
    return await _fast_viral_collector().refresh(limit=limit)
