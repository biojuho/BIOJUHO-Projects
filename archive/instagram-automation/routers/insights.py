"""Instagram Insights API Router.

Routes for analytics, performance metrics, and reporting.

Endpoints:
- GET  /api/insights              Performance summary
- GET  /api/insights/report       Human-readable report
- POST /api/insights/collect      Trigger insights collection
- GET  /api/insights/best-times   Best posting times analysis
- GET  /api/insights/best-types   Best content types analysis
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dependencies import get_analytics
from services.analytics import AnalyticsEngine

router = APIRouter(
    prefix="/api/insights",
    tags=["insights"],
)


@router.get("")
async def get_insights(
    days: int = Query(30, ge=1, le=365),
    analytics: AnalyticsEngine = Depends(get_analytics),
):
    """Get performance summary.

    Args:
        days: Number of days to analyze (1-365)
        analytics: Analytics engine dependency

    Returns:
        Performance summary statistics
    """
    return analytics.get_performance_summary(days)


@router.get("/report")
async def get_report(
    days: int = Query(7, ge=1, le=90),
    analytics: AnalyticsEngine = Depends(get_analytics),
):
    """Get human-readable report.

    Args:
        days: Number of days to analyze (1-90)
        analytics: Analytics engine dependency

    Returns:
        Human-readable analytics report
    """
    return {"report": analytics.generate_report_text(days)}


@router.post("/collect")
async def trigger_collect(
    analytics: AnalyticsEngine = Depends(get_analytics),
):
    """Manually trigger insights collection.

    Args:
        analytics: Analytics engine dependency

    Returns:
        Number of insights collected
    """
    count = await analytics.collect_all_insights()
    return {"collected": count}


@router.get("/best-times")
async def best_posting_times(
    analytics: AnalyticsEngine = Depends(get_analytics),
):
    """Analyze best posting times.

    Args:
        analytics: Analytics engine dependency

    Returns:
        Best posting times based on historical performance
    """
    return analytics.get_best_posting_time()


@router.get("/best-types")
async def best_content_types(
    analytics: AnalyticsEngine = Depends(get_analytics),
):
    """Analyze best content types.

    Args:
        analytics: Analytics engine dependency

    Returns:
        Best content types based on historical performance
    """
    return analytics.get_best_content_type()
