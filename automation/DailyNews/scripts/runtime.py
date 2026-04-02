from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import feedparser
import httpx
from settings import (
    DATA_DIR,
    LOG_DIR,
    PIPELINE_HTTP_TIMEOUT_SEC,
    PIPELINE_LOCK_TIMEOUT_SEC,
    PIPELINE_MAX_RETRIES,
    PIPELINE_STATE_DB,
    SCHEDULER_LOG_PATH,
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def configure_stdout_utf8() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except OSError:
            pass


def generate_run_id(job_name: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{job_name}-{timestamp}-{os.getpid()}"


def _quote(value: Any) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text):
        return f'"{text}"'
    return text


@dataclass
class PipelineLogger:
    job_name: str
    run_id: str
    log_path: Path

    def _emit(self, level: str, step: str, status: str, message: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "ts": utc_now_iso(),
            "level": level.upper(),
            "job": self.job_name,
            "run_id": self.run_id,
            "step": step,
            "status": status,
            "message": message,
        }
        payload.update({key: value for key, value in fields.items() if value is not None})
        line = " ".join(f"{key}={_quote(value)}" for key, value in payload.items())
        print(line, flush=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def info(self, step: str, status: str, message: str, **fields: Any) -> None:
        self._emit("INFO", step, status, message, **fields)

    def warning(self, step: str, status: str, message: str, **fields: Any) -> None:
        self._emit("WARN", step, status, message, **fields)

    def debug(self, step: str, status: str, message: str, **fields: Any) -> None:
        self._emit("DEBUG", step, status, message, **fields)

    def error(self, step: str, status: str, message: str, **fields: Any) -> None:
        self._emit("ERROR", step, status, message, **fields)


def get_logger(job_name: str, run_id: str) -> PipelineLogger:
    return PipelineLogger(job_name=job_name, run_id=run_id, log_path=LOG_DIR / f"{job_name}.log")


def append_scheduler_log(message: str) -> None:
    SCHEDULER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCHEDULER_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now_iso()}] {message}\n")


async def run_with_timeout(coro: Awaitable[Any], timeout_sec: float) -> Any:
    return await asyncio.wait_for(coro, timeout=timeout_sec)


async def async_retry(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    attempts: int | None = None,
    base_delay: float = 1.0,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Any:
    max_attempts = attempts or PIPELINE_MAX_RETRIES
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except retry_exceptions as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    if last_error is not None:
        raise last_error
    raise RuntimeError("async_retry exhausted without executing a coroutine")


async def safe_gather(tasks: Iterable[Awaitable[Any]]) -> list[Any]:
    return list(await asyncio.gather(*tasks, return_exceptions=True))


async def fetch_feed_entries(
    url: str,
    *,
    timeout_sec: float | None = None,
    attempts: int | None = None,
) -> list[Any]:
    request_timeout = timeout_sec or PIPELINE_HTTP_TIMEOUT_SEC

    async def _fetch() -> list[Any]:
        async with httpx.AsyncClient(timeout=request_timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "AntigravityNewsBot/1.0 (+https://notion.so)"},
            )
            response.raise_for_status()
        # Use raw bytes so feedparser respects the XML encoding declaration
        # (fixes mojibake with Korean RSS feeds like EUC-KR / CP949)
        parsed = feedparser.parse(response.content)
        return list(parsed.entries)

    return await async_retry(_fetch, attempts=attempts, base_delay=1.5)


class AlreadyRunningError(RuntimeError):
    pass


class JobLock:
    def __init__(
        self,
        job_name: str,
        run_id: str,
        *,
        timeout_sec: int = PIPELINE_LOCK_TIMEOUT_SEC,
    ) -> None:
        self.job_name = job_name
        self.run_id = run_id
        self.timeout_sec = timeout_sec
        self.path = DATA_DIR / f"{job_name}.lock"

    def _try_expire_stale_lock(self) -> bool:
        """Remove lock file if it's older than timeout_sec. Returns True if removed."""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return True  # broken or gone → treat as available
        started_at = payload.get("started_at")
        if started_at:
            try:
                age_sec = time.time() - datetime.fromisoformat(started_at).timestamp()
                if age_sec > self.timeout_sec:
                    self.path.unlink(missing_ok=True)
                    return True
            except ValueError:
                pass
        return False

    def __enter__(self) -> JobLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"pid": os.getpid(), "run_id": self.run_id, "started_at": utc_now_iso()},
            indent=2,
        )
        try:
            # Atomic create: O_CREAT | O_EXCL guarantees only one process wins
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, payload.encode("utf-8"))
            os.close(fd)
            return self
        except FileExistsError:
            # Lock file exists — check if it's stale
            if self._try_expire_stale_lock():
                # Stale lock removed, retry once
                try:
                    fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, payload.encode("utf-8"))
                    os.close(fd)
                    return self
                except FileExistsError:
                    pass
            raise AlreadyRunningError(f"{self.job_name} is already running")

    def __exit__(self, exc_type, exc, tb) -> None:
        self.path.unlink(missing_ok=True)


class PipelineStateStore:
    def __init__(self, path: Path = PIPELINE_STATE_DB) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    def __enter__(self) -> PipelineStateStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    summary_json TEXT,
                    error_text TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS article_cache (
                    link TEXT PRIMARY KEY,
                    source TEXT,
                    first_seen_at TEXT NOT NULL,
                    notion_page_id TEXT,
                    last_run_id TEXT
                )
                """
            )

    def record_job_start(self, run_id: str, job_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO job_runs(run_id, job_name, started_at, finished_at, status, summary_json, error_text)
                VALUES (?, ?, ?, NULL, ?, NULL, NULL)
                """,
                (run_id, job_name, utc_now_iso(), "running"),
            )

    def record_job_finish(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any] | None = None,
        error_text: str | None = None,
    ) -> None:
        summary_json = json.dumps(summary, ensure_ascii=False) if summary is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE job_runs
                SET finished_at = ?, status = ?, summary_json = ?, error_text = ?
                WHERE run_id = ?
                """,
                (utc_now_iso(), status, summary_json, error_text, run_id),
            )

    def has_article(self, link: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM article_cache WHERE link = ? LIMIT 1",
                (link,),
            ).fetchone()
        return row is not None

    def record_article(
        self,
        *,
        link: str,
        source: str,
        notion_page_id: str | None,
        run_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO article_cache(link, source, first_seen_at, notion_page_id, last_run_id)
                VALUES (
                    ?,
                    ?,
                    COALESCE((SELECT first_seen_at FROM article_cache WHERE link = ?), ?),
                    ?,
                    ?
                )
                """,
                (link, source, link, utc_now_iso(), notion_page_id, run_id),
            )


def _notion_error_details(exc: BaseException) -> str:
    details = f"{type(exc).__name__}: {exc}"
    if hasattr(exc, "body"):
        details += f" | Body: {exc.body}"
    return details


async def create_notion_page_with_retry(
    *,
    notion_client: Any,
    parent: dict[str, Any],
    properties: dict[str, Any],
    children: Sequence[dict[str, Any]] | None,
    logger: PipelineLogger,
    step: str,
    timeout_sec: float = 20.0,
    attempts: int | None = None,
) -> dict[str, Any]:
    async def _create() -> dict[str, Any]:
        return await run_with_timeout(
            notion_client.pages.create(
                parent=parent,
                properties=properties,
                children=list(children or []),
            ),
            timeout_sec,
        )

    try:
        result = await async_retry(_create, attempts=attempts, base_delay=1.5)
        logger.info(step, "success", "notion page created")
        return result
    except Exception as exc:
        detail = _notion_error_details(exc)
        logger.error(step, "failed", "notion page create failed", error=detail)
        append_scheduler_log(f"[ALERT] {logger.job_name} {logger.run_id} {step} failed: {detail}")
        raise
