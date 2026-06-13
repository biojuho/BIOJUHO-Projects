"""Validate the getdaytrends Supabase recovery packet artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts import readiness_check
except ImportError:  # pragma: no cover - used when executed from scripts/
    import readiness_check  # type: ignore


POSTGRES_USER_URL_RE = re.compile(r"\bpostgres(?:ql)?://postgres\.", re.IGNORECASE)
SUPABASE_USER_RE = re.compile(r"\bpostgres\.[A-Za-z0-9_.-]+")
TENANT_USER_RE = re.compile(r"\btenant/user\s+postgres\.[A-Za-z0-9_.-]+", re.IGNORECASE)
REQUIRED_ACCEPTED_POOLER_SHAPES = {
    "shared_supavisor_transaction": {
        "host": "aws-[region].pooler.supabase.com",
        "port": 6543,
        "username": "postgres.<project_ref>",
        "database": "postgres",
        "url_shape_without_password": "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres",
    },
    "dedicated_pgbouncer_transaction": {
        "host": "db.<project_ref>.supabase.co",
        "port": 6543,
        "username": "postgres",
        "database": "postgres",
        "url_shape_without_password": "postgres@db.<project_ref>.supabase.co:6543/postgres",
    },
}
REQUIRED_LAUNCH_SUCCESS_CRITERIA = (
    "Live DB doctor reports OK for the primary Supabase PostgreSQL connection.",
    "Pooler runtime compatibility reports OK with prepared-statement caching disabled for transaction-pooler asyncpg paths.",
    "CLI smoke reports runtime_fallback_count 0.",
    "Production text hygiene reports pass.",
    "Strict readiness reports status pass.",
    "Launch secret scan reports valid with zero findings, zero missing paths, and current artifacts included.",
    "Canonical getdaytrends workspace smoke reports all configured checks PASS.",
)
REQUIRED_VERIFICATION_COMMANDS = (
    readiness_check.LIVE_DB_DOCTOR_COMMAND,
    readiness_check.CLI_SMOKE_REFRESH_COMMAND,
    readiness_check.BROWSER_SMOKE_REFRESH_COMMAND,
    readiness_check.TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
    readiness_check.TEXT_HYGIENE_REFRESH_COMMAND,
    readiness_check.STRICT_READINESS_REFRESH_COMMAND,
    readiness_check.LAUNCH_SECRET_SCAN_REFRESH_COMMAND,
    readiness_check.CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
)
REQUIRED_POST_CREDENTIAL_RECHECK_SEQUENCE = (
    {
        "step": "live_db_doctor",
        "command": readiness_check.LIVE_DB_DOCTOR_COMMAND,
        "success_criterion": "Live DB doctor reports OK for the primary Supabase PostgreSQL connection.",
    },
    {
        "step": "cli_smoke",
        "command": readiness_check.CLI_SMOKE_REFRESH_COMMAND,
        "success_criterion": "CLI smoke completes with runtime_fallback_count 0.",
    },
    {
        "step": "strict_readiness",
        "command": readiness_check.STRICT_READINESS_REFRESH_COMMAND,
        "success_criterion": "Strict readiness reports status pass.",
    },
    {
        "step": "canonical_workspace_smoke",
        "command": readiness_check.CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
        "success_criterion": "Canonical getdaytrends workspace smoke reports all configured checks PASS.",
    },
)
REQUIRED_POST_CREDENTIAL_RECHECK_EVIDENCE = (
    {
        "step": "live_db_doctor",
        "artifact": "operator console output",
        "success_signal": "[OK] db.live_postgres and no raw DATABASE_URL or credential value in output.",
    },
    {
        "step": "cli_smoke",
        "artifact": "logs\\smoke\\cli_smoke_latest.json",
        "success_signal": "runtime_fallback_count=0.",
    },
    {
        "step": "strict_readiness",
        "artifact": "logs\\readiness\\readiness_latest.json",
        "success_signal": "status=pass and failed=0.",
    },
    {
        "step": "canonical_workspace_smoke",
        "artifact": "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
        "success_signal": "all configured getdaytrends checks pass.",
    },
)
REQUIRED_OPERATOR_FINAL_PROOF_BUNDLE = (
    {
        "artifact": "logs\\readiness\\readiness_latest.json",
        "success_signal": "status=pass, failed=0, and cli_smoke_report/live_db_doctor both OK.",
    },
    {
        "artifact": "logs\\smoke\\cli_smoke_latest.json",
        "success_signal": "runtime_fallback_count=0 and provider_auth_failure_count=0.",
    },
    {
        "artifact": "logs\\smoke\\dashboard_browser_latest.json",
        "success_signal": "dashboard browser smoke reports pass.",
    },
    {
        "artifact": "logs\\smoke\\dashboard_browser_tap_source_evidence.json",
        "success_signal": "TAP fixture browser smoke reports all required TAP checks pass.",
    },
    {
        "artifact": "logs\\hygiene\\text_hygiene_latest.json",
        "success_signal": "status=pass with findings=0 and read_errors=0.",
    },
    {
        "artifact": "..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json",
        "success_signal": "status=valid, findings=0, missing=0, and current artifacts included.",
    },
    {
        "artifact": "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
        "success_signal": "all configured getdaytrends workspace smoke checks pass.",
    },
)


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"{path} is missing"
    except Exception as exc:
        return None, f"{path} is not readable: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path} root is not a JSON object"
    return payload, ""


def _packet_readiness_report(packet_report: Path) -> Path | None:
    packet, _ = _load_json(packet_report)
    if not isinstance(packet, dict):
        return None
    readiness_report = packet.get("readiness_report")
    if isinstance(readiness_report, str) and readiness_report.strip():
        return Path(readiness_report)
    return None


def _text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_string_values(child))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for child in value:
            strings.extend(_string_values(child))
        return strings
    return []


def _has_value(payload: dict[str, Any], key: str) -> bool:
    if key == "live_db_failure_type":
        return key in payload
    value = payload.get(key)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) or key in {"issue_types", "blocking_checks"}
    if isinstance(value, dict):
        return bool(value)
    return value is not None


def _same_path(left: Any, right: Path) -> bool:
    try:
        return Path(str(left)).resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


def _expected_packet_report_for_verifier_command(
    packet: dict[str, Any],
    *,
    base_command: str,
    packet_report: Path,
) -> Path | None:
    commands = packet.get("verification_commands")
    if not isinstance(commands, list):
        return None
    prefix = f"{base_command} --packet-report"
    if any(str(command).startswith(prefix) for command in commands):
        return packet_report
    return None


def _checks_by_name(readiness_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = readiness_payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name", "")): check
        for check in checks
        if isinstance(check, dict) and str(check.get("name", "")).strip()
    }


def _contains_runtime_fallback(readiness_payload: dict[str, Any]) -> bool:
    cli_check = _checks_by_name(readiness_payload).get("cli_smoke_report", {})
    evidence = cli_check.get("evidence") if isinstance(cli_check.get("evidence"), dict) else {}
    return bool(evidence.get("runtime_fallbacks")) or int(evidence.get("runtime_fallback_count") or 0) > 0


def _runtime_fallback_source_expectations(readiness_payload: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    cli_check = _checks_by_name(readiness_payload).get("cli_smoke_report", {})
    evidence = cli_check.get("evidence") if isinstance(cli_check.get("evidence"), dict) else {}
    fallbacks = readiness_check._runtime_fallbacks(evidence)
    try:
        count = int(evidence.get("runtime_fallback_count") or len(fallbacks))
    except (TypeError, ValueError):
        count = len(fallbacks)
    kinds = sorted({str(item.get("kind") or item.get("name") or "unknown") for item in fallbacks})
    checks = sorted(
        {
            str(item.get("check") or item.get("command") or "").strip()
            for item in fallbacks
            if str(item.get("check") or item.get("command") or "").strip()
        }
    )
    return count, kinds, checks


def _validate_runtime_fallback_operator_text(
    packet: dict[str, Any],
    expected_count: int,
    expected_kinds: list[str],
    expected_checks: list[str],
) -> list[str]:
    errors: list[str] = []
    summary = str(packet.get("recovery_summary") or "")
    bundle = str(packet.get("recovery_bundle") or "")
    expected_markers = [
        f"Runtime fallback count: {expected_count}",
        "Runtime fallback kinds: " + ", ".join(expected_kinds),
    ]
    if expected_checks:
        expected_markers.append("Runtime fallback checks: " + ", ".join(expected_checks))

    for marker in expected_markers:
        if marker not in summary:
            errors.append(f"recovery_summary missing runtime fallback marker: {marker}")
        if marker not in bundle:
            errors.append(f"recovery_bundle missing runtime fallback marker: {marker}")
    return errors


def _validate_operator_command_bundles(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    command_groups = (
        ("scheduler_pause_commands", "scheduler_pause_command_bundle"),
        ("scheduler_resume_commands", "scheduler_resume_command_bundle"),
        ("credential_update_commands", "credential_update_command_bundle"),
        ("verification_commands", "verification_command_bundle"),
    )
    for list_key, bundle_key in command_groups:
        commands = packet.get(list_key)
        command_bundle = packet.get(bundle_key)
        if not isinstance(commands, list) or not commands:
            errors.append(f"{list_key} must be a non-empty command list")
            continue
        if not isinstance(command_bundle, str) or not command_bundle.strip():
            errors.append(f"{bundle_key} must be non-empty")
            continue
        if "Set-Location -LiteralPath" not in command_bundle:
            errors.append(f"{bundle_key} must start from the getdaytrends workspace")
        if command_bundle not in recovery_bundle:
            errors.append(f"recovery_bundle missing command bundle: {bundle_key}")
        for command in commands:
            command_text = str(command).strip()
            if not command_text:
                errors.append(f"{list_key} contains an empty command")
                continue
            if command_text not in command_bundle:
                errors.append(f"{bundle_key} missing command: {command_text}")
            if command_text not in recovery_bundle:
                errors.append(f"recovery_bundle missing command from {list_key}: {command_text}")
    return errors


def _validate_launch_success_criteria(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    criteria = packet.get("launch_success_criteria")
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    if not isinstance(criteria, list):
        return ["launch_success_criteria must be a list"]

    for criterion in REQUIRED_LAUNCH_SUCCESS_CRITERIA:
        if criterion not in criteria:
            errors.append(f"launch_success_criteria missing required criterion: {criterion}")
        if criterion not in recovery_bundle:
            errors.append(f"recovery_bundle missing launch success criterion: {criterion}")
    return errors


def _validate_verification_commands(packet: dict[str, Any], packet_report: Path | None) -> list[str]:
    errors: list[str] = []
    commands = packet.get("verification_commands")
    verification_bundle = str(packet.get("verification_command_bundle") or "")
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    if not isinstance(commands, list):
        return ["verification_commands must be a list"]

    required_commands = (
        *REQUIRED_VERIFICATION_COMMANDS[:6],
        readiness_check._packet_verifier_command(
            readiness_check.SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND,
            packet_report,
        ),
        *REQUIRED_VERIFICATION_COMMANDS[6:],
    )
    for command in required_commands:
        if command not in commands:
            errors.append(f"verification_commands missing required launch command: {command}")
        if command not in verification_bundle:
            errors.append(f"verification_command_bundle missing required launch command: {command}")
        if command not in recovery_bundle:
            errors.append(f"recovery_bundle missing required verification command: {command}")
    return errors


def _validate_post_credential_recheck_sequence(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sequence = packet.get("post_credential_recheck_sequence")
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    if not isinstance(sequence, list):
        return ["post_credential_recheck_sequence must be a list"]
    if len(sequence) != len(REQUIRED_POST_CREDENTIAL_RECHECK_SEQUENCE):
        errors.append("post_credential_recheck_sequence must contain the required ordered steps")

    for index, expected in enumerate(REQUIRED_POST_CREDENTIAL_RECHECK_SEQUENCE):
        actual = sequence[index] if index < len(sequence) and isinstance(sequence[index], dict) else {}
        for key, expected_value in expected.items():
            if actual.get(key) != expected_value:
                errors.append(
                    f"post_credential_recheck_sequence step {index + 1} {key} must be {expected_value}"
                )
            if expected_value not in recovery_bundle:
                errors.append(f"recovery_bundle missing post-credential recheck {key}: {expected_value}")
    return errors


def _validate_post_credential_recheck_evidence(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    evidence = packet.get("post_credential_recheck_evidence")
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    if not isinstance(evidence, list):
        return ["post_credential_recheck_evidence must be a list"]
    if len(evidence) != len(REQUIRED_POST_CREDENTIAL_RECHECK_EVIDENCE):
        errors.append("post_credential_recheck_evidence must contain the required ordered evidence artifacts")

    for index, expected in enumerate(REQUIRED_POST_CREDENTIAL_RECHECK_EVIDENCE):
        actual = evidence[index] if index < len(evidence) and isinstance(evidence[index], dict) else {}
        for key, expected_value in expected.items():
            if actual.get(key) != expected_value:
                errors.append(f"post_credential_recheck_evidence step {index + 1} {key} must be {expected_value}")
            if expected_value not in recovery_bundle:
                errors.append(f"recovery_bundle missing post-credential evidence {key}: {expected_value}")
    return errors


def _validate_operator_final_proof_bundle(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    proof_bundle = packet.get("operator_final_proof_bundle")
    recovery_bundle = str(packet.get("recovery_bundle") or "")
    if not isinstance(proof_bundle, list):
        return ["operator_final_proof_bundle must be a list"]
    if len(proof_bundle) != len(REQUIRED_OPERATOR_FINAL_PROOF_BUNDLE):
        errors.append("operator_final_proof_bundle must contain the required final proof artifacts")

    for index, expected in enumerate(REQUIRED_OPERATOR_FINAL_PROOF_BUNDLE):
        actual = proof_bundle[index] if index < len(proof_bundle) and isinstance(proof_bundle[index], dict) else {}
        for key, expected_value in expected.items():
            if actual.get(key) != expected_value:
                errors.append(f"operator_final_proof_bundle item {index + 1} {key} must be {expected_value}")
            if expected_value not in recovery_bundle:
                errors.append(f"recovery_bundle missing operator final proof {key}: {expected_value}")
    return errors


def _live_db_failed(readiness_payload: dict[str, Any]) -> bool:
    live_check = _checks_by_name(readiness_payload).get("live_db_doctor")
    return bool(live_check) and live_check.get("ok") is False


def _validate_secret_hygiene(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    secret_hygiene = packet.get("secret_hygiene") if isinstance(packet.get("secret_hygiene"), dict) else {}
    if secret_hygiene.get("masked_postgres_urls") is not True:
        errors.append("secret_hygiene.masked_postgres_urls must be true")
    if secret_hygiene.get("masked_supabase_pooler_users") is not True:
        errors.append("secret_hygiene.masked_supabase_pooler_users must be true")
    if secret_hygiene.get("contains_plaintext_secret_values") is not False:
        errors.append("secret_hygiene.contains_plaintext_secret_values must be false")

    raw = "\n".join(_string_values(packet))
    if POSTGRES_USER_URL_RE.search(raw):
        errors.append("packet contains an unmasked PostgreSQL URL user")
    if TENANT_USER_RE.search(raw):
        errors.append("packet contains an unmasked tenant/user value")
    for match in SUPABASE_USER_RE.finditer(raw):
        if match.group(0) != "postgres.<project_ref>":
            errors.append("packet contains an unmasked Supabase pooler user")
            break
    if readiness_check.OPENAI_KEY_RE.search(raw) or readiness_check.GOOGLE_API_KEY_RE.search(raw):
        errors.append("packet contains an unmasked provider API key")
    return errors


def _validate_accepted_pooler_shapes(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    shapes = packet.get("accepted_transaction_pooler_shapes")
    if not isinstance(shapes, list):
        return ["accepted_transaction_pooler_shapes must be a list"]

    by_kind = {str(shape.get("kind")): shape for shape in shapes if isinstance(shape, dict)}
    for kind, expected_shape in REQUIRED_ACCEPTED_POOLER_SHAPES.items():
        shape = by_kind.get(kind)
        if not isinstance(shape, dict):
            errors.append(f"accepted_transaction_pooler_shapes missing: {kind}")
            continue
        for key, expected_value in expected_shape.items():
            if shape.get(key) != expected_value:
                errors.append(f"accepted_transaction_pooler_shapes.{kind}.{key} is not the expected passwordless value")

    if packet.get("accepts_shared_supavisor_transaction_pooler") is not True:
        errors.append("accepts_shared_supavisor_transaction_pooler must be true")
    if packet.get("accepts_dedicated_pgbouncer_transaction_pooler") is not True:
        errors.append("accepts_dedicated_pgbouncer_transaction_pooler must be true")

    return errors


def validate_recovery_packet(readiness_report: Path, packet_report: Path) -> list[str]:
    readiness_payload, readiness_error = _load_json(readiness_report)
    packet, packet_error = _load_json(packet_report)
    errors: list[str] = []
    if readiness_payload is None:
        errors.append(readiness_error)
    if packet is None:
        errors.append(packet_error)
    if readiness_payload is None or packet is None:
        return errors

    expected_packet_report = _expected_packet_report_for_verifier_command(
        packet,
        base_command=readiness_check.SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND,
        packet_report=packet_report,
    )
    expected = readiness_check.build_supabase_recovery_packet(
        readiness_payload,
        readiness_report=readiness_report,
        recovery_packet_report=expected_packet_report,
    )
    required_keys = (
        "schema_version",
        "status",
        "generated_at",
        "readiness_report",
        "readiness_generated_at",
        "readiness_status",
        "required_env",
        "issue_types",
        "live_db_failure_type",
        "next_required_action",
        "operator_focus",
        "blocking_checks",
        "source_checks",
        "recovery_summary",
        "evidence_freshness",
        "launch_success_criteria",
        "reference_links",
        "connection_mode_facts",
        "accepted_transaction_pooler_shapes",
        "accepts_shared_supavisor_transaction_pooler",
        "accepts_dedicated_pgbouncer_transaction_pooler",
        "scheduler_pause_commands",
        "scheduler_pause_command_bundle",
        "scheduler_resume_commands",
        "scheduler_resume_command_bundle",
        "credential_update_commands",
        "credential_update_command_bundle",
        "recovery_checklist",
        "post_credential_recheck_sequence",
        "post_credential_recheck_evidence",
        "operator_final_proof_bundle",
        "env_template",
        "recovery_bundle",
        "verification_commands",
        "verification_command_bundle",
        "secret_hygiene",
    )
    for key in required_keys:
        if not _has_value(packet, key):
            errors.append(f"packet missing required field: {key}")

    exact_match_keys = (
        "schema_version",
        "status",
        "readiness_status",
        "required_env",
        "issue_types",
        "live_db_failure_type",
        "next_required_action",
        "operator_focus",
        "blocking_checks",
        "source_checks",
        "diagnostics",
        "runtime_fallbacks",
        "launch_success_criteria",
        "reference_links",
        "connection_mode_facts",
        "accepted_transaction_pooler_shapes",
        "accepts_shared_supavisor_transaction_pooler",
        "accepts_dedicated_pgbouncer_transaction_pooler",
        "scheduler_task_names",
        "scheduler_pause_commands",
        "scheduler_pause_command_bundle",
        "scheduler_resume_commands",
        "scheduler_resume_command_bundle",
        "credential_update_commands",
        "credential_update_command_bundle",
        "recovery_checklist",
        "post_credential_recheck_sequence",
        "post_credential_recheck_evidence",
        "operator_final_proof_bundle",
        "env_template",
        "verification_commands",
        "verification_command_bundle",
        "secret_hygiene",
    )
    for key in exact_match_keys:
        if packet.get(key) != expected.get(key):
            errors.append(f"packet field does not match current readiness contract: {key}")

    if packet.get("readiness_generated_at") != readiness_payload.get("generated_at"):
        errors.append("packet readiness_generated_at does not match readiness report generated_at")
    if not _same_path(packet.get("readiness_report"), readiness_report):
        errors.append("packet readiness_report does not match the verified readiness report path")
    freshness = packet.get("evidence_freshness") if isinstance(packet.get("evidence_freshness"), dict) else {}
    if freshness.get("readiness_generated_at") != readiness_payload.get("generated_at"):
        errors.append("packet evidence_freshness.readiness_generated_at does not match readiness report")

    if packet.get("status") not in {"blocked", "clear", "not_evaluated"}:
        errors.append("packet status must be blocked, clear, or not_evaluated")
    if packet.get("required_env") != ["DATABASE_URL", "SUPABASE_URL"]:
        errors.append("packet required_env must be DATABASE_URL and SUPABASE_URL")
    if packet.get("status") == "blocked" and not packet.get("issue_types"):
        errors.append("blocked packet must include issue_types")
    if _contains_runtime_fallback(readiness_payload) and "runtime_database_fallback" not in packet.get("issue_types", []):
        errors.append("runtime fallback readiness evidence must produce runtime_database_fallback")
    if _contains_runtime_fallback(readiness_payload):
        source_checks = packet.get("source_checks") if isinstance(packet.get("source_checks"), dict) else {}
        cli_source = source_checks.get("cli_smoke_report") if isinstance(source_checks.get("cli_smoke_report"), dict) else {}
        expected_count, expected_kinds, expected_checks = _runtime_fallback_source_expectations(readiness_payload)
        if cli_source.get("runtime_fallback_count") != expected_count:
            errors.append("runtime fallback source check count must match readiness fallback evidence")
        if cli_source.get("runtime_fallback_kinds") != expected_kinds:
            errors.append("runtime fallback source check kinds must match readiness fallback evidence")
        if cli_source.get("runtime_fallback_checks") != expected_checks:
            errors.append("runtime fallback source check checks must match readiness fallback evidence")
        errors.extend(
            _validate_runtime_fallback_operator_text(packet, expected_count, expected_kinds, expected_checks)
        )
    if _live_db_failed(readiness_payload) and "live_db_doctor_failed" not in packet.get("issue_types", []):
        errors.append("failed live DB doctor must produce live_db_doctor_failed")
    if _live_db_failed(readiness_payload) and not str(packet.get("live_db_failure_type") or "").strip():
        errors.append("failed live DB doctor must include live_db_failure_type")

    bundle = str(packet.get("recovery_bundle") or "")
    for marker in (
        "## Next required action",
        "## Operator focus",
        "## Current blocker summary",
        "## Evidence freshness",
        "## Launch success criteria",
        "## Env template",
        "## Connection mode facts",
        "## Scheduler pause commands",
        "## Credential update commands",
        "## Recovery checklist",
        "## Post-credential recheck sequence",
        "## Post-credential evidence artifacts",
        "## Operator final proof bundle",
        "## Scheduler resume commands",
        "## References",
        "## Verification commands",
    ):
        if marker not in bundle:
            errors.append(f"recovery_bundle missing section: {marker}")
    for command in (
        readiness_check.LIVE_DB_DOCTOR_COMMAND,
        readiness_check.CLI_SMOKE_REFRESH_COMMAND,
        readiness_check.STRICT_READINESS_REFRESH_COMMAND,
        readiness_check.CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
    ):
        if command not in packet.get("verification_commands", []):
            errors.append(f"verification_commands missing: {command}")

    errors.extend(_validate_launch_success_criteria(packet))
    errors.extend(_validate_verification_commands(packet, expected_packet_report))
    errors.extend(_validate_post_credential_recheck_sequence(packet))
    errors.extend(_validate_post_credential_recheck_evidence(packet))
    errors.extend(_validate_operator_final_proof_bundle(packet))
    errors.extend(_validate_operator_command_bundles(packet))
    errors.extend(_validate_accepted_pooler_shapes(packet))
    errors.extend(_validate_secret_hygiene(packet))
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the getdaytrends Supabase recovery packet artifact.")
    parser.add_argument("--readiness-report", type=Path)
    parser.add_argument("--packet-report", type=Path, default=readiness_check.DEFAULT_SUPABASE_RECOVERY_PACKET)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    readiness_report = (
        args.readiness_report
        or _packet_readiness_report(args.packet_report)
        or readiness_check.DEFAULT_REPORT
    )
    errors = validate_recovery_packet(readiness_report, args.packet_report)
    if errors:
        print("getdaytrends Supabase recovery packet: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    packet, _ = _load_json(args.packet_report)
    issue_types = ", ".join(packet.get("issue_types", [])) if isinstance(packet, dict) else ""
    print(f"getdaytrends Supabase recovery packet: PASS status={packet.get('status')} issues={issue_types or 'none'}")
    print(f"readiness report: {readiness_report}")
    print(f"packet report: {args.packet_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
