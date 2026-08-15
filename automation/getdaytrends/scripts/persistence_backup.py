#!/usr/bin/env python3
"""Verified local backup and whole-segment restore for GetDayTrends runtime data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

MODULE_ROOT = str(Path(__file__).resolve().parents[1])
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_paths import (  # noqa: E402
    DEFAULT_POLICY_PATH,
    RUNTIME_FILE_NAMES,
    RUNTIME_MANIFEST_NAME,
    SQLITE_FILE_NAMES,
    RuntimeLockError,
    RuntimePathError,
    RuntimeWriterLock,
    atomic_write_bytes,
    atomic_write_json,
    initialize_runtime_segment,
    inspect_runtime_files,
    load_runtime_manifest,
    runtime_paths_for_root,
    writer_lock_is_active,
)

SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


class PersistenceError(RuntimeError):
    """Base error for verified backup and restore operations."""


class BackupValidationError(PersistenceError):
    """A backup or staged restore failed integrity/provenance validation."""


class RestoreRefusedError(PersistenceError):
    """Restore was refused before any runtime file replacement."""


def _utc_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _policy_fingerprint(policy_path: Path) -> str:
    try:
        return _sha256_file(policy_path)
    except OSError as exc:
        raise BackupValidationError(f"cannot fingerprint policy file {policy_path}: {exc}") from exc


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _backup_sqlite(source: Path, destination: Path) -> None:
    """Create a WAL-consistent SQLite snapshot via Connection.backup()."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    try:
        with (
            sqlite3.connect(source_uri, uri=True, timeout=10.0) as source_conn,
            sqlite3.connect(destination, timeout=10.0) as destination_conn,
        ):
            source_conn.backup(destination_conn)
            destination_conn.commit()
            # ``backup()`` copies the source page header, including WAL
            # journal mode. A portable offline snapshot must not create
            # fresh -wal/-shm files merely by being verified or restored.
            destination_conn.execute("PRAGMA journal_mode=DELETE").fetchone()
            integrity = [str(row[0]) for row in destination_conn.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise BackupValidationError(
                    f"SQLite backup integrity_check failed for {source}: {integrity}"
                )
    except (OSError, sqlite3.Error) as exc:
        raise BackupValidationError(f"cannot back up SQLite file {source}: {exc}") from exc
    _fsync_file(destination)
    _fsync_directory(destination.parent)


def _copy_json_snapshot(source: Path, destination: Path) -> None:
    try:
        raw = source.read_bytes()
        json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupValidationError(f"cannot parse JSON source {source}: {exc}") from exc
    atomic_write_bytes(destination, raw)


def _require_complete_files(root: Path) -> dict[str, dict[str, Any]]:
    try:
        metadata: dict[str, dict[str, Any]] = inspect_runtime_files(
            runtime_paths_for_root(root, validate=False)
        )
    except RuntimePathError as exc:
        raise BackupValidationError(str(exc)) from exc
    missing_or_empty = [
        name
        for name, item in metadata.items()
        if not bool(item.get("exists")) or int(item.get("size") or 0) == 0
    ]
    if missing_or_empty:
        raise BackupValidationError(
            "runtime segment is incomplete; missing or empty files: "
            + ", ".join(sorted(missing_or_empty))
        )
    return metadata


def _load_backup_manifest(directory: Path) -> dict[str, Any]:
    try:
        manifest: dict[str, Any] | None = load_runtime_manifest(
            directory / RUNTIME_MANIFEST_NAME
        )
    except RuntimePathError as exc:
        raise BackupValidationError(str(exc)) from exc
    if manifest is None:
        raise BackupValidationError(f"backup manifest is missing: {directory / RUNTIME_MANIFEST_NAME}")
    return manifest


def _verify_payload_files(directory: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if manifest.get("format_version") != 1:
        raise BackupValidationError("unsupported runtime segment manifest version")
    if manifest.get("target_files") != list(RUNTIME_FILE_NAMES):
        raise BackupValidationError("backup target file list does not match the 0037 contract")
    if not str(manifest.get("segment_id") or "").strip():
        raise BackupValidationError("backup segment_id is missing")
    expected_files = manifest.get("files")
    if not isinstance(expected_files, dict) or set(expected_files) != set(RUNTIME_FILE_NAMES):
        raise BackupValidationError("backup file metadata is incomplete")
    actual_files = _require_complete_files(directory)
    mismatches = [
        name
        for name in RUNTIME_FILE_NAMES
        if actual_files[name] != expected_files.get(name)
    ]
    if mismatches:
        raise BackupValidationError(
            "backup checksum/size/row/time verification failed: " + ", ".join(mismatches)
        )
    return actual_files


def verify_backup(
    backup_dir: Path | str,
    *,
    policy_path: Path | str | None = DEFAULT_POLICY_PATH,
) -> dict[str, Any]:
    """Reopen and remeasure every backup file against its manifest."""
    directory = Path(backup_dir).resolve(strict=False)
    if not directory.is_dir():
        raise BackupValidationError(f"backup directory does not exist: {directory}")
    manifest = _load_backup_manifest(directory)
    if manifest.get("manifest_type") != "getdaytrends-runtime-backup":
        raise BackupValidationError("manifest is not a completed GetDayTrends runtime backup")
    if manifest.get("status") != "COMPLETE":
        raise BackupValidationError("backup manifest status is not COMPLETE")
    if policy_path is not None:
        expected_policy = _policy_fingerprint(Path(policy_path))
        if manifest.get("policy_fingerprint") != expected_policy:
            raise BackupValidationError("backup policy fingerprint does not match the requested policy")
    _verify_payload_files(directory, manifest)
    return manifest


def create_backup(
    data_root: Path | str,
    backup_dir: Path | str,
    *,
    policy_path: Path | str = DEFAULT_POLICY_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create and atomically publish a fully verified one-segment backup."""
    try:
        source_paths = runtime_paths_for_root(data_root, validate=True)
    except RuntimePathError as exc:
        raise BackupValidationError(str(exc)) from exc
    destination = Path(backup_dir)
    if not destination.is_absolute():
        raise BackupValidationError(f"backup directory must be absolute: {destination}")
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise BackupValidationError(f"backup destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    policy = Path(policy_path).resolve(strict=False)
    _require_complete_files(source_paths.data_root)
    try:
        source_manifest = initialize_runtime_segment(source_paths, policy_path=policy, now=now)
    except RuntimePathError as exc:
        raise BackupValidationError(str(exc)) from exc

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-{uuid.uuid4().hex}-",
            dir=destination.parent,
        )
    )
    published = False
    try:
        for name, source in source_paths.runtime_files().items():
            target = staging / name
            if name in SQLITE_FILE_NAMES:
                _backup_sqlite(source, target)
            else:
                _copy_json_snapshot(source, target)

        staged_metadata = _require_complete_files(staging)
        timestamp = _utc_iso(now)
        manifest: dict[str, Any] = {
            "format_version": 1,
            "manifest_type": "getdaytrends-runtime-backup",
            "status": "COMPLETE",
            "segment_id": source_manifest["segment_id"],
            "started_at": source_manifest["started_at"],
            "backup_created_at": timestamp,
            "updated_at": timestamp,
            "data_root": str(source_paths.data_root),
            "target_files": list(RUNTIME_FILE_NAMES),
            "policy_fingerprint": _policy_fingerprint(policy),
            "files": staged_metadata,
        }
        atomic_write_json(staging / RUNTIME_MANIFEST_NAME, manifest)
        verify_backup(staging, policy_path=policy)
        _fsync_directory(staging)
        os.replace(staging, destination)
        published = True
        _fsync_directory(destination.parent)
        return verify_backup(destination, policy_path=policy)
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)


def is_tcp_port_active(port: int) -> bool:
    """Return True if a local listener accepts a TCP connection on the port."""
    for host, family in (("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6)):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as client:
                client.settimeout(0.15)
                if client.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def _current_segment_requires_approval(
    target_paths: Any,
    backup_segment_id: str,
    *,
    approve_segment_replace: bool,
) -> None:
    try:
        current = load_runtime_manifest(target_paths.runtime_manifest)
    except RuntimePathError as exc:
        raise RestoreRefusedError(str(exc)) from exc
    current_files_exist = any(path.exists() for path in target_paths.runtime_files().values())
    if current is None:
        if current_files_exist and not approve_segment_replace:
            raise RestoreRefusedError(
                "target has runtime files but no segment manifest; explicit replacement approval is required"
            )
        return
    current_segment_id = str(current.get("segment_id") or "")
    is_broken = current.get("status") == "BROKEN"
    if (is_broken or current_segment_id != backup_segment_id) and not approve_segment_replace:
        raise RestoreRefusedError(
            "backup and target segments differ or target is BROKEN; "
            "explicit replacement approval is required"
        )


def _sidecar_paths(root: Path) -> list[Path]:
    return [
        Path(str(root / db_name) + suffix)
        for db_name in SQLITE_FILE_NAMES
        for suffix in SIDECAR_SUFFIXES
    ]


def _copy_backup_to_restore_staging(
    backup_dir: Path,
    staging: Path,
    manifest: dict[str, Any],
    target_root: Path,
    *,
    now: datetime | None,
) -> dict[str, Any]:
    for name in RUNTIME_FILE_NAMES:
        atomic_write_bytes(staging / name, (backup_dir / name).read_bytes())
    runtime_manifest = dict(manifest)
    timestamp = _utc_iso(now)
    runtime_manifest.update(
        {
            "manifest_type": "getdaytrends-runtime-segment",
            "status": "ACTIVE",
            "data_root": str(target_root),
            "restored_at": timestamp,
            "updated_at": timestamp,
        }
    )
    runtime_manifest.pop("backup_created_at", None)
    atomic_write_json(staging / RUNTIME_MANIFEST_NAME, runtime_manifest)
    _verify_payload_files(staging, runtime_manifest)
    return runtime_manifest


def restore_backup(
    backup_dir: Path | str,
    data_root: Path | str,
    *,
    policy_path: Path | str = DEFAULT_POLICY_PATH,
    approve_segment_replace: bool = False,
    port: int = 8010,
    port_checker: Callable[[int], bool] = is_tcp_port_active,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate in staging, then replace all files without row-level merging."""
    backup = Path(backup_dir).resolve(strict=False)
    policy = Path(policy_path).resolve(strict=False)
    try:
        target_paths = runtime_paths_for_root(data_root, validate=False)
    except RuntimePathError as exc:
        raise RestoreRefusedError(str(exc)) from exc
    if backup == target_paths.data_root:
        raise RestoreRefusedError("backup directory and data root must differ")
    manifest = verify_backup(backup, policy_path=policy)
    backup_segment_id = str(manifest["segment_id"])

    if writer_lock_is_active(target_paths.writer_lock):
        raise RestoreRefusedError(f"runtime writer lock is active: {target_paths.writer_lock}")
    try:
        port_active = port_checker(port)
    except Exception as exc:
        raise RestoreRefusedError(f"cannot prove port {port} is inactive: {exc}") from exc
    if port_active:
        raise RestoreRefusedError(f"restore refused while local port {port} is active")
    _current_segment_requires_approval(
        target_paths,
        backup_segment_id,
        approve_segment_replace=approve_segment_replace,
    )

    try:
        target_paths = runtime_paths_for_root(data_root, validate=True)
    except RuntimePathError as exc:
        raise RestoreRefusedError(str(exc)) from exc
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{target_paths.data_root.name}.restore-staging-{uuid.uuid4().hex}-",
            dir=target_paths.data_root.parent,
        )
    )
    rollback = Path(
        tempfile.mkdtemp(
            prefix=f".{target_paths.data_root.name}.restore-rollback-{uuid.uuid4().hex}-",
            dir=target_paths.data_root.parent,
        )
    )
    moved_originals: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    lock = RuntimeWriterLock(target_paths.writer_lock)
    try:
        runtime_manifest = _copy_backup_to_restore_staging(
            backup,
            staging,
            manifest,
            target_paths.data_root,
            now=now,
        )
        try:
            lock.acquire()
        except RuntimeLockError as exc:
            raise RestoreRefusedError(str(exc)) from exc
        if port_checker(port):
            raise RestoreRefusedError(f"restore refused while local port {port} is active")
        _current_segment_requires_approval(
            target_paths,
            backup_segment_id,
            approve_segment_replace=approve_segment_replace,
        )

        replacement_targets = [
            *target_paths.runtime_files().values(),
            target_paths.runtime_manifest,
        ]
        old_paths = [*replacement_targets, *_sidecar_paths(target_paths.data_root)]
        try:
            for old_path in old_paths:
                if old_path.exists():
                    rollback_path = rollback / old_path.name
                    os.replace(old_path, rollback_path)
                    moved_originals.append((rollback_path, old_path))
            for name in (*RUNTIME_FILE_NAMES, RUNTIME_MANIFEST_NAME):
                staged_path = staging / name
                target_path = target_paths.data_root / name
                os.replace(staged_path, target_path)
                installed.append(target_path)
            _fsync_directory(target_paths.data_root)
            installed_manifest = _load_backup_manifest(target_paths.data_root)
            _verify_payload_files(target_paths.data_root, installed_manifest)
            if installed_manifest != runtime_manifest:
                raise BackupValidationError("installed runtime manifest differs from verified staging")
            remaining_sidecars = [path for path in _sidecar_paths(target_paths.data_root) if path.exists()]
            if remaining_sidecars:
                raise BackupValidationError(
                    "stale SQLite sidecars remain after restore: "
                    + ", ".join(path.name for path in remaining_sidecars)
                )
        except Exception:
            for target_path in installed:
                target_path.unlink(missing_ok=True)
            for rollback_path, old_path in reversed(moved_originals):
                if rollback_path.exists():
                    os.replace(rollback_path, old_path)
            _fsync_directory(target_paths.data_root)
            raise
        shutil.rmtree(rollback)
        return runtime_manifest
    finally:
        lock.release()
        if staging.exists():
            shutil.rmtree(staging)
        if rollback.exists():
            shutil.rmtree(rollback)


def initialize_segment(
    data_root: Path | str,
    *,
    policy_path: Path | str = DEFAULT_POLICY_PATH,
    reset: bool = False,
) -> dict[str, Any]:
    try:
        paths = runtime_paths_for_root(data_root, validate=True)
        with RuntimeWriterLock(paths.writer_lock):
            result: dict[str, Any] = initialize_runtime_segment(
                paths,
                policy_path=Path(policy_path).resolve(strict=False),
                reset=reset,
            )
            return result
    except (RuntimeLockError, RuntimePathError) as exc:
        raise PersistenceError(str(exc)) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="create a verified local backup")
    backup_parser.add_argument("--data-root", type=Path, required=True)
    backup_parser.add_argument("--backup-dir", type=Path, required=True)
    backup_parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)

    verify_parser = subparsers.add_parser("verify", help="verify an existing backup")
    verify_parser.add_argument("--backup-dir", type=Path, required=True)
    verify_parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)

    restore_parser = subparsers.add_parser("restore", help="restore one whole verified segment")
    restore_parser.add_argument("--backup-dir", type=Path, required=True)
    restore_parser.add_argument("--data-root", type=Path, required=True)
    restore_parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)
    restore_parser.add_argument("--port", type=int, default=8010)
    restore_parser.add_argument("--approve-segment-replace", action="store_true")

    segment_parser = subparsers.add_parser("segment-init", help="initialize or explicitly reset a segment")
    segment_parser.add_argument("--data-root", type=Path, required=True)
    segment_parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)
    segment_parser.add_argument("--reset", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "backup":
            result = create_backup(args.data_root, args.backup_dir, policy_path=args.policy_path)
        elif args.command == "verify":
            result = verify_backup(args.backup_dir, policy_path=args.policy_path)
        elif args.command == "restore":
            result = restore_backup(
                args.backup_dir,
                args.data_root,
                policy_path=args.policy_path,
                approve_segment_replace=args.approve_segment_replace,
                port=args.port,
            )
        else:
            result = initialize_segment(
                args.data_root,
                policy_path=args.policy_path,
                reset=args.reset,
            )
    except (PersistenceError, RuntimePathError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
