#!/usr/bin/env python3
"""Summarize MCP workspace-smoke JSON into trace-oriented metrics."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_RESULT_FIELDS = ("scope", "name", "cwd", "command", "returncode", "ok")
DURATION_FIELDS = ("duration_seconds", "elapsed_seconds", "duration", "elapsed")
INPUT_TOKEN_FIELDS = ("input_tokens", "prompt_tokens", "tokens_input")
OUTPUT_TOKEN_FIELDS = ("output_tokens", "completion_tokens", "tokens_output")
TOTAL_TOKEN_FIELDS = ("total_tokens", "tokens")
COST_FIELDS = ("cost_usd", "estimated_cost_usd", "usd_cost")
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


def extract_usage(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    input_tokens, input_source = _first_number(result, usage, INPUT_TOKEN_FIELDS, integer=True)
    output_tokens, output_source = _first_number(result, usage, OUTPUT_TOKEN_FIELDS, integer=True)
    total_tokens, total_source = _first_number(result, usage, TOTAL_TOKEN_FIELDS, integer=True)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
        total_source = "derived"

    cost_usd, cost_source = _first_number(result, usage, COST_FIELDS, integer=False)
    sources = sorted(
        source
        for source in {input_source, output_source, total_source, cost_source}
        if source is not None
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": _round_cost(cost_usd) if cost_usd is not None else None,
        "sources": sources,
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
            "usage": _usage_summary(checks),
            "path_depth": _path_depth_summary(checks),
        },
        "checks": checks,
        "span_tree": _span_tree(checks, scope=scope),
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


def write_markdown(metrics: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(format_markdown(metrics), encoding="utf-8")


def write_html(metrics: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(format_html(metrics), encoding="utf-8")


def write_otel_json(metrics: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(format_otel_json(metrics), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_otel_submit_report(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def format_markdown(metrics: dict[str, Any]) -> str:
    summary = metrics["summary"]
    timing = summary["timing"]
    usage = summary["usage"]
    path_depth = summary["path_depth"]
    lines = [
        "# MCP Smoke Trace Metrics",
        "",
        "## Source",
        "",
        f"- Smoke report: `{metrics['source_path']}`",
        f"- Scope: `{metrics['scope']}`",
        f"- Source status: `{metrics.get('source_status')}`",
        f"- Source generated at: `{metrics.get('source_generated_at')}`",
        "",
        "## Summary",
        "",
        f"- Checks: {summary['checks']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Timing observed: {timing['observed_checks']} observed, {timing['missing_checks']} missing",
        f"- Total observed seconds: {_markdown_value(timing['total_seconds'])}",
        f"- Slowest check: {_markdown_value(timing['slowest_check'])} ({_markdown_value(timing['max_seconds'])}s)",
        f"- Usage observed: {usage['observed_checks']} observed, {usage['missing_checks']} missing",
        f"- Total tokens: {_markdown_value(usage['total_tokens'])}",
        f"- Cost USD: {_markdown_value(usage['cost_usd'])}",
        f"- Costliest check: {_markdown_value(usage['costliest_check'])} ({_markdown_value(usage['max_cost_usd'])} USD)",
        f"- Max cwd depth: {path_depth['max_cwd_depth']}",
        f"- Max command path depth: {path_depth['max_command_path_depth']}",
        f"- Command path tokens: {path_depth['command_path_tokens']}",
        "",
        "## Runtime Kinds",
        "",
        "| Kind | Count |",
        "| --- | ---: |",
    ]
    runtime_kinds = summary["runtime_kinds"]
    if runtime_kinds:
        lines.extend(f"| {_markdown_cell(kind)} | {count} |" for kind, count in runtime_kinds.items())
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Kind | OK | CWD | Duration seconds | Total tokens | Cost USD | Command path depth |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for check in metrics["checks"]:
        duration = check["duration_seconds"]
        duration_cell = "" if duration is None else str(duration)
        total_tokens = "" if check["total_tokens"] is None else str(check["total_tokens"])
        cost_usd = "" if check["cost_usd"] is None else str(check["cost_usd"])
        lines.append(
            "| "
            f"{_markdown_cell(check['name'])} | "
            f"{_markdown_cell(check['command_kind'])} | "
            f"{str(check['ok']).lower()} | "
            f"{_markdown_cell(check['cwd'])} | "
            f"{duration_cell} | "
            f"{total_tokens} | "
            f"{cost_usd} | "
            f"{check['command_path_depth']} |"
        )

    trace_integrity = metrics["trace_integrity"]
    lines.extend(
        [
            "",
            "## Span Tree",
            "",
            f"- Root span: `{metrics['span_tree']['root']['span_id']}`",
            f"- Child spans: {metrics['span_tree']['summary']['spans']}",
            f"- Max depth: {metrics['span_tree']['summary']['max_depth']}",
            "",
            "| Span | Parent | Previous | Check | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for span in metrics["span_tree"]["spans"]:
        lines.append(
            "| "
            f"{_markdown_cell(span['span_id'])} | "
            f"{_markdown_cell(span['parent_id'])} | "
            f"{_markdown_cell(span['previous_span_id'] or '')} | "
            f"{_markdown_cell(span['name'])} | "
            f"{_markdown_cell(span['status'])} |"
        )

    lines.extend(
        [
            "",
            "## Trace Integrity",
            "",
            f"- OK: `{str(trace_integrity['ok']).lower()}`",
        ]
    )
    issues = trace_integrity["issues"]
    if issues:
        lines.extend(f"- Issue: `{_markdown_cell(issue)}`" for issue in issues)
    else:
        lines.append("- Issues: none")
    lines.append("")
    return "\n".join(lines)


def format_html(metrics: dict[str, Any]) -> str:
    summary = metrics["summary"]
    timing = summary["timing"]
    usage = summary["usage"]
    path_depth = summary["path_depth"]
    runtime_rows = "\n".join(
        f"<tr><td>{_html_cell(kind)}</td><td>{count}</td></tr>"
        for kind, count in summary["runtime_kinds"].items()
    ) or "<tr><td>none</td><td>0</td></tr>"
    check_rows = "\n".join(
        "<tr>"
        f"<td>{_html_cell(check['name'])}</td>"
        f"<td>{_html_cell(check['command_kind'])}</td>"
        f"<td>{str(check['ok']).lower()}</td>"
        f"<td>{_html_cell(check['cwd'])}</td>"
        f"<td>{'' if check['duration_seconds'] is None else check['duration_seconds']}</td>"
        f"<td>{'' if check['total_tokens'] is None else check['total_tokens']}</td>"
        f"<td>{'' if check['cost_usd'] is None else check['cost_usd']}</td>"
        f"<td>{check['command_path_depth']}</td>"
        "</tr>"
        for check in metrics["checks"]
    )
    issues = metrics["trace_integrity"]["issues"]
    issue_items = "\n".join(f"<li>{_html_cell(issue)}</li>" for issue in issues) or "<li>none</li>"
    span_rows = "\n".join(
        "<tr>"
        f"<td>{_html_cell(span['span_id'])}</td>"
        f"<td>{_html_cell(span['parent_id'])}</td>"
        f"<td>{_html_cell(span['previous_span_id'] or '')}</td>"
        f"<td>{_html_cell(span['name'])}</td>"
        f"<td>{_html_cell(span['status'])}</td>"
        "</tr>"
        for span in metrics["span_tree"]["spans"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MCP Smoke Trace Metrics</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    h1, h2 {{ color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
    .ok {{ color: #047857; font-weight: 700; }}
    .fail {{ color: #b91c1c; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>MCP Smoke Trace Metrics</h1>
  <h2>Source</h2>
  <ul>
    <li>Smoke report: <code>{_html_cell(metrics['source_path'])}</code></li>
    <li>Scope: <code>{_html_cell(metrics['scope'])}</code></li>
    <li>Source status: <code>{_html_cell(metrics.get('source_status'))}</code></li>
    <li>Source generated at: <code>{_html_cell(metrics.get('source_generated_at'))}</code></li>
  </ul>
  <h2>Summary</h2>
  <ul>
    <li>Checks: {summary['checks']}</li>
    <li>Passed: {summary['passed']}</li>
    <li>Failed: {summary['failed']}</li>
    <li>Timing observed: {timing['observed_checks']} observed, {timing['missing_checks']} missing</li>
    <li>Total observed seconds: {_html_cell(timing['total_seconds'])}</li>
    <li>Slowest check: {_html_cell(timing['slowest_check'])} ({_html_cell(timing['max_seconds'])}s)</li>
    <li>Usage observed: {usage['observed_checks']} observed, {usage['missing_checks']} missing</li>
    <li>Total tokens: {_html_cell(usage['total_tokens'])}</li>
    <li>Cost USD: {_html_cell(usage['cost_usd'])}</li>
    <li>Costliest check: {_html_cell(usage['costliest_check'])} ({_html_cell(usage['max_cost_usd'])} USD)</li>
    <li>Max cwd depth: {path_depth['max_cwd_depth']}</li>
    <li>Max command path depth: {path_depth['max_command_path_depth']}</li>
    <li>Command path tokens: {path_depth['command_path_tokens']}</li>
  </ul>
  <h2>Runtime Kinds</h2>
  <table>
    <thead><tr><th>Kind</th><th>Count</th></tr></thead>
    <tbody>
{runtime_rows}
    </tbody>
  </table>
  <h2>Checks</h2>
  <table>
    <thead><tr><th>Check</th><th>Kind</th><th>OK</th><th>CWD</th><th>Duration seconds</th><th>Total tokens</th><th>Cost USD</th><th>Command path depth</th></tr></thead>
    <tbody>
{check_rows}
    </tbody>
  </table>
  <h2>Span Tree</h2>
  <ul>
    <li>Root span: {_html_cell(metrics['span_tree']['root']['span_id'])}</li>
    <li>Child spans: {metrics['span_tree']['summary']['spans']}</li>
    <li>Max depth: {metrics['span_tree']['summary']['max_depth']}</li>
  </ul>
  <table>
    <thead><tr><th>Span</th><th>Parent</th><th>Previous</th><th>Check</th><th>Status</th></tr></thead>
    <tbody>
{span_rows}
    </tbody>
  </table>
  <h2>Trace Integrity</h2>
  <p class="{'ok' if metrics['trace_integrity']['ok'] else 'fail'}">OK: {str(metrics['trace_integrity']['ok']).lower()}</p>
  <ul>
{issue_items}
  </ul>
</body>
</html>
"""


_NANOS_PER_SECOND = 1_000_000_000
# Floor so zero/unknown-duration spans still render with visible extent in collectors.
_MIN_SPAN_DURATION_NS = 1_000_000


def _otel_base_epoch_ns(metrics: dict[str, Any]) -> int:
    generated_at = metrics.get("source_generated_at")
    if generated_at:
        try:
            parsed = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return int(parsed.timestamp() * _NANOS_PER_SECOND)
    return time.time_ns()


def _span_duration_ns(duration_seconds: Any) -> int:
    if isinstance(duration_seconds, (int, float)) and not isinstance(duration_seconds, bool) and duration_seconds > 0:
        return max(int(duration_seconds * _NANOS_PER_SECOND), _MIN_SPAN_DURATION_NS)
    return _MIN_SPAN_DURATION_NS


def _otel_time_fields(start_ns: int, end_ns: int) -> dict[str, str]:
    return {"startTimeUnixNano": str(start_ns), "endTimeUnixNano": str(end_ns)}


def format_otel_json(metrics: dict[str, Any]) -> dict[str, Any]:
    # Mix the source report's generation time into the trace id so each smoke run
    # submits a distinct trace; identical resubmits of one report stay idempotent.
    discriminator = metrics.get("source_generated_at") or ""
    trace_id = _stable_hex(f"{discriminator}:{metrics['source_path']}:{metrics['scope']}", 32)
    base_ns = _otel_base_epoch_ns(metrics)
    children: list[dict[str, Any]] = []
    cursor_ns = base_ns
    for span in metrics["span_tree"]["spans"]:
        duration_ns = _span_duration_ns(span.get("duration_seconds"))
        children.append(
            {
                "traceId": trace_id,
                "spanId": _stable_hex(span["span_id"], 16),
                "parentSpanId": _stable_hex(span["parent_id"], 16),
                "name": span["name"],
                **_otel_time_fields(cursor_ns, cursor_ns + duration_ns),
                "kind": "SPAN_KIND_INTERNAL",
                "status": {"code": _otel_status(span["status"])},
                "attributes": _otel_attributes(
                    {
                        "mcp.span_id": span["span_id"],
                        "mcp.parent_span_id": span["parent_id"],
                        "mcp.previous_span_id": span["previous_span_id"],
                        "mcp.command_kind": span["command_kind"],
                        "mcp.cwd": span["cwd"],
                        "mcp.duration_seconds": span["duration_seconds"],
                    }
                ),
            }
        )
        cursor_ns += duration_ns
    root_span = metrics["span_tree"]["root"]
    root_end_ns = max(cursor_ns, base_ns + _MIN_SPAN_DURATION_NS)
    spans = [
        {
            "traceId": trace_id,
            "spanId": _stable_hex(root_span["span_id"], 16),
            "name": root_span["name"],
            **_otel_time_fields(base_ns, root_end_ns),
            "kind": "SPAN_KIND_INTERNAL",
            "status": {"code": _otel_status(root_span["status"])},
            "attributes": _otel_attributes(
                {
                    "mcp.scope": metrics["scope"],
                    "mcp.source_path": metrics["source_path"],
                    "mcp.source_status": metrics.get("source_status"),
                    "mcp.child_spans": metrics["span_tree"]["summary"]["spans"],
                }
            ),
        },
        *children,
    ]
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _otel_attributes(
                        {
                            "service.name": "mcp-smoke-trace-metrics",
                            "service.namespace": "local-ai-workspace",
                        }
                    )
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "ops.scripts.mcp_smoke_trace_metrics"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def submit_otel_json(
    otel_payload: dict[str, Any],
    endpoint: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "mcp-smoke-trace-metrics/1",
    }
    if headers:
        request_headers.update(headers)
    request_body = json.dumps(otel_payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(endpoint, data=request_body, headers=request_headers, method="POST")
    report: dict[str, Any] = {
        "schema_version": 1,
        "endpoint": endpoint,
        "ok": False,
        "status_code": None,
        "request_bytes": len(request_body),
        "request_header_names": sorted(request_headers),
        "response_content_type": None,
        "response_body_preview": "",
        "error": None,
    }

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read(4096)
            report["status_code"] = response.status
            report["ok"] = 200 <= response.status < 300
            report["response_content_type"] = response.headers.get("Content-Type")
            report["response_body_preview"] = _decode_preview(response_body)
    except urllib.error.HTTPError as exc:
        response_body = exc.read(4096)
        report["status_code"] = exc.code
        report["response_content_type"] = exc.headers.get("Content-Type")
        report["response_body_preview"] = _decode_preview(response_body)
        report["error"] = f"HTTP {exc.code}"
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        report["error"] = str(exc)

    return report


def _check_metrics(result: dict[str, Any]) -> dict[str, Any]:
    command = str(result.get("command") or "")
    cwd = str(result.get("cwd") or "")
    duration = extract_duration(result)
    usage = extract_usage(result)
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
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": usage["cost_usd"],
        "usage_sources": usage["sources"],
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


def _usage_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [
        check
        for check in checks
        if check["input_tokens"] is not None
        or check["output_tokens"] is not None
        or check["total_tokens"] is not None
        or check["cost_usd"] is not None
    ]
    token_observed = [check for check in checks if check["total_tokens"] is not None]
    cost_observed = [check for check in checks if check["cost_usd"] is not None]
    heaviest = max(token_observed, key=lambda item: item["total_tokens"], default=None)
    costliest = max(cost_observed, key=lambda item: item["cost_usd"], default=None)
    input_total = _sum_optional_int(check["input_tokens"] for check in checks)
    output_total = _sum_optional_int(check["output_tokens"] for check in checks)
    token_total = _sum_optional_int(check["total_tokens"] for check in checks)
    cost_total = _sum_optional_float(check["cost_usd"] for check in checks)
    return {
        "observed_checks": len(observed),
        "missing_checks": len(checks) - len(observed),
        "input_tokens": input_total,
        "output_tokens": output_total,
        "total_tokens": token_total,
        "cost_usd": _round_cost(cost_total) if cost_total is not None else None,
        "max_tokens": heaviest["total_tokens"] if heaviest else None,
        "token_heaviest_check": heaviest["name"] if heaviest else None,
        "max_cost_usd": costliest["cost_usd"] if costliest else None,
        "costliest_check": costliest["name"] if costliest else None,
    }


def _span_tree(checks: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    root_span_id = f"{scope}:root"
    spans: list[dict[str, Any]] = []
    previous_span_id: str | None = None
    for index, check in enumerate(checks, start=1):
        span_id = f"{scope}:check:{index}"
        span = {
            "span_id": span_id,
            "parent_id": root_span_id,
            "previous_span_id": previous_span_id,
            "name": check["name"],
            "status": "ok" if check["ok"] is True else "error",
            "duration_seconds": check["duration_seconds"],
            "command_kind": check["command_kind"],
            "cwd": check["cwd"],
        }
        spans.append(span)
        previous_span_id = span_id
    return {
        "root": {
            "span_id": root_span_id,
            "parent_id": None,
            "name": f"{scope} smoke",
            "status": "ok" if all(check["ok"] is True for check in checks) else "error",
        },
        "summary": {
            "spans": len(spans),
            "max_depth": 1 if spans else 0,
            "linked_spans": sum(1 for span in spans if span["previous_span_id"] is not None),
        },
        "spans": spans,
    }


def _path_depth_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "max_cwd_depth": max((check["cwd_depth"] for check in checks), default=0),
        "max_command_path_depth": max((check["command_path_depth"] for check in checks), default=0),
        "command_path_tokens": sum(check["command_path_tokens"] for check in checks),
    }


def _first_number(
    result: dict[str, Any],
    usage: dict[str, Any],
    fields: tuple[str, ...],
    *,
    integer: bool,
) -> tuple[int | float | None, str | None]:
    for container, prefix in ((result, ""), (usage, "usage.")):
        for field in fields:
            value = _number_value(container.get(field), integer=integer)
            if value is not None:
                return value, f"{prefix}{field}"
    return None, None


def _number_value(value: Any, *, integer: bool) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return int(value) if integer else float(value)
    return None


def _sum_optional_int(values: Any) -> int | None:
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _sum_optional_float(values: Any) -> float | None:
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _round_cost(value: float) -> float:
    return round(value, 6)


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


def _markdown_value(value: Any) -> str:
    return "`None`" if value is None else f"`{_markdown_cell(str(value))}`"


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _html_cell(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _decode_preview(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").replace("\r", " ").replace("\n", " ")[:512]


def _stable_hex(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _otel_status(status: str) -> str:
    return "STATUS_CODE_OK" if status == "ok" else "STATUS_CODE_ERROR"


def _otel_attributes(values: dict[str, Any]) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            wrapped = {"boolValue": value}
        elif isinstance(value, int):
            wrapped = {"intValue": str(value)}
        elif isinstance(value, float):
            wrapped = {"doubleValue": value}
        else:
            wrapped = {"stringValue": str(value)}
        attributes.append({"key": key, "value": wrapped})
    return attributes


def _parse_submit_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"header {value!r} must use NAME=VALUE")
        name, header_value = value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("header name must not be empty")
        headers[name] = header_value.strip()
    return headers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build MCP trace metrics from workspace-smoke JSON.")
    parser.add_argument("smoke_json", help="Path to a schema v1 workspace smoke JSON report.")
    parser.add_argument("--scope", default="mcp", help="Scope to summarize. Defaults to mcp.")
    parser.add_argument("--json-out", help="Optional output path for the metrics JSON.")
    parser.add_argument("--markdown-out", help="Optional output path for a Markdown metrics report.")
    parser.add_argument("--html-out", help="Optional output path for a standalone HTML metrics report.")
    parser.add_argument("--otel-json-out", help="Optional output path for an OTEL-style JSON span export.")
    parser.add_argument("--otel-submit-url", help="Optional OTLP/HTTP JSON traces endpoint to POST the OTEL export.")
    parser.add_argument("--otel-submit-timeout-seconds", type=float, default=10.0, help="Timeout for OTEL submission. Defaults to 10.")
    parser.add_argument("--otel-submit-header", action="append", default=[], help="Extra OTEL submit header as NAME=VALUE. May be repeated.")
    parser.add_argument("--otel-submit-report-out", help="Optional JSON report path for OTEL submit result.")
    parser.add_argument("--allow-otel-submit-failure", action="store_true", help="Return success even when OTEL submission fails.")
    parser.add_argument("--allow-issues", action="store_true", help="Return success even when trace integrity issues exist.")
    args = parser.parse_args(argv)
    if args.otel_submit_report_out and not args.otel_submit_url:
        parser.error("--otel-submit-report-out requires --otel-submit-url")
    try:
        submit_headers = _parse_submit_headers(args.otel_submit_header)
    except ValueError as exc:
        parser.error(str(exc))

    source_path = Path(args.smoke_json)
    payload = load_smoke_report(source_path)
    metrics = build_metrics(payload, source_path=source_path, scope=args.scope)
    if args.markdown_out:
        write_markdown(metrics, Path(args.markdown_out))
    if args.html_out:
        write_html(metrics, Path(args.html_out))
    otel_payload = format_otel_json(metrics) if args.otel_json_out or args.otel_submit_url else None
    if args.otel_json_out and otel_payload is not None:
        Path(args.otel_json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.otel_json_out).write_text(json.dumps(otel_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    submit_report: dict[str, Any] | None = None
    if args.otel_submit_url and otel_payload is not None:
        submit_report = submit_otel_json(
            otel_payload,
            args.otel_submit_url,
            timeout_seconds=args.otel_submit_timeout_seconds,
            headers=submit_headers,
        )
        if args.otel_submit_report_out:
            write_otel_submit_report(submit_report, Path(args.otel_submit_report_out))
    write_metrics(metrics, Path(args.json_out) if args.json_out else None)
    trace_ok = args.allow_issues or metrics["trace_integrity"]["ok"]
    submit_ok = submit_report is None or args.allow_otel_submit_failure or submit_report["ok"]
    return 0 if trace_ok and submit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
