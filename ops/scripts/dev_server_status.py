from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "dev_server_targets.json"
ALLOWED_KINDS = {"api", "frontend", "mcp", "preview"}
ALLOWED_SMOKE_SCOPES = {"workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
TARGET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIRED_TARGET_FIELDS = {
    "id",
    "label",
    "project",
    "kind",
    "cwd",
    "command",
    "url",
    "expected_status",
}

FetchResult = tuple[int | None, int | None, str | None, str | None]
FetchFn = Callable[[str, float], FetchResult]
SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def validate_manifest(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), errors)
    _require_string(payload.get("description"), "description", errors)

    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for index, target in enumerate(targets):
        prefix = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_TARGET_FIELDS - set(target)
        for field in sorted(missing):
            errors.append(f"{prefix}.{field} is required")
        target_id = _require_string(target.get("id"), f"{prefix}.id", errors)
        if target_id:
            if not TARGET_ID_RE.match(target_id):
                errors.append(f"{prefix}.id must use lowercase letters, numbers, hyphens, or underscores")
            if target_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(target_id)
        _require_string(target.get("label"), f"{prefix}.label", errors)
        _require_string(target.get("project"), f"{prefix}.project", errors)
        kind = _require_string(target.get("kind"), f"{prefix}.kind", errors)
        if kind and kind not in ALLOWED_KINDS:
            errors.append(f"{prefix}.kind must be one of {', '.join(sorted(ALLOWED_KINDS))}")
        _validate_cwd(target.get("cwd"), f"{prefix}.cwd", workspace_root, errors)
        _validate_command(target.get("command"), f"{prefix}.command", errors)
        _validate_url(target.get("url"), f"{prefix}.url", errors)
        _validate_expected_status(target.get("expected_status"), f"{prefix}.expected_status", errors)
        markers = target.get("expected_body_contains")
        if markers is not None:
            _validate_string_list(markers, f"{prefix}.expected_body_contains", errors)
        smoke_scope = target.get("smoke_scope")
        if smoke_scope is not None and smoke_scope not in ALLOWED_SMOKE_SCOPES:
            errors.append(f"{prefix}.smoke_scope must be a known smoke scope")
        tags = target.get("tags")
        if tags is not None:
            _validate_string_list(tags, f"{prefix}.tags", errors)
    return errors


def select_targets(payload: dict[str, Any], target_ids: list[str] | None = None) -> list[dict[str, Any]]:
    targets = list(payload["targets"])
    if not target_ids:
        return targets

    by_id = {target["id"]: target for target in targets}
    missing = [target_id for target_id in target_ids if target_id not in by_id]
    if missing:
        raise ValueError(f"unknown target id(s): {', '.join(missing)}")
    return [by_id[target_id] for target_id in target_ids]


def probe_target(target: dict[str, Any], *, timeout: float = 2.0, fetcher: FetchFn | None = None) -> dict[str, Any]:
    fetch = fetch_http_status if fetcher is None else fetcher
    status_code, latency_ms, body, error = fetch(target["url"], timeout)
    expected_status = target["expected_status"]
    expected_markers = target.get("expected_body_contains", [])
    missing_markers = _missing_body_markers(body, expected_markers)
    marker_error = None
    if status_code in expected_status and missing_markers:
        marker_error = "response body missing marker(s): " + ", ".join(missing_markers)
    result_error = error or marker_error
    ok = result_error is None and status_code in expected_status
    return {
        "id": target["id"],
        "label": target["label"],
        "project": target["project"],
        "kind": target["kind"],
        "cwd": target["cwd"],
        "command": format_command(target["command"]),
        "url": target["url"],
        "expected_status": expected_status,
        "expected_body_contains": expected_markers,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "ok": ok,
        "error": result_error,
    }


def fetch_http_status(url: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "dev-server-status/1"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            latency_ms = int((time.perf_counter() - started) * 1000)
            body = _read_response_body(response)
            return response.getcode(), latency_ms, body, None
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        body = _read_response_body(exc)
        return exc.code, latency_ms, body, None
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return None, latency_ms, None, _format_error(exc)


def build_report(
    payload: dict[str, Any],
    *,
    target_ids: list[str] | None = None,
    timeout: float = 2.0,
    fetcher: FetchFn | None = None,
) -> dict[str, Any]:
    targets = select_targets(payload, target_ids)
    results = [probe_target(target, timeout=timeout, fetcher=fetcher) for target in targets]
    ready = sum(1 for result in results if result["ok"])
    total = len(results)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ready" if ready == total else "degraded",
        "summary": {
            "total": total,
            "ready": ready,
            "unready": total - ready,
        },
        "targets": results,
    }


def wait_for_ready(
    payload: dict[str, Any],
    *,
    target_ids: list[str] | None = None,
    timeout: float = 2.0,
    wait_timeout: float = 30.0,
    poll_interval: float = 1.0,
    fetcher: FetchFn | None = None,
    sleeper: SleepFn = time.sleep,
    clock: ClockFn = time.monotonic,
) -> dict[str, Any]:
    wait_timeout = max(wait_timeout, 0.0)
    poll_interval = max(poll_interval, 0.0)
    deadline = clock() + wait_timeout
    attempts = 0
    report: dict[str, Any] | None = None

    while True:
        attempts += 1
        report = build_report(payload, target_ids=target_ids, timeout=timeout, fetcher=fetcher)
        if report["summary"]["unready"] == 0:
            break
        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleeper(min(poll_interval, remaining))

    assert report is not None
    report["wait"] = {
        "enabled": True,
        "attempts": attempts,
        "timeout_seconds": wait_timeout,
        "poll_interval_seconds": poll_interval,
        "ready": report["summary"]["unready"] == 0,
    }
    return report


def run(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    json_out: Path | None = None,
    target_ids: list[str] | None = None,
    timeout: float = 2.0,
    validate_only: bool = False,
    wait_ready: bool = False,
    wait_timeout: float = 30.0,
    poll_interval: float = 1.0,
    fetcher: FetchFn | None = None,
    sleeper: SleepFn = time.sleep,
    clock: ClockFn = time.monotonic,
) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))

    if validate_only:
        targets = select_targets(payload, target_ids)
        report = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "validated",
            "summary": {"total": len(targets), "ready": 0, "unready": 0},
            "targets": [
                {
                    "id": target["id"],
                    "label": target["label"],
                    "project": target["project"],
                    "kind": target["kind"],
                    "cwd": target["cwd"],
                    "command": format_command(target["command"]),
                    "url": target["url"],
                    "expected_status": target["expected_status"],
                    "expected_body_contains": target.get("expected_body_contains", []),
                }
                for target in targets
            ],
        }
    elif wait_ready:
        report = wait_for_ready(
            payload,
            target_ids=target_ids,
            timeout=timeout,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
            fetcher=fetcher,
            sleeper=sleeper,
            clock=clock,
        )
    else:
        report = build_report(payload, target_ids=target_ids, timeout=timeout, fetcher=fetcher)

    if json_out is not None:
        _write_json_atomic(json_out, report)
    return report


def format_command(command: list[str]) -> str:
    return " ".join(_quote_command_part(part) for part in command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report local dev-server readiness from a checked manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--target", action="append", dest="target_ids")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--wait-ready", action="store_true")
    parser.add_argument("--wait-timeout", type=float, default=30.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--fail-on-unready", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = run(
            args.manifest,
            json_out=args.json_out,
            target_ids=args.target_ids,
            timeout=args.timeout,
            validate_only=args.validate_only,
            wait_ready=args.wait_ready,
            wait_timeout=args.wait_timeout,
            poll_interval=args.poll_interval,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dev server status failed: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]
    if args.validate_only:
        print(f"dev server manifest valid: {summary['total']} target(s)")
        return 0

    prefix = "dev server wait" if args.wait_ready else "dev server status"
    wait_suffix = ""
    if args.wait_ready and "wait" in report:
        wait_suffix = f", attempts={report['wait']['attempts']}"
    print(f"{prefix}: {summary['ready']}/{summary['total']} ready, {summary['unready']} unready{wait_suffix}")
    if args.fail_on_unready and summary["unready"]:
        return 1
    return 0


def _validate_timestamp(value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append("generated_at must be a non-empty ISO timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("generated_at must be parseable as ISO datetime")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append("generated_at must include a timezone offset")


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_cwd(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    path_value = _require_string(value, field, errors)
    if not path_value:
        return
    if not _is_repo_relative(path_value):
        errors.append(f"{field} must be a repo-relative path")
        return
    if not (workspace_root / path_value).is_dir():
        errors.append(f"{field} must exist as a directory in the workspace")


def _validate_command(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, part in enumerate(value):
        if not isinstance(part, str) or not part.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
        if isinstance(part, str) and any(separator in part for separator in ("&&", "||", ";")):
            errors.append(f"{field}[{index}] must not include shell command separators")


def _validate_url(value: Any, field: str, errors: list[str]) -> None:
    url = _require_string(value, field, errors)
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        errors.append(f"{field} must use http or https")
    if parsed.hostname not in LOCAL_HOSTS:
        errors.append(f"{field} must target localhost or 127.0.0.1")
    if parsed.port is None:
        errors.append(f"{field} must include an explicit port")


def _validate_expected_status(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int) or item < 100 or item > 599:
            errors.append(f"{field}[{index}] must be an HTTP status code")


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return False
    if normalized.startswith("/") or normalized.startswith("../"):
        return False
    if "/../" in f"/{normalized}/":
        return False
    return not Path(value).is_absolute()


def _quote_command_part(part: str) -> str:
    if part == "":
        return '""'
    if any(ch.isspace() for ch in part):
        return '"' + part.replace('"', '\\"') + '"'
    return part


def _read_response_body(response: Any) -> str:
    try:
        raw = response.read(65536)
    except OSError:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")


def _missing_body_markers(body: str | None, markers: list[str]) -> list[str]:
    if not markers:
        return []
    content = body or ""
    return [marker for marker in markers if marker not in content]


def _format_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.URLError) and exc.reason:
        return str(exc.reason)
    return str(exc)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
