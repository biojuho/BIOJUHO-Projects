"""Tests for persistent observation-based lead time measurement."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lead_time_tracker import (  # noqa: E402
    LeadTimeTracker,
    load_lead_time_store,
    summarize_lead_time_store,
)


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


def test_summarize_includes_negative_leads_and_does_not_require_write(tmp_path):
    """Signed summary keeps late detections; loading is read-only."""
    path = tmp_path / "viral_lead_times.json"
    payload = {
        "version": 1,
        "updated_at": "2026-08-07T00:00:00+00:00",
        "items": {
            "ruliweb:1": {
                "community_source": "ruliweb",
                "post_id": "1",
                "direct_first_seen_at": "2026-08-07T00:00:00+00:00",
                "aggregator_first_seen_at": "2026-08-07T01:00:00+00:00",
            },
            "theqoo:2": {
                "community_source": "theqoo",
                "post_id": "2",
                "direct_first_seen_at": "2026-08-07T02:00:00+00:00",
                "aggregator_first_seen_at": "2026-08-07T01:00:00+00:00",
            },
            "dogdrip:3": {
                "community_source": "dogdrip",
                "post_id": "3",
                "direct_first_seen_at": "2026-08-07T00:00:00+00:00",
                "aggregator_first_seen_at": None,
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    loaded = load_lead_time_store(path)
    summary = summarize_lead_time_store(loaded)

    assert path.read_text(encoding="utf-8") == before
    assert summary["record_count"] == 3
    assert summary["paired_count"] == 2
    assert summary["status_counts"]["measured"] == 1
    assert summary["status_counts"]["aggregator_first"] == 1
    assert summary["status_counts"]["awaiting_aggregator"] == 1
    assert summary["signed_lead"]["negative_count"] == 1
    assert summary["signed_lead"]["negative_share_pct"] == 50.0
    assert summary["signed_lead"]["positive_count"] == 1
    assert summary["signed_lead"]["median_minutes"] == 0.0  # (+60 and -60)
    assert summary["evidence_grade"] == "insufficient"  # paired n < 10

