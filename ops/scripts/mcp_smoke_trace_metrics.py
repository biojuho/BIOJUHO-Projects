#!/usr/bin/env python3
"""Summarize MCP workspace-smoke JSON into trace-oriented metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_RESULT_FIELDS = ("scope", "name", "cwd", "command", "returncode", "ok")
DURATION_FIELDS = ("duration_seconds", "elapsed_seconds", "duration", "elapsed")
DURATION_PATTERN = re.compile(
    r"\b(?:built|completed|finished|passed|failed|errors?|warnings?)\b[^\r\n]*?\bin\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ms|milliseconds?|s|sec|secs|seconds?|m|min|mins|minutes?)\b",
    re.IGNORECASE,
)
GENERIC_DURATION_PATTERN = re.compile(
    r"\bin\s+(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>ms|milliseconds?|s|sec|secs|seconds?|m|min|mins|minutes?)\b",
    re.IGNORECASE,
)
CLOCK_DURATION_PATTERN = re.compile(
    r"\((?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:\.(?P<fraction>\d+))?\)"
)
COMMAND_TOKEN_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'|(\S+)')


def load_smoke_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a schema v1 JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path} must use schema_version 1")
    if not isinstance(payload.get("results"), list):
        raise ValueError(f"{path} is missing a results array")
    return payload


def command_kind(command: str) -> str:
    lower_command = command.lower()
    if "compileall" in lower_command:
        return "compileall"
    if "py_compile" in lower_command:
        return "py_compile"
    if "pytest" in lower_command:
        return "pytest"
    if "npm" in lower_command:
        return "npm"
    if "node" in lower_command:
        return "node"
    return "other"


def extract_duration(result: dict[str, Any]) -> dict[str, Any]:
    for field in DURATION_FIELDS:
        seconds = _duration_field_seconds(result.get(field))
        if seconds is not None:
            return {"seconds": _round_seconds(seconds), "source": field}

    for field in ("stdout_tail", "stderr_tail"):
        text = str(result.get(field) or "")
        seconds = _duration_from_text(text)
        if seconds is not None:
            return {"seconds": _round_seconds(seconds), "source": field}

    return {"seconds": None, "source": None}


def path_depth(value: str) -> int:
    parts = _path_parts(value)
    return len(parts) if value.strip() != "." else 0


def command_path_metrics(command: str) -> dict[str, int]:
    depths = [
        path_depth(token)
        for token in _command_tokens(command)
        if _looks_like_path(token)
    ]
    return {
        "path_tokens": len(depths),
        "max_depth": max(depths, default=0),
    }


def result_issue(result: Any, index: int) -> list[str]:
    issues: list[str] = []
    if not isinstance(result, dict):
        return [f"results[{index}] is not an object"]

    for field in REQUIRED_RESULT_FIELDS:
        if field not in result:
            issues.append(f"results[{index}] missing {field}")

    for field in ("scope", "name", "cwd", "command"):
        if field in result and not str(result.get(field) or "").strip():
            issues.append(f"results[{index}].{field} is empty")

    ok_value = result.get("ok")
    returncode = result.get("returncode")
    if not isinstance(ok_value, bool):
        issues.append(f"results[{index}].ok is not boolean")
    if not isinstance(returncode, int):
        issues.append(f"results[{index}].returncode is not an integer")
    if isinstance(ok_value, bool) and isinstance(returncode, int) and ok_value != (returncode == 0):
        issues.append(f"results[{index}].ok contradicts returncode")

    return issues


def build_metrics(payload: dict[str, Any], *, source_path: Path, scope: str = "mcp") -> dict[str, Any]:
    all_results = payload["results"]
    integrity_issues: list[str] = []
    for index, result in enumerate(all_results):
        integrity_issues.extend(result_issue(result, index))

    scoped_results = [
        result
        for result in all_results
        if isinstance(result, dict) and str(result.get("scope") or "").strip() == scope
    ]
    if not scoped_results:
        integrity_issues.append(f"no results found for scope {scope!r}")

    kind_counts = Counter(command_kind(str(result.get("command") or "")) for result in scoped_results)
    cwd_counts = Counter(str(result.get("cwd") or "") for result in scoped_results)
    passed = sum(1 for result in scoped_results if result.get("ok") is True)
    failed = sum(1 for result in scoped_results if result.get("ok") is False)
    checks = [_check_metrics(result) for result in scoped_results]

    return {
        "schema_version": 1,
        "source_path": str(source_path),
        "source_status": payload.get("status"),
        "source_generated_at": payload.get("generated_at"),
        "scope": scope,
        "summary": {
            "checks": len(scoped_results),
            "passed": passed,
            "failed": failed,
            "runtime_kinds": dict(sorted(kind_counts.items())),
            "cwd_counts": dict(sorted(cwd_counts.items())),
            "timing": _timing_summary(checks),
            "path_depth": _path_depth_summary(checks),
        },
        "checks": checks,
        "trace_integrity": {
            "ok": not integrity_issues,
            "issues": integrity_issues,
        },
    }


def write_metrics(metrics: dict[str, Any], out_path: Path | None) -> None:
    rendered = json.dumps(metrics, indent=2, ensure_ascii=False)
    if out_path is None:
        print(rendered)
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered + "\n", encoding="utf-8")


def _check_metrics(result: dict[str, Any]) -> dict[str, Any]:
    command = str(result.get("command") or "")
    cwd = str(result.get("cwd") or "")
    duration = extract_duration(result)
    command_paths = command_path_metrics(command)
    return {
        "name": str(result.get("name") or ""),
        "cwd": cwd,
        "cwd_depth": path_depth(cwd),
        "command_kind": command_kind(command),
        "command_path_tokens": command_paths["path_tokens"],
        "command_path_depth": command_paths["max_depth"],
        "duration_seconds": duration["seconds"],
        "duration_source": duration["source"],
        "returncode": result.get("returncode"),
        "ok": result.get("ok"),
    }


def _timing_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [
        {"name": check["name"], "seconds": check["duration_seconds"]}
        for check in checks
        if check["duration_seconds"] is not None
    ]
    slowest = max(observed, key=lambda item: item["seconds"], default=None)
    total = sum(item["seconds"] for item in observed)
    return {
        "observed_checks": len(observed),
        "missing_checks": len(checks) - len(observed),
        "total_seconds": _round_seconds(total) if observed else None,
        "max_seconds": slowest["seconds"] if slowest else None,
        "slowest_check": slowest["name"] if slowest else None,
    }


def _path_depth_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "max_cwd_depth": max((check["cwd_depth"] for check in checks), default=0),
        "max_command_path_depth": max((check["command_path_depth"] for check in checks), default=0),
        "command_path_tokens": sum(check["command_path_tokens"] for check in checks),
    }


def _duration_field_seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


def _duration_from_text(text: str) -> float | None:
    for pattern in (DURATION_PATTERN, GENERIC_DURATION_PATTERN):
        match = pattern.search(text)
        if match:
            return _duration_value_seconds(match.group("value"), match.group("unit"))

    match = CLOCK_DURATION_PATTERN.search(text)
    if not match:
        return None
    seconds = (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
    )
    fraction = match.group("fraction")
    if fraction:
        seconds += float(f"0.{fraction}")
    return float(seconds)


def _duration_value_seconds(value: str, unit: str) -> float:
    numeric_value = float(value)
    normalized_unit = unit.lower()
    if normalized_unit in {"ms", "millisecond", "milliseconds"}:
        return numeric_value / 1000
    if normalized_unit in {"m", "min", "mins", "minute", "minutes"}:
        return numeric_value * 60
    return numeric_value


def _round_seconds(value: float) -> float:
    return round(value, 3)


def _command_tokens(command: str) -> list[str]:
    tokens: list[str] = []
    for match in COMMAND_TOKEN_PATTERN.finditer(command):
        tokens.append(next(group for group in match.groups() if group is not None))
    return tokens


def _looks_like_path(value: str) -> bool:
    stripped = _strip_path_token(value)
    if "://" in stripped:
        return False
    return "/" in stripped or "\\" in stripped


def _path_parts(value: str) -> list[str]:
    stripped = _strip_path_token(value)
    if not stripped or stripped == ".":
        return []
    normalized = stripped.replace("\\", "/")
    normalized = re.sub(r"^[A-Za-z]:/", "", normalized)
    return [part for part in normalized.split("/") if part and part != "."]


def _strip_path_token(value: str) -> str:
    return value.strip().strip("\"'").strip(".,;:()[]{}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build MCP trace metrics from workspace-smoke JSON.")
    parser.add_argument("smoke_json", help="Path to a schema v1 workspace smoke JSON report.")
    parser.add_argument("--scope", default="mcp", help="Scope to summarize. Defaults to mcp.")
    parser.add_argument("--json-out", help="Optional output path for the metrics JSON.")
    parser.add_argument("--allow-issues", action="store_true", help="Return success even when trace integrity issues exist.")
    args = parser.parse_args(argv)

    source_path = Path(args.smoke_json)
    payload = load_smoke_report(source_path)
    metrics = build_metrics(payload, source_path=source_path, scope=args.scope)
    write_metrics(metrics, Path(args.json_out) if args.json_out else None)
    return 0 if args.allow_issues or metrics["trace_integrity"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
