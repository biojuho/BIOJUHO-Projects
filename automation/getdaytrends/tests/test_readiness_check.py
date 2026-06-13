import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import readiness_check

_FAKE_OPENAI_KEY = "sk-" + "secretopenai123456"
_FAKE_GOOGLE_KEY = "AI" + "zaABCDEFGHIJKLMNOPQRST"
_FAKE_LEAKED_OPENAI_KEY = "sk-" + "realSecretValue123456"
_FAKE_LEAKED_GOOGLE_KEY = "AI" + "zaReallySecretGoogleKey12345"
_FAKE_POOLER_USER = "postgres" + ".secretref"
_FAKE_PASSWORD_DATABASE_URL = (
    "postgresql://"
    + _FAKE_POOLER_USER
    + ":"
    + "password"
    + "@example.supabase.com:6543/postgres"
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scheduled_wrapper_strips_ansi_escape_sequences_before_writing_logs():
    script = Path(__file__).resolve().parents[1] / "run_scheduled_getdaytrends.ps1"
    source = script.read_text(encoding="utf-8")

    assert '$env:NO_COLOR = "1"' in source
    assert '$env:LOGURU_COLORIZE = "false"' in source
    assert "function Remove-AnsiEscapeSequences" in source
    assert "$escape = [char]27" in source
    assert '-replace "$escape\\[[0-?]*[ -/]*[@-~]"' in source
    assert "$text = Remove-AnsiEscapeSequences -Text $text" in source


def test_scheduled_wrapper_writes_artifact_json_without_utf8_bom():
    script = Path(__file__).resolve().parents[1] / "run_scheduled_getdaytrends.ps1"
    source = script.read_text(encoding="utf-8")

    assert "Set-Content -Path $artifactPath" not in source
    assert "[System.IO.File]::WriteAllText($artifactPath, $artifactJson" in source
    assert "[System.Text.UTF8Encoding]::new($false)" in source


def test_readiness_passes_with_complete_artifacts(tmp_path):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    report = tmp_path / "readiness.json"

    _write_json(smoke, {"status": "pass", "summary": {"total": 2, "passed": 2, "failed": 0}, "results": []})
    screenshot.write_bytes(b"png")
    _write_json(
        browser,
        {
            "status": "pass",
            "schema_version": 1,
            "summary": {"total": 3, "passed": 3, "failed": 0},
            "screenshot": str(screenshot),
        },
    )
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": [], "summary": {"checked": 4}})
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-04_010000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "summary_fallback_log": str(scheduler_dir / "fallback.log"),
            "duration_seconds": 1.2,
        },
    )

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=scheduler_dir,
        report_path=report,
        require_browser=True,
        require_scheduler=True,
    )

    assert payload["status"] == "pass"
    assert payload["summary"]["failed"] == 0
    assert report.exists()


def test_readiness_report_records_launch_requirement_flags(tmp_path):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    report = tmp_path / "readiness.json"

    _write_json(smoke, {"status": "pass", "summary": {"total": 2, "passed": 2, "failed": 0}, "results": []})
    screenshot.write_bytes(b"png")
    _write_json(
        browser,
        {
            "status": "pass",
            "schema_version": 1,
            "summary": {"total": 3, "passed": 3, "failed": 0},
            "screenshot": str(screenshot),
        },
    )
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": [], "summary": {"checked": 4}})
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-04_010000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=scheduler_dir,
        report_path=report,
        require_browser=True,
        require_scheduler=True,
        require_tap_fixture_browser=True,
        max_cli_smoke_age_hours=24,
        max_browser_smoke_age_hours=24,
        max_scheduler_age_hours=24,
        fail_on_runtime_fallback=True,
        require_live_db=False,
    )

    assert payload["requirements"] == {
        "require_browser": True,
        "require_tap_fixture_browser": True,
        "require_scheduler": True,
        "fail_on_runtime_fallback": True,
        "require_live_db": False,
        "max_cli_smoke_age_hours": 24,
        "max_browser_smoke_age_hours": 24,
        "max_scheduler_age_hours": 24,
    }
    assert json.loads(report.read_text(encoding="utf-8"))["requirements"] == payload["requirements"]


def test_readiness_fails_missing_smoke_report(tmp_path):
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    screenshot.write_bytes(b"png")
    _write_json(browser, {"status": "pass", "summary": {"failed": 0}, "screenshot": str(screenshot)})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})

    payload = readiness_check.run_readiness(
        smoke_report=tmp_path / "missing-smoke.json",
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=tmp_path / "scheduler",
        report_path=tmp_path / "readiness.json",
        require_browser=True,
        require_scheduler=False,
    )

    assert payload["status"] == "fail"
    assert any(check["name"] == "cli_smoke_report" and not check["ok"] for check in payload["checks"])


def test_cli_smoke_max_age_policy_fails_stale_report(tmp_path):
    stale_time = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": stale_time,
            "summary": {"total": 4, "passed": 4, "failed": 0},
            "results": [],
        },
    )

    check = readiness_check.check_smoke_report(smoke, max_age_hours=24)

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["age_hours"] >= 24
    assert check.evidence["max_age_hours"] == 24
    assert "max allowed" in check.message
    assert "smoke_cli.py --include-dry-run" in check.remediation


def test_cli_smoke_max_age_policy_accepts_fresh_report(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 4, "passed": 4, "failed": 0},
            "results": [],
        },
    )

    check = readiness_check.check_smoke_report(smoke, max_age_hours=24)

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["age_hours"] <= 1
    assert check.evidence["max_age_hours"] == 24


def test_cli_smoke_runtime_fallback_policy_allows_by_default(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "results": [
                {
                    "name": "stats",
                    "ok": True,
                    "stdout_tail": "",
                    "stderr_tail": "PostgreSQL connection failed; falling back to local SQLite for this run",
                }
            ],
        },
    )

    check = readiness_check.check_smoke_report(smoke)

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["runtime_fallback_count"] == 1
    assert check.evidence["runtime_fallbacks"][0]["kind"] == "database.sqlite_fallback"


def test_cli_smoke_runtime_fallback_policy_fails_when_strict(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "results": [
                {
                    "name": "stats",
                    "ok": True,
                    "stdout_tail": "",
                    "stderr_tail": (
                        "PostgreSQL connection failed; falling back to local SQLite for this run\n"
                        "Failed to init cost DB: connection failed (falling back to in-memory)"
                    ),
                }
            ],
        },
    )

    check = readiness_check.check_smoke_report(smoke, fail_on_runtime_fallback=True)

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["fail_on_runtime_fallback"] is True
    assert check.evidence["runtime_fallback_count"] == 2
    assert "runtime fallback" in check.message
    assert "Fix DATABASE_URL" in check.remediation
    assert "cost DB" in check.remediation
    assert "python scripts\\smoke_cli.py --include-dry-run" in check.remediation
    assert "without fallback. Dry-run validate" in check.remediation
    assert "without fallback. dry-run" not in check.remediation
    assert "verification bundle. rerun python" not in check.remediation.lower()
    assert "then rerun the verification bundle. the verification bundle includes" in check.remediation.lower()


def test_cli_smoke_runtime_fallback_policy_uses_report_summary_fields(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "runtime_fallback_count": 1,
            "runtime_fallbacks": [
                {
                    "check": "stats",
                    "stream": "stderr_tail",
                    "kind": "database.sqlite_fallback",
                    "snippet": f"{_FAKE_PASSWORD_DATABASE_URL} fell back to SQLite",
                }
            ],
            "results": [
                {
                    "name": "stats",
                    "ok": True,
                    "stdout_tail": "",
                    "stderr_tail": "",
                }
            ],
        },
    )

    check = readiness_check.check_smoke_report(smoke, fail_on_runtime_fallback=True)

    assert check.ok is False
    assert check.evidence["runtime_fallback_count"] == 1
    assert check.evidence["runtime_fallbacks"][0]["kind"] == "database.sqlite_fallback"
    assert _FAKE_PASSWORD_DATABASE_URL not in check.evidence["runtime_fallbacks"][0]["snippet"]
    assert "postgresql://***" in check.evidence["runtime_fallbacks"][0]["snippet"]


def test_cli_smoke_runtime_fallback_policy_uses_database_only_remediation(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "results": [
                {
                    "name": "stats",
                    "ok": True,
                    "stdout_tail": "",
                    "stderr_tail": "PostgreSQL connection failed; falling back to local SQLite for this run",
                }
            ],
        },
    )

    check = readiness_check.check_smoke_report(smoke, fail_on_runtime_fallback=True)

    assert check.ok is False
    assert check.evidence["runtime_fallback_count"] == 1
    assert "Fix DATABASE_URL" in check.remediation
    assert "cost DB" not in check.remediation
    assert "python scripts\\smoke_cli.py --include-dry-run" in check.remediation
    assert "without fallback. Dry-run validate" in check.remediation
    assert "without fallback. dry-run" not in check.remediation
    assert "verification bundle. rerun python" not in check.remediation.lower()
    assert "then rerun the verification bundle. the verification bundle includes" in check.remediation.lower()


def test_provider_auth_report_accepts_clean_cli_smoke(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "results": [{"name": "dry_run", "ok": True, "stdout_tail": "ok", "stderr_tail": ""}],
        },
    )

    check = readiness_check.check_provider_auth_report(smoke)

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["provider_auth_failure_count"] == 0


def test_provider_auth_report_fails_leaked_or_invalid_keys_and_masks_values(tmp_path):
    smoke = tmp_path / "smoke.json"
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 2, "passed": 2, "failed": 0},
            "results": [
                {
                    "name": "dry_run",
                    "ok": True,
                    "stdout_tail": "",
                    "stderr_tail": (
                        "ClientError: 403 PERMISSION_DENIED. Your API key was reported as leaked. "
                        f"Incorrect API key provided: {_FAKE_OPENAI_KEY}. "
                        f"Google key {_FAKE_GOOGLE_KEY} should not appear. "
                        "Your team 1c3c0277-c0a6-4041-ba8b-eac0623e3f2c has either used all available credits "
                        "or reached its monthly spending limit."
                    ),
                }
            ],
        },
    )

    check = readiness_check.check_provider_auth_report(smoke)

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["provider_auth_failure_count"] >= 3
    raw = json.dumps(check.to_dict())
    assert _FAKE_OPENAI_KEY not in raw
    assert _FAKE_GOOGLE_KEY not in raw
    assert "1c3c0277-c0a6-4041-ba8b-eac0623e3f2c" not in raw
    assert "sk-***" in raw
    assert "AIza***" in raw
    assert "team ***" in raw
    kinds = {failure["kind"] for failure in check.evidence["provider_auth_failures"]}
    assert "provider.quota_or_billing" in kinds
    assert "Rotate or revoke" in check.remediation
    assert "python scripts\\smoke_cli.py --include-dry-run" in check.remediation
    assert "verification bundle. then rerun" not in check.remediation.lower()
    assert "then rerun the verification bundle. the verification bundle includes" in check.remediation.lower()


def test_provider_auth_report_scans_scheduler_detail_log_and_masks_values(tmp_path):
    smoke = tmp_path / "smoke.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text(
        "ClientError: 403 PERMISSION_DENIED. "
        "Your API key was reported as leaked. "
        f"Google key {_FAKE_GOOGLE_KEY} should not appear. "
        "Your team 1c3c0277-c0a6-4041-ba8b-eac0623e3f2c has reached its monthly spending limit.",
        encoding="utf-8",
    )
    summary.write_text("ok", encoding="utf-8")
    _write_json(
        smoke,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 1, "passed": 1, "failed": 0},
            "results": [{"name": "dry_run", "ok": True, "stdout_tail": "ok", "stderr_tail": ""}],
        },
    )
    _write_json(
        scheduler_dir / "run_2026-06-07_010000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.0,
        },
    )

    check = readiness_check.check_provider_auth_report(smoke, scheduler_dir=scheduler_dir)

    assert check.ok is False
    assert check.level == "ERROR"
    assert "CLI smoke and scheduler output contains" in check.message
    kinds = {failure["kind"] for failure in check.evidence["provider_auth_failures"]}
    assert "provider.api_key_leaked" in kinds
    assert "provider.permission_denied" in kinds
    assert "provider.quota_or_billing" in kinds
    assert any(failure["check"] == "scheduler_artifact" for failure in check.evidence["provider_auth_failures"])
    raw = json.dumps(check.to_dict())
    assert _FAKE_GOOGLE_KEY not in raw
    assert "1c3c0277-c0a6-4041-ba8b-eac0623e3f2c" not in raw
    assert "AIza***" in raw
    assert "team ***" in raw


def test_live_db_doctor_passes_when_command_succeeds(monkeypatch):
    def fake_run(*args, **kwargs):
        return readiness_check.subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=(
                "[OK] db.database_url_source: DATABASE_URL source: workspace root .env\n"
                "[OK] db.supabase_url_shape: Supabase transaction pooler shape detected"
                "\n[OK] db.supabase_project_ref_crosscheck: DATABASE_URL and SUPABASE_URL project refs match (ref_fp=1234567890)"
            ),
            stderr="",
        )

    monkeypatch.setattr(readiness_check.subprocess, "run", fake_run)

    check = readiness_check.check_live_db_doctor(python_exe="python")

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["exit_code"] == 0
    assert any("db.supabase_url_shape" in line for line in check.evidence["diagnostics"])
    assert any("db.supabase_project_ref_crosscheck" in line for line in check.evidence["diagnostics"])


def test_live_db_doctor_fails_with_masked_diagnostics(monkeypatch):
    def fake_run(*args, **kwargs):
        return readiness_check.subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout=(
                f"DATABASE     : {_FAKE_PASSWORD_DATABASE_URL}\n"
                "[OK] db.database_url_source: DATABASE_URL source: workspace root .env\n"
                f"[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: user={_FAKE_POOLER_USER}\n"
                "[WARN] db.supabase_project_ref_crosscheck: SUPABASE_URL is not set; cannot cross-check DATABASE_URL project ref\n"
                "[OK] db.endpoint_dns: Database endpoint DNS resolved: host=example.supabase.com, addresses=1\n"
                "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded: host=example.supabase.com, port=6543\n"
                "[ERROR] db.live_postgres: Live PostgreSQL probe failed: InternalServerError: "
                f"(ENOTFOUND) tenant/user {_FAKE_POOLER_USER} not found"
            ),
            stderr="",
        )

    monkeypatch.setattr(readiness_check.subprocess, "run", fake_run)

    check = readiness_check.check_live_db_doctor(python_exe="python")

    assert check.ok is False
    assert check.level == "ERROR"
    assert "tenant/user ***" in check.message
    assert check.evidence["failure_type"] == "diagnostic_error"
    assert "Diagnostics:" not in check.message
    assert any("db.endpoint_tcp" in line for line in check.evidence["diagnostics"])
    assert _FAKE_POOLER_USER not in json.dumps(check.evidence)
    assert "password" not in json.dumps(check.evidence)
    assert "Set SUPABASE_URL from the same Supabase project" in check.remediation
    assert "Supabase project ref" in check.remediation
    assert "python main.py --doctor --require-live-db" in check.remediation
    assert "pooler settings. Dry-run validate" in check.remediation
    assert "pooler settings. dry-run" not in check.remediation
    assert "verification bundle. rerun python" not in check.remediation.lower()
    assert "then rerun the verification bundle. the verification bundle includes" in check.remediation.lower()
    assert readiness_check.SUPABASE_CONNECTION_REFERENCE["url"] in check.remediation


def test_live_db_doctor_prioritizes_supabase_project_ref_mismatch(monkeypatch):
    def fake_run(*args, **kwargs):
        return readiness_check.subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout=(
                f"[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: user={_FAKE_POOLER_USER}\n"
                "[ERROR] db.supabase_project_ref_crosscheck: DATABASE_URL pooler project ref does not match SUPABASE_URL "
                "(database_ref_fp=1111111111, supabase_url_ref_fp=2222222222)\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(readiness_check.subprocess, "run", fake_run)

    check = readiness_check.check_live_db_doctor(python_exe="python")

    assert check.ok is False
    assert "db.supabase_project_ref_crosscheck" in check.message
    assert "Diagnostics:" not in check.message
    assert "Copy both SUPABASE_URL and the Transaction pooler DATABASE_URL" in check.remediation
    assert "pooler settings. Dry-run validate" in check.remediation
    assert "pooler settings. dry-run" not in check.remediation
    assert _FAKE_POOLER_USER not in json.dumps(check.evidence)
    assert "database_ref_fp=1111111111" in check.message


def test_pooler_runtime_compatibility_requires_prepared_statement_cache_disabled(tmp_path):
    good_connection = tmp_path / "connection.py"
    good_main = tmp_path / "main.py"
    missing_marker = tmp_path / "migrate.py"
    good_connection.write_text("await asyncpg.connect(url, statement_cache_size=0)\n", encoding="utf-8")
    good_main.write_text("conn = await asyncpg.connect(url, statement_cache_size = 0)\n", encoding="utf-8")
    missing_marker.write_text("await asyncpg.create_pool(url)\n", encoding="utf-8")

    ok_check = readiness_check.check_pooler_runtime_compatibility(paths=(good_connection, good_main))

    assert ok_check.ok is True
    assert ok_check.level == "OK"
    assert ok_check.evidence["required_marker"] == "statement_cache_size=0"
    assert all(item["statement_cache_size_zero"] for item in ok_check.evidence["checked_files"])

    failed_check = readiness_check.check_pooler_runtime_compatibility(
        paths=(good_connection, good_main, missing_marker)
    )

    assert failed_check.ok is False
    assert failed_check.level == "ERROR"
    assert str(missing_marker) in failed_check.evidence["missing_statement_cache_disable"]
    assert "statement_cache_size=0" in failed_check.remediation
    assert readiness_check.SUPABASE_CONNECTION_REFERENCE["url"] in failed_check.remediation


def test_supabase_recovery_packet_masks_and_classifies_blocker():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal.",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [
                        {
                            "check": "doctor",
                            "stream": "stderr_tail",
                            "kind": "database.sqlite_fallback",
                            "snippet": (
                                f"{_FAKE_PASSWORD_DATABASE_URL} "
                                "postgresql connection failed; falling back to local sqlite"
                            ),
                        }
                    ],
                },
            },
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor failed.",
                "remediation": "Set SUPABASE_URL and DATABASE_URL, then rerun.",
                "evidence": {
                    "diagnostics": [
                        f"[OK] db.supabase_url_shape: user={_FAKE_POOLER_USER}",
                        "[WARN] db.supabase_project_ref_crosscheck: SUPABASE_URL is not set; cannot cross-check DATABASE_URL project ref",
                        "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded: host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543",
                        f"[ERROR] db.live_postgres: Live PostgreSQL probe failed: tenant/user {_FAKE_POOLER_USER} not found",
                    ]
                },
            },
            {
                "name": "provider_auth_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke contains 1 provider authentication failure signal(s).",
                "evidence": {
                    "provider_auth_failure_count": 1,
                    "provider_auth_failures": [
                        {
                            "check": "dry_run",
                            "stream": "stderr_tail",
                            "kind": "provider.permission_denied",
                            "snippet": "permission_denied",
                        }
                    ],
                },
            },
        ],
    }

    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert packet["status"] == "blocked"
    assert packet["required_env"] == ["DATABASE_URL", "SUPABASE_URL"]
    assert "runtime_database_fallback" in packet["issue_types"]
    assert "missing_supabase_url_crosscheck" in packet["issue_types"]
    assert "pooler_tenant_user_not_found" in packet["issue_types"]
    assert packet["live_db_failure_type"] == "diagnostic_error"
    assert packet["source_checks"]["cli_smoke_report"]["runtime_fallback_kinds"] == ["database.sqlite_fallback"]
    assert packet["source_checks"]["cli_smoke_report"]["runtime_fallback_checks"] == ["doctor"]
    assert packet["source_checks"]["live_db_doctor"]["failure_type"] == "diagnostic_error"
    assert [item["name"] for item in packet["blocking_checks"]] == ["cli_smoke_report", "live_db_doctor"]
    assert "Runtime fallback checks: doctor" in packet["recovery_summary"]
    assert "Runtime fallback checks: doctor" in packet["recovery_bundle"]
    assert "provider_auth_report" not in packet["recovery_summary"]
    assert "provider_auth_report" not in packet["recovery_bundle"]
    assert "Transaction pooler" in packet["next_required_action"]
    assert packet["next_required_action"].startswith("Pause scheduled/background getdaytrends clients")
    assert "SUPABASE_URL is missing" in packet["operator_focus"]
    assert "DATABASE_URL belongs to the intended project" in packet["operator_focus"]
    assert "then dry-run validate" in packet["next_required_action"]
    assert "then Dry-run validate" not in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --database-url-stdin" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --database-url-stdin --write" in packet["next_required_action"]
    assert "verification bundle" in packet["next_required_action"]
    assert "python main.py --doctor --require-live-db" in packet["verification_commands"]
    assert packet["verification_command_bundle"].startswith("Set-Location -LiteralPath '")
    assert "automation\\getdaytrends" in packet["verification_command_bundle"]
    assert packet["credential_update_command_bundle"].startswith("Set-Location -LiteralPath '")
    assert "input-status" in packet["credential_update_command_bundle"]
    assert "Fast path" in packet["credential_update_command_bundle"]
    assert "Get-Clipboard -Raw" in packet["credential_update_command_bundle"]
    assert "without interactive EOF" in packet["credential_update_command_bundle"]
    assert "Pause scheduled/background getdaytrends clients" in packet["credential_update_command_bundle"]
    assert "circuit breaker" in packet["credential_update_command_bundle"]
    assert "wait at least 2 minutes" in packet["credential_update_command_bundle"]
    assert "Interactive fallback" in packet["credential_update_command_bundle"]
    assert "Transaction pooler DATABASE_URL" in packet["credential_update_command_bundle"]
    assert "Ctrl+Z, then Enter in PowerShell" in packet["credential_update_command_bundle"]
    assert "getdaytrends_update_credentials.py --database-url-stdin" in packet["credential_update_command_bundle"]
    assert "getdaytrends_update_credentials.py --database-url-stdin --write" in packet["credential_update_command_bundle"]
    assert packet["scheduler_task_names"] == ["GetDayTrends_CurrentUser", "GetDayTrends", "GetDayTrends_NewTask"]
    assert packet["scheduler_pause_command_bundle"].startswith("Set-Location -LiteralPath '")
    assert "data\\getdaytrends.lock" in packet["scheduler_pause_command_bundle"]
    assert "Get-Process -Id" in packet["scheduler_pause_command_bundle"]
    assert "schtasks /Query /TN" in packet["scheduler_pause_command_bundle"]
    assert "schtasks /Change /TN $taskName /DISABLE" in packet["scheduler_pause_command_bundle"]
    assert "GetDayTrends_CurrentUser" in packet["scheduler_pause_command_bundle"]
    assert packet["scheduler_resume_command_bundle"].startswith("Set-Location -LiteralPath '")
    assert "schtasks /Change /TN $taskName /ENABLE" in packet["scheduler_resume_command_bundle"]
    assert "live DB doctor" in packet["scheduler_resume_command_bundle"]
    assert "python scripts\\browser_smoke.py --tap-source-fixture" in packet["verification_command_bundle"]
    assert "python scripts\\check_text_hygiene.py" in packet["verification_command_bundle"]
    assert "python scripts\\readiness_check.py" in packet["verification_command_bundle"]
    assert "getdaytrends_launch_secret_scan.py" in packet["verification_command_bundle"]
    assert "--include-current-artifacts" in packet["verification_command_bundle"]
    assert "python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends" in packet["verification_command_bundle"]
    assert "workspace-smoke-getdaytrends-operator-recheck.json" in packet["verification_command_bundle"]
    assert "workspace-smoke-getdaytrends-launch-final.json" not in packet["verification_command_bundle"]
    assert packet["reference_links"] == [
        readiness_check.SUPABASE_CONNECTION_REFERENCE,
        readiness_check.SUPABASE_SUPAVISOR_TERMINOLOGY_REFERENCE,
        readiness_check.SUPABASE_CIRCUIT_BREAKER_REFERENCE,
        readiness_check.MICROSOFT_SCHTASKS_QUERY_REFERENCE,
        readiness_check.MICROSOFT_SCHTASKS_CHANGE_REFERENCE,
    ]
    assert packet["connection_mode_facts"] == readiness_check.SUPABASE_TRANSACTION_POOLER_FACTS
    assert "Expected DATABASE_URL mode: Supabase Transaction pooler." in packet["connection_mode_facts"]
    assert readiness_check.ACCEPTED_TRANSACTION_POOLER_SHAPE_SUMMARY in packet["connection_mode_facts"]
    assert any(
        "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres" in fact
        for fact in packet["connection_mode_facts"]
    )
    assert any(
        "postgres@db.<project_ref>.supabase.co:6543/postgres" in fact
        for fact in packet["connection_mode_facts"]
    )
    assert packet["accepted_transaction_pooler_shapes"] == readiness_check.ACCEPTED_TRANSACTION_POOLER_SHAPES
    shape_by_kind = {shape["kind"]: shape for shape in packet["accepted_transaction_pooler_shapes"]}
    assert shape_by_kind["shared_supavisor_transaction"]["username"] == "postgres.<project_ref>"
    assert shape_by_kind["dedicated_pgbouncer_transaction"]["username"] == "postgres"
    assert shape_by_kind["shared_supavisor_transaction"]["url_shape_without_password"].endswith(":6543/postgres")
    assert shape_by_kind["dedicated_pgbouncer_transaction"]["url_shape_without_password"].endswith(":6543/postgres")
    assert packet["accepts_shared_supavisor_transaction_pooler"] is True
    assert packet["accepts_dedicated_pgbouncer_transaction_pooler"] is True
    assert any("pause scheduled/background getdaytrends clients" in fact for fact in packet["connection_mode_facts"])
    assert any("Supavisor/shared pooler circuit breaker" in fact for fact in packet["connection_mode_facts"])
    assert any("statement_cache_size=0" in fact for fact in packet["connection_mode_facts"])
    assert any("user+database+mode" in fact for fact in packet["connection_mode_facts"])
    assert "SUPABASE_URL=https://<project_ref>.supabase.co" in packet["env_template"]
    assert "DATABASE_URL=<transaction_pooler_uri_from_same_project>" in packet["env_template"]
    assert "aws-1-ap-northeast-2.pooler.supabase.com:6543" in packet["env_template"]
    assert "# getdaytrends Supabase recovery bundle" in packet["recovery_bundle"]
    assert "## Next required action" in packet["recovery_bundle"]
    assert packet["next_required_action"] in packet["recovery_bundle"]
    assert "## Operator focus" in packet["recovery_bundle"]
    assert packet["operator_focus"] in packet["recovery_bundle"]
    assert "## Current blocker summary" in packet["recovery_bundle"]
    assert "Operator focus:" in packet["recovery_summary"]
    assert "pooler_tenant_user_not_found" in packet["recovery_bundle"]
    assert "db.endpoint_tcp" in packet["recovery_bundle"]
    assert "## Evidence freshness" in packet["recovery_bundle"]
    assert "Packet generated:" in packet["recovery_bundle"]
    assert "Readiness generated:" in packet["recovery_bundle"]
    assert "Readiness report:" in packet["recovery_bundle"]
    assert "## Launch success criteria" in packet["recovery_bundle"]
    assert "Pooler runtime compatibility reports OK" in packet["recovery_bundle"]
    assert "Canonical getdaytrends workspace smoke reports all configured checks PASS" in packet["recovery_bundle"]
    assert "## Env template" in packet["recovery_bundle"]
    assert "## Connection mode facts" in packet["recovery_bundle"]
    assert "Expected port: 6543." in packet["recovery_bundle"]
    assert "statement_cache_size=0" in packet["recovery_bundle"]
    assert "user+database+mode" in packet["recovery_bundle"]
    assert "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres" in packet["recovery_bundle"]
    assert "postgres@db.<project_ref>.supabase.co:6543/postgres" in packet["recovery_bundle"]
    assert "## Scheduler pause commands" in packet["recovery_bundle"]
    assert packet["scheduler_pause_command_bundle"] in packet["recovery_bundle"]
    assert "## Credential update commands" in packet["recovery_bundle"]
    assert packet["credential_update_command_bundle"] in packet["recovery_bundle"]
    assert "## Recovery checklist" in packet["recovery_bundle"]
    assert "Pause scheduled/background getdaytrends clients" in packet["recovery_bundle"]
    assert "Copy and run the scheduler pause commands" in packet["recovery_bundle"]
    assert "pooler_runtime_compatibility is OK" in packet["recovery_bundle"]
    assert [item["step"] for item in packet["post_credential_recheck_sequence"]] == [
        "live_db_doctor",
        "cli_smoke",
        "strict_readiness",
        "canonical_workspace_smoke",
    ]
    assert "## Post-credential recheck sequence" in packet["recovery_bundle"]
    assert "Command: python main.py --doctor --require-live-db" in packet["recovery_bundle"]
    assert "Success: CLI smoke completes with runtime_fallback_count 0." in packet["recovery_bundle"]
    assert "Success: Strict readiness reports status pass." in packet["recovery_bundle"]
    assert [item["artifact"] for item in packet["post_credential_recheck_evidence"]] == [
        "operator console output",
        "logs\\smoke\\cli_smoke_latest.json",
        "logs\\readiness\\readiness_latest.json",
        "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
    ]
    assert "## Post-credential evidence artifacts" in packet["recovery_bundle"]
    assert "Signal: runtime_fallback_count=0." in packet["recovery_bundle"]
    assert "Artifact: logs\\readiness\\readiness_latest.json" in packet["recovery_bundle"]
    assert "Signal: status=pass and failed=0." in packet["recovery_bundle"]
    assert [item["artifact"] for item in packet["operator_final_proof_bundle"]] == [
        "logs\\readiness\\readiness_latest.json",
        "logs\\smoke\\cli_smoke_latest.json",
        "logs\\smoke\\dashboard_browser_latest.json",
        "logs\\smoke\\dashboard_browser_tap_source_evidence.json",
        "logs\\hygiene\\text_hygiene_latest.json",
        "..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json",
        "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
    ]
    assert "## Operator final proof bundle" in packet["recovery_bundle"]
    assert "cli_smoke_report/live_db_doctor both OK" in packet["recovery_bundle"]
    assert "status=valid, findings=0, missing=0" in packet["recovery_bundle"]
    assert "## Scheduler resume commands" in packet["recovery_bundle"]
    assert packet["scheduler_resume_command_bundle"] in packet["recovery_bundle"]
    assert "wait at least 2 minutes" in packet["recovery_bundle"]
    assert "Choose one accepted Transaction pooler connection string" in packet["recovery_bundle"]
    assert "## References" in packet["recovery_bundle"]
    assert readiness_check.SUPABASE_CONNECTION_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.SUPABASE_CONNECTION_REFERENCE["url"] in packet["recovery_bundle"]
    assert readiness_check.SUPABASE_CIRCUIT_BREAKER_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.SUPABASE_CIRCUIT_BREAKER_REFERENCE["url"] in packet["recovery_bundle"]
    assert readiness_check.MICROSOFT_SCHTASKS_QUERY_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.MICROSOFT_SCHTASKS_QUERY_REFERENCE["url"] in packet["recovery_bundle"]
    assert readiness_check.MICROSOFT_SCHTASKS_CHANGE_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.MICROSOFT_SCHTASKS_CHANGE_REFERENCE["url"] in packet["recovery_bundle"]
    assert "## Verification commands" in packet["recovery_bundle"]
    assert "Set-Location -LiteralPath" in packet["recovery_bundle"]
    assert "run_workspace_smoke.py --scope getdaytrends" in packet["recovery_bundle"]
    assert "workspace-smoke-getdaytrends-operator-recheck.json" in packet["recovery_bundle"]
    assert "workspace-smoke-getdaytrends-launch-final.json" not in packet["recovery_bundle"]
    assert "Status: blocked" in packet["recovery_summary"]
    assert "Issue types:" in packet["recovery_summary"]
    assert "Next required action:" in packet["recovery_summary"]
    assert "live_db_doctor" in packet["recovery_summary"]
    assert packet["evidence_freshness"]["packet_generated_at"]
    assert packet["evidence_freshness"]["readiness_generated_at"] == payload["generated_at"]
    assert "Readiness report:" in packet["evidence_freshness_summary"]
    assert "runtime_fallback_count 0" in "\n".join(packet["launch_success_criteria"])
    assert "Production text hygiene reports pass" in "\n".join(packet["launch_success_criteria"])
    assert "Launch secret scan reports valid" in "\n".join(packet["launch_success_criteria"])
    assert "Pooler runtime compatibility reports OK" in "\n".join(packet["launch_success_criteria"])
    assert "Strict readiness reports status pass" in "\n".join(packet["launch_success_criteria"])
    assert packet["source_checks"]["pooler_runtime_compatibility"]["evaluated"] is False
    raw = json.dumps(packet)
    assert _FAKE_POOLER_USER not in raw
    assert f"{_FAKE_POOLER_USER}:password" not in raw
    assert "password@example.supabase.com" not in raw
    assert "postgresql://***" in raw
    assert "tenant/user ***" in raw


def test_supabase_recovery_packet_focuses_current_pooler_credentials_when_shape_passes():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal.",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [
                        {
                            "check": "stats",
                            "stream": "stderr_tail",
                            "kind": "database.sqlite_fallback",
                            "snippet": f"tenant/user {_FAKE_POOLER_USER} not found",
                        }
                    ],
                },
            },
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor failed.",
                "evidence": {
                    "diagnostics": [
                        f"[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543, user={_FAKE_POOLER_USER}",
                        "[OK] db.supabase_project_ref_crosscheck: DATABASE_URL and SUPABASE_URL project refs match (ref_fp=1234567890)",
                        "[OK] db.endpoint_dns: Database endpoint DNS resolved: host=aws-1-ap-northeast-2.pooler.supabase.com, addresses=2",
                        "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded: host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543",
                        f"[ERROR] db.live_postgres: Live PostgreSQL probe failed: tenant/user {_FAKE_POOLER_USER} not found",
                    ]
                },
            },
        ],
    }

    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert "pooler_tenant_user_not_found" in packet["issue_types"]
    assert "Project refs, DNS, and TCP already pass" in packet["operator_focus"]
    assert "Transaction pooler credentials" in packet["operator_focus"]
    assert "credential_update_command_bundle" in packet
    assert "getdaytrends_update_credentials.py --database-url-stdin --write" in packet["credential_update_command_bundle"]
    assert "## Operator focus" in packet["recovery_bundle"]
    assert "## Credential update commands" in packet["recovery_bundle"]
    assert packet["operator_focus"] in packet["recovery_bundle"]
    assert "Operator focus:" in packet["recovery_summary"]
    assert "Runtime fallback checks: stats" in packet["recovery_summary"]
    assert "Runtime fallback checks: stats" in packet["recovery_bundle"]
    raw = json.dumps(packet)
    assert _FAKE_POOLER_USER not in raw
    assert "tenant/user ***" in raw


def test_supabase_recovery_packet_classifies_non_transaction_pooler_mode():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal.",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [{"kind": "database.sqlite_fallback", "snippet": "fallback"}],
                },
            },
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor failed.",
                "evidence": {
                    "diagnostics": [
                        f"[ERROR] db.supabase_pooler_mode: Supabase pooler URL must use the Shared Pooler transaction mode for production launch readiness: host=aws-1-ap-northeast-2.pooler.supabase.com, port=5432, expected_port=6543, user={_FAKE_POOLER_USER}, database=postgres",
                    ]
                },
            },
        ],
    }

    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert "supabase_transaction_pooler_required" in packet["issue_types"]
    assert packet["next_required_action"].startswith("Pause scheduled/background getdaytrends clients")
    assert "port 6543" in packet["next_required_action"]
    assert "Transaction pooler URI" in packet["operator_focus"]
    raw = json.dumps(packet)
    assert _FAKE_POOLER_USER not in raw
    assert "expected_port=6543" in raw


def test_supabase_recovery_packet_classifies_live_db_timeout():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with runtime fallback.",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [{"kind": "database.sqlite_fallback", "snippet": "fallback"}],
                },
            },
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor timed out after 45s.",
                "remediation": "Fix DATABASE_URL / Supabase pooler credentials.",
                "evidence": {"timeout": True, "diagnostics": [], "output_tail": ""},
            },
        ],
    }

    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert packet["status"] == "blocked"
    assert "live_db_doctor_timeout" in packet["issue_types"]
    assert "live_postgres_probe_failed" in packet["issue_types"]
    assert "runtime_database_fallback" in packet["issue_types"]
    assert packet["next_required_action"].startswith("Pause scheduled/background getdaytrends clients")
    assert "SUPABASE_URL" in packet["next_required_action"]
    assert "DATABASE_URL" in packet["next_required_action"]
    assert "Transaction pooler" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --database-url-stdin" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --database-url-stdin --write" in packet["next_required_action"]
    assert "verification bundle" in packet["next_required_action"]
    assert "live_db_doctor_timeout" in packet["recovery_summary"]


def test_provider_auth_recovery_packet_masks_and_classifies_blocker():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke failed.",
                "evidence": {"path": "logs/smoke/cli_smoke_latest.json"},
            },
            {
                "name": "provider_auth_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke contains 2 provider authentication failure signal(s).",
                "remediation": readiness_check.PROVIDER_AUTH_REMEDIATION,
                "evidence": {
                    "provider_auth_failure_count": 2,
                    "provider_auth_failures": [
                        {
                            "check": "generate",
                            "stream": "stderr_tail",
                            "kind": "provider.api_key_leaked",
                            "snippet": f"Your API key was reported as leaked: {_FAKE_LEAKED_OPENAI_KEY}",
                        },
                        {
                            "check": "generate",
                            "stream": "stderr_tail",
                            "kind": "provider.permission_denied",
                            "snippet": f"PERMISSION_DENIED for {_FAKE_LEAKED_GOOGLE_KEY}",
                        },
                    ],
                },
            },
        ],
    }

    packet = readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert packet["status"] == "blocked"
    assert packet["required_env"] == ["OPENAI_API_KEY", "GOOGLE_API_KEY"]
    assert packet["provider_auth_failure_count"] == 2
    assert packet["source_checks"]["provider_auth_report"]["provider_auth_failure_count"] == 2
    assert "provider.api_key_leaked" in packet["issue_types"]
    assert "provider.permission_denied" in packet["issue_types"]
    assert "Revoke any leaked provider key immediately" in packet["next_required_action"]
    assert "GETDAYTRENDS_NEW_OPENAI_API_KEY" in packet["next_required_action"]
    assert "GETDAYTRENDS_NEW_GOOGLE_API_KEY" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --write" in packet["next_required_action"]
    assert "python scripts\\smoke_cli.py --include-dry-run" in packet["verification_commands"]
    assert packet["verification_command_bundle"].startswith("Set-Location -LiteralPath '")
    assert packet["reference_links"] == [
        readiness_check.OPENAI_API_KEY_REFERENCE,
        readiness_check.GOOGLE_AI_API_KEY_REFERENCE,
    ]
    assert "# getdaytrends provider credential recovery bundle" in packet["recovery_bundle"]
    assert "## Launch success criteria" in packet["recovery_bundle"]
    assert "provider_auth_failure_count 0" in packet["recovery_bundle"]
    assert "## Env template" in packet["recovery_bundle"]
    assert "OPENAI_API_KEY=<rotated_openai_key_if_used>" in packet["env_template"]
    assert "GOOGLE_API_KEY=<rotated_google_ai_key_if_used>" in packet["env_template"]
    assert "## Recovery checklist" in packet["recovery_bundle"]
    assert "production secret store" in packet["recovery_bundle"]
    assert "## References" in packet["recovery_bundle"]
    assert readiness_check.OPENAI_API_KEY_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.OPENAI_API_KEY_REFERENCE["url"] in packet["recovery_bundle"]
    assert readiness_check.GOOGLE_AI_API_KEY_REFERENCE["label"] in packet["recovery_bundle"]
    assert readiness_check.GOOGLE_AI_API_KEY_REFERENCE["url"] in packet["recovery_bundle"]
    assert "## Verification commands" in packet["recovery_bundle"]
    assert "run_workspace_smoke.py --scope getdaytrends" in packet["recovery_bundle"]
    assert "workspace-smoke-getdaytrends-operator-recheck.json" in packet["recovery_bundle"]
    assert "workspace-smoke-getdaytrends-launch-final.json" not in packet["recovery_bundle"]
    assert "Status: blocked" in packet["recovery_summary"]
    assert [item["name"] for item in packet["blocking_checks"]] == ["provider_auth_report"]
    assert "cli_smoke_report" not in packet["recovery_summary"]
    assert "cli_smoke_report" not in packet["recovery_bundle"]
    assert "Provider auth failure count: 2" in packet["recovery_summary"]
    assert packet["evidence_freshness"]["readiness_generated_at"] == payload["generated_at"]
    raw = json.dumps(packet)
    assert _FAKE_LEAKED_OPENAI_KEY not in raw
    assert _FAKE_LEAKED_GOOGLE_KEY not in raw
    assert "sk-***" in raw
    assert "AIza***" in raw


def test_provider_auth_recovery_packet_permission_denied_names_secret_destinations():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal(s).",
                "evidence": {"path": "logs/smoke/cli_smoke_latest.json"},
            },
            {
                "name": "provider_auth_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke contains 1 provider authentication failure signal(s).",
                "remediation": readiness_check.PROVIDER_AUTH_REMEDIATION,
                "evidence": {
                    "provider_auth_failure_count": 1,
                    "provider_auth_failures": [
                        {
                            "check": "dry_run",
                            "stream": "stderr_tail",
                            "kind": "provider.permission_denied",
                            "snippet": "Please use another API key.",
                        },
                    ],
                },
            },
        ],
    }

    packet = readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert [item["name"] for item in packet["blocking_checks"]] == ["provider_auth_report"]
    assert "cli_smoke_report" not in packet["recovery_summary"]
    assert "provider key" in packet["next_required_action"]
    assert ".env" in packet["next_required_action"]
    assert "production secret store" in packet["next_required_action"]
    assert "GETDAYTRENDS_NEW_OPENAI_API_KEY" in packet["next_required_action"]
    assert "GETDAYTRENDS_NEW_GOOGLE_API_KEY" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py" in packet["next_required_action"]
    assert "getdaytrends_update_credentials.py --write" in packet["next_required_action"]
    assert "verification bundle" in packet["next_required_action"]


def test_provider_auth_recovery_packet_combines_leaked_key_and_billing_actions():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "provider_auth_report",
                "ok": False,
                "level": "ERROR",
                "message": "Provider auth failures.",
                "evidence": {
                    "provider_auth_failure_count": 2,
                    "provider_auth_failures": [
                        {
                            "check": "dry_run",
                            "stream": "stderr_tail",
                            "kind": "provider.api_key_leaked",
                            "snippet": "Your API key was reported as leaked.",
                        },
                        {
                            "check": "dry_run",
                            "stream": "stderr_tail",
                            "kind": "provider.quota_or_billing",
                            "snippet": "Your team *** has reached its monthly spending limit.",
                        },
                    ],
                },
            }
        ],
    }

    packet = readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert "provider.api_key_leaked" in packet["issue_types"]
    assert "provider.quota_or_billing" in packet["issue_types"]
    assert "Revoke any leaked provider key immediately" in packet["next_required_action"]
    assert "billing/credit limits" in packet["next_required_action"]
    assert "production secret store" in packet["next_required_action"]


def test_provider_auth_recovery_packet_clear_exposes_zero_failure_count():
    payload = {
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "name": "provider_auth_report",
                "ok": True,
                "level": "OK",
                "message": "No provider authentication failures found in CLI smoke output.",
                "evidence": {
                    "provider_auth_failure_count": 0,
                    "provider_auth_failures": [],
                },
            },
        ],
    }

    packet = readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_check.DEFAULT_REPORT)

    assert packet["status"] == "clear"
    assert packet["issue_types"] == []
    assert packet["provider_auth_failure_count"] == 0
    assert packet["source_checks"]["provider_auth_report"]["provider_auth_failure_count"] == 0
    assert packet["provider_auth_failures"] == []
    assert "Issue types: -" in packet["recovery_summary"]
    assert "Provider auth failure count: 0" in packet["recovery_summary"]
    assert "Provider auth failure count: 0" in packet["recovery_bundle"]


def test_readiness_includes_live_db_doctor_when_required(tmp_path, monkeypatch):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    report = tmp_path / "readiness.json"

    _write_json(smoke, {"status": "pass", "summary": {"total": 2, "passed": 2, "failed": 0}, "results": []})
    screenshot.write_bytes(b"png")
    _write_json(browser, {"status": "pass", "summary": {"total": 1, "passed": 1, "failed": 0}, "screenshot": str(screenshot)})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": [], "summary": {"checked": 4}})
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    _write_json(
        scheduler_dir / "run_2026-06-05_020000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )

    monkeypatch.setattr(
        readiness_check,
        "check_live_db_doctor",
        lambda: readiness_check.EvidenceCheck(
            "live_db_doctor",
            False,
            "ERROR",
            "Live DB doctor failed.",
            {
                "failure_type": "diagnostic_error",
                "diagnostics": ["[ERROR] db.live_postgres: tenant/user *** not found"],
            },
            "Fix DATABASE_URL / Supabase pooler credentials.",
        ),
    )

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=scheduler_dir,
        report_path=report,
        require_browser=True,
        require_scheduler=True,
        require_live_db=True,
    )

    live_db = next(check for check in payload["checks"] if check["name"] == "live_db_doctor")
    pooler_runtime = next(check for check in payload["checks"] if check["name"] == "pooler_runtime_compatibility")
    assert payload["status"] == "fail"
    assert payload["summary"]["total"] == 8
    assert pooler_runtime["ok"] is True
    assert live_db["ok"] is False
    assert "tenant/user ***" in live_db["evidence"]["diagnostics"][0]
    assert live_db["evidence"]["failure_type"] == "diagnostic_error"


def test_readiness_writes_supabase_recovery_packet_when_requested(tmp_path, monkeypatch):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    report = tmp_path / "readiness.json"
    packet_path = tmp_path / "supabase_recovery_packet.json"

    _write_json(smoke, {"status": "pass", "summary": {"total": 2, "passed": 2, "failed": 0}, "results": []})
    screenshot.write_bytes(b"png")
    _write_json(browser, {"status": "pass", "summary": {"total": 1, "passed": 1, "failed": 0}, "screenshot": str(screenshot)})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": [], "summary": {"checked": 4}})
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    _write_json(
        scheduler_dir / "run_2026-06-05_020000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )

    monkeypatch.setattr(
        readiness_check,
        "check_live_db_doctor",
        lambda: readiness_check.EvidenceCheck(
            "live_db_doctor",
            False,
            "ERROR",
            "Live DB doctor failed.",
            {
                "failure_type": "diagnostic_error",
                "diagnostics": ["[ERROR] db.live_postgres: tenant/user *** not found"],
            },
            "Fix DATABASE_URL / Supabase pooler credentials.",
        ),
    )

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=scheduler_dir,
        report_path=report,
        recovery_packet_report=packet_path,
        require_browser=True,
        require_scheduler=True,
        require_live_db=True,
    )

    assert payload["artifacts"]["supabase_recovery_packet"] == str(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["status"] == "blocked"
    assert "live_db_doctor_failed" in packet["issue_types"]
    assert packet["live_db_failure_type"] == "diagnostic_error"
    assert packet["source_checks"]["live_db_doctor"]["failure_type"] == "diagnostic_error"
    assert packet["readiness_report"] == str(report)
    packet_verify_command = readiness_check._packet_verifier_command(
        readiness_check.SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND,
        packet_path,
    )
    assert packet_verify_command in packet["verification_commands"]
    assert packet_verify_command in packet["verification_command_bundle"]
    assert packet_verify_command in packet["recovery_bundle"]


def test_strict_default_readiness_writes_stable_strict_sidecar(tmp_path, monkeypatch):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    tap_browser = tmp_path / "tap_browser.json"
    browser_screenshot = tmp_path / "browser.png"
    tap_screenshot = tmp_path / "tap_browser.png"
    hygiene = tmp_path / "hygiene.json"
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    default_report = tmp_path / "logs" / "readiness" / "readiness_latest.json"
    strict_report = tmp_path / "logs" / "readiness" / "strict_readiness_latest.json"
    default_packet = tmp_path / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
    strict_packet = tmp_path / "logs" / "readiness" / "strict_supabase_recovery_packet_latest.json"

    _write_json(smoke, {"status": "pass", "summary": {"total": 2, "passed": 2, "failed": 0}, "results": []})
    browser_screenshot.write_bytes(b"png")
    tap_screenshot.write_bytes(b"png")
    _write_json(
        browser,
        {"status": "pass", "summary": {"total": 1, "passed": 1, "failed": 0}, "screenshot": str(browser_screenshot)},
    )
    _write_json(
        tap_browser,
        {"status": "pass", "summary": {"total": 1, "passed": 1, "failed": 0}, "screenshot": str(tap_screenshot)},
    )
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": [], "summary": {"checked": 4}})
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    _write_json(
        scheduler_dir / "run_2026-06-05_020000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )
    monkeypatch.setattr(readiness_check, "DEFAULT_REPORT", default_report)
    monkeypatch.setattr(readiness_check, "DEFAULT_STRICT_REPORT", strict_report)
    monkeypatch.setattr(readiness_check, "DEFAULT_STRICT_SUPABASE_RECOVERY_PACKET", strict_packet)
    monkeypatch.setattr(
        readiness_check,
        "check_live_db_doctor",
        lambda: readiness_check.EvidenceCheck(
            "live_db_doctor",
            False,
            "ERROR",
            "Live DB doctor failed.",
            {"failure_type": "diagnostic_error", "diagnostics": ["[ERROR] db.live_postgres"]},
            "Fix DATABASE_URL / Supabase pooler credentials.",
        ),
    )

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        tap_fixture_browser_report=tap_browser,
        hygiene_report=hygiene,
        scheduler_dir=scheduler_dir,
        report_path=default_report,
        recovery_packet_report=default_packet,
        require_browser=True,
        require_tap_fixture_browser=True,
        require_scheduler=True,
        max_cli_smoke_age_hours=24,
        max_browser_smoke_age_hours=24,
        max_scheduler_age_hours=24,
        fail_on_runtime_fallback=True,
        require_live_db=True,
    )

    default_payload = json.loads(default_report.read_text(encoding="utf-8"))
    strict_payload = json.loads(strict_report.read_text(encoding="utf-8"))
    strict_packet_payload = json.loads(strict_packet.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert default_payload["requirements"] == strict_payload["requirements"]
    assert default_payload["summary"] == strict_payload["summary"]
    assert strict_payload["artifacts"]["supabase_recovery_packet"] == str(strict_packet)
    assert strict_packet_payload["readiness_report"] == str(strict_report)
    assert strict_packet_payload["status"] == "blocked"
    assert strict_payload["requirements"]["fail_on_runtime_fallback"] is True
    assert strict_payload["requirements"]["require_live_db"] is True
    assert strict_payload["requirements"]["max_browser_smoke_age_hours"] == 24


def test_load_json_accepts_powershell_utf8_bom(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text("\ufeff" + json.dumps({"status": "success"}), encoding="utf-8")

    payload, error = readiness_check._load_json(path)

    assert error == ""
    assert payload == {"status": "success"}


def test_scheduler_can_be_downgraded_to_warning(tmp_path):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    hygiene = tmp_path / "hygiene.json"
    _write_json(smoke, {"status": "pass", "summary": {"failed": 0}, "results": []})
    screenshot.write_bytes(b"png")
    _write_json(browser, {"status": "pass", "summary": {"failed": 0}, "screenshot": str(screenshot)})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=tmp_path / "scheduler",
        report_path=tmp_path / "readiness.json",
        require_browser=True,
        require_scheduler=False,
    )

    scheduler = next(check for check in payload["checks"] if check["name"] == "scheduler_artifact")
    assert payload["status"] == "pass"
    assert scheduler["level"] == "WARN"
    assert scheduler["ok"] is False
    assert payload["summary"]["warnings"] == 1


def test_scheduler_max_age_policy_fails_stale_artifact(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    stale_time = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_010000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": stale_time,
            "finished_at": stale_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["age_hours"] >= 24
    assert check.evidence["max_age_hours"] == 24
    assert "max allowed" in check.message
    assert "run_scheduled_getdaytrends.ps1" in check.remediation
    assert "-Country korea" in check.remediation


def test_scheduler_max_age_policy_accepts_fresh_artifact(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_020000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["age_hours"] <= 1
    assert check.evidence["max_age_hours"] == 24


def test_scheduler_artifact_selection_prefers_payload_timestamp_over_mtime(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    older = scheduler_dir / "run_2026-06-05_020000.json"
    newer = scheduler_dir / "run_2026-06-05_030000.json"
    _write_json(
        older,
        {
            "status": "success",
            "exit_code": 0,
            "started_at": "2026-06-05T02:00:00+00:00",
            "finished_at": "2026-06-05T02:01:00+00:00",
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 60,
        },
    )
    _write_json(
        newer,
        {
            "status": "success",
            "exit_code": 0,
            "started_at": "2026-06-05T03:00:00+00:00",
            "finished_at": "2026-06-05T03:01:00+00:00",
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 60,
        },
    )
    os.utime(newer, (1_700_000_000, 1_700_000_000))
    os.utime(older, (1_700_000_100, 1_700_000_100))

    check = readiness_check.check_scheduler_artifact(scheduler_dir, required=True)

    assert check.ok is True
    assert check.evidence["path"] == str(newer)


def test_scheduler_artifact_evidence_includes_operator_paths_and_command(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    artifact = scheduler_dir / "run_2026-06-05_020000.json"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    fallback = scheduler_dir / "fallback.log"
    project_root = tmp_path / "project"
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    command = f"{python} {project_root / 'main.py'} --one-shot --country korea --limit 1 --dry-run"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    _write_json(
        artifact,
        {
            "status": "success",
            "exit_code": 0,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "duration_seconds": 1.2,
            "project_root": str(project_root),
            "python": str(python),
            "command": command,
            "artifact_path": str(artifact),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "summary_fallback_log": str(fallback),
            "summary_fallback_used": False,
            "country": "korea",
            "limit": 1,
            "dry_run": True,
            "generated": 2,
            "saved": 2,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is True
    assert check.evidence["project_root"] == str(project_root)
    assert check.evidence["python"] == str(python)
    assert check.evidence["command"] == command
    assert check.evidence["artifact_path"] == str(artifact)
    assert check.evidence["artifact_path_present"] is True
    assert check.evidence["artifact_path_matches_latest"] is True
    assert check.evidence["detail_log"] == str(detail)
    assert check.evidence["summary_log"] == str(summary)
    assert check.evidence["summary_fallback_log"] == str(fallback)
    assert check.evidence["summary_fallback_used"] is False
    assert check.evidence["summary_fallback_used_present"] is True
    assert check.evidence["summary_fallback_used_valid"] is True
    assert check.evidence["detail_log_exists"] is True
    assert check.evidence["summary_log_exists"] is True
    assert check.evidence["detail_log_contained"] is True
    assert check.evidence["summary_log_contained"] is True
    assert check.evidence["primary_summary_log_contained"] is True
    assert check.evidence["summary_fallback_log_contained"] is False
    assert check.evidence["duration_seconds_valid"] is True
    assert check.evidence["started_at_valid"] is True
    assert check.evidence["finished_at_valid"] is True
    assert check.evidence["timestamp_window_valid"] is True
    assert check.evidence["primary_summary_log_exists"] is True
    assert check.evidence["summary_fallback_log_exists"] is False
    assert check.evidence["country"] == "korea"
    assert check.evidence["limit"] == 1


def test_scheduler_artifact_evidence_reports_summary_fallback_log_exists(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    artifact = scheduler_dir / "run_2026-06-05_020000.json"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    fallback = scheduler_dir / "fallback.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    fallback.write_text("fallback ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        artifact,
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "duration_seconds": 1.2,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "summary_fallback_log": str(fallback),
            "artifact_path": str(artifact),
            "summary_fallback_used": True,
            "generated": 2,
            "saved": 2,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is True
    assert check.evidence["detail_log_exists"] is True
    assert check.evidence["summary_log_exists"] is True
    assert check.evidence["primary_summary_log_exists"] is False
    assert check.evidence["summary_fallback_log_exists"] is True
    assert check.evidence["summary_log_contained"] is True
    assert check.evidence["primary_summary_log_contained"] is False
    assert check.evidence["summary_fallback_log_contained"] is True
    assert check.evidence["artifact_path_present"] is True
    assert check.evidence["artifact_path_matches_latest"] is True
    assert check.evidence["summary_fallback_used"] is True
    assert check.evidence["summary_fallback_used_present"] is True
    assert check.evidence["summary_fallback_used_valid"] is True


def test_scheduler_artifact_fails_when_detail_log_is_outside_scheduler_dir(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    external_dir = tmp_path / "external"
    detail = external_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_025000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "duration_seconds": 1.2,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["detail_log_exists"] is True
    assert check.evidence["detail_log_contained"] is False
    assert check.evidence["summary_log_contained"] is True
    assert check.message == "Latest scheduler artifact detail log points outside the scheduler log directory."


def test_scheduler_artifact_reports_when_only_summary_log_is_outside_scheduler_dir(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    external_dir = tmp_path / "external"
    detail = scheduler_dir / "run.log"
    summary = external_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_025500.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "duration_seconds": 1.2,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is True
    assert check.level == "OK"
    assert check.evidence["detail_log_contained"] is True
    assert check.evidence["summary_log_exists"] is True
    assert check.evidence["summary_log_contained"] is False
    assert check.evidence["primary_summary_log_contained"] is False
    assert check.message == "Latest scheduler artifact is successful and has matching logs."


def test_scheduler_artifact_fails_when_pipeline_metrics_report_errors(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("pipeline_metrics | generated=0 saved=0 errors=1", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_030000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
            "generated": 0,
            "saved": 0,
            "errors": 1,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["errors"] == 1
    assert "pipeline errors=1" in check.message


def test_scheduler_artifact_fails_when_duration_is_missing(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_040000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.message == "Latest scheduler artifact has missing or invalid duration_seconds."
    assert check.evidence["duration_seconds"] is None
    assert check.evidence["duration_seconds_valid"] is False


def test_scheduler_artifact_rejects_boolean_duration(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_050000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": fresh_time,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": True,
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.evidence["duration_seconds"] is True
    assert check.evidence["duration_seconds_valid"] is False


def test_scheduler_artifact_fails_when_started_at_is_missing(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    fresh_time = datetime.now(UTC).isoformat()
    _write_json(
        scheduler_dir / "run_2026-06-05_060000.json",
        {
            "status": "success",
            "exit_code": 0,
            "finished_at": fresh_time,
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.message == "Latest scheduler artifact has missing, invalid, or reversed started_at/finished_at timestamps."
    assert check.evidence["started_at_valid"] is False
    assert check.evidence["finished_at_valid"] is True
    assert check.evidence["timestamp_window_valid"] is False


def test_scheduler_artifact_fails_when_finished_at_precedes_started_at(tmp_path):
    scheduler_dir = tmp_path / "scheduler"
    detail = scheduler_dir / "run.log"
    summary = scheduler_dir / "summary.log"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("ok", encoding="utf-8")
    summary.write_text("ok", encoding="utf-8")
    started_at = datetime.now(UTC)
    finished_at = started_at - timedelta(seconds=1)
    _write_json(
        scheduler_dir / "run_2026-06-05_070000.json",
        {
            "status": "success",
            "exit_code": 0,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "detail_log": str(detail),
            "summary_log": str(summary),
            "duration_seconds": 1.2,
            "generated": 1,
            "saved": 1,
            "errors": 0,
        },
    )

    check = readiness_check.check_scheduler_artifact(
        scheduler_dir,
        required=True,
        max_age_hours=24,
    )

    assert check.ok is False
    assert check.evidence["started_at_valid"] is True
    assert check.evidence["finished_at_valid"] is True
    assert check.evidence["timestamp_window_valid"] is False


def test_browser_report_can_be_downgraded_to_warning(tmp_path):
    smoke = tmp_path / "smoke.json"
    hygiene = tmp_path / "hygiene.json"
    _write_json(smoke, {"status": "pass", "summary": {"failed": 0}, "results": []})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=tmp_path / "missing-browser.json",
        hygiene_report=hygiene,
        scheduler_dir=tmp_path / "scheduler",
        report_path=tmp_path / "readiness.json",
        require_browser=False,
        require_scheduler=False,
    )

    browser = next(check for check in payload["checks"] if check["name"] == "dashboard_browser_report")
    assert payload["status"] == "pass"
    assert browser["level"] == "WARN"
    assert browser["ok"] is False
    assert payload["summary"]["warnings"] == 2


def test_default_browser_report_prefers_fresh_non_tap_artifact(tmp_path, monkeypatch):
    smoke = tmp_path / "smoke.json"
    hygiene = tmp_path / "hygiene.json"
    smoke_dir = tmp_path / "smoke"
    stale_browser = smoke_dir / "dashboard_browser_latest.json"
    stale_screenshot = smoke_dir / "dashboard_browser_latest.png"
    fresh_browser = smoke_dir / "dashboard_browser_full_smoke_fresh.json"
    fresh_screenshot = smoke_dir / "dashboard_browser_full_smoke_fresh.png"
    tap_browser = smoke_dir / "dashboard_browser_tap_source_newer.json"
    tap_screenshot = smoke_dir / "dashboard_browser_tap_source_newer.png"
    report = tmp_path / "readiness.json"
    scheduler_dir = tmp_path / "scheduler"
    stale_screenshot.parent.mkdir(parents=True, exist_ok=True)
    stale_screenshot.write_bytes(b"png")
    fresh_screenshot.write_bytes(b"png")
    tap_screenshot.write_bytes(b"png")
    _write_json(smoke, {"status": "pass", "summary": {"failed": 0}, "results": []})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})
    _write_json(
        stale_browser,
        {
            "status": "pass",
            "generated_at": "2026-06-07T01:00:00+09:00",
            "summary": {"total": 82, "passed": 82, "failed": 0},
            "screenshot": str(stale_screenshot),
        },
    )
    _write_json(
        fresh_browser,
        {
            "status": "pass",
            "generated_at": "2026-06-07T02:00:00+09:00",
            "summary": {"total": 87, "passed": 87, "failed": 0},
            "screenshot": str(fresh_screenshot),
        },
    )
    _write_json(
        tap_browser,
        {
            "status": "pass",
            "generated_at": "2026-06-07T03:00:00+09:00",
            "summary": {"total": 89, "passed": 89, "failed": 0},
            "screenshot": str(tap_screenshot),
        },
    )
    monkeypatch.setattr(readiness_check, "DEFAULT_BROWSER_REPORT", stale_browser)

    rc = readiness_check.main(
        [
            "--smoke-report",
            str(smoke),
            "--hygiene-report",
            str(hygiene),
            "--scheduler-dir",
            str(scheduler_dir),
            "--report",
            str(report),
            "--no-recovery-packet",
            "--no-require-scheduler",
            "--no-require-tap-fixture-browser",
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    browser = next(check for check in payload["checks"] if check["name"] == "dashboard_browser_report")
    assert rc == 0
    assert browser["ok"] is True
    assert browser["evidence"]["path"] == str(fresh_browser)
    assert browser["evidence"]["summary"] == {"total": 87, "passed": 87, "failed": 0}
    assert str(stale_browser) not in json.dumps(browser)
    assert str(tap_browser) not in json.dumps(browser)


def test_browser_report_resolves_workspace_relative_screenshot_independent_of_cwd(tmp_path, monkeypatch):
    project_root = tmp_path / "automation" / "getdaytrends"
    smoke_dir = project_root / "logs" / "smoke"
    report = smoke_dir / "dashboard_browser_workspace_relative.json"
    screenshot = smoke_dir / "dashboard_browser_workspace_relative.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.write_bytes(b"png")
    _write_json(
        report,
        {
            "status": "pass",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"total": 1, "passed": 1, "failed": 0},
            "screenshot": str(screenshot.relative_to(tmp_path)),
        },
    )
    monkeypatch.setattr(readiness_check, "PROJECT_ROOT", project_root)
    monkeypatch.chdir(project_root)

    check = readiness_check.check_browser_report(report, required=True, max_age_hours=24)

    assert check.ok is True
    assert check.evidence["screenshot_exists"] is True
    assert Path(check.evidence["screenshot"]).resolve() == screenshot.resolve()


def test_default_browser_report_prefers_passing_report_over_newer_failed_report(tmp_path, monkeypatch):
    smoke = tmp_path / "smoke.json"
    hygiene = tmp_path / "hygiene.json"
    smoke_dir = tmp_path / "smoke"
    passing_browser = smoke_dir / "dashboard_browser_latest.json"
    passing_screenshot = smoke_dir / "dashboard_browser_latest.png"
    failed_browser = smoke_dir / "dashboard_browser_failed_newer.json"
    failed_screenshot = smoke_dir / "dashboard_browser_failed_newer.png"
    report = tmp_path / "readiness.json"
    scheduler_dir = tmp_path / "scheduler"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    passing_screenshot.write_bytes(b"png")
    failed_screenshot.write_bytes(b"png")
    _write_json(smoke, {"status": "pass", "summary": {"failed": 0}, "results": []})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})
    _write_json(
        passing_browser,
        {
            "status": "pass",
            "generated_at": "2026-06-07T02:00:00+09:00",
            "summary": {"total": 87, "passed": 87, "failed": 0},
            "screenshot": str(passing_screenshot),
        },
    )
    _write_json(
        failed_browser,
        {
            "status": "fail",
            "generated_at": "2026-06-07T03:00:00+09:00",
            "summary": {"total": 87, "passed": 86, "failed": 1},
            "screenshot": str(failed_screenshot),
        },
    )
    monkeypatch.setattr(readiness_check, "DEFAULT_BROWSER_REPORT", passing_browser)

    rc = readiness_check.main(
        [
            "--smoke-report",
            str(smoke),
            "--hygiene-report",
            str(hygiene),
            "--scheduler-dir",
            str(scheduler_dir),
            "--report",
            str(report),
            "--no-recovery-packet",
            "--no-require-scheduler",
            "--no-require-tap-fixture-browser",
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    browser = next(check for check in payload["checks"] if check["name"] == "dashboard_browser_report")
    assert rc == 0
    assert browser["ok"] is True
    assert browser["evidence"]["path"] == str(passing_browser)
    assert str(failed_browser) not in json.dumps(browser)


def test_browser_report_requires_screenshot(tmp_path):
    smoke = tmp_path / "smoke.json"
    browser = tmp_path / "browser.json"
    hygiene = tmp_path / "hygiene.json"
    _write_json(smoke, {"status": "pass", "summary": {"failed": 0}, "results": []})
    _write_json(browser, {"status": "pass", "summary": {"failed": 0}, "screenshot": str(tmp_path / "missing.png")})
    _write_json(hygiene, {"status": "pass", "findings": [], "read_errors": []})

    payload = readiness_check.run_readiness(
        smoke_report=smoke,
        browser_report=browser,
        hygiene_report=hygiene,
        scheduler_dir=tmp_path / "scheduler",
        report_path=tmp_path / "readiness.json",
        require_browser=True,
        require_scheduler=False,
    )

    assert payload["status"] == "fail"
    assert any(check["name"] == "dashboard_browser_report" and not check["ok"] for check in payload["checks"])


def test_browser_report_max_age_policy_fails_stale_report(tmp_path):
    report = tmp_path / "browser.json"
    screenshot = tmp_path / "browser.png"
    screenshot.write_bytes(b"png")
    _write_json(
        report,
        {
            "status": "pass",
            "generated_at": (datetime.now(UTC) - timedelta(hours=30)).isoformat(),
            "summary": {"total": 12, "passed": 12, "failed": 0},
            "screenshot": str(screenshot),
        },
    )

    check = readiness_check.check_browser_report(report, required=True, max_age_hours=24)

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["age_hours"] >= 24
    assert check.evidence["max_age_hours"] == 24
    assert "max allowed" in check.message


def test_tap_fixture_browser_report_requires_source_and_degraded_guards(tmp_path):
    report = tmp_path / "tap-fixture.json"
    screenshot = tmp_path / "tap-fixture.png"
    screenshot.write_bytes(b"png")
    _write_json(
        report,
        {
            "status": "pass",
            "schema_version": 1,
            "summary": {"total": 15, "passed": 15, "failed": 0},
            "screenshot": str(screenshot),
            "mode": {"tap_source_fixture": True},
            "checks": [
                {"name": "tap_source_notes_rendered", "ok": True},
                {"name": "fixture_endpoints_not_degraded", "ok": True},
                {"name": "tap_deal_room_ops_summary", "ok": True},
                {"name": "tap_deal_room_track_click_event", "ok": True},
                {"name": "tap_deal_room_checkout_open_recovery", "ok": True},
                {"name": "tap_checkout_return_notice", "ok": True},
                {"name": "operator_action_buttons_described", "ok": True},
                {"name": "server_has_no_dashboard_degraded_endpoint_logs", "ok": True},
            ],
        },
    )

    check = readiness_check.check_tap_fixture_browser_report(report, required=True)

    assert check.ok is True
    assert check.name == "tap_fixture_browser_report"
    assert check.evidence["missing_required_checks"] == []
    assert check.evidence["failed_required_checks"] == []


def test_tap_fixture_browser_report_fails_missing_required_guard(tmp_path):
    report = tmp_path / "tap-fixture.json"
    screenshot = tmp_path / "tap-fixture.png"
    screenshot.write_bytes(b"png")
    _write_json(
        report,
        {
            "status": "pass",
            "summary": {"total": 13, "passed": 13, "failed": 0},
            "screenshot": str(screenshot),
            "mode": {"tap_source_fixture": True},
            "checks": [{"name": "tap_source_notes_rendered", "ok": True}],
        },
    )

    check = readiness_check.check_tap_fixture_browser_report(report, required=True)

    assert check.ok is False
    assert check.level == "ERROR"
    assert "fixture_endpoints_not_degraded" in check.evidence["missing_required_checks"]
    assert "tap_deal_room_ops_summary" in check.evidence["missing_required_checks"]
    assert "tap_deal_room_track_click_event" in check.evidence["missing_required_checks"]
    assert "tap_deal_room_checkout_open_recovery" in check.evidence["missing_required_checks"]
    assert "tap_checkout_return_notice" in check.evidence["missing_required_checks"]
    assert "operator_action_buttons_described" in check.evidence["missing_required_checks"]
    assert "browser_smoke.py --tap-source-fixture" in check.remediation


def test_tap_fixture_browser_report_max_age_policy_fails_stale_report(tmp_path):
    report = tmp_path / "tap-fixture.json"
    screenshot = tmp_path / "tap-fixture.png"
    screenshot.write_bytes(b"png")
    _write_json(
        report,
        {
            "status": "pass",
            "generated_at": (datetime.now(UTC) - timedelta(hours=30)).isoformat(),
            "summary": {"total": 15, "passed": 15, "failed": 0},
            "screenshot": str(screenshot),
            "mode": {"tap_source_fixture": True},
            "checks": [
                {"name": "tap_source_notes_rendered", "ok": True},
                {"name": "fixture_endpoints_not_degraded", "ok": True},
                {"name": "tap_deal_room_ops_summary", "ok": True},
                {"name": "tap_deal_room_track_click_event", "ok": True},
                {"name": "tap_deal_room_checkout_open_recovery", "ok": True},
                {"name": "tap_checkout_return_notice", "ok": True},
                {"name": "operator_action_buttons_described", "ok": True},
                {"name": "server_has_no_dashboard_degraded_endpoint_logs", "ok": True},
            ],
        },
    )

    check = readiness_check.check_tap_fixture_browser_report(report, required=True, max_age_hours=24)

    assert check.ok is False
    assert check.level == "ERROR"
    assert check.evidence["age_hours"] >= 24
    assert check.evidence["max_age_hours"] == 24
    assert "max allowed" in check.message


def test_main_returns_nonzero_for_failed_readiness(tmp_path):
    custom_report = tmp_path / "readiness.json"
    code = readiness_check.main(
        [
            "--smoke-report",
            str(tmp_path / "missing.json"),
            "--hygiene-report",
            str(tmp_path / "missing-hygiene.json"),
            "--scheduler-dir",
            str(tmp_path / "scheduler"),
            "--report",
            str(custom_report),
            "--no-require-scheduler",
            "--no-require-browser",
        ]
    )

    assert code == 1
    assert custom_report.exists()
    assert (tmp_path / "readiness_supabase_recovery_packet.json").exists()
    assert (tmp_path / "readiness_provider_auth_recovery_packet.json").exists()
    assert json.loads(custom_report.read_text(encoding="utf-8"))["artifacts"]["supabase_recovery_packet"] == str(
        tmp_path / "readiness_supabase_recovery_packet.json"
    )
    assert json.loads(custom_report.read_text(encoding="utf-8"))["artifacts"]["provider_auth_recovery_packet"] == str(
        tmp_path / "readiness_provider_auth_recovery_packet.json"
    )
    supabase_packet_path = tmp_path / "readiness_supabase_recovery_packet.json"
    provider_packet_path = tmp_path / "readiness_provider_auth_recovery_packet.json"
    supabase_packet = json.loads(supabase_packet_path.read_text(encoding="utf-8"))
    provider_packet = json.loads(provider_packet_path.read_text(encoding="utf-8"))
    supabase_packet_verify_command = readiness_check._packet_verifier_command(
        readiness_check.SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND,
        supabase_packet_path,
    )
    provider_packet_verify_command = readiness_check._packet_verifier_command(
        readiness_check.PROVIDER_AUTH_RECOVERY_PACKET_VERIFY_COMMAND,
        provider_packet_path,
    )
    assert supabase_packet_verify_command in supabase_packet["verification_commands"]
    assert supabase_packet_verify_command in supabase_packet["verification_command_bundle"]
    assert provider_packet_verify_command in provider_packet["verification_commands"]
    assert provider_packet_verify_command in provider_packet["verification_command_bundle"]


def test_default_recovery_packet_path_uses_latest_only_for_default_report(tmp_path):
    assert readiness_check._default_recovery_packet_path(readiness_check.DEFAULT_REPORT) == (
        readiness_check.DEFAULT_SUPABASE_RECOVERY_PACKET
    )
    assert readiness_check._default_recovery_packet_path(tmp_path / "custom-readiness.json") == (
        tmp_path / "custom-readiness_supabase_recovery_packet.json"
    )
    assert readiness_check._default_provider_auth_recovery_packet_path(readiness_check.DEFAULT_REPORT) == (
        readiness_check.DEFAULT_PROVIDER_AUTH_RECOVERY_PACKET
    )
    assert readiness_check._default_provider_auth_recovery_packet_path(tmp_path / "custom-readiness.json") == (
        tmp_path / "custom-readiness_provider_auth_recovery_packet.json"
    )


def test_write_report_retries_locked_replace(tmp_path, monkeypatch):
    report = tmp_path / "readiness.json"
    temp_path = report.with_name(f".{report.name}.tmp")
    original_replace = type(temp_path).replace
    calls = {"count": 0}
    sleeps: list[float] = []

    def fake_replace(self, target):
        if self == temp_path and target == report and calls["count"] < 2:
            calls["count"] += 1
            raise PermissionError("file is temporarily locked")
        return original_replace(self, target)

    monkeypatch.setattr(type(temp_path), "replace", fake_replace)
    monkeypatch.setattr(readiness_check.time, "sleep", lambda delay: sleeps.append(delay))

    readiness_check._write_report(report, {"status": "fail"})

    assert json.loads(report.read_text(encoding="utf-8")) == {"status": "fail"}
    assert calls["count"] == 2
    assert sleeps == [0.2, 0.2]
