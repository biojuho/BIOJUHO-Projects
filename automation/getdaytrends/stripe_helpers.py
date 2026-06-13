"""
getdaytrends — Stripe Payment Helpers.

Extracted from dashboard.py for maintainability.
Contains Stripe checkout session creation, webhook event parsing,
and currency/amount utilities.
"""

import re
from typing import Any
from urllib.parse import quote_plus

from fastapi import Request


def _stripe_amount_divisor(currency: str) -> int:
    zero_decimal_currencies = {
        "bif",
        "clp",
        "djf",
        "gnf",
        "jpy",
        "kmf",
        "krw",
        "mga",
        "pyg",
        "rwf",
        "ugx",
        "vnd",
        "vuv",
        "xaf",
        "xof",
        "xpf",
    }
    return 1 if (currency or "").strip().lower() in zero_decimal_currencies else 100


def _format_stripe_price_anchor(amount_total: int | float | None, currency: str) -> str:
    if amount_total in (None, ""):
        return ""
    normalized_currency = (currency or "usd").strip().lower()
    value = float(amount_total) / _stripe_amount_divisor(normalized_currency)
    if normalized_currency == "usd":
        return f"${value:.0f}"
    return f"{normalized_currency.upper()} {value:.0f}"


def _parse_tap_checkout_handle(checkout_handle: str) -> dict[str, str]:
    handle = (checkout_handle or "").strip()
    if not handle:
        return {}
    parts = handle.split(":", 3)
    if len(parts) < 4:
        return {}
    return {
        "provider": parts[0].strip().lower(),
        "package_tier": parts[1].strip().lower(),
        "target_country": parts[2].strip().lower(),
        "keyword": parts[3].strip(),
    }


def _require_checkout_handle_field(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"checkout_handle is missing {field_name}")


def _normalized_checkout_payload(parsed_handle: dict[str, str]) -> dict[str, str]:
    return {
        "keyword": str(parsed_handle.get("keyword") or "").strip(),
        "target_country": str(parsed_handle.get("target_country") or "").strip().lower(),
        "package_tier": str(parsed_handle.get("package_tier") or "").strip().lower(),
    }


def _validate_required_checkout_handle_fields(handle_payload: dict[str, str]) -> None:
    for field_name in ("keyword", "target_country", "package_tier"):
        _require_checkout_handle_field(handle_payload[field_name], field_name)


def _validate_checkout_handle_match(
    *,
    field_name: str,
    expected: str,
    actual: str,
    casefold: bool = False,
) -> None:
    if casefold:
        matches = expected.strip().casefold() == actual.casefold()
    else:
        matches = expected.strip().lower() == actual
    if not matches:
        raise ValueError(f"checkout_handle {field_name} mismatch")


def _validate_tap_checkout_payload_matches_handle(
    parsed_handle: dict[str, str],
    *,
    keyword: str,
    target_country: str,
    package_tier: str,
) -> None:
    handle_payload = _normalized_checkout_payload(parsed_handle)
    _validate_required_checkout_handle_fields(handle_payload)
    _validate_checkout_handle_match(
        field_name="keyword",
        expected=keyword or "",
        actual=handle_payload["keyword"],
        casefold=True,
    )
    _validate_checkout_handle_match(
        field_name="target_country",
        expected=target_country or "",
        actual=handle_payload["target_country"],
    )
    _validate_checkout_handle_match(
        field_name="package_tier",
        expected=package_tier or "",
        actual=handle_payload["package_tier"],
    )


def _extract_price_anchor_amount(price_anchor: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", str(price_anchor or ""))
    if not match:
        raise ValueError("Invalid TAP deal-room price anchor")
    return float(match.group(1))


def _coerce_non_negative_float(value: Any, *, field_name: str) -> float:
    if value in (None, ""):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}") from exc
    if parsed < 0:
        raise ValueError(f"Invalid {field_name}")
    return parsed


def _build_tap_checkout_redirect_urls(request: Request, keyword: str) -> tuple[str, str]:
    base_url = str(request.base_url).rstrip("/")
    encoded_keyword = quote_plus(str(keyword or ""))
    success_url = (
        f"{base_url}/?tap_checkout=success"
        f"&tap_keyword={encoded_keyword}"
        "&tap_checkout_session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{base_url}/?tap_checkout=cancel&tap_keyword={encoded_keyword}"
    return success_url, cancel_url


def _create_stripe_checkout_session(
    *,
    secret_key: str,
    currency: str,
    unit_amount: int,
    keyword: str,
    premium_title: str,
    teaser_body: str,
    checkout_handle: str,
    metadata: dict[str, str],
    success_url: str,
    cancel_url: str,
) -> dict:
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    if unit_amount <= 0:
        raise ValueError("Stripe checkout requires a positive unit amount")
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("stripe package is required for Stripe checkout") from exc

    stripe.api_key = secret_key
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=checkout_handle,
        metadata=metadata,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency,
                    "unit_amount": unit_amount,
                    "product_data": {
                        "name": premium_title or keyword,
                        "description": (teaser_body or f"Premium execution bundle for {keyword}")[:500],
                    },
                },
            }
        ],
    )
    return dict(session)


def _validate_stripe_checkout_session_payload(session: dict) -> tuple[str, str]:
    session_id = str(session.get("id") or "").strip()
    if not session_id:
        raise ValueError("Stripe checkout session response is missing id")

    session_url = str(session.get("url") or "").strip()
    if not session_url:
        raise ValueError("Stripe checkout session response is missing url")

    return session_id, session_url


def _retrieve_stripe_checkout_session(*, secret_key: str, session_id: str) -> dict:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("checkout session id is required")
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("stripe package is required for Stripe checkout session lookup") from exc

    stripe.api_key = secret_key
    try:
        session = stripe.checkout.Session.retrieve(normalized_session_id)
    except Exception as exc:
        raise RuntimeError(f"Stripe checkout session lookup failed: {exc}") from exc
    return dict(session)


def _stripe_checkout_session_status_payload(session: dict) -> dict:
    session_id = str(session.get("id") or "").strip()
    if not session_id:
        raise ValueError("Stripe checkout session response is missing id")

    metadata = dict(session.get("metadata") or {})
    checkout_handle = str(session.get("client_reference_id") or metadata.get("checkout_handle") or "").strip()
    parsed_handle = _parse_tap_checkout_handle(checkout_handle)
    currency = str(session.get("currency") or metadata.get("currency") or "").strip().lower()
    amount_total = session.get("amount_total")
    return {
        "ok": True,
        "provider": "stripe",
        "session_id": session_id,
        "checkout_status": str(session.get("status") or "").strip().lower(),
        "payment_status": str(session.get("payment_status") or "").strip().lower(),
        "currency": currency,
        "amount_total": amount_total if amount_total not in (None, "") else None,
        "price_anchor": _format_stripe_price_anchor(amount_total, currency) if amount_total not in (None, "") else "",
        "checkout_handle": checkout_handle,
        "keyword": str(metadata.get("keyword") or parsed_handle.get("keyword") or "").strip(),
        "target_country": str(metadata.get("target_country") or parsed_handle.get("target_country") or "").strip().lower(),
        "package_tier": str(
            metadata.get("package_tier") or parsed_handle.get("package_tier") or ""
        ).strip().lower(),
        "livemode": bool(session.get("livemode")),
    }


def _construct_stripe_event(payload: bytes, stripe_signature: str, signing_secret: str) -> dict:
    if not signing_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
    if not stripe_signature:
        raise ValueError("Missing Stripe-Signature header")
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("stripe package is required for Stripe webhook verification") from exc

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, signing_secret)
    except Exception as exc:
        raise ValueError("Invalid Stripe webhook signature") from exc
    return dict(event)


def _unsupported_stripe_event(event_type: str) -> dict | None:
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        return None
    return {"handled": False, "reason": "unsupported_event_type", "event_type": event_type}


def _stripe_session_from_event(event: dict) -> dict:
    data = event.get("data") or {}
    return data.get("object") or {}


def _stripe_checkout_handle(session: dict, metadata: dict) -> str:
    return metadata.get("checkout_handle") or session.get("client_reference_id") or ""


def _stripe_keyword(metadata: dict, parsed_handle: dict) -> str:
    return metadata.get("keyword") or parsed_handle.get("keyword") or ""


def _stripe_revenue_value(amount_total: object, currency: str, event_type: str) -> float | dict:
    if amount_total in (None, ""):
        return 0.0
    try:
        normalized_amount_total = _coerce_non_negative_float(amount_total, field_name="amount_total")
    except ValueError:
        return {"handled": False, "reason": "invalid_amount_total", "event_type": event_type}
    return round(normalized_amount_total / _stripe_amount_divisor(currency), 2)


def _stripe_actor_id(session: dict, metadata: dict, customer_details: dict) -> str:
    return (
        metadata.get("actor_id")
        or session.get("customer_email")
        or customer_details.get("email")
        or session.get("customer")
        or ""
    )


def _stripe_purchase_metadata(
    session: dict,
    metadata: dict,
    *,
    event_type: str,
    payment_status: str,
    currency: str,
    amount_total: object,
) -> dict:
    customer_details = session.get("customer_details") or {}
    return {
        "provider": "stripe",
        "stripe_event_type": event_type,
        "stripe_session_id": session.get("id") or "",
        "stripe_payment_intent": session.get("payment_intent") or "",
        "stripe_customer_id": session.get("customer") or "",
        "payment_status": payment_status,
        "currency": currency.lower(),
        "amount_total": amount_total if amount_total is not None else 0,
        "customer_email": session.get("customer_email") or customer_details.get("email") or "",
        "pricing_variant": metadata.get("pricing_variant") or "",
        "quoted_price_value": metadata.get("quoted_price_value") or "",
    }


def _stripe_unhandled(reason: str, event_type: str) -> dict:
    return {"handled": False, "reason": reason, "event_type": event_type}


def _stripe_payment_status(session: dict) -> str:
    return str(session.get("payment_status") or "").strip().lower()


def _stripe_event_context(event: dict) -> dict:
    event_type = str(event.get("type") or "").strip()
    session = _stripe_session_from_event(event)
    metadata = dict(session.get("metadata") or {})
    checkout_handle = _stripe_checkout_handle(session, metadata)
    return {
        "event_type": event_type,
        "session": session,
        "metadata": metadata,
        "checkout_handle": checkout_handle,
        "parsed_handle": _parse_tap_checkout_handle(checkout_handle),
        "payment_status": _stripe_payment_status(session),
    }


def _stripe_purchase_currency(session: dict, metadata: dict) -> str:
    return str(session.get("currency") or metadata.get("currency") or "usd")


def _stripe_purchase_target_country(metadata: dict, parsed_handle: dict) -> str:
    return metadata.get("target_country") or parsed_handle.get("target_country") or ""


def _stripe_purchase_package_tier(metadata: dict, parsed_handle: dict) -> str:
    return metadata.get("package_tier") or parsed_handle.get("package_tier") or "premium_alert_bundle"


def _stripe_purchase_price_anchor(metadata: dict, amount_total: object, currency: str) -> str:
    return metadata.get("price_anchor") or _format_stripe_price_anchor(amount_total, currency)


def _stripe_purchase_core_fields(event: dict, context: dict, keyword: str, revenue_value: float) -> dict:
    session = context["session"]
    return {
        "handled": True,
        "event_id": str(event.get("id") or ""),
        "event_type": "purchase",
        "provider_event_type": context["event_type"],
        "keyword": keyword,
        "checkout_handle": context["checkout_handle"],
        "session_id": str(session.get("id") or ""),
        "revenue_value": revenue_value,
    }


def _stripe_purchase_commerce_fields(
    metadata: dict,
    parsed_handle: dict,
    *,
    amount_total: object,
    currency: str,
) -> dict:
    return {
        "snapshot_id": metadata.get("snapshot_id") or "",
        "target_country": _stripe_purchase_target_country(metadata, parsed_handle),
        "audience_segment": metadata.get("audience_segment") or "creator",
        "package_tier": _stripe_purchase_package_tier(metadata, parsed_handle),
        "offer_tier": metadata.get("offer_tier") or "premium",
        "price_anchor": _stripe_purchase_price_anchor(metadata, amount_total, currency),
    }


def _stripe_purchase_payload(event: dict, context: dict, keyword: str, revenue_value: float) -> dict:
    session = context["session"]
    metadata = context["metadata"]
    parsed_handle = context["parsed_handle"]
    amount_total = session.get("amount_total")
    currency = _stripe_purchase_currency(session, metadata)
    customer_details = session.get("customer_details") or {}
    event_type = context["event_type"]
    return {
        **_stripe_purchase_core_fields(event, context, keyword, revenue_value),
        **_stripe_purchase_commerce_fields(
            metadata,
            parsed_handle,
            amount_total=amount_total,
            currency=currency,
        ),
        "actor_id": _stripe_actor_id(session, metadata, customer_details),
        "metadata": _stripe_purchase_metadata(
            session,
            metadata,
            event_type=event_type,
            payment_status=context["payment_status"],
            currency=currency,
            amount_total=amount_total,
        ),
    }


def _extract_tap_purchase_from_stripe_event(event: dict) -> dict:
    context = _stripe_event_context(event)
    event_type = context["event_type"]
    unsupported = _unsupported_stripe_event(event_type)
    if unsupported:
        return unsupported

    session = context["session"]
    metadata = context["metadata"]
    payment_status = context["payment_status"]
    if event_type == "checkout.session.completed" and payment_status and payment_status != "paid":
        return _stripe_unhandled("session_not_paid", event_type)

    keyword = _stripe_keyword(metadata, context["parsed_handle"])
    if not keyword:
        return _stripe_unhandled("missing_keyword", event_type)

    amount_total = session.get("amount_total")
    currency = str(session.get("currency") or metadata.get("currency") or "usd")
    revenue_value = _stripe_revenue_value(amount_total, currency, event_type)
    if isinstance(revenue_value, dict):
        return revenue_value

    return _stripe_purchase_payload(event, context, keyword, revenue_value)
