"""Tests for fail-open, minimal filter shadow storage."""

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filter_eval.shadow_store import (  # noqa: E402
    FilterShadowStore,
    record_filter_candidate_fail_open,
)


def _record(store, *, source="x-radar", candidate_id="candidate-1", verdict="allow"):
    return record_filter_candidate_fail_open(
        store,
        source=source,
        candidate_id=candidate_id,
        title="국회 법안 논의" if verdict == "block" else "AI 신제품 공개",
        extra_text="최소 문맥",
        filter_verdict=verdict,
        filter_reason="정치 제외" if verdict == "block" else "",
        observed_at=datetime(2026, 8, 11, tzinfo=UTC),
    )


def test_store_records_allow_and_block_deduplicates_and_separates_policy(tmp_path):
    db_path = tmp_path / "shadow.sqlite3"
    first_policy = FilterShadowStore(db_path, policy_fingerprint_value="policy-a")
    second_policy = FilterShadowStore(db_path, policy_fingerprint_value="policy-b")

    assert _record(first_policy, verdict="allow") is True
    assert _record(first_policy, verdict="allow") is False
    assert _record(first_policy, candidate_id="candidate-2", verdict="block") is True
    assert _record(second_policy, verdict="allow") is True

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT candidate_id, filter_verdict, policy_fingerprint "
            "FROM filter_candidates ORDER BY policy_fingerprint, candidate_id"
        ).fetchall()

    assert rows == [
        ("candidate-1", "allow", "policy-a"),
        ("candidate-2", "block", "policy-a"),
        ("candidate-1", "allow", "policy-b"),
    ]


def test_schema_contains_only_the_minimum_runtime_fields(tmp_path):
    db_path = tmp_path / "shadow.sqlite3"
    assert _record(FilterShadowStore(db_path, policy_fingerprint_value="policy-a")) is True

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(filter_candidates)")]

    assert columns == [
        "observed_at",
        "source",
        "candidate_id",
        "title",
        "extra_text",
        "filter_verdict",
        "filter_reason",
        "policy_fingerprint",
    ]
    assert not ({"url", "body", "nickname", "token", "label", "labeled_by", "labeled_at"} & set(columns))


def test_write_failure_and_injected_store_exception_are_fail_open(tmp_path):
    directory_instead_of_db = tmp_path / "not-a-db"
    directory_instead_of_db.mkdir()
    broken = FilterShadowStore(directory_instead_of_db, policy_fingerprint_value="policy-a")

    class ExplodingStore:
        def record(self, **candidate):
            raise RuntimeError("forced failure")

    assert _record(broken) is False
    assert _record(ExplodingStore()) is False


def test_missing_policy_file_disables_only_shadow_recording(tmp_path):
    store = FilterShadowStore(
        tmp_path / "shadow.sqlite3",
        policy_path=tmp_path / "missing-policy.py",
    )

    assert _record(store) is False
    assert not store.db_path.exists()
