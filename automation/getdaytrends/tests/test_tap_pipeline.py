"""Focused tests for TAP pipeline refresh hooks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

try:

    from getdaytrends.core.pipeline import _step_refresh_tap_products

except (ImportError, ModuleNotFoundError):

    from core.pipeline import _step_refresh_tap_products


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

    with patch("getdaytrends.tap.refresh_tap_market_surfaces", new_callable=AsyncMock, return_value=summary_stub), \
         patch("getdaytrends.tap.dispatch_tap_alert_queue", new_callable=AsyncMock, return_value=dispatch_stub) as mock_dispatch:
        result = await _step_refresh_tap_products(AsyncMock(), config)

    assert result["dispatch"]["dispatched"] == 2
    mock_dispatch.assert_awaited_once()
