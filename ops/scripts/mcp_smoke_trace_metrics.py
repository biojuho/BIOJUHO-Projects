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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

REQUIRED_RESULT_FIELDS = ("scope", "name", "cwd", "command", "returncode", "ok")
NON_EMPTY_RESULT_TEXT_FIELDS = ("scope", "name", "cwd", "command")
DURATION_FIELDS = ("duration_seconds", "elapsed_seconds", "duration", "elapsed")
TEXT_DURATION_FIELDS = ("stdout_tail", "stderr_tail")
INPUT_TOKEN_FIELDS = ("input_tokens", "prompt_tokens", "tokens_input")
OUTPUT_TOKEN_FIELDS = ("output_tokens", "completion_tokens", "tokens_output")
TOTAL_TOKEN_FIELDS = ("total_tokens", "tokens")
COST_FIELDS = ("cost_usd", "estimated_cost_usd", "usd_cost")
USAGE_OBSERVATION_FIELDS = ("input_tokens", "output_tokens", "total_tokens", "cost_usd")
OTEL_STATUS_CODE_OK = "STATUS_CODE_OK"
OTEL_STATUS_CODE_ERROR = "STATUS_CODE_ERROR"
_NANOS_PER_SECOND = 1_000_000_000
# Floor so zero/unknown-duration spans still render with visible extent in collectors.
_MIN_SPAN_DURATION_NS = 1_000_000
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
DURATION_TEXT_PATTERNS = (DURATION_PATTERN, GENERIC_DURATION_PATTERN)
CLOCK_DURATION_PATTERN = re.compile(r"\((?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:\.(?P<fraction>\d+))?\)")
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_MILLISECONDS_PER_SECOND = 1000
_MILLISECOND_UNITS = {"ms", "millisecond", "milliseconds"}
_MINUTE_UNITS = {"m", "min", "mins", "minute", "minutes"}
_PATH_TOKEN_QUOTE_CHARS = "\"'"
_PATH_TOKEN_PUNCTUATION_CHARS = ".,;:()[]{}"
COMMAND_TOKEN_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'|(\S+)')
_OTEL_SERVICE_NAME = "mcp-smoke-trace-metrics"
_OTEL_SERVICE_NAMESPACE = "local-ai-workspace"
_OTEL_SCOPE_NAME = "ops.scripts.mcp_smoke_trace_metrics"
_OTEL_SUBMIT_USER_AGENT = "mcp-smoke-trace-metrics/1"
_OTEL_RESPONSE_PREVIEW_BYTES = 4096
_DECODE_PREVIEW_CHARS = 512
_HTTP_SUCCESS_MIN_STATUS = 200
_HTTP_SUCCESS_EXCLUSIVE_MAX_STATUS = 300
_HTTP_METHOD_POST = "POST"
_OTEL_SUBMIT_DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": _OTEL_SUBMIT_USER_AGENT,
}
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def load_smoke_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    return _validated_smoke_report_payload(path, payload)


def _validated_smoke_report_payload(path: Path, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a schema v1 JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path} must use schema_version 1")
    if not isinstance(payload.get("results"), list):
        raise ValueError(f"{path} is missing a results array")
    return payload


def command_kind(command: str) -> str:
    lower_command = command.lower()
    return next((kind for token, kind in _COMMAND_KIND_RULES if token in lower_command), "other")


_COMMAND_KIND_RULES = (
    ("compileall", "compileall"),
    ("py_compile", "py_compile"),
    ("pytest", "pytest"),
    ("npm", "npm"),
    ("node", "node"),
)


def extract_duration(result: dict[str, Any]) -> dict[str, Any]:
    return _duration_from_result_fields(result) or _duration_from_result_text(result) or _missing_duration_result()


def _duration_from_result_fields(result: dict[str, Any]) -> dict[str, Any] | None:
    for field in DURATION_FIELDS:
        seconds = _duration_field_seconds(result.get(field))
        if seconds is not None:
            return _duration_result(seconds, field)
    return None


def _duration_from_result_text(result: dict[str, Any]) -> dict[str, Any] | None:
    for field in TEXT_DURATION_FIELDS:
        text = _result_text(result, field)
        seconds = _duration_from_text(text)
        if seconds is not None:
            return _duration_result(seconds, field)
    return None


def _duration_result(seconds: float, source: str) -> dict[str, Any]:
    return {"seconds": _round_seconds(seconds), "source": source}


def _missing_duration_result() -> dict[str, Any]:
    return {"seconds": None, "source": None}


def _result_text(result: dict[str, Any], field: str) -> str:
    return str(result.get(field) or "")


def _result_text_stripped(result: dict[str, Any], field: str) -> str:
    return _result_text(result, field).strip()


def path_depth(value: str) -> int:
    parts = _path_parts(value)
    return 0 if _is_current_directory_path(value) else len(parts)


def _is_current_directory_path(value: str) -> bool:
    return value.strip() == "."


def command_path_metrics(command: str) -> dict[str, int]:
    depths = [path_depth(token) for token in _command_tokens(command) if _looks_like_path(token)]
    return {
        "path_tokens": len(depths),
        "max_depth": _max_command_path_depth(depths),
    }


def _max_command_path_depth(depths: list[int]) -> int:
    return max(depths, default=0)


def _unique_usage_sources(sources: Iterable[str | None]) -> list[str]:
    return sorted(source for source in set(sources) if source is not None)


def extract_usage(result: dict[str, Any]) -> dict[str, Any]:
    usage_payload = result.get("usage")
    usage = usage_payload if isinstance(usage_payload, dict) else {}
    input_tokens, input_source = _first_number(result, usage, INPUT_TOKEN_FIELDS, integer=True)
    output_tokens, output_source = _first_number(result, usage, OUTPUT_TOKEN_FIELDS, integer=True)
    total_tokens, total_source = _first_number(result, usage, TOTAL_TOKEN_FIELDS, integer=True)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
        total_source = "derived"

    cost_usd, cost_source = _first_number(result, usage, COST_FIELDS, integer=False)
    sources = _unique_usage_sources((input_source, output_source, total_source, cost_source))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": _rounded_cost_or_none(cost_usd),
        "sources": sources,
    }


def _rounded_cost_or_none(cost_usd: float | None) -> float | None:
    return _round_cost(cost_usd) if cost_usd is not None else None


def _missing_required_result_fields(result: dict[str, Any], index: int) -> list[str]:
    return [f"{_result_container(index)} missing {field}" for field in REQUIRED_RESULT_FIELDS if field not in result]


def _result_container(index: int) -> str:
    return f"results[{index}]"


def _result_field(index: int, field: str) -> str:
    return f"{_result_container(index)}.{field}"


def _empty_result_text_fields(result: dict[str, Any], index: int) -> list[str]:
    return [
        f"{_result_field(index, field)} is empty"
        for field in NON_EMPTY_RESULT_TEXT_FIELDS
        if field in result and not _result_text_stripped(result, field)
    ]


def _result_status_issues(result: dict[str, Any], index: int) -> list[str]:
    ok_value = result.get("ok")
    returncode = result.get("returncode")
    issue_rules = [
        (not isinstance(ok_value, bool), f"{_result_field(index, 'ok')} is not boolean"),
        (not isinstance(returncode, int), f"{_result_field(index, 'returncode')} is not an integer"),
        (
            isinstance(ok_value, bool) and isinstance(returncode, int) and ok_value != (returncode == 0),
            f"{_result_field(index, 'ok')} contradicts returncode",
        ),
    ]
    return [message for failed, message in issue_rules if failed]


def result_issue(result: Any, index: int) -> list[str]:
    if not isinstance(result, dict):
        return [f"{_result_container(index)} is not an object"]

    return (
        _missing_required_result_fields(result, index)
        + _empty_result_text_fields(result, index)
        + _result_status_issues(result, index)
    )


def _metrics_summary(scoped_results: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **_metrics_summary_outcome_fields(scoped_results),
        **_metrics_summary_counter_fields(scoped_results),
        "timing": _timing_summary(checks),
        "usage": _usage_summary(checks),
        "path_depth": _path_depth_summary(checks),
    }


def _metrics_summary_outcome_fields(scoped_results: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for result in scoped_results if result.get("ok") is True)
    failed = sum(1 for result in scoped_results if result.get("ok") is False)
    return {
        "checks": len(scoped_results),
        "passed": passed,
        "failed": failed,
    }


def _metrics_summary_counter_fields(scoped_results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    kind_counts = Counter(command_kind(_result_text(result, "command")) for result in scoped_results)
    cwd_counts = Counter(_result_text(result, "cwd") for result in scoped_results)
    return {
        "runtime_kinds": _sorted_counter(kind_counts),
        "cwd_counts": _sorted_counter(cwd_counts),
    }


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def _metrics_payload(
    payload: dict[str, Any],
    *,
    source_path: Path,
    scope: str,
    scoped_results: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    integrity_issues: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_path": str(source_path),
        "source_status": payload.get("status"),
        "source_generated_at": payload.get("generated_at"),
        "scope": scope,
        "summary": _metrics_summary(scoped_results, checks),
        "checks": checks,
        "span_tree": _span_tree(checks, scope=scope),
        "trace_integrity": {
            "ok": not integrity_issues,
            "issues": integrity_issues,
        },
    }


def _integrity_issues_for_scope(
    all_results: list[Any],
    scoped_results: list[dict[str, Any]],
    scope: str,
) -> list[str]:
    result_issues = [issue for index, result in enumerate(all_results) for issue in result_issue(result, index)]
    scope_issues = [] if scoped_results else [f"no results found for scope {scope!r}"]
    return result_issues + scope_issues


def build_metrics(payload: dict[str, Any], *, source_path: Path, scope: str = "mcp") -> dict[str, Any]:
    all_results = payload["results"]
    scoped_results = [
        result for result in all_results if isinstance(result, dict) and _result_text_stripped(result, "scope") == scope
    ]
    integrity_issues = _integrity_issues_for_scope(all_results, scoped_results, scope)
    checks = [_check_metrics(result) for result in scoped_results]

    return _metrics_payload(
        payload,
        source_path=source_path,
        scope=scope,
        scoped_results=scoped_results,
        checks=checks,
        integrity_issues=integrity_issues,
    )


def write_metrics(metrics: dict[str, Any], out_path: Path | None) -> None:
    if out_path is None:
        print(_pretty_json_text(metrics))
        return
    _write_pretty_json_file(metrics, out_path)


def write_markdown(metrics: dict[str, Any], out_path: Path) -> None:
    _write_text_file(out_path, format_markdown(metrics))


def write_html(metrics: dict[str, Any], out_path: Path) -> None:
    _write_text_file(out_path, format_html(metrics))


def _write_otel_payload(payload: dict[str, Any], out_path: Path) -> None:
    _write_pretty_json_file(payload, out_path)


def write_otel_json(metrics: dict[str, Any], out_path: Path) -> None:
    _write_otel_payload(format_otel_json(metrics), out_path)


def write_otel_submit_report(report: dict[str, Any], out_path: Path) -> None:
    _write_pretty_json_file(report, out_path)


def _write_pretty_json_file(payload: dict[str, Any], out_path: Path) -> None:
    _write_text_file(out_path, _pretty_json_text(payload) + "\n")


def _write_text_file(out_path: Path, text: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


def _pretty_json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _formatted_check_cells(
    check: dict[str, Any],
    text_cell: Callable[[Any], str],
) -> list[Any]:
    duration_cell = _blank_if_none(check["duration_seconds"])
    total_tokens_cell = _blank_if_none(check["total_tokens"])
    cost_usd_cell = _blank_if_none(check["cost_usd"])
    return [
        text_cell(check["name"]),
        text_cell(check["command_kind"]),
        _bool_text(check["ok"]),
        text_cell(check["cwd"]),
        duration_cell,
        total_tokens_cell,
        cost_usd_cell,
        check["command_path_depth"],
    ]


def _markdown_table_row(cells: Iterable[Any]) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def _formatted_span_cells(
    span: dict[str, Any],
    text_cell: Callable[[Any], str],
) -> list[str]:
    return [
        text_cell(_span_id(span)),
        text_cell(span["parent_id"]),
        text_cell(span["previous_span_id"] or ""),
        text_cell(span["name"]),
        text_cell(span["status"]),
    ]


def _html_table_row(cells: Iterable[Any]) -> str:
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _markdown_source_lines(metrics: dict[str, Any]) -> list[str]:
    return [
        "# MCP Smoke Trace Metrics",
        "",
        "## Source",
        "",
        _markdown_bullet("Smoke report", _markdown_value(metrics["source_path"])),
        _markdown_bullet("Scope", _markdown_value(metrics["scope"])),
        _markdown_bullet("Source status", _markdown_value(metrics.get("source_status"))),
        _markdown_bullet("Source generated at", _markdown_value(metrics.get("source_generated_at"))),
    ]


def _markdown_bullet(label: str, value: Any) -> str:
    return f"- {label}: {value}"


def _markdown_summary_lines(summary: dict[str, Any]) -> list[str]:
    return [
        "",
        "## Summary",
        "",
        *_markdown_summary_metric_lines(summary),
    ]


def _markdown_summary_metric_lines(summary: dict[str, Any]) -> list[str]:
    timing = summary["timing"]
    usage = summary["usage"]
    path_depth = summary["path_depth"]
    return [
        *_markdown_summary_count_lines(summary),
        *_markdown_timing_summary_lines(timing),
        *_markdown_usage_summary_lines(usage),
        *_markdown_path_depth_summary_lines(path_depth),
    ]


def _markdown_path_depth_summary_lines(path_depth: dict[str, Any]) -> list[str]:
    return [
        _markdown_bullet("Max cwd depth", path_depth["max_cwd_depth"]),
        _markdown_bullet("Max command path depth", path_depth["max_command_path_depth"]),
        _markdown_bullet("Command path tokens", path_depth["command_path_tokens"]),
    ]


def _markdown_usage_summary_lines(usage: dict[str, Any]) -> list[str]:
    return [
        _markdown_bullet("Usage observed", _observed_missing_text(usage)),
        _markdown_bullet("Total tokens", _markdown_value(usage["total_tokens"])),
        _markdown_bullet("Cost USD", _markdown_value(usage["cost_usd"])),
        _markdown_bullet(
            "Costliest check",
            _markdown_measurement_text(usage["costliest_check"], usage["max_cost_usd"], " USD"),
        ),
    ]


def _markdown_timing_summary_lines(timing: dict[str, Any]) -> list[str]:
    return [
        _markdown_bullet("Timing observed", _observed_missing_text(timing)),
        _markdown_bullet("Total observed seconds", _markdown_value(timing["total_seconds"])),
        _markdown_bullet(
            "Slowest check",
            _markdown_measurement_text(timing["slowest_check"], timing["max_seconds"], "s"),
        ),
    ]


def _markdown_summary_count_lines(summary: dict[str, Any]) -> list[str]:
    return [
        _markdown_bullet("Checks", summary["checks"]),
        _markdown_bullet("Passed", summary["passed"]),
        _markdown_bullet("Failed", summary["failed"]),
    ]


def _markdown_source_summary_lines(metrics: dict[str, Any]) -> list[str]:
    return _flatten_markdown_sections(
        [
            _markdown_source_lines(metrics),
            _markdown_summary_lines(metrics["summary"]),
        ]
    )


def _markdown_measurement_text(label: Any, value: Any, suffix: str) -> str:
    return f"{_markdown_value(label)} ({_markdown_value(value)}{suffix})"


def _markdown_runtime_kind_lines(runtime_kinds: dict[str, int]) -> list[str]:
    return [
        "",
        "## Runtime Kinds",
        "",
        "| Kind | Count |",
        "| --- | ---: |",
        *_markdown_runtime_kind_rows(runtime_kinds),
    ]


def _markdown_runtime_kind_rows(runtime_kinds: dict[str, int]) -> list[str]:
    if not runtime_kinds:
        return [_markdown_table_row(["none", 0])]
    return [_markdown_runtime_kind_row(kind, count) for kind, count in runtime_kinds.items()]


def _markdown_runtime_kind_row(kind: str, count: int) -> str:
    return _markdown_table_row([_markdown_cell(kind), count])


def _markdown_check_lines(checks: list[dict[str, Any]]) -> list[str]:
    return [
        "",
        "## Checks",
        "",
        "| Check | Kind | OK | CWD | Duration seconds | Total tokens | Cost USD | Command path depth |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        *[_markdown_table_row(_formatted_check_cells(check, _markdown_cell)) for check in checks],
    ]


def _markdown_span_tree_lines(span_tree: dict[str, Any]) -> list[str]:
    return [
        "",
        "## Span Tree",
        "",
        _markdown_bullet("Root span", f"`{span_tree['root']['span_id']}`"),
        _markdown_bullet("Child spans", span_tree["summary"]["spans"]),
        _markdown_bullet("Max depth", span_tree["summary"]["max_depth"]),
        "",
        "| Span | Parent | Previous | Check | Status |",
        "| --- | --- | --- | --- | --- |",
        *[_markdown_table_row(_formatted_span_cells(span, _markdown_cell)) for span in span_tree["spans"]],
    ]


def _markdown_trace_integrity_lines(trace_integrity: dict[str, Any]) -> list[str]:
    return [
        "",
        "## Trace Integrity",
        "",
        f"- OK: `{_bool_text(trace_integrity['ok'])}`",
        *(
            [_markdown_trace_issue_line(issue) for issue in trace_integrity["issues"]]
            if trace_integrity["issues"]
            else ["- Issues: none"]
        ),
        "",
    ]


def _markdown_trace_issue_line(issue: str) -> str:
    return _markdown_bullet("Issue", _markdown_code_value(issue))


def format_markdown(metrics: dict[str, Any]) -> str:
    summary = metrics["summary"]
    lines = _flatten_markdown_sections(_markdown_sections(metrics, summary))
    return "\n".join(lines)


def _markdown_sections(metrics: dict[str, Any], summary: dict[str, Any]) -> list[list[str]]:
    return [
        _markdown_source_summary_lines(metrics),
        _markdown_runtime_kind_lines(summary["runtime_kinds"]),
        _markdown_check_lines(metrics["checks"]),
        _markdown_span_tree_lines(metrics["span_tree"]),
        _markdown_trace_integrity_lines(metrics["trace_integrity"]),
    ]


def _flatten_markdown_sections(sections: list[list[str]]) -> list[str]:
    return [line for section in sections for line in section]


def _html_runtime_rows(runtime_kinds: dict[str, int]) -> str:
    return _html_fragments_or_empty(
        (_html_runtime_row(kind, count) for kind, count in runtime_kinds.items()),
        _html_table_row(["none", 0]),
    )


def _html_runtime_row(kind: str, count: int) -> str:
    return _html_table_row([_html_cell(kind), count])


def _html_check_rows(checks: list[dict[str, Any]]) -> str:
    return _join_html_fragments(_html_table_row(_formatted_check_cells(check, _html_cell)) for check in checks)


def _html_span_rows(spans: list[dict[str, Any]]) -> str:
    return _join_html_fragments(_html_table_row(_formatted_span_cells(span, _html_cell)) for span in spans)


def _html_issue_items(issues: list[str]) -> str:
    return _html_fragments_or_empty(
        (_html_issue_item(issue) for issue in issues),
        _html_list_item("none"),
    )


def _join_html_fragments(fragments: Iterable[str]) -> str:
    return "\n".join(fragments)


def _html_fragments_or_empty(fragments: Iterable[str], empty_fragment: str) -> str:
    return _join_html_fragments(fragments) or empty_fragment


def _html_issue_item(issue: str) -> str:
    return _html_list_item(_html_cell(issue))


def _html_list_item(content: Any) -> str:
    return f"<li>{content}</li>"


def _html_source_section(metrics: dict[str, Any]) -> str:
    return f"""{_html_heading(1, "MCP Smoke Trace Metrics")}
{_html_heading_2("Source")}
{_html_unordered_list(_html_source_items(metrics))}"""


def _html_heading(level: int, text: str) -> str:
    return f"  <h{level}>{text}</h{level}>"


def _html_unordered_list(items: str, item_indent: str = "    ") -> str:
    return f"""  <ul>
{item_indent}{items}
  </ul>"""


def _html_source_items(metrics: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_list_item(f"Smoke report: <code>{_html_cell(metrics['source_path'])}</code>"),
            _html_list_item(f"Scope: <code>{_html_cell(metrics['scope'])}</code>"),
            _html_list_item(f"Source status: <code>{_html_cell(metrics.get('source_status'))}</code>"),
            _html_list_item(f"Source generated at: <code>{_html_cell(metrics.get('source_generated_at'))}</code>"),
        ]
    )


def _html_summary_section(summary: dict[str, Any]) -> str:
    return f"""{_html_heading_2("Summary")}
{_html_unordered_list(_html_summary_items(summary))}"""


def _html_summary_items(summary: dict[str, Any]) -> str:
    timing = summary["timing"]
    usage = summary["usage"]
    path_depth = summary["path_depth"]
    return _join_indented_html_items(
        [
            _html_summary_count_items(summary),
            _html_timing_summary_items(timing),
            _html_usage_summary_items(usage),
            _html_path_depth_summary_items(path_depth),
        ]
    )


def _html_summary_count_items(summary: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_raw_mapping_item("Checks", summary, "checks"),
            _html_raw_mapping_item("Passed", summary, "passed"),
            _html_raw_mapping_item("Failed", summary, "failed"),
        ]
    )


def _join_indented_html_items(items: Iterable[str]) -> str:
    return "\n    ".join(items)


def _html_timing_summary_items(timing: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_list_item(f"Timing observed: {_observed_missing_text(timing)}"),
            _html_list_item(f"Total observed seconds: {_html_cell(timing['total_seconds'])}"),
            _html_list_item(
                "Slowest check: " + _html_measurement_text(timing["slowest_check"], timing["max_seconds"], "s")
            ),
        ]
    )


def _html_usage_summary_items(usage: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_list_item(f"Usage observed: {_observed_missing_text(usage)}"),
            _html_list_item(f"Total tokens: {_html_cell(usage['total_tokens'])}"),
            _html_list_item(f"Cost USD: {_html_cell(usage['cost_usd'])}"),
            _html_list_item(
                "Costliest check: " + _html_measurement_text(usage["costliest_check"], usage["max_cost_usd"], " USD")
            ),
        ]
    )


def _html_path_depth_summary_items(path_depth: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_raw_mapping_item("Max cwd depth", path_depth, "max_cwd_depth"),
            _html_raw_mapping_item("Max command path depth", path_depth, "max_command_path_depth"),
            _html_raw_mapping_item("Command path tokens", path_depth, "command_path_tokens"),
        ]
    )


def _html_raw_mapping_item(label: str, mapping: dict[str, Any], key: str) -> str:
    return _html_list_item(f"{label}: {mapping[key]}")


def _observed_missing_text(summary: dict[str, Any]) -> str:
    return f"{summary['observed_checks']} observed, {summary['missing_checks']} missing"


def _html_measurement_text(label: Any, value: Any, suffix: str) -> str:
    return f"{_html_cell(label)} ({_html_cell(value)}{suffix})"


def _html_style_block() -> str:
    return """  <style>
    body { font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }
    h1, h2 { color: #111827; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }
    th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; }
    th { background: #f3f4f6; }
    code { background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }
    .ok { color: #047857; font-weight: 700; }
    .fail { color: #b91c1c; font-weight: 700; }
  </style>"""


def _html_runtime_table(runtime_rows: str) -> str:
    return f"""{_html_heading_2("Runtime Kinds")}
{_html_table(_html_runtime_header_cells(), runtime_rows)}"""


def _html_heading_2(text: str) -> str:
    return _html_heading(2, text)


def _html_runtime_header_cells() -> str:
    return _html_header_cells(["Kind", "Count"])


def _html_header_cells(labels: Iterable[str]) -> str:
    return "".join(f"<th>{label}</th>" for label in labels)


def _html_table(header_cells: str, body_rows: str) -> str:
    return f"""  <table>
    <thead><tr>{header_cells}</tr></thead>
    <tbody>
{body_rows}
    </tbody>
  </table>"""


def _html_checks_table(check_rows: str) -> str:
    return f"""{_html_heading_2("Checks")}
{_html_table(_html_checks_header_cells(), check_rows)}"""


def _html_checks_header_cells() -> str:
    return _html_header_cells(
        [
            "Check",
            "Kind",
            "OK",
            "CWD",
            "Duration seconds",
            "Total tokens",
            "Cost USD",
            "Command path depth",
        ]
    )


def _html_span_tree_section(span_tree: dict[str, Any], span_rows: str) -> str:
    return f"""{_html_heading_2("Span Tree")}
{_html_unordered_list(_html_span_tree_items(span_tree))}
{_html_table(_html_span_header_cells(), span_rows)}"""


def _html_span_header_cells() -> str:
    return _html_header_cells(["Span", "Parent", "Previous", "Check", "Status"])


def _html_span_tree_items(span_tree: dict[str, Any]) -> str:
    return _join_indented_html_items(
        [
            _html_root_span_item(span_tree),
            _html_child_spans_item(span_tree),
            _html_max_depth_item(span_tree),
        ]
    )


def _html_root_span_item(span_tree: dict[str, Any]) -> str:
    return _html_list_item(f"Root span: {_html_cell(span_tree['root']['span_id'])}")


def _html_child_spans_item(span_tree: dict[str, Any]) -> str:
    return _html_list_item(f"Child spans: {span_tree['summary']['spans']}")


def _html_max_depth_item(span_tree: dict[str, Any]) -> str:
    return _html_list_item(f"Max depth: {span_tree['summary']['max_depth']}")


def _html_trace_integrity_section(status_class: str, status_text: str, issue_items: str) -> str:
    return f"""{_html_heading_2("Trace Integrity")}
  <p class="{status_class}">OK: {status_text}</p>
{_html_unordered_list(issue_items, item_indent="")}"""


def _html_body(
    source_summary_html: str,
    runtime_table_html: str,
    checks_table_html: str,
    span_tree_html: str,
    trace_integrity_html: str,
) -> str:
    return f"""<body>
{source_summary_html}
{runtime_table_html}
{checks_table_html}
{span_tree_html}
{trace_integrity_html}
</body>"""


def _html_document(style_html: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MCP Smoke Trace Metrics</title>
{style_html}
</head>
{body_html}
</html>
"""


def _html_trace_integrity_html(trace_integrity: dict[str, Any]) -> str:
    issue_items = _html_issue_items(trace_integrity["issues"])
    trace_status_class = "ok" if trace_integrity["ok"] else "fail"
    trace_status_text = _bool_text(trace_integrity["ok"])
    return _html_trace_integrity_section(trace_status_class, trace_status_text, issue_items)


def _html_body_sections(metrics: dict[str, Any], summary: dict[str, Any]) -> tuple[str, str, str, str, str]:
    span_tree = metrics["span_tree"]
    return (
        _join_html_fragments(
            [
                _html_source_section(metrics),
                _html_summary_section(metrics["summary"]),
            ]
        ),
        _html_runtime_table(_html_runtime_rows(summary["runtime_kinds"])),
        _html_checks_table(_html_check_rows(metrics["checks"])),
        _html_span_tree_section(span_tree, _html_span_rows(span_tree["spans"])),
        _html_trace_integrity_html(metrics["trace_integrity"]),
    )


def format_html(metrics: dict[str, Any]) -> str:
    summary = metrics["summary"]
    style_html = _html_style_block()
    body_html = _html_body(*_html_body_sections(metrics, summary))
    return _html_document(style_html, body_html)


def _otel_root_span_payload(
    metrics: dict[str, Any],
    trace_id: str,
    start_ns: int,
    end_ns: int,
) -> dict[str, Any]:
    root_span = metrics["span_tree"]["root"]
    return {
        "traceId": trace_id,
        "spanId": _otel_span_id(root_span["span_id"]),
        "name": root_span["name"],
        **_otel_time_fields(start_ns, end_ns),
        **_otel_span_kind_status_fields(root_span["status"]),
        "attributes": _otel_attributes(_otel_root_span_attributes(metrics)),
    }


def _otel_root_span_attributes(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcp.scope": metrics["scope"],
        "mcp.source_path": metrics["source_path"],
        "mcp.source_status": metrics.get("source_status"),
        "mcp.child_spans": metrics["span_tree"]["summary"]["spans"],
    }


def _otel_child_span_payload(
    span: dict[str, Any],
    trace_id: str,
    start_ns: int,
    end_ns: int,
) -> dict[str, Any]:
    return {
        "traceId": trace_id,
        "spanId": _otel_span_id(span["span_id"]),
        "parentSpanId": _otel_span_id(span["parent_id"]),
        "name": span["name"],
        **_otel_time_fields(start_ns, end_ns),
        **_otel_span_kind_status_fields(span["status"]),
        "attributes": _otel_attributes(_otel_child_span_attributes(span)),
    }


def _otel_span_kind_status_fields(status: str) -> dict[str, Any]:
    return {
        "kind": "SPAN_KIND_INTERNAL",
        "status": _otel_status_payload(status),
    }


def _otel_child_span_attributes(span: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcp.span_id": span["span_id"],
        "mcp.parent_span_id": span["parent_id"],
        "mcp.previous_span_id": span["previous_span_id"],
        "mcp.command_kind": span["command_kind"],
        "mcp.cwd": span["cwd"],
        "mcp.duration_seconds": span["duration_seconds"],
    }


def _otel_status_payload(status: str) -> dict[str, str]:
    return {"code": _otel_status(status)}


def _otel_span_id(value: str) -> str:
    return _stable_hex(value, 16)


def _otel_spans(metrics: dict[str, Any], trace_id: str) -> list[dict[str, Any]]:
    base_ns = _otel_base_epoch_ns(metrics)
    children = _otel_child_spans(metrics, trace_id, base_ns)
    root_end_ns = max(
        (int(span["endTimeUnixNano"]) for span in children),
        default=base_ns + _MIN_SPAN_DURATION_NS,
    )
    return [_otel_root_span_payload(metrics, trace_id, base_ns, root_end_ns), *children]


def _otel_child_spans(metrics: dict[str, Any], trace_id: str, base_ns: int) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    cursor_ns = base_ns
    for span in metrics["span_tree"]["spans"]:
        duration_ns = _span_duration_ns(span.get("duration_seconds"))
        spans.append(_otel_child_span_payload(span, trace_id, cursor_ns, cursor_ns + duration_ns))
        cursor_ns += duration_ns
    return spans


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


def _otel_resource_spans_payload(spans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _otel_attributes(_otel_resource_attributes())},
                "scopeSpans": _otel_scope_spans(spans),
            }
        ]
    }


def _otel_scope_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "scope": {"name": _OTEL_SCOPE_NAME},
            "spans": spans,
        }
    ]


def _otel_resource_attributes() -> dict[str, str]:
    return {
        "service.name": _OTEL_SERVICE_NAME,
        "service.namespace": _OTEL_SERVICE_NAMESPACE,
    }


def format_otel_json(metrics: dict[str, Any]) -> dict[str, Any]:
    trace_id = _otel_trace_id(metrics)
    spans = _otel_spans(metrics, trace_id)
    return _otel_resource_spans_payload(spans)


def _otel_trace_id(metrics: dict[str, Any]) -> str:
    # Mix the source report's generation time into the trace id so each smoke run
    # submits a distinct trace; identical resubmits of one report stay idempotent.
    discriminator = metrics.get("source_generated_at") or ""
    return _stable_hex(f"{discriminator}:{metrics['source_path']}:{metrics['scope']}", 32)


def _otel_submit_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return {
        **_OTEL_SUBMIT_DEFAULT_HEADERS,
        **_otel_submit_header_overrides(headers),
    }


def _otel_submit_header_overrides(headers: dict[str, str] | None) -> dict[str, str]:
    return headers or {}


def _otel_request_body(otel_payload: dict[str, Any]) -> bytes:
    return json.dumps(otel_payload, ensure_ascii=False).encode("utf-8")


def _initial_otel_submit_report(endpoint: str, request_body: bytes, request_headers: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        **_otel_submit_request_report_fields(endpoint, request_body, request_headers),
        "ok": False,
        **_otel_submit_response_default_fields(),
    }


def _otel_submit_response_default_fields() -> dict[str, Any]:
    return {
        "status_code": None,
        "response_content_type": None,
        "response_body_preview": "",
        "error": None,
    }


def _otel_submit_request_report_fields(
    endpoint: str,
    request_body: bytes,
    request_headers: dict[str, str],
) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "request_bytes": len(request_body),
        "request_header_names": sorted(request_headers),
    }


def _otel_submit_request(
    endpoint: str,
    request_body: bytes,
    request_headers: dict[str, str],
) -> urllib.request.Request:
    return urllib.request.Request(endpoint, data=request_body, headers=request_headers, method=_HTTP_METHOD_POST)


def _otel_submit_request_and_report(
    otel_payload: dict[str, Any],
    endpoint: str,
    headers: dict[str, str] | None,
) -> tuple[urllib.request.Request, dict[str, Any]]:
    request_headers, request_body = _otel_submit_request_parts(otel_payload, headers)
    return (
        _otel_submit_request(endpoint, request_body, request_headers),
        _initial_otel_submit_report(endpoint, request_body, request_headers),
    )


def _otel_submit_request_parts(
    otel_payload: dict[str, Any],
    headers: dict[str, str] | None,
) -> tuple[dict[str, str], bytes]:
    return _otel_submit_headers(headers), _otel_request_body(otel_payload)


def _is_success_status(status: int) -> bool:
    return _HTTP_SUCCESS_MIN_STATUS <= status < _HTTP_SUCCESS_EXCLUSIVE_MAX_STATUS


def _record_otel_response(
    report: dict[str, Any],
    *,
    status_code: int,
    content_type: str | None,
    response_body: bytes,
    ok: bool,
) -> None:
    report.update(
        _otel_response_report_fields(
            status_code=status_code,
            content_type=content_type,
            response_body=response_body,
            ok=ok,
        )
    )


def _otel_response_report_fields(
    *,
    status_code: int,
    content_type: str | None,
    response_body: bytes,
    ok: bool,
) -> dict[str, Any]:
    return {
        "status_code": status_code,
        "ok": ok,
        "response_content_type": content_type,
        "response_body_preview": _decode_preview(response_body),
    }


def _record_opened_otel_response(report: dict[str, Any], response: Any) -> None:
    response_body = _read_otel_response_preview(response)
    _record_otel_response(
        report,
        status_code=response.status,
        content_type=_otel_response_content_type(response),
        response_body=response_body,
        ok=_is_success_status(response.status),
    )


def _record_otel_http_error(report: dict[str, Any], exc: urllib.error.HTTPError) -> None:
    response_body = _read_otel_response_preview(exc)
    _record_otel_response(
        report,
        status_code=exc.code,
        content_type=_otel_response_content_type(exc),
        response_body=response_body,
        ok=report["ok"],
    )
    report["error"] = _otel_http_error_message(exc)


def _otel_http_error_message(exc: urllib.error.HTTPError) -> str:
    return f"HTTP {exc.code}"


def _otel_response_content_type(response: Any) -> str | None:
    return response.headers.get("Content-Type")


def _read_otel_response_preview(response: Any) -> bytes:
    return response.read(_OTEL_RESPONSE_PREVIEW_BYTES)


def submit_otel_json(
    otel_payload: dict[str, Any],
    endpoint: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request, report = _otel_submit_request_and_report(otel_payload, endpoint, headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            _record_opened_otel_response(report, response)
    except urllib.error.HTTPError as exc:
        _record_otel_http_error(report, exc)
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        _record_otel_transport_error(report, exc)

    return report


def _record_otel_transport_error(report: dict[str, Any], exc: Exception) -> None:
    report["error"] = str(exc)


def _usage_metric_fields(usage: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": usage["cost_usd"],
        "usage_sources": usage["sources"],
    }


def _command_path_metric_fields(command_paths: dict[str, int]) -> dict[str, int]:
    return {
        "command_path_tokens": command_paths["path_tokens"],
        "command_path_depth": command_paths["max_depth"],
    }


def _duration_metric_fields(duration: dict[str, Any]) -> dict[str, Any]:
    return {
        "duration_seconds": duration["seconds"],
        "duration_source": duration["source"],
    }


def _result_status_metric_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "ok": result.get("ok"),
    }


def _check_identity_metric_fields(result: dict[str, Any], command: str, cwd: str) -> dict[str, Any]:
    return {
        "name": _result_text(result, "name"),
        "cwd": cwd,
        "cwd_depth": path_depth(cwd),
        "command_kind": command_kind(command),
    }


def _check_metrics(result: dict[str, Any]) -> dict[str, Any]:
    command = _result_text(result, "command")
    cwd = _result_text(result, "cwd")
    duration = extract_duration(result)
    usage = extract_usage(result)
    command_paths = command_path_metrics(command)
    return {
        **_check_identity_metric_fields(result, command, cwd),
        **_command_path_metric_fields(command_paths),
        **_duration_metric_fields(duration),
        **_usage_metric_fields(usage),
        **_result_status_metric_fields(result),
    }


def _observed_durations(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_observed_duration_entry(check) for check in _checks_with_observed_field(checks, "duration_seconds")]


def _observed_duration_entry(check: dict[str, Any]) -> dict[str, Any]:
    return {"name": check["name"], "seconds": check["duration_seconds"]}


def _timing_observation_counts(checks: list[dict[str, Any]], observed: list[dict[str, Any]]) -> dict[str, int]:
    return _observation_counts(checks, observed)


def _slowest_duration_check(observed: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(observed, key=_duration_seconds_key, default=None)


def _duration_seconds_key(item: dict[str, Any]) -> Any:
    return item["seconds"]


def _total_observed_seconds(observed: list[dict[str, Any]]) -> float:
    return sum(item["seconds"] for item in observed)


def _timing_total_summary_fields(observed: list[dict[str, Any]], total: float) -> dict[str, Any]:
    return {
        "total_seconds": _total_seconds_or_none(observed, total),
    }


def _total_seconds_or_none(observed: list[dict[str, Any]], total: float) -> float | None:
    return _round_seconds(total) if observed else None


def _timing_extreme_summary_fields(slowest: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "max_seconds": _field_value_or_none(slowest, "seconds"),
        "slowest_check": _field_value_or_none(slowest, "name"),
    }


def _timing_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    observed = _observed_durations(checks)
    slowest = _slowest_duration_check(observed)
    total = _total_observed_seconds(observed)
    return {
        **_timing_observation_counts(checks, observed),
        **_timing_total_summary_fields(observed, total),
        **_timing_extreme_summary_fields(slowest),
    }


def _usage_observed_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _checks_with_any_observed_field(checks, USAGE_OBSERVATION_FIELDS)


def _checks_with_observed_field(checks: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    return [check for check in checks if check[field] is not None]


def _checks_with_any_observed_field(checks: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [check for check in checks if _check_has_any_observed_field(check, fields)]


def _check_has_any_observed_field(check: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(check[field] is not None for field in fields)


def _usage_totals(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **_usage_token_totals(checks),
        "cost_total": _sum_optional_check_floats(checks, "cost_usd"),
    }


def _usage_token_totals(checks: list[dict[str, Any]]) -> dict[str, int | None]:
    return {
        "input_tokens": _sum_optional_check_ints(checks, "input_tokens"),
        "output_tokens": _sum_optional_check_ints(checks, "output_tokens"),
        "total_tokens": _sum_optional_check_ints(checks, "total_tokens"),
    }


def _sum_optional_check_ints(checks: list[dict[str, Any]], field: str) -> int | None:
    return _sum_optional_int(check[field] for check in checks)


def _sum_optional_check_floats(checks: list[dict[str, Any]], field: str) -> float | None:
    return _sum_optional_float(check[field] for check in checks)


def _token_heaviest_check(checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _max_observed_check(checks, "total_tokens")


def _costliest_check(checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _max_observed_check(checks, "cost_usd")


def _usage_extreme_checks(
    checks: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return _token_heaviest_check(checks), _costliest_check(checks)


def _max_observed_check(checks: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    observed = _checks_with_observed_field(checks, field)
    return max(observed, key=_field_value_key(field), default=None)


def _field_value_key(field: str) -> Callable[[dict[str, Any]], Any]:
    def key(item: dict[str, Any]) -> Any:
        return item[field]

    return key


def _usage_observation_counts(checks: list[dict[str, Any]], observed: list[dict[str, Any]]) -> dict[str, int]:
    return _observation_counts(checks, observed)


def _observation_counts(checks: list[dict[str, Any]], observed: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "observed_checks": len(observed),
        "missing_checks": len(checks) - len(observed),
    }


def _usage_total_summary_fields(totals: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "cost_usd": _rounded_cost_or_none(totals["cost_total"]),
    }


def _usage_extreme_summary_fields(
    heaviest: dict[str, Any] | None,
    costliest: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "max_tokens": _field_value_or_none(heaviest, "total_tokens"),
        "token_heaviest_check": _field_value_or_none(heaviest, "name"),
        "max_cost_usd": _field_value_or_none(costliest, "cost_usd"),
        "costliest_check": _field_value_or_none(costliest, "name"),
    }


def _field_value_or_none(item: dict[str, Any] | None, field: str) -> Any:
    return item[field] if item else None


def _usage_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    observed = _usage_observed_checks(checks)
    heaviest, costliest = _usage_extreme_checks(checks)
    totals = _usage_totals(checks)
    return {
        **_usage_observation_counts(checks, observed),
        **_usage_total_summary_fields(totals),
        **_usage_extreme_summary_fields(heaviest, costliest),
    }


def _check_span(
    *,
    root_span_id: str,
    scope: str,
    index: int,
    check: dict[str, Any],
    previous_span_id: str | None,
) -> dict[str, Any]:
    span_id = _check_span_id(scope, index)
    return {
        "span_id": span_id,
        "parent_id": root_span_id,
        "previous_span_id": previous_span_id,
        "name": check["name"],
        "status": _check_span_status(check),
        "duration_seconds": check["duration_seconds"],
        "command_kind": check["command_kind"],
        "cwd": check["cwd"],
    }


def _check_span_status(check: dict[str, Any]) -> str:
    return _span_status(check["ok"] is True)


def _check_span_id(scope: str, index: int) -> str:
    return f"{scope}:check:{index}"


def _root_span(root_span_id: str, scope: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "span_id": root_span_id,
        "parent_id": None,
        "name": _root_span_name(scope),
        "status": _root_span_status(checks),
    }


def _root_span_name(scope: str) -> str:
    return f"{scope} smoke"


def _root_span_status(checks: list[dict[str, Any]]) -> str:
    return _span_status(all(check["ok"] is True for check in checks))


def _span_status(ok: bool) -> str:
    return "ok" if ok else "error"


def _span_tree_summary(spans: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "spans": _span_count(spans),
        "max_depth": _span_tree_max_depth(spans),
        "linked_spans": _linked_span_count(spans),
    }


def _span_tree_max_depth(spans: list[dict[str, Any]]) -> int:
    return 1 if spans else 0


def _span_count(spans: list[dict[str, Any]]) -> int:
    return len(spans)


def _linked_span_count(spans: list[dict[str, Any]]) -> int:
    return sum(1 for span in spans if _span_has_previous(span))


def _span_has_previous(span: dict[str, Any]) -> bool:
    return span["previous_span_id"] is not None


def _check_spans(root_span_id: str, scope: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    previous_span_id: str | None = None
    for index, check in enumerate(checks, start=1):
        span, previous_span_id = _linked_check_span(
            root_span_id=root_span_id,
            scope=scope,
            index=index,
            check=check,
            previous_span_id=previous_span_id,
        )
        spans.append(span)
    return spans


def _linked_check_span(
    *,
    root_span_id: str,
    scope: str,
    index: int,
    check: dict[str, Any],
    previous_span_id: str | None,
) -> tuple[dict[str, Any], str]:
    span = _check_span(
        root_span_id=root_span_id,
        scope=scope,
        index=index,
        check=check,
        previous_span_id=previous_span_id,
    )
    return span, _span_id(span)


def _span_id(span: dict[str, Any]) -> str:
    return span["span_id"]


def _span_tree(checks: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    root_span_id = _root_span_id(scope)
    spans = _check_spans(root_span_id, scope, checks)
    return _span_tree_payload(root_span_id, scope, checks, spans)


def _span_tree_payload(
    root_span_id: str,
    scope: str,
    checks: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "root": _root_span(root_span_id, scope, checks),
        "summary": _span_tree_summary(spans),
        "spans": spans,
    }


def _root_span_id(scope: str) -> str:
    return f"{scope}:root"


def _path_depth_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        **_cwd_path_summary_fields(checks),
        **_command_path_summary_fields(checks),
    }


def _cwd_path_summary_fields(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "max_cwd_depth": _max_path_depth(checks, "cwd_depth"),
    }


def _command_path_summary_fields(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "max_command_path_depth": _max_path_depth(checks, "command_path_depth"),
        "command_path_tokens": _total_command_path_tokens(checks),
    }


def _max_path_depth(checks: list[dict[str, Any]], field: str) -> int:
    return max((check[field] for check in checks), default=0)


def _total_command_path_tokens(checks: list[dict[str, Any]]) -> int:
    return sum(check["command_path_tokens"] for check in checks)


def _first_number(
    result: dict[str, Any],
    usage: dict[str, Any],
    fields: tuple[str, ...],
    *,
    integer: bool,
) -> tuple[int | float | None, str | None]:
    for container, prefix in _number_sources(result, usage):
        value, source = _first_number_in_source(container, prefix, fields, integer=integer)
        if value is not None:
            return value, source
    return None, None


def _first_number_in_source(
    container: dict[str, Any],
    prefix: str,
    fields: tuple[str, ...],
    *,
    integer: bool,
) -> tuple[int | float | None, str | None]:
    for field in fields:
        value = _number_value(container.get(field), integer=integer)
        if value is not None:
            return value, f"{prefix}{field}"
    return None, None


def _number_sources(
    result: dict[str, Any],
    usage: dict[str, Any],
) -> tuple[tuple[dict[str, Any], str], tuple[dict[str, Any], str]]:
    return (result, ""), (usage, "usage.")


def _number_value(value: Any, *, integer: bool) -> int | float | None:
    if _is_non_negative_number(value):
        return _coerce_number_value(value, integer=integer)
    return None


def _coerce_number_value(value: int | float, *, integer: bool) -> int | float:
    return int(value) if integer else float(value)


def _is_non_negative_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value >= 0


def _sum_optional_int(values: Iterable[int | None]) -> int | None:
    return _sum_observed_values(values)


def _sum_optional_float(values: Iterable[float | None]) -> float | None:
    return _sum_observed_values(values)


def _sum_observed_values[NumberT: (int, float)](values: Iterable[NumberT | None]) -> NumberT | None:
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _round_cost(value: float) -> float:
    return round(value, 6)


def _duration_field_seconds(value: Any) -> float | None:
    if _is_non_negative_number(value):
        return float(value)
    return None


def _duration_from_text(text: str) -> float | None:
    match = _first_duration_text_match(text)
    if match:
        return _duration_value_seconds(match.group("value"), match.group("unit"))
    return _duration_from_clock_text(text)


def _first_duration_text_match(text: str) -> re.Match[str] | None:
    for pattern in DURATION_TEXT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match
    return None


def _duration_from_clock_text(text: str) -> float | None:
    match = CLOCK_DURATION_PATTERN.search(text)
    if not match:
        return None
    return _clock_duration_seconds(match)


def _clock_duration_seconds(match: re.Match[str]) -> float:
    return float(_clock_match_seconds(match) + _clock_fraction_seconds(match))


def _clock_match_seconds(match: re.Match[str]) -> float:
    return (
        int(match.group("hours")) * _SECONDS_PER_HOUR
        + int(match.group("minutes")) * _SECONDS_PER_MINUTE
        + int(match.group("seconds"))
    )


def _clock_fraction_seconds(match: re.Match[str]) -> float:
    fraction = match.group("fraction")
    return float(f"0.{fraction}") if fraction else 0.0


def _duration_value_seconds(value: str, unit: str) -> float:
    return float(value) * _duration_unit_seconds(unit)


def _duration_unit_seconds(unit: str) -> float:
    normalized_unit = unit.lower()
    if normalized_unit in _MILLISECOND_UNITS:
        return 1 / _MILLISECONDS_PER_SECOND
    if normalized_unit in _MINUTE_UNITS:
        return _SECONDS_PER_MINUTE
    return 1.0


def _round_seconds(value: float) -> float:
    return round(value, 3)


def _command_token_from_match(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


def _command_tokens(command: str) -> list[str]:
    return [_command_token_from_match(match) for match in COMMAND_TOKEN_PATTERN.finditer(command)]


def _looks_like_path(value: str) -> bool:
    stripped = _strip_path_token(value)
    if _is_url_like_path_token(stripped):
        return False
    return _has_path_separator(stripped)


def _is_url_like_path_token(value: str) -> bool:
    return "://" in value


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value


def _path_parts(value: str) -> list[str]:
    stripped = _strip_path_token(value)
    if _has_no_path_parts(stripped):
        return []
    normalized = _normalized_path_token(stripped)
    return [part for part in normalized.split("/") if _is_path_part(part)]


def _has_no_path_parts(value: str) -> bool:
    return not value or _is_current_directory_path(value)


def _is_path_part(value: str) -> bool:
    return bool(value) and not _is_current_directory_path(value)


def _normalized_path_token(value: str) -> str:
    normalized = _path_token_with_forward_slashes(value)
    return _strip_windows_drive_prefix(normalized)


def _path_token_with_forward_slashes(value: str) -> str:
    return value.replace("\\", "/")


def _strip_windows_drive_prefix(value: str) -> str:
    return re.sub(r"^[A-Za-z]:/", "", value)


def _strip_path_token(value: str) -> str:
    return _strip_path_token_punctuation(_strip_path_token_quotes(value.strip()))


def _strip_path_token_quotes(value: str) -> str:
    return value.strip(_PATH_TOKEN_QUOTE_CHARS)


def _strip_path_token_punctuation(value: str) -> str:
    return value.strip(_PATH_TOKEN_PUNCTUATION_CHARS)


def _markdown_value(value: Any) -> str:
    return "`None`" if value is None else _markdown_code_value(value)


def _markdown_code_value(value: Any) -> str:
    return f"`{_markdown_cell(value)}`"


def _markdown_cell(value: Any) -> str:
    return _markdown_cell_text(str(value))


def _markdown_cell_text(value: str) -> str:
    return _single_line_text(value.replace("|", "\\|"))


def _html_cell(value: Any) -> str:
    return _html_cell_text(str(value))


def _html_cell_text(value: str) -> str:
    return html.escape(value, quote=True)


def _bool_text(value: bool) -> str:
    return str(value).lower()


def _blank_if_none(value: Any) -> str:
    return "" if value is None else str(value)


def _decode_preview(value: bytes) -> str:
    return _single_line_preview_text(value.decode("utf-8", errors="replace"))


def _single_line_preview_text(value: str) -> str:
    return _single_line_text(value)[:_DECODE_PREVIEW_CHARS]


def _single_line_text(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")


def _stable_hex(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _otel_status(status: str) -> str:
    return OTEL_STATUS_CODE_OK if status == "ok" else OTEL_STATUS_CODE_ERROR


def _otel_attributes(values: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": key, "value": _otel_attribute_value(value)} for key, value in values.items() if value is not None]


def _otel_attribute_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    numeric_value = _otel_numeric_attribute_value(value)
    if numeric_value is not None:
        return numeric_value
    return {"stringValue": str(value)}


def _otel_numeric_attribute_value(value: Any) -> dict[str, Any] | None:
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return None


def _parse_submit_headers(values: list[str]) -> dict[str, str]:
    return dict(_parse_submit_header(value) for value in values)


def _parse_submit_header(value: str) -> tuple[str, str]:
    name, header_value = _split_submit_header(value)
    name = name.strip()
    if not name:
        raise ValueError("header name must not be empty")
    return name, header_value.strip()


def _split_submit_header(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"header {value!r} must use NAME=VALUE")
    return value.split("=", 1)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build MCP trace metrics from workspace-smoke JSON.")
    parser.add_argument("smoke_json", help="Path to a schema v1 workspace smoke JSON report.")
    parser.add_argument("--scope", default="mcp", help="Scope to summarize. Defaults to mcp.")
    parser.add_argument("--json-out", help="Optional output path for the metrics JSON.")
    parser.add_argument("--markdown-out", help="Optional output path for a Markdown metrics report.")
    parser.add_argument("--html-out", help="Optional output path for a standalone HTML metrics report.")
    _add_otel_arguments(parser)
    parser.add_argument(
        "--allow-issues", action="store_true", help="Return success even when trace integrity issues exist."
    )
    return parser


def _add_otel_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--otel-json-out", help="Optional output path for an OTEL-style JSON span export.")
    parser.add_argument("--otel-submit-url", help="Optional OTLP/HTTP JSON traces endpoint to POST the OTEL export.")
    parser.add_argument(
        "--otel-submit-timeout-seconds", type=float, default=10.0, help="Timeout for OTEL submission. Defaults to 10."
    )
    parser.add_argument(
        "--otel-submit-header",
        action="append",
        default=[],
        help="Extra OTEL submit header as NAME=VALUE. May be repeated.",
    )
    parser.add_argument("--otel-submit-report-out", help="Optional JSON report path for OTEL submit result.")
    parser.add_argument(
        "--allow-otel-submit-failure", action="store_true", help="Return success even when OTEL submission fails."
    )


def _parse_otel_submit_headers_from_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> dict[str, str]:
    if args.otel_submit_report_out and not args.otel_submit_url:
        parser.error("--otel-submit-report-out requires --otel-submit-url")
    try:
        return _parse_submit_headers(args.otel_submit_header)
    except ValueError as exc:
        parser.error(str(exc))


def _write_report_if_requested(
    output_path: str | None,
    writer: Callable[[dict[str, Any], Path], None],
    payload: dict[str, Any] | None,
) -> None:
    if output_path and payload is not None:
        writer(payload, Path(output_path))


def _submit_otel_if_requested(
    otel_payload: dict[str, Any] | None,
    *,
    submit_url: str | None,
    timeout_seconds: float,
    headers: dict[str, str],
    submit_report_out: str | None,
) -> dict[str, Any] | None:
    if not _should_submit_otel(otel_payload, submit_url):
        return None
    submit_report = submit_otel_json(
        otel_payload,
        submit_url,
        timeout_seconds=timeout_seconds,
        headers=headers,
    )
    _write_otel_submit_report_if_requested(submit_report, submit_report_out)
    return submit_report


def _should_submit_otel(otel_payload: dict[str, Any] | None, submit_url: str | None) -> bool:
    return bool(submit_url) and otel_payload is not None


def _write_otel_submit_report_if_requested(submit_report: dict[str, Any], submit_report_out: str | None) -> None:
    _write_report_if_requested(submit_report_out, write_otel_submit_report, submit_report)


def _format_otel_payload_if_requested(
    metrics: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    if _needs_otel_payload(args):
        return format_otel_json(metrics)
    return None


def _needs_otel_payload(args: argparse.Namespace) -> Any:
    return args.otel_json_out or args.otel_submit_url


def _write_otel_payload_if_requested(
    otel_payload: dict[str, Any] | None,
    otel_json_out: str | None,
) -> None:
    _write_report_if_requested(otel_json_out, _write_otel_payload, otel_payload)


def _main_exit_code(
    *,
    allow_issues: bool,
    trace_integrity_ok: bool,
    submit_report: dict[str, Any] | None,
    allow_otel_submit_failure: bool,
) -> int:
    return (
        EXIT_SUCCESS
        if _trace_exit_ok(allow_issues, trace_integrity_ok)
        and _submit_exit_ok(submit_report, allow_otel_submit_failure)
        else EXIT_FAILURE
    )


def _trace_exit_ok(allow_issues: bool, trace_integrity_ok: bool) -> bool:
    return allow_issues or trace_integrity_ok


def _submit_exit_ok(submit_report: dict[str, Any] | None, allow_otel_submit_failure: bool) -> bool:
    if submit_report is None:
        return True
    if allow_otel_submit_failure:
        return True
    return bool(submit_report["ok"])


def _build_metrics_from_args(args: argparse.Namespace) -> dict[str, Any]:
    source_path = Path(args.smoke_json)
    payload = load_smoke_report(source_path)
    return build_metrics(payload, source_path=source_path, scope=args.scope)


def _handle_otel_outputs(
    metrics: dict[str, Any],
    args: argparse.Namespace,
    submit_headers: dict[str, str],
) -> dict[str, Any] | None:
    otel_payload = _format_otel_payload_if_requested(metrics, args)
    _write_otel_payload_if_requested(otel_payload, args.otel_json_out)
    return _submit_otel_if_requested(
        otel_payload,
        submit_url=args.otel_submit_url,
        timeout_seconds=args.otel_submit_timeout_seconds,
        headers=submit_headers,
        submit_report_out=args.otel_submit_report_out,
    )


def _parse_args_and_submit_headers(argv: list[str] | None) -> tuple[argparse.Namespace, dict[str, str]]:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    return args, _parse_otel_submit_headers_from_args(parser, args)


def main(argv: list[str] | None = None) -> int:
    args, submit_headers = _parse_args_and_submit_headers(argv)
    metrics = _build_metrics_from_args(args)
    _write_report_if_requested(args.markdown_out, write_markdown, metrics)
    _write_report_if_requested(args.html_out, write_html, metrics)
    submit_report = _handle_otel_outputs(metrics, args, submit_headers)
    write_metrics(metrics, Path(args.json_out) if args.json_out else None)
    return _main_exit_code(
        allow_issues=args.allow_issues,
        trace_integrity_ok=metrics["trace_integrity"]["ok"],
        submit_report=submit_report,
        allow_otel_submit_failure=args.allow_otel_submit_failure,
    )


if __name__ == "__main__":
    raise SystemExit(main())
