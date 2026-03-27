from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.events import utc_now_iso


class AlreadyRunningError(RuntimeError):
    pass


@dataclass
class JobLock:
    job_name: str
    run_id: str
    timeout_sec: int

    def __post_init__(self) -> None:
        settings = get_settings()
        self.path: Path = settings.data_dir / f"{self.job_name}.lock"

    def __enter__(self) -> "JobLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            payload = {}
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            started_at = payload.get("started_at")
            if started_at:
                try:
                    age_sec = time.time() - datetime.fromisoformat(started_at).timestamp()
                    if age_sec > self.timeout_sec:
                        self.path.unlink(missing_ok=True)
                    else:
                        raise AlreadyRunningError(f"{self.job_name} is already running")
                except ValueError:
                    raise AlreadyRunningError(f"{self.job_name} has an invalid lock file") from None
            else:
                raise AlreadyRunningError(f"{self.job_name} is already running")
        payload = {"run_id": self.run_id, "started_at": utc_now_iso()}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.path.unlink(missing_ok=True)
