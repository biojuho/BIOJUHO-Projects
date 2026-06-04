from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_source_freshness.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "github_modernization_sources.json"
SNAPSHOT_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_FRESHNESS_2026-06-05.json"
SNAPSHOT_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_FRESHNESS_2026-06-05.md"


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
    assert report["source_count"] == 30
    assert report["passed"] == 30
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
        "OpenHands/OpenHands",
        "microsoft/autogen",
        "google/adk-python",
        "run-llama/llama_index",
        "strands-agents/harness-sdk",
        "deepset-ai/haystack",
        "mastra-ai/mastra",
        "lastmile-ai/mcp-agent",
    }


def test_checked_in_source_snapshot_matches_manifest_and_renderer() -> None:
    freshness = load_module()
    manifest = freshness.radar.load_manifest(MANIFEST_PATH)
    snapshot = json.loads(SNAPSHOT_JSON_PATH.read_text(encoding="utf-8"))
    records = snapshot["records"]
    sources = manifest["sources"]

    datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))
    assert snapshot["status"] == "pass"
    assert snapshot["source_count"] == len(sources) == 30
    assert snapshot["passed"] == len(sources)
    assert snapshot["failed"] == 0
    assert snapshot["manifest_generated_at"] == manifest["generated_at"]
    assert [record["repo"] for record in records] == [source["repo"] for source in sources]

    for record, source in zip(records, sources, strict=True):
        assert record["category"] == source["category"]
        assert record["adoption_status"] == source["adoption_status"]
        assert record["status"] == "pass"
        assert record["error"] == ""
        assert record["metadata"]["repo"] == source["repo"]
        assert freshness._metadata_viability_error(record["metadata"]) == ""

    assert SNAPSHOT_MARKDOWN_PATH.read_text(encoding="utf-8") == freshness.render_markdown(snapshot)


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
    assert report["records"][0]["failure_type"] == "github_api_rate_limit"
    assert report["rate_limited_count"] == 1
    assert report["partial"] is True
    assert report["complete"] is False
    assert report["token_required"] is True


def test_collect_source_freshness_marks_github_rate_limit_boundary() -> None:
    freshness = load_module()
    seen = 0

    def fake_fetch(repo: str, timeout_seconds: float):
        nonlocal seen
        seen += 1
        if seen > 19:
            raise freshness.GitHubApiError(
                repo,
                403,
                '{"message":"API rate limit exceeded for 203.0.113.10"}',
                failure_type=freshness.RATE_LIMIT_FAILURE_TYPE,
                requires_token=True,
            )
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
    markdown = freshness.render_markdown(report)

    assert report["status"] == "fail"
    assert report["passed"] == 19
    assert report["failed"] == 11
    assert report["complete"] is False
    assert report["partial"] is True
    assert report["rate_limited"] is True
    assert report["rate_limited_count"] == 11
    assert report["token_required"] is True
    assert report["token_hint"] == "Set GITHUB_TOKEN or GH_TOKEN before adopting this live source snapshot."
    assert {record["failure_type"] for record in report["records"] if record["status"] == "fail"} == {
        "github_api_rate_limit"
    }
    assert "Partial: `true`" in markdown
    assert "Rate-limited failures: `11`" in markdown
    assert "GITHUB_TOKEN or GH_TOKEN" in markdown


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
        assert report["failed"] == 30
        assert {record["error"] for record in report["records"]} == {expected_error}
        assert {record["failure_type"] for record in report["records"]} == {"metadata_viability"}


def test_github_headers_accepts_gh_token(monkeypatch) -> None:
    freshness = load_module()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "ghp_example")

    headers = freshness._github_headers()

    assert headers["Authorization"] == "Bearer ghp_example"


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
