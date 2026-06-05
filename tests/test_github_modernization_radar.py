from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RADAR_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_modernization_radar.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "github_modernization_sources.json"


def load_radar_module():
    spec = importlib.util.spec_from_file_location("github_modernization_radar", RADAR_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_manifest_validates_against_real_workspace_evidence() -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = radar.summarize_manifest(payload)

    assert errors == []
    assert summary["source_count"] == 6
    assert summary["adoption_status_counts"] == {
        "adopted": 3,
        "partially_adopted": 2,
        "watch": 1,
    }
    assert {source["repo"] for source in summary["sources"]} == {
        "PrefectHQ/fastmcp",
        "lastmile-ai/mcp-eval",
        "evalstate/fast-agent",
        "dsifry/metaswarm",
        "open-webui/mcpo",
        "Uninen/devserver-mcp",
    }
    assert all(source["evidence_count"] >= 4 for source in summary["sources"])


def test_cli_writes_machine_and_markdown_evidence(tmp_path: Path) -> None:
    radar = load_radar_module()
    json_out = tmp_path / "radar.json"
    markdown_out = tmp_path / "radar.md"

    result = radar.main(
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
    assert machine["source_count"] == 6
    assert machine["adoption_status_counts"]["adopted"] == 3
    assert machine["adoption_status_counts"]["partially_adopted"] == 2
    assert "GitHub Similar Systems Modernization Radar" in markdown
    assert "PrefectHQ/fastmcp" in markdown
    assert "Keep the default smoke gate deterministic and offline" in markdown


def test_manifest_rejects_missing_local_evidence(tmp_path: Path) -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)
    payload["sources"][0]["local_evidence"] = ["missing/path.py"]

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "sources[0].local_evidence[0] must exist in the workspace" in errors


def test_manifest_rejects_untrusted_or_escaping_source_data() -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)
    payload["sources"][0]["url"] = "https://example.com/not-github"
    payload["sources"][0]["local_evidence"] = ["../outside.py"]

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "sources[0].url must be a GitHub HTTPS URL" in errors
    assert "sources[0].local_evidence[0] must be a repo-relative path" in errors
