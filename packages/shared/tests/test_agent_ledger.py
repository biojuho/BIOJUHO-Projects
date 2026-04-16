"""Unit tests for shared.telemetry.agent_ledger.

Covers:
  1. build_ledger_entry  — schema shape, field types, rounding, defaults
  2. write_ledger_entry  — path layout, roundtrip, idempotency
  3. Failure modes       — non-writable root, naive datetimes, empty run_id

The ledger is an observer contract: these tests freeze the v1 schema so
future changes stay additive (new optional fields only).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.telemetry.agent_ledger import (
    LEDGER_SCHEMA_VERSION,
    build_ledger_entry,
    write_ledger_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ledger_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ledger writes to a tmp directory via AGENT_LEDGER_ROOT env override."""
    root = tmp_path / "ledger"
    monkeypatch.setenv("AGENT_LEDGER_ROOT", str(root))
    return root


@pytest.fixture
def sample_times() -> tuple[datetime, datetime]:
    started = datetime(2026, 4, 16, 6, 0, 0, tzinfo=UTC)
    finished = started + timedelta(seconds=47, milliseconds=300)
    return started, finished


# ===========================================================================
# 1. build_ledger_entry — schema contract
# ===========================================================================


class TestBuildEntry:
    def test_minimal_entry_has_all_v1_fields(self, sample_times: tuple[datetime, datetime]) -> None:
        started, finished = sample_times
        entry = build_ledger_entry(
            agent="test-agent",
            run_id="abc12345-def6-7890",
            started_at=started,
            finished_at=finished,
            status="success",
        )
        expected_keys = {
            "schema_version",
            "agent",
            "run_id",
            "started_at",
            "finished_at",
            "duration_s",
            "status",
            "cost_usd",
            "tokens_input",
            "tokens_output",
            "outcomes",
            "metadata",
        }
        assert set(entry.keys()) == expected_keys
        assert entry["schema_version"] == LEDGER_SCHEMA_VERSION

    def test_duration_computed_from_timestamps(self, sample_times: tuple[datetime, datetime]) -> None:
        started, finished = sample_times
        entry = build_ledger_entry(
            agent="a", run_id="r", started_at=started, finished_at=finished, status="success"
        )
        assert entry["duration_s"] == pytest.approx(47.3, abs=0.001)

    def test_cost_rounded_to_six_decimals(self, sample_times: tuple[datetime, datetime]) -> None:
        started, finished = sample_times
        entry = build_ledger_entry(
            agent="a",
            run_id="r",
            started_at=started,
            finished_at=finished,
            status="success",
            cost_usd=0.123456789,
        )
        assert entry["cost_usd"] == 0.123457

    def test_defaults_are_safe(self, sample_times: tuple[datetime, datetime]) -> None:
        started, finished = sample_times
        entry = build_ledger_entry(
            agent="a", run_id="r", started_at=started, finished_at=finished, status="success"
        )
        assert entry["cost_usd"] == 0.0
        assert entry["tokens_input"] == 0
        assert entry["tokens_output"] == 0
        assert entry["outcomes"] == {}
        assert entry["metadata"] == {}

    def test_outcomes_and_metadata_copied_not_referenced(
        self, sample_times: tuple[datetime, datetime]
    ) -> None:
        started, finished = sample_times
        outcomes = {"notion_ok": True}
        metadata = {"window": "morning"}
        entry = build_ledger_entry(
            agent="a",
            run_id="r",
            started_at=started,
            finished_at=finished,
            status="success",
            outcomes=outcomes,
            metadata=metadata,
        )
        outcomes["notion_ok"] = False
        metadata["window"] = "evening"
        assert entry["outcomes"] == {"notion_ok": True}
        assert entry["metadata"] == {"window": "morning"}

    def test_naive_datetime_treated_as_utc(self) -> None:
        naive_start = datetime(2026, 4, 16, 6, 0, 0)
        naive_end = datetime(2026, 4, 16, 6, 0, 10)
        entry = build_ledger_entry(
            agent="a",
            run_id="r",
            started_at=naive_start,
            finished_at=naive_end,
            status="success",
        )
        assert entry["started_at"].endswith("+00:00")
        assert entry["duration_s"] == 10.0

    def test_non_utc_timezone_converted_to_utc(self) -> None:
        kst = timezone(timedelta(hours=9))
        started = datetime(2026, 4, 16, 15, 0, 0, tzinfo=kst)
        finished = datetime(2026, 4, 16, 15, 0, 5, tzinfo=kst)
        entry = build_ledger_entry(
            agent="a", run_id="r", started_at=started, finished_at=finished, status="success"
        )
        assert "+00:00" in entry["started_at"]
        assert entry["started_at"].startswith("2026-04-16T06:00:00")

    def test_empty_run_id_becomes_unknown(self, sample_times: tuple[datetime, datetime]) -> None:
        started, finished = sample_times
        entry = build_ledger_entry(
            agent="a", run_id="", started_at=started, finished_at=finished, status="success"
        )
        assert entry["run_id"] == "unknown"


# ===========================================================================
# 2. write_ledger_entry — filesystem roundtrip
# ===========================================================================


class TestWriteEntry:
    def test_writes_file_under_agent_subdir(
        self, ledger_root: Path, sample_times: tuple[datetime, datetime]
    ) -> None:
        started, finished = sample_times
        path = write_ledger_entry(
            agent="dailynews-morning",
            run_id="abcdef12-3456",
            started_at=started,
            finished_at=finished,
            status="success",
            cost_usd=0.15,
            outcomes={"notion_ok": True},
            metadata={"window": "morning"},
        )
        assert path is not None
        assert path.exists()
        assert path.parent == ledger_root / "dailynews-morning"
        assert path.name == "2026-04-16_abcdef12.json"

    def test_file_contains_valid_json_matching_build(
        self, ledger_root: Path, sample_times: tuple[datetime, datetime]
    ) -> None:
        started, finished = sample_times
        path = write_ledger_entry(
            agent="a",
            run_id="run-xyz-1234567890",
            started_at=started,
            finished_at=finished,
            status="partial_failed",
            cost_usd=0.07,
            tokens_input=1200,
            tokens_output=450,
            outcomes={"categories_success": 3, "categories_failed": 1},
            metadata={"target_db": "db_xyz"},
        )
        assert path is not None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["agent"] == "a"
        assert loaded["status"] == "partial_failed"
        assert loaded["cost_usd"] == 0.07
        assert loaded["tokens_input"] == 1200
        assert loaded["tokens_output"] == 450
        assert loaded["outcomes"]["categories_failed"] == 1
        assert loaded["metadata"]["target_db"] == "db_xyz"

    def test_overwrite_same_run_same_day_is_idempotent(
        self, ledger_root: Path, sample_times: tuple[datetime, datetime]
    ) -> None:
        started, finished = sample_times
        path1 = write_ledger_entry(
            agent="a", run_id="same", started_at=started, finished_at=finished, status="success"
        )
        path2 = write_ledger_entry(
            agent="a",
            run_id="same",
            started_at=started,
            finished_at=finished,
            status="failed",
        )
        assert path1 == path2
        loaded = json.loads(path2.read_text(encoding="utf-8"))
        assert loaded["status"] == "failed"

    def test_unicode_metadata_preserved(
        self, ledger_root: Path, sample_times: tuple[datetime, datetime]
    ) -> None:
        started, finished = sample_times
        path = write_ledger_entry(
            agent="getdaytrends",
            run_id="r",
            started_at=started,
            finished_at=finished,
            status="success",
            metadata={"note": "한글 메모 ✓"},
        )
        assert path is not None
        raw = path.read_text(encoding="utf-8")
        assert "한글 메모" in raw


# ===========================================================================
# 3. Failure modes — must never raise
# ===========================================================================


class TestFailsafe:
    def test_unwritable_root_returns_none_not_raise(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        sample_times: tuple[datetime, datetime],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Point the root at a path that can't be created (file-as-parent trick)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        monkeypatch.setenv("AGENT_LEDGER_ROOT", str(blocker / "ledger"))
        started, finished = sample_times
        result = write_ledger_entry(
            agent="a", run_id="r", started_at=started, finished_at=finished, status="success"
        )
        assert result is None
        captured = capsys.readouterr()
        assert "agent_ledger" in captured.err
