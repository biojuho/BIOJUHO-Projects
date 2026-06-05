#!/usr/bin/env python3
"""Summarize MCP workspace-smoke JSON into trace-oriented metrics."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_RESULT_FIELDS = ("scope", "name", "cwd", "command", "returncode", "ok")


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
        },
        "checks": [
            {
                "name": str(result.get("name") or ""),
                "cwd": str(result.get("cwd") or ""),
                "command_kind": command_kind(str(result.get("command") or "")),
                "returncode": result.get("returncode"),
                "ok": result.get("ok"),
            }
            for result in scoped_results
        ],
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
