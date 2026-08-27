from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from runtime_paths import RuntimeLockError, RuntimeWriterLock
from video_queue_producer import VideoQueueProducer, VideoQueueRefreshError

if TYPE_CHECKING:
    from pathlib import Path


def _project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "bramble"
    script = root / "ops" / "scripts" / "video_candidates.py"
    script.parent.mkdir(parents=True)
    script.write_text("# synthetic entrypoint\n", encoding="utf-8")
    return root, root / "content" / "queue" / "latest-video.json"


def _write_queue(path: Path, generated_at: str, *, confirmed: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "counts": {"confirmed_videos": confirmed},
                "videos": [],
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


@pytest.mark.asyncio
async def test_refresh_uses_fixed_argv_replaces_json_and_records_success(tmp_path):
    root, queue = _project(tmp_path)
    _write_queue(queue, "2026-08-26T18:00:00+09:00")
    calls: list[tuple[list[str], dict]] = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        _write_queue(queue, "2026-08-27T04:15:00+09:00", confirmed=3)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    producer = VideoQueueProducer(
        project_root=root,
        queue_path=queue,
        python_executable="/synthetic/python",
        runner=runner,
        request_sleep_seconds=0,
        clock=lambda: datetime(2026, 8, 26, 19, 15, tzinfo=UTC),
    )

    snapshot = await producer.refresh()

    argv, kwargs = calls[0]
    assert argv[0] == "/synthetic/python"
    assert argv[1] == str(root / "ops" / "scripts" / "video_candidates.py")
    assert "--skip-media-probe" in argv
    assert argv[argv.index("--json-out") + 1] == str(queue)
    assert kwargs["cwd"] == root
    assert kwargs["check"] is False
    assert snapshot["refreshed_at"] == "2026-08-27T04:15:00+09:00"
    assert snapshot["last_success_at"] == "2026-08-27T04:15:00+09:00"
    assert snapshot["last_error"] is None
    assert snapshot["counts"]["confirmed_videos"] == 3


@pytest.mark.asyncio
async def test_nonzero_exit_preserves_old_queue_and_records_error(tmp_path):
    root, queue = _project(tmp_path)
    _write_queue(queue, "2026-08-26T18:00:00+09:00")
    before = queue.read_bytes()

    def runner(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="input unavailable")

    producer = VideoQueueProducer(project_root=root, queue_path=queue, runner=runner)

    with pytest.raises(VideoQueueRefreshError, match="exited 2"):
        await producer.refresh()

    assert queue.read_bytes() == before
    assert producer.snapshot()["last_returncode"] == 2
    assert "exited 2" in str(producer.snapshot()["last_error"])


@pytest.mark.asyncio
async def test_zero_exit_without_atomic_replacement_fails_closed(tmp_path):
    root, queue = _project(tmp_path)
    _write_queue(queue, "2026-08-26T18:00:00+09:00")

    def runner(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="claimed success", stderr="")

    producer = VideoQueueProducer(project_root=root, queue_path=queue, runner=runner)

    with pytest.raises(VideoQueueRefreshError, match="without replacing JSON"):
        await producer.refresh()


@pytest.mark.asyncio
async def test_active_lock_blocks_second_producer_before_runner(tmp_path):
    root, queue = _project(tmp_path)
    called = False

    def runner(argv, **_kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    producer = VideoQueueProducer(project_root=root, queue_path=queue, runner=runner)
    with (
        RuntimeWriterLock(producer.lock_path),
        pytest.raises(RuntimeLockError, match="runtime writer lock is active"),
    ):
        await producer.refresh()
    assert called is False


def test_snapshot_keeps_missing_or_invalid_time_unknown(tmp_path):
    root, queue = _project(tmp_path)
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text('{"generated_at": null}', encoding="utf-8")
    producer = VideoQueueProducer(project_root=root, queue_path=queue)

    snapshot = producer.snapshot()

    assert snapshot["refreshed_at"] is None
    assert "no generated_at" in str(snapshot["last_error"])
