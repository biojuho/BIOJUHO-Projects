from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "mcp_otel_collector_handoff.json"
REQUIRED_SOURCE_FIELDS = {"repo", "url", "docs_url", "observed_pattern"}
REQUIRED_HANDOFF_FIELDS = {
    "status",
    "input_command",
    "validator_command",
    "collector_runtime",
    "default_behavior",
    "operator_decisions_required",
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), "generated_at", errors)
    _validate_source(payload.get("source"), errors)
    _validate_handoff(payload.get("handoff"), errors)
    _validate_string_list(payload.get("required_resource_attributes"), "required_resource_attributes", errors)
    _validate_string_list(payload.get("required_span_attributes"), "required_span_attributes", errors)
    _validate_string_list(payload.get("required_span_fields"), "required_span_fields", errors)
    _validate_pipeline(payload.get("collector_pipeline_candidate"), errors)
    _validate_ab_contract(payload.get("ab_contract"), errors)
    return errors


def build_handoff_report(
    manifest: dict[str, Any],
    otel_jsonl_path: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    required_resource_attributes = manifest.get("required_resource_attributes", [])
    required_span_attributes = manifest.get("required_span_attributes", [])
    required_span_fields = manifest.get("required_span_fields", [])
    counters: Counter[str] = Counter()

    if not otel_jsonl_path.exists():
        errors.append(f"otel_jsonl_path does not exist: {otel_jsonl_path}")
    elif not otel_jsonl_path.is_file():
        errors.append(f"otel_jsonl_path must be a file: {otel_jsonl_path}")
    else:
        _validate_otel_jsonl(
            otel_jsonl_path,
            required_resource_attributes=required_resource_attributes,
            required_span_attributes=required_span_attributes,
            required_span_fields=required_span_fields,
            counters=counters,
            errors=errors,
        )

    if counters["line_count"] == 0 and otel_jsonl_path.exists() and otel_jsonl_path.is_file():
        errors.append("otel_jsonl_path must contain at least one non-empty JSONL line")
    if counters["span_count"] == 0 and counters["line_count"] > 0:
        errors.append("otel_jsonl_path must contain at least one span")

    source = manifest.get("source", {}) if isinstance(manifest.get("source"), dict) else {}
    handoff = manifest.get("handoff", {}) if isinstance(manifest.get("handoff"), dict) else {}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if not errors else "fail",
        "source_repo": source.get("repo"),
        "source_url": source.get("url"),
        "source_docs_url": source.get("docs_url"),
        "collector_runtime": handoff.get("collector_runtime"),
        "default_behavior": handoff.get("default_behavior"),
        "manifest_path": _repo_relative(manifest_path),
        "otel_jsonl_path": str(otel_jsonl_path),
        "line_count": counters["line_count"],
        "resource_span_count": counters["resource_span_count"],
        "scope_span_count": counters["scope_span_count"],
        "span_count": counters["span_count"],
        "resource_attribute_hits": {
            name: counters[f"resource_attr:{name}"] for name in required_resource_attributes
        },
        "span_attribute_hits": {
            name: counters[f"span_attr:{name}"] for name in required_span_attributes
        },
        "required_resource_attributes": required_resource_attributes,
        "required_span_attributes": required_span_attributes,
        "required_span_fields": required_span_fields,
        "operator_decisions_required": handoff.get("operator_decisions_required", []),
        "errors": errors,
    }


def run(
    manifest_path: Path,
    otel_jsonl_path: Path,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    report = build_handoff_report(manifest, otel_jsonl_path, manifest_path=manifest_path)
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(report))
    if report["status"] != "pass":
        raise ValueError("\n".join(report["errors"]))
    return report


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MCP OTLP Collector Handoff",
        "",
        f"- Status: `{report['status']}`",
        f"- Source: `{report['source_repo']}`",
        f"- Source URL: {report['source_url']}",
        f"- Source docs: {report['source_docs_url']}",
        f"- Collector runtime: `{report['collector_runtime']}`",
        f"- Default behavior: `{report['default_behavior']}`",
        f"- OTLP JSONL: `{report['otel_jsonl_path']}`",
        f"- Lines: `{report['line_count']}`",
        f"- Resource spans: `{report['resource_span_count']}`",
        f"- Scope spans: `{report['scope_span_count']}`",
        f"- Spans: `{report['span_count']}`",
        "",
        "## Required Resource Attributes",
        "",
    ]
    lines.extend(
        f"- `{name}`: `{report['resource_attribute_hits'].get(name, 0)}`"
        for name in report["required_resource_attributes"]
    )
    lines.extend(["", "## Required Span Attributes", ""])
    lines.extend(
        f"- `{name}`: `{report['span_attribute_hits'].get(name, 0)}`"
        for name in report["required_span_attributes"]
    )
    lines.extend(["", "## Operator Decisions Required", ""])
    lines.extend(f"- {item}" for item in report["operator_decisions_required"])
    lines.extend(["", "## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MCP OTLP JSONL as ready for an operator-owned collector handoff.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--otel-jsonl", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args.manifest, args.otel_jsonl, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"mcp otel collector handoff failed: {exc}", file=sys.stderr)
        return 1
    print(
        "mcp otel collector handoff valid: "
        f"{report['span_count']} spans, "
        f"collector_runtime={report['collector_runtime']}, "
        f"default_behavior={report['default_behavior']}"
    )
    return 0


def _validate_otel_jsonl(
    path: Path,
    *,
    required_resource_attributes: list[str],
    required_span_attributes: list[str],
    required_span_fields: list[str],
    counters: Counter[str],
    errors: list[str],
) -> None:
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        counters["line_count"] += 1
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"line {line_number}: payload must be an object")
            continue
        resource_spans = payload.get("resourceSpans")
        if not isinstance(resource_spans, list) or not resource_spans:
            errors.append(f"line {line_number}: resourceSpans must be a non-empty array")
            continue
        for resource_index, resource_span in enumerate(resource_spans):
            prefix = f"line {line_number} resourceSpans[{resource_index}]"
            _validate_resource_span(
                resource_span,
                prefix=prefix,
                required_resource_attributes=required_resource_attributes,
                required_span_attributes=required_span_attributes,
                required_span_fields=required_span_fields,
                counters=counters,
                errors=errors,
            )


def _validate_resource_span(
    resource_span: Any,
    *,
    prefix: str,
    required_resource_attributes: list[str],
    required_span_attributes: list[str],
    required_span_fields: list[str],
    counters: Counter[str],
    errors: list[str],
) -> None:
    if not isinstance(resource_span, dict):
        errors.append(f"{prefix}: must be an object")
        return
    counters["resource_span_count"] += 1
    resource = resource_span.get("resource")
    resource_attributes = {}
    if isinstance(resource, dict):
        resource_attributes = _attribute_map(resource.get("attributes"))
    for name in required_resource_attributes:
        if name not in resource_attributes:
            errors.append(f"{prefix}: missing resource attribute {name}")
        else:
            counters[f"resource_attr:{name}"] += 1

    scope_spans = resource_span.get("scopeSpans")
    if not isinstance(scope_spans, list) or not scope_spans:
        errors.append(f"{prefix}: scopeSpans must be a non-empty array")
        return
    for scope_index, scope_span in enumerate(scope_spans):
        _validate_scope_span(
            scope_span,
            prefix=f"{prefix}.scopeSpans[{scope_index}]",
            required_span_attributes=required_span_attributes,
            required_span_fields=required_span_fields,
            counters=counters,
            errors=errors,
        )


def _validate_scope_span(
    scope_span: Any,
    *,
    prefix: str,
    required_span_attributes: list[str],
    required_span_fields: list[str],
    counters: Counter[str],
    errors: list[str],
) -> None:
    if not isinstance(scope_span, dict):
        errors.append(f"{prefix}: must be an object")
        return
    counters["scope_span_count"] += 1
    spans = scope_span.get("spans")
    if not isinstance(spans, list) or not spans:
        errors.append(f"{prefix}: spans must be a non-empty array")
        return
    for span_index, span in enumerate(spans):
        _validate_span(
            span,
            prefix=f"{prefix}.spans[{span_index}]",
            required_span_attributes=required_span_attributes,
            required_span_fields=required_span_fields,
            counters=counters,
            errors=errors,
        )


def _validate_span(
    span: Any,
    *,
    prefix: str,
    required_span_attributes: list[str],
    required_span_fields: list[str],
    counters: Counter[str],
    errors: list[str],
) -> None:
    if not isinstance(span, dict):
        errors.append(f"{prefix}: must be an object")
        return
    counters["span_count"] += 1
    for field in required_span_fields:
        if field not in span:
            errors.append(f"{prefix}: missing span field {field}")
    span_attributes = _attribute_map(span.get("attributes"))
    for name in required_span_attributes:
        if name not in span_attributes:
            errors.append(f"{prefix}: missing span attribute {name}")
        else:
            counters[f"span_attr:{name}"] += 1


def _attribute_map(attributes: Any) -> dict[str, Any]:
    if not isinstance(attributes, list):
        return {}
    values: dict[str, Any] = {}
    for item in attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        values[key] = _unwrap_otel_value(value)
    return values


def _unwrap_otel_value(value: dict[str, Any]) -> Any:
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return value[key]
    return value


def _validate_source(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("source must be an object")
        return
    for field in sorted(REQUIRED_SOURCE_FIELDS):
        _require_string(value.get(field), f"source.{field}", errors)
    repo = value.get("repo")
    if isinstance(repo, str) and repo.count("/") != 1:
        errors.append("source.repo must use owner/name format")
    url = value.get("url")
    if isinstance(url, str) and not url.startswith("https://github.com/"):
        errors.append("source.url must be a GitHub HTTPS URL")


def _validate_handoff(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("handoff must be an object")
        return
    for field in sorted(REQUIRED_HANDOFF_FIELDS):
        if field == "operator_decisions_required":
            _validate_string_list(value.get(field), f"handoff.{field}", errors)
        else:
            _require_string(value.get(field), f"handoff.{field}", errors)


def _validate_pipeline(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("collector_pipeline_candidate must be an object")
        return
    for field in ("status", "receiver", "processor", "exporter", "reason"):
        _require_string(value.get(field), f"collector_pipeline_candidate.{field}", errors)


def _validate_ab_contract(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("ab_contract must be an object")
        return
    for field in ("baseline", "variant", "primary_kpi", "decision_rule"):
        _require_string(value.get(field), f"ab_contract.{field}", errors)


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")


def _validate_timestamp(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty ISO timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be parseable as ISO datetime")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{field} must include a timezone offset")


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
