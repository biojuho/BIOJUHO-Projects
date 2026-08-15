"""0037 data-root resolution and runtime-segment fail-closed tests."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import runtime_paths as runtime_paths_module
from config import AppConfig
from fast_viral_collector import FastViralCollector
from filter_eval.shadow_store import FilterShadowStore
from runtime_paths import (
    DATA_DIR_ENV,
    PROJECT_DIR,
    RUNTIME_FILE_NAMES,
    RuntimeLockError,
    RuntimePathError,
    RuntimeWriterLock,
    initialize_runtime_segment,
    load_runtime_manifest,
    resolve_runtime_paths,
    runtime_paths_for_root,
)


def test_unset_env_preserves_all_eight_legacy_paths_byte_for_byte():
    paths = resolve_runtime_paths({})
    legacy_data = PROJECT_DIR / "data"

    assert paths.configured is False
    assert {name: os.fspath(path) for name, path in paths.runtime_files().items()} == {
        "getdaytrends.db": "data/getdaytrends.db",
        "filter_eval_shadow.sqlite3": os.fspath(legacy_data / "filter_eval_shadow.sqlite3"),
        "reference_library.json": os.fspath(legacy_data / "reference_library.json"),
        "x_exposure_observations.json": os.fspath(legacy_data / "x_exposure_observations.json"),
        "community_exposure_observations.json": os.fspath(
            legacy_data / "community_exposure_observations.json"
        ),
        "fast_viral_snapshot.json": os.fspath(legacy_data / "fast_viral_snapshot.json"),
        "community_post_meta.json": os.fspath(legacy_data / "community_post_meta.json"),
        "viral_lead_times.json": os.fspath(legacy_data / "viral_lead_times.json"),
    }

    with patch.dict(os.environ, {}, clear=True):
        assert AppConfig.from_env().db_path == "data/getdaytrends.db"


def test_unset_data_root_keeps_legacy_db_path_override():
    with patch.dict(os.environ, {"DB_PATH": "custom/legacy.db"}, clear=True):
        assert AppConfig.from_env().db_path == "custom/legacy.db"


def test_configured_absolute_root_owns_all_eight_paths_and_minimal_wiring(tmp_path):
    root = tmp_path / "durable-data"
    with patch.dict(
        os.environ,
        {DATA_DIR_ENV: str(root), "DB_PATH": "must-not-win.db"},
        clear=True,
    ):
        paths = resolve_runtime_paths()
        config = AppConfig.from_env()
        shadow = FilterShadowStore(paths.filter_eval_shadow, policy_fingerprint_value="policy")
        collector = FastViralCollector(paths.fast_viral_snapshot)

    assert paths.configured is True
    assert list(paths.runtime_files()) == list(RUNTIME_FILE_NAMES)
    assert all(path.is_absolute() and path.parent == root for path in paths.runtime_files().values())
    assert config.db_path == str(root / "getdaytrends.db")
    assert shadow.db_path == root / "filter_eval_shadow.sqlite3"
    assert collector.snapshot_path == root / "fast_viral_snapshot.json"
    assert collector.exposure_tracker.state_path == root / "community_exposure_observations.json"
    assert collector.exposure_tracker.post_meta_path == root / "community_post_meta.json"
    assert collector.lead_tracker.state_path == root / "viral_lead_times.json"


@pytest.mark.parametrize("raw_root", ["", "   ", "relative/data"])
def test_empty_and_relative_roots_fail_closed(raw_root):
    with pytest.raises(RuntimePathError):
        resolve_runtime_paths({DATA_DIR_ENV: raw_root})


def test_file_root_fails_without_creating_fallback_data(tmp_path):
    root_file = tmp_path / "not-a-directory"
    root_file.write_text("file", encoding="utf-8")

    with pytest.raises(RuntimePathError):
        resolve_runtime_paths({DATA_DIR_ENV: str(root_file)})

    assert root_file.read_text(encoding="utf-8") == "file"
    assert not (tmp_path / "data" / "getdaytrends.db").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission-mode contract")
def test_unwritable_root_fails_closed(tmp_path):
    root = tmp_path / "read-only"
    root.mkdir()
    root.chmod(0o500)
    try:
        with pytest.raises(RuntimePathError, match="not writable"):
            resolve_runtime_paths({DATA_DIR_ENV: str(root)})
    finally:
        root.chmod(0o700)


def test_segment_restarts_with_same_id_and_marks_missing_expected_file_broken(tmp_path):
    root = tmp_path / "runtime"
    policy = tmp_path / "content_filters.py"
    policy.write_text("POLICY = 'fixed'\n", encoding="utf-8")
    paths = runtime_paths_for_root(root)
    paths.fast_viral_snapshot.write_text(json.dumps({"items": []}), encoding="utf-8")

    first = initialize_runtime_segment(paths, policy_path=policy)
    second = initialize_runtime_segment(paths, policy_path=policy)

    assert first["segment_id"] == second["segment_id"]
    assert second["status"] == "ACTIVE"
    assert second["data_root"] == str(root)
    assert second["files"]["fast_viral_snapshot.json"]["size"] > 0

    paths.fast_viral_snapshot.unlink()
    with pytest.raises(RuntimePathError, match="missing or empty"):
        initialize_runtime_segment(paths, policy_path=policy)

    broken = load_runtime_manifest(paths.runtime_manifest)
    assert broken is not None
    assert broken["status"] == "BROKEN"
    assert "fast_viral_snapshot.json" in broken["broken_reason"]

    reset = initialize_runtime_segment(paths, policy_path=policy, reset=True)
    assert reset["status"] == "ACTIVE"
    assert reset["segment_id"] != first["segment_id"]
    assert reset["previous_segment_id"] == first["segment_id"]


def test_stale_lock_cleanup_does_not_remove_competing_writer_lock(tmp_path, monkeypatch):
    paths = runtime_paths_for_root(tmp_path / "runtime")
    paths.writer_lock.write_text("999999999:stale-writer", encoding="utf-8")
    competing_token = f"{os.getpid()}:competing-writer"

    def replace_stale_lock_while_its_pid_is_checked(_pid: int) -> bool:
        paths.writer_lock.write_text(competing_token, encoding="utf-8")
        return False

    monkeypatch.setattr(
        runtime_paths_module,
        "_pid_is_alive",
        replace_stale_lock_while_its_pid_is_checked,
    )

    contender = RuntimeWriterLock(paths.writer_lock)
    with pytest.raises(RuntimeLockError):
        contender.acquire()

    assert contender.token is None
    assert paths.writer_lock.read_text(encoding="utf-8") == competing_token


@pytest.mark.asyncio
async def test_configured_dashboard_lifespan_holds_single_writer_lock_and_manifest(tmp_path, monkeypatch):
    import dashboard

    paths = runtime_paths_for_root(tmp_path / "dashboard-runtime")
    monkeypatch.setattr(dashboard, "_runtime_paths", paths)
    monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_ENABLED", "false")

    async with dashboard._lifespan(dashboard.app):
        assert paths.writer_lock.exists()
        manifest = load_runtime_manifest(paths.runtime_manifest)
        assert manifest is not None
        assert manifest["status"] == "ACTIVE"
        assert manifest["data_root"] == str(paths.data_root)

    assert not paths.writer_lock.exists()
