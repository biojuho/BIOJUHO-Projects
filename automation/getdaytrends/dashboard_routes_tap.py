"""
getdaytrends — TAP (Trend Arbitrage Publisher) Dashboard Routes.
Stripe checkout, deal room, alert dispatch 라우트.
dashboard.py에서 분리됨. FastAPI APIRouter 사용.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

try:
    from .db import (
        get_connection,
        get_tap_alert_queue_snapshot,
        get_tap_checkout_session_summary,
        get_tap_deal_room_funnel,
        init_db,
        mark_tap_checkout_session_completed,
        record_tap_deal_room_event,
        upsert_tap_checkout_session,
    )
    from .tap import (
        DealRoomRequest,
        TapBoardRequest,
        build_tap_board_snapshot,
        build_tap_deal_room_snapshot,
        dispatch_tap_alert_queue,
        empty_tap_board,
        get_latest_tap_board_snapshot,
    )
except ImportError:
    from db import (
        get_tap_alert_queue_snapshot,
        get_tap_checkout_session_summary,
        get_tap_deal_room_funnel,
        mark_tap_checkout_session_completed,
        record_tap_deal_room_event,
        upsert_tap_checkout_session,
    )
    from tap import (
        DealRoomRequest,
        TapBoardRequest,
        build_tap_board_snapshot,
        build_tap_deal_room_snapshot,
        dispatch_tap_alert_queue,
        empty_tap_board,
        get_latest_tap_board_snapshot,
    )

try:
    from .stripe_helpers import (
        _build_tap_checkout_redirect_urls,
        _coerce_non_negative_float,
        _construct_stripe_event,
        _create_stripe_checkout_session,
        _extract_price_anchor_amount,
        _extract_tap_purchase_from_stripe_event,
        _format_stripe_price_anchor,
        _parse_tap_checkout_handle,
        _retrieve_stripe_checkout_session,
        _stripe_amount_divisor,
        _stripe_checkout_session_status_payload,
        _validate_stripe_checkout_session_payload,
        _validate_tap_checkout_payload_matches_handle,
    )
except ImportError:
    from stripe_helpers import (
        _build_tap_checkout_redirect_urls,
        _coerce_non_negative_float,
        _construct_stripe_event,
        _create_stripe_checkout_session,
        _extract_price_anchor_amount,
        _extract_tap_purchase_from_stripe_event,
        _parse_tap_checkout_handle,
        _retrieve_stripe_checkout_session,
        _stripe_amount_divisor,
        _stripe_checkout_session_status_payload,
        _validate_stripe_checkout_session_payload,
        _validate_tap_checkout_payload_matches_handle,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tap"])

# These will be injected from dashboard.py
_config = None
_get_conn = None
_close_conn = None
_run_db_json_with_fallback = None
_tap_alert_queue_fallback = None
_tap_deal_room_fallback = None
_tap_deal_room_funnel_fallback = None
_tap_checkout_summary_fallback = None


def init_tap_router(
    config,
    get_conn_fn,
    close_conn_fn,
    run_db_json_fn,
    alert_queue_fallback,
    deal_room_fallback,
    funnel_fallback,
    checkout_summary_fallback,
) -> None:
    """Inject dependencies from main dashboard module."""
    global _config, _get_conn, _close_conn, _run_db_json_with_fallback
    global _tap_alert_queue_fallback, _tap_deal_room_fallback
    global _tap_deal_room_funnel_fallback, _tap_checkout_summary_fallback
    _config = config
    _get_conn = get_conn_fn
    _close_conn = close_conn_fn
    _run_db_json_with_fallback = run_db_json_fn
    _tap_alert_queue_fallback = alert_queue_fallback
    _tap_deal_room_fallback = deal_room_fallback
    _tap_deal_room_funnel_fallback = funnel_fallback
    _tap_checkout_summary_fallback = checkout_summary_fallback


def _tap_alert_dispatch_fallback(*, target_country: str, dry_run: bool) -> dict:
    return {
        "target_country": (target_country or "").strip().lower(),
        "dry_run": dry_run,
        "channels": [],
        "attempted": 0,
        "dispatched": 0,
        "failed": 0,
        "skipped": 0,
        "items": [],
    }


@router.get("/api/tap/alerts")
async def api_tap_alert_queue(
    limit: int = Query(20, ge=1, le=200),
    lifecycle_status: str = Query("queued", min_length=0, max_length=32),
    target_country: str = Query("", min_length=0, max_length=64),
) -> object:
    """Operational snapshot of the TAP premium alert queue."""

    async def _load_tap_alert_queue(conn) -> object:
        return await get_tap_alert_queue_snapshot(
            conn,
            limit=limit,
            lifecycle_status=lifecycle_status,
            target_country=target_country,
        )

    return await _run_db_json_with_fallback(
        "api_tap_alert_queue",
        _load_tap_alert_queue,
        _tap_alert_queue_fallback,
    )


@router.post("/api/tap/alerts/dispatch")
async def api_dispatch_tap_alert_queue(
    limit: int = Query(5, ge=1, le=100),
    target_country: str = Query("", min_length=0, max_length=64),
    dry_run: bool = Query(False),
) -> object:
    """Manually drain queued TAP alerts into configured channels."""
    async def _dispatch(conn) -> object:
        summary = await dispatch_tap_alert_queue(
            conn,
            _config,
            limit=limit,
            target_country=target_country,
            dry_run=dry_run,
        )
        return summary.to_dict()

    return await _run_db_json_with_fallback(
        "api_tap_alert_dispatch",
        _dispatch,
        lambda: _tap_alert_dispatch_fallback(target_country=target_country, dry_run=dry_run),
    )


@router.get("/api/tap/opportunities")
async def api_tap_opportunities(
    target_country: str = Query("", min_length=0, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    teaser_count: int = Query(3, ge=0, le=10),
    force_refresh: bool = Query(False),
) -> object:
    """Phase-1 product feed for TAP arbitrage opportunities."""
    board_country = (target_country or _config.country or "").strip().lower()

    async def _load_tap_opportunities(conn) -> object:
        board = await build_tap_board_snapshot(
            conn,
            _config,
            TapBoardRequest(
                target_country=board_country,
                limit=limit,
                teaser_count=teaser_count,
                force_refresh=force_refresh,
                snapshot_source="dashboard_api",
            ),
        )
        return board.to_dict()

    return await _run_db_json_with_fallback(
        "api_tap_opportunities",
        _load_tap_opportunities,
        lambda: empty_tap_board(target_country=board_country, teaser_count=teaser_count).to_dict(),
    )


@router.get("/api/tap/opportunities/latest")
async def api_tap_opportunities_latest(
    target_country: str = Query("", min_length=0, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    teaser_count: int = Query(3, ge=0, le=10),
    max_age_minutes: int = Query(180, ge=0, le=1440),
) -> object:
    """Read the most recent TAP snapshot without forcing a rebuild."""
    board_country = (target_country or _config.country or "").strip().lower()

    async def _load_tap_opportunities_latest(conn) -> object:
        board = await get_latest_tap_board_snapshot(
            conn,
            _config,
            TapBoardRequest(
                target_country=board_country,
                limit=limit,
                teaser_count=teaser_count,
                persist_snapshot=False,
                snapshot_max_age_minutes=max_age_minutes,
                snapshot_source="dashboard_api",
            ),
        )
        if board is None:
            board = empty_tap_board(target_country=board_country, teaser_count=teaser_count)
        return board.to_dict()

    return await _run_db_json_with_fallback(
        "api_tap_opportunities_latest",
        _load_tap_opportunities_latest,
        lambda: empty_tap_board(target_country=board_country, teaser_count=teaser_count).to_dict(),
    )


@router.get("/api/tap/deal-room")
async def api_tap_deal_room(
    target_country: str = Query("", min_length=0, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    teaser_count: int = Query(3, ge=0, le=10),
    audience_segment: str = Query("creator", min_length=1, max_length=64),
    package_tier: str = Query("premium_alert_bundle", min_length=1, max_length=64),
    currency: str = Query("USD", min_length=1, max_length=8),
    include_public_teasers: bool = Query(True),
    include_checkout: bool = Query(False),
) -> object:
    """Commercial scaffolding for teaser-to-premium TAP conversion."""

    async def _load_tap_deal_room(conn) -> object:
        room = await build_tap_deal_room_snapshot(
            conn,
            _config,
            DealRoomRequest(
                target_country=target_country,
                limit=limit,
                teaser_count=teaser_count,
                audience_segment=audience_segment,
                package_tier=package_tier,
                currency=currency,
                include_public_teasers=include_public_teasers,
                include_checkout=include_checkout,
            ),
        )
        return room.to_dict()

    return await _run_db_json_with_fallback(
        "api_tap_deal_room",
        _load_tap_deal_room,
        lambda: _tap_deal_room_fallback(
            target_country=target_country,
            teaser_count=teaser_count,
            audience_segment=audience_segment,
            package_tier=package_tier,
        ),
    )


@router.post("/api/tap/deal-room/events")
async def api_tap_deal_room_event(
    keyword: str = Query(..., min_length=1, max_length=200),
    event_type: str = Query(..., min_length=1, max_length=64),
    snapshot_id: str = Query("", min_length=0, max_length=128),
    target_country: str = Query("", min_length=0, max_length=64),
    audience_segment: str = Query("creator", min_length=1, max_length=64),
    package_tier: str = Query("premium_alert_bundle", min_length=1, max_length=64),
    offer_tier: str = Query("premium", min_length=1, max_length=32),
    price_anchor: str = Query("", min_length=0, max_length=32),
    checkout_handle: str = Query("", min_length=0, max_length=256),
    session_id: str = Query("", min_length=0, max_length=128),
    actor_id: str = Query("", min_length=0, max_length=128),
    revenue_value: float = Query(0.0, ge=0.0),
) -> object:
    """Track one TAP deal-room funnel event."""
    normalized_keyword = (keyword or "").strip()
    raw_event_type = str(event_type or "")
    normalized_event_type = raw_event_type.strip().lower()
    supported_event_types = {"view", "click", "checkout_open", "purchase"}

    if not normalized_keyword:
        return JSONResponse({"ok": False, "error": "keyword is required"}, status_code=400)
    if normalized_event_type not in supported_event_types:
        return JSONResponse(
            {
                "ok": False,
                "error": f"unsupported deal-room event_type: {raw_event_type.strip() or raw_event_type}",
            },
            status_code=400,
        )

    conn = None
    try:
        conn = await _get_conn()
        try:
            event_id = await record_tap_deal_room_event(
                conn,
                keyword=normalized_keyword,
                event_type=normalized_event_type,
                snapshot_id=snapshot_id,
                target_country=target_country,
                audience_segment=audience_segment,
                package_tier=package_tier,
                offer_tier=offer_tier,
                price_anchor=price_anchor,
                checkout_handle=checkout_handle,
                session_id=session_id,
                actor_id=actor_id,
                revenue_value=revenue_value,
            )
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return JSONResponse({"ok": True, "event_id": event_id})
    finally:
        await _close_conn(conn)


@router.get("/api/tap/deal-room/funnel")
async def api_tap_deal_room_funnel(
    days: int = Query(30, ge=1, le=365),
    target_country: str = Query("", min_length=0, max_length=64),
    audience_segment: str = Query("", min_length=0, max_length=64),
    package_tier: str = Query("", min_length=0, max_length=64),
    limit: int = Query(20, ge=1, le=200),
) -> object:
    """Read aggregated TAP deal-room funnel performance."""

    async def _load_tap_deal_room_funnel(conn) -> object:
        return await get_tap_deal_room_funnel(
            conn,
            days=days,
            target_country=target_country,
            audience_segment=audience_segment,
            package_tier=package_tier,
            limit=limit,
        )

    return await _run_db_json_with_fallback(
        "api_tap_deal_room_funnel",
        _load_tap_deal_room_funnel,
        lambda: _tap_deal_room_funnel_fallback(
            days=days,
            target_country=target_country,
            audience_segment=audience_segment,
            package_tier=package_tier,
        ),
    )


@router.get("/api/tap/deal-room/checkouts")
async def api_tap_deal_room_checkouts(
    days: int = Query(30, ge=1, le=365),
    target_country: str = Query("", min_length=0, max_length=64),
    audience_segment: str = Query("", min_length=0, max_length=64),
    package_tier: str = Query("", min_length=0, max_length=64),
    limit: int = Query(10, ge=1, le=100),
) -> object:
    """Read checkout-session ops summary for TAP deal-room commerce."""

    async def _load_tap_deal_room_checkouts(conn) -> object:
        return await get_tap_checkout_session_summary(
            conn,
            days=days,
            target_country=target_country,
            audience_segment=audience_segment,
            package_tier=package_tier,
            limit=limit,
        )

    return await _run_db_json_with_fallback(
        "api_tap_deal_room_checkouts",
        _load_tap_deal_room_checkouts,
        lambda: _tap_checkout_summary_fallback(
            days=days,
            target_country=target_country,
            audience_segment=audience_segment,
            package_tier=package_tier,
        ),
    )


# ── Stripe helpers (extracted to stripe_helpers.py) ──


def _tap_checkout_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)


def _tap_checkout_price_value(payload: dict, price_anchor: str) -> float:
    quoted_price_value = payload.get("quoted_price_value")
    return float(quoted_price_value if quoted_price_value not in (None, "") else _extract_price_anchor_amount(price_anchor))


def _tap_checkout_keyword(payload: dict) -> str:
    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("keyword is required")
    return keyword


def _tap_checkout_parsed_handle(payload: dict) -> tuple[str, dict]:
    checkout_handle = str(payload.get("checkout_handle") or "").strip()
    parsed_handle = _parse_tap_checkout_handle(checkout_handle)
    if parsed_handle.get("provider") != "stripe":
        raise ValueError("Unsupported checkout handle")
    return checkout_handle, parsed_handle


def _tap_checkout_target_context(payload: dict, parsed_handle: dict) -> tuple[str, str]:
    target_country = str(payload.get("target_country") or parsed_handle.get("target_country") or "").strip().lower()
    package_tier = (
        str(payload.get("package_tier") or parsed_handle.get("package_tier") or "premium_alert_bundle").strip().lower()
    )
    return target_country, package_tier


def _validate_tap_checkout_context(
    parsed_handle: dict,
    *,
    keyword: str,
    target_country: str,
    package_tier: str,
) -> None:
    _validate_tap_checkout_payload_matches_handle(
        parsed_handle,
        keyword=keyword,
        target_country=target_country,
        package_tier=package_tier,
    )


def _tap_checkout_positive_price(payload: dict) -> tuple[str, float]:
    price_anchor = str(payload.get("price_anchor") or "").strip()
    price_value = _tap_checkout_price_value(payload, price_anchor)
    if price_value <= 0:
        raise ValueError("quoted_price_value must be positive")
    return price_anchor, price_value


def _tap_checkout_optional_context(payload: dict, keyword: str) -> dict:
    return {
        "premium_title": str(payload.get("premium_title") or keyword).strip(),
        "teaser_body": str(payload.get("teaser_body") or "").strip(),
        "snapshot_id": str(payload.get("snapshot_id") or "").strip(),
        "audience_segment": str(payload.get("audience_segment") or "creator").strip().lower(),
        "offer_tier": str(payload.get("offer_tier") or "premium").strip().lower(),
        "actor_id": str(payload.get("actor_id") or "").strip(),
        "pricing_variant": str(payload.get("pricing_variant") or "").strip(),
        "pricing_context": payload.get("pricing_context") if isinstance(payload.get("pricing_context"), dict) else {},
    }


def _tap_checkout_request_context(payload: dict) -> dict:
    keyword = _tap_checkout_keyword(payload)
    checkout_handle, parsed_handle = _tap_checkout_parsed_handle(payload)
    target_country, package_tier = _tap_checkout_target_context(payload, parsed_handle)
    _validate_tap_checkout_context(
        parsed_handle,
        keyword=keyword,
        target_country=target_country,
        package_tier=package_tier,
    )

    price_anchor, price_value = _tap_checkout_positive_price(payload)
    currency = str(payload.get("currency") or "usd").strip().lower()
    return _tap_checkout_optional_context(payload, keyword) | {
        "keyword": keyword,
        "checkout_handle": checkout_handle,
        "target_country": target_country,
        "package_tier": package_tier,
        "currency": currency,
        "price_anchor": price_anchor,
        "price_value": price_value,
    }


def _tap_checkout_metadata(context: dict) -> dict:
    return {
        "keyword": context["keyword"],
        "snapshot_id": context["snapshot_id"],
        "target_country": context["target_country"],
        "audience_segment": context["audience_segment"],
        "package_tier": context["package_tier"],
        "offer_tier": context["offer_tier"],
        "price_anchor": context["price_anchor"],
        "quoted_price_value": f"{context['price_value']:.2f}",
        "checkout_handle": context["checkout_handle"],
        "currency": context["currency"],
        "actor_id": context["actor_id"],
        "pricing_variant": context["pricing_variant"],
    }


def _tap_checkout_response_payload(session_id: str, session_url: str, checkout_handle: str) -> dict:
    return {
        "ok": True,
        "provider": "stripe",
        "session_id": session_id,
        "url": session_url,
        "checkout_handle": checkout_handle,
        "tracking_status": "tracked",
    }


def _tap_checkout_session_status_error(message: str, session_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "provider": "stripe",
            "session_id": session_id,
            "status": "unavailable",
            "error": message,
        },
        status_code=status_code,
    )


async def _persist_tap_checkout_tracking(
    *,
    context: dict,
    session_id: str,
    session_url: str,
    success_url: str,
    cancel_url: str,
) -> None:
    conn = None
    try:
        conn = await _get_conn()
        await upsert_tap_checkout_session(
            conn,
            checkout_session_id=session_id,
            checkout_handle=context["checkout_handle"],
            snapshot_id=context["snapshot_id"],
            keyword=context["keyword"],
            target_country=context["target_country"],
            audience_segment=context["audience_segment"],
            package_tier=context["package_tier"],
            offer_tier=context["offer_tier"],
            session_status="created",
            payment_status="pending",
            currency=context["currency"],
            quoted_price_value=context["price_value"],
            revenue_value=0.0,
            checkout_url=session_url,
            actor_id=context["actor_id"],
            metadata={
                "provider": "stripe",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "pricing_variant": context["pricing_variant"],
                "pricing_context": context["pricing_context"],
            },
        )
        await record_tap_deal_room_event(
            conn,
            keyword=context["keyword"],
            event_type="checkout_open",
            snapshot_id=context["snapshot_id"],
            target_country=context["target_country"],
            audience_segment=context["audience_segment"],
            package_tier=context["package_tier"],
            offer_tier=context["offer_tier"],
            price_anchor=context["price_anchor"],
            checkout_handle=context["checkout_handle"],
            session_id=session_id,
            actor_id=context["actor_id"],
            revenue_value=0.0,
            metadata={
                "provider": "stripe",
                "quoted_price_value": context["price_value"],
                "checkout_url": session_url,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "pricing_variant": context["pricing_variant"],
                "pricing_context": context["pricing_context"],
            },
        )
    finally:
        await _close_conn(conn)


@router.post("/api/tap/deal-room/checkout")
async def api_tap_deal_room_checkout(request: Request) -> object:
    """Create a Stripe Checkout Session for one TAP deal-room offer."""
    try:
        payload = await request.json()
    except Exception:
        return _tap_checkout_error("Invalid JSON payload")

    try:
        context = _tap_checkout_request_context(payload)
    except (TypeError, ValueError) as exc:
        return _tap_checkout_error(str(exc))

    success_url, cancel_url = _build_tap_checkout_redirect_urls(request, context["keyword"])
    unit_amount = int(round(context["price_value"] * _stripe_amount_divisor(context["currency"])))
    try:
        session = _create_stripe_checkout_session(
            secret_key=getattr(_config, "stripe_secret_key", ""),
            currency=context["currency"],
            unit_amount=unit_amount,
            keyword=context["keyword"],
            premium_title=context["premium_title"],
            teaser_body=context["teaser_body"],
            checkout_handle=context["checkout_handle"],
            metadata=_tap_checkout_metadata(context),
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except RuntimeError as exc:
        return _tap_checkout_error(str(exc), status_code=503)
    except ValueError as exc:
        return _tap_checkout_error(str(exc))

    try:
        session_id, session_url = _validate_stripe_checkout_session_payload(session)
    except ValueError as exc:
        return _tap_checkout_error(str(exc), status_code=502)

    response_payload = _tap_checkout_response_payload(session_id, session_url, context["checkout_handle"])
    try:
        await _persist_tap_checkout_tracking(
            context=context,
            session_id=session_id,
            session_url=session_url,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception:
        logger.warning("Stripe checkout tracking degraded", exc_info=True)
        response_payload["tracking_status"] = "degraded"
        response_payload["tracking_warning"] = (
            "Checkout was created, but tracking persistence is temporarily unavailable."
        )

    return JSONResponse(response_payload)


@router.get("/api/tap/deal-room/checkout/session/{session_id}")
async def api_tap_deal_room_checkout_session_status(
    session_id: str = Path(..., min_length=1, max_length=128),
) -> object:
    """Retrieve a Stripe Checkout Session for dashboard return-page display only."""
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id.startswith("cs_"):
        return _tap_checkout_session_status_error(
            "checkout session id must start with cs_",
            normalized_session_id,
            400,
        )

    try:
        session = _retrieve_stripe_checkout_session(
            secret_key=getattr(_config, "stripe_secret_key", ""),
            session_id=normalized_session_id,
        )
        payload = _stripe_checkout_session_status_payload(session)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message or "package is required" in message else 502
        return _tap_checkout_session_status_error(message, normalized_session_id, status_code)
    except ValueError as exc:
        return _tap_checkout_session_status_error(str(exc), normalized_session_id, 502)

    return JSONResponse(payload)


@router.post("/api/tap/deal-room/webhooks/stripe")
async def api_tap_deal_room_stripe_webhook(request: Request) -> object:
    """Verify Stripe checkout completion webhooks and store purchase events."""
    try:
        event = await _verified_stripe_webhook_event(request)
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    purchase = _extract_tap_purchase_from_stripe_event(event)
    try:
        purchase_record = _tap_purchase_webhook_record(purchase)
    except _TapWebhookIgnored as ignored:
        return JSONResponse(ignored.payload)

    conn = None
    try:
        conn = await _get_conn()
        event_id = await _persist_tap_purchase_webhook(conn, purchase_record)
        return JSONResponse(_tap_purchase_webhook_success(event_id, purchase_record))
    except Exception:
        logger.warning("Stripe webhook persistence failed", exc_info=True)
        return JSONResponse(_tap_purchase_webhook_retryable_error(purchase_record), status_code=503)
    finally:
        await _close_conn(conn)


class _TapWebhookIgnored(Exception):
    def __init__(self, payload: dict) -> None:
        self.payload = payload


async def _verified_stripe_webhook_event(request: Request) -> dict:
    payload = await request.body()
    stripe_signature = request.headers.get("Stripe-Signature", "")
    signing_secret = getattr(_config, "stripe_webhook_secret", "")
    return _construct_stripe_event(payload, stripe_signature, signing_secret)


def _tap_webhook_ignored_payload(reason: str, purchase: dict, **extra: object) -> dict:
    payload = {
        "ok": True,
        "ignored": True,
        "reason": reason,
        "event_type": extra.pop("event_type", "purchase"),
    }
    keyword = purchase.get("keyword", "")
    if keyword:
        payload["keyword"] = keyword
    payload.update(extra)
    return payload


def _require_tap_webhook_session_id(purchase: dict) -> str:
    session_id = str(purchase.get("session_id") or "").strip()
    if not session_id:
        raise _TapWebhookIgnored(_tap_webhook_ignored_payload("missing_session_id", purchase))
    return session_id


def _tap_webhook_revenue_value(purchase: dict, session_id: str) -> float:
    try:
        return round(_coerce_non_negative_float(purchase.get("revenue_value", 0.0), field_name="revenue_value"), 2)
    except ValueError as exc:
        raise _TapWebhookIgnored(
            _tap_webhook_ignored_payload("invalid_revenue_value", purchase, session_id=session_id)
        ) from exc


def _tap_webhook_metadata(purchase: dict) -> dict:
    return purchase.get("metadata", {}) or {}


def _tap_purchase_webhook_record(purchase: dict) -> dict:
    if not purchase.get("handled"):
        raise _TapWebhookIgnored(
            _tap_webhook_ignored_payload(
                purchase.get("reason", "unhandled"),
                purchase,
                event_type=purchase.get("event_type", ""),
            )
        )

    session_id = _require_tap_webhook_session_id(purchase)
    revenue_value = _tap_webhook_revenue_value(purchase, session_id)
    metadata = _tap_webhook_metadata(purchase)
    return {
        "purchase": purchase,
        "session_id": session_id,
        "revenue_value": revenue_value,
        "metadata": metadata,
        "payment_status": str(metadata.get("payment_status") or "paid").strip().lower() or "paid",
        "currency": str(metadata.get("currency") or "usd").strip().lower() or "usd",
        "stripe_customer_id": str(metadata.get("stripe_customer_id") or "").strip(),
        "event_id": str(purchase.get("event_id") or "").strip(),
    }


async def _persist_tap_purchase_webhook(conn, record: dict) -> str:
    completed = await mark_tap_checkout_session_completed(
        conn,
        checkout_session_id=record["session_id"],
        payment_status=record["payment_status"],
        revenue_value=record["revenue_value"],
        stripe_customer_id=record["stripe_customer_id"],
        stripe_event_id=record["event_id"],
        metadata=record["metadata"],
    )
    if not completed:
        await _insert_completed_tap_checkout_session(conn, record)
    return await _record_tap_purchase_event(conn, record)


async def _insert_completed_tap_checkout_session(conn, record: dict) -> None:
    purchase = record["purchase"]
    await upsert_tap_checkout_session(
        conn,
        checkout_session_id=record["session_id"],
        checkout_handle=purchase.get("checkout_handle", ""),
        snapshot_id=purchase.get("snapshot_id", ""),
        keyword=purchase["keyword"],
        target_country=purchase.get("target_country", ""),
        audience_segment=purchase.get("audience_segment", "creator"),
        package_tier=purchase.get("package_tier", "premium_alert_bundle"),
        offer_tier=purchase.get("offer_tier", "premium"),
        session_status="completed",
        payment_status=record["payment_status"],
        currency=record["currency"],
        quoted_price_value=record["revenue_value"],
        revenue_value=record["revenue_value"],
        checkout_url="",
        actor_id=purchase.get("actor_id", ""),
        stripe_customer_id=record["stripe_customer_id"],
        stripe_event_id=record["event_id"],
        metadata=record["metadata"],
        completed_at=datetime.utcnow().isoformat(),
    )


async def _record_tap_purchase_event(conn, record: dict) -> str:
    purchase = record["purchase"]
    return await record_tap_deal_room_event(
        conn,
        keyword=purchase["keyword"],
        event_type="purchase",
        snapshot_id=purchase.get("snapshot_id", ""),
        target_country=purchase.get("target_country", ""),
        audience_segment=purchase.get("audience_segment", "creator"),
        package_tier=purchase.get("package_tier", "premium_alert_bundle"),
        offer_tier=purchase.get("offer_tier", "premium"),
        price_anchor=purchase.get("price_anchor", ""),
        checkout_handle=purchase.get("checkout_handle", ""),
        session_id=record["session_id"],
        actor_id=purchase.get("actor_id", ""),
        revenue_value=record["revenue_value"],
        metadata=record["metadata"],
        event_id=record["event_id"],
    )


def _tap_purchase_webhook_success(event_id: str, record: dict) -> dict:
    return {
        "ok": True,
        "processed": True,
        "event_id": event_id,
        "keyword": record["purchase"]["keyword"],
        "event_type": "purchase",
        "revenue_value": record["revenue_value"],
    }


def _tap_purchase_webhook_retryable_error(record: dict) -> dict:
    return {
        "ok": False,
        "error": "Webhook persistence unavailable",
        "retryable": True,
        "event_id": record["event_id"],
        "session_id": record["session_id"],
    }
