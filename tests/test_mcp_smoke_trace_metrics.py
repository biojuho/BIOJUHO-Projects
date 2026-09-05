from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_smoke_trace_metrics.py"
CLI_TIMEOUT_SECONDS = 30


def load_metrics_module():
    spec = importlib.util.spec_from_file_location("mcp_smoke_trace_metrics", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def smoke_payload(results: list[dict]) -> dict:
    passed = sum(1 for result in results if result.get("ok") is True)
    failed = sum(1 for result in results if result.get("ok") is False)
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "complete",
        "summary": {
            "total": len(results),
            "completed": len(results),
            "passed": passed,
            "failed": failed,
            "remaining": 0,
        },
        "results": results,
    }


def result(
    name: str,
    command: str,
    *,
    scope: str = "mcp",
    cwd: str = ".",
    returncode: int = 0,
    ok: bool = True,
    stdout_tail: str = "",
    stderr_tail: str = "",
    duration_seconds: float | None = None,
    **extra,
) -> dict:
    payload = {
        "scope": scope,
        "name": name,
        "cwd": cwd,
        "command": command,
        "returncode": returncode,
        "ok": ok,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    payload.update(extra)
    return payload


def test_build_metrics_summarizes_mcp_runtime_kinds(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result("notebooklm compile", "python -m compileall mcp/notebooklm-mcp"),
            result(
                "canva-mcp build",
                "npm.cmd run build",
                cwd="mcp\\canva-mcp",
                returncode=1,
                ok=False,
                stdout_tail="built in 1.17s",
            ),
            result("workspace regression tests", "python -m pytest tests/test_workspace_smoke.py", scope="workspace"),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")

    assert metrics["summary"]["checks"] == 2
    assert metrics["summary"]["passed"] == 1
    assert metrics["summary"]["failed"] == 1
    assert metrics["summary"]["runtime_kinds"] == {"compileall": 1, "npm": 1}
    assert metrics["summary"]["timing"] == {
        "observed_checks": 1,
        "missing_checks": 1,
        "total_seconds": 1.17,
        "max_seconds": 1.17,
        "slowest_check": "canva-mcp build",
    }
    assert metrics["summary"]["usage"] == {
        "observed_checks": 0,
        "missing_checks": 2,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "max_tokens": None,
        "token_heaviest_check": None,
        "max_cost_usd": None,
        "costliest_check": None,
    }
    assert metrics["summary"]["path_depth"]["max_cwd_depth"] == 2
    assert metrics["summary"]["path_depth"]["max_command_path_depth"] == 2
    assert metrics["span_tree"]["root"] == {
        "span_id": "mcp:root",
        "parent_id": None,
        "name": "mcp smoke",
        "status": "error",
    }
    assert metrics["span_tree"]["summary"] == {"spans": 2, "max_depth": 1, "linked_spans": 1}
    assert metrics["span_tree"]["spans"][0]["previous_span_id"] is None
    assert metrics["span_tree"]["spans"][1]["previous_span_id"] == "mcp:check:1"
    assert metrics["trace_integrity"] == {"ok": True, "issues": []}
    assert [check["name"] for check in metrics["checks"]] == ["notebooklm compile", "canva-mcp build"]
    assert metrics["checks"][1]["duration_source"] == "stdout_tail"


def test_build_metrics_reports_trace_integrity_issues(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            {
                "scope": "mcp",
                "name": "broken",
                "cwd": "",
                "command": "",
                "returncode": 0,
                "ok": False,
            }
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")

    assert metrics["trace_integrity"]["ok"] is False
    assert "results[0].cwd is empty" in metrics["trace_integrity"]["issues"]
    assert "results[0].command is empty" in metrics["trace_integrity"]["issues"]
    assert "results[0].ok contradicts returncode" in metrics["trace_integrity"]["issues"]


def test_build_metrics_derives_timing_and_path_depth_from_trace_tails(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result(
                "DailyNews unit tests",
                "python -m pytest tests/unit -q --basetemp var/tmp/pytest-dailynews",
                cwd="automation\\DailyNews",
                stdout_tail="249 passed in 117.48s (0:01:57)",
            ),
            result(
                "canva-mcp build",
                "npm.cmd run build",
                cwd="mcp\\canva-mcp",
                stdout_tail="built in 820ms",
            ),
            result(
                "explicit duration",
                "python -m pytest tests -q",
                duration_seconds=0.375,
            ),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")

    assert metrics["summary"]["timing"] == {
        "observed_checks": 3,
        "missing_checks": 0,
        "total_seconds": 118.675,
        "max_seconds": 117.48,
        "slowest_check": "DailyNews unit tests",
    }
    assert metrics["summary"]["path_depth"] == {
        "max_cwd_depth": 2,
        "max_command_path_depth": 3,
        "command_path_tokens": 2,
    }
    assert [check["duration_seconds"] for check in metrics["checks"]] == [117.48, 0.82, 0.375]
    assert metrics["checks"][2]["duration_source"] == "duration_seconds"


def test_build_metrics_summarizes_optional_token_and_cost_usage(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result(
                "agent eval",
                "python -m pytest tests -q",
                input_tokens=120,
                output_tokens=30,
                cost_usd=0.00123456,
            ),
            result(
                "nested eval",
                "python -m pytest tests -q",
                usage={"prompt_tokens": 50, "completion_tokens": 10, "estimated_cost_usd": 0.002},
            ),
            result("no usage", "python -m pytest tests -q"),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")

    assert metrics["summary"]["usage"] == {
        "observed_checks": 2,
        "missing_checks": 1,
        "input_tokens": 170,
        "output_tokens": 40,
        "total_tokens": 210,
        "cost_usd": 0.003235,
        "max_tokens": 150,
        "token_heaviest_check": "agent eval",
        "max_cost_usd": 0.002,
        "costliest_check": "nested eval",
    }
    assert metrics["checks"][0]["total_tokens"] == 150
    assert metrics["checks"][0]["usage_sources"] == ["cost_usd", "derived", "input_tokens", "output_tokens"]
    assert metrics["checks"][1]["usage_sources"] == [
        "derived",
        "usage.completion_tokens",
        "usage.estimated_cost_usd",
        "usage.prompt_tokens",
    ]


def test_format_markdown_summarizes_metrics_for_handoff(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result(
                "canva|build",
                "npm.cmd run build",
                cwd="mcp\\canva-mcp",
                stdout_tail="built in 820ms",
                total_tokens=88,
                cost_usd=0.0042,
            ),
            result("telegram tests", "python -m pytest tests -q"),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")
    report = metrics_module.format_markdown(metrics)

    assert report.startswith("# MCP Smoke Trace Metrics")
    assert "- Checks: 2" in report
    assert "- Total observed seconds: `0.82`" in report
    assert "- Slowest check: `canva\\|build` (`0.82`s)" in report
    assert "- Usage observed: 1 observed, 1 missing" in report
    assert "- Total tokens: `88`" in report
    assert "- Cost USD: `0.0042`" in report
    assert "| npm | 1 |" in report
    assert "| pytest | 1 |" in report
    assert "| canva\\|build | npm | true | mcp\\canva-mcp | 0.82 | 88 | 0.0042 | 0 |" in report
    assert "## Span Tree" in report
    assert "| mcp:check:2 | mcp:root | mcp:check:1 | telegram tests | ok |" in report
    assert "- OK: `true`" in report
    assert "- Issues: none" in report


def test_format_html_summarizes_metrics_for_ci_report(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result(
                "canva<script>",
                "npm.cmd run build",
                cwd="mcp\\canva-mcp",
                stdout_tail="built in 820ms",
                total_tokens=88,
                cost_usd=0.0042,
            ),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")
    report = metrics_module.format_html(metrics)

    assert report.startswith("<!doctype html>")
    assert "<title>MCP Smoke Trace Metrics</title>" in report
    assert "canva&lt;script&gt;" in report
    assert "<li>Checks: 1</li>" in report
    assert "<li>Usage observed: 1 observed, 0 missing</li>" in report
    assert "<li>Total tokens: 88</li>" in report
    assert "<td>npm</td><td>1</td>" in report
    assert "<td>0.0042</td>" in report
    assert "<h2>Span Tree</h2>" in report
    assert "<td>mcp:check:1</td><td>mcp:root</td><td></td><td>canva&lt;script&gt;</td><td>ok</td>" in report
    assert '<p class="ok">OK: true</p>' in report


def test_format_otel_json_exports_deterministic_span_tree(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result("first", "python -m pytest tests -q", duration_seconds=0.25),
            result("second", "npm.cmd run test", returncode=1, ok=False),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")
    otel = metrics_module.format_otel_json(metrics)
    spans = otel["resourceSpans"][0]["scopeSpans"][0]["spans"]

    assert otel["resourceSpans"][0]["resource"]["attributes"][0] == {
        "key": "service.name",
        "value": {"stringValue": "mcp-smoke-trace-metrics"},
    }
    assert len(spans) == 3
    assert len(spans[0]["traceId"]) == 32
    assert len(spans[0]["spanId"]) == 16
    assert spans[0]["name"] == "mcp smoke"
    assert spans[0]["status"] == {"code": "STATUS_CODE_ERROR"}
    assert spans[1]["parentSpanId"] == spans[0]["spanId"]
    assert spans[1]["status"] == {"code": "STATUS_CODE_OK"}
    assert spans[2]["status"] == {"code": "STATUS_CODE_ERROR"}
    assert any(
        attribute == {"key": "mcp.previous_span_id", "value": {"stringValue": "mcp:check:1"}}
        for attribute in spans[2]["attributes"]
    )


def test_submit_otel_json_posts_payload_to_local_collector(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload([result("first", "python -m pytest tests -q")])
    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")
    otel = metrics_module.format_otel_json(metrics)
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            captured["path"] = self.path
            captured["content_type"] = self.headers["Content-Type"]
            captured["test_header"] = self.headers["X-Test"]
            captured["body"] = json.loads(body.decode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"accepted":true}')

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        report = metrics_module.submit_otel_json(
            otel,
            f"http://127.0.0.1:{server.server_port}/v1/traces",
            timeout_seconds=5,
            headers={"X-Test": "yes"},
        )
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert report["ok"] is True
    assert report["status_code"] == 200
    assert report["request_bytes"] > 0
    assert "X-Test" in report["request_header_names"]
    assert report["response_body_preview"] == '{"accepted":true}'
    assert captured["path"] == "/v1/traces"
    assert captured["content_type"] == "application/json"
    assert captured["test_header"] == "yes"
    assert captured["body"] == otel


def test_cli_writes_metrics_json_markdown_and_html(tmp_path: Path) -> None:
    smoke_path = tmp_path / "smoke.json"
    metrics_path = tmp_path / "metrics.json"
    markdown_path = tmp_path / "metrics.md"
    html_path = tmp_path / "metrics.html"
    otel_path = tmp_path / "metrics.otel.json"
    smoke_path.write_text(
        json.dumps(
            smoke_payload(
                [
                    result("DailyNews unit tests", "python -m pytest tests/unit -q"),
                    result("telegram-mcp tests", "python -m pytest tests -q"),
                ]
            )
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(smoke_path),
            "--json-out",
            str(metrics_path),
            "--markdown-out",
            str(markdown_path),
            "--html-out",
            str(html_path),
            "--otel-json-out",
            str(otel_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=CLI_TIMEOUT_SECONDS,
    )

    assert completed.returncode == 0
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["summary"]["checks"] == 2
    assert metrics["summary"]["runtime_kinds"] == {"pytest": 2}
    assert metrics["trace_integrity"]["ok"] is True
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# MCP Smoke Trace Metrics" in markdown
    assert "| DailyNews unit tests | pytest | true | . |  |  |  | 2 |" in markdown
    html = html_path.read_text(encoding="utf-8")
    assert "<h1>MCP Smoke Trace Metrics</h1>" in html
    assert "<td>DailyNews unit tests</td>" in html
    otel = json.loads(otel_path.read_text(encoding="utf-8"))
    assert len(otel["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 3


def test_cli_posts_otel_json_and_writes_submit_report(tmp_path: Path) -> None:
    smoke_path = tmp_path / "smoke.json"
    otel_path = tmp_path / "metrics.otel.json"
    submit_report_path = tmp_path / "submit.json"
    smoke_path.write_text(
        json.dumps(smoke_payload([result("DailyNews unit tests", "python -m pytest tests/unit -q")])),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            captured["path"] = self.path
            captured["body"] = json.loads(body.decode("utf-8"))
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"queued":true}')

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                str(smoke_path),
                "--otel-json-out",
                str(otel_path),
                "--otel-submit-url",
                f"http://127.0.0.1:{server.server_port}/v1/traces",
                "--otel-submit-report-out",
                str(submit_report_path),
                "--otel-submit-header",
                "X-Test=cli",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=CLI_TIMEOUT_SECONDS,
        )
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert completed.returncode == 0, completed.stderr
    assert captured["path"] == "/v1/traces"
    otel = json.loads(otel_path.read_text(encoding="utf-8"))
    assert captured["body"] == otel
    report = json.loads(submit_report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["status_code"] == 202
    assert report["response_body_preview"] == '{"queued":true}'


def test_format_otel_json_sets_span_timestamps_from_source_generated_at(tmp_path: Path) -> None:
    from datetime import datetime

    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result("first", "python -m pytest tests -q", duration_seconds=0.25),
            result("second", "npm.cmd run test", returncode=1, ok=False),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")
    spans = metrics_module.format_otel_json(metrics)["resourceSpans"][0]["scopeSpans"][0]["spans"]

    base_ns = int(datetime.fromisoformat("2026-06-05T00:00:00+00:00").timestamp() * 1_000_000_000)
    root, first, second = spans
    assert int(root["startTimeUnixNano"]) == base_ns
    assert int(first["startTimeUnixNano"]) == base_ns
    assert int(first["endTimeUnixNano"]) == base_ns + 250_000_000
    assert int(second["startTimeUnixNano"]) == int(first["endTimeUnixNano"])
    assert int(second["endTimeUnixNano"]) > int(second["startTimeUnixNano"])
    assert int(root["endTimeUnixNano"]) == int(second["endTimeUnixNano"])


def test_otel_trace_id_distinguishes_runs_by_generated_at(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    source_path = tmp_path / "smoke.json"

    def trace_id_for(generated_at: str) -> str:
        payload = smoke_payload([result("first", "python -m pytest tests -q")])
        payload["generated_at"] = generated_at
        metrics = metrics_module.build_metrics(payload, source_path=source_path)
        otel = metrics_module.format_otel_json(metrics)
        return otel["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"]

    first_run = trace_id_for("2026-06-05T00:00:00+00:00")
    identical_rerun = trace_id_for("2026-06-05T00:00:00+00:00")
    next_run = trace_id_for("2026-06-06T00:00:00+00:00")

    assert first_run == identical_rerun
    assert first_run != next_run
