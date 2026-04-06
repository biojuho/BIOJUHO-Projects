"""Tests for TAP deal room scaffolding."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tap.deal_room import (
    DealRoomRequest,
    TapDealRoomBuilder,
    build_tap_deal_room_snapshot,
    required_tap_deal_room_dependencies,
)
from tap.product_feed import OpportunityTier, PublishWindow, RevenuePlay, TapBoard, TapBoardItem


def _sample_board() -> TapBoard:
    return TapBoard(
        snapshot_id="tap_snapshot_1",
        generated_at="2026-04-06T00:00:00",
        target_country="united-states",
        total_detected=2,
        teaser_count=1,
        items=[
            TapBoardItem(
                keyword="AI phone",
                source_country="japan",
                target_countries=["united-states"],
                viral_score=92,
                priority=91.0,
                time_gap_hours=2.5,
                paywall_tier=OpportunityTier.FREE_TEASER,
                public_teaser="Japan is already moving on AI phone.",
                recommended_platforms=["x", "threads", "naver_blog"],
                recommended_angle="Localize before it becomes mainstream.",
                execution_notes=["Ship within 90 minutes", "Lead with the behavior shift"],
                publish_window=PublishWindow(
                    urgency_label="prep_now",
                    opens_in_minutes=10,
                    closes_in_minutes=90,
                    rationale="Fast window.",
                ),
                revenue_play=RevenuePlay(
                    playbook_type="sponsorship_ready",
                    pricing_hint="premium_alert_bundle",
                    cta_strategy="sell early access",
                    reasoning="High-signal item.",
                ),
            ),
            TapBoardItem(
                keyword="Robot vacuum drama",
                source_country="korea",
                target_countries=["united-states"],
                viral_score=78,
                priority=80.0,
                time_gap_hours=6.0,
                paywall_tier=OpportunityTier.PREMIUM,
                public_teaser="Korea is already reacting to robot vacuum drama.",
                recommended_platforms=["x"],
                recommended_angle="Fast local explainer.",
                execution_notes=["Publish within 3 hours"],
            ),
        ],
    )


def test_builder_creates_teaser_and_premium_offer_shapes():
    builder = TapDealRoomBuilder()
    room = builder.build(
        _sample_board(),
        request=DealRoomRequest(include_checkout=True, target_country="united-states"),
    )

    assert room.target_country == "united-states"
    assert len(room.offers) == 2
    assert room.offers[0].tier == "teaser"
    assert room.offers[0].package_tier == "premium_alert_bundle"
    assert room.offers[0].price_anchor == "$99"
    assert room.offers[0].price_value == 99.0
    assert room.offers[0].checkout_handle.startswith("stripe:premium_alert_bundle:united-states")
    assert room.offers[0].pricing_variant.endswith("baseline_v1")
    assert room.offers[1].tier == "premium"
    assert room.offers[1].checkout_handle.startswith("stripe:premium_alert_bundle:united-states")


def test_required_dependencies_include_checkout_hint():
    deps = required_tap_deal_room_dependencies()
    assert "stripe>=10.12.0" in deps


def test_builder_can_hide_public_teasers():
    builder = TapDealRoomBuilder()
    room = builder.build(
        _sample_board(),
        request=DealRoomRequest(
            target_country="united-states",
            include_public_teasers=False,
        ),
    )

    assert len(room.offers) == 1
    assert room.offers[0].tier == "premium"


def test_builder_applies_segment_pricing_experiment():
    builder = TapDealRoomBuilder()
    room = builder.build(
        _sample_board(),
        request=DealRoomRequest(
            include_checkout=True,
            target_country="united-kingdom",
            audience_segment="agency",
        ),
        funnel_stats_map={
            "aiphone::teaser": {
                "views": 25,
                "clicks": 8,
                "purchases": 0,
                "ctr": 0.32,
                "purchase_rate": 0.0,
            }
        },
        checkout_summary={"totals": {"completion_rate": 0.12}},
    )

    assert room.offers[0].price_value > 99.0
    assert room.offers[0].pricing_context["experiment_strategy"] == "recovery"
    assert room.offers[0].pricing_context["audience_multiplier"] == 1.35
    assert room.offers[0].pricing_variant.startswith("united_kingdom__agency__premium_alert_bundle__recovery")
    assert "recovery mode" in room.offers[0].learning_note.lower()


@pytest.mark.asyncio
async def test_service_builds_room_from_tap_board_snapshot():
    board = _sample_board()
    config = SimpleNamespace(country="united-states")

    with patch(
        "tap.service.build_tap_board_snapshot",
        new=AsyncMock(return_value=board),
    ):
        room = await build_tap_deal_room_snapshot(
            object(),
            config,
            DealRoomRequest(target_country="united-states", include_checkout=True),
        )

    assert room.snapshot_id == "tap_snapshot_1"
    assert room.offers[0].keyword == "AI phone"
