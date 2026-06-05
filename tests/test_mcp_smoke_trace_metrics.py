from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_smoke_trace_metrics.py"


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
    assert '<p class="ok">OK: true</p>' in report


def test_cli_writes_metrics_json_markdown_and_html(tmp_path: Path) -> None:
    smoke_path = tmp_path / "smoke.json"
    metrics_path = tmp_path / "metrics.json"
    markdown_path = tmp_path / "metrics.md"
    html_path = tmp_path / "metrics.html"
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
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
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
