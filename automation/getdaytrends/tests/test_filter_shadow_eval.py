"""Tests for deterministic shadow export and fail-closed metric denominators."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filter_eval.build_shadow_eval_set import _load_rows, build_sample, write_tsv  # noqa: E402
from filter_eval.eval_filter import _metrics  # noqa: E402
from filter_eval.shadow_store import FilterShadowStore  # noqa: E402


def _insert_candidates(db_path: Path) -> None:
    store = FilterShadowStore(db_path, policy_fingerprint_value="policy-a")
    for verdict in ("allow", "block"):
        for index in range(3):
            assert store.record(
                source="x-radar",
                candidate_id=f"{verdict}-{index}",
                title=f"{verdict} 제목 {index}",
                filter_verdict=verdict,
                filter_reason="정치 제외" if verdict == "block" else "",
                observed_at=datetime(2026, 8, 10, 16 + index, tzinfo=UTC),
            )


def test_export_is_kst_bounded_deterministic_weighted_and_unlabeled(tmp_path):
    db_path = tmp_path / "shadow.sqlite3"
    _insert_candidates(db_path)
    rows = _load_rows(db_path, from_day="2026-08-11", to_day="2026-08-11")

    first = build_sample(rows, seed="fixed-seed", per_verdict=2)
    second = build_sample(rows, seed="fixed-seed", per_verdict=2)
    first_path = tmp_path / "first.tsv"
    second_path = tmp_path / "second.tsv"
    write_tsv(first_path, first)
    write_tsv(second_path, second)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert len(first) == 4
    assert {row["population_count"] for row in first} == {"3"}
    assert {row["sample_count"] for row in first} == {"2"}
    assert {row["sample_weight"] for row in first} == {"1.5"}
    assert all(row["label"] == row["labeled_by"] == row["labeled_at"] == "" for row in first)


def test_export_refuses_to_mix_policy_fingerprints():
    rows = [
        {
            "source": "x-radar",
            "candidate_id": "one",
            "filter_verdict": "allow",
            "policy_fingerprint": "policy-a",
            "title": "하나",
            "extra_text": "",
            "filter_reason": "",
            "observed_at": "2026-08-11T00:00:00+00:00",
        },
        {
            "source": "x-radar",
            "candidate_id": "two",
            "filter_verdict": "block",
            "policy_fingerprint": "policy-b",
            "title": "둘",
            "extra_text": "",
            "filter_reason": "정치 제외",
            "observed_at": "2026-08-11T00:00:00+00:00",
        },
    ]

    with pytest.raises(ValueError, match="policy_fingerprint"):
        build_sample(rows, seed="fixed-seed", per_verdict=1)


def _labeled_rows(*, block_politics: int, block_nonpolitics: int, allow_politics: int, allow_nonpolitics: int):
    rows = []
    specs = [
        ("block", "politics", block_politics, "10"),
        ("block", "not_politics", block_nonpolitics, "10"),
        ("allow", "politics", allow_politics, "20"),
        ("allow", "not_politics", allow_nonpolitics, "20"),
    ]
    for verdict, label, count, weight in specs:
        for index in range(count):
            rows.append(
                {
                    "id": f"{verdict}-{label}-{index}",
                    "source": "synthetic",
                    "title": "합성 제목",
                    "filter_verdict": verdict,
                    "filter_reason": "정치 제외" if verdict == "block" else "",
                    "sample_weight": weight,
                    "label": label,
                }
            )
    return rows


def test_weighted_metrics_match_hand_calculation():
    metrics = _metrics(
        _labeled_rows(
            block_politics=24,
            block_nonpolitics=6,
            allow_politics=6,
            allow_nonpolitics=24,
        )
    )

    assert metrics["precision"] == pytest.approx(0.8)
    assert metrics["allow_politics_leak_rate"] == pytest.approx(0.2)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["weighted_confusion"] == {
        "true_positive": 240.0,
        "false_negative": 120.0,
        "false_positive": 60.0,
        "true_negative": 480.0,
    }
    assert metrics["metric_status"] == {
        "precision": "ok",
        "allow_politics_leak_rate": "ok",
        "recall": "ok",
    }


def test_each_metric_suppresses_only_when_its_denominator_is_too_small():
    block_short = _metrics(
        _labeled_rows(
            block_politics=23,
            block_nonpolitics=6,
            allow_politics=7,
            allow_nonpolitics=23,
        )
    )
    allow_short = _metrics(
        _labeled_rows(
            block_politics=24,
            block_nonpolitics=6,
            allow_politics=5,
            allow_nonpolitics=24,
        )
    )
    politics_short = _metrics(
        _labeled_rows(
            block_politics=23,
            block_nonpolitics=7,
            allow_politics=6,
            allow_nonpolitics=24,
        )
    )

    assert block_short["precision"] is None
    assert block_short["metric_status"]["precision"] == "block_n<30"
    assert block_short["allow_politics_leak_rate"] is not None
    assert block_short["recall"] is not None

    assert allow_short["allow_politics_leak_rate"] is None
    assert allow_short["metric_status"]["allow_politics_leak_rate"] == "allow_n<30"
    assert allow_short["precision"] is not None

    assert politics_short["recall"] is None
    assert politics_short["metric_status"]["recall"] == "politics_n<30"
