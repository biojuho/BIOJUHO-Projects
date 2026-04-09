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


def _validate_tap_checkout_payload_matches_handle(
    parsed_handle: dict[str, str],
    *,
    keyword: str,
    target_country: str,
    package_tier: str,
) -> None:
    handle_keyword = str(parsed_handle.get("keyword") or "").strip()
    handle_target_country = str(parsed_handle.get("target_country") or "").strip().lower()
    handle_package_tier = str(parsed_handle.get("package_tier") or "").strip().lower()

    if not handle_keyword:
        raise ValueError("checkout_handle is missing keyword")
    if not handle_target_country:
        raise ValueError("checkout_handle is missing target_country")
    if not handle_package_tier:
        raise ValueError("checkout_handle is missing package_tier")
    if (keyword or "").strip().casefold() != handle_keyword.casefold():
        raise ValueError("checkout_handle keyword mismatch")
    if (target_country or "").strip().lower() != handle_target_country:
        raise ValueError("checkout_handle target_country mismatch")
    if (package_tier or "").strip().lower() != handle_package_tier:
        raise ValueError("checkout_handle package_tier mismatch")


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
    success_url = f"{base_url}/?tap_checkout=success&tap_keyword={encoded_keyword}"
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


def _extract_tap_purchase_from_stripe_event(event: dict) -> dict:
    event_type = str(event.get("type") or "").strip()
    if event_type not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        return {"handled": False, "reason": "unsupported_event_type", "event_type": event_type}

    data = event.get("data") or {}
    session = data.get("object") or {}
    metadata = dict(session.get("metadata") or {})
    checkout_handle = metadata.get("checkout_handle") or session.get("client_reference_id") or ""
    parsed_handle = _parse_tap_checkout_handle(checkout_handle)
    payment_status = str(session.get("payment_status") or "").strip().lower()
    if event_type == "checkout.session.completed" and payment_status and payment_status != "paid":
        return {"handled": False, "reason": "session_not_paid", "event_type": event_type}

    keyword = metadata.get("keyword") or parsed_handle.get("keyword") or ""
    if not keyword:
        return {"handled": False, "reason": "missing_keyword", "event_type": event_type}

    amount_total = session.get("amount_total")
    currency = str(session.get("currency") or metadata.get("currency") or "usd")
    customer_details = session.get("customer_details") or {}
    revenue_value = 0.0
    if amount_total not in (None, ""):
        try:
            normalized_amount_total = _coerce_non_negative_float(amount_total, field_name="amount_total")
        except ValueError:
            return {"handled": False, "reason": "invalid_amount_total", "event_type": event_type}
        revenue_value = round(normalized_amount_total / _stripe_amount_divisor(currency), 2)

    return {
        "handled": True,
        "event_id": str(event.get("id") or ""),
        "event_type": "purchase",
        "provider_event_type": event_type,
        "keyword": keyword,
        "snapshot_id": metadata.get("snapshot_id") or "",
        "target_country": metadata.get("target_country") or parsed_handle.get("target_country") or "",
        "audience_segment": metadata.get("audience_segment") or "creator",
        "package_tier": metadata.get("package_tier") or parsed_handle.get("package_tier") or "premium_alert_bundle",
        "offer_tier": metadata.get("offer_tier") or "premium",
        "price_anchor": metadata.get("price_anchor") or _format_stripe_price_anchor(amount_total, currency),
        "checkout_handle": checkout_handle,
        "session_id": str(session.get("id") or ""),
        "actor_id": (
            metadata.get("actor_id")
            or session.get("customer_email")
            or customer_details.get("email")
            or session.get("customer")
            or ""
        ),
        "revenue_value": revenue_value,
        "metadata": {
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
        },
    }

