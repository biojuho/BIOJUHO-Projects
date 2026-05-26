from __future__ import annotations

import pytest
from stripe_helpers import _extract_tap_purchase_from_stripe_event, _validate_tap_checkout_payload_matches_handle


def test_extract_tap_purchase_from_completed_paid_session() -> None:
    event = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_123",
                "client_reference_id": "stripe:premium_alert_bundle:united-states:AI regulation",
                "amount_total": 9900,
                "currency": "usd",
                "payment_status": "paid",
                "payment_intent": "pi_123",
                "customer": "cus_123",
                "customer_details": {"email": "buyer@example.com"},
                "metadata": {
                    "snapshot_id": "snap_1",
                    "audience_segment": "creator",
                    "price_anchor": "$99",
                },
            }
        },
    }

    purchase = _extract_tap_purchase_from_stripe_event(event)

    assert purchase["handled"] is True
    assert purchase["event_id"] == "evt_123"
    assert purchase["keyword"] == "AI regulation"
    assert purchase["target_country"] == "united-states"
    assert purchase["package_tier"] == "premium_alert_bundle"
    assert purchase["session_id"] == "cs_123"
    assert purchase["actor_id"] == "buyer@example.com"
    assert purchase["revenue_value"] == 99.0
    assert purchase["metadata"]["stripe_payment_intent"] == "pi_123"
    assert purchase["metadata"]["stripe_customer_id"] == "cus_123"


def test_extract_tap_purchase_uses_handle_and_price_fallbacks() -> None:
    event = {
        "id": "evt_handle",
        "type": "checkout.session.async_payment_succeeded",
        "data": {
            "object": {
                "id": "cs_handle",
                "client_reference_id": "stripe:premium_alert_bundle:japan:Robotaxi",
                "amount_total": 2500,
                "currency": "jpy",
                "customer": "cus_handle",
                "metadata": {"snapshot_id": "snap_handle"},
            }
        },
    }

    purchase = _extract_tap_purchase_from_stripe_event(event)

    assert purchase["handled"] is True
    assert purchase["keyword"] == "Robotaxi"
    assert purchase["target_country"] == "japan"
    assert purchase["package_tier"] == "premium_alert_bundle"
    assert purchase["audience_segment"] == "creator"
    assert purchase["offer_tier"] == "premium"
    assert purchase["price_anchor"] == "JPY 2500"
    assert purchase["actor_id"] == "cus_handle"


def test_extract_tap_purchase_ignores_unpaid_completed_session() -> None:
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"payment_status": "unpaid", "metadata": {"keyword": "AI"}}},
    }

    assert _extract_tap_purchase_from_stripe_event(event) == {
        "handled": False,
        "reason": "session_not_paid",
        "event_type": "checkout.session.completed",
    }


def test_extract_tap_purchase_rejects_missing_keyword_and_invalid_amount() -> None:
    missing_keyword = {
        "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {"metadata": {}, "amount_total": 9900}},
    }
    invalid_amount = {
        "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {"metadata": {"keyword": "AI"}, "amount_total": "bad"}},
    }

    assert _extract_tap_purchase_from_stripe_event(missing_keyword)["reason"] == "missing_keyword"
    assert _extract_tap_purchase_from_stripe_event(invalid_amount)["reason"] == "invalid_amount_total"


def test_validate_tap_checkout_payload_matches_handle_preserves_error_strings() -> None:
    parsed = {
        "keyword": "AI regulation",
        "target_country": "united-states",
        "package_tier": "premium_alert_bundle",
    }

    _validate_tap_checkout_payload_matches_handle(
        parsed,
        keyword="ai regulation",
        target_country="united-states",
        package_tier="premium_alert_bundle",
    )

    with pytest.raises(ValueError, match="checkout_handle keyword mismatch"):
        _validate_tap_checkout_payload_matches_handle(
            parsed,
            keyword="Different topic",
            target_country="united-states",
            package_tier="premium_alert_bundle",
        )
