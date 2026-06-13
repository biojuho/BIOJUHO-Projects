import json
from datetime import UTC, datetime

from scripts import readiness_check, verify_provider_auth_recovery_packet, verify_supabase_recovery_packet


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _readiness_payload():
    return {
        "schema_version": 1,
        "status": "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"total": 3, "passed": 1, "failed": 2},
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal(s).",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [
                        {
                            "check": "stats",
                            "stream": "stderr_tail",
                            "kind": "database.sqlite_fallback",
                            "snippet": "PostgreSQL connection failed; falling back to local SQLite",
                        }
                    ],
                },
            },
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
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor failed.",
                "remediation": readiness_check.LIVE_DB_DOCTOR_REMEDIATION,
                "evidence": {
                    "diagnostics": [
                        "[ERROR] db.live_postgres: Live PostgreSQL probe failed: tenant/user *** not found",
                    ]
                },
            },
        ],
    }


def _clear_supabase_readiness_payload():
    return {
        "schema_version": 1,
        "status": "pass",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"total": 1, "passed": 1, "failed": 0},
        "checks": [
            {
                "name": "live_db_doctor",
                "ok": True,
                "level": "OK",
                "message": "Live DB doctor passed.",
                "evidence": {
                    "exit_code": 0,
                    "diagnostics": ["[OK] db.live_postgres: Live PostgreSQL probe succeeded"],
                },
            }
        ],
    }


def test_supabase_recovery_packet_verifier_accepts_current_blocked_packet(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()

    _write_json(readiness_report, payload)
    _write_json(
        packet_report,
        readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report),
    )

    assert verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report) == []
    assert verify_supabase_recovery_packet.main(
        ["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]
    ) == 0


def test_supabase_recovery_packet_verifier_rejects_stale_readiness_timestamp(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["readiness_generated_at"] = "2026-01-01T00:00:00+00:00"

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "packet readiness_generated_at does not match readiness report generated_at" in errors


def test_supabase_recovery_packet_verifier_accepts_clear_packet_without_failure_type(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _clear_supabase_readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)

    assert packet["status"] == "clear"
    assert packet["live_db_failure_type"] == ""

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    assert verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report) == []


def test_supabase_recovery_packet_verifier_requires_failed_live_db_failure_type(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["live_db_failure_type"] = ""

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "failed live DB doctor must include live_db_failure_type" in errors
    assert "packet field does not match current readiness contract: live_db_failure_type" in errors


def test_supabase_recovery_packet_verifier_requires_runtime_fallback_source_details(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["source_checks"]["cli_smoke_report"]["runtime_fallback_count"] = 0
    packet["source_checks"]["cli_smoke_report"]["runtime_fallback_kinds"] = []
    packet["source_checks"]["cli_smoke_report"]["runtime_fallback_checks"] = []

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "runtime fallback source check count must match readiness fallback evidence" in errors
    assert "runtime fallback source check kinds must match readiness fallback evidence" in errors
    assert "runtime fallback source check checks must match readiness fallback evidence" in errors
    assert "packet field does not match current readiness contract: source_checks" in errors


def test_supabase_recovery_packet_verifier_requires_runtime_fallback_operator_text(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    for field in ("recovery_summary", "recovery_bundle"):
        packet[field] = packet[field].replace("Runtime fallback count: 1\n", "")
        packet[field] = packet[field].replace("Runtime fallback kinds: database.sqlite_fallback\n", "")
        packet[field] = packet[field].replace("Runtime fallback checks: stats\n", "")

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "recovery_summary missing runtime fallback marker: Runtime fallback count: 1" in errors
    assert "recovery_bundle missing runtime fallback marker: Runtime fallback count: 1" in errors
    assert (
        "recovery_summary missing runtime fallback marker: Runtime fallback kinds: database.sqlite_fallback"
        in errors
    )
    assert "recovery_bundle missing runtime fallback marker: Runtime fallback checks: stats" in errors


def test_supabase_recovery_packet_verifier_requires_operator_command_bundles(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["scheduler_pause_command_bundle"] = ""
    packet["verification_command_bundle"] = "python main.py --doctor --require-live-db"

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "scheduler_pause_command_bundle must be non-empty" in errors
    assert "verification_command_bundle must start from the getdaytrends workspace" in errors
    assert "verification_command_bundle missing command: python scripts\\smoke_cli.py --include-dry-run" in errors
    assert "packet missing required field: scheduler_pause_command_bundle" in errors
    assert "packet field does not match current readiness contract: verification_command_bundle" in errors


def test_supabase_recovery_packet_verifier_requires_static_launch_success_criteria(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    criterion = "CLI smoke reports runtime_fallback_count 0."
    packet["launch_success_criteria"].remove(criterion)
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(criterion, "CLI smoke reports a passing run.")

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert f"launch_success_criteria missing required criterion: {criterion}" in errors
    assert f"recovery_bundle missing launch success criterion: {criterion}" in errors
    assert "packet field does not match current readiness contract: launch_success_criteria" in errors


def test_supabase_recovery_packet_verifier_requires_static_verification_commands(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    command = readiness_check.LAUNCH_SECRET_SCAN_REFRESH_COMMAND
    packet["verification_commands"].remove(command)
    packet["verification_command_bundle"] = packet["verification_command_bundle"].replace(command, "")
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(command, "")

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert f"verification_commands missing required launch command: {command}" in errors
    assert f"verification_command_bundle missing required launch command: {command}" in errors
    assert f"recovery_bundle missing required verification command: {command}" in errors
    assert "packet field does not match current readiness contract: verification_commands" in errors


def test_supabase_recovery_packet_verifier_requires_ordered_post_credential_recheck_sequence(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["post_credential_recheck_sequence"][1]["success_criterion"] = "CLI smoke passes."
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(
        "Success: CLI smoke completes with runtime_fallback_count 0.",
        "Success: CLI smoke passes.",
    )

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert (
        "post_credential_recheck_sequence step 2 success_criterion must be "
        "CLI smoke completes with runtime_fallback_count 0."
    ) in errors
    assert (
        "recovery_bundle missing post-credential recheck success_criterion: "
        "CLI smoke completes with runtime_fallback_count 0."
    ) in errors
    assert "packet field does not match current readiness contract: post_credential_recheck_sequence" in errors


def test_supabase_recovery_packet_verifier_requires_post_credential_recheck_bundle_visibility(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("## Post-credential recheck sequence", "")
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("python main.py --doctor --require-live-db", "")

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "recovery_bundle missing section: ## Post-credential recheck sequence" in errors
    assert (
        "recovery_bundle missing post-credential recheck command: "
        "python main.py --doctor --require-live-db"
    ) in errors


def test_supabase_recovery_packet_verifier_requires_post_credential_evidence_artifacts(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["post_credential_recheck_evidence"][1]["artifact"] = "logs\\smoke\\cli_smoke.json"
    packet["post_credential_recheck_evidence"][1]["success_signal"] = "CLI smoke passes."
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("logs\\smoke\\cli_smoke_latest.json", "")
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("runtime_fallback_count=0.", "CLI smoke passes.")

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert (
        "post_credential_recheck_evidence step 2 artifact must be "
        "logs\\smoke\\cli_smoke_latest.json"
    ) in errors
    assert "post_credential_recheck_evidence step 2 success_signal must be runtime_fallback_count=0." in errors
    assert (
        "recovery_bundle missing post-credential evidence artifact: "
        "logs\\smoke\\cli_smoke_latest.json"
    ) in errors
    assert "recovery_bundle missing post-credential evidence success_signal: runtime_fallback_count=0." in errors
    assert "packet field does not match current readiness contract: post_credential_recheck_evidence" in errors


def test_supabase_recovery_packet_verifier_requires_post_credential_evidence_bundle_visibility(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("## Post-credential evidence artifacts", "")
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(
        "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
        "",
    )

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "recovery_bundle missing section: ## Post-credential evidence artifacts" in errors
    assert (
        "recovery_bundle missing post-credential evidence artifact: "
        "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json"
    ) in errors


def test_supabase_recovery_packet_verifier_requires_operator_final_proof_bundle(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["operator_final_proof_bundle"][1]["success_signal"] = "CLI smoke passes."
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(
        "runtime_fallback_count=0 and provider_auth_failure_count=0.",
        "CLI smoke passes.",
    )

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert (
        "operator_final_proof_bundle item 2 success_signal must be "
        "runtime_fallback_count=0 and provider_auth_failure_count=0."
    ) in errors
    assert (
        "recovery_bundle missing operator final proof success_signal: "
        "runtime_fallback_count=0 and provider_auth_failure_count=0."
    ) in errors
    assert "packet field does not match current readiness contract: operator_final_proof_bundle" in errors


def test_supabase_recovery_packet_verifier_requires_operator_final_proof_bundle_visibility(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase_recovery_packet.json"
    payload = _readiness_payload()
    packet = readiness_check.build_supabase_recovery_packet(payload, readiness_report=readiness_report)
    packet["recovery_bundle"] = packet["recovery_bundle"].replace("## Operator final proof bundle", "")
    packet["recovery_bundle"] = packet["recovery_bundle"].replace(
        "..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json",
        "",
    )

    _write_json(readiness_report, payload)
    _write_json(packet_report, packet)

    errors = verify_supabase_recovery_packet.validate_recovery_packet(readiness_report, packet_report)

    assert "recovery_bundle missing section: ## Operator final proof bundle" in errors
    assert (
        "recovery_bundle missing operator final proof artifact: "
        "..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json"
    ) in errors


def test_provider_auth_recovery_packet_verifier_accepts_clear_packet(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "provider_auth_recovery_packet.json"
    payload = _readiness_payload()

    _write_json(readiness_report, payload)
    _write_json(
        packet_report,
        readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_report),
    )

    assert verify_provider_auth_recovery_packet.validate_recovery_packet(readiness_report, packet_report) == []
    assert verify_provider_auth_recovery_packet.main(
        ["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]
    ) == 0


def test_provider_auth_recovery_packet_verifier_accepts_stale_zero_failure_report(tmp_path):
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "provider_auth_recovery_packet.json"
    payload = _readiness_payload()
    provider_check = next(check for check in payload["checks"] if check["name"] == "provider_auth_report")
    provider_check.update(
        {
            "ok": False,
            "level": "ERROR",
            "message": "Provider auth evidence is 24.78h old; max allowed is 24.0h.",
            "remediation": readiness_check.CLI_SMOKE_REFRESH_COMMAND,
        }
    )
    provider_check["evidence"].update(
        {
            "age_hours": 24.78,
            "max_age_hours": 24.0,
            "provider_auth_failure_count": 0,
            "provider_auth_failures": [],
        }
    )

    _write_json(readiness_report, payload)
    _write_json(
        packet_report,
        readiness_check.build_provider_auth_recovery_packet(payload, readiness_report=readiness_report),
    )

    assert verify_provider_auth_recovery_packet.validate_recovery_packet(readiness_report, packet_report) == []
