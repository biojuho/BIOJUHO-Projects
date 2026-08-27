"""FastAPI routes for the live X content opportunity radar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    from .freshness import attach_freshness
    from .kernel_screen import attach_kernel_screen
except ImportError:  # 스크립트로 직접 실행할 때
    from freshness import attach_freshness
    from kernel_screen import attach_kernel_screen

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


# 0099: 합성 `items`와 분리 배열 4개에 같은 나이 표시 규칙을 적용한다.
# 한곳만 고치면 화면의 네 섹션이 서로 다른 나이 문법을 쓰는 일이 없다.
_ITEM_ARRAY_KEYS = (
    "items",
    "breaking_now_items",
    "latest_news_items",
    "today_issue_items",
    "x_native_items",
)


def _annotate_item_age(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    item = dict(raw)
    age = item.get("age_minutes")
    has_age = isinstance(age, (int, float)) and not isinstance(age, bool)
    item["age_basis"] = str(item.get("age_basis") or "unknown")
    item["age_display"] = f"{age:g}분" if has_age else "미상"
    if not has_age:
        item["age_minutes"] = None
    return item


def _with_explicit_age(payload: dict[str, object]) -> dict[str, object]:
    """Copy response items and make unknown age visible instead of guessing it."""
    response = dict(payload)
    for key in _ITEM_ARRAY_KEYS:
        raw_items = payload.get(key)
        if not isinstance(raw_items, list):
            continue
        annotated = [item for item in map(_annotate_item_age, raw_items) if item is not None]
        response[key] = annotated
    return response


def _render_x_radar(payload: dict[str, object]) -> dict[str, object]:
    visible = _with_explicit_age(payload)
    # 0099 snapshots distinguish the last attempt from the last successful
    # collection.  Keep compatibility with older snapshots, but a failed
    # attempt must never turn a last-good response fresh again.
    freshness_field = "last_success_at" if "last_success_at" in visible else "refreshed_at"
    return attach_kernel_screen(
        attach_freshness(visible, "x_radar", field=freshness_field),
        title_field="keyword",
    )


@router.get("")
def get_x_radar():
    # 수집이 멈춰도 화면은 마지막 스냅샷을 계속 보여준다. 얼마나 묵었는지를
    # 함께 실어 보내야 프론트가 라이브 표시를 껐다 켤 수 있다.
    return _render_x_radar(_x_radar().snapshot())


@router.post("/refresh")
async def refresh_x_radar(payload: XRadarRefreshRequest):
    # 화면은 이 응답을 그대로 렌더링한다(GET 스냅샷을 다시 부르지 않는다).
    # 여기에 freshness를 싣지 않으면 방금 수집한 직후에도 배지가 비어 버린다.
    result = await _x_radar().refresh(
        country=payload.country,
        limit=payload.limit,
        focus_keywords=payload.focus_keywords,
        force_refresh=payload.force_refresh,
    )
    return _render_x_radar(result)
