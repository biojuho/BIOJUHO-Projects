from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_otel_collector_handoff.py"
HANDOFF_MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "mcp_otel_collector_handoff.json"
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "run_workspace_smoke.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_handoff_module():
    return load_module(HANDOFF_SCRIPT_PATH, "mcp_otel_collector_handoff")


def load_smoke_module():
    return load_module(SMOKE_SCRIPT_PATH, "workspace_smoke_for_handoff")


def make_otel_payload() -> dict[str, object]:
    smoke = load_smoke_module()
    payload = smoke.build_mcp_otel_export(
        [
            smoke.Result("workspace", "workspace regression tests", ".", "python -m pytest tests", 0, True, "ok", ""),
            smoke.Result(
                "mcp",
                "DailyNews unit tests",
                "automation/DailyNews",
                "python -m pytest tests/unit",
                0,
                True,
                "ok",
                "",
                elapsed_seconds=1.25,
                started_at_unix_nano=1000,
                ended_at_unix_nano=2000,
            ),
        ],
        trace_id="3" * 32,
    )
    assert payload is not None
    return payload


def write_jsonl(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "workspace-smoke-mcp.otlp.jsonl"
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")
    return path


def test_current_handoff_manifest_validates() -> None:
    handoff = load_handoff_module()
    manifest = handoff.load_manifest(HANDOFF_MANIFEST_PATH)

    errors = handoff.validate_manifest(manifest)

    assert errors == []
    assert manifest["source"]["repo"] == "open-telemetry/opentelemetry-collector"
    assert manifest["handoff"]["collector_runtime"] == "future_scoped_operator_owned"


def test_run_accepts_workspace_smoke_otel_payload(tmp_path: Path) -> None:
    handoff = load_handoff_module()
    otel_path = write_jsonl(tmp_path, make_otel_payload())
    json_out = tmp_path / "handoff.json"
    markdown_out = tmp_path / "handoff.md"

    report = handoff.run(HANDOFF_MANIFEST_PATH, otel_path, json_out=json_out, markdown_out=markdown_out)

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert report["status"] == "pass"
    assert persisted["span_count"] == 1
    assert persisted["resource_span_count"] == 1
    assert persisted["collector_runtime"] == "future_scoped_operator_owned"
    assert persisted["span_attribute_hits"]["workspace_smoke.command.kind"] == 1
    assert "MCP OTLP Collector Handoff" in markdown
    assert "open-telemetry/opentelemetry-collector" in markdown


def test_build_report_rejects_missing_required_span_attribute(tmp_path: Path) -> None:
    handoff = load_handoff_module()
    manifest = handoff.load_manifest(HANDOFF_MANIFEST_PATH)
    payload = make_otel_payload()
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    span["attributes"] = [
        item for item in span["attributes"] if item["key"] != "workspace_smoke.command"
    ]
    otel_path = write_jsonl(tmp_path, payload)

    report = handoff.build_handoff_report(manifest, otel_path)

    assert report["status"] == "fail"
    assert report["span_count"] == 1
    assert any("missing span attribute workspace_smoke.command" in error for error in report["errors"])


def test_cli_writes_outputs_for_valid_handoff(tmp_path: Path) -> None:
    handoff = load_handoff_module()
    otel_path = write_jsonl(tmp_path, make_otel_payload())
    json_out = tmp_path / "handoff.json"
    markdown_out = tmp_path / "handoff.md"

    exit_code = handoff.main(
        [
            "--manifest",
            str(HANDOFF_MANIFEST_PATH),
            "--otel-jsonl",
            str(otel_path),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "pass"
    assert "Collector runtime" in markdown_out.read_text(encoding="utf-8")
