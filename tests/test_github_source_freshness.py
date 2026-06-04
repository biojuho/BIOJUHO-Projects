from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_source_freshness.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "github_modernization_sources.json"


def load_module():
    spec = importlib.util.spec_from_file_location("github_source_freshness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_source_freshness_maps_manifest_repos() -> None:
    freshness = load_module()

    def fake_fetch(repo: str, timeout_seconds: float):
        return {
            "repo": repo,
            "html_url": f"https://github.com/{repo}",
            "default_branch": "main",
            "pushed_at": "2026-06-05T00:00:00Z",
            "updated_at": "2026-06-05T00:01:00Z",
            "archived": False,
            "disabled": False,
            "visibility": "public",
            "stargazers_count": 10,
            "forks_count": 2,
            "open_issues_count": 1,
            "license": "MIT",
        }

    report = freshness.collect_source_freshness(MANIFEST_PATH, fetch_repo=fake_fetch)

    assert report["status"] == "pass"
    assert report["source_count"] == 22
    assert report["passed"] == 22
    assert report["failed"] == 0
    assert {record["repo"] for record in report["records"]} >= {
        "PrefectHQ/fastmcp",
        "crewAIInc/crewAI",
        "openai/openai-agents-python",
        "browser-use/browser-use",
        "microsoft/agent-framework",
        "agno-agi/agno",
        "vercel/ai",
        "Significant-Gravitas/AutoGPT",
        "FlowiseAI/Flowise",
        "microsoft/playwright-mcp",
    }


def test_collect_source_freshness_records_fetch_failures() -> None:
    freshness = load_module()

    def fake_fetch(repo: str, timeout_seconds: float):
        if repo == "PrefectHQ/fastmcp":
            raise RuntimeError("rate limited")
        return {
            "repo": repo,
            "html_url": f"https://github.com/{repo}",
            "default_branch": "main",
            "pushed_at": "2026-06-05T00:00:00Z",
            "updated_at": "2026-06-05T00:01:00Z",
            "archived": False,
            "disabled": False,
            "visibility": "public",
            "stargazers_count": 10,
            "forks_count": 2,
            "open_issues_count": 1,
            "license": "MIT",
        }

    report = freshness.collect_source_freshness(MANIFEST_PATH, fetch_repo=fake_fetch)

    assert report["status"] == "fail"
    assert report["failed"] == 1
    assert report["records"][0]["error"] == "rate limited"


def test_collect_source_freshness_rejects_nonviable_metadata() -> None:
    freshness = load_module()

    base_metadata = {
        "repo": "repo",
        "html_url": "https://github.com/owner/repo",
        "default_branch": "main",
        "pushed_at": "2026-06-05T00:00:00Z",
        "updated_at": "2026-06-05T00:01:00Z",
        "archived": False,
        "disabled": False,
        "visibility": "public",
        "stargazers_count": 10,
        "forks_count": 2,
        "open_issues_count": 1,
        "license": "MIT",
    }

    cases = [
        ({"archived": True}, "repository is archived"),
        ({"disabled": True}, "repository is disabled"),
        ({"default_branch": ""}, "missing default_branch"),
    ]
    for override, expected_error in cases:
        def fake_fetch(repo: str, timeout_seconds: float, override=override):
            metadata = dict(base_metadata)
            metadata.update({"repo": repo, "html_url": f"https://github.com/{repo}"})
            metadata.update(override)
            return metadata

        report = freshness.collect_source_freshness(MANIFEST_PATH, fetch_repo=fake_fetch)

        assert report["status"] == "fail"
        assert report["failed"] == 22
        assert {record["error"] for record in report["records"]} == {expected_error}


def test_render_markdown_includes_repo_table() -> None:
    freshness = load_module()
    report = {
        "status": "pass",
        "source_count": 1,
        "passed": 1,
        "failed": 0,
        "generated_at": "2026-06-05T00:00:00+00:00",
        "github_api_version": "2022-11-28",
        "records": [
            {
                "repo": "owner/repo",
                "status": "pass",
                "metadata": {
                    "default_branch": "main",
                    "pushed_at": "2026-06-05T00:00:00Z",
                    "updated_at": "2026-06-05T00:01:00Z",
                    "stargazers_count": 10,
                    "forks_count": 2,
                    "archived": False,
                },
            }
        ],
    }

    markdown = freshness.render_markdown(report)

    assert "GitHub Source Freshness Snapshot" in markdown
    assert "| owner/repo | pass | main |" in markdown
    assert "- none" in markdown


def test_run_writes_outputs_with_fake_collector(monkeypatch, tmp_path: Path) -> None:
    freshness = load_module()
    json_out = tmp_path / "freshness.json"
    markdown_out = tmp_path / "freshness.md"

    def fake_collect(manifest_path: Path, *, timeout_seconds: float):
        return {
            "schema_version": 1,
            "generated_at": "2026-06-05T00:00:00+00:00",
            "status": "pass",
            "source_count": 1,
            "passed": 1,
            "failed": 0,
            "manifest_generated_at": "2026-06-05T00:00:00+09:00",
            "github_api_version": "2022-11-28",
            "records": [],
        }

    monkeypatch.setattr(freshness, "collect_source_freshness", fake_collect)

    result = freshness.run(MANIFEST_PATH, json_out=json_out, markdown_out=markdown_out)

    assert result["status"] == "pass"
    assert json.loads(json_out.read_text(encoding="utf-8"))["source_count"] == 1
    assert "GitHub Source Freshness Snapshot" in markdown_out.read_text(encoding="utf-8")
