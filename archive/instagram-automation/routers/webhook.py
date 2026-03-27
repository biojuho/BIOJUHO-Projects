"""Meta Webhook Router.

Handles Instagram webhook verification and event processing.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from dependencies import get_config, get_dm_responder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/instagram")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification endpoint.

    Meta will send a GET request to verify the webhook endpoint.
    """
    config = get_config()
    if hub_mode == "subscribe" and hub_verify_token == config.webhook.verify_token:
        logger.info("Webhook verified successfully")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/instagram")
async def receive_webhook(request: Request):
    """Receive and process Meta webhook events.

    Handles incoming webhook events from Meta (Instagram messages, comments, etc.)
    """
    dm_responder = get_dm_responder()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    body_bytes = await request.body()

    if not dm_responder.verify_signature(body_bytes, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = await request.json()
    events = dm_responder.parse_webhook_body(body)

    for event in events:
        try:
            await dm_responder.handle_event(event)
        except Exception as e:
            logger.error("Error handling webhook event: %s", e)

    return {"status": "ok"}
