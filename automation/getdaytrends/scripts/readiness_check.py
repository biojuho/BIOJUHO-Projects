"""Check getdaytrends production readiness evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SMOKE_REPORT = PROJECT_ROOT / "logs" / "smoke" / "cli_smoke_latest.json"
DEFAULT_BROWSER_REPORT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_latest.json"
DEFAULT_TAP_FIXTURE_BROWSER_REPORT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.json"
DEFAULT_HYGIENE_REPORT = PROJECT_ROOT / "logs" / "hygiene" / "text_hygiene_latest.json"
DEFAULT_SCHEDULER_DIR = PROJECT_ROOT / "logs" / "scheduler"
DEFAULT_REPORT = PROJECT_ROOT / "logs" / "readiness" / "readiness_latest.json"
DEFAULT_STRICT_REPORT = PROJECT_ROOT / "logs" / "readiness" / "strict_readiness_latest.json"
DEFAULT_SUPABASE_RECOVERY_PACKET = PROJECT_ROOT / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
DEFAULT_PROVIDER_AUTH_RECOVERY_PACKET = PROJECT_ROOT / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json"
DEFAULT_STRICT_SUPABASE_RECOVERY_PACKET = (
    PROJECT_ROOT / "logs" / "readiness" / "strict_supabase_recovery_packet_latest.json"
)
DEFAULT_STRICT_PROVIDER_AUTH_RECOVERY_PACKET = (
    PROJECT_ROOT / "logs" / "readiness" / "strict_provider_auth_recovery_packet_latest.json"
)
CLI_SMOKE_REFRESH_COMMAND = "python scripts\\smoke_cli.py --include-dry-run"
BROWSER_SMOKE_REFRESH_COMMAND = "python scripts\\browser_smoke.py --timeout 45"
TAP_FIXTURE_BROWSER_REFRESH_COMMAND = (
    "python scripts\\browser_smoke.py --tap-source-fixture --timeout 45 "
    "--report logs\\smoke\\dashboard_browser_tap_source_evidence.json "
    "--screenshot logs\\smoke\\dashboard_browser_tap_source_evidence.png"
)
TEXT_HYGIENE_REFRESH_COMMAND = "python scripts\\check_text_hygiene.py"
STRICT_READINESS_REFRESH_COMMAND = (
    "python scripts\\readiness_check.py --max-scheduler-age-hours 24 "
    "--max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 "
    "--fail-on-runtime-fallback --require-live-db"
)
LAUNCH_SECRET_SCAN_REFRESH_COMMAND = (
    "python ..\\..\\ops\\scripts\\getdaytrends_launch_secret_scan.py "
    "--include-current-artifacts "
    "--json-out ..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json"
)
CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND = (
    "python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends "
    "--json-out ..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json"
)
SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND = "python scripts\\verify_supabase_recovery_packet.py"
PROVIDER_AUTH_RECOVERY_PACKET_VERIFY_COMMAND = "python scripts\\verify_provider_auth_recovery_packet.py"
SAFE_CREDENTIAL_UPDATE_COMMAND = "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py"
SAFE_CREDENTIAL_INPUT_STATUS_COMMAND = SAFE_CREDENTIAL_UPDATE_COMMAND + " --input-status"
SAFE_DATABASE_UPDATE_VALIDATE_COMMAND = SAFE_CREDENTIAL_UPDATE_COMMAND + " --database-url-stdin"
SAFE_DATABASE_UPDATE_WRITE_COMMAND = SAFE_CREDENTIAL_UPDATE_COMMAND + " --database-url-stdin --write"
SAFE_PROVIDER_UPDATE_VALIDATE_COMMAND = SAFE_CREDENTIAL_UPDATE_COMMAND
SAFE_PROVIDER_UPDATE_WRITE_COMMAND = SAFE_CREDENTIAL_UPDATE_COMMAND + " --write"
SAFE_DATABASE_UPDATE_NEXT_ACTION = (
    f"dry-run validate the copied values with {SAFE_DATABASE_UPDATE_VALIDATE_COMMAND}, apply them locally with "
    f"{SAFE_DATABASE_UPDATE_WRITE_COMMAND}, then rerun the verification bundle."
)
SAFE_DATABASE_UPDATE_NEXT_ACTION_SENTENCE = SAFE_DATABASE_UPDATE_NEXT_ACTION[0].upper() + SAFE_DATABASE_UPDATE_NEXT_ACTION[1:]
SAFE_PROVIDER_UPDATE_NEXT_ACTION = (
    "Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY in the local shell, "
    f"dry-run validate with {SAFE_PROVIDER_UPDATE_VALIDATE_COMMAND}, apply the value to the local .env with "
    f"{SAFE_PROVIDER_UPDATE_WRITE_COMMAND}, update the production secret store, then rerun the verification bundle."
)
CANONICAL_WORKSPACE_SMOKE_SUCCESS_CRITERION = (
    "Canonical getdaytrends workspace smoke reports all configured checks PASS."
)
SUPABASE_CONNECTION_REFERENCE = {
    "label": "Supabase database connection guide",
    "url": "https://supabase.com/docs/guides/database/connecting-to-postgres",
}
SUPABASE_CIRCUIT_BREAKER_REFERENCE = {
    "label": "Supabase Supavisor password rotation circuit-breaker guide",
    "url": "https://supabase.com/docs/guides/troubleshooting/supavisor-error-circuit-breaker-open-after-password-rotation-0fdb72",
}
SUPABASE_SUPAVISOR_TERMINOLOGY_REFERENCE = {
    "label": "Supabase Supavisor connection terminology guide",
    "url": "https://supabase.com/docs/guides/troubleshooting/supavisor-and-connection-terminology-explained-9pr_ZO",
}
MICROSOFT_SCHTASKS_QUERY_REFERENCE = {
    "label": "Microsoft schtasks query reference",
    "url": "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-query",
}
MICROSOFT_SCHTASKS_CHANGE_REFERENCE = {
    "label": "Microsoft schtasks change reference",
    "url": "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-change",
}
GETDAYTRENDS_SCHEDULED_TASK_NAMES = (
    "GetDayTrends_CurrentUser",
    "GetDayTrends",
    "GetDayTrends_NewTask",
)
ACCEPTED_TRANSACTION_POOLER_SHAPES = [
    {
        "kind": "shared_supavisor_transaction",
        "host": "aws-[region].pooler.supabase.com",
        "port": 6543,
        "username": "postgres.<project_ref>",
        "database": "postgres",
        "url_shape_without_password": "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres",
    },
    {
        "kind": "dedicated_pgbouncer_transaction",
        "host": "db.<project_ref>.supabase.co",
        "port": 6543,
        "username": "postgres",
        "database": "postgres",
        "url_shape_without_password": "postgres@db.<project_ref>.supabase.co:6543/postgres",
    },
]
ACCEPTED_TRANSACTION_POOLER_SHAPE_SUMMARY = (
    "Accepted Transaction pooler shapes: shared Supavisor "
    "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres or dedicated PgBouncer "
    "postgres@db.<project_ref>.supabase.co:6543/postgres."
)
SUPABASE_TRANSACTION_POOLER_FACTS = [
    "Expected DATABASE_URL mode: Supabase Transaction pooler.",
    ACCEPTED_TRANSACTION_POOLER_SHAPE_SUMMARY,
    "Expected port: 6543.",
    "Expected database: postgres.",
    "Copy DATABASE_URL from the Supabase Dashboard Connect panel and keep SUPABASE_URL from the same project.",
    "Before rotating or replacing the database password, pause scheduled/background getdaytrends clients so stale credentials stop hitting the pooler.",
    "For Supavisor/shared pooler circuit breaker responses after bad password attempts, wait for the short lockout to clear after updating credentials.",
    "Transaction mode does not support prepared statements; keep asyncpg transaction-pooler paths configured with statement_cache_size=0.",
    "For the shared Supavisor pooler, the intended user+database+mode combination is postgres.<project_ref> + postgres + transaction/6543.",
]
OPENAI_API_KEY_REFERENCE = {
    "label": "OpenAI API key production guidance",
    "url": "https://developers.openai.com/api/docs/guides/production-best-practices#api-keys",
}
GOOGLE_AI_API_KEY_REFERENCE = {
    "label": "Google AI Gemini API key guide",
    "url": "https://ai.google.dev/gemini-api/docs/api-key",
}
DATABASE_FALLBACK_REMEDIATION = (
    "Fix DATABASE_URL / Supabase pooler credentials, verify the production database connects "
    f"without fallback. {SAFE_DATABASE_UPDATE_NEXT_ACTION_SENTENCE} "
    "The verification bundle includes python scripts\\smoke_cli.py --include-dry-run."
)
COST_DB_FALLBACK_REMEDIATION = (
    "Fix LLM_COSTS_DATABASE_URL / shared cost DB connectivity, verify cost tracking persists "
    "without falling back to in-memory storage, then rerun python scripts\\smoke_cli.py --include-dry-run."
)
PROVIDER_AUTH_REMEDIATION = (
    "Rotate or revoke the affected LLM provider key. "
    f"{SAFE_PROVIDER_UPDATE_NEXT_ACTION} "
    "The verification bundle includes python scripts\\smoke_cli.py --include-dry-run and strict readiness."
)
RUNTIME_FALLBACK_REMEDIATION = (
    "Fix DATABASE_URL / Supabase pooler credentials, verify the production database and any configured "
    f"cost DB path connect without fallback. {SAFE_DATABASE_UPDATE_NEXT_ACTION_SENTENCE} "
    "The verification bundle includes python scripts\\smoke_cli.py --include-dry-run."
)
LIVE_DB_DOCTOR_COMMAND = "python main.py --doctor --require-live-db"
LIVE_DB_DOCTOR_REMEDIATION = (
    "Fix DATABASE_URL / Supabase pooler credentials, confirm SUPABASE_URL comes from the same project, "
    "and verify the Supabase project ref, project state, "
    f"database password, and pooler settings. {SAFE_DATABASE_UPDATE_NEXT_ACTION_SENTENCE} "
    "The verification bundle includes python main.py --doctor --require-live-db. "
    f"Reference: {SUPABASE_CONNECTION_REFERENCE['url']}"
)
SUPABASE_URL_CROSSCHECK_REMEDIATION = (
    "Set SUPABASE_URL from the same Supabase project as DATABASE_URL so the doctor can verify both refs automatically."
)
SUPABASE_REF_MISMATCH_REMEDIATION = (
    "Copy both SUPABASE_URL and the Transaction pooler DATABASE_URL from the same Supabase project Connect panel."
)
RUNTIME_FALLBACK_PATTERNS = (
    ("database.sqlite_fallback", "postgresql connection failed; falling back to local sqlite"),
    ("cost_db.in_memory_fallback", "failed to init cost db:"),
    ("cost_db.in_memory_fallback", "falling back to in-memory"),
)
PROVIDER_AUTH_PATTERNS = (
    ("provider.api_key_leaked", "api key was reported as leaked"),
    ("provider.invalid_api_key", "incorrect api key"),
    ("provider.permission_denied", "permission_denied"),
    ("provider.permission_denied", "does not have permission"),
    ("provider.quota_or_billing", "used all available credits"),
    ("provider.quota_or_billing", "monthly spending limit"),
    ("provider.quota_or_billing", "purchase more credits"),
    ("provider.authentication_error", "authenticationerror"),
    ("provider.auth_failure", "auth failure"),
)
SCHEDULER_REFRESH_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    ".\\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea"
)
REQUIRED_TAP_FIXTURE_CHECKS = (
    "tap_source_notes_rendered",
    "fixture_endpoints_not_degraded",
    "tap_deal_room_ops_summary",
    "tap_deal_room_track_click_event",
    "tap_deal_room_checkout_open_recovery",
    "tap_checkout_return_notice",
    "operator_action_buttons_described",
    "server_has_no_dashboard_degraded_endpoint_logs",
)
BENCHMARK_DOC = PROJECT_ROOT / "docs" / "GITHUB_BENCHMARK_2026-06-04.md"
REQUIRED_DOCS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "WORKFLOW.md",
    PROJECT_ROOT / "GETDAYTRENDS_COMPLETION_PLAN.md",
    PROJECT_ROOT / "docs" / "RUNBOOK_ROLLBACK_FAILOVER.md",
    BENCHMARK_DOC,
)
POOLER_RUNTIME_COMPATIBILITY_FILES = (
    PROJECT_ROOT / "db_layer" / "connection.py",
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "scripts" / "migrate_sqlite_to_supabase.py",
)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
POSTGRES_URL_RE = re.compile(r"\b(postgres(?:ql)?://)[^\s\"'<>]+", re.IGNORECASE)
SUPABASE_USER_RE = re.compile(r"\bpostgres\.[A-Za-z0-9_.-]+")
TENANT_USER_RE = re.compile(r"(\btenant/user\s+)[^\s),;]+", re.IGNORECASE)
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{16,}\b")
PROVIDER_TEAM_ID_RE = re.compile(
    r"(\bteam\s+)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
DOCTOR_DIAGNOSTIC_RE = re.compile(r"^\[(?P<level>[A-Z]+)\]\s+(?P<check_id>[A-Za-z0-9_.-]+):\s*(?P<message>.*)$")
ASYNC_PG_STATEMENT_CACHE_DISABLED_RE = re.compile(r"\bstatement_cache_size\s*=\s*0\b")


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    ok: bool
    level: str
    message: str
    evidence: dict[str, Any]
    remediation: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "ok": self.ok,
            "level": self.level,
            "message": self.message,
            "evidence": self.evidence,
        }
        if self.remediation:
            payload["remediation"] = self.remediation
        return payload


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, "json root is not an object"
    return payload, ""


def _json_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    results = payload.get("results")
    if isinstance(results, list):
        passed = sum(1 for result in results if isinstance(result, dict) and result.get("ok") is True)
        failed = sum(1 for result in results if isinstance(result, dict) and result.get("ok") is not True)
        return {"total": len(results), "passed": passed, "failed": failed}
    return {}


def _matching_line(text: str, needle: str) -> str:
    needle_lower = needle.lower()
    for line in text.splitlines():
        if needle_lower in line.lower():
            return ANSI_ESCAPE_RE.sub("", line).strip()[:240]
    return ANSI_ESCAPE_RE.sub("", text).strip()[:240]


def _mask_sensitive_text(text: str) -> str:
    masked = POSTGRES_URL_RE.sub(r"\1***", text)
    masked = SUPABASE_USER_RE.sub("postgres.<project_ref>", masked)
    masked = TENANT_USER_RE.sub(r"\1***", masked)
    masked = OPENAI_KEY_RE.sub("sk-***", masked)
    masked = GOOGLE_API_KEY_RE.sub("AIza***", masked)
    return PROVIDER_TEAM_ID_RE.sub(r"\1***", masked)


def _reference_links_section(reference_links: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- {link['label']}: {link['url']}"
        for link in reference_links
        if link.get("label") and link.get("url")
    )


def _doctor_diagnostic_lines(output: str) -> list[str]:
    diagnostic_ids = (
        "db.database_url_source",
        "db.supabase_url_shape",
        "db.supabase_project_ref_crosscheck",
        "db.endpoint_dns",
        "db.endpoint_tcp",
        "db.live_postgres",
    )
    lines: list[str] = []
    for raw_line in output.splitlines():
        line = _mask_sensitive_text(ANSI_ESCAPE_RE.sub("", raw_line).strip())
        if any(check_id in line for check_id in diagnostic_ids):
            lines.append(line[:320])
    return lines


def _doctor_failure_detail(diagnostics: list[str]) -> str:
    priority_ids = ("db.supabase_project_ref_crosscheck", "db.live_postgres", "db.endpoint_tcp", "db.endpoint_dns")
    for check_id in priority_ids:
        line = next((item for item in diagnostics if check_id in item and "[ERROR]" in item), "")
        if line:
            return line
    return next((item for item in diagnostics if "[ERROR]" in item), "")


def _live_db_doctor_remediation(diagnostics: list[str]) -> str:
    additions: list[str] = []
    joined = "\n".join(diagnostics)
    if "db.supabase_project_ref_crosscheck" in joined:
        if "does not match SUPABASE_URL" in joined:
            additions.append(SUPABASE_REF_MISMATCH_REMEDIATION)
        elif "SUPABASE_URL is not set" in joined:
            additions.append(SUPABASE_URL_CROSSCHECK_REMEDIATION)
    if additions:
        return " ".join([*additions, LIVE_DB_DOCTOR_REMEDIATION])
    return LIVE_DB_DOCTOR_REMEDIATION


def _live_db_failure_type(
    check: dict[str, Any],
    evidence: dict[str, Any],
    *,
    diagnostics: list[dict[str, str]] | None = None,
) -> str:
    if not isinstance(evidence, dict):
        return ""
    message = str(check.get("message") or "").strip().lower()
    if evidence.get("timeout") is True or "timed out" in message:
        return "timeout"
    if evidence.get("error"):
        return "execution_error"
    parsed_diagnostics = diagnostics if diagnostics is not None else _parsed_doctor_diagnostics(evidence.get("diagnostics"))
    if any(str(item.get("level") or "").upper() == "ERROR" for item in parsed_diagnostics):
        return "diagnostic_error"
    exit_code = evidence.get("exit_code")
    try:
        return "" if int(exit_code) == 0 else "nonzero_exit"
    except (TypeError, ValueError):
        return ""


def _check_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name", "")): check
        for check in checks
        if isinstance(check, dict) and str(check.get("name", "")).strip()
    }


def _masked_dict_list(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    masked_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        masked_items.append(
            {
                str(key): _mask_sensitive_text(str(value)) if isinstance(value, str) else value
                for key, value in item.items()
            }
        )
    return masked_items


def _parsed_doctor_diagnostics(diagnostics: Any) -> list[dict[str, str]]:
    if not isinstance(diagnostics, list):
        return []
    parsed: list[dict[str, str]] = []
    for diagnostic in diagnostics:
        line = _mask_sensitive_text(str(diagnostic).strip())
        if not line:
            continue
        match = DOCTOR_DIAGNOSTIC_RE.match(line)
        if match:
            parsed.append(
                {
                    "level": match.group("level"),
                    "check_id": match.group("check_id"),
                    "message": match.group("message")[:320],
                    "line": line[:420],
                }
            )
        else:
            parsed.append({"level": "INFO", "check_id": "", "message": line[:320], "line": line[:420]})
    return parsed


def _supabase_recovery_issue_types(
    *,
    diagnostics: list[dict[str, str]],
    runtime_fallbacks: list[dict[str, Any]],
    live_db_failed: bool,
    live_db_timeout: bool = False,
) -> list[str]:
    issue_types: list[str] = []
    if runtime_fallbacks:
        issue_types.append("runtime_database_fallback")
    if live_db_failed:
        issue_types.append("live_db_doctor_failed")
    if live_db_timeout:
        issue_types.append("live_db_doctor_timeout")
        issue_types.append("live_postgres_probe_failed")
    for diagnostic in diagnostics:
        check_id = diagnostic.get("check_id", "")
        level = diagnostic.get("level", "")
        message = diagnostic.get("message", "")
        if check_id == "db.supabase_project_ref_crosscheck":
            if "SUPABASE_URL is not set" in message:
                issue_types.append("missing_supabase_url_crosscheck")
            elif "does not match SUPABASE_URL" in message:
                issue_types.append("supabase_project_ref_mismatch")
        if check_id == "db.supabase_pooler_mode" and level == "ERROR":
            issue_types.append("supabase_transaction_pooler_required")
        if check_id == "db.live_postgres" and level == "ERROR":
            issue_types.append("live_postgres_probe_failed")
            if "tenant/user" in message.lower():
                issue_types.append("pooler_tenant_user_not_found")
        if check_id == "db.endpoint_dns" and level == "ERROR":
            issue_types.append("database_endpoint_dns_failed")
        if check_id == "db.endpoint_tcp" and level == "ERROR":
            issue_types.append("database_endpoint_tcp_failed")
    return sorted(set(issue_types))


def _supabase_recovery_env_template(diagnostics: list[dict[str, str]]) -> str:
    endpoint = ""
    for diagnostic in diagnostics:
        if diagnostic.get("check_id") != "db.endpoint_tcp":
            continue
        message = diagnostic.get("message", "")
        host_match = re.search(r"host=([^,\s]+)", message)
        port_match = re.search(r"port=(\d+)", message)
        if host_match and port_match:
            endpoint = f"{host_match.group(1)}:{port_match.group(1)}"
            break

    lines = [
        "# getdaytrends production database recovery template",
        "# Fill these values from the same Supabase project Connect panel.",
        "SUPABASE_URL=https://<project_ref>.supabase.co",
        "DATABASE_URL=<transaction_pooler_uri_from_same_project>",
    ]
    if endpoint:
        lines.append(f"# Current pooler endpoint observed by doctor: {endpoint}")
    lines.extend(
        [
            "# DATABASE_URL must use the Transaction pooler URI, current database password, and port 6543.",
            "# After saving, run the copied verification command bundle from the dashboard.",
        ]
    )
    return "\n".join(lines)


def _database_credential_update_command_bundle() -> tuple[list[str], str]:
    project_root_literal = str(PROJECT_ROOT).replace("'", "''")
    commands = [
        f"Set-Location -LiteralPath '{project_root_literal}'",
        "# Preflight: confirm whether replacement credential inputs are staged before rerunning strict readiness.",
        SAFE_CREDENTIAL_INPUT_STATUS_COMMAND,
        "# Pause scheduled/background getdaytrends clients before rotating or applying DB credentials to avoid repeated stale-password pooler attempts.",
        "# If Supavisor reports a circuit breaker, wait at least 2 minutes after applying corrected credentials before retrying.",
        "# Fast path: copy the new Transaction pooler DATABASE_URL, then dry-run from the clipboard without interactive EOF.",
        f"Get-Clipboard -Raw | {SAFE_DATABASE_UPDATE_VALIDATE_COMMAND}",
        "# Apply from the clipboard only after the dry-run passes.",
        f"Get-Clipboard -Raw | {SAFE_DATABASE_UPDATE_WRITE_COMMAND}",
        "# Interactive fallback: run this, paste the same DATABASE_URL, then send EOF by pressing Ctrl+Z, then Enter in PowerShell.",
        SAFE_DATABASE_UPDATE_VALIDATE_COMMAND,
        "# Interactive apply fallback: paste the same DATABASE_URL again, then send EOF by pressing Ctrl+Z, then Enter in PowerShell.",
        SAFE_DATABASE_UPDATE_WRITE_COMMAND,
    ]
    return commands, "\n".join(commands)


def _scheduler_pause_command_bundle() -> tuple[list[str], str]:
    project_root_literal = str(PROJECT_ROOT).replace("'", "''")
    task_names_literal = ", ".join(f"'{name}'" for name in GETDAYTRENDS_SCHEDULED_TASK_NAMES)
    commands = [
        f"Set-Location -LiteralPath '{project_root_literal}'",
        "# Inspect the duplicate-run lock before pausing scheduled execution.",
        "$lockPath = Join-Path (Get-Location) 'data\\getdaytrends.lock'",
        "if (Test-Path $lockPath) {",
        "  $lockPid = (Get-Content -Raw $lockPath).Trim()",
        "  if ($lockPid -match '^\\d+$') { Get-Process -Id ([int]$lockPid) -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,Path }",
        "}",
        f"$taskNames = @({task_names_literal})",
        "# Pause known getdaytrends scheduled tasks before rotating or applying DB credentials.",
        "foreach ($taskName in $taskNames) {",
        "  $taskStatus = schtasks /Query /TN $taskName /FO LIST 2>$null",
        "  if ($LASTEXITCODE -eq 0) { $taskStatus; schtasks /Change /TN $taskName /DISABLE } else { \"Task not found: $taskName\" }",
        "}",
        "# Confirm the known task states before continuing with credential rotation.",
        "foreach ($taskName in $taskNames) { schtasks /Query /TN $taskName /FO LIST 2>$null }",
    ]
    return commands, "\n".join(commands)


def _scheduler_resume_command_bundle() -> tuple[list[str], str]:
    project_root_literal = str(PROJECT_ROOT).replace("'", "''")
    task_names_literal = ", ".join(f"'{name}'" for name in GETDAYTRENDS_SCHEDULED_TASK_NAMES)
    commands = [
        f"Set-Location -LiteralPath '{project_root_literal}'",
        f"$taskNames = @({task_names_literal})",
        "# Re-enable only after live DB doctor, CLI smoke, strict readiness, and workspace smoke pass.",
        "foreach ($taskName in $taskNames) {",
        "  $taskStatus = schtasks /Query /TN $taskName /FO LIST 2>$null",
        "  if ($LASTEXITCODE -eq 0) { $taskStatus; schtasks /Change /TN $taskName /ENABLE } else { \"Task not found: $taskName\" }",
        "}",
        "# Confirm the known task states after re-enable.",
        "foreach ($taskName in $taskNames) { schtasks /Query /TN $taskName /FO LIST 2>$null }",
    ]
    return commands, "\n".join(commands)


def _post_credential_recheck_sequence() -> list[dict[str, str]]:
    return [
        {
            "step": "live_db_doctor",
            "command": LIVE_DB_DOCTOR_COMMAND,
            "success_criterion": "Live DB doctor reports OK for the primary Supabase PostgreSQL connection.",
        },
        {
            "step": "cli_smoke",
            "command": CLI_SMOKE_REFRESH_COMMAND,
            "success_criterion": "CLI smoke completes with runtime_fallback_count 0.",
        },
        {
            "step": "strict_readiness",
            "command": STRICT_READINESS_REFRESH_COMMAND,
            "success_criterion": "Strict readiness reports status pass.",
        },
        {
            "step": "canonical_workspace_smoke",
            "command": CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
            "success_criterion": CANONICAL_WORKSPACE_SMOKE_SUCCESS_CRITERION,
        },
    ]


def _post_credential_recheck_section(sequence: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(sequence, 1):
        lines.append(f"{index}. {item['step']}")
        lines.append(f"   Command: {item['command']}")
        lines.append(f"   Success: {item['success_criterion']}")
    return "\n".join(lines)


def _post_credential_recheck_evidence() -> list[dict[str, str]]:
    return [
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
    ]


def _post_credential_recheck_evidence_section(evidence: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(evidence, 1):
        lines.append(f"{index}. {item['step']}")
        lines.append(f"   Artifact: {item['artifact']}")
        lines.append(f"   Signal: {item['success_signal']}")
    return "\n".join(lines)


def _operator_final_proof_bundle() -> list[dict[str, str]]:
    return [
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
    ]


def _operator_final_proof_bundle_section(proof_bundle: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(proof_bundle, 1):
        lines.append(f"{index}. {item['artifact']}")
        lines.append(f"   Success: {item['success_signal']}")
    return "\n".join(lines)


def _supabase_diagnostic_level(diagnostics: list[dict[str, str]], check_id: str) -> str:
    for diagnostic in diagnostics:
        if diagnostic.get("check_id") == check_id:
            return str(diagnostic.get("level") or "").upper()
    return ""


def _supabase_operator_focus(issue_types: list[str], diagnostics: list[dict[str, str]]) -> str:
    issue_set = set(issue_types)
    refs_ok = _supabase_diagnostic_level(diagnostics, "db.supabase_project_ref_crosscheck") == "OK"
    dns_ok = _supabase_diagnostic_level(diagnostics, "db.endpoint_dns") == "OK"
    tcp_ok = _supabase_diagnostic_level(diagnostics, "db.endpoint_tcp") == "OK"
    if "supabase_project_ref_mismatch" in issue_set:
        return (
            "SUPABASE_URL and DATABASE_URL point at different Supabase projects. Recopy both values from the "
            "same project Connect panel before retesting."
        )
    if "missing_supabase_url_crosscheck" in issue_set:
        return (
            "SUPABASE_URL is missing, so the doctor cannot prove DATABASE_URL belongs to the intended project. "
            "Set SUPABASE_URL from the same project before changing lower-level network settings."
        )
    if "supabase_transaction_pooler_required" in issue_set:
        return (
            "DATABASE_URL uses a Supabase pooler mode other than the required Transaction pooler. Recopy the "
            "Transaction pooler URI from the same project Connect panel and keep port 6543."
        )
    if "pooler_tenant_user_not_found" in issue_set:
        if refs_ok and dns_ok and tcp_ok:
            return (
                "Project refs, DNS, and TCP already pass; focus on the current Supabase project state, database "
                "password, and Transaction pooler credentials from the Dashboard Connect panel."
            )
        return (
            "The pooler rejected the tenant/user. Confirm the project is active, then recopy the current "
            "Transaction pooler URI and database password from the Dashboard Connect panel."
        )
    if "database_endpoint_dns_failed" in issue_set:
        return "DNS failed before authentication; verify the Transaction pooler host copied into DATABASE_URL."
    if "database_endpoint_tcp_failed" in issue_set:
        return "TCP failed before authentication; verify port 6543 network access and the DATABASE_URL host/port."
    if "live_db_doctor_timeout" in issue_set:
        return "Live DB doctor timed out; verify network reachability before changing provider credentials."
    if "runtime_database_fallback" in issue_set:
        return "CLI smoke is still falling back to SQLite; fix the primary DATABASE_URL and rerun strict readiness."
    return "No Supabase launch blocker is currently classified."


def _supabase_recovery_summary(
    *,
    status: str,
    issue_types: list[str],
    next_required_action: str,
    operator_focus: str,
    blocking_checks: list[dict[str, str]],
    diagnostics: list[dict[str, str]],
    runtime_fallbacks: list[dict[str, Any]],
) -> str:
    lines = [
        f"Status: {status}",
        "Issue types: " + (", ".join(issue_types) if issue_types else "-"),
    ]
    if next_required_action:
        lines.append(f"Next required action: {next_required_action}")
    if operator_focus:
        lines.append(f"Operator focus: {operator_focus}")
    if blocking_checks:
        lines.append("Blocking checks: " + ", ".join(str(check.get("name", "unknown")) for check in blocking_checks))
    if runtime_fallbacks:
        fallback_kinds = sorted({str(item.get("kind") or item.get("name") or "unknown") for item in runtime_fallbacks})
        fallback_checks = sorted(
            {
                str(item.get("check") or item.get("command") or "").strip()
                for item in runtime_fallbacks
                if str(item.get("check") or item.get("command") or "").strip()
            }
        )
        lines.append(f"Runtime fallback count: {len(runtime_fallbacks)}")
        lines.append("Runtime fallback kinds: " + ", ".join(fallback_kinds))
        if fallback_checks:
            lines.append("Runtime fallback checks: " + ", ".join(fallback_checks))

    diagnostic_lines = [str(item.get("line", "")).strip() for item in diagnostics if str(item.get("line", "")).strip()]
    if diagnostic_lines:
        lines.append("Doctor diagnostics:")
        lines.extend(f"- {line}" for line in diagnostic_lines[-4:])
    return "\n".join(_mask_sensitive_text(line) for line in lines)


def _supabase_pause_first_action(action: str) -> str:
    return (
        "Pause scheduled/background getdaytrends clients before rotating or applying database credentials, "
        f"then {action[:1].lower()}{action[1:]}"
    )


def _supabase_next_required_action(issue_types: list[str]) -> str:
    issue_set = set(issue_types)
    if "supabase_project_ref_mismatch" in issue_set:
        return _supabase_pause_first_action(
            "Copy both SUPABASE_URL and the Transaction pooler DATABASE_URL from the same Supabase "
            f"project Connect panel, then {SAFE_DATABASE_UPDATE_NEXT_ACTION}"
        )
    if "pooler_tenant_user_not_found" in issue_set:
        return _supabase_pause_first_action(
            "Set SUPABASE_URL from the intended Supabase project, replace DATABASE_URL with that same "
            "project's current Transaction pooler URI, rotate or correct the pooler credential if needed, "
            f"then {SAFE_DATABASE_UPDATE_NEXT_ACTION}"
        )
    if "supabase_transaction_pooler_required" in issue_set:
        return _supabase_pause_first_action(
            "Confirm SUPABASE_URL is set to the intended Supabase project, replace DATABASE_URL with that "
            f"same project's Transaction pooler URI on port 6543, then {SAFE_DATABASE_UPDATE_NEXT_ACTION}"
        )
    if "live_db_doctor_timeout" in issue_set or "live_postgres_probe_failed" in issue_set:
        return _supabase_pause_first_action(
            "Set SUPABASE_URL from the intended Supabase project, verify DATABASE_URL uses that same "
            "project's Transaction pooler host, current database password, and reachable network path, "
            f"then {SAFE_DATABASE_UPDATE_NEXT_ACTION}"
        )
    if "missing_supabase_url_crosscheck" in issue_set:
        return (
            "Set SUPABASE_URL from the same Supabase project as DATABASE_URL so the live DB doctor can "
            "cross-check the project before final smoke."
        )
    if "database_endpoint_dns_failed" in issue_set:
        return "Verify the Transaction pooler host in DATABASE_URL and DNS access, then rerun the verification bundle."
    if "database_endpoint_tcp_failed" in issue_set:
        return "Verify pooler port 6543 network access and DATABASE_URL host/port, then rerun the verification bundle."
    if "runtime_database_fallback" in issue_set:
        return _supabase_pause_first_action(
            "Fix the primary DATABASE_URL so CLI smoke reaches PostgreSQL without SQLite fallback, then rerun strict readiness."
        )
    return "No Supabase launch blocker is currently classified; run the final canonical workspace smoke before release."


def build_supabase_recovery_packet(
    readiness_payload: dict[str, Any],
    *,
    readiness_report: Path | None = None,
    recovery_packet_report: Path | None = None,
) -> dict[str, Any]:
    checks_by_name = _check_by_name(readiness_payload)
    cli_check = checks_by_name.get("cli_smoke_report", {})
    live_check = checks_by_name.get("live_db_doctor", {})
    pooler_compat_check = checks_by_name.get("pooler_runtime_compatibility", {})
    cli_evidence = cli_check.get("evidence") if isinstance(cli_check.get("evidence"), dict) else {}
    live_evidence = live_check.get("evidence") if isinstance(live_check.get("evidence"), dict) else {}
    runtime_fallbacks = _masked_dict_list(cli_evidence.get("runtime_fallbacks"))
    runtime_fallback_kinds = sorted(
        {str(item.get("kind") or item.get("name") or "unknown") for item in runtime_fallbacks}
    )
    runtime_fallback_checks = sorted(
        {
            str(item.get("check") or item.get("command") or "").strip()
            for item in runtime_fallbacks
            if str(item.get("check") or item.get("command") or "").strip()
        }
    )
    diagnostics = _parsed_doctor_diagnostics(live_evidence.get("diagnostics"))
    live_db_evaluated = bool(live_check)
    live_db_failed = bool(live_check) and live_check.get("ok") is False
    live_db_timeout = live_evidence.get("timeout") is True or "timed out" in str(
        live_check.get("message", "")
    ).lower()
    live_db_failure_type = str(live_evidence.get("failure_type") or "").strip()
    if not live_db_failure_type and live_db_failed:
        live_db_failure_type = _live_db_failure_type(live_check, live_evidence, diagnostics=diagnostics)
    issue_types = _supabase_recovery_issue_types(
        diagnostics=diagnostics,
        runtime_fallbacks=runtime_fallbacks,
        live_db_failed=live_db_failed,
        live_db_timeout=live_db_timeout,
    )
    supabase_source_checks = (cli_check, live_check)
    blocking_checks = [
        {
            "name": str(check.get("name", "unknown_check")),
            "level": str(check.get("level", "ERROR")),
            "message": _mask_sensitive_text(str(check.get("message", "")))[:420],
        }
        for check in supabase_source_checks
        if check.get("ok") is False and str(check.get("level", "ERROR")).upper() != "WARN"
    ]
    if issue_types:
        status = "blocked"
    elif live_db_evaluated:
        status = "clear"
    else:
        status = "not_evaluated"
    generated_at = datetime.now().astimezone().isoformat()
    readiness_generated_at = str(readiness_payload.get("generated_at") or "")
    readiness_report_path = str(readiness_report or DEFAULT_REPORT)

    recovery_checklist = [
        "Pause scheduled/background getdaytrends clients before rotating or applying database credentials.",
        "Copy and run the scheduler pause commands so known getdaytrends Task Scheduler jobs are disabled before credential rotation.",
        "Open the Supabase dashboard Connect panel for the intended production project.",
        "Choose one accepted Transaction pooler connection string: shared Supavisor "
        "postgres.<project_ref>@aws-[region].pooler.supabase.com:6543/postgres or dedicated PgBouncer "
        "postgres@db.<project_ref>.supabase.co:6543/postgres.",
        "Set SUPABASE_URL to the Project URL from that same Supabase project.",
        "Set DATABASE_URL to the Transaction pooler URI from that same project, including the current database password.",
        f"Dry-run validate the copied Supabase values with {SAFE_DATABASE_UPDATE_VALIDATE_COMMAND}.",
        f"Apply the copied Supabase values locally with {SAFE_DATABASE_UPDATE_WRITE_COMMAND}.",
        "If db.live_postgres reports tenant/user not found, confirm the project is active and regenerate or correct the pooler credentials.",
        "If Supavisor reports a circuit breaker after bad password attempts, wait at least 2 minutes after stopping stale clients and applying corrected credentials before retrying.",
        "Confirm pooler_runtime_compatibility is OK so asyncpg transaction-pooler paths keep statement_cache_size=0.",
        f"Run {LIVE_DB_DOCTOR_COMMAND} from automation\\getdaytrends.",
        "Rerun python scripts\\smoke_cli.py --include-dry-run and confirm runtime_fallback_count is 0.",
        f"Rerun {STRICT_READINESS_REFRESH_COMMAND} and confirm readiness status is pass.",
        f"Rerun {CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND} and confirm all configured checks pass.",
        "Copy and run the scheduler resume commands only after the live DB and strict launch gates pass.",
    ]
    verification_commands = [
        LIVE_DB_DOCTOR_COMMAND,
        CLI_SMOKE_REFRESH_COMMAND,
        BROWSER_SMOKE_REFRESH_COMMAND,
        TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
        TEXT_HYGIENE_REFRESH_COMMAND,
        STRICT_READINESS_REFRESH_COMMAND,
        _packet_verifier_command(SUPABASE_RECOVERY_PACKET_VERIFY_COMMAND, recovery_packet_report),
        LAUNCH_SECRET_SCAN_REFRESH_COMMAND,
        CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
    ]
    project_root_literal = str(PROJECT_ROOT).replace("'", "''")
    verification_command_bundle = "\n".join(
        [
            f"Set-Location -LiteralPath '{project_root_literal}'",
            *verification_commands,
        ]
    )
    launch_success_criteria = [
        "Live DB doctor reports OK for the primary Supabase PostgreSQL connection.",
        "Pooler runtime compatibility reports OK with prepared-statement caching disabled for transaction-pooler asyncpg paths.",
        "CLI smoke reports runtime_fallback_count 0.",
        "Production text hygiene reports pass.",
        "Strict readiness reports status pass.",
        "Launch secret scan reports valid with zero findings, zero missing paths, and current artifacts included.",
        CANONICAL_WORKSPACE_SMOKE_SUCCESS_CRITERION,
    ]
    reference_links = [
        SUPABASE_CONNECTION_REFERENCE,
        SUPABASE_SUPAVISOR_TERMINOLOGY_REFERENCE,
        SUPABASE_CIRCUIT_BREAKER_REFERENCE,
        MICROSOFT_SCHTASKS_QUERY_REFERENCE,
        MICROSOFT_SCHTASKS_CHANGE_REFERENCE,
    ]
    evidence_freshness = {
        "packet_generated_at": generated_at,
        "readiness_generated_at": readiness_generated_at,
        "readiness_report": readiness_report_path,
    }
    evidence_freshness_summary = "\n".join(
        [
            f"Packet generated: {generated_at}",
            f"Readiness generated: {readiness_generated_at or 'unknown'}",
            f"Readiness report: {readiness_report_path}",
        ]
    )
    env_template = _supabase_recovery_env_template(diagnostics)
    credential_update_commands, credential_update_command_bundle = _database_credential_update_command_bundle()
    scheduler_pause_commands, scheduler_pause_command_bundle = _scheduler_pause_command_bundle()
    scheduler_resume_commands, scheduler_resume_command_bundle = _scheduler_resume_command_bundle()
    post_credential_recheck_sequence = _post_credential_recheck_sequence()
    post_credential_recheck_evidence = _post_credential_recheck_evidence()
    operator_final_proof_bundle = _operator_final_proof_bundle()
    next_required_action = _mask_sensitive_text(_supabase_next_required_action(issue_types))
    operator_focus = _mask_sensitive_text(_supabase_operator_focus(issue_types, diagnostics))
    recovery_summary = _supabase_recovery_summary(
        status=status,
        issue_types=issue_types,
        next_required_action=next_required_action,
        operator_focus=operator_focus,
        blocking_checks=blocking_checks,
        diagnostics=diagnostics,
        runtime_fallbacks=runtime_fallbacks,
    )
    recovery_bundle = "\n\n".join(
        [
            "# getdaytrends Supabase recovery bundle",
            "## Next required action\n" + next_required_action,
            "## Operator focus\n" + operator_focus,
            "## Current blocker summary\n" + recovery_summary,
            "## Evidence freshness\n" + evidence_freshness_summary,
            "## Launch success criteria\n"
            + "\n".join(f"{index}. {item}" for index, item in enumerate(launch_success_criteria, 1)),
            "## Env template\n" + env_template,
            "## Connection mode facts\n"
            + "\n".join(f"{index}. {item}" for index, item in enumerate(SUPABASE_TRANSACTION_POOLER_FACTS, 1)),
            "## Scheduler pause commands\n" + scheduler_pause_command_bundle,
            "## Credential update commands\n" + credential_update_command_bundle,
            "## Recovery checklist\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(recovery_checklist, 1)),
            "## Post-credential recheck sequence\n"
            + _post_credential_recheck_section(post_credential_recheck_sequence),
            "## Post-credential evidence artifacts\n"
            + _post_credential_recheck_evidence_section(post_credential_recheck_evidence),
            "## Operator final proof bundle\n" + _operator_final_proof_bundle_section(operator_final_proof_bundle),
            "## Scheduler resume commands\n" + scheduler_resume_command_bundle,
            "## References\n" + _reference_links_section(reference_links),
            "## Verification commands\n" + verification_command_bundle,
        ]
    )
    return {
        "schema_version": 1,
        "status": status,
        "generated_at": generated_at,
        "readiness_report": readiness_report_path,
        "readiness_generated_at": readiness_generated_at,
        "readiness_status": readiness_payload.get("status"),
        "required_env": ["DATABASE_URL", "SUPABASE_URL"],
        "issue_types": issue_types,
        "live_db_failure_type": live_db_failure_type,
        "next_required_action": next_required_action,
        "operator_focus": operator_focus,
        "blocking_checks": blocking_checks,
        "source_checks": {
            "cli_smoke_report": {
                "ok": cli_check.get("ok"),
                "message": _mask_sensitive_text(str(cli_check.get("message", "")))[:420],
                "runtime_fallback_count": cli_evidence.get("runtime_fallback_count"),
                "runtime_fallback_kinds": runtime_fallback_kinds,
                "runtime_fallback_checks": runtime_fallback_checks,
            },
            "live_db_doctor": {
                "evaluated": live_db_evaluated,
                "ok": live_check.get("ok") if live_db_evaluated else None,
                "message": _mask_sensitive_text(str(live_check.get("message", "")))[:420],
                "failure_type": live_db_failure_type,
                "remediation": _mask_sensitive_text(str(live_check.get("remediation", "")))[:900],
            },
            "pooler_runtime_compatibility": {
                "evaluated": bool(pooler_compat_check),
                "ok": pooler_compat_check.get("ok") if pooler_compat_check else None,
                "message": _mask_sensitive_text(str(pooler_compat_check.get("message", "")))[:420],
            },
        },
        "diagnostics": diagnostics,
        "runtime_fallbacks": runtime_fallbacks,
        "recovery_summary": recovery_summary,
        "evidence_freshness": evidence_freshness,
        "evidence_freshness_summary": evidence_freshness_summary,
        "launch_success_criteria": launch_success_criteria,
        "reference_links": reference_links,
        "connection_mode_facts": SUPABASE_TRANSACTION_POOLER_FACTS,
        "accepted_transaction_pooler_shapes": ACCEPTED_TRANSACTION_POOLER_SHAPES,
        "accepts_shared_supavisor_transaction_pooler": True,
        "accepts_dedicated_pgbouncer_transaction_pooler": True,
        "scheduler_task_names": list(GETDAYTRENDS_SCHEDULED_TASK_NAMES),
        "scheduler_pause_commands": scheduler_pause_commands,
        "scheduler_pause_command_bundle": scheduler_pause_command_bundle,
        "scheduler_resume_commands": scheduler_resume_commands,
        "scheduler_resume_command_bundle": scheduler_resume_command_bundle,
        "credential_update_commands": credential_update_commands,
        "credential_update_command_bundle": credential_update_command_bundle,
        "recovery_checklist": recovery_checklist,
        "post_credential_recheck_sequence": post_credential_recheck_sequence,
        "post_credential_recheck_evidence": post_credential_recheck_evidence,
        "operator_final_proof_bundle": operator_final_proof_bundle,
        "env_template": env_template,
        "recovery_bundle": recovery_bundle,
        "verification_commands": verification_commands,
        "verification_command_bundle": verification_command_bundle,
        "secret_hygiene": {
            "masked_postgres_urls": True,
            "masked_supabase_pooler_users": True,
            "contains_plaintext_secret_values": False,
        },
    }


def _process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _command_path_arg(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
        project_root = PROJECT_ROOT.resolve(strict=False)
        display = str(resolved.relative_to(project_root)) if resolved.is_relative_to(project_root) else str(path)
    except (OSError, ValueError):
        display = str(path)
    display = display.replace("/", "\\")
    if any(char.isspace() for char in display):
        return '"' + display.replace('"', '`"') + '"'
    return display


def _packet_verifier_command(base_command: str, packet_report: Path | None) -> str:
    if packet_report is None:
        return base_command
    return f"{base_command} --packet-report {_command_path_arg(packet_report)}"


def _runtime_fallbacks(payload: dict[str, Any]) -> list[dict[str, str]]:
    reported_fallbacks = _masked_dict_list(payload.get("runtime_fallbacks"))
    if reported_fallbacks:
        return [
            {
                "check": str(item.get("check") or "unknown"),
                "stream": str(item.get("stream") or "unknown"),
                "kind": str(item.get("kind") or "unknown"),
                "snippet": str(item.get("snippet") or ""),
            }
            for item in reported_fallbacks
        ]

    results = payload.get("results")
    if not isinstance(results, list):
        return []

    fallbacks: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        check_name = str(result.get("name", "unknown"))
        for stream_name in ("stdout_tail", "stderr_tail"):
            value = result.get(stream_name)
            if not isinstance(value, str) or not value:
                continue
            lower_value = value.lower()
            for kind, needle in RUNTIME_FALLBACK_PATTERNS:
                if needle in lower_value:
                    key = (check_name, stream_name, kind)
                    if key in seen:
                        continue
                    seen.add(key)
                    fallbacks.append(
                        {
                            "check": check_name,
                            "stream": stream_name,
                            "kind": kind,
                            "snippet": _matching_line(value, needle),
                        }
                    )
    return fallbacks


def _runtime_fallback_remediation(fallbacks: list[dict[str, str]]) -> str:
    kinds = {fallback.get("kind", "") for fallback in fallbacks}
    if kinds == {"database.sqlite_fallback"}:
        return DATABASE_FALLBACK_REMEDIATION
    if kinds == {"cost_db.in_memory_fallback"}:
        return COST_DB_FALLBACK_REMEDIATION
    return RUNTIME_FALLBACK_REMEDIATION


def _provider_auth_failures_from_text(
    check_name: str,
    stream_name: str,
    value: str,
    seen: set[tuple[str, str, str]] | None = None,
) -> list[dict[str, str]]:
    if not value:
        return []

    failures: list[dict[str, str]] = []
    seen_keys = seen if seen is not None else set()
    lower_value = value.lower()
    for kind, needle in PROVIDER_AUTH_PATTERNS:
        if needle not in lower_value:
            continue
        key = (check_name, stream_name, kind)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        failures.append(
            {
                "check": check_name,
                "stream": stream_name,
                "kind": kind,
                "snippet": _mask_sensitive_text(_matching_line(value, needle)),
            }
        )
    return failures


def _provider_auth_failures(payload: dict[str, Any]) -> list[dict[str, str]]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    failures: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        check_name = str(result.get("name", "unknown"))
        for stream_name in ("stdout_tail", "stderr_tail"):
            value = result.get(stream_name)
            if not isinstance(value, str) or not value:
                continue
            failures.extend(_provider_auth_failures_from_text(check_name, stream_name, value, seen))
    return failures


def _provider_auth_failures_from_scheduler(scheduler_dir: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    evidence: dict[str, Any] = {"scheduler_dir": str(scheduler_dir)}
    latest = _latest_scheduler_artifact(scheduler_dir)
    if latest is None:
        evidence["scheduler_artifact"] = ""
        return [], evidence

    payload, error = _load_json(latest)
    evidence["scheduler_artifact"] = str(latest)
    if payload is None:
        evidence["scheduler_artifact_error"] = error
        return [], evidence

    candidates = [
        ("scheduler_detail_log", payload.get("detail_log")),
        ("scheduler_summary_log", payload.get("summary_log")),
        ("scheduler_summary_fallback_log", payload.get("summary_fallback_log")),
    ]
    for stream_name, path_value in candidates:
        if not path_value:
            continue
        candidate = Path(str(path_value))
        if not candidate.exists():
            continue
        evidence[stream_name] = str(candidate)
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            evidence[f"{stream_name}_error"] = f"{type(exc).__name__}: {exc}"
            continue
        failures = _provider_auth_failures_from_text("scheduler_artifact", stream_name, text)
        evidence["scheduler_provider_auth_scanned_log"] = str(candidate)
        return failures, evidence
    return [], evidence


def check_provider_auth_report(
    path: Path,
    *,
    max_age_hours: float | None = None,
    scheduler_dir: Path | None = None,
) -> EvidenceCheck:
    payload, error = _load_json(path)
    evidence = {"path": str(path)}
    if payload is None:
        return EvidenceCheck(
            "provider_auth_report",
            False,
            "ERROR",
            f"Provider auth evidence is not readable from CLI smoke report: {error}",
            evidence,
            CLI_SMOKE_REFRESH_COMMAND,
        )

    generated_at = payload.get("generated_at")
    age_hours = _age_hours(generated_at)
    freshness_ok = True
    freshness_message = ""
    if max_age_hours is not None:
        if age_hours is None:
            freshness_ok = False
            freshness_message = "Provider auth evidence has no parseable generated_at timestamp."
        elif age_hours > max_age_hours:
            freshness_ok = False
            freshness_message = f"Provider auth evidence is {age_hours}h old; max allowed is {max_age_hours}h."
    failures = _provider_auth_failures(payload)
    scheduler_evidence: dict[str, Any] = {}
    if scheduler_dir is not None:
        scheduler_failures, scheduler_evidence = _provider_auth_failures_from_scheduler(scheduler_dir)
        failures.extend(scheduler_failures)
    evidence.update(
        {
            "generated_at": generated_at,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "provider_auth_failure_count": len(failures),
            "provider_auth_failures": failures,
            **scheduler_evidence,
        }
    )
    ok = freshness_ok and not failures
    source_label = "CLI smoke and scheduler output" if scheduler_dir is not None else "CLI smoke output"
    return EvidenceCheck(
        "provider_auth_report",
        ok,
        "OK" if ok else "ERROR",
        f"No provider authentication failures found in {source_label}."
        if ok
        else (freshness_message or f"{source_label} contains {len(failures)} provider authentication failure signal(s)."),
        evidence,
        "" if ok else (CLI_SMOKE_REFRESH_COMMAND if freshness_message else PROVIDER_AUTH_REMEDIATION),
    )


def _provider_auth_issue_types(failures: list[dict[str, Any]]) -> list[str]:
    return sorted({str(failure.get("kind") or "provider.auth_failure") for failure in failures})


def _provider_auth_next_required_action(issue_types: list[str]) -> str:
    issue_set = set(issue_types)
    permission_or_billing = bool(
        issue_set.intersection({"provider.permission_denied", "provider.quota_or_billing"})
    )
    permission_billing_action = (
        "Confirm the provider project, organization, model access, and billing/credit limits before rerunning. "
    )
    if "provider.api_key_leaked" in issue_set:
        extra_action = permission_billing_action if permission_or_billing else ""
        return (
            "Revoke any leaked provider key immediately, create a fresh scoped key. "
            + extra_action
            + SAFE_PROVIDER_UPDATE_NEXT_ACTION
        )
    if permission_or_billing:
        return (
            "Rotate or correct the provider key. "
            + permission_billing_action
            + SAFE_PROVIDER_UPDATE_NEXT_ACTION
        )
    if issue_set:
        return (
            "Rotate or revoke the affected LLM provider key. " + SAFE_PROVIDER_UPDATE_NEXT_ACTION
        )
    return "No provider credential launch blocker is currently classified; run the final canonical workspace smoke before release."


def _provider_auth_recovery_env_template() -> str:
    return "\n".join(
        [
            "# getdaytrends LLM provider credential recovery template",
            "# Use fresh scoped keys only. Never reuse a key that was reported leaked, revoked, or permission denied.",
            "OPENAI_API_KEY=<rotated_openai_key_if_used>",
            "GOOGLE_API_KEY=<rotated_google_ai_key_if_used>",
            "# Update the production secret store with the same active provider key values.",
            "# After saving, run the copied verification command bundle from the dashboard.",
        ]
    )


def _provider_auth_recovery_summary(
    *,
    status: str,
    issue_types: list[str],
    next_required_action: str,
    blocking_checks: list[dict[str, str]],
    failures: list[dict[str, Any]],
) -> str:
    lines = [
        f"Status: {status}",
        "Issue types: " + (", ".join(issue_types) if issue_types else "-"),
    ]
    if next_required_action:
        lines.append(f"Next required action: {next_required_action}")
    if blocking_checks:
        lines.append("Blocking checks: " + ", ".join(str(check.get("name", "unknown")) for check in blocking_checks))
    lines.append(f"Provider auth failure count: {len(failures)}")
    if failures:
        lines.append("Provider auth failures:")
        for failure in failures[:8]:
            lines.append(
                "- "
                + " | ".join(
                    part
                    for part in (
                        str(failure.get("check", "")).strip(),
                        str(failure.get("stream", "")).strip(),
                        str(failure.get("kind", "")).strip(),
                        str(failure.get("snippet", "")).strip(),
                    )
                    if part
                )
            )
    return "\n".join(_mask_sensitive_text(line) for line in lines)


def build_provider_auth_recovery_packet(
    readiness_payload: dict[str, Any],
    *,
    readiness_report: Path | None = None,
    recovery_packet_report: Path | None = None,
) -> dict[str, Any]:
    checks_by_name = _check_by_name(readiness_payload)
    provider_check = checks_by_name.get("provider_auth_report", {})
    cli_check = checks_by_name.get("cli_smoke_report", {})
    provider_evidence = provider_check.get("evidence") if isinstance(provider_check.get("evidence"), dict) else {}
    failures = _masked_dict_list(provider_evidence.get("provider_auth_failures"))
    provider_auth_failure_count = provider_evidence.get("provider_auth_failure_count")
    if not isinstance(provider_auth_failure_count, int):
        provider_auth_failure_count = len(failures)
    provider_evaluated = bool(provider_check)
    issue_types = _provider_auth_issue_types(failures)
    blocking_checks = [
        {
            "name": str(check.get("name", "unknown_check")),
            "level": str(check.get("level", "ERROR")),
            "message": _mask_sensitive_text(str(check.get("message", "")))[:420],
        }
        for check in (provider_check,)
        if check and check.get("ok") is False and str(check.get("level", "ERROR")).upper() != "WARN"
    ]
    if issue_types:
        status = "blocked"
    elif provider_evaluated:
        status = "clear"
    else:
        status = "not_evaluated"
    generated_at = datetime.now().astimezone().isoformat()
    readiness_generated_at = str(readiness_payload.get("generated_at") or "")
    readiness_report_path = str(readiness_report or DEFAULT_REPORT)
    next_required_action = _mask_sensitive_text(_provider_auth_next_required_action(issue_types))
    recovery_checklist = [
        "Identify the provider named by the CLI smoke failure and disable the leaked, revoked, or denied key.",
        "Generate a fresh scoped provider key with access to the model used by getdaytrends.",
        "Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY in the local shell; do not paste provider keys into command arguments.",
        f"Dry-run validate the provider key update with {SAFE_PROVIDER_UPDATE_VALIDATE_COMMAND}.",
        f"Apply the provider key locally with {SAFE_PROVIDER_UPDATE_WRITE_COMMAND}.",
        "Update the production secret store with the same active provider key values; keep local and deployed values aligned.",
        "Confirm provider project, billing, organization, and model permissions if the failure is permission denied.",
        f"Rerun {CLI_SMOKE_REFRESH_COMMAND} and confirm provider_auth_failure_count is 0.",
        f"Rerun {STRICT_READINESS_REFRESH_COMMAND} and confirm readiness status is pass.",
        f"Rerun {CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND} and confirm all configured checks pass.",
    ]
    verification_commands = [
        CLI_SMOKE_REFRESH_COMMAND,
        BROWSER_SMOKE_REFRESH_COMMAND,
        STRICT_READINESS_REFRESH_COMMAND,
        _packet_verifier_command(PROVIDER_AUTH_RECOVERY_PACKET_VERIFY_COMMAND, recovery_packet_report),
        CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
    ]
    project_root_literal = str(PROJECT_ROOT).replace("'", "''")
    verification_command_bundle = "\n".join(
        [
            f"Set-Location -LiteralPath '{project_root_literal}'",
            *verification_commands,
        ]
    )
    launch_success_criteria = [
        "Provider auth report shows provider_auth_failure_count 0.",
        "CLI smoke passes without leaked-key, invalid-key, permission-denied, or authentication failure output.",
        "Strict readiness reports status pass.",
        CANONICAL_WORKSPACE_SMOKE_SUCCESS_CRITERION,
    ]
    reference_links = [OPENAI_API_KEY_REFERENCE, GOOGLE_AI_API_KEY_REFERENCE]
    evidence_freshness = {
        "packet_generated_at": generated_at,
        "readiness_generated_at": readiness_generated_at,
        "readiness_report": readiness_report_path,
    }
    evidence_freshness_summary = "\n".join(
        [
            f"Packet generated: {generated_at}",
            f"Readiness generated: {readiness_generated_at or 'unknown'}",
            f"Readiness report: {readiness_report_path}",
        ]
    )
    env_template = _provider_auth_recovery_env_template()
    recovery_summary = _provider_auth_recovery_summary(
        status=status,
        issue_types=issue_types,
        next_required_action=next_required_action,
        blocking_checks=blocking_checks,
        failures=failures,
    )
    recovery_bundle = "\n\n".join(
        [
            "# getdaytrends provider credential recovery bundle",
            "## Next required action\n" + next_required_action,
            "## Current blocker summary\n" + recovery_summary,
            "## Evidence freshness\n" + evidence_freshness_summary,
            "## Launch success criteria\n"
            + "\n".join(f"{index}. {item}" for index, item in enumerate(launch_success_criteria, 1)),
            "## Env template\n" + env_template,
            "## Recovery checklist\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(recovery_checklist, 1)),
            "## References\n" + _reference_links_section(reference_links),
            "## Verification commands\n" + verification_command_bundle,
        ]
    )
    return {
        "schema_version": 1,
        "status": status,
        "generated_at": generated_at,
        "readiness_report": readiness_report_path,
        "readiness_generated_at": readiness_generated_at,
        "readiness_status": readiness_payload.get("status"),
        "required_env": ["OPENAI_API_KEY", "GOOGLE_API_KEY"],
        "issue_types": issue_types,
        "provider_auth_failure_count": provider_auth_failure_count,
        "next_required_action": next_required_action,
        "blocking_checks": blocking_checks,
        "source_checks": {
            "provider_auth_report": {
                "evaluated": provider_evaluated,
                "ok": provider_check.get("ok") if provider_evaluated else None,
                "message": _mask_sensitive_text(str(provider_check.get("message", "")))[:420],
                "provider_auth_failure_count": provider_auth_failure_count,
            },
            "cli_smoke_report": {
                "ok": cli_check.get("ok"),
                "message": _mask_sensitive_text(str(cli_check.get("message", "")))[:420],
            },
        },
        "provider_auth_failures": failures,
        "recovery_summary": recovery_summary,
        "evidence_freshness": evidence_freshness,
        "evidence_freshness_summary": evidence_freshness_summary,
        "launch_success_criteria": launch_success_criteria,
        "reference_links": reference_links,
        "recovery_checklist": recovery_checklist,
        "env_template": env_template,
        "recovery_bundle": recovery_bundle,
        "verification_commands": verification_commands,
        "verification_command_bundle": verification_command_bundle,
        "secret_hygiene": {
            "masked_openai_keys": True,
            "masked_google_api_keys": True,
            "contains_plaintext_secret_values": False,
        },
    }


def check_smoke_report(
    path: Path,
    *,
    max_age_hours: float | None = None,
    fail_on_runtime_fallback: bool = False,
) -> EvidenceCheck:
    payload, error = _load_json(path)
    evidence = {"path": str(path)}
    if payload is None:
        return EvidenceCheck(
            "cli_smoke_report",
            False,
            "ERROR",
            f"CLI smoke report is not readable: {error}",
            evidence,
            CLI_SMOKE_REFRESH_COMMAND,
        )

    summary = _json_summary(payload)
    generated_at = payload.get("generated_at")
    age_hours = _age_hours(generated_at)
    runtime_fallbacks = _runtime_fallbacks(payload)
    freshness_ok = True
    freshness_message = ""
    if max_age_hours is not None:
        if age_hours is None:
            freshness_ok = False
            freshness_message = "CLI smoke report has no parseable generated_at timestamp."
        elif age_hours > max_age_hours:
            freshness_ok = False
            freshness_message = f"CLI smoke report is {age_hours}h old; max allowed is {max_age_hours}h."
    evidence.update(
        {
            "status": payload.get("status"),
            "schema_version": payload.get("schema_version"),
            "generated_at": generated_at,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "summary": summary,
            "fail_on_runtime_fallback": fail_on_runtime_fallback,
            "runtime_fallback_count": len(runtime_fallbacks),
            "runtime_fallbacks": runtime_fallbacks,
        }
    )
    fallback_ok = not (fail_on_runtime_fallback and runtime_fallbacks)
    ok = (
        payload.get("status") == "pass"
        and int(summary.get("failed", 0) or 0) == 0
        and freshness_ok
        and fallback_ok
    )
    fallback_message = ""
    if fail_on_runtime_fallback and runtime_fallbacks:
        fallback_message = f"CLI smoke passed with {len(runtime_fallbacks)} runtime fallback signal(s)."
    return EvidenceCheck(
        "cli_smoke_report",
        ok,
        "OK" if ok else "ERROR",
        "CLI smoke report is passing."
        if ok
        else (freshness_message or fallback_message or "CLI smoke report is failing or incomplete."),
        evidence,
        "" if ok else (_runtime_fallback_remediation(runtime_fallbacks) if fallback_message else CLI_SMOKE_REFRESH_COMMAND),
    )


def check_live_db_doctor(
    *,
    python_exe: str | None = None,
    timeout_seconds: int = 45,
) -> EvidenceCheck:
    command = [python_exe or sys.executable, "main.py", "--doctor", "--require-live-db"]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    evidence: dict[str, Any] = {
        "command": LIVE_DB_DOCTOR_COMMAND,
        "cwd": str(PROJECT_ROOT),
        "timeout_seconds": timeout_seconds,
    }
    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        output = _mask_sensitive_text(_process_text(exc.stdout) + "\n" + _process_text(exc.stderr))
        evidence.update(
            {
                "timeout": True,
                "failure_type": "timeout",
                "diagnostics": _doctor_diagnostic_lines(output),
                "output_tail": output[-1200:],
            }
        )
        return EvidenceCheck(
            "live_db_doctor",
            False,
            "ERROR",
            f"Live DB doctor timed out after {timeout_seconds}s.",
            evidence,
            LIVE_DB_DOCTOR_REMEDIATION,
        )
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        evidence["failure_type"] = "execution_error"
        return EvidenceCheck(
            "live_db_doctor",
            False,
            "ERROR",
            "Live DB doctor could not be executed.",
            evidence,
            LIVE_DB_DOCTOR_REMEDIATION,
        )

    stdout = _mask_sensitive_text(completed.stdout or "")
    stderr = _mask_sensitive_text(completed.stderr or "")
    combined_output = f"{stdout}\n{stderr}".strip()
    diagnostics = _doctor_diagnostic_lines(combined_output)
    evidence.update(
        {
            "exit_code": completed.returncode,
            "diagnostics": diagnostics,
            "stdout_tail": stdout[-1200:],
            "stderr_tail": stderr[-1200:],
        }
    )
    ok = completed.returncode == 0
    failure_detail = _doctor_failure_detail(diagnostics)
    failure_message = f"Live DB doctor failed. {failure_detail}".strip()
    if not ok:
        evidence["failure_type"] = _live_db_failure_type({"message": failure_message}, evidence)
    return EvidenceCheck(
        "live_db_doctor",
        ok,
        "OK" if ok else "ERROR",
        "Live DB doctor passed." if ok else failure_message,
        evidence,
        "" if ok else _live_db_doctor_remediation(diagnostics),
    )


def check_hygiene_report(path: Path) -> EvidenceCheck:
    payload, error = _load_json(path)
    evidence = {"path": str(path)}
    if payload is None:
        return EvidenceCheck(
            "text_hygiene_report",
            False,
            "ERROR",
            f"Text hygiene report is not readable: {error}",
            evidence,
            "Run python scripts\\check_text_hygiene.py from automation\\getdaytrends.",
        )

    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    read_errors = payload.get("read_errors") if isinstance(payload.get("read_errors"), list) else []
    evidence.update(
        {
            "status": payload.get("status"),
            "schema_version": payload.get("schema_version"),
            "summary": payload.get("summary", {}),
            "findings": len(findings),
            "read_errors": len(read_errors),
        }
    )
    ok = payload.get("status") == "pass" and not findings and not read_errors
    return EvidenceCheck(
        "text_hygiene_report",
        ok,
        "OK" if ok else "ERROR",
        "Production docs are clean." if ok else "Production docs have hygiene findings.",
        evidence,
        "" if ok else "Fix the reported docs and rerun python scripts\\check_text_hygiene.py.",
    )


def check_browser_report(path: Path, *, required: bool, max_age_hours: float | None = None) -> EvidenceCheck:
    payload, error = _load_json(path)
    evidence = {"path": str(path)}
    if payload is None:
        return EvidenceCheck(
            "dashboard_browser_report",
            False,
            "ERROR" if required else "WARN",
            f"Dashboard browser smoke report is not readable: {error}",
            evidence,
            BROWSER_SMOKE_REFRESH_COMMAND,
        )

    summary = _json_summary(payload)
    screenshot = _resolve_project_artifact_path(payload.get("screenshot", ""), relative_to=path)
    generated_at = payload.get("generated_at")
    age_hours = _age_hours(generated_at)
    freshness_ok = True
    freshness_message = ""
    if max_age_hours is not None:
        if age_hours is None:
            freshness_ok = False
            freshness_message = "Dashboard browser smoke report has no parseable generated_at timestamp."
        elif age_hours > max_age_hours:
            freshness_ok = False
            freshness_message = f"Dashboard browser smoke report is {age_hours}h old; max allowed is {max_age_hours}h."
    evidence.update(
        {
            "status": payload.get("status"),
            "schema_version": payload.get("schema_version"),
            "generated_at": generated_at,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "summary": summary,
            "screenshot": str(screenshot),
            "screenshot_exists": screenshot.exists(),
        }
    )
    ok = payload.get("status") == "pass" and int(summary.get("failed", 0) or 0) == 0 and screenshot.exists() and freshness_ok
    return EvidenceCheck(
        "dashboard_browser_report",
        ok,
        "OK" if ok else ("ERROR" if required else "WARN"),
        "Dashboard browser smoke is passing."
        if ok
        else (freshness_message or "Dashboard browser smoke is missing or failing."),
        evidence,
        "" if ok else BROWSER_SMOKE_REFRESH_COMMAND,
    )


def check_tap_fixture_browser_report(path: Path, *, required: bool, max_age_hours: float | None = None) -> EvidenceCheck:
    payload, error = _load_json(path)
    evidence: dict[str, Any] = {"path": str(path)}
    if payload is None:
        return EvidenceCheck(
            "tap_fixture_browser_report",
            False,
            "ERROR" if required else "WARN",
            f"TAP fixture browser smoke report is not readable: {error}",
            evidence,
            TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
        )

    summary = _json_summary(payload)
    screenshot = _resolve_project_artifact_path(payload.get("screenshot", ""), relative_to=path)
    generated_at = payload.get("generated_at")
    age_hours = _age_hours(generated_at)
    freshness_ok = True
    freshness_message = ""
    if max_age_hours is not None:
        if age_hours is None:
            freshness_ok = False
            freshness_message = "TAP fixture browser smoke report has no parseable generated_at timestamp."
        elif age_hours > max_age_hours:
            freshness_ok = False
            freshness_message = f"TAP fixture browser smoke report is {age_hours}h old; max allowed is {max_age_hours}h."
    mode = payload.get("mode") if isinstance(payload.get("mode"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    checks_by_name = {
        str(check.get("name", "")): check
        for check in checks
        if isinstance(check, dict) and str(check.get("name", "")).strip()
    }
    missing_required = [name for name in REQUIRED_TAP_FIXTURE_CHECKS if name not in checks_by_name]
    failed_required = [
        name for name in REQUIRED_TAP_FIXTURE_CHECKS if isinstance(checks_by_name.get(name), dict) and checks_by_name[name].get("ok") is not True
    ]
    evidence.update(
        {
            "status": payload.get("status"),
            "schema_version": payload.get("schema_version"),
            "generated_at": generated_at,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "summary": summary,
            "screenshot": str(screenshot),
            "screenshot_exists": screenshot.exists(),
            "mode": mode,
            "required_checks": list(REQUIRED_TAP_FIXTURE_CHECKS),
            "missing_required_checks": missing_required,
            "failed_required_checks": failed_required,
        }
    )
    ok = (
        payload.get("status") == "pass"
        and int(summary.get("failed", 0) or 0) == 0
        and screenshot.exists()
        and mode.get("tap_source_fixture") is True
        and not missing_required
        and not failed_required
        and freshness_ok
    )
    return EvidenceCheck(
        "tap_fixture_browser_report",
        ok,
        "OK" if ok else ("ERROR" if required else "WARN"),
        "TAP fixture browser smoke is passing."
        if ok
        else (
            freshness_message
            or "TAP fixture browser smoke is missing, failing, or lacks required source/degraded-endpoint checks."
        ),
        evidence,
        "" if ok else TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
    )


def _latest_scheduler_artifact(scheduler_dir: Path) -> Path | None:
    candidates = [path for path in scheduler_dir.glob("run_*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=_scheduler_artifact_recency_key)


def _scheduler_artifact_recency_key(path: Path) -> tuple[int, float, int, float, float]:
    payload_ts = _scheduler_artifact_payload_timestamp(path)
    filename_ts = _scheduler_artifact_filename_timestamp(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (
        1 if payload_ts is not None else 0,
        payload_ts if payload_ts is not None else float("-inf"),
        1 if filename_ts is not None else 0,
        filename_ts if filename_ts is not None else float("-inf"),
        mtime,
    )


def _scheduler_artifact_payload_timestamp(path: Path) -> float | None:
    payload, _error = _load_json(path)
    if not isinstance(payload, dict):
        return None
    for field in ("finished_at", "ended_at", "started_at", "generated_at"):
        parsed = _parse_iso_datetime(payload.get(field))
        if parsed is not None:
            return parsed.timestamp()
    return None


def _scheduler_artifact_filename_timestamp(path: Path) -> float | None:
    match = re.fullmatch(r"run_(\d{4}-\d{2}-\d{2})_(\d{6})\.json", path.name)
    if not match:
        return None
    try:
        parsed = datetime.strptime(" ".join(match.groups()), "%Y-%m-%d %H%M%S")
    except ValueError:
        return None
    return parsed.timestamp()


def _json_artifact_recency_key(path: Path) -> tuple[int, int, float, float]:
    payload, _ = _load_json(path)
    generated_dt = _parse_iso_datetime(payload.get("generated_at") if isinstance(payload, dict) else "")
    generated_ts = generated_dt.timestamp() if generated_dt is not None else float("-inf")
    summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}
    pass_rank = (
        1
        if isinstance(payload, dict)
        and payload.get("status") == "pass"
        and int(summary.get("failed", 0) or 0) == 0
        else 0
    )
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (pass_rank, 1 if generated_dt is not None else 0, generated_ts, mtime)


def _latest_dashboard_browser_report(smoke_dir: Path) -> Path:
    candidates = [
        path
        for path in smoke_dir.glob("dashboard_browser*.json")
        if path.is_file() and "tap_source" not in path.name
    ]
    if not candidates:
        return DEFAULT_BROWSER_REPORT
    return max(candidates, key=_json_artifact_recency_key)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_hours(value: Any) -> float | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    return round(max((now - parsed).total_seconds(), 0) / 3600, 2)


def _workspace_root() -> Path:
    if PROJECT_ROOT.parent.name.lower() == "automation":
        return PROJECT_ROOT.parent.parent
    return PROJECT_ROOT.parent


def _resolve_project_artifact_path(value: Any, *, relative_to: Path | None = None) -> Path:
    raw_path = str(value or "").strip()
    if not raw_path:
        return Path("")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    candidates = []
    if relative_to is not None:
        candidates.append(relative_to.parent / candidate)
    candidates.extend([PROJECT_ROOT / candidate, _workspace_root() / candidate])
    for path in candidates:
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return candidates[0] if candidates else candidate


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        return path.resolve(strict=False).is_relative_to(parent.resolve(strict=False))
    except OSError:
        return False


def _path_matches(path_value: Any, expected: Path) -> bool:
    if not isinstance(path_value, str) or not path_value.strip():
        return False
    try:
        return Path(path_value).resolve(strict=False) == expected.resolve(strict=False)
    except OSError:
        return False


def check_scheduler_artifact(
    scheduler_dir: Path,
    *,
    required: bool,
    max_age_hours: float | None = None,
) -> EvidenceCheck:
    latest = _latest_scheduler_artifact(scheduler_dir)
    evidence: dict[str, Any] = {"scheduler_dir": str(scheduler_dir)}
    if latest is None:
        return EvidenceCheck(
            "scheduler_artifact",
            False,
            "WARN" if not required else "ERROR",
            "No scheduler artifact found.",
            evidence,
            SCHEDULER_REFRESH_COMMAND,
        )

    payload, error = _load_json(latest)
    evidence["path"] = str(latest)
    if payload is None:
        return EvidenceCheck(
            "scheduler_artifact",
            False,
            "ERROR",
            f"Latest scheduler artifact is not readable: {error}",
            evidence,
            "Rerun the scheduler wrapper and inspect logs\\scheduler.",
        )

    detail_log = Path(str(payload.get("detail_log", "")))
    summary_log = Path(str(payload.get("summary_log", "")))
    summary_fallback_log = Path(str(payload.get("summary_fallback_log", "")))
    artifact_path = payload.get("artifact_path")
    artifact_path_present = isinstance(artifact_path, str) and bool(artifact_path.strip())
    artifact_path_matches_latest = _path_matches(artifact_path, latest)
    summary_fallback_used = payload.get("summary_fallback_used")
    summary_fallback_used_present = "summary_fallback_used" in payload
    summary_fallback_used_valid = not summary_fallback_used_present or isinstance(summary_fallback_used, bool)
    primary_summary_exists = summary_log.exists()
    summary_fallback_exists = summary_fallback_log.exists()
    summary_exists = primary_summary_exists or summary_fallback_exists
    detail_exists = detail_log.exists()
    detail_log_contained = detail_exists and _path_is_within(detail_log, scheduler_dir)
    primary_summary_log_contained = primary_summary_exists and _path_is_within(summary_log, scheduler_dir)
    summary_fallback_log_contained = summary_fallback_exists and _path_is_within(summary_fallback_log, scheduler_dir)
    summary_log_contained = primary_summary_log_contained or summary_fallback_log_contained
    started_at = payload.get("started_at")
    finished_at = payload.get("finished_at")
    started_dt = _parse_iso_datetime(started_at)
    finished_dt = _parse_iso_datetime(finished_at)
    timestamp_window_ok = started_dt is not None and finished_dt is not None and finished_dt >= started_dt
    timestamp = finished_at or started_at
    age_hours = _age_hours(timestamp)
    duration_seconds = payload.get("duration_seconds")
    duration_ok = (
        isinstance(duration_seconds, int | float) and not isinstance(duration_seconds, bool) and duration_seconds >= 0
    )
    pipeline_errors = payload.get("errors")
    pipeline_errors_ok = not isinstance(pipeline_errors, int) or pipeline_errors == 0
    freshness_ok = True
    freshness_message = ""
    if max_age_hours is not None:
        if age_hours is None:
            freshness_ok = False
            freshness_message = "Latest scheduler artifact has no parseable timestamp."
        elif age_hours > max_age_hours:
            freshness_ok = False
            freshness_message = f"Latest scheduler artifact is {age_hours}h old; max allowed is {max_age_hours}h."

    ok = (
        payload.get("status") == "success"
        and payload.get("exit_code") == 0
        and duration_ok
        and timestamp_window_ok
        and detail_exists
        and summary_exists
        and detail_log_contained
        and pipeline_errors_ok
        and freshness_ok
    )
    evidence.update(
        {
            "status": payload.get("status"),
            "exit_code": payload.get("exit_code"),
            "duration_seconds": duration_seconds,
            "duration_seconds_valid": duration_ok,
            "started_at": started_at,
            "finished_at": finished_at,
            "started_at_valid": started_dt is not None,
            "finished_at_valid": finished_dt is not None,
            "timestamp_window_valid": timestamp_window_ok,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "project_root": payload.get("project_root"),
            "python": payload.get("python"),
            "command": payload.get("command"),
            "artifact_path": artifact_path,
            "artifact_path_present": artifact_path_present,
            "artifact_path_matches_latest": artifact_path_matches_latest,
            "detail_log": payload.get("detail_log"),
            "summary_log": payload.get("summary_log"),
            "summary_fallback_log": payload.get("summary_fallback_log"),
            "summary_fallback_used": summary_fallback_used,
            "summary_fallback_used_present": summary_fallback_used_present,
            "summary_fallback_used_valid": summary_fallback_used_valid,
            "detail_log_exists": detail_exists,
            "summary_log_exists": summary_exists,
            "detail_log_contained": detail_log_contained,
            "summary_log_contained": summary_log_contained,
            "primary_summary_log_contained": primary_summary_log_contained,
            "summary_fallback_log_contained": summary_fallback_log_contained,
            "primary_summary_log_exists": primary_summary_exists,
            "summary_fallback_log_exists": summary_fallback_exists,
            "country": payload.get("country"),
            "limit": payload.get("limit"),
            "dry_run": payload.get("dry_run"),
            "generated": payload.get("generated"),
            "saved": payload.get("saved"),
            "errors": pipeline_errors,
        }
    )
    if freshness_message:
        failure_message = freshness_message
    elif not duration_ok:
        failure_message = "Latest scheduler artifact has missing or invalid duration_seconds."
    elif not timestamp_window_ok:
        failure_message = "Latest scheduler artifact has missing, invalid, or reversed started_at/finished_at timestamps."
    elif detail_exists and not detail_log_contained:
        failure_message = "Latest scheduler artifact detail log points outside the scheduler log directory."
    elif not pipeline_errors_ok:
        failure_message = f"Latest scheduler artifact completed with pipeline errors={pipeline_errors}."
    else:
        failure_message = "Latest scheduler artifact is missing success status or log evidence."
    return EvidenceCheck(
        "scheduler_artifact",
        ok,
        "OK" if ok else ("ERROR" if required else "WARN"),
        "Latest scheduler artifact is successful and has matching logs."
        if ok
        else failure_message,
        evidence,
        "" if ok else SCHEDULER_REFRESH_COMMAND,
    )


def check_docs(paths: tuple[Path, ...] = REQUIRED_DOCS) -> EvidenceCheck:
    missing = [str(path) for path in paths if not path.exists()]
    unreadable: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            path.read_text(encoding="utf-8")
        except Exception as exc:
            unreadable.append(f"{path}: {type(exc).__name__}: {exc}")
    ok = not missing and not unreadable
    return EvidenceCheck(
        "production_docs",
        ok,
        "OK" if ok else "ERROR",
        "Production and GitHub benchmark docs are present." if ok else "Production docs are missing or unreadable.",
        {"checked_files": [str(path) for path in paths], "missing": missing, "unreadable": unreadable},
        "" if ok else "Restore the missing docs and rerun the text hygiene gate.",
    )


def check_pooler_runtime_compatibility(
    paths: tuple[Path, ...] = POOLER_RUNTIME_COMPATIBILITY_FILES,
) -> EvidenceCheck:
    checked_files: list[dict[str, Any]] = []
    missing: list[str] = []
    missing_statement_cache_disable: list[str] = []
    unreadable: list[str] = []
    for path in paths:
        record: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
            "statement_cache_size_zero": False,
        }
        if not path.exists():
            missing.append(str(path))
            checked_files.append(record)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            unreadable.append(f"{path}: {type(exc).__name__}: {exc}")
            record["read_error"] = f"{type(exc).__name__}: {exc}"
            checked_files.append(record)
            continue
        statement_cache_disabled = ASYNC_PG_STATEMENT_CACHE_DISABLED_RE.search(text) is not None
        record["statement_cache_size_zero"] = statement_cache_disabled
        if not statement_cache_disabled:
            missing_statement_cache_disable.append(str(path))
        checked_files.append(record)

    ok = not missing and not unreadable and not missing_statement_cache_disable
    evidence = {
        "checked_files": checked_files,
        "missing": missing,
        "unreadable": unreadable,
        "missing_statement_cache_disable": missing_statement_cache_disable,
        "required_marker": "statement_cache_size=0",
        "reference": SUPABASE_CONNECTION_REFERENCE,
    }
    return EvidenceCheck(
        "pooler_runtime_compatibility",
        ok,
        "OK" if ok else "ERROR",
        "Transaction pooler runtime compatibility is configured."
        if ok
        else "Transaction pooler runtime compatibility is missing prepared-statement disable evidence.",
        evidence,
        ""
        if ok
        else (
            "Keep asyncpg transaction-pooler paths configured with statement_cache_size=0 before launch; "
            "Supabase transaction mode does not support prepared statements. "
            f"Reference: {SUPABASE_CONNECTION_REFERENCE['url']}"
        ),
    )


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _replace_report_with_retry(temp_path, path)


def _replace_report_with_retry(temp_path: Path, path: Path, *, attempts: int = 6, delay_seconds: float = 0.2) -> None:
    for attempt in range(attempts):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_seconds)


def _default_recovery_packet_path(report_path: Path) -> Path:
    try:
        if report_path.resolve() == DEFAULT_REPORT.resolve():
            return DEFAULT_SUPABASE_RECOVERY_PACKET
    except OSError:
        pass
    return report_path.with_name(f"{report_path.stem}_supabase_recovery_packet.json")


def _default_provider_auth_recovery_packet_path(report_path: Path) -> Path:
    try:
        if report_path.resolve() == DEFAULT_REPORT.resolve():
            return DEFAULT_PROVIDER_AUTH_RECOVERY_PACKET
    except OSError:
        pass
    return report_path.with_name(f"{report_path.stem}_provider_auth_recovery_packet.json")


def _strict_readiness_sidecar_required(report_path: Path, payload: dict[str, Any]) -> bool:
    try:
        if report_path.resolve() != DEFAULT_REPORT.resolve():
            return False
    except OSError:
        return False
    requirements = payload.get("requirements") if isinstance(payload.get("requirements"), dict) else {}
    return all(
        (
            requirements.get("require_browser") is True,
            requirements.get("require_tap_fixture_browser") is True,
            requirements.get("require_scheduler") is True,
            requirements.get("fail_on_runtime_fallback") is True,
            requirements.get("require_live_db") is True,
            requirements.get("max_cli_smoke_age_hours") is not None,
            requirements.get("max_browser_smoke_age_hours") is not None,
            requirements.get("max_scheduler_age_hours") is not None,
        )
    )


def _strict_readiness_sidecar_payload(
    payload: dict[str, Any],
    *,
    include_supabase_packet: bool,
    include_provider_auth_packet: bool,
) -> dict[str, Any]:
    sidecar_payload = dict(payload)
    artifacts = dict(payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {})
    if include_supabase_packet:
        artifacts["supabase_recovery_packet"] = str(DEFAULT_STRICT_SUPABASE_RECOVERY_PACKET)
    if include_provider_auth_packet:
        artifacts["provider_auth_recovery_packet"] = str(DEFAULT_STRICT_PROVIDER_AUTH_RECOVERY_PACKET)
    if artifacts:
        sidecar_payload["artifacts"] = artifacts
    return sidecar_payload


def _write_strict_readiness_sidecar(
    payload: dict[str, Any],
    *,
    include_supabase_packet: bool,
    include_provider_auth_packet: bool,
) -> None:
    sidecar_payload = _strict_readiness_sidecar_payload(
        payload,
        include_supabase_packet=include_supabase_packet,
        include_provider_auth_packet=include_provider_auth_packet,
    )
    if include_supabase_packet:
        packet = build_supabase_recovery_packet(
            sidecar_payload,
            readiness_report=DEFAULT_STRICT_REPORT,
            recovery_packet_report=DEFAULT_STRICT_SUPABASE_RECOVERY_PACKET,
        )
        _write_report(DEFAULT_STRICT_SUPABASE_RECOVERY_PACKET, packet)
    if include_provider_auth_packet:
        provider_packet = build_provider_auth_recovery_packet(
            sidecar_payload,
            readiness_report=DEFAULT_STRICT_REPORT,
            recovery_packet_report=DEFAULT_STRICT_PROVIDER_AUTH_RECOVERY_PACKET,
        )
        _write_report(DEFAULT_STRICT_PROVIDER_AUTH_RECOVERY_PACKET, provider_packet)
    _write_report(DEFAULT_STRICT_REPORT, sidecar_payload)


def run_readiness(
    *,
    smoke_report: Path,
    browser_report: Path,
    hygiene_report: Path,
    scheduler_dir: Path,
    report_path: Path,
    require_browser: bool,
    require_scheduler: bool,
    recovery_packet_report: Path | None = None,
    provider_auth_recovery_packet_report: Path | None = None,
    tap_fixture_browser_report: Path | None = None,
    require_tap_fixture_browser: bool = True,
    max_cli_smoke_age_hours: float | None = None,
    max_browser_smoke_age_hours: float | None = None,
    max_scheduler_age_hours: float | None = None,
    fail_on_runtime_fallback: bool = False,
    require_live_db: bool = False,
) -> dict[str, Any]:
    checks = [
        check_smoke_report(
            smoke_report,
            max_age_hours=max_cli_smoke_age_hours,
            fail_on_runtime_fallback=fail_on_runtime_fallback,
        ),
        check_provider_auth_report(
            smoke_report,
            max_age_hours=max_cli_smoke_age_hours,
            scheduler_dir=scheduler_dir,
        ),
        check_browser_report(browser_report, required=require_browser, max_age_hours=max_browser_smoke_age_hours),
        check_hygiene_report(hygiene_report),
        check_scheduler_artifact(
            scheduler_dir,
            required=require_scheduler,
            max_age_hours=max_scheduler_age_hours,
        ),
        check_pooler_runtime_compatibility(),
        check_docs(),
    ]
    if tap_fixture_browser_report is not None:
        checks.insert(
            2,
            check_tap_fixture_browser_report(
                tap_fixture_browser_report,
                required=require_tap_fixture_browser,
                max_age_hours=max_browser_smoke_age_hours,
            ),
        )
    if require_live_db:
        checks.append(check_live_db_doctor())
    blocking_checks = [check for check in checks if check.level != "WARN"]
    failed = [check for check in blocking_checks if not check.ok]
    warnings = [check for check in checks if check.level == "WARN" and not check.ok]
    payload = {
        "schema_version": 1,
        "status": "pass" if not failed else "fail",
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "requirements": {
            "require_browser": require_browser,
            "require_tap_fixture_browser": require_tap_fixture_browser,
            "require_scheduler": require_scheduler,
            "fail_on_runtime_fallback": fail_on_runtime_fallback,
            "require_live_db": require_live_db,
            "max_cli_smoke_age_hours": max_cli_smoke_age_hours,
            "max_browser_smoke_age_hours": max_browser_smoke_age_hours,
            "max_scheduler_age_hours": max_scheduler_age_hours,
        },
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check.ok),
            "failed": len(failed),
            "warnings": len(warnings),
        },
        "checks": [check.to_dict() for check in checks],
    }
    artifacts: dict[str, str] = {}
    if recovery_packet_report is not None:
        artifacts["supabase_recovery_packet"] = str(recovery_packet_report)
    if provider_auth_recovery_packet_report is not None:
        artifacts["provider_auth_recovery_packet"] = str(provider_auth_recovery_packet_report)
    if artifacts:
        payload["artifacts"] = artifacts
    if recovery_packet_report is not None:
        packet = build_supabase_recovery_packet(
            payload,
            readiness_report=report_path,
            recovery_packet_report=recovery_packet_report,
        )
        _write_report(recovery_packet_report, packet)
    if provider_auth_recovery_packet_report is not None:
        provider_packet = build_provider_auth_recovery_packet(
            payload,
            readiness_report=report_path,
            recovery_packet_report=provider_auth_recovery_packet_report,
        )
        _write_report(provider_auth_recovery_packet_report, provider_packet)
    _write_report(report_path, payload)
    if _strict_readiness_sidecar_required(report_path, payload):
        _write_strict_readiness_sidecar(
            payload,
            include_supabase_packet=recovery_packet_report is not None,
            include_provider_auth_packet=provider_auth_recovery_packet_report is not None,
        )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check getdaytrends production readiness evidence.")
    parser.add_argument("--smoke-report", type=Path, default=DEFAULT_SMOKE_REPORT)
    parser.add_argument("--browser-report", type=Path, default=None)
    parser.add_argument("--tap-fixture-browser-report", type=Path, default=DEFAULT_TAP_FIXTURE_BROWSER_REPORT)
    parser.add_argument("--hygiene-report", type=Path, default=DEFAULT_HYGIENE_REPORT)
    parser.add_argument("--scheduler-dir", type=Path, default=DEFAULT_SCHEDULER_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--recovery-packet-report", type=Path, default=None)
    parser.add_argument("--provider-auth-recovery-packet-report", type=Path, default=None)
    parser.add_argument(
        "--no-recovery-packet",
        action="store_true",
        help="Do not write recovery packet artifacts for this readiness run.",
    )
    parser.add_argument(
        "--max-scheduler-age-hours",
        type=float,
        default=None,
        help="Fail required scheduler evidence when the latest artifact is older than this many hours.",
    )
    parser.add_argument(
        "--max-cli-smoke-age-hours",
        type=float,
        default=None,
        help="Fail CLI smoke evidence when the report is older than this many hours.",
    )
    parser.add_argument(
        "--max-browser-smoke-age-hours",
        type=float,
        default=None,
        help="Fail dashboard and TAP fixture browser evidence when reports are older than this many hours.",
    )
    parser.add_argument(
        "--fail-on-runtime-fallback",
        action="store_true",
        help="Fail launch readiness when CLI smoke only passes through database or cost-DB fallback.",
    )
    parser.add_argument(
        "--require-live-db",
        action="store_true",
        help="Run python main.py --doctor --require-live-db and fail launch readiness if the live DB preflight fails.",
    )
    parser.add_argument(
        "--no-require-scheduler",
        action="store_true",
        help="Downgrade missing scheduler evidence to a warning for developer-only checks.",
    )
    parser.add_argument(
        "--no-require-browser",
        action="store_true",
        help="Downgrade missing dashboard browser evidence to a warning for developer-only checks.",
    )
    parser.add_argument(
        "--no-require-tap-fixture-browser",
        action="store_true",
        help="Downgrade missing TAP fixture browser evidence to a warning for developer-only checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    recovery_packet_report = None
    provider_auth_recovery_packet_report = None
    if not args.no_recovery_packet:
        recovery_packet_report = args.recovery_packet_report or _default_recovery_packet_path(args.report)
        provider_auth_recovery_packet_report = (
            args.provider_auth_recovery_packet_report or _default_provider_auth_recovery_packet_path(args.report)
        )
    payload = run_readiness(
        smoke_report=args.smoke_report,
        browser_report=args.browser_report or _latest_dashboard_browser_report(DEFAULT_BROWSER_REPORT.parent),
        tap_fixture_browser_report=args.tap_fixture_browser_report,
        hygiene_report=args.hygiene_report,
        scheduler_dir=args.scheduler_dir,
        report_path=args.report,
        recovery_packet_report=recovery_packet_report,
        provider_auth_recovery_packet_report=provider_auth_recovery_packet_report,
        require_browser=not args.no_require_browser,
        require_tap_fixture_browser=not args.no_require_tap_fixture_browser,
        require_scheduler=not args.no_require_scheduler,
        max_cli_smoke_age_hours=args.max_cli_smoke_age_hours,
        max_browser_smoke_age_hours=args.max_browser_smoke_age_hours,
        max_scheduler_age_hours=args.max_scheduler_age_hours,
        fail_on_runtime_fallback=args.fail_on_runtime_fallback,
        require_live_db=args.require_live_db,
    )
    print(f"getdaytrends readiness: {payload['status']}")
    print(f"report: {args.report}")
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    if artifacts.get("supabase_recovery_packet"):
        print(f"supabase recovery packet: {artifacts['supabase_recovery_packet']}")
    if artifacts.get("provider_auth_recovery_packet"):
        print(f"provider auth recovery packet: {artifacts['provider_auth_recovery_packet']}")
    for check in payload["checks"]:
        marker = "OK" if check["ok"] else check["level"]
        print(f"{marker} {check['name']}: {check['message']}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
