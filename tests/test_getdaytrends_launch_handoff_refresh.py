import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "ops" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "getdaytrends_launch_handoff_refresh.py"


def load_refresh_module():
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("getdaytrends_launch_handoff_refresh", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_getdaytrends_launch_handoff_refresh_writes_status_then_scans_outputs(monkeypatch, tmp_path):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"
    scan_json = tmp_path / "var" / "scan.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text("{}", encoding="utf-8")
    seen_extra_paths = []

    def fake_build_status(**kwargs):
        return {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_canonical_smoke_pass", "ok": False, "detail": "launch readiness gate"},
                {"name": "getdaytrends_handoff_docs_secret_scan_ready", "ok": True, "detail": "clean"},
            ],
            "source": {"live_source": {}},
        }

    def fake_scan(*, workspace_root, extra_paths=None, include_current_artifacts=False):
        assert include_current_artifacts is True
        seen_extra_paths.extend(Path(path) for path in extra_paths or [])
        assert status_json.is_file()
        assert status_md.is_file()
        return {
            "schema_version": 1,
            "include_current_artifacts": include_current_artifacts,
            "status": "valid",
            "ok": True,
            "supabase_recovery_packet_contract_ok": True,
            "supabase_recovery_packet_contract_errors": [],
            "scanned_paths": ["status", "markdown", "radar"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        }

    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.getdaytrends_launch_secret_scan, "build_getdaytrends_launch_secret_scan", fake_scan)

    bundle = refresh.refresh_getdaytrends_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        allow_action_required=True,
    )

    assert bundle["ok"] is True
    assert bundle["status_allowed"] is True
    assert bundle["action_required_failures_ok"] is True
    assert bundle["failed_checks"] == [
        "getdaytrends_canonical_smoke_pass",
        "getdaytrends_strict_readiness_pass",
    ]
    assert bundle["unexpected_failed_checks"] == []
    assert bundle["status"]["state"] == "action_required"
    assert bundle["status"]["topic"] == "getdaytrends"
    assert bundle["secret_scan"]["scanned"] == 3
    assert bundle["secret_scan"]["include_current_artifacts"] is True
    assert bundle["secret_scan"]["supabase_recovery_packet_contract_ok"] is True
    assert bundle["secret_scan"]["supabase_recovery_packet_contract_errors"] == []
    assert status_json.is_file()
    assert json.loads(status_json.read_text(encoding="utf-8"))["preferred_topic"] == "getdaytrends"
    assert status_md.read_text(encoding="utf-8") == "operator markdown"
    assert json.loads(scan_json.read_text(encoding="utf-8"))["ok"] is True
    assert json.loads(bundle_json.read_text(encoding="utf-8"))["ok"] is True
    assert status_json in seen_extra_paths
    assert status_md in seen_extra_paths
    assert radar in seen_extra_paths


def test_getdaytrends_launch_handoff_refresh_surfaces_completion_audit_blockers_when_status_is_ok(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"
    scan_json = tmp_path / "var" / "scan.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text("{}", encoding="utf-8")

    def fake_build_status(**kwargs):
        return {
            "schema_version": 1,
            "status": "ok",
            "preferred_topic": "shared_supabase",
            "checks": [{"name": "getdaytrends_handoff_docs_secret_scan_ready", "ok": True}],
            "completion_audit": {
                "blocking_requirements": [
                    "dailynews_first_run_launch_ready",
                    "getdaytrends_strict_readiness_pass",
                    "getdaytrends_canonical_smoke_pass",
                ]
            },
            "source": {"live_source": {}},
        }

    def fake_scan(*, workspace_root, extra_paths=None, include_current_artifacts=False):
        return {
            "schema_version": 1,
            "include_current_artifacts": include_current_artifacts,
            "status": "valid",
            "ok": True,
            "supabase_recovery_packet_contract_ok": True,
            "supabase_recovery_packet_contract_errors": [],
            "scanned_paths": ["status", "markdown", "radar"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        }

    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.getdaytrends_launch_secret_scan, "build_getdaytrends_launch_secret_scan", fake_scan)

    bundle = refresh.refresh_getdaytrends_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        allow_action_required=True,
        require_getdaytrends_topic=False,
    )

    assert bundle["ok"] is True
    assert bundle["effective_status"] == "action_required"
    assert bundle["status"]["state"] == "ok"
    assert bundle["status"]["effective_state"] == "action_required"
    assert bundle["completion_blocking_requirements"] == [
        "dailynews_first_run_launch_ready",
        "getdaytrends_canonical_smoke_pass",
        "getdaytrends_strict_readiness_pass",
    ]
    assert bundle["failed_checks"] == [
        "dailynews_first_run_launch_ready",
        "getdaytrends_canonical_smoke_pass",
        "getdaytrends_strict_readiness_pass",
    ]
    assert bundle["unexpected_failed_checks"] == []
    assert bundle["action_required_failures_ok"] is True
    assert json.loads(bundle_json.read_text(encoding="utf-8"))["effective_status"] == "action_required"


def test_getdaytrends_launch_handoff_refresh_auto_refreshes_missing_radar_before_status(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "missing-radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"
    scan_json = tmp_path / "var" / "scan.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    seen_extra_paths = []

    def fake_radar_run(manifest_path, *, json_out=None, markdown_out=None, latest_commit_overrides=None):
        assert json_out == radar
        assert markdown_out == radar_md
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text('{"source_count": 8}', encoding="utf-8")
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text("# radar\n", encoding="utf-8")
        return {"source_count": 8, "adoption_status_counts": {"adopted": 8}}

    def fake_build_status(**kwargs):
        assert radar.is_file()
        assert radar_md.is_file()
        return {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_canonical_smoke_pass", "ok": False, "detail": "launch readiness gate"},
            ],
            "source": {"live_source": {}},
        }

    def fake_scan(*, workspace_root, extra_paths=None, include_current_artifacts=False):
        assert include_current_artifacts is True
        seen_extra_paths.extend(Path(path) for path in extra_paths or [])
        return {
            "schema_version": 1,
            "include_current_artifacts": include_current_artifacts,
            "status": "valid",
            "ok": True,
            "supabase_recovery_packet_contract_ok": True,
            "supabase_recovery_packet_contract_errors": [],
            "scanned_paths": ["status", "markdown", "radar", "radar_md"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        }

    monkeypatch.setattr(refresh.github_modernization_radar, "run", fake_radar_run)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.getdaytrends_launch_secret_scan, "build_getdaytrends_launch_secret_scan", fake_scan)

    bundle = refresh.refresh_getdaytrends_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        allow_action_required=True,
    )

    assert bundle["ok"] is True
    assert bundle["radar"]["auto_refresh_needed"] is True
    assert bundle["radar"]["auto_refreshed"] is True
    assert bundle["radar"]["source_count"] == 8
    assert bundle["radar"]["adoption_status_counts"] == {"adopted": 8}
    assert radar in seen_extra_paths
    assert radar_md in seen_extra_paths
    assert json.loads(bundle_json.read_text(encoding="utf-8"))["radar"]["auto_refreshed"] is True


def test_getdaytrends_launch_handoff_refresh_auto_refreshes_missing_radar_markdown_before_scan(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"
    scan_json = tmp_path / "var" / "scan.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "repo": "Veritas-7/autoresearch-skill-system",
                        "latest_observed_commit": "a" * 40,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    seen_extra_paths = []

    def fake_radar_run(manifest_path, *, json_out=None, markdown_out=None, latest_commit_overrides=None):
        assert json_out == radar
        assert markdown_out == radar_md
        assert latest_commit_overrides is None
        radar.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "repo": "Veritas-7/autoresearch-skill-system",
                            "latest_observed_commit": "a" * 40,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        radar_md.parent.mkdir(parents=True, exist_ok=True)
        radar_md.write_text("# radar\n", encoding="utf-8")
        return {"source_count": 8, "adoption_status_counts": {"adopted": 8}}

    def fake_scan(*, workspace_root, extra_paths=None, include_current_artifacts=False):
        assert include_current_artifacts is True
        seen_extra_paths.extend(Path(path) for path in extra_paths or [])
        assert radar_md.is_file()
        return {
            "schema_version": 1,
            "include_current_artifacts": include_current_artifacts,
            "status": "valid",
            "ok": True,
            "supabase_recovery_packet_contract_ok": True,
            "supabase_recovery_packet_contract_errors": [],
            "scanned_paths": ["status", "markdown", "radar", "radar_md"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        }

    monkeypatch.setattr(refresh.github_modernization_radar, "run", fake_radar_run)
    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_canonical_smoke_pass", "ok": False, "detail": "launch readiness gate"},
            ],
            "source": {"live_source": {}},
        },
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(refresh.getdaytrends_launch_secret_scan, "build_getdaytrends_launch_secret_scan", fake_scan)

    bundle = refresh.refresh_getdaytrends_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        allow_action_required=True,
    )

    assert bundle["ok"] is True
    assert bundle["radar"]["auto_refresh_needed"] is True
    assert bundle["radar"]["auto_refresh_reason"] == "missing_markdown"
    assert bundle["radar"]["auto_refreshed"] is True
    assert radar_md in seen_extra_paths
    assert json.loads(bundle_json.read_text(encoding="utf-8"))["radar"]["auto_refresh_reason"] == "missing_markdown"


def test_getdaytrends_launch_handoff_refresh_auto_refreshes_stale_live_source_radar(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    radar = tmp_path / "var" / "radar.json"
    radar_md = tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"
    status_json = tmp_path / "var" / "status.json"
    status_md = tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"
    scan_json = tmp_path / "var" / "scan.json"
    bundle_json = tmp_path / "var" / "bundle.json"
    live_commit = "f" * 40
    radar.parent.mkdir(parents=True, exist_ok=True)
    radar.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "repo": "Veritas-7/autoresearch-skill-system",
                        "latest_observed_commit": "e" * 40,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_radar_run(manifest_path, *, json_out=None, markdown_out=None, latest_commit_overrides=None):
        assert latest_commit_overrides == {"Veritas-7/autoresearch-skill-system": live_commit}
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

    monkeypatch.setattr(refresh.github_modernization_radar, "run", fake_radar_run)
    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_canonical_smoke_pass", "ok": False, "detail": "launch readiness gate"},
            ],
            "source": {"live_source": {"status": "current", "detail": "recorded=f live=f"}},
        },
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": True,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        },
    )

    bundle = refresh.refresh_getdaytrends_launch_handoff(
        workspace_root=tmp_path,
        radar_json=radar,
        radar_markdown_out=radar_md,
        status_json_out=status_json,
        status_markdown_out=status_md,
        secret_scan_json_out=scan_json,
        bundle_json_out=bundle_json,
        live_source_commit=live_commit,
        allow_action_required=True,
    )

    assert bundle["ok"] is True
    assert bundle["radar"]["auto_refresh_reason"] == "stale_live_source_commit"
    assert bundle["radar"]["auto_refreshed"] is True
    assert bundle["radar"]["recorded_latest_observed_commit"] == live_commit


def test_getdaytrends_launch_handoff_refresh_allows_expected_recovery_packet_action_required(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_canonical_smoke_pass", "ok": False, "detail": "launch readiness gate"},
                {
                    "name": "getdaytrends_recovery_packet_actionable",
                    "ok": False,
                    "detail": "status=blocked issues=runtime_database_fallback action_present=true",
                },
            ],
            "source": {"live_source": {}},
        },
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": True,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "scan.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-action-required",
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
    assert bundle["failed_checks"] == [
        "getdaytrends_canonical_smoke_pass",
        "getdaytrends_recovery_packet_actionable",
        "getdaytrends_strict_readiness_pass",
    ]
    assert bundle["unexpected_failed_checks"] == []
    assert "getdaytrends_recovery_packet_actionable" in bundle["allowed_action_required_failures"]


def test_getdaytrends_launch_handoff_refresh_fails_on_unexpected_action_required_check(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "action_required",
            "preferred_topic": "getdaytrends",
            "checks": [
                {"name": "getdaytrends_strict_readiness_pass", "ok": False, "detail": "external credential"},
                {"name": "getdaytrends_browser_evidence_fresh", "ok": False, "detail": "unexpected stale browser evidence"},
            ],
            "source": {"live_source": {}},
        },
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": True,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "scan.json"),
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
    assert bundle["action_required_failures_ok"] is False
    assert bundle["failed_checks"] == [
        "getdaytrends_browser_evidence_fresh",
        "getdaytrends_strict_readiness_pass",
    ]
    assert bundle["unexpected_failed_checks"] == ["getdaytrends_browser_evidence_fresh"]


def test_getdaytrends_launch_handoff_refresh_fails_when_post_write_scan_finds_secret(monkeypatch, tmp_path):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {"schema_version": 1, "status": "ok", "preferred_topic": "getdaytrends", "checks": []},
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": False,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [{"path": "status", "patterns": ["google_api_key"]}],
            "finding_patterns": ["google_api_key"],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "scan.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-action-required",
            "--allow-unchecked-live-source",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))
    scan = json.loads((tmp_path / "var" / "scan.json").read_text(encoding="utf-8"))

    assert rc == 1
    assert bundle["ok"] is False
    assert bundle["secret_scan"]["findings"] == 1
    assert scan["finding_patterns"] == ["google_api_key"]


def test_getdaytrends_launch_handoff_refresh_fails_when_status_topic_is_not_getdaytrends(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()

    monkeypatch.setattr(
        refresh.auto_research_status,
        "build_status",
        lambda **kwargs: {"schema_version": 1, "status": "ok", "preferred_topic": "DailyNews", "checks": []},
    )
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": True,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "scan.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
            "--allow-unchecked-live-source",
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))

    assert rc == 1
    assert bundle["ok"] is False
    assert bundle["topic_ok"] is False
    assert bundle["required_topic"] == "getdaytrends"
    assert bundle["status"]["topic"] == "DailyNews"
    assert bundle["secret_scan"]["ok"] is True


def test_getdaytrends_launch_handoff_refresh_main_requires_live_source_by_default(
    monkeypatch,
    tmp_path,
):
    refresh = load_refresh_module()
    live_commit = "a" * 40

    def fake_radar_run(manifest_path, *, json_out=None, markdown_out=None, latest_commit_overrides=None):
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
        assert kwargs["live_source_commit"] == live_commit
        assert kwargs["live_source_checked"] is True
        return {
            "schema_version": 1,
            "status": "ok",
            "preferred_topic": "getdaytrends",
            "checks": [],
            "source": {
                "live_source": {
                    "checked": True,
                    "status": "current",
                    "detail": f"recorded={live_commit} live={live_commit}",
                }
            },
        }

    monkeypatch.setattr(refresh.auto_research_status, "_fetch_veritas_live_commit", lambda workspace_root: live_commit)
    monkeypatch.setattr(refresh.github_modernization_radar, "run", fake_radar_run)
    monkeypatch.setattr(refresh.auto_research_status, "build_status", fake_build_status)
    monkeypatch.setattr(refresh.auto_research_status, "format_markdown", lambda report: "operator markdown")
    monkeypatch.setattr(
        refresh.getdaytrends_launch_secret_scan,
        "build_getdaytrends_launch_secret_scan",
        lambda **kwargs: {
            "schema_version": 1,
            "status": "valid",
            "ok": True,
            "scanned_paths": ["status"],
            "missing_paths": [],
            "findings": [],
            "finding_patterns": [],
        },
    )

    rc = refresh.main(
        [
            "--radar-json",
            str(tmp_path / "var" / "radar.json"),
            "--radar-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "RADAR.md"),
            "--status-json-out",
            str(tmp_path / "var" / "status.json"),
            "--status-markdown-out",
            str(tmp_path / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_GETDAYTRENDS_STATUS.md"),
            "--secret-scan-json-out",
            str(tmp_path / "var" / "scan.json"),
            "--bundle-json-out",
            str(tmp_path / "var" / "bundle.json"),
        ],
        workspace_root=tmp_path,
    )

    bundle = json.loads((tmp_path / "var" / "bundle.json").read_text(encoding="utf-8"))

    assert rc == 0
    assert bundle["ok"] is True
    assert bundle["live_source_required"] is True
    assert bundle["live_source_ok"] is True
    assert bundle["live_source_status"] == "current"
