import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "ops" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "desci_launch_handoff_refresh.py"


def load_refresh_module():
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("desci_launch_handoff_refresh", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean_scan(scanned: int = 13) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "valid",
        "ok": True,
        "scanned_paths": [f"target-{index}.md" for index in range(scanned)],
        "missing_paths": [],
        "findings": [],
        "finding_patterns": [],
    }


def desci_status(live_commit: str = "a" * 40, *, topic: str = "DeSci", state: str = "ok") -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": state,
        "preferred_topic": topic,
        "checks": [] if state == "ok" else [{"name": "desci_launch_handoff_secret_scan_ready", "ok": False}],
        "source": {
            "latest_observed_commit": live_commit,
            "live_source": {
                "status": "current",
                "detail": f"recorded={live_commit} live={live_commit}",
            },
        },
    }


def test_desci_launch_handoff_refresh_pre_scans_then_converges_status_and_bundle(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    live_commit = "b" * 40
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text("{}", encoding="utf-8")
    radar_md.parent.mkdir(parents=True, exist_ok=True)
    radar_md.write_text("# radar\n", encoding="utf-8")
    scan_calls: list[list[Path]] = []
    status_calls = []

    def fake_scan(*, workspace_root, extra_paths=None):
        scan_calls.append([Path(path) for path in extra_paths or []])
        if len(scan_calls) == 1:
            assert not status_json.exists()
        else:
            assert status_json.is_file()
            assert status_md.is_file()
        return clean_scan()

    def fake_build_status(**kwargs):
        status_calls.append(kwargs)
        assert scan_json.is_file()
        assert kwargs["live_source_commit"] == live_commit
        assert kwargs["live_source_checked"] is True
        assert kwargs["live_sources_checked"] is False
        return desci_status(live_commit)

    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", fake_scan)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=live_commit,
        auto_refresh_radar=False,
    )

    assert len(scan_calls) == 3
    assert len(status_calls) == 5
    assert bundle["ok"] is True
    assert bundle["scope"] == "desci_launch_handoff_refresh"
    assert bundle["bundle_json_path"] == "var/bundle.json"
    assert bundle["status"]["state"] == "ok"
    assert bundle["status"]["topic"] == "DeSci"
    assert bundle["secret_scan_passes"] == 3
    assert bundle["secret_scan"]["scanned"] == 13
    assert bundle["live_source_required"] is True
    assert bundle["live_source_ok"] is True
    assert status_json in scan_calls[1]
    assert status_md in scan_calls[1]
    assert radar in scan_calls[1]
    assert radar_md in scan_calls[1]
    assert bundle_json in scan_calls[2]
    assert json.loads(status_json.read_text(encoding="utf-8"))["preferred_topic"] == "DeSci"
    assert status_md.read_text(encoding="utf-8") == "operator markdown"
    assert json.loads(scan_json.read_text(encoding="utf-8"))["ok"] is True
    assert json.loads(bundle_json.read_text(encoding="utf-8"))["ok"] is True


def test_desci_launch_handoff_refresh_summarizes_release_handoff_provider_preflight(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-07" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-07" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    release_handoff_json = tmp_path / "apps" / "desci-platform" / "var" / "release-handoff-current.json"
    live_commit = "e" * 40
    release_handoff_json.parent.mkdir(parents=True, exist_ok=True)
    release_handoff_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ok": False,
                "release_decision": "no-go",
                "provider_preflight_ok": False,
                "provider_preflight": {
                    "ok": False,
                    "provider_count": 3,
                    "ready_provider_count": 1,
                    "check_count": 7,
                    "passed_check_count": 3,
                    "failed_check_count": 4,
                    "missing_cli_count": 0,
                    "auth_context_missing_count": 2,
                    "source_artifact": "var/provider-preflight-current.json",
                    "failed_checks": [
                        {
                            "provider": "railway",
                            "command": "railway whoami",
                            "failure_reason": "nonzero_exit",
                            "stderr_preview": "Unauthorized. Please login.",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    scan_calls: list[list[Path]] = []

    def fake_scan(*, workspace_root, extra_paths=None):
        scan_calls.append([Path(path) for path in extra_paths or []])
        return clean_scan(scanned=15)

    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", fake_scan)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", lambda **kwargs: desci_status(live_commit))
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        release_handoff_json=release_handoff_json,
        live_source_commit=live_commit,
        auto_refresh_radar=False,
    )
    raw_bundle = json.dumps(bundle)
    status_markdown = status_md.read_text(encoding="utf-8")

    assert bundle["ok"] is True
    assert all(release_handoff_json in call for call in scan_calls)
    assert bundle["release_handoff"]["status"] == "valid"
    assert bundle["release_handoff"]["provider_preflight_present"] is True
    assert bundle["release_handoff"]["provider_preflight_ok"] is False
    assert bundle["release_handoff"]["failed_check_count"] == 4
    assert bundle["release_handoff"]["auth_context_missing_count"] == 2
    assert bundle["release_handoff"]["provider_blockers"] == [
        {
            "provider": "railway",
            "id": "",
            "command": "railway whoami",
            "failure_reason": "nonzero_exit",
            "remediation": "",
            "docs_url": "",
        }
    ]
    assert "Unauthorized" not in raw_bundle
    assert "stderr_preview" not in raw_bundle
    assert "## DeSci Provider Blockers" in status_markdown
    assert "`railway` `railway whoami`: `nonzero_exit`" in status_markdown
    assert "Unauthorized" not in status_markdown
    assert "stderr_preview" not in status_markdown


def test_desci_launch_handoff_refresh_summarizes_provider_workflow_bundle(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-07" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-07" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    provider_workflow_json = tmp_path / "apps" / "desci-platform" / "var" / "provider-workflow-bundle.json"
    live_commit = "8" * 40
    provider_workflow_json.parent.mkdir(parents=True, exist_ok=True)
    provider_workflow_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "require_complete_bundle": False,
                "index_complete_bundle": False,
                "first_decision_artifact": "var/provider-workflow.json",
                "provider_apply_workflow": {
                    "ok": False,
                    "operator_phase": "provider_apply_workflow_blocked",
                    "operator_command_count": 8,
                    "operator_command_failure_count": 0,
                },
                "summary": {
                    "missing_required_count": 8,
                    "artifact_failure_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    scan_calls: list[list[Path]] = []

    def fake_scan(*, workspace_root, extra_paths=None):
        scan_calls.append([Path(path) for path in extra_paths or []])
        return clean_scan(scanned=16)

    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", fake_scan)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", lambda **kwargs: desci_status(live_commit))
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        provider_workflow_bundle_json=provider_workflow_json,
        live_source_commit=live_commit,
        auto_refresh_radar=False,
    )
    status_payload = json.loads(status_json.read_text(encoding="utf-8"))
    handoff = status_payload["desci"]["handoff_refresh"]
    status_markdown = status_md.read_text(encoding="utf-8")

    assert bundle["ok"] is True
    assert all(provider_workflow_json in call for call in scan_calls)
    assert bundle["provider_workflow_bundle"]["status"] == "valid"
    assert bundle["provider_workflow_bundle"]["ok"] is True
    assert bundle["provider_workflow_bundle"]["operator_command_count"] == 8
    assert handoff["provider_workflow_bundle_required"] is True
    assert handoff["provider_workflow_bundle_ok"] is True
    assert handoff["provider_workflow_bundle_workflow_ok"] is False
    assert handoff["provider_workflow_bundle_missing_required_count"] == 8
    assert handoff["provider_workflow_bundle_artifact_failure_count"] == 0
    assert handoff["provider_workflow_bundle_operator_command_count"] == 8
    assert "## DeSci Provider Workflow Bundle" in status_markdown
    assert "- Operator commands: `8`" in status_markdown
    assert "- Missing required artifacts: `8`" in status_markdown


def test_desci_launch_handoff_refresh_auto_discovers_latest_release_handoff(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-07" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    release_handoff_dir = tmp_path / "apps" / "desci-platform" / "var"
    older = release_handoff_dir / "release-handoff-a.json"
    latest = release_handoff_dir / "release-handoff-z.json"
    live_commit = "f" * 40
    release_handoff_dir.mkdir(parents=True, exist_ok=True)
    for path in (older, latest):
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": False,
                    "release_decision": "no-go",
                    "provider_preflight_ok": False,
                    "provider_preflight": {
                        "ok": False,
                        "provider_count": 3,
                        "ready_provider_count": 1,
                        "check_count": 7,
                        "failed_check_count": 4,
                        "missing_cli_count": 0,
                        "auth_context_missing_count": 2,
                    },
                }
            ),
            encoding="utf-8",
        )
    scan_calls: list[list[Path]] = []

    def fake_scan(*, workspace_root, extra_paths=None):
        scan_calls.append([Path(path) for path in extra_paths or []])
        return clean_scan(scanned=15)

    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", fake_scan)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", lambda **kwargs: desci_status(live_commit))
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=live_commit,
        auto_refresh_radar=False,
    )

    assert bundle["ok"] is True
    assert bundle["release_handoff"]["status"] == "valid"
    assert bundle["release_handoff"]["path"] == "apps/desci-platform/var/release-handoff-z.json"
    assert all(latest in call for call in scan_calls)
    assert all(older not in call for call in scan_calls)


def test_desci_launch_handoff_refresh_runs_without_optional_local_helpers(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    commit = "1" * 40
    radar = tmp_path / "var" / "radar.json"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-07" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    release_handoff_json = tmp_path / "apps" / "desci-platform" / "var" / "release-handoff-current.json"
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_count": 1,
                "adoption_status_counts": {"adopted": 1},
                "sources": [
                    {
                        "repo": "Veritas-7/autoresearch-skill-system",
                        "adoption_status": "adopted",
                        "latest_observed_commit": commit,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    release_handoff_json.parent.mkdir(parents=True, exist_ok=True)
    release_handoff_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ok": False,
                "release_decision": "no-go",
                "provider_preflight_ok": False,
                "provider_preflight": {
                    "ok": False,
                    "provider_count": 3,
                    "ready_provider_count": 1,
                    "check_count": 7,
                    "failed_check_count": 4,
                    "missing_cli_count": 0,
                    "auth_context_missing_count": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(refresh, "auto_research_status", None)
    monkeypatch.setattr(refresh, "desci_launch_secret_scan", None)

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=commit,
        auto_refresh_radar=False,
    )
    status_payload = json.loads(status_json.read_text(encoding="utf-8"))
    scan_payload = json.loads(scan_json.read_text(encoding="utf-8"))

    assert bundle["ok"] is True
    assert bundle["release_handoff"]["status"] == "valid"
    assert bundle["release_handoff"]["provider_preflight_present"] is True
    assert bundle["unexpected_failed_checks"] == []
    assert status_payload["source"]["live_source"]["status"] == "current"
    assert scan_payload["ok"] is True
    assert status_md.read_text(encoding="utf-8").startswith("# AutoResearch Operator Status")


def test_desci_launch_handoff_refresh_defaults_blank_status_topic_to_desci(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-07" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    status = desci_status(topic="")

    monkeypatch.setattr(refresh.auto_research_status, "build_status", lambda **kwargs: status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=tmp_path / "var" / "radar.json",
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit="2" * 40,
        auto_refresh_radar=False,
    )

    assert bundle["ok"] is True
    assert bundle["status"]["topic"] == "DeSci"
    assert json.loads(status_json.read_text(encoding="utf-8"))["preferred_topic"] == "DeSci"


def test_desci_launch_handoff_refresh_final_status_uses_active_bundle(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    live_commit = "4" * 40
    radar = tmp_path / "apps" / "desci-platform" / "var" / "radar.json"
    radar_md = tmp_path / "apps" / "desci-platform" / "docs" / "reports" / "2026-07" / "RADAR.md"
    status_json = tmp_path / "apps" / "desci-platform" / "var" / "status.json"
    status_md = tmp_path / "apps" / "desci-platform" / "docs" / "reports" / "2026-07" / "STATUS.md"
    scan_json = tmp_path / "apps" / "desci-platform" / "var" / "desci-launch-secret-scan-active.json"
    bundle_json = tmp_path / "apps" / "desci-platform" / "var" / "desci-launch-handoff-refresh-active.json"
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "repo": "Veritas-7/autoresearch-skill-system",
                        "latest_observed_commit": live_commit,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    radar_md.parent.mkdir(parents=True, exist_ok=True)
    radar_md.write_text("# radar\n", encoding="utf-8")
    formatted_reports = []

    def fake_build_status(**kwargs):
        report = desci_status(live_commit)
        report["desci"] = {
            "handoff_refresh": {
                "path": "var/desci-launch-handoff-refresh-stale.json",
                "live_source_status": "not_checked",
            },
            "launch_handoff_secret_scan": {
                "path": "var/desci-launch-secret-scan-stale.json",
                "scanned_paths": [],
            },
        }
        return report

    def fake_format_markdown(report):
        formatted_reports.append(json.loads(json.dumps(report)))
        return report["desci"]["handoff_refresh"]["path"]

    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", fake_format_markdown)
    monkeypatch.setattr(
        refresh.desci_launch_secret_scan,
        "build_desci_launch_secret_scan",
        lambda **kwargs: clean_scan(scanned=19),
    )

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=live_commit,
        auto_refresh_radar=False,
    )
    status_payload = json.loads(status_json.read_text(encoding="utf-8"))
    handoff = status_payload["desci"]["handoff_refresh"]
    secret_scan = status_payload["desci"]["launch_handoff_secret_scan"]

    assert bundle["ok"] is True
    assert handoff["path"] == "apps/desci-platform/var/desci-launch-handoff-refresh-active.json"
    assert handoff["live_source_status"] == "current"
    assert handoff["recorded_latest_observed_commit"] == live_commit
    assert handoff["source_fields_ready"] is True
    assert secret_scan["path"] == "apps/desci-platform/var/desci-launch-secret-scan-active.json"
    assert len(secret_scan["scanned_paths"]) == 19
    assert status_md.read_text(encoding="utf-8") == handoff["path"]
    assert formatted_reports[-1]["desci"]["handoff_refresh"]["path"] == handoff["path"]


def test_desci_launch_handoff_refresh_auto_refreshes_missing_radar_before_status(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "missing-radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    live_commit = "c" * 40
    seen_extra_paths: list[Path] = []

    def fake_radar_run(manifest_path, *, json_out=None, markdown_out=None, latest_commit_overrides=None):
        assert json_out == radar
        assert markdown_out == radar_md
        assert latest_commit_overrides == {"Veritas-7/autoresearch-skill-system": live_commit}
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "repo": "Veritas-7/autoresearch-skill-system",
                            "latest_observed_commit": live_commit,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text("# radar\n", encoding="utf-8")
        return {"source_count": 8, "adoption_status_counts": {"adopted": 8}}

    def fake_build_status(**kwargs):
        assert radar.is_file()
        assert radar_md.is_file()
        assert kwargs["live_source_commit"] == live_commit
        return desci_status(live_commit)

    def fake_scan(*, workspace_root, extra_paths=None):
        seen_extra_paths.extend(Path(path) for path in extra_paths or [])
        return clean_scan()

    monkeypatch.setattr(refresh.github_modernization_radar, "run", fake_radar_run)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", fake_scan)

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=live_commit,
    )

    assert bundle["ok"] is True
    assert bundle["radar"]["auto_refresh_needed"] is True
    assert bundle["radar"]["auto_refreshed"] is True
    assert bundle["radar"]["auto_refresh_reason"] == "missing"
    assert bundle["radar"]["recorded_latest_observed_commit"] == live_commit
    assert bundle["recorded_latest_observed_commit"] == live_commit
    assert radar in seen_extra_paths
    assert radar_md in seen_extra_paths


def test_desci_launch_handoff_refresh_fetches_live_source_by_default(monkeypatch, tmp_path):
    refresh = load_refresh_module()
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"
    scan_json = tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    live_commit = "d" * 40
    seen = {}

    def fake_build_status(**kwargs):
        seen["live_source_commit"] = kwargs["live_source_commit"]
        seen["live_source_checked"] = kwargs["live_source_checked"]
        seen["live_sources_checked"] = kwargs["live_sources_checked"]
        return desci_status(live_commit)

    monkeypatch.setattr(refresh.auto_research_status, "_fetch_veritas_live_commit", lambda workspace_root: live_commit)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    bundle = refresh.refresh_desci_launch_handoff(
        workspace_root=tmp_path,
        radar_json=tmp_path / "var" / "radar.json",
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        auto_refresh_radar=False,
    )

    assert bundle["ok"] is True
    assert seen == {
        "live_source_commit": live_commit,
        "live_source_checked": True,
        "live_sources_checked": False,
    }


def test_desci_launch_handoff_refresh_fails_when_status_topic_is_not_desci(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: desci_status(topic="DailyNews"),
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-unchecked-live-source",
            "--no-auto-radar-refresh",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))

    assert rc == 1
    assert bundle["ok"] is False
    assert bundle["topic_ok"] is False
    assert bundle["required_topic"] == "DeSci"
    assert bundle["status"]["topic"] == "DailyNews"
    assert bundle["secret_scan"]["ok"] is True


def test_desci_launch_handoff_refresh_fails_when_post_write_scan_finds_secret(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    fake_secret = "sk" + "_live_" + ("A" * 24)

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: desci_status(),
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.desci_launch_secret_scan,
        "build_desci_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": False,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [{"path": "status", "patterns": ["stripe_secret_key"], "value": fake_secret}],
            "finding_patterns": ["stripe_secret_key"],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-unchecked-live-source",
            "--no-auto-radar-refresh",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))
    raw_bundle = json.dumps(bundle)

    assert rc == 1
    assert bundle["ok"] is False
    assert bundle["secret_scan"]["findings"] == 1
    assert "stripe_secret_key" not in raw_bundle
    assert fake_secret not in raw_bundle


def test_desci_launch_handoff_refresh_fails_unexpected_action_required_failure(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: desci_status(state="action_required"),
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-action-required",
            "--allow-unchecked-live-source",
            "--no-auto-radar-refresh",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))

    assert rc == 1
    assert bundle["ok"] is False
    assert bundle["status_allowed"] is False
    assert bundle["unexpected_failed_checks"] == ["desci_launch_handoff_secret_scan_ready"]


def test_desci_launch_handoff_refresh_allows_bootstrap_self_gate(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    status = desci_status(state="action_required")
    status["checks"] = [{"name": "desci_launch_handoff_refresh_ready", "ok": False}]

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: status,
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-unchecked-live-source",
            "--no-auto-radar-refresh",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))

    assert rc == 0
    assert bundle["ok"] is True
    assert bundle["status_allowed"] is True
    assert bundle["action_required_failures_ok"] is True
    assert bundle["failed_checks"] == ["desci_launch_handoff_refresh_ready"]
    assert bundle["unexpected_failed_checks"] == []
    assert bundle["allowed_action_required_failures"] == ["desci_launch_handoff_refresh_ready"]


def test_desci_launch_handoff_refresh_reports_active_bundle_path(monkeypatch, tmp_path, capsys):
    refresh = load_refresh_module()
    bundle_json = tmp_path / "custom" / "handoff.json"

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: desci_status(),
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.desci_launch_secret_scan, "build_desci_launch_secret_scan", lambda **kwargs: clean_scan())

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "desci-launch-secret-scan-handoff-refresh.json"),
            "--bundle-json-out",
            str(bundle_json),
            "--allow-unchecked-live-source",
            "--no-auto-radar-refresh",
        ],
        workspace_root=tmp_path,
    )

    stdout = capsys.readouterr().out
    bundle = json.loads(bundle_json.read_text(encoding="utf-8"))

    assert rc == 0
    assert bundle["ok"] is True
    assert bundle["bundle_json_path"] == "custom/handoff.json"
    assert "bundle=custom/handoff.json" in stdout
