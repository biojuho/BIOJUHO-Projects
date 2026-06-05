"""Focused tests for TAP pipeline refresh hooks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

try:
    from getdaytrends.core.pipeline import _step_refresh_tap_products
    from getdaytrends.tap.service import dispatch_tap_alert_queue

except (ImportError, ModuleNotFoundError):
    from core.pipeline import _step_refresh_tap_products
    from tap.service import dispatch_tap_alert_queue


@pytest.mark.asyncio
async def test_step_refresh_tap_products_skips_single_country_configs():
    result = await _step_refresh_tap_products(
        AsyncMock(),
        SimpleNamespace(enable_tap=True, countries=["korea"]),
    )

    assert result == {}


@pytest.mark.asyncio
async def test_step_refresh_tap_products_returns_refresh_summary():
    summary_stub = SimpleNamespace(
        to_dict=lambda: {
            "markets": [{"target_country": "korea", "queued": 1}],
            "snapshots_built": 2,
            "alerts_queued": 1,
            "total_detected": 4,
        }
    )

    with patch("getdaytrends.tap.refresh_tap_market_surfaces", new_callable=AsyncMock, return_value=summary_stub):
        result = await _step_refresh_tap_products(
            AsyncMock(),
            SimpleNamespace(enable_tap=True, countries=["korea", "united-states"]),
        )

    assert result["snapshots_built"] == 2
    assert result["alerts_queued"] == 1


@pytest.mark.asyncio
async def test_step_refresh_tap_products_dispatches_when_enabled():
    summary_stub = SimpleNamespace(
        to_dict=lambda: {
            "markets": [{"target_country": "korea", "queued": 1}],
            "snapshots_built": 2,
            "alerts_queued": 2,
            "total_detected": 4,
        }
    )
    dispatch_stub = SimpleNamespace(
        to_dict=lambda: {
            "attempted": 2,
            "dispatched": 2,
            "failed": 0,
            "skipped": 0,
            "items": [],
        }
    )
    config = SimpleNamespace(
        enable_tap=True,
        countries=["korea", "united-states"],
        enable_tap_alert_dispatch=True,
        tap_alert_dispatch_batch_size=3,
    )

    with (
        patch("getdaytrends.tap.refresh_tap_market_surfaces", new_callable=AsyncMock, return_value=summary_stub),
        patch(
            "getdaytrends.tap.dispatch_tap_alert_queue", new_callable=AsyncMock, return_value=dispatch_stub
        ) as mock_dispatch,
    ):
        result = await _step_refresh_tap_products(AsyncMock(), config)

    assert result["dispatch"]["dispatched"] == 2
    mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_tap_alert_queue_coalesces_duplicate_dedupe_keys_when_enabled():
    sent_messages: list[str] = []
    updates: list[dict] = []

    async def load_batch(conn, *, limit, target_country, lifecycle_status):
        assert limit == 10
        assert target_country == ""
        assert lifecycle_status == "queued"
        return [
            {
                "alert_id": "alert-1",
                "dedupe_key": "us:airegulation",
                "keyword": "AI regulation",
                "alert_message": "first alert",
            },
            {
                "alert_id": "alert-2",
                "dedupe_key": "us:airegulation",
                "keyword": "AI regulation",
                "alert_message": "duplicate alert",
            },
            {
                "alert_id": "alert-3",
                "dedupe_key": "us:climate",
                "keyword": "Climate trend",
                "alert_message": "second key alert",
            },
        ]

    async def update_status(conn, **kwargs):
        updates.append(kwargs)
        return True

    def send_alert(message, config):
        sent_messages.append(message)
        return {"telegram": {"ok": True}}

    module_name = dispatch_tap_alert_queue.__module__
    config = SimpleNamespace(
        tap_alert_dispatch_batch_size=10,
        tap_alert_dispatch_coalesce=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        no_alerts=False,
    )

    with (
        patch(f"{module_name}._load_alert_queue_funcs", return_value=(load_batch, update_status)),
        patch(f"{module_name}._load_alert_sender", return_value=send_alert),
    ):
        summary = await dispatch_tap_alert_queue(AsyncMock(), config)

    payload = summary.to_dict()
    assert sent_messages == ["first alert", "second key alert"]
    assert payload["attempted"] == 2
    assert payload["dispatched"] == 2
    assert payload["skipped"] == 1
    assert payload["coalesced"] == 1
    assert [item["status"] for item in payload["items"]] == [
        "coalesced_duplicate",
        "dispatched",
        "dispatched",
    ]
    assert payload["items"][0]["alert_id"] == "alert-2"
    assert payload["items"][0]["coalesced_into_alert_id"] == "alert-1"
    assert [(item["alert_id"], item["lifecycle_status"]) for item in updates] == [
        ("alert-2", "skipped"),
        ("alert-1", "dispatched"),
        ("alert-3", "dispatched"),
    ]
    assert updates[0]["metadata_patch"]["last_delivery"]["reason"] == "coalesced_duplicate"
