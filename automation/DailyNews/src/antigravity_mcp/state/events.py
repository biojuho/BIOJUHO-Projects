from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_run_id(job_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{job_name}-{timestamp}"


def build_response(
    *,
    status: str,
    data: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "status": status,
        "data": data or {},
        "meta": {"warnings": []},
        "error": error,
    }
    if meta:
        envelope["meta"].update(meta)
    return envelope


def ok(data: dict[str, Any], *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_response(status="ok", data=data, meta=meta)


def partial(
    data: dict[str, Any],
    *,
    warnings: list[str],
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_meta = dict(meta or {})
    merged_meta["warnings"] = list(warnings)
    return build_response(status="partial", data=data, meta=merged_meta)


def error_response(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    data: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_response(
        status="error",
        data=data or {},
        meta=meta,
        error={"code": code, "message": message, "retryable": retryable},
    )


def json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
