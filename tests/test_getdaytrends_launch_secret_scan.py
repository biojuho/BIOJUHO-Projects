import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "ops" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "getdaytrends_launch_secret_scan.py"


def load_scan_module():
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("getdaytrends_launch_secret_scan", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_default_getdaytrends_scan_files(
    workspace_root: Path,
    *,
    operator_status_text: str = "status",
) -> None:
    report_dir = workspace_root / "docs" / "reports" / "2026-06"
    var_dir = workspace_root / "var"
    project_docs = workspace_root / "automation" / "getdaytrends" / "docs"
    ops_scripts = workspace_root / "ops" / "scripts"
    report_dir.mkdir(parents=True, exist_ok=True)
    var_dir.mkdir(parents=True, exist_ok=True)
    project_docs.mkdir(parents=True, exist_ok=True)
    ops_scripts.mkdir(parents=True, exist_ok=True)
    (workspace_root / "automation" / "getdaytrends" / "QC_LOG.md").write_text(
        "getdaytrends qc\n",
        encoding="utf-8",
    )
    (workspace_root / "next-actions.md").write_text("getdaytrends next action\n", encoding="utf-8")
    (workspace_root / "HANDOFF.md").write_text("getdaytrends handoff\n", encoding="utf-8")
    (ops_scripts / "getdaytrends_update_credentials.py").write_text(
        "getdaytrends credential update script\n",
        encoding="utf-8",
    )
    (ops_scripts / "apply_workspace_supabase_pooler_url.py").write_text(
        "shared pooler updater script\n",
        encoding="utf-8",
    )
    (ops_scripts / "apply_workspace_supabase_pooler_url.ps1").write_text(
        "Read-Host \"Paste new Supabase Transaction pooler DATABASE_URL\" -AsSecureString\n",
        encoding="utf-8",
    )
    (ops_scripts / "supabase_pooler_management_probe.py").write_text(
        "Supabase Management API pooler probe\n",
        encoding="utf-8",
    )
    (ops_scripts / "supabase_pooler_shape_audit.py").write_text(
        "Supabase pooler shape audit\n",
        encoding="utf-8",
    )
    (ops_scripts / "complete_goal_local_credential_side_channel_audit.py").write_text(
        "Supabase local credential side-channel audit\n",
        encoding="utf-8",
    )
    (ops_scripts / "complete_goal_no_credential_refresh.py").write_text(
        "Complete goal no-credential refresh driver\n",
        encoding="utf-8",
    )
    getdaytrends_scripts = workspace_root / "automation" / "getdaytrends" / "scripts"
    getdaytrends_scripts.mkdir(parents=True, exist_ok=True)
    (getdaytrends_scripts / "verify_supabase_recovery_packet.py").write_text(
        "Supabase recovery packet verifier\n",
        encoding="utf-8",
    )
    (getdaytrends_scripts / "verify_provider_auth_recovery_packet.py").write_text(
        "Provider auth recovery packet verifier\n",
        encoding="utf-8",
    )
    (project_docs / "GITHUB_BENCHMARK_2026-06-04.md").write_text(
        "getdaytrends benchmark\n",
        encoding="utf-8",
    )
    (report_dir / "GETDAYTRENDS_LAUNCH_COMPLETION_AUDIT_2026-06-06.md").write_text(
        "getdaytrends launch audit\n",
        encoding="utf-8",
    )
    (report_dir / "AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_2026-06-06.md").write_text(
        "getdaytrends cycle report\n",
        encoding="utf-8",
    )
    (report_dir / "AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_STATUS_2026-06-06.md").write_text(
        operator_status_text,
        encoding="utf-8",
    )
    (report_dir / "GETDAYTRENDS_SUPABASE_EXTERNAL_REPAIR_PACKET_2026-06-09.md").write_text(
        "getdaytrends Supabase external repair packet\n",
        encoding="utf-8",
    )
    (report_dir / "AUTO_RESEARCH_COMPLETION_BLOCKER_MODEL_SPLIT_2026-06-09.md").write_text(
        "completion blocker model split\n",
        encoding="utf-8",
    )
    (report_dir / "GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS_BROWSER_FRESHNESS_2026-06-06.md").write_text(
        "getdaytrends radar report\n",
        encoding="utf-8",
    )
    (var_dir / "auto-research-status-getdaytrends-browser-freshness-2026-06-06.json").write_text(
        json.dumps({"status": "action_required"}),
        encoding="utf-8",
    )
    (var_dir / "github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json").write_text(
        json.dumps({"source_count": 8}),
        encoding="utf-8",
    )


def write_current_getdaytrends_artifacts(
    workspace_root: Path,
    *,
    provider_packet_text: str = "provider packet clean",
    supabase_packet_override: dict | None = None,
) -> None:
    project_root = workspace_root / "automation" / "getdaytrends"
    smoke_dir = project_root / "logs" / "smoke"
    readiness_dir = project_root / "logs" / "readiness"
    hygiene_dir = project_root / "logs" / "hygiene"
    var_dir = workspace_root / "var"
    for directory in (smoke_dir, readiness_dir, hygiene_dir, var_dir):
        directory.mkdir(parents=True, exist_ok=True)
    (var_dir / "workspace-smoke-getdaytrends-launch-final.json").write_text(
        json.dumps({"status": "action_required"}),
        encoding="utf-8",
    )
    (smoke_dir / "cli_smoke_latest.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (smoke_dir / "dashboard_browser_latest.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (smoke_dir / "dashboard_browser_tap_source_evidence.json").write_text(
        json.dumps({"status": "pass"}),
        encoding="utf-8",
    )
    (readiness_dir / "readiness_latest.json").write_text(json.dumps({"status": "fail"}), encoding="utf-8")
    (readiness_dir / "strict_readiness_latest.json").write_text(json.dumps({"status": "fail"}), encoding="utf-8")
    supabase_packet = supabase_packet_override or {
        "status": "blocked",
        "required_env": ["DATABASE_URL", "SUPABASE_URL"],
        "accepts_shared_supavisor_transaction_pooler": True,
        "accepts_dedicated_pgbouncer_transaction_pooler": True,
        "accepted_transaction_pooler_shapes": [
            {
                "kind": "shared_supavisor_transaction",
                "host": "aws-[region].pooler.supabase.com",
                "port": 6543,
                "username": "postgres.<project_ref>",
                "database": "postgres",
                "url_shape_without_password": (
                    "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres"
                ),
            },
            {
                "kind": "dedicated_pgbouncer_transaction",
                "host": "db.<project_ref>.supabase.co",
                "port": 6543,
                "username": "postgres",
                "database": "postgres",
                "url_shape_without_password": "postgres@db.<project_ref>.supabase.co:6543/postgres",
            },
        ],
        "secret_hygiene": {
            "masked_postgres_urls": True,
            "masked_supabase_pooler_users": True,
            "contains_plaintext_secret_values": False,
        },
    }
    (readiness_dir / "supabase_recovery_packet_latest.json").write_text(json.dumps(supabase_packet), encoding="utf-8")
    (readiness_dir / "strict_supabase_recovery_packet_latest.json").write_text(
        json.dumps(supabase_packet),
        encoding="utf-8",
    )
    (readiness_dir / "provider_auth_recovery_packet_latest.json").write_text(
        provider_packet_text,
        encoding="utf-8",
    )
    (readiness_dir / "strict_provider_auth_recovery_packet_latest.json").write_text(
        provider_packet_text,
        encoding="utf-8",
    )
    (hygiene_dir / "text_hygiene_latest.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")


def test_getdaytrends_launch_secret_scan_defaults_are_clean(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)

    report = scan.build_getdaytrends_launch_secret_scan(workspace_root=tmp_path)

    assert report["ok"] is True
    assert report["status"] == "valid"
    assert report["findings"] == []
    assert report["missing_paths"] == []
    assert len(report["scanned_paths"]) == 21
    assert "HANDOFF.md" in report["scanned_paths"]
    assert "ops/scripts/getdaytrends_update_credentials.py" in report["scanned_paths"]
    assert "ops/scripts/apply_workspace_supabase_pooler_url.py" in report["scanned_paths"]
    assert "ops/scripts/apply_workspace_supabase_pooler_url.ps1" in report["scanned_paths"]
    assert "ops/scripts/supabase_pooler_management_probe.py" in report["scanned_paths"]
    assert "ops/scripts/supabase_pooler_shape_audit.py" in report["scanned_paths"]
    assert "ops/scripts/complete_goal_local_credential_side_channel_audit.py" in report["scanned_paths"]
    assert "ops/scripts/complete_goal_no_credential_refresh.py" in report["scanned_paths"]
    assert "automation/getdaytrends/scripts/verify_supabase_recovery_packet.py" in report["scanned_paths"]
    assert "automation/getdaytrends/scripts/verify_provider_auth_recovery_packet.py" in report["scanned_paths"]
    assert "docs/reports/2026-06/GETDAYTRENDS_SUPABASE_EXTERNAL_REPAIR_PACKET_2026-06-09.md" in report["scanned_paths"]
    assert "docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_BLOCKER_MODEL_SPLIT_2026-06-09.md" in report["scanned_paths"]
    assert "docs/reports/2026-06/AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_STATUS_2026-06-06.md" in report["scanned_paths"]
    assert "var/github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json" in report["scanned_paths"]


def test_getdaytrends_launch_secret_scan_falls_back_to_modernization_reports(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    report_dir = tmp_path / "docs" / "reports" / "2026-06"
    for name in (
        "GETDAYTRENDS_LAUNCH_COMPLETION_AUDIT_2026-06-06.md",
        "AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_2026-06-06.md",
        "AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_STATUS_2026-06-06.md",
    ):
        (report_dir / name).unlink()

    report = scan.build_getdaytrends_launch_secret_scan(workspace_root=tmp_path)

    assert report["ok"] is True
    assert report["missing_paths"] == []
    assert (
        "docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS_BROWSER_FRESHNESS_2026-06-06.md"
        in report["scanned_paths"]
    )
    assert not any("GETDAYTRENDS_LAUNCH_COMPLETION_AUDITmissing" in path for path in report["missing_paths"])
    assert not any("AUTO_RESEARCH_GETDAYTRENDS_missing" in path for path in report["missing_paths"])


def test_getdaytrends_launch_secret_scan_can_include_current_artifacts(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    write_current_getdaytrends_artifacts(tmp_path)
    out = tmp_path / "var" / "getdaytrends-launch-secret-scan-current.json"

    rc = scan.main(["--include-current-artifacts", "--json-out", str(out)], workspace_root=tmp_path)
    report = json.loads(out.read_text(encoding="utf-8"))

    assert rc == 0
    assert report["ok"] is True
    assert report["include_current_artifacts"] is True
    assert report["supabase_recovery_packet_contract_ok"] is True
    assert report["supabase_recovery_packet_contract_errors"] == []
    assert len(report["scanned_paths"]) == 32
    assert "automation/getdaytrends/logs/smoke/cli_smoke_latest.json" in report["scanned_paths"]
    assert "automation/getdaytrends/logs/readiness/strict_readiness_latest.json" in report["scanned_paths"]
    assert "automation/getdaytrends/logs/readiness/strict_supabase_recovery_packet_latest.json" in report["scanned_paths"]
    assert "automation/getdaytrends/logs/readiness/provider_auth_recovery_packet_latest.json" in report["scanned_paths"]
    assert (
        "automation/getdaytrends/logs/readiness/strict_provider_auth_recovery_packet_latest.json"
        in report["scanned_paths"]
    )
    assert "var/workspace-smoke-getdaytrends-launch-final.json" in report["scanned_paths"]


def test_getdaytrends_launch_secret_scan_current_artifacts_prefer_fresh_dashboard_browser_smoke(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    write_current_getdaytrends_artifacts(tmp_path)
    smoke_dir = tmp_path / "automation" / "getdaytrends" / "logs" / "smoke"
    stale_latest = smoke_dir / "dashboard_browser_latest.json"
    fresh_full = smoke_dir / "dashboard_browser_full_smoke_fresh.json"
    tap_fixture = smoke_dir / "dashboard_browser_tap_source_newer.json"
    stale_latest.write_text(
        json.dumps({"status": "pass", "generated_at": "2026-06-07T01:00:00+09:00"}),
        encoding="utf-8",
    )
    fresh_full.write_text(
        json.dumps({"status": "pass", "generated_at": "2026-06-07T02:00:00+09:00"}),
        encoding="utf-8",
    )
    tap_fixture.write_text(
        json.dumps({"status": "pass", "generated_at": "2026-06-07T03:00:00+09:00"}),
        encoding="utf-8",
    )

    report = scan.build_getdaytrends_launch_secret_scan(
        workspace_root=tmp_path,
        include_current_artifacts=True,
    )

    assert report["ok"] is True
    assert report["supabase_recovery_packet_contract_ok"] is True
    assert len(report["scanned_paths"]) == 32
    assert "automation/getdaytrends/logs/smoke/dashboard_browser_full_smoke_fresh.json" in report["scanned_paths"]
    assert "automation/getdaytrends/logs/smoke/dashboard_browser_latest.json" not in report["scanned_paths"]
    assert "automation/getdaytrends/logs/smoke/dashboard_browser_tap_source_newer.json" not in report["scanned_paths"]
    assert "automation/getdaytrends/logs/smoke/dashboard_browser_tap_source_evidence.json" in report["scanned_paths"]


def test_getdaytrends_launch_secret_scan_current_artifacts_prefer_fresh_complete_workspace_smoke(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    write_current_getdaytrends_artifacts(tmp_path)
    var_dir = tmp_path / "var"
    launch_final = var_dir / "workspace-smoke-getdaytrends-launch-final.json"
    current_cycle = var_dir / "workspace-smoke-getdaytrends-current-cycle-2026-06-07.json"
    newer_partial = var_dir / "workspace-smoke-getdaytrends-newer-partial.json"
    launch_final.write_text(
        json.dumps(
            {
                "status": "complete",
                "generated_at": "2026-06-07T03:30:00+09:00",
                "summary": {"total": 6, "completed": 6, "passed": 5, "failed": 1, "remaining": 0},
            }
        ),
        encoding="utf-8",
    )
    current_cycle.write_text(
        json.dumps(
            {
                "status": "complete",
                "generated_at": "2026-06-07T02:00:00+09:00",
                "summary": {"total": 6, "completed": 6, "passed": 5, "failed": 1, "remaining": 0},
            }
        ),
        encoding="utf-8",
    )
    newer_partial.write_text(
        json.dumps(
            {
                "status": "partial",
                "generated_at": "2026-06-07T03:00:00+09:00",
                "summary": {"total": 6, "completed": 2, "passed": 2, "failed": 0, "remaining": 4},
            }
        ),
        encoding="utf-8",
    )

    report = scan.build_getdaytrends_launch_secret_scan(
        workspace_root=tmp_path,
        include_current_artifacts=True,
    )

    assert report["ok"] is True
    assert report["supabase_recovery_packet_contract_ok"] is True
    assert len(report["scanned_paths"]) == 32
    assert "var/workspace-smoke-getdaytrends-current-cycle-2026-06-07.json" in report["scanned_paths"]
    assert "var/workspace-smoke-getdaytrends-launch-final.json" not in report["scanned_paths"]
    assert "var/workspace-smoke-getdaytrends-newer-partial.json" not in report["scanned_paths"]


def test_getdaytrends_launch_secret_scan_ignores_newer_single_check_smoke_when_launch_final_exists(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    write_current_getdaytrends_artifacts(tmp_path)
    var_dir = tmp_path / "var"
    launch_final = var_dir / "workspace-smoke-getdaytrends-launch-final.json"
    single_check = var_dir / "workspace-smoke-getdaytrends-single-check-proof.json"
    launch_final.write_text(
        json.dumps(
            {
                "status": "complete",
                "generated_at": "2026-06-07T02:00:00+09:00",
                "summary": {"total": 6, "completed": 6, "passed": 5, "failed": 1, "remaining": 0},
            }
        ),
        encoding="utf-8",
    )
    single_check.write_text(
        json.dumps(
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {
                    "total": 1,
                    "completed": 1,
                    "passed": 0,
                    "failed": 1,
                    "remaining": 0,
                    "expected_external_failures": ["getdaytrends launch readiness gate"],
                    "unexpected_failures": [],
                },
            }
        ),
        encoding="utf-8",
    )

    report = scan.build_getdaytrends_launch_secret_scan(
        workspace_root=tmp_path,
        include_current_artifacts=True,
    )

    assert report["ok"] is True
    assert "var/workspace-smoke-getdaytrends-launch-final.json" in report["scanned_paths"]
    assert "var/workspace-smoke-getdaytrends-single-check-proof.json" not in report["scanned_paths"]


def test_getdaytrends_launch_secret_scan_fails_without_echoing_secret_value(tmp_path):
    scan = load_scan_module()
    fake_google_key = "AI" + "za" + "ABCDEFGHIJKLMNOPQRST"
    write_default_getdaytrends_scan_files(
        tmp_path,
        operator_status_text=f"bad getdaytrends handoff value {fake_google_key}",
    )
    out = tmp_path / "var" / "getdaytrends-launch-secret-scan.json"

    rc = scan.main(["--json-out", str(out)], workspace_root=tmp_path)
    report = json.loads(out.read_text(encoding="utf-8"))
    raw_report = json.dumps(report)

    assert rc == 1
    assert report["ok"] is False
    assert report["finding_patterns"] == ["google_api_key"]
    assert report["findings"][0]["patterns"] == ["google_api_key"]
    assert "AUTO_RESEARCH_GETDAYTRENDS_BROWSER_FRESHNESS_STATUS_2026-06-06.md" in report["findings"][0]["path"]
    assert fake_google_key not in raw_report


def test_getdaytrends_launch_secret_scan_current_artifact_leak_fails_without_echoing_value(tmp_path):
    scan = load_scan_module()
    fake_openai_key = "sk-" + "a" * 24
    write_default_getdaytrends_scan_files(tmp_path)
    write_current_getdaytrends_artifacts(
        tmp_path,
        provider_packet_text=f"provider packet accidentally contains {fake_openai_key}",
    )

    report = scan.build_getdaytrends_launch_secret_scan(
        workspace_root=tmp_path,
        include_current_artifacts=True,
    )
    raw_report = json.dumps(report)

    assert report["ok"] is False
    assert report["finding_patterns"] == ["openai_api_key"]
    assert report["findings"][0]["patterns"] == ["openai_api_key"]
    assert "provider_auth_recovery_packet_latest.json" in report["findings"][0]["path"]
    assert fake_openai_key not in raw_report


def test_getdaytrends_launch_secret_scan_requires_both_supabase_recovery_packet_shapes(tmp_path):
    scan = load_scan_module()
    write_default_getdaytrends_scan_files(tmp_path)
    packet = {
        "status": "blocked",
        "required_env": ["DATABASE_URL", "SUPABASE_URL"],
        "accepts_shared_supavisor_transaction_pooler": True,
        "accepts_dedicated_pgbouncer_transaction_pooler": False,
        "accepted_transaction_pooler_shapes": [
            {
                "kind": "shared_supavisor_transaction",
                "host": "aws-[region].pooler.supabase.com",
                "port": 6543,
                "username": "postgres.<project_ref>",
                "database": "postgres",
                "url_shape_without_password": (
                    "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres"
                ),
            }
        ],
        "secret_hygiene": {
            "masked_postgres_urls": True,
            "masked_supabase_pooler_users": True,
            "contains_plaintext_secret_values": False,
        },
    }
    write_current_getdaytrends_artifacts(tmp_path, supabase_packet_override=packet)
    out = tmp_path / "var" / "getdaytrends-launch-secret-scan-current.json"

    rc = scan.main(["--include-current-artifacts", "--json-out", str(out)], workspace_root=tmp_path)
    report = json.loads(out.read_text(encoding="utf-8"))

    assert rc == 1
    assert report["ok"] is False
    assert report["status"] == "valid"
    assert report["findings"] == []
    assert report["supabase_recovery_packet_contract_ok"] is False
    assert any(
        "accepts_dedicated_pgbouncer_transaction_pooler must be true" in error
        for error in report["supabase_recovery_packet_contract_errors"]
    )
    assert any(
        "accepted_transaction_pooler_shapes missing dedicated_pgbouncer_transaction" in error
        for error in report["supabase_recovery_packet_contract_errors"]
    )
