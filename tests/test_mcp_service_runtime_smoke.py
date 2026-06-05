from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_service_runtime_smoke.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "mcp_service_manifest.json"


def load_module():
    spec = importlib.util.spec_from_file_location("mcp_service_runtime_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_process(tool_count: int = 3) -> subprocess.CompletedProcess[str]:
    tools = [{"name": f"tool_{index}"} for index in range(tool_count)]
    stdout = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "sample-server", "version": "1.0"},
                    },
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": tools}}),
        ]
    )
    return subprocess.CompletedProcess(["python", "server.py"], 0, stdout, "runtime warning\n")


def test_eligible_services_selects_stdio_python_and_skips_canva() -> None:
    smoke = load_module()
    payload = smoke.service_manifest.load_manifest(MANIFEST_PATH)

    selected, skipped = smoke.eligible_services(payload)

    assert {service["id"] for service in selected} == {
        "dailynews-antigravity",
        "desci-research",
        "telegram-bot",
    }
    assert skipped == [{"id": "canva-local", "reason": "stdio_transport_not_declared"}]


def test_build_service_result_accepts_tools_list_response() -> None:
    smoke = load_module()
    service = {
        "id": "sample",
        "name": "Sample MCP",
        "cwd": ".",
        "command": ["python", "server.py"],
        "required_env": ["SAMPLE_TOKEN"],
        "expected_min_tools": 2,
    }

    result = smoke.build_service_result(service, ["python", "server.py"], sample_process(tool_count=3))

    assert result["status"] == "pass"
    assert result["tool_count"] == 3
    assert result["server_name"] == "sample-server"
    assert result["capability_keys"] == ["tools"]
    assert result["missing_env"] == ["SAMPLE_TOKEN"]
    assert result["stderr_tail"] == "runtime warning"


def test_build_service_result_fails_when_tool_count_is_too_low() -> None:
    smoke = load_module()
    service = {
        "id": "sample",
        "name": "Sample MCP",
        "cwd": ".",
        "command": ["python", "server.py"],
        "required_env": [],
        "expected_min_tools": 4,
    }

    result = smoke.build_service_result(service, ["python", "server.py"], sample_process(tool_count=3))

    assert result["status"] == "fail"
    assert result["errors"] == ["expected at least 4 tools, got 3"]


def test_run_service_smoke_converts_launch_error_to_failed_service(monkeypatch) -> None:
    smoke = load_module()
    service = {
        "id": "sample",
        "name": "Sample MCP",
        "cwd": ".",
        "command": ["python", "server.py"],
        "required_env": ["SAMPLE_TOKEN"],
        "expected_min_tools": 2,
    }

    def fake_run(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    result = smoke.run_service_smoke(service, timeout_seconds=1, python_exe=sys.executable)

    assert result["status"] == "fail"
    assert result["tool_count"] == 0
    assert result["missing_env"] == ["SAMPLE_TOKEN"]
    assert result["errors"] == ["runtime launch failed: connection refused"]


def test_build_report_summarizes_skips_and_credentials() -> None:
    smoke = load_module()
    payload = {"generated_at": "2026-06-05T00:00:00+09:00", "services": [{}, {}, {}]}
    services = [
        {"id": "a", "status": "pass", "tool_count": 2, "missing_env": []},
        {"id": "b", "status": "pass", "tool_count": 3, "missing_env": ["TOKEN"]},
    ]

    report = smoke.build_report(payload, services, [{"id": "c", "reason": "skip"}])

    assert report["status"] == "pass"
    assert report["summary"]["total_manifest_services"] == 3
    assert report["summary"]["checked_services"] == 2
    assert report["summary"]["skipped_services"] == 1
    assert report["summary"]["credential_gated_checked_services"] == 1
    assert report["summary"]["total_tools_listed"] == 5


def test_runtime_smoke_cli_writes_report_with_fake_runner(tmp_path: Path, monkeypatch) -> None:
    smoke = load_module()
    json_out = tmp_path / "runtime.json"
    markdown_out = tmp_path / "runtime.md"

    def fake_runner(service, *, timeout_seconds, protocol_version, python_exe=sys.executable):
        return {
            "id": service["id"],
            "name": service["name"],
            "status": "pass",
            "command": "python server.py",
            "cwd": service["cwd"],
            "transport": "stdio",
            "expected_min_tools": service["expected_min_tools"],
            "tool_count": service["expected_min_tools"],
            "tools": ["tool"],
            "server_name": service["name"],
            "server_version": "1.0",
            "capability_keys": ["tools"],
            "required_env": service.get("required_env", []),
            "missing_env": [],
            "stderr_tail": "",
            "errors": [],
        }

    monkeypatch.setattr(smoke, "run_service_smoke", fake_runner)
    exit_code = smoke.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert report["status"] == "pass"
    assert report["summary"]["checked_services"] == 3
    assert "MCP Service Runtime Smoke" in markdown
