"""External trigger API router — n8n and webhook integration endpoints.

Routes for external automation platforms to trigger posts and push trends.
All routes require authentication via X-API-Token header.

Endpoints:
- POST /api/external/trigger-post   Trigger a single post
- POST /api/external/push-trends    Push trending topics
- GET  /api/external/status         System status
- GET  /api/external/trigger-log    Recent trigger history
"""

from __future__ import annotations

from dependencies import get_trigger_handler
from fastapi import APIRouter, Depends, HTTPException, Request
from services.external_trigger import (
    ExternalTriggerHandler,
    TrendPushRequest,
    TriggerPostRequest,
    verify_token,
)

router = APIRouter(prefix="/api/external", tags=["external"])


# ---- Helper Functions ----


def _check_token(request: Request) -> None:
    """Validate external API token from header.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If token is invalid or missing
    """
    token = request.headers.get("X-API-Token", "")
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


# ---- Route Handlers ----


@router.post("/trigger-post")
async def external_trigger_post(
    req: TriggerPostRequest,
    request: Request,
    trigger_handler: ExternalTriggerHandler = Depends(get_trigger_handler),
):
    """Trigger a single post from external system (n8n, webhook).

    Args:
        req: Post trigger configuration
        request: FastAPI request (for auth)
        trigger_handler: External trigger handler dependency

    Returns:
        Trigger result with status and details

    Raises:
        HTTPException: If authentication fails
    """
    _check_token(request)
    result = trigger_handler.handle_post_trigger(req)
    return result.model_dump()


@router.post("/push-trends")
async def external_push_trends(
    req: TrendPushRequest,
    request: Request,
    trigger_handler: ExternalTriggerHandler = Depends(get_trigger_handler),
):
    """Push trending topics from GetDayTrends or other sources.

    Args:
        req: Trend push configuration
        request: FastAPI request (for auth)
        trigger_handler: External trigger handler dependency

    Returns:
        Trigger result with processed trends

    Raises:
        HTTPException: If authentication fails
    """
    _check_token(request)
    result = trigger_handler.handle_trend_push(req)
    return result.model_dump()


@router.get("/status")
async def external_status(
    request: Request,
    trigger_handler: ExternalTriggerHandler = Depends(get_trigger_handler),
):
    """System status for external monitoring.

    Args:
        request: FastAPI request (for auth)
        trigger_handler: External trigger handler dependency

    Returns:
        System status and metrics

    Raises:
        HTTPException: If authentication fails
    """
    _check_token(request)
    return trigger_handler.get_status()


@router.get("/trigger-log")
async def external_trigger_log(
    request: Request,
    trigger_handler: ExternalTriggerHandler = Depends(get_trigger_handler),
):
    """Recent external trigger history.

    Args:
        request: FastAPI request (for auth)
        trigger_handler: External trigger handler dependency

    Returns:
        Recent trigger log entries (last 20)

    Raises:
        HTTPException: If authentication fails
    """
    _check_token(request)
    return {"log": trigger_handler._trigger_log[-20:]}
