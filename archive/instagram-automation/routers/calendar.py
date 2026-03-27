"""Content calendar router — Weekly content planning endpoints.

Routes for managing and generating content calendars.

Endpoints:
- GET  /api/calendar/week      Get weekly content plan
- GET  /api/calendar/today     Get today's content plan
- POST /api/calendar/generate  Generate weekly plan
- GET  /api/calendar/stats     Calendar statistics
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from dependencies import get_calendar
from services.content_calendar import ContentCalendar

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


# ---- Pydantic Models ----


class CalendarGenerateRequest(BaseModel):
    """Request model for generating a weekly content plan."""

    posting_hours: list[int] = [12]


# ---- Route Handlers ----


@router.get("/week")
async def get_week_plan(
    start_date: str | None = Query(None),
    calendar: ContentCalendar = Depends(get_calendar),
):
    """Get weekly content plan.

    Args:
        start_date: Optional start date (ISO format)
        calendar: Content calendar dependency

    Returns:
        Weekly content plan with scheduled posts
    """
    return calendar.get_week_plan(start_date)


@router.get("/today")
async def get_today_plan(calendar: ContentCalendar = Depends(get_calendar)):
    """Get today's content plan.

    Args:
        calendar: Content calendar dependency

    Returns:
        Today's scheduled posts and tasks
    """
    return calendar.get_today_plan()


@router.post("/generate")
async def generate_week_plan(
    req: CalendarGenerateRequest,
    calendar: ContentCalendar = Depends(get_calendar),
):
    """Generate a weekly content plan.

    Args:
        req: Calendar generation configuration
        calendar: Content calendar dependency

    Returns:
        Generated calendar entries
    """
    entries = calendar.generate_weekly_plan(posting_hours=req.posting_hours)
    return {"generated": len(entries), "entries": [e.to_dict() for e in entries]}


@router.get("/stats")
async def calendar_stats(calendar: ContentCalendar = Depends(get_calendar)):
    """Calendar statistics.

    Args:
        calendar: Content calendar dependency

    Returns:
        Calendar statistics and metrics
    """
    return calendar.get_stats()
