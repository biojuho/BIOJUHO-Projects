"""Produce the bramble video-material queue from the server scheduler.

The dashboard route is deliberately a file reader.  This adapter owns the
missing producer side without importing code across repositories: it runs the
canonical bramble CLI with a fixed argv, verifies that the atomic JSON output
was actually replaced, and exposes scheduler-compatible freshness state.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from runtime_paths import RuntimeLockError, RuntimeWriterLock


DEFAULT_BRAMBLE_ROOT = Path("/Users/ju-hopark/orca/workspaces/X/bramble")
DEFAULT_QUEUE_RELATIVE_PATH = Path("content/queue/latest-video.json")
DEFAULT_PROCESS_TIMEOUT_SECONDS = 240
DEFAULT_MAX_AGE_MINUTES = 180
DEFAULT_PROBE_LIMIT = 40
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0
DEFAULT_REQUEST_SLEEP_SECONDS = 1.0


class VideoQueueRefreshError(RuntimeError):
    """The producer could not prove a fresh, valid queue replacement."""


def _env_int(name: str, fallback: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        return max(minimum, int(raw.strip()))
    except ValueError:
        return fallback


def _env_float(name: str, fallback: float, *, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        return max(minimum, float(raw.strip()))
    except ValueError:
        return fallback


def _iso_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _file_signature(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_ino, stat.st_mtime_ns, stat.st_size


def _parse_generated_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoQueueRefreshError("video queue JSON has no generated_at")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise VideoQueueRefreshError("video queue generated_at is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise VideoQueueRefreshError("video queue generated_at has no timezone")
    return value.strip()


class VideoQueueProducer:
    """Scheduler adapter with one-process-at-a-time and fail-closed output proof."""

    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        queue_path: Path | str | None = None,
        lock_path: Path | str | None = None,
        python_executable: Path | str | None = None,
        process_timeout_seconds: int | None = None,
        max_age_minutes: int | None = None,
        probe_limit: int | None = None,
        request_timeout_seconds: float | None = None,
        request_sleep_seconds: float | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        configured_root = os.getenv("VIDEO_QUEUE_PROJECT_ROOT", "").strip()
        self.project_root = Path(project_root or configured_root or DEFAULT_BRAMBLE_ROOT).resolve(strict=False)
        configured_queue = os.getenv("VIDEO_QUEUE_JSON_PATH", "").strip()
        self.queue_path = Path(
            queue_path or configured_queue or self.project_root / DEFAULT_QUEUE_RELATIVE_PATH
        ).resolve(strict=False)
        configured_lock = os.getenv("VIDEO_QUEUE_PRODUCER_LOCK_PATH", "").strip()
        self.lock_path = Path(
            lock_path or configured_lock or self.queue_path.with_name(f".{self.queue_path.name}.producer.lock")
        ).resolve(strict=False)
        self.python_executable = str(python_executable or sys.executable)
        self.process_timeout_seconds = process_timeout_seconds or _env_int(
            "VIDEO_QUEUE_PRODUCER_TIMEOUT_SECONDS",
            DEFAULT_PROCESS_TIMEOUT_SECONDS,
        )
        self.max_age_minutes = max_age_minutes or _env_int("VIDEO_QUEUE_MAX_AGE_MINUTES", DEFAULT_MAX_AGE_MINUTES)
        self.probe_limit = probe_limit or _env_int("VIDEO_QUEUE_PROBE_LIMIT", DEFAULT_PROBE_LIMIT)
        self.request_timeout_seconds = (
            request_timeout_seconds
            if request_timeout_seconds is not None
            else _env_float("VIDEO_QUEUE_REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS)
        )
        self.request_sleep_seconds = (
            request_sleep_seconds
            if request_sleep_seconds is not None
            else _env_float("VIDEO_QUEUE_REQUEST_SLEEP_SECONDS", DEFAULT_REQUEST_SLEEP_SECONDS)
        )
        self._runner = runner
        self._clock = clock or (lambda: datetime.now(UTC))
        self._last_attempt_at: str | None = None
        self._last_success_at: str | None = None
        self._last_error_at: str | None = None
        self._last_error: str | None = None
        self._last_returncode: int | None = None

    @property
    def script_path(self) -> Path:
        return self.project_root / "ops" / "scripts" / "video_candidates.py"

    def command(self) -> list[str]:
        """Return the fixed, shell-free command used by the automatic lane."""
        return [
            self.python_executable,
            str(self.script_path),
            "--limit",
            str(self.probe_limit),
            "--max-age",
            str(self.max_age_minutes),
            "--timeout",
            str(self.request_timeout_seconds),
            "--sleep",
            str(self.request_sleep_seconds),
            "--skip-media-probe",
            "--json-out",
            str(self.queue_path),
            "--no-queue",
        ]

    def _read_payload(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.queue_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise VideoQueueRefreshError(f"video queue JSON does not exist: {self.queue_path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise VideoQueueRefreshError(f"video queue JSON is unreadable: {self.queue_path}") from exc
        if not isinstance(payload, dict):
            raise VideoQueueRefreshError("video queue JSON root is not an object")
        _parse_generated_at(payload.get("generated_at"))
        return payload

    def snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        snapshot_error: str | None = None
        try:
            payload = self._read_payload()
        except VideoQueueRefreshError as exc:
            snapshot_error = str(exc)
        generated_at = payload.get("generated_at") if payload else None
        return {
            "refreshed_at": generated_at if isinstance(generated_at, str) else None,
            "generated_at": generated_at if isinstance(generated_at, str) else None,
            "counts": payload.get("counts", {}) if isinstance(payload.get("counts"), dict) else {},
            "last_attempt_at": self._last_attempt_at,
            "last_success_at": self._last_success_at or generated_at,
            "last_error_at": self._last_error_at,
            "last_error": self._last_error or snapshot_error,
            "last_returncode": self._last_returncode,
            "queue_path": str(self.queue_path),
            "lock_path": str(self.lock_path),
        }

    async def refresh(self) -> dict[str, Any]:
        """Run blocking probes off the event loop; the scheduler awaits the result."""
        return await asyncio.to_thread(self._refresh_sync)

    def _refresh_sync(self) -> dict[str, Any]:
        self._last_attempt_at = _iso_now(self._clock)
        before = _file_signature(self.queue_path)
        try:
            if not self.script_path.is_file():
                raise VideoQueueRefreshError(f"video queue script does not exist: {self.script_path}")
            with RuntimeWriterLock(self.lock_path):
                completed = self._runner(
                    self.command(),
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=self.process_timeout_seconds,
                    check=False,
                )
                self._last_returncode = int(completed.returncode)
                if completed.returncode != 0:
                    detail = (completed.stderr or completed.stdout or "no process output").strip()
                    raise VideoQueueRefreshError(f"video queue producer exited {completed.returncode}: {detail[-400:]}")
                after = _file_signature(self.queue_path)
                if after is None or after == before:
                    raise VideoQueueRefreshError("video queue command returned 0 without replacing JSON")
                payload = self._read_payload()
        except (OSError, subprocess.TimeoutExpired, RuntimeLockError, VideoQueueRefreshError) as exc:
            self._last_error_at = _iso_now(self._clock)
            self._last_error = f"{type(exc).__name__}: {exc}"[:500]
            raise

        self._last_success_at = _parse_generated_at(payload.get("generated_at"))
        self._last_error_at = None
        self._last_error = None
        return self.snapshot()


__all__ = [
    "DEFAULT_BRAMBLE_ROOT",
    "DEFAULT_QUEUE_RELATIVE_PATH",
    "VideoQueueProducer",
    "VideoQueueRefreshError",
]
