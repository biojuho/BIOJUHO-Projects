from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "mcp_service_inventory.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "mcp_services.json"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("mcp_service_inventory", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_manifest_validates_tracked_mcp_service_paths() -> None:
    inventory = load_inventory_module()
    payload = inventory.load_manifest(MANIFEST_PATH)

    errors = inventory.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = inventory.summarize_manifest(payload)

    assert errors == []
    assert summary["service_count"] == 5
    assert summary["status_counts"] == {"active": 4, "candidate": 1}
    assert summary["language_counts"] == {"external": 1, "python": 3, "typescript": 1}
    assert summary["transport_counts"] == {"cli": 1, "http-sse": 1, "stdio": 4}
    assert {service["id"] for service in summary["services"]} == {
        "canva-mcp",
        "desci-research-mcp",
        "telegram-mcp",
        "github-mcp",
        "notebooklm-mcp",
    }


def test_cli_writes_machine_and_markdown_evidence(tmp_path: Path) -> None:
    inventory = load_inventory_module()
    json_out = tmp_path / "mcp-services.json"
    markdown_out = tmp_path / "mcp-services.md"

    result = inventory.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    machine = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert machine["service_count"] == 5
    assert machine["transport_counts"]["stdio"] == 4
    assert "MCP Service Inventory" in markdown
    assert "canva-mcp" in markdown
    assert "notebooklm-mcp" in markdown


def test_manifest_rejects_unsafe_missing_and_untracked_paths(tmp_path: Path) -> None:
    inventory = load_inventory_module()
    payload = inventory.load_manifest(MANIFEST_PATH)
    local_only = PROJECT_ROOT / "var" / "local-only-mcp-inventory-test.txt"
    local_only.parent.mkdir(parents=True, exist_ok=True)
    local_only.write_text("local only", encoding="utf-8")
    try:
        payload["services"][0]["entrypoints"] = ["../outside.ts"]
        payload["services"][0]["evidence"] = ["missing/evidence.md", "var/local-only-mcp-inventory-test.txt"]

        errors = inventory.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    finally:
        local_only.unlink(missing_ok=True)

    assert "services[0].entrypoints[0] must be a repo-relative path" in errors
    assert "services[0].evidence[0] must exist in the workspace" in errors
    assert "services[0].evidence[1] must be tracked in git" in errors


def test_manifest_rejects_duplicate_ids_and_unknown_transport() -> None:
    inventory = load_inventory_module()
    payload = inventory.load_manifest(MANIFEST_PATH)
    payload["services"][1]["id"] = payload["services"][0]["id"]
    payload["services"][1]["transport_modes"] = ["telepathy"]

    errors = inventory.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "services[1].id must be unique" in errors
    assert "services[1].transport_modes contains unsupported value: telepathy" in errors
