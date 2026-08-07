"""Tests for persistent observation-based lead time measurement."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lead_time_tracker import (  # noqa: E402
    LeadTimeTracker,
    load_lead_time_store,
    normalize_lead_identity,
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


def test_normalize_pairs_ppomppu_composite_without_title_guessing():
    """IssueLink freeboard IDs are composites; native no= is the real post id."""
    assert normalize_lead_identity("ppomppu", "468400010070329") == ("ppomppu", "10070329")
    assert normalize_lead_identity("ppomppu_freeboard", "10070329") == ("ppomppu", "10070329")
    assert normalize_lead_identity("bobae", "300003426651") == ("bobae", "3426651")
    assert normalize_lead_identity("bobae_strange", "6968435") == ("bobae", "6968435")
    # Unproven composites stay untouched — do not invent pairs.
    assert normalize_lead_identity("ppomppu", "315600000725388") == ("ppomppu", "315600000725388")


def test_summarize_normalized_pairing_raises_pair_count_from_raw_split(tmp_path):
    payload = {
        "version": 1,
        "items": {
            "ppomppu_freeboard:10070329": {
                "community_source": "ppomppu_freeboard",
                "post_id": "10070329",
                "direct_first_seen_at": "2026-08-07T00:00:00+00:00",
                "aggregator_first_seen_at": None,
            },
            "ppomppu:468400010070329": {
                "community_source": "ppomppu",
                "post_id": "468400010070329",
                "direct_first_seen_at": None,
                "aggregator_first_seen_at": "2026-08-07T00:40:00+00:00",
            },
        },
    }
    raw = summarize_lead_time_store(payload, normalize_identities=False)
    norm = summarize_lead_time_store(payload, normalize_identities=True)
    assert raw["paired_count"] == 0
    assert norm["paired_count"] == 1
    assert norm["signed_lead"]["median_minutes"] == 40.0
    assert norm["by_source"][0]["community_source"] == "ppomppu"


def test_tracker_records_composite_aggregator_against_native_direct(tmp_path):
    tracker = LeadTimeTracker(tmp_path / "lead.json")
    start = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    tracker.record_observations(
        [{"id": "10070329", "community_source": "ppomppu_freeboard"}],
        [],
        observed_at=start,
    )
    tracker.record_observations(
        [],
        [{"id": "468400010070329", "community_source": "ppomppu"}],
        observed_at=start + timedelta(minutes=15),
    )
    measured = tracker.metrics_for({"id": "10070329", "community_source": "ppomppu_freeboard"})
    assert measured["lead_status"] == "measured"
    assert measured["lead_minutes"] == 15.0
    assert measured["lead_identity"] == "ppomppu:10070329"

