from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RADAR_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_modernization_radar.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "github_modernization_sources.json"
REPORT_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md"


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
    assert summary["source_count"] == 30
    assert summary["adoption_status_counts"] == {
        "adopted": 1,
        "partially_adopted": 29,
    }
    assert {source["repo"] for source in summary["sources"]} == {
        "PrefectHQ/fastmcp",
        "modelcontextprotocol/python-sdk",
        "lastmile-ai/mcp-eval",
        "open-telemetry/opentelemetry-collector",
        "evalstate/fast-agent",
        "langchain-ai/langgraph",
        "crewAIInc/crewAI",
        "openai/openai-agents-python",
        "browser-use/browser-use",
        "pydantic/pydantic-ai",
        "humanlayer/humanlayer",
        "microsoft/agent-framework",
        "agno-agi/agno",
        "vercel/ai",
        "Significant-Gravitas/AutoGPT",
        "FlowiseAI/Flowise",
        "dsifry/metaswarm",
        "modelcontextprotocol/inspector",
        "microsoft/mcp-gateway",
        "open-webui/mcpo",
        "microsoft/playwright-mcp",
        "Uninen/devserver-mcp",
        "OpenHands/OpenHands",
        "microsoft/autogen",
        "google/adk-python",
        "run-llama/llama_index",
        "strands-agents/harness-sdk",
        "deepset-ai/haystack",
        "mastra-ai/mastra",
        "lastmile-ai/mcp-agent",
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
    assert machine["source_count"] == 30
    assert machine["adoption_status_counts"]["partially_adopted"] == 29
    assert "GitHub Similar Systems Modernization Radar" in markdown
    assert "PrefectHQ/fastmcp" in markdown
    assert "modelcontextprotocol/python-sdk" in markdown
    assert "modelcontextprotocol/inspector" in markdown
    assert "open-telemetry/opentelemetry-collector" in markdown
    assert "langchain-ai/langgraph" in markdown
    assert "crewAIInc/crewAI" in markdown
    assert "openai/openai-agents-python" in markdown
    assert "browser-use/browser-use" in markdown
    assert "pydantic/pydantic-ai" in markdown
    assert "humanlayer/humanlayer" in markdown
    assert "microsoft/agent-framework" in markdown
    assert "agno-agi/agno" in markdown
    assert "vercel/ai" in markdown
    assert "Significant-Gravitas/AutoGPT" in markdown
    assert "FlowiseAI/Flowise" in markdown
    assert "microsoft/mcp-gateway" in markdown
    assert "microsoft/playwright-mcp" in markdown
    assert "OpenHands/OpenHands" in markdown
    assert "microsoft/autogen" in markdown
    assert "google/adk-python" in markdown
    assert "run-llama/llama_index" in markdown
    assert "strands-agents/harness-sdk" in markdown
    assert "deepset-ai/haystack" in markdown
    assert "mastra-ai/mastra" in markdown
    assert "lastmile-ai/mcp-agent" in markdown
    assert "Keep the default smoke gate deterministic and offline" in markdown


def test_checked_in_modernization_report_matches_manifest_renderer() -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = radar.summarize_manifest(payload)
    expected = radar.format_markdown(payload, summary)

    assert errors == []
    assert REPORT_MARKDOWN_PATH.read_text(encoding="utf-8") == expected


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
