"""FastAPI routes for direct-community early viral detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

try:
    from .freshness import attach_freshness
    from .kernel_screen import attach_kernel_screen
except ImportError:  # 스크립트로 직접 실행할 때
    from freshness import attach_freshness
    from kernel_screen import attach_kernel_screen

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
    # 적합도 점수(지금 퍼지는가)와 커널 판정(X에서 판정이 붙는가)은 다른 축이다.
    # 둘을 나란히 실어 보내야 점수 순으로 잘못 집는 걸 막는다.
    return attach_kernel_screen(attach_freshness(_fast_viral_collector().snapshot(), "fast_viral"))


@router.post("/refresh")
async def refresh_fast_viral(limit: int = Query(default=12, ge=5, le=30)):
    # GET 스냅샷과 같은 이유로 여기에도 싣는다 — 화면이 렌더링하는 건 이 응답이다.
    return attach_kernel_screen(attach_freshness(await _fast_viral_collector().refresh(limit=limit), "fast_viral"))
