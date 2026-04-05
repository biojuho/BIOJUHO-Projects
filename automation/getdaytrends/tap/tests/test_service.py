"""Tests for TAP service helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tap.detector import ArbitrageOpportunity
from tap.product_feed import TapBoard
from tap.service import (
    TapBoardRequest,
    build_tap_board_snapshot,
    dispatch_tap_alert_queue,
    get_latest_tap_board_snapshot,
    refresh_tap_market_surfaces,
)


def _db_funcs(load_return=None, save_return="tap_saved", enqueue_return=0):
    return (
        AsyncMock(return_value=load_return),
        AsyncMock(return_value=save_return),
        AsyncMock(return_value=enqueue_return),
    )


def _alert_queue_funcs(batch_return=None):
    return (
        AsyncMock(return_value=batch_return or []),
        AsyncMock(return_value=True),
    )


@pytest.mark.asyncio
async def test_build_tap_board_snapshot_uses_target_country_and_teaser_count():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(country="korea")

    opportunities = [
        ArbitrageOpportunity(
            keyword="Trend A",
            source_country="korea",
            target_countries=["united-states"],
            viral_score=90,
            priority=88.0,
            time_gap_hours=2.0,
        ),
        ArbitrageOpportunity(
            keyword="Trend B",
            source_country="japan",
            target_countries=["united-states"],
            viral_score=75,
            priority=60.0,
            time_gap_hours=5.0,
        ),
    ]

    with patch("tap.service._load_db_funcs", return_value=_db_funcs(load_return=None)), \
         patch("tap.service.TrendArbitrageDetector.detect", new_callable=AsyncMock, return_value=opportunities):
        board = await build_tap_board_snapshot(
            mock_conn,
            mock_config,
            TapBoardRequest(target_country="united-states", limit=10, teaser_count=1),
        )

    assert board.target_country == "united-states"
    assert board.total_detected == 2
    assert board.items[0].paywall_tier.value == "free_teaser"
    assert board.items[1].paywall_tier.value == "premium"


@pytest.mark.asyncio
async def test_build_tap_board_snapshot_falls_back_to_config_country():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(country="japan")

    with patch("tap.service._load_db_funcs", return_value=_db_funcs(load_return=None)), \
         patch("tap.service.TrendArbitrageDetector.detect", new_callable=AsyncMock, return_value=[]):
        board = await build_tap_board_snapshot(mock_conn, mock_config, TapBoardRequest())

    assert board.target_country == "japan"
    assert board.total_detected == 0
    assert board.items == []


@pytest.mark.asyncio
async def test_get_latest_tap_board_snapshot_projects_cached_board():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(country="united-states")
    cached_board = TapBoard.from_dict(
        {
            "snapshot_id": "tap_cached",
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "united-states",
            "total_detected": 3,
            "teaser_count": 2,
            "items": [
                {
                    "keyword": "Trend A",
                    "source_country": "korea",
                    "target_countries": ["united-states"],
                    "viral_score": 90,
                    "priority": 88.0,
                    "time_gap_hours": 2.0,
                    "paywall_tier": "premium",
                    "public_teaser": "teaser-a",
                    "recommended_platforms": ["x"],
                    "recommended_angle": "angle-a",
                    "execution_notes": ["note-a"],
                    "publish_window": None,
                    "revenue_play": None,
                },
                {
                    "keyword": "Trend B",
                    "source_country": "japan",
                    "target_countries": ["united-states"],
                    "viral_score": 80,
                    "priority": 75.0,
                    "time_gap_hours": 3.0,
                    "paywall_tier": "premium",
                    "public_teaser": "teaser-b",
                    "recommended_platforms": ["x"],
                    "recommended_angle": "angle-b",
                    "execution_notes": ["note-b"],
                    "publish_window": None,
                    "revenue_play": None,
                },
            ],
            "snapshot_source": "test_suite",
            "delivery_mode": "cached",
            "future_dependencies": [],
        }
    )

    with patch("tap.service._load_db_funcs", return_value=_db_funcs(load_return=cached_board)):
        board = await get_latest_tap_board_snapshot(
            mock_conn,
            mock_config,
            TapBoardRequest(limit=1, teaser_count=1),
        )

    assert board is not None
    assert board.delivery_mode == "cached"
    assert len(board.items) == 1
    assert board.items[0].paywall_tier.value == "free_teaser"


@pytest.mark.asyncio
async def test_build_tap_board_snapshot_persists_fresh_board():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(country="korea")
    opportunities = [
        ArbitrageOpportunity(
            keyword="Trend A",
            source_country="korea",
            target_countries=["united-states"],
            viral_score=90,
            priority=88.0,
            time_gap_hours=2.0,
        )
    ]
    save_mock = AsyncMock(return_value="tap_saved")

    with patch("tap.service._load_db_funcs", return_value=(AsyncMock(return_value=None), save_mock, AsyncMock(return_value=0))), \
         patch("tap.service.TrendArbitrageDetector.detect", new_callable=AsyncMock, return_value=opportunities):
        board = await build_tap_board_snapshot(
            mock_conn,
            mock_config,
            TapBoardRequest(target_country="united-states", limit=1, teaser_count=1),
        )

    assert board.delivery_mode == "live"
    assert board.items[0].paywall_tier.value == "free_teaser"
    save_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_tap_market_surfaces_builds_each_market_and_queues_alerts():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(
        country="korea",
        countries=["korea", "united-states", "japan"],
        tap_board_limit=5,
        tap_teaser_count=1,
        tap_snapshot_max_age_minutes=30,
        enable_tap_alert_queue=True,
        tap_alert_top_k=2,
        tap_alert_min_priority=80.0,
        tap_alert_min_viral_score=75,
        tap_alert_cooldown_minutes=180,
    )

    board = TapBoard.from_dict(
        {
            "snapshot_id": "tap_market",
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "korea",
            "total_detected": 2,
            "teaser_count": 1,
            "items": [],
            "snapshot_source": "tap_refresh",
            "delivery_mode": "live",
            "future_dependencies": [],
        }
    )

    with patch("tap.service.build_tap_board_snapshot", new_callable=AsyncMock, return_value=board) as mock_build, \
         patch("tap.service._load_db_funcs", return_value=(AsyncMock(return_value=None), AsyncMock(return_value="tap_market"), AsyncMock(return_value=2))):
        summary = await refresh_tap_market_surfaces(mock_conn, mock_config, snapshot_source="pipeline")

    assert summary.snapshots_built == 3
    assert summary.alerts_queued == 6
    assert summary.total_detected == 6
    assert len(summary.markets) == 3
    assert mock_build.await_count == 3


@pytest.mark.asyncio
async def test_dispatch_tap_alert_queue_marks_successful_items_dispatched():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        discord_webhook_url="",
        slack_webhook_url="",
        smtp_host="",
        alert_email="",
        no_alerts=False,
        tap_alert_dispatch_batch_size=5,
    )
    batch = [
        {
            "alert_id": "tapa_1",
            "keyword": "AI regulation",
            "alert_message": "message-1",
        },
        {
            "alert_id": "tapa_2",
            "keyword": "Chip war",
            "alert_message": "message-2",
        },
    ]
    queue_load, update_status = _alert_queue_funcs(batch_return=batch)

    with patch("tap.service._load_alert_queue_funcs", return_value=(queue_load, update_status)), \
         patch("tap.service._load_alert_sender", return_value=lambda message, config: {"telegram": {"ok": True}}):
        summary = await dispatch_tap_alert_queue(mock_conn, mock_config, limit=2)

    assert summary.attempted == 2
    assert summary.dispatched == 2
    assert summary.failed == 0
    assert update_status.await_count == 2
    assert all(item["status"] == "dispatched" for item in summary.items)
    metadata_patch = update_status.await_args_list[0].kwargs["metadata_patch"]
    assert metadata_patch["last_delivery"]["status"] == "dispatched"
    assert metadata_patch["last_delivery"]["channel_results"]["telegram"]["ok"] is True


@pytest.mark.asyncio
async def test_dispatch_tap_alert_queue_persists_failure_reason():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        discord_webhook_url="",
        slack_webhook_url="",
        smtp_host="",
        alert_email="",
        no_alerts=False,
        tap_alert_dispatch_batch_size=5,
    )
    batch = [
        {
            "alert_id": "tapa_failed",
            "keyword": "AI regulation",
            "alert_message": "message-1",
        }
    ]
    queue_load, update_status = _alert_queue_funcs(batch_return=batch)

    with patch("tap.service._load_alert_queue_funcs", return_value=(queue_load, update_status)), \
         patch("tap.service._load_alert_sender", return_value=lambda message, config: {"telegram": {"ok": False, "error": "timeout"}}):
        summary = await dispatch_tap_alert_queue(mock_conn, mock_config, limit=1)

    assert summary.failed == 1
    assert summary.items[0]["failure_reason"] == "telegram: timeout"
    metadata_patch = update_status.await_args.kwargs["metadata_patch"]
    assert metadata_patch["last_delivery"]["status"] == "failed"
    assert metadata_patch["last_delivery"]["failure_reason"] == "telegram: timeout"


@pytest.mark.asyncio
async def test_dispatch_tap_alert_queue_dry_run_does_not_update_queue():
    mock_conn = AsyncMock()
    mock_config = SimpleNamespace(
        telegram_bot_token="",
        telegram_chat_id="",
        discord_webhook_url="",
        slack_webhook_url="",
        smtp_host="",
        alert_email="",
        no_alerts=False,
        tap_alert_dispatch_batch_size=5,
    )
    batch = [
        {
            "alert_id": "tapa_1",
            "keyword": "AI regulation",
            "alert_message": "message-1",
        }
    ]
    queue_load, update_status = _alert_queue_funcs(batch_return=batch)

    with patch("tap.service._load_alert_queue_funcs", return_value=(queue_load, update_status)):
        summary = await dispatch_tap_alert_queue(mock_conn, mock_config, limit=1, dry_run=True)

    assert summary.dry_run is True
    assert summary.skipped == 1
    assert summary.dispatched == 0
    update_status.assert_not_awaited()
