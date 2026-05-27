"""
BioLinker job orchestration service.

The API uses this manager for long-running tasks that need status polling and
SSE progress updates. Jobs stay in memory for local execution and are also
mirrored to Redis when available so snapshots survive transient API reads.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from models import JobAcceptedResponse, JobEvent, JobSnapshot, JobStatus, JobType

from services.logging_config import get_logger
from services.redis_store import get_redis_store

log = get_logger("biolinker.services.job_manager")

JobRunner = Callable[["JobContext"], Awaitable[Any]]
_MISSING = object()
_TERMINAL_STATUSES = {JobStatus.SUCCEEDED, JobStatus.FAILED}


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _JobRecord:
    id: str
    type: JobType
    status: JobStatus
    progress: int
    message: str
    storage: str
    access: str
    payload: dict[str, Any] = field(default_factory=dict)
    owner_uid: str | None = None
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utcnow)
    events: list[JobEvent] = field(default_factory=list)
    version: int = 0

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            id=self.id,
            type=self.type,
            status=self.status,
            progress=self.progress,
            message=self.message,
            storage=self.storage,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            updated_at=self.updated_at,
            events=list(self.events),
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "storage": self.storage,
            "access": self.access,
            "payload": self.payload,
            "owner_uid": self.owner_uid,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat(),
            "events": [event.model_dump(mode="json") for event in self.events],
            "version": self.version,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> _JobRecord:
        return cls(
            id=str(data["id"]),
            type=JobType(str(data["type"])),
            status=JobStatus(str(data["status"])),
            progress=int(data.get("progress", 0) or 0),
            message=str(data.get("message", "") or ""),
            storage=str(data.get("storage", "memory") or "memory"),
            access=str(data.get("access", "private") or "private"),
            payload=dict(data.get("payload", {}) or {}),
            owner_uid=str(data.get("owner_uid") or "") or None,
            result=data.get("result"),
            error=str(data.get("error") or "") or None,
            created_at=datetime.fromisoformat(str(data["created_at"])),
            started_at=datetime.fromisoformat(str(data["started_at"])) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(str(data["completed_at"])) if data.get("completed_at") else None,
            updated_at=datetime.fromisoformat(str(data["updated_at"])),
            events=[JobEvent.model_validate(event) for event in data.get("events", [])],
            version=int(data.get("version", 0) or 0),
        )


class JobContext:
    """Mutable job lifecycle helper passed to job runners."""

    def __init__(self, manager: JobManager, job_id: str):
        self._manager = manager
        self.job_id = job_id

    @property
    def payload(self) -> dict[str, Any]:
        record = self._manager.get_record(self.job_id)
        return dict(record.payload if record else {})

    @property
    def owner_uid(self) -> str | None:
        record = self._manager.get_record(self.job_id)
        return record.owner_uid if record else None

    async def update(self, progress: int, message: str) -> JobSnapshot | None:
        return await self._manager.update_job(
            self.job_id,
            status=JobStatus.RUNNING,
            progress=progress,
            message=message,
        )

    async def succeed(self, result: Any, message: str = "Job completed") -> JobSnapshot | None:
        return await self._manager.update_job(
            self.job_id,
            status=JobStatus.SUCCEEDED,
            progress=100,
            message=message,
            result=result,
            completed=True,
        )

    async def fail(self, error: str, message: str = "Job failed") -> JobSnapshot | None:
        return await self._manager.update_job(
            self.job_id,
            status=JobStatus.FAILED,
            message=message,
            error=error,
            completed=True,
        )


class JobManager:
    """In-process job lifecycle manager with optional Redis mirroring."""

    def __init__(self) -> None:
        self._jobs: dict[str, _JobRecord] = {}
        self._conditions: dict[str, asyncio.Condition] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def _storage_backend(self) -> str:
        try:
            redis_store = get_redis_store()
        except Exception:  # noqa: BLE001
            return "memory"
        return "redis" if getattr(redis_store, "is_ready", False) else "memory"

    def _cache_key(self, job_id: str) -> str:
        return f"biolinker:jobs:{job_id}"

    def _persist_record(self, record: _JobRecord) -> None:
        if record.storage != "redis":
            return
        try:
            redis_store = get_redis_store()
            if getattr(redis_store, "is_ready", False):
                redis_store.set(
                    self._cache_key(record.id),
                    json.dumps(record.serialize(), ensure_ascii=False),
                    ex=24 * 60 * 60,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("job_persist_failed", job_id=record.id, error=str(exc))

    def _load_record(self, job_id: str) -> _JobRecord | None:
        if job_id in self._jobs:
            return self._jobs[job_id]

        try:
            redis_store = get_redis_store()
            payload = redis_store.get(self._cache_key(job_id))
        except Exception:  # noqa: BLE001
            return None

        if not payload:
            return None

        try:
            record = _JobRecord.deserialize(json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

        self._jobs[job_id] = record
        self._conditions.setdefault(job_id, asyncio.Condition())
        return record

    def get_record(self, job_id: str) -> _JobRecord | None:
        return self._load_record(job_id)

    async def create_job(
        self,
        *,
        job_type: JobType,
        payload: dict[str, Any] | None,
        runner: JobRunner,
        message: str,
        owner_uid: str | None = None,
        access: str = "private",
    ) -> JobAcceptedResponse:
        job_id = str(uuid.uuid4())
        created_at = _utcnow()
        storage = self._storage_backend()
        record = _JobRecord(
            id=job_id,
            type=job_type,
            status=JobStatus.QUEUED,
            progress=0,
            message=message,
            storage=storage,
            access=access,
            payload=dict(payload or {}),
            owner_uid=owner_uid,
            created_at=created_at,
            updated_at=created_at,
            events=[JobEvent(timestamp=created_at, status=JobStatus.QUEUED, progress=0, message=message)],
        )
        self._jobs[job_id] = record
        self._conditions[job_id] = asyncio.Condition()
        self._persist_record(record)
        self._tasks[job_id] = asyncio.create_task(self._run_job(job_id, runner), name=f"biolinker-job-{job_id}")
        log.info("job_created", job_id=job_id, job_type=job_type.value, owner_uid=owner_uid, access=access)
        return JobAcceptedResponse(job=record.snapshot())

    async def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: Any = _MISSING,
        error: str | None | object = _MISSING,
        completed: bool = False,
    ) -> JobSnapshot | None:
        record = self.get_record(job_id)
        if record is None:
            return None

        if status is not None:
            record.status = status
            if status == JobStatus.RUNNING and record.started_at is None:
                record.started_at = _utcnow()
        if progress is not None:
            record.progress = max(0, min(100, progress))
        if message is not None:
            record.message = message
        if result is not _MISSING:
            record.result = result
        if error is not _MISSING:
            record.error = error if isinstance(error, str) else None
        if completed or record.status in _TERMINAL_STATUSES:
            record.completed_at = _utcnow()
            if record.status == JobStatus.SUCCEEDED:
                record.progress = 100
            if record.status == JobStatus.FAILED and progress is None:
                record.progress = max(record.progress, 1)

        record.updated_at = _utcnow()
        record.version += 1
        record.events.append(
            JobEvent(
                timestamp=record.updated_at,
                status=record.status,
                progress=record.progress,
                message=record.message,
            )
        )
        if len(record.events) > 50:
            record.events = record.events[-50:]

        self._persist_record(record)

        condition = self._conditions.setdefault(job_id, asyncio.Condition())
        async with condition:
            condition.notify_all()

        return record.snapshot()

    async def _run_job(self, job_id: str, runner: JobRunner) -> None:
        record = self.get_record(job_id)
        if record is None:
            return

        try:
            await self.update_job(job_id, status=JobStatus.RUNNING, progress=5, message="Job started")
            context = JobContext(self, job_id)
            result = await runner(context)
            latest = self.get_record(job_id)
            if latest and latest.status not in _TERMINAL_STATUSES:
                await context.succeed(result, message="Job completed")
        except asyncio.CancelledError:
            log.info("job_cancelled", job_id=job_id, job_type=record.type.value)
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("job_execution_failed", job_id=job_id, job_type=record.type.value, error=str(exc))
            context = JobContext(self, job_id)
            await context.fail(str(exc), message="Job failed")
        finally:
            self._tasks.pop(job_id, None)

    async def stream(self, job_id: str):
        """Yield successive job snapshots until the job reaches a terminal state."""

        record = self.get_record(job_id)
        if record is None:
            return

        last_version = -1
        while True:
            current = self.get_record(job_id)
            if current is None:
                return

            if current.version != last_version:
                last_version = current.version
                yield current.snapshot()

            if current.status in _TERMINAL_STATUSES:
                return

            condition = self._conditions.setdefault(job_id, asyncio.Condition())
            try:
                async with condition:
                    await asyncio.wait_for(condition.wait(), timeout=15)
            except TimeoutError:
                continue

    def reset(self) -> None:
        """Clear in-memory state between tests."""

        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        self._jobs.clear()
        self._conditions.clear()


_job_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
