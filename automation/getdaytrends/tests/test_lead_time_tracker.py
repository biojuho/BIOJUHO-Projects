"""Tests for persistent observation-based lead time measurement."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lead_time_tracker import LeadTimeTracker  # noqa: E402


def _item(post_id: str = "123"):
    return {"id": post_id, "community_source": "fmkorea"}


def test_tracker_persists_and_measures_only_direct_before_aggregator(tmp_path):
    state_path = tmp_path / "lead.json"
    tracker = LeadTimeTracker(state_path)
    start = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    tracker.record_observations([_item()], [], observed_at=start)

    waiting = tracker.metrics_for(_item())
    assert waiting["lead_status"] == "awaiting_aggregator"
    assert waiting["lead_minutes"] is None

    tracker = LeadTimeTracker(state_path)
    tracker.record_observations([], [_item()], observed_at=start + timedelta(minutes=7, seconds=30))
    measured = tracker.metrics_for(_item())
    assert measured["lead_status"] == "measured"
    assert measured["lead_seconds"] == 450
    assert measured["lead_minutes"] == 7.5


def test_tracker_does_not_claim_lead_for_same_poll_or_aggregator_first(tmp_path):
    tracker = LeadTimeTracker(tmp_path / "lead.json")
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    tracker.record_observations([_item("same")], [_item("same")], observed_at=now)
    tracker.record_observations([], [_item("late")], observed_at=now)
    tracker.record_observations([_item("late")], [], observed_at=now + timedelta(minutes=5))

    assert tracker.metrics_for(_item("same"))["lead_status"] == "same_poll"
    assert tracker.metrics_for(_item("same"))["lead_minutes"] is None
    assert tracker.metrics_for(_item("late"))["lead_status"] == "aggregator_first"
    assert tracker.metrics_for(_item("late"))["lead_minutes"] is None
