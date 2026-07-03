from __future__ import annotations

import importlib.util
import json
import re
import subprocess
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


def minimal_manifest(local_evidence: list[str]) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T00:00:00+00:00",
        "search_context": {
            "objective": "Map source-backed modernization signals.",
            "queries": ["agent quality gate"],
        },
        "sources": [
            {
                "repo": "owner/project",
                "url": "https://github.com/owner/project",
                "category": "quality-gate",
                "adoption_status": "watch",
                "why_similar": "It validates durable evidence.",
                "observed_patterns": ["tracked evidence"],
                "local_evidence": local_evidence,
                "gap": "Synthetic fixture.",
            }
        ],
    }


def test_current_manifest_validates_against_real_workspace_evidence() -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = radar.summarize_manifest(payload)

    assert errors == []
    assert summary["source_count"] == 8
    assert summary["adoption_status_counts"] == {
        "adopted": 8,
    }
    assert {source["repo"] for source in summary["sources"]} == {
        "PrefectHQ/fastmcp",
        "lastmile-ai/mcp-eval",
        "evalstate/fast-agent",
        "Veritas-7/autoresearch-skill-system",
        "kodustech/agent-readiness",
        "dsifry/metaswarm",
        "open-webui/mcpo",
        "Uninen/devserver-mcp",
    }
    assert all(source["evidence_count"] >= 4 for source in summary["sources"])
    veritas = next(source for source in summary["sources"] if source["repo"] == "Veritas-7/autoresearch-skill-system")
    assert re.fullmatch(r"[0-9a-f]{40}", veritas["latest_observed_commit"])


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
    assert machine["source_count"] == 8
    assert machine["adoption_status_counts"]["adopted"] == 8
    assert "partially_adopted" not in machine["adoption_status_counts"]
    assert machine["local_evidence_path_count"] >= 80
    assert machine["local_evidence_git_tracked"] is True
    expected_title_date = machine["generated_at"].split("T", 1)[0]
    assert markdown.startswith(f"# GitHub Similar Systems Modernization Radar - {expected_title_date}")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.+\+00:00", machine["rendered_at"])
    assert f"- Rendered at: `{machine['rendered_at']}`" in markdown
    assert "- Local evidence tracking: all " in markdown
    assert "paths exist and are git-tracked" in markdown
    assert "PrefectHQ/fastmcp" in markdown
    assert "Veritas-7/autoresearch-skill-system" in markdown
    assert "kodustech/agent-readiness" in markdown
    assert re.search(r"Latest observed commit: `[0-9a-f]{40}`", markdown)
    assert "Keep the default smoke gate deterministic and offline" in markdown


def test_cli_can_override_latest_commit_in_outputs_without_editing_manifest(tmp_path: Path) -> None:
    radar = load_radar_module()
    json_out = tmp_path / "radar.json"
    markdown_out = tmp_path / "radar.md"
    override_commit = "0123456789abcdef0123456789abcdef01234567"
    manifest_before = MANIFEST_PATH.read_text(encoding="utf-8")

    result = radar.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--latest-observed-commit",
            f"Veritas-7/autoresearch-skill-system={override_commit}",
        ]
    )

    machine = json.loads(json_out.read_text(encoding="utf-8"))
    veritas = next(source for source in machine["sources"] if source["repo"] == "Veritas-7/autoresearch-skill-system")
    markdown = markdown_out.read_text(encoding="utf-8")

    assert result == 0
    assert veritas["latest_observed_commit"] == override_commit
    assert f"Latest observed commit: `{override_commit}`" in markdown
    assert MANIFEST_PATH.read_text(encoding="utf-8") == manifest_before


def test_cli_can_refresh_latest_commits_in_outputs_without_editing_manifest(tmp_path: Path, monkeypatch) -> None:
    radar = load_radar_module()
    json_out = tmp_path / "radar.json"
    markdown_out = tmp_path / "radar.md"
    refreshed_commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
    manifest_before = MANIFEST_PATH.read_text(encoding="utf-8")

    monkeypatch.setattr(radar, "_fetch_remote_head_commit", lambda _url: refreshed_commit)

    result = radar.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--refresh-latest-commits",
        ]
    )

    machine = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")

    assert result == 0
    assert machine["latest_commit_refresh"]["checked_count"] == 8
    assert machine["latest_commit_refresh"]["failed_count"] == 0
    assert machine["latest_commit_refresh"]["updated_count"] == 8
    assert machine["latest_commit_refresh"]["review_required_count"] == 8
    assert all(item["review_required"] is True for item in machine["latest_commit_refresh"]["repositories"])
    assert all(
        item["compare_url"].startswith("https://github.com/")
        for item in machine["latest_commit_refresh"]["repositories"]
    )
    assert all(item["category"] for item in machine["latest_commit_refresh"]["repositories"])
    assert all(item["local_evidence_count"] >= 1 for item in machine["latest_commit_refresh"]["repositories"])
    assert all(item["local_review_targets"] for item in machine["latest_commit_refresh"]["repositories"])
    assert {source["latest_observed_commit"] for source in machine["sources"]} == {refreshed_commit}
    assert "Latest commit refresh: 8 GitHub HEAD refs checked" in markdown
    assert "review_required=8" in markdown
    assert "## Refresh Review Queue" in markdown
    assert "| Repo | Status | Category | Local review targets | Compare |" in markdown
    assert "`production-mcp-framework`" in markdown
    assert "`ops/references/mcp_services.json`" in markdown
    assert "[compare](https://github.com/" in markdown
    assert f"Latest observed commit: `{refreshed_commit}`" in markdown
    assert MANIFEST_PATH.read_text(encoding="utf-8") == manifest_before


def test_latest_commit_refresh_records_failures_without_mutating_source(monkeypatch) -> None:
    radar = load_radar_module()
    payload = minimal_manifest(["tracked.md"])
    previous_commit = "0123456789abcdef0123456789abcdef01234567"
    payload["sources"][0]["latest_observed_commit"] = previous_commit
    payload["sources"][0]["url"] = "https://github.com/owner/project"

    def fake_fetch(_url: str) -> str:
        raise ValueError("network unavailable")

    monkeypatch.setattr(radar, "_fetch_remote_head_commit", fake_fetch)

    refresh = radar.refresh_manifest_latest_commits(payload)

    assert refresh["checked_count"] == 1
    assert refresh["failed_count"] == 1
    assert refresh["updated_count"] == 0
    assert refresh["review_required_count"] == 1
    assert refresh["repositories"][0]["status"] == "failed"
    assert refresh["repositories"][0]["review_required"] is True
    assert refresh["repositories"][0]["previous_commit"] == previous_commit
    assert refresh["repositories"][0]["category"] == "quality-gate"
    assert refresh["repositories"][0]["local_review_targets"] == ["tracked.md"]
    assert "network unavailable" in refresh["repositories"][0]["error"]
    assert payload["sources"][0]["latest_observed_commit"] == previous_commit


def test_refresh_review_queue_reports_no_work_when_sources_are_current(monkeypatch) -> None:
    radar = load_radar_module()
    payload = minimal_manifest(["tracked.md"])
    current_commit = "0123456789abcdef0123456789abcdef01234567"
    payload["sources"][0]["latest_observed_commit"] = current_commit
    payload["sources"][0]["url"] = "https://github.com/owner/project"

    monkeypatch.setattr(radar, "_fetch_remote_head_commit", lambda _url: current_commit)

    refresh = radar.refresh_manifest_latest_commits(payload)
    summary = radar.summarize_manifest(payload, latest_commit_refresh=refresh, rendered_at="2026-06-18T00:00:00+00:00")
    markdown = radar.format_markdown(payload, summary)

    assert refresh["review_required_count"] == 0
    assert refresh["repositories"][0]["review_required"] is False
    assert "compare_url" not in refresh["repositories"][0]
    assert "- Review required: `0`" in markdown


def test_parse_ls_remote_head_accepts_only_head_sha() -> None:
    radar = load_radar_module()

    assert (
        radar._parse_ls_remote_head("abcdefabcdefabcdefabcdefabcdefabcdefabcd\tHEAD\n")
        == "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
    )
    assert radar._parse_ls_remote_head("not-a-sha\tHEAD\n") == ""
    assert radar._parse_ls_remote_head("abcdefabcdefabcdefabcdefabcdefabcdefabcd\trefs/heads/main\n") == ""


def test_manifest_rejects_missing_local_evidence(tmp_path: Path) -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)
    payload["sources"][0]["local_evidence"] = ["missing/path.py"]

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "sources[0].local_evidence[0] must exist in the workspace" in errors


def test_manifest_rejects_untracked_local_evidence(tmp_path: Path) -> None:
    radar = load_radar_module()
    evidence_path = tmp_path / "local-only-report.md"
    evidence_path.write_text("local only", encoding="utf-8")
    payload = minimal_manifest(["local-only-report.md"])

    errors = radar.validate_manifest(payload, workspace_root=tmp_path)

    assert "sources[0].local_evidence[0] must be tracked by git" in errors


def test_manifest_treats_git_tracking_timeout_as_untracked(tmp_path: Path, monkeypatch) -> None:
    radar = load_radar_module()
    evidence_path = tmp_path / "local-only-report.md"
    evidence_path.write_text("local only", encoding="utf-8")
    payload = minimal_manifest(["local-only-report.md"])

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["git", "ls-files"], timeout=radar.GIT_TRACKED_TIMEOUT_SECONDS)

    monkeypatch.setattr(radar.subprocess, "run", fake_run)

    errors = radar.validate_manifest(payload, workspace_root=tmp_path)

    assert "sources[0].local_evidence[0] must be tracked by git" in errors


def test_manifest_rejects_untrusted_or_escaping_source_data() -> None:
    radar = load_radar_module()
    payload = radar.load_manifest(MANIFEST_PATH)
    payload["sources"][0]["url"] = "https://example.com/not-github"
    payload["sources"][0]["local_evidence"] = ["../outside.py"]
    payload["sources"][0]["latest_observed_commit"] = "not-a-sha"

    errors = radar.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "sources[0].url must be a GitHub HTTPS URL" in errors
    assert "sources[0].local_evidence[0] must be a repo-relative path" in errors
    assert "sources[0].latest_observed_commit must be a 40-character lowercase git SHA when provided" in errors
