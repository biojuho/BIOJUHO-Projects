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


def result(name: str, command: str, *, scope: str = "mcp", returncode: int = 0, ok: bool = True) -> dict:
    return {
        "scope": scope,
        "name": name,
        "cwd": ".",
        "command": command,
        "returncode": returncode,
        "ok": ok,
        "stdout_tail": "",
        "stderr_tail": "",
    }


def test_build_metrics_summarizes_mcp_runtime_kinds(tmp_path: Path) -> None:
    metrics_module = load_metrics_module()
    payload = smoke_payload(
        [
            result("notebooklm compile", "python -m compileall mcp/notebooklm-mcp"),
            result("canva-mcp build", "npm.cmd run build", returncode=1, ok=False),
            result("workspace regression tests", "python -m pytest tests/test_workspace_smoke.py", scope="workspace"),
        ]
    )

    metrics = metrics_module.build_metrics(payload, source_path=tmp_path / "smoke.json")

    assert metrics["summary"]["checks"] == 2
    assert metrics["summary"]["passed"] == 1
    assert metrics["summary"]["failed"] == 1
    assert metrics["summary"]["runtime_kinds"] == {"compileall": 1, "npm": 1}
    assert metrics["trace_integrity"] == {"ok": True, "issues": []}
    assert [check["name"] for check in metrics["checks"]] == ["notebooklm compile", "canva-mcp build"]


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


def test_cli_writes_metrics_json(tmp_path: Path) -> None:
    smoke_path = tmp_path / "smoke.json"
    metrics_path = tmp_path / "metrics.json"
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
        [sys.executable, str(SCRIPT_PATH), str(smoke_path), "--json-out", str(metrics_path)],
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
