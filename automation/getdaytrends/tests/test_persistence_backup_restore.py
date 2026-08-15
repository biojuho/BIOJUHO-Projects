"""Adversarial synthetic tests for 0037 backup and whole-segment restore."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from runtime_paths import (
    RUNTIME_FILE_NAMES,
    RUNTIME_MANIFEST_NAME,
    SQLITE_FILE_NAMES,
    initialize_runtime_segment,
    runtime_paths_for_root,
)
from scripts.persistence_backup import (
    BackupValidationError,
    RestoreRefusedError,
    create_backup,
    restore_backup,
    verify_backup,
)


def _create_sqlite(
    path: Path,
    *,
    table_name: str,
    observed_at_values: list[str],
) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute(
        f'CREATE TABLE "{table_name}" ('
        "id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (observed_at, payload) VALUES (?, ?)',
        [(value, f"row-{index}") for index, value in enumerate(observed_at_values)],
    )
    conn.commit()
    return conn


def _populate_runtime(
    root: Path,
    policy: Path,
    *,
    label: str,
    keep_wal_open: bool = False,
) -> tuple[dict, sqlite3.Connection | None]:
    paths = runtime_paths_for_root(root)
    main_conn = _create_sqlite(
        paths.getdaytrends_db,
        table_name="observations",
        observed_at_values=[
            "2026-08-12T00:00:00+00:00",
            "2026-08-12T00:05:00+00:00",
            "2026-08-12T00:10:00+00:00",
        ],
    )
    shadow_conn = _create_sqlite(
        paths.filter_eval_shadow,
        table_name="filter_candidates",
        observed_at_values=[
            "2026-08-12T00:01:00+00:00",
            "2026-08-12T00:06:00+00:00",
        ],
    )
    shadow_conn.close()
    for name, path in paths.runtime_files().items():
        if name not in SQLITE_FILE_NAMES:
            path.write_text(
                json.dumps({"label": label, "file": name}, ensure_ascii=False),
                encoding="utf-8",
            )
    manifest = initialize_runtime_segment(paths, policy_path=policy)
    if keep_wal_open:
        assert Path(str(paths.getdaytrends_db) + "-wal").exists()
        return manifest, main_conn
    main_conn.close()
    return manifest, None


def _known_bytes(root: Path) -> dict[str, bytes]:
    names = (*RUNTIME_FILE_NAMES, RUNTIME_MANIFEST_NAME)
    return {name: (root / name).read_bytes() for name in names if (root / name).exists()}


def _make_backup(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    policy = tmp_path / "content_filters.py"
    policy.write_text("POLICY_VERSION = '0037-test'\n", encoding="utf-8")
    source = tmp_path / "source"
    backup = tmp_path / "backups" / "segment-a"
    _, open_conn = _populate_runtime(source, policy, label="source", keep_wal_open=True)
    try:
        manifest = create_backup(source, backup, policy_path=policy)
    finally:
        assert open_conn is not None
        open_conn.close()
    return policy, source, backup, manifest


def test_wal_safe_backup_verifies_checksum_size_rows_and_observed_range(tmp_path):
    policy, _source, backup, manifest = _make_backup(tmp_path)

    verified = verify_backup(backup, policy_path=policy)

    assert verified == manifest
    main_meta = manifest["files"]["getdaytrends.db"]
    shadow_meta = manifest["files"]["filter_eval_shadow.sqlite3"]
    assert main_meta["row_count"] == 3
    assert main_meta["observed_at_min"] == "2026-08-12T00:00:00+00:00"
    assert main_meta["observed_at_max"] == "2026-08-12T00:10:00+00:00"
    assert shadow_meta["row_count"] == 2
    assert shadow_meta["observed_at_min"] == "2026-08-12T00:01:00+00:00"
    assert shadow_meta["observed_at_max"] == "2026-08-12T00:06:00+00:00"
    assert sorted(path.name for path in backup.iterdir()) == sorted(
        (*RUNTIME_FILE_NAMES, RUNTIME_MANIFEST_NAME)
    )
    assert not any(".tmp-" in path.name for path in backup.iterdir())


@pytest.mark.parametrize(
    "corruption",
    ["truncated-sqlite", "bad-sha", "bad-size", "bad-row", "bad-time", "invalid-json", "missing"],
)
def test_backup_verification_rejects_corruption_and_manifest_mismatch(tmp_path, corruption):
    policy, _source, backup, _manifest = _make_backup(tmp_path)
    manifest_path = backup / RUNTIME_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if corruption == "truncated-sqlite":
        (backup / "getdaytrends.db").write_bytes(b"not-a-sqlite-database")
    elif corruption == "bad-sha":
        manifest["files"]["reference_library.json"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "bad-size":
        manifest["files"]["reference_library.json"]["size"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "bad-row":
        manifest["files"]["getdaytrends.db"]["row_count"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "bad-time":
        manifest["files"]["getdaytrends.db"]["observed_at_min"] = "1900-01-01T00:00:00+00:00"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "invalid-json":
        (backup / "community_post_meta.json").write_text("{", encoding="utf-8")
    else:
        (backup / "viral_lead_times.json").unlink()

    with pytest.raises(BackupValidationError):
        verify_backup(backup, policy_path=policy)


def test_restore_requires_explicit_different_segment_approval_then_replaces_all_and_sidecars(tmp_path):
    policy, _source, backup, backup_manifest = _make_backup(tmp_path)
    target = tmp_path / "target"
    target_manifest, _ = _populate_runtime(target, policy, label="target")
    assert target_manifest["segment_id"] != backup_manifest["segment_id"]
    before = _known_bytes(target)

    with pytest.raises(RestoreRefusedError, match="explicit replacement approval"):
        restore_backup(
            backup,
            target,
            policy_path=policy,
            port_checker=lambda port: False,
        )
    assert _known_bytes(target) == before

    for db_name in SQLITE_FILE_NAMES:
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(target / db_name) + suffix).write_bytes(b"stale-sidecar")

    restored = restore_backup(
        backup,
        target,
        policy_path=policy,
        approve_segment_replace=True,
        port_checker=lambda port: False,
    )

    assert restored["segment_id"] == backup_manifest["segment_id"]
    assert restored["status"] == "ACTIVE"
    assert restored["data_root"] == str(target)
    for name in RUNTIME_FILE_NAMES:
        assert (target / name).read_bytes() == (backup / name).read_bytes()
    for db_name in SQLITE_FILE_NAMES:
        for suffix in ("-wal", "-shm", "-journal"):
            assert not Path(str(target / db_name) + suffix).exists()
    verify_backup(backup, policy_path=policy)


def test_restore_refuses_when_backup_directory_is_the_data_root(tmp_path):
    policy, _source, backup, _manifest = _make_backup(tmp_path)
    before = _known_bytes(backup)

    with pytest.raises(RestoreRefusedError, match="backup directory and data root must differ"):
        restore_backup(
            backup,
            backup,
            policy_path=policy,
            port_checker=lambda port: False,
        )

    assert _known_bytes(backup) == before
    verify_backup(backup, policy_path=policy)


def test_active_writer_lock_and_port_8010_each_refuse_without_changing_target(tmp_path):
    policy, _source, backup, _manifest = _make_backup(tmp_path)
    target = tmp_path / "target"
    _populate_runtime(target, policy, label="target")
    target_paths = runtime_paths_for_root(target)
    before = _known_bytes(target)

    target_paths.writer_lock.write_text(f"{os.getpid()}:test", encoding="utf-8")
    with pytest.raises(RestoreRefusedError, match="writer lock is active"):
        restore_backup(
            backup,
            target,
            policy_path=policy,
            approve_segment_replace=True,
            port_checker=lambda port: False,
        )
    assert _known_bytes(target) == before
    target_paths.writer_lock.unlink()

    checked_ports: list[int] = []

    def active_8010(port: int) -> bool:
        checked_ports.append(port)
        return port == 8010

    with pytest.raises(RestoreRefusedError, match="port 8010 is active"):
        restore_backup(
            backup,
            target,
            policy_path=policy,
            approve_segment_replace=True,
            port_checker=active_8010,
        )
    assert checked_ports == [8010]
    assert _known_bytes(target) == before


def test_corrupt_backup_fails_before_restore_staging_changes_target(tmp_path):
    policy, _source, backup, _manifest = _make_backup(tmp_path)
    target = tmp_path / "target"
    _populate_runtime(target, policy, label="target")
    before = _known_bytes(target)
    (backup / "fast_viral_snapshot.json").write_text("not-json", encoding="utf-8")

    with pytest.raises(BackupValidationError):
        restore_backup(
            backup,
            target,
            policy_path=policy,
            approve_segment_replace=True,
            port_checker=lambda port: False,
        )

    assert _known_bytes(target) == before
