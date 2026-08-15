"""Runtime data-root, segment-manifest, and writer-lock contracts.

The legacy layout remains untouched when ``GETDAYTRENDS_DATA_DIR`` is absent.
When it is present, every mutable observation file is resolved below one
validated absolute directory and invalid roots fail before a store can fall
back to the source worktree.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

DATA_DIR_ENV = "GETDAYTRENDS_DATA_DIR"
PROJECT_DIR = Path(__file__).resolve().parent
LEGACY_DATA_DIR = PROJECT_DIR / "data"
DEFAULT_POLICY_PATH = PROJECT_DIR / "content_filters.py"

RUNTIME_FILE_NAMES = (
    "getdaytrends.db",
    "filter_eval_shadow.sqlite3",
    "reference_library.json",
    "x_exposure_observations.json",
    "community_exposure_observations.json",
    "fast_viral_snapshot.json",
    "community_post_meta.json",
    "viral_lead_times.json",
)
SQLITE_FILE_NAMES = frozenset({"getdaytrends.db", "filter_eval_shadow.sqlite3"})
JSON_FILE_NAMES = frozenset(set(RUNTIME_FILE_NAMES) - SQLITE_FILE_NAMES)
RUNTIME_MANIFEST_NAME = "runtime-segment.json"
WRITER_LOCK_NAME = "getdaytrends.lock"


class RuntimePathError(RuntimeError):
    """The configured runtime data contract is invalid or broken."""


class RuntimeLockError(RuntimeError):
    """The single-writer runtime lock could not be acquired safely."""


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved paths for every mutable GetDayTrends observation file."""

    configured: bool
    data_root: Path
    getdaytrends_db: Path
    filter_eval_shadow: Path
    reference_library: Path
    x_exposure_observations: Path
    community_exposure_observations: Path
    fast_viral_snapshot: Path
    community_post_meta: Path
    viral_lead_times: Path
    runtime_manifest: Path
    writer_lock: Path

    def runtime_files(self) -> dict[str, Path]:
        return {
            "getdaytrends.db": self.getdaytrends_db,
            "filter_eval_shadow.sqlite3": self.filter_eval_shadow,
            "reference_library.json": self.reference_library,
            "x_exposure_observations.json": self.x_exposure_observations,
            "community_exposure_observations.json": self.community_exposure_observations,
            "fast_viral_snapshot.json": self.fast_viral_snapshot,
            "community_post_meta.json": self.community_post_meta,
            "viral_lead_times.json": self.viral_lead_times,
        }


def _legacy_paths() -> RuntimePaths:
    """Return the exact pre-0037 per-consumer defaults without I/O."""
    return RuntimePaths(
        configured=False,
        data_root=LEGACY_DATA_DIR,
        # AppConfig's historical default is deliberately CWD-relative.
        getdaytrends_db=Path("data/getdaytrends.db"),
        filter_eval_shadow=LEGACY_DATA_DIR / "filter_eval_shadow.sqlite3",
        reference_library=LEGACY_DATA_DIR / "reference_library.json",
        x_exposure_observations=LEGACY_DATA_DIR / "x_exposure_observations.json",
        community_exposure_observations=LEGACY_DATA_DIR / "community_exposure_observations.json",
        fast_viral_snapshot=LEGACY_DATA_DIR / "fast_viral_snapshot.json",
        community_post_meta=LEGACY_DATA_DIR / "community_post_meta.json",
        viral_lead_times=LEGACY_DATA_DIR / "viral_lead_times.json",
        runtime_manifest=LEGACY_DATA_DIR / RUNTIME_MANIFEST_NAME,
        writer_lock=Path(__file__).parent / "data" / WRITER_LOCK_NAME,
    )


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _probe_writable_directory(root: Path) -> None:
    probe_path: Path | None = None
    try:
        fd, raw_path = tempfile.mkstemp(prefix=".getdaytrends-write-probe-", dir=root)
        probe_path = Path(raw_path)
        try:
            os.write(fd, b"write-probe")
            os.fsync(fd)
        finally:
            os.close(fd)
        probe_path.unlink()
        _fsync_directory(root)
    except OSError as exc:
        if probe_path is not None:
            probe_path.unlink(missing_ok=True)
        raise RuntimePathError(f"runtime data root is not writable: {root}: {exc}") from exc


def _validated_absolute_root(root: Path, *, validate: bool) -> Path:
    if not root.is_absolute():
        raise RuntimePathError(f"{DATA_DIR_ENV} must be an absolute path: {root}")
    resolved = root.resolve(strict=False)
    if not validate:
        return resolved
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimePathError(f"cannot create runtime data root {resolved}: {exc}") from exc
    if not resolved.is_dir():
        raise RuntimePathError(f"runtime data root is not a directory: {resolved}")
    _probe_writable_directory(resolved)
    return resolved


def runtime_paths_for_root(root: Path | str, *, validate: bool = True) -> RuntimePaths:
    """Resolve all runtime files below an explicit absolute root."""
    resolved = _validated_absolute_root(Path(root), validate=validate)
    files = {name: resolved / name for name in RUNTIME_FILE_NAMES}
    return RuntimePaths(
        configured=True,
        data_root=resolved,
        getdaytrends_db=files["getdaytrends.db"],
        filter_eval_shadow=files["filter_eval_shadow.sqlite3"],
        reference_library=files["reference_library.json"],
        x_exposure_observations=files["x_exposure_observations.json"],
        community_exposure_observations=files["community_exposure_observations.json"],
        fast_viral_snapshot=files["fast_viral_snapshot.json"],
        community_post_meta=files["community_post_meta.json"],
        viral_lead_times=files["viral_lead_times.json"],
        runtime_manifest=resolved / RUNTIME_MANIFEST_NAME,
        writer_lock=resolved / WRITER_LOCK_NAME,
    )


def resolve_runtime_paths(
    environ: Mapping[str, str] | None = None,
    *,
    validate: bool = True,
) -> RuntimePaths:
    """Resolve legacy defaults or the configured fail-closed absolute root."""
    env = os.environ if environ is None else environ
    if DATA_DIR_ENV not in env:
        return _legacy_paths()
    raw_root = env.get(DATA_DIR_ENV, "")
    if not raw_root or not raw_root.strip():
        raise RuntimePathError(f"{DATA_DIR_ENV} must not be empty")
    return runtime_paths_for_root(Path(raw_root), validate=validate)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sqlite_file_metadata(path: Path) -> dict[str, Any]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5.0) as conn:
            integrity = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise RuntimePathError(f"SQLite integrity_check failed for {path}: {integrity}")
            table_names = [
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            table_stats: dict[str, dict[str, Any]] = {}
            observed_mins: list[str] = []
            observed_maxes: list[str] = []
            total_rows = 0
            for table_name in table_names:
                quoted = _quote_identifier(table_name)
                row_count = int(conn.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0])
                total_rows += row_count
                columns = {
                    str(row[1])
                    for row in conn.execute(f"PRAGMA table_info({quoted})")
                }
                observed_min: str | None = None
                observed_max: str | None = None
                if "observed_at" in columns:
                    observed_row = conn.execute(
                        f"SELECT min(CAST(observed_at AS TEXT)), "
                        f"max(CAST(observed_at AS TEXT)) FROM {quoted}"
                    ).fetchone()
                    if observed_row and observed_row[0] is not None:
                        observed_min = str(observed_row[0])
                        observed_mins.append(observed_min)
                    if observed_row and observed_row[1] is not None:
                        observed_max = str(observed_row[1])
                        observed_maxes.append(observed_max)
                table_stats[table_name] = {
                    "row_count": row_count,
                    "observed_at_min": observed_min,
                    "observed_at_max": observed_max,
                }
    except (OSError, sqlite3.Error) as exc:
        raise RuntimePathError(f"cannot validate SQLite file {path}: {exc}") from exc

    return {
        "exists": True,
        "kind": "sqlite",
        "sha256": _sha256_file(path),
        "size": path.stat().st_size,
        "row_count": total_rows,
        "observed_at_min": min(observed_mins) if observed_mins else None,
        "observed_at_max": max(observed_maxes) if observed_maxes else None,
        "tables": table_stats,
    }


def inspect_runtime_file(path: Path, name: str) -> dict[str, Any]:
    """Return checksum, size, and SQLite observation statistics."""
    if name not in RUNTIME_FILE_NAMES:
        raise RuntimePathError(f"unknown runtime file: {name}")
    if not path.exists():
        return {
            "exists": False,
            "kind": "sqlite" if name in SQLITE_FILE_NAMES else "json",
            "sha256": None,
            "size": 0,
        }
    if path.is_symlink():
        raise RuntimePathError(f"runtime file must not be a symbolic link: {path}")
    if not path.is_file():
        raise RuntimePathError(f"runtime path is not a file: {path}")
    size = path.stat().st_size
    if size == 0:
        return {
            "exists": True,
            "kind": "sqlite" if name in SQLITE_FILE_NAMES else "json",
            "sha256": _sha256_file(path),
            "size": 0,
        }
    if name in SQLITE_FILE_NAMES:
        return _sqlite_file_metadata(path)
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimePathError(f"cannot validate JSON file {path}: {exc}") from exc
    return {
        "exists": True,
        "kind": "json",
        "sha256": _sha256_file(path),
        "size": size,
    }


def inspect_runtime_files(paths: RuntimePaths) -> dict[str, dict[str, Any]]:
    return {
        name: inspect_runtime_file(path, name)
        for name, path in paths.runtime_files().items()
    }


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write, fsync, and atomically replace one file plus its directory entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    fd: int | None = None
    try:
        fd = os.open(temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _fsync_directory(path.parent)
    except Exception:
        if fd is not None:
            os.close(fd)
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    atomic_write_bytes(path, encoded)


def load_runtime_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimePathError(f"cannot read runtime segment manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimePathError(f"runtime segment manifest must be an object: {path}")
    return payload


def _utc_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def initialize_runtime_segment(
    paths: RuntimePaths,
    *,
    policy_path: Path = DEFAULT_POLICY_PATH,
    reset: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create or continue one segment, marking missing expected data BROKEN."""
    if not paths.configured:
        raise RuntimePathError("runtime segments require an explicit absolute data root")
    try:
        policy_fingerprint = _sha256_file(policy_path)
    except OSError as exc:
        raise RuntimePathError(f"cannot fingerprint policy file {policy_path}: {exc}") from exc

    existing = load_runtime_manifest(paths.runtime_manifest)
    timestamp = _utc_iso(now)
    if existing and not reset:
        if existing.get("status") == "BROKEN":
            raise RuntimePathError(
                "runtime segment is BROKEN; explicitly initialize a new segment before writing"
            )
        if existing.get("target_files") != list(RUNTIME_FILE_NAMES):
            raise RuntimePathError("runtime segment target file list does not match the 0037 contract")

    try:
        current_files = inspect_runtime_files(paths)
    except RuntimePathError as exc:
        if existing and not reset:
            broken = dict(existing)
            broken.update(
                {
                    "status": "BROKEN",
                    "broken_at": timestamp,
                    "broken_reason": str(exc),
                }
            )
            atomic_write_json(paths.runtime_manifest, broken)
        raise

    if existing and not reset:
        missing_expected = [
            name
            for name, old_meta in existing.get("files", {}).items()
            if isinstance(old_meta, dict)
            and bool(old_meta.get("exists"))
            and int(old_meta.get("size") or 0) > 0
            and (
                not bool(current_files.get(name, {}).get("exists"))
                or int(current_files.get(name, {}).get("size") or 0) == 0
            )
        ]
        if missing_expected:
            broken = dict(existing)
            broken.update(
                {
                    "status": "BROKEN",
                    "broken_at": timestamp,
                    "broken_reason": "previously non-empty runtime files are missing or empty: "
                    + ", ".join(sorted(missing_expected)),
                }
            )
            atomic_write_json(paths.runtime_manifest, broken)
            raise RuntimePathError(str(broken["broken_reason"]))

    previous_segment_id = str(existing.get("segment_id")) if existing else None
    segment_id = (
        str(existing["segment_id"])
        if existing and not reset and existing.get("segment_id")
        else str(uuid.uuid4())
    )
    started_at = (
        str(existing.get("started_at"))
        if existing and not reset and existing.get("started_at")
        else timestamp
    )
    manifest: dict[str, Any] = {
        "format_version": 1,
        "segment_id": segment_id,
        "started_at": started_at,
        "updated_at": timestamp,
        "status": "ACTIVE",
        "data_root": str(paths.data_root),
        "target_files": list(RUNTIME_FILE_NAMES),
        "policy_fingerprint": policy_fingerprint,
        "files": current_files,
    }
    if reset and previous_segment_id:
        manifest["previous_segment_id"] = previous_segment_id
        manifest["reset_at"] = timestamp
    atomic_write_json(paths.runtime_manifest, manifest)
    return manifest


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def writer_lock_is_active(path: Path) -> bool:
    """Treat unreadable/malformed locks as active; dead-PID locks as stale."""
    if not path.exists():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip().split(":", 1)[0])
    except (OSError, ValueError):
        return True
    return _pid_is_alive(pid)


class RuntimeWriterLock:
    """Exclusive PID/token lock shared by dashboard startup and restore."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.token: str | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            token = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                try:
                    observed_token = self.path.read_text(encoding="utf-8").strip()
                except OSError:
                    observed_token = ""
                if attempt == 0 and observed_token and not writer_lock_is_active(self.path):
                    try:
                        if self.path.read_text(encoding="utf-8").strip() != observed_token:
                            raise RuntimeLockError(
                                f"runtime writer lock changed during stale cleanup: {self.path}"
                            )
                        self.path.unlink()
                    except OSError as unlink_exc:
                        raise RuntimeLockError(
                            f"cannot remove stale runtime writer lock {self.path}: {unlink_exc}"
                        ) from unlink_exc
                    continue
                raise RuntimeLockError(f"runtime writer lock is active: {self.path}") from exc
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(token)
                    handle.flush()
                    os.fsync(handle.fileno())
                _fsync_directory(self.path.parent)
                self.token = token
                return
            except Exception:
                self.path.unlink(missing_ok=True)
                raise
        raise RuntimeLockError(f"cannot acquire runtime writer lock: {self.path}")

    def release(self) -> None:
        if self.token is None:
            return
        try:
            if self.path.read_text(encoding="utf-8").strip() == self.token:
                self.path.unlink(missing_ok=True)
                _fsync_directory(self.path.parent)
        except OSError:
            pass
        finally:
            self.token = None

    def __enter__(self) -> RuntimeWriterLock:
        self.acquire()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.release()


__all__ = [
    "DATA_DIR_ENV",
    "DEFAULT_POLICY_PATH",
    "JSON_FILE_NAMES",
    "RUNTIME_FILE_NAMES",
    "RUNTIME_MANIFEST_NAME",
    "SQLITE_FILE_NAMES",
    "RuntimeLockError",
    "RuntimePathError",
    "RuntimePaths",
    "RuntimeWriterLock",
    "atomic_write_bytes",
    "atomic_write_json",
    "initialize_runtime_segment",
    "inspect_runtime_file",
    "inspect_runtime_files",
    "load_runtime_manifest",
    "resolve_runtime_paths",
    "runtime_paths_for_root",
    "writer_lock_is_active",
]
