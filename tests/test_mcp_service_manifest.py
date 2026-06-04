from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_service_manifest.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "mcp_service_manifest.json"


def load_manifest_module():
    spec = importlib.util.spec_from_file_location("mcp_service_manifest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_mcp_service_manifest_validates() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = manifest.build_summary(payload, workspace_root=PROJECT_ROOT)

    assert errors == []
    assert summary["summary"]["total_services"] == 4
    assert summary["summary"]["fastmcp_services"] == 3
    assert summary["summary"]["languages"] == {"python": 3, "typescript": 1}
    assert summary["summary"]["transports"]["stdio"] == 3
    assert summary["summary"]["transports"]["sse"] == 1


def test_tool_count_detection_covers_python_and_typescript_services() -> None:
    manifest = load_manifest_module()

    dailynews_server = PROJECT_ROOT / "automation/DailyNews/src/antigravity_mcp/server.py"
    canva_tools = PROJECT_ROOT / "mcp/canva-mcp/src/server/tools.ts"

    assert manifest.detect_tool_count(dailynews_server, "python") == 26
    assert manifest.detect_tool_count(PROJECT_ROOT / "mcp/desci-research-mcp/server.py", "python") == 6
    assert manifest.detect_tool_count(PROJECT_ROOT / "mcp/telegram-mcp/server.py", "python") == 7
    assert manifest.detect_tool_count(canva_tools, "typescript") >= 20


def test_manifest_rejects_invalid_service_data() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)
    payload["schema_version"] = True
    payload["services"][0]["id"] = "bad id"
    payload["services"][0]["source_path"] = "../outside.py"
    payload["services"][0]["language"] = "ruby"
    payload["services"][0]["transports"] = ["stdio", "websocket"]
    payload["services"][0]["expected_min_tools"] = 999

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "schema_version must be 1" in errors
    assert "services[0].id must use lowercase letters, numbers, hyphens, or underscores" in errors
    assert "services[0].source_path must be a repo-relative path" in errors
    assert "services[0].language must be one of python, typescript" in errors
    assert "services[0].transports contains unknown transport: websocket" in errors


def test_cli_writes_summary_outputs(tmp_path: Path) -> None:
    manifest = load_manifest_module()
    json_out = tmp_path / "mcp-services.json"
    markdown_out = tmp_path / "mcp-services.md"

    result = manifest.main(
        ["--manifest", str(MANIFEST_PATH), "--json-out", str(json_out), "--markdown-out", str(markdown_out)]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["summary"]["total_services"] == 4
    assert payload["summary"]["fastmcp_services"] == 3
    assert "dailynews-antigravity" in markdown
    assert "Detected tools" in markdown
