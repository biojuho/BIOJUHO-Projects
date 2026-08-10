"""Tests for observable momentum history used by X exposure ranking."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exposure_observation_tracker import ExposureObservationTracker  # noqa: E402


def test_tracker_reports_only_observed_positive_growth_and_rank_change(tmp_path):
    path = tmp_path / "observations.json"
    tracker = ExposureObservationTracker(path)
    start = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    first = tracker.record(
        "topic:power",
        {"x_rank": 8, "original_count": 2, "source_count": 2, "comments": 10, "mentions": 1},
        observed_at=start,
        score_version="v1",
    )
    tracker.save(now=start)

    tracker = ExposureObservationTracker(path)
    second = tracker.record(
        "topic:power",
        {"x_rank": 3, "original_count": 5, "source_count": 4, "comments": 28, "mentions": 2},
        observed_at=start + timedelta(minutes=10),
        score_version="v1",
    )

    assert first["x_rank_change"] is None
    assert first["new_sources"] is None
    assert second["x_rank_change"] == 5
    assert second["new_originals"] == 3
    assert second["new_sources"] == 2
    assert second["comment_growth"] == 18
    assert second["new_mentions"] == 1
    assert first["observation_count"] == 1
    assert first["positive_rank_streak"] == 0
    assert second["observation_count"] == 2
    assert second["positive_rank_streak"] == 1

    third = tracker.record(
        "topic:power",
        {"x_rank": 1, "original_count": 5, "source_count": 4, "comments": 28, "mentions": 2},
        observed_at=start + timedelta(minutes=20),
        score_version="v1",
    )
    assert third["positive_rank_streak"] == 2


def test_tracker_does_not_turn_decreases_into_negative_growth():
    tracker = ExposureObservationTracker(None)
    now = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    tracker.record(
        "topic:quiet",
        {"original_count": 4, "source_count": 3, "comments": 20, "mentions": 2},
        observed_at=now,
        score_version="v1",
    )
    result = tracker.record(
        "topic:quiet",
        {"original_count": 2, "source_count": 2, "comments": 5, "mentions": 1},
        observed_at=now + timedelta(minutes=10),
        score_version="v1",
    )

    assert result["new_originals"] == 0
    assert result["new_sources"] == 0
    assert result["comment_growth"] == 0
    assert result["new_mentions"] == 0


def test_tracker_does_not_count_same_upstream_sample_twice():
    tracker = ExposureObservationTracker(None)
    now = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    first = tracker.record(
        "topic:cached",
        {"sample_id": "korea:1", "x_rank": 3},
        observed_at=now,
        score_version="v1",
    )
    repeated = tracker.record(
        "topic:cached",
        {"sample_id": "korea:1", "x_rank": 3},
        observed_at=now + timedelta(minutes=2),
        score_version="v1",
    )
    fresh = tracker.record(
        "topic:cached",
        {"sample_id": "korea:2", "x_rank": 2},
        observed_at=now + timedelta(minutes=4),
        score_version="v1",
    )

    assert first["sample_advanced"] is True
    assert repeated["sample_advanced"] is False
    assert repeated["observation_count"] == 1
    assert fresh["sample_advanced"] is True
    assert fresh["observation_count"] == 2
    assert fresh["x_rank_change"] == 1


def test_tracker_writes_three_post_metadata_records_once_and_atomically(tmp_path):
    observation_path = tmp_path / "observations.json"
    meta_path = tmp_path / "community_post_meta.json"
    start = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
    tracker = ExposureObservationTracker(observation_path, post_meta_path=meta_path)

    keys = [
        "community:direct:ruliweb:1",
        "community:direct:theqoo:2",
        "community:cluster:abc123",
    ]
    for index, key in enumerate(keys):
        tracker.record(
            key,
            {"comments": index, "mentions": 1, "source_count": 1},
            observed_at=start + timedelta(minutes=index),
            score_version="community-exposure-v1",
            post_meta={
                "title": f"처음 본 제목 {index}",
                "community_source": "ruliweb",
                "community_label": "루리웹",
                "source_url": f"https://example.com/{index}",
                "category": "유머",
                "kernel_axis": "unknown",
                **({"kernel_person": True} if index == 0 else {}),
            },
        )
    tracker.save(now=start + timedelta(minutes=3))

    first = json.loads(meta_path.read_text(encoding="utf-8"))
    assert list(first["posts"]) == keys
    assert first["posts"][keys[0]]["kernel_person"] is True
    assert first["posts"][keys[1]]["kernel_person"] is None
    assert not meta_path.with_suffix(".tmp").exists()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert set(observation["series"]) == set(keys)
    assert "title" not in observation["series"][keys[0]][0]

    original = first["posts"][keys[0]].copy()
    tracker = ExposureObservationTracker(observation_path, post_meta_path=meta_path)
    tracker.record(
        keys[0],
        {"comments": 99, "mentions": 2, "source_count": 1},
        observed_at=start + timedelta(hours=1),
        score_version="community-exposure-v1",
        post_meta={
            "title": "수정된 제목",
            "community_source": "ruliweb",
            "community_label": "루리웹",
            "source_url": "https://example.com/changed",
            "category": "변경",
            "kernel_axis": "live_gap",
            "kernel_person": False,
        },
    )
    tracker.save(now=start + timedelta(hours=1))

    second = json.loads(meta_path.read_text(encoding="utf-8"))
    assert second["posts"][keys[0]] == original


def test_tracker_prunes_oldest_post_metadata_over_the_cap(tmp_path, capsys):
    meta_path = tmp_path / "community_post_meta.json"
    start = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
    tracker = ExposureObservationTracker(
        None,
        post_meta_path=meta_path,
        max_meta_posts=2,
    )

    for index in range(3):
        tracker.record(
            f"community:direct:test:{index}",
            {},
            observed_at=start + timedelta(minutes=index),
            score_version="v1",
            post_meta={"title": str(index)},
        )
    tracker.save(now=start + timedelta(minutes=3))

    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert set(payload["posts"]) == {
        "community:direct:test:1",
        "community:direct:test:2",
    }
    assert "pruned 1 oldest posts" in capsys.readouterr().err
