"""Tests for the TAP product feed scaffolding."""

from tap.detector import ArbitrageOpportunity
from tap.product_feed import OpportunityTier, TapBoardBuilder, empty_tap_board, required_tap_product_dependencies


def _make_opportunity(
    keyword: str,
    *,
    source_country: str = "korea",
    target_countries: list[str] | None = None,
    viral_score: int = 80,
    priority: float = 70.0,
    time_gap_hours: float = 2.5,
) -> ArbitrageOpportunity:
    return ArbitrageOpportunity(
        keyword=keyword,
        source_country=source_country,
        target_countries=target_countries or ["united-states"],
        viral_score=viral_score,
        priority=priority,
        time_gap_hours=time_gap_hours,
    )


class TestTapBoardBuilder:
    def test_build_assigns_teaser_then_premium(self):
        builder = TapBoardBuilder()
        board = builder.build(
            [
                _make_opportunity("Trend A", priority=95.0),
                _make_opportunity("Trend B", priority=70.0),
            ],
            target_country="united-states",
            teaser_count=1,
        )

        assert board.total_detected == 2
        assert len(board.items) == 2
        assert board.items[0].paywall_tier is OpportunityTier.FREE_TEASER
        assert board.items[1].paywall_tier is OpportunityTier.PREMIUM

    def test_build_filters_for_target_country(self):
        builder = TapBoardBuilder()
        board = builder.build(
            [
                _make_opportunity("US gap", target_countries=["united-states"]),
                _make_opportunity("JP gap", target_countries=["japan"]),
            ],
            target_country="united-states",
        )

        assert board.total_detected == 1
        assert [item.keyword for item in board.items] == ["US gap"]

    def test_high_score_recommends_blog_distribution(self):
        builder = TapBoardBuilder()
        board = builder.build(
            [_make_opportunity("Premium signal", viral_score=91, priority=91.0)],
            target_country="united-states",
        )

        item = board.items[0]
        assert "naver_blog" in item.recommended_platforms
        assert item.publish_window is not None
        assert item.revenue_play is not None


def test_empty_board_is_schema_stable():
    board = empty_tap_board(target_country="united-states", teaser_count=2)
    payload = board.to_dict()

    assert payload["target_country"] == "united-states"
    assert payload["teaser_count"] == 2
    assert payload["items"] == []


def test_dependency_hints_are_exposed():
    deps = required_tap_product_dependencies()

    assert "rapidfuzz>=3.9.0" in deps
    assert "redis>=5.0.0" in deps


def test_board_can_be_projected_for_cached_delivery():
    builder = TapBoardBuilder()
    board = builder.build(
        [
            _make_opportunity("Trend A", priority=95.0),
            _make_opportunity("Trend B", priority=70.0),
            _make_opportunity("Trend C", priority=65.0),
        ],
        target_country="united-states",
        teaser_count=2,
    )

    projected = board.clone_for_delivery(limit=2, teaser_count=1, delivery_mode="cached")

    assert len(projected.items) == 2
    assert projected.delivery_mode == "cached"
    assert projected.items[0].paywall_tier is OpportunityTier.FREE_TEASER
    assert projected.items[1].paywall_tier is OpportunityTier.PREMIUM
