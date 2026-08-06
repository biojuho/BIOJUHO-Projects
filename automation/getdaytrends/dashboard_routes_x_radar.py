"""FastAPI routes for the live X content opportunity radar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    try:
        from .x_opportunity_radar import XOpportunityRadar
    except ImportError:
        from x_opportunity_radar import XOpportunityRadar


router = APIRouter(prefix="/api/x-radar", tags=["x-opportunity-radar"])
_radar: XOpportunityRadar | None = None


class XRadarRefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    country: str = Field(default="korea", pattern="^(korea)$")
    limit: int = Field(default=20, ge=5, le=30)
    focus_keywords: list[str] = Field(default_factory=list, max_length=8)
    force_refresh: bool = False

    @field_validator("focus_keywords")
    @classmethod
    def validate_focus_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("focus keywords must be 80 characters or fewer")
        return cleaned


def init_x_radar_router(radar: XOpportunityRadar) -> None:
    global _radar
    _radar = radar


def _x_radar() -> XOpportunityRadar:
    if _radar is None:
        raise HTTPException(status_code=503, detail="X opportunity radar is not initialized")
    return _radar


@router.get("")
def get_x_radar():
    return _x_radar().snapshot()


@router.post("/refresh")
async def refresh_x_radar(payload: XRadarRefreshRequest):
    return await _x_radar().refresh(
        country=payload.country,
        limit=payload.limit,
        focus_keywords=payload.focus_keywords,
        force_refresh=payload.force_refresh,
    )
