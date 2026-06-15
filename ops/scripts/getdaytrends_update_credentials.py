from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from complete_goal_gate_common import (
    CURRENT_DATE_STAMP,
    WORKSPACE_ROOT,
    env_assignment_map,
    file_meta,
    fingerprint,
    redacted_windows_env_status,
    scoped_env_value,
    scoped_redacted_env_status,
    write_json,
)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_ENV_PATH = WORKSPACE_ROOT / ".env"
DEFAULT_LOCAL_ENV_PATH = WORKSPACE_ROOT / "automation" / "getdaytrends" / ".env"
DEFAULT_JSON_OUT = WORKSPACE_ROOT / "var" / f"getdaytrends-credential-input-status-current-{CURRENT_DATE_STAMP}.json"
DEFAULT_CURRENT_JSON_OUT = WORKSPACE_ROOT / "var" / "getdaytrends-credential-input-status-current.json"
REPORT_MONTH = CURRENT_DATE_STAMP[:7]
DEFAULT_MARKDOWN_OUT = (
    WORKSPACE_ROOT / "docs" / "reports" / REPORT_MONTH / f"AUTO_RESEARCH_GETDAYTRENDS_CREDENTIAL_INPUT_STATUS_{CURRENT_DATE_STAMP}.md"
)
POST_UPDATE_COMMAND = (
    "python ops/scripts/workspace_external_credential_recovery_refresh.py --execute --continue-on-failure "
    "--preflight-unblock-gate --allow-blocked-external "
    f"--json-out var/workspace-external-credential-recovery-refresh-current-full-matrix-{CURRENT_DATE_STAMP}.json "
    f"--markdown-out docs/reports/{REPORT_MONTH}/WORKSPACE_EXTERNAL_CREDENTIAL_RECOVERY_REFRESH_CURRENT_FULL_MATRIX_{CURRENT_DATE_STAMP}.md"
)
UPDATE_ENV_NAMES = (
    "GETDAYTRENDS_NEW_DATABASE_URL",
    "GETDAYTRENDS_NEW_SUPABASE_URL",
    "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
)
OPTIONAL_WRITE_ENV = {
    "GETDAYTRENDS_NEW_SUPABASE_URL": "SUPABASE_URL",
    "GETDAYTRENDS_NEW_OPENAI_API_KEY": "OPENAI_API_KEY",
    "GETDAYTRENDS_NEW_GOOGLE_API_KEY": "GOOGLE_API_KEY",
}
SCHEDULER_ARTIFACT_EVIDENCE_FIELDS = (
    "artifact_path_present",
    "artifact_path_matches_latest",
    "summary_fallback_used",
    "summary_fallback_used_present",
    "summary_fallback_used_valid",
)
PROJECT_REF_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ASSIGNMENT_RE = re.compile(r"^(?P<prefix>\s*(?:export\s+)?)(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*?)(?P<newline>\r?\n)?$")


@dataclass(frozen=True)
class Assignment:
    index: int
    prefix: str
    name: str
    raw_value: str
    newline: str


def _read_lines(path: Path) -> tuple[list[str], dict[str, Assignment]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        lines = []
    assignments: dict[str, Assignment] = {}
    for index, line in enumerate(lines):
        match = ASSIGNMENT_RE.match(line)
        if match:
            assignments[match.group("name")] = Assignment(
                index=index,
                prefix=match.group("prefix"),
                name=match.group("name"),
                raw_value=match.group("value"),
                newline=match.group("newline") or "",
            )
    return lines, assignments


def _decode(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _project_ref_from_supabase_url(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not host.endswith(".supabase.co"):
        raise ValueError("SUPABASE_URL must be shaped like https://<project_ref>.supabase.co")
    project_ref = host.removesuffix(".supabase.co")
    if not PROJECT_REF_RE.match(project_ref):
        raise ValueError("SUPABASE_URL project ref has an unsupported shape")
    return project_ref


def database_shape(value: str) -> dict[str, Any]:
    parsed = urlparse(value)
    host = parsed.hostname or ""
    username = parsed.username or ""
    port = _database_url_port(parsed)
    database = parsed.path.strip("/")
    _validate_database_url_basics(parsed, port, database, value)
    pooler = _pooler_shape(host, username)
    _validate_project_ref(pooler["project_ref"])
    return {
        "scheme": parsed.scheme,
        "host": host,
        "port": port,
        "pooler_kind": pooler["pooler_kind"],
        "username_kind": pooler["username_kind"],
        "project_ref": pooler["project_ref"],
        "project_ref_fp": fingerprint(pooler["project_ref"]),
        "database": database,
        "password_present": True,
    }


def _database_url_port(parsed: object) -> int | None:
    try:
        return parsed.port  # type: ignore[attr-defined]
    except ValueError as exc:
        raise ValueError("DATABASE_URL port must be a valid integer") from exc


def _validate_database_url_basics(parsed: object, port: int | None, database: str, value: str) -> None:
    for failed, message in _database_url_basic_rules(parsed, port, database, value):
        if failed:
            raise ValueError(message)


def _database_url_basic_rules(parsed: object, port: int | None, database: str, value: str) -> list[tuple[bool, str]]:
    return [
        (parsed.scheme not in {"postgres", "postgresql"}, "DATABASE_URL must use postgres or postgresql scheme"),  # type: ignore[attr-defined]
        (port != 6543, "DATABASE_URL must use the Transaction pooler port 6543"),
        (not parsed.password, "DATABASE_URL must include a database password"),  # type: ignore[attr-defined]
        (not database, "DATABASE_URL must include a database name"),
        (any(ch.isspace() for ch in value), "DATABASE_URL must not contain raw whitespace"),
    ]


def _pooler_shape(host: str, username: str) -> dict[str, str]:
    if host.endswith(".pooler.supabase.com"):
        return _shared_pooler_shape(username)
    if host.startswith("db.") and host.endswith(".supabase.co"):
        return _dedicated_pooler_shape(host, username)
    raise ValueError("DATABASE_URL must use a Supabase Transaction pooler host")


def _shared_pooler_shape(username: str) -> dict[str, str]:
    if not username.startswith("postgres."):
        raise ValueError("DATABASE_URL shared pooler username must use postgres.<project_ref>")
    return {
        "pooler_kind": "shared_transaction_pooler",
        "username_kind": "postgres_dot_project_ref",
        "project_ref": username.removeprefix("postgres."),
    }


def _dedicated_pooler_shape(host: str, username: str) -> dict[str, str]:
    if username != "postgres":
        raise ValueError("DATABASE_URL dedicated pooler username must be postgres")
    return {
        "pooler_kind": "dedicated_transaction_pooler",
        "username_kind": "postgres",
        "project_ref": host.removeprefix("db.").removesuffix(".supabase.co"),
    }


def _validate_project_ref(project_ref: str) -> None:
    if not project_ref or not PROJECT_REF_RE.match(project_ref):
        raise ValueError("DATABASE_URL pooler project ref has an unsupported shape")


def _validate_database_url(new_url: str, assignments: dict[str, Assignment], *, allow_host_change: bool) -> tuple[dict[str, Any], list[str]]:
    _validate_new_database_url_text(new_url)
    expected_ref = _expected_supabase_ref(assignments)
    shape = database_shape(new_url.strip())
    if shape["project_ref"] != expected_ref:
        raise ValueError("DATABASE_URL project ref does not match SUPABASE_URL")
    warnings = _host_change_warnings(assignments, shape, allow_host_change)
    public = dict(shape)
    public.pop("project_ref", None)
    public["supabase_url_project_ref_fp"] = fingerprint(expected_ref)
    public["project_refs_match"] = True
    return public, warnings


def _validate_new_database_url_text(new_url: str) -> None:
    if not new_url.strip():
        raise ValueError("new DATABASE_URL is empty")
    if "\n" in new_url or "\r" in new_url:
        raise ValueError("new DATABASE_URL must be a single line")


def _expected_supabase_ref(assignments: dict[str, Assignment]) -> str:
    supabase_url = assignments.get("SUPABASE_URL")
    if supabase_url is None:
        raise ValueError("SUPABASE_URL is missing from the env file")
    return _project_ref_from_supabase_url(_decode(supabase_url.raw_value))


def _host_change_warnings(
    assignments: dict[str, Assignment],
    shape: dict[str, Any],
    allow_host_change: bool,
) -> list[str]:
    current_shape = _current_database_shape(assignments)
    if not current_shape or current_shape["host"] == shape["host"]:
        return []
    if allow_host_change:
        return ["database host changed from the previous DATABASE_URL"]
    raise ValueError("DATABASE_URL host changed; rerun with --allow-host-change if this is intentional")


def _current_database_shape(assignments: dict[str, Assignment]) -> dict[str, Any] | None:
    current = assignments.get("DATABASE_URL")
    if current is None:
        return None
    try:
        return database_shape(_decode(current.raw_value))
    except ValueError:
        return None


def _validation_assignments(
    local_assignments: dict[str, Assignment],
    root_assignments: dict[str, Assignment],
) -> tuple[dict[str, Assignment], str]:
    merged = dict(local_assignments)
    if "SUPABASE_URL" in merged:
        return merged, "local_env"
    root_supabase_url = root_assignments.get("SUPABASE_URL")
    if root_supabase_url is not None:
        merged["SUPABASE_URL"] = root_supabase_url
        return merged, "root_env"
    return merged, ""


def _format_line(prefix: str, name: str, value: str, newline: str) -> str:
    line_newline = newline or "\n"
    return f"{prefix}{name}={value}{line_newline}"


def _write_values(path: Path, updates: dict[str, str]) -> Path | None:
    lines, assignments = _read_lines(path)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.bak-{timestamp}")
    backup_created = _write_backup(path, backup_path)
    _ensure_trailing_newline(lines)
    for name, value in updates.items():
        _apply_update_line(lines, assignments, name, value)
    tmp_path = path.with_name(f"{path.name}.tmp-{timestamp}")
    tmp_path.write_text("".join(lines), encoding="utf-8")
    os.replace(tmp_path, path)
    return backup_path if backup_created else None


def _write_backup(path: Path, backup_path: Path) -> bool:
    if path.exists():
        backup_path.write_bytes(path.read_bytes())
        return True
    return False


def _ensure_trailing_newline(lines: list[str]) -> None:
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] = lines[-1] + "\n"


def _apply_update_line(lines: list[str], assignments: dict[str, Assignment], name: str, value: str) -> None:
    assignment = assignments.get(name)
    if assignment is None:
        lines.append(_format_line("", name, value, "\n"))
        return
    lines[assignment.index] = _format_line(assignment.prefix, assignment.name, value, assignment.newline)


def _env_value(name: str, environ: dict[str, str] | None = None) -> str:
    return scoped_env_value(name, environ=environ)


def _redacted_update_env_vars(
    environ: dict[str, str] | None = None,
    scoped_env: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    return scoped_redacted_env_status(UPDATE_ENV_NAMES, environ=environ, scoped_env=scoped_env)


def build_input_status(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    env_path: Path = DEFAULT_ENV_PATH,
    local_env_path: Path = DEFAULT_LOCAL_ENV_PATH,
    environ: dict[str, str] | None = None,
    scoped_env: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    update_vars = _redacted_update_env_vars(environ, scoped_env)
    windows_update_vars = redacted_windows_env_status(
        UPDATE_ENV_NAMES,
        scoped_env=scoped_env,
        read_windows=environ is None and scoped_env is None,
    )
    update_state = _update_signal_state(update_vars, windows_update_vars)
    artifacts = _status_artifact_paths(workspace_root)
    mtime_state = _mtime_state(env_path, local_env_path, artifacts)
    input_signal = _input_signal_summary(update_vars, windows_update_vars, mtime_state)
    rerun = _rerun_recommended(update_state, mtime_state)
    disabled = _disabled_providers(local_env_path)
    evidence_summary = {
        "readiness": _artifact_summary(artifacts["readiness"]),
        "workspace_smoke": _artifact_summary(artifacts["workspace_smoke"]),
    }
    launch_blocker_summary = _launch_blocker_summary(rerun, evidence_summary)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "changed" if rerun else "unchanged",
        "ok": True,
        "credential_update_env_vars": update_vars,
        "windows_credential_update_env_vars": windows_update_vars,
        "process_update_env_var_present": update_state["process_update"],
        "windows_update_env_var_present": update_state["windows_update"],
        "credential_manager": {"checked": True, "matching_target_count": 0, "targets": []},
        "credential_source_signal_present": update_state["any_update"],
        "any_update_env_var_present": update_state["any_update"],
        "input_signal": input_signal,
        "input_signal_fingerprint": input_signal["fingerprint"],
        "paths": _path_meta(env_path, local_env_path, artifacts, workspace_root),
        "local_provider_route": _local_provider_route(local_env_path, disabled, workspace_root),
        "supabase_management_capability": _supabase_management_capability(),
        "evidence_summary": evidence_summary,
        "launch_blocker_summary": launch_blocker_summary,
        "root_env_newer_than_readiness": mtime_state["root_env_newer_than_readiness"],
        "root_env_newer_than_workspace_smoke": mtime_state["root_env_newer_than_workspace_smoke"],
        "local_env_newer_than_readiness": mtime_state["local_env_newer_than_readiness"],
        "local_env_newer_than_workspace_smoke": mtime_state["local_env_newer_than_workspace_smoke"],
        "env_newer_than_readiness": mtime_state["env_newer_than_readiness"],
        "env_newer_than_workspace_smoke": mtime_state["env_newer_than_workspace_smoke"],
        "rerun_recommended": rerun,
        "safe_to_skip_strict_readiness_until_credential_inputs_change": not rerun,
        "secrets_redacted": True,
        "operator_next_action": launch_blocker_summary["operator_next_action"],
        "next_command_after_provider_fix": "python ops/scripts/getdaytrends_update_credentials.py --database-url-stdin --write",
        "next_verification_after_local_update": POST_UPDATE_COMMAND,
    }


def _input_signal_summary(
    update_vars: dict[str, Any],
    windows_update_vars: dict[str, Any],
    mtime_state: dict[str, bool],
) -> dict[str, Any]:
    process_signal = {
        name: {
            "present": bool(record.get("present")),
            "fingerprint": record.get("fingerprint", ""),
            "source": record.get("source", ""),
        }
        for name, record in update_vars.items()
    }
    windows_signal = {
        scope: {
            name: {
                "present": bool(record.get("present")),
                "fingerprint": record.get("fingerprint", ""),
            }
            for name, record in records.items()
        }
        for scope, records in windows_update_vars.items()
    }
    mtime_signal = {
        key: bool(value)
        for key, value in mtime_state.items()
        if key.endswith("_newer_than_readiness") or key.endswith("_newer_than_workspace_smoke")
    }
    material = {
        "process": process_signal,
        "windows": windows_signal,
        "mtime": mtime_signal,
    }
    present_update_env_vars = sorted(name for name, record in process_signal.items() if record["present"])
    windows_present_update_env_vars = sorted(
        f"{scope}:{name}"
        for scope, records in windows_signal.items()
        for name, record in records.items()
        if record["present"]
    )
    return {
        "schema_version": 1,
        "fingerprint": fingerprint(json.dumps(material, sort_keys=True, separators=(",", ":"))),
        "credential_env_present": bool(present_update_env_vars or windows_present_update_env_vars),
        "present_update_env_vars": present_update_env_vars,
        "windows_present_update_env_vars": windows_present_update_env_vars,
        "mtime_signal_present": any(mtime_signal.values()),
        "material_scope": "redacted_env_fingerprints_and_artifact_mtime_flags",
    }


def _update_signal_state(update_vars: dict[str, Any], windows_update_vars: dict[str, Any]) -> dict[str, bool]:
    scoped_update = any(item["present"] for item in update_vars.values())
    process_update = any(item["present"] and item.get("source") == "Process" for item in update_vars.values())
    windows_update = any(item["present"] for scope in windows_update_vars.values() for item in scope.values())
    return {
        "any_update": scoped_update or windows_update,
        "process_update": process_update,
        "windows_update": windows_update,
    }


def _status_artifact_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "readiness": workspace_root / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json",
        "workspace_smoke": workspace_root / "var" / "workspace-smoke-getdaytrends-launch-final.json",
    }


def _mtime_state(env_path: Path, local_env_path: Path, artifacts: dict[str, Path]) -> dict[str, bool]:
    env_mtime = _path_mtime(env_path)
    local_mtime = _path_mtime(local_env_path)
    readiness_mtime = _path_mtime(artifacts["readiness"])
    smoke_mtime = _path_mtime(artifacts["workspace_smoke"])
    env_max = max(env_mtime, local_mtime)
    return {
        "root_env_newer_than_readiness": _newer_than(env_mtime, readiness_mtime),
        "root_env_newer_than_workspace_smoke": _newer_than(env_mtime, smoke_mtime),
        "local_env_newer_than_readiness": _newer_than(local_mtime, readiness_mtime),
        "local_env_newer_than_workspace_smoke": _newer_than(local_mtime, smoke_mtime),
        "env_newer_than_readiness": _newer_than(env_max, readiness_mtime),
        "env_newer_than_workspace_smoke": _newer_than(env_max, smoke_mtime),
    }


def _path_mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0


def _newer_than(left_mtime: float, right_mtime: float) -> bool:
    return bool(left_mtime and right_mtime and left_mtime > right_mtime)


def _rerun_recommended(update_state: dict[str, bool], mtime_state: dict[str, bool]) -> bool:
    return update_state["any_update"] or mtime_state["env_newer_than_readiness"] or mtime_state["env_newer_than_workspace_smoke"]


def _disabled_providers(local_env_path: Path) -> list[str]:
    local_assignments = env_assignment_map(local_env_path)
    return [part.strip() for part in local_assignments.get("DAILYNEWS_DISABLED_LLM_PROVIDERS", "").split(",") if part.strip()]


def _path_meta(env_path: Path, local_env_path: Path, artifacts: dict[str, Path], workspace_root: Path) -> dict[str, Any]:
    return {
        "env": file_meta(env_path, workspace_root),
        "local_env": file_meta(local_env_path, workspace_root),
        "readiness": file_meta(artifacts["readiness"], workspace_root),
        "workspace_smoke": file_meta(artifacts["workspace_smoke"], workspace_root),
    }


def _local_provider_route(local_env_path: Path, disabled: list[str], workspace_root: Path) -> dict[str, Any]:
    return {
        "path": file_meta(local_env_path, workspace_root),
        "keys": {"DAILYNEWS_DISABLED_LLM_PROVIDERS": _disabled_provider_record(disabled)},
        "google_or_gemini_disabled": "google" in disabled or "gemini" in disabled,
    }


def _disabled_provider_record(disabled: list[str]) -> dict[str, Any]:
    return {
        "present": bool(disabled),
        "provider_count": len(disabled),
        "providers": disabled,
        "fingerprint": fingerprint(",".join(disabled)),
    }


def _supabase_management_capability() -> dict[str, Any]:
    return {
        "supabase_cli": {"found": False, "path_present": False},
        "access_token_present": False,
        "project_id_present": False,
        "db_password_present": False,
        "service_role_key_present": False,
        "secret_management_matching_names": 0,
        "can_rotate_db_password_locally": False,
        "reason": "No complete local Supabase management path was found; provider-console credential repair is still required.",
    }


def _artifact_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        summary = {
            "exists": True,
            "status": payload.get("status"),
            "generated_at": payload.get("generated_at"),
            "summary": payload.get("summary"),
        }
        scheduler_artifact = _scheduler_artifact_summary(payload, path)
        if scheduler_artifact:
            summary["scheduler_artifact"] = scheduler_artifact
        return summary
    except Exception:
        return {"exists": True, "status": "unreadable"}


def _scheduler_artifact_summary(payload: dict[str, Any], readiness_path: Path) -> dict[str, Any]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != "scheduler_artifact":
            continue
        evidence = check.get("evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        scheduler_dir = readiness_path.parent.parent / "scheduler"
        selected_path_value = evidence.get("path")
        artifact_payload = _load_scheduler_artifact(selected_path_value, scheduler_dir)
        artifact_evidence = _scheduler_artifact_payload_evidence(artifact_payload, selected_path_value)
        latest_path = _latest_scheduler_artifact(scheduler_dir)
        latest_path_value = str(latest_path) if latest_path is not None else ""
        latest_payload = _load_scheduler_artifact(latest_path_value, scheduler_dir)
        latest_evidence = _scheduler_artifact_payload_evidence(latest_payload, latest_path_value)
        summary: dict[str, Any] = {}
        if isinstance(check.get("ok"), bool):
            summary["ok"] = check["ok"]
        if isinstance(check.get("level"), str):
            summary["level"] = check["level"]
        if isinstance(evidence.get("status"), str):
            summary["status"] = evidence["status"]
        if isinstance(evidence.get("exit_code"), int) and not isinstance(evidence.get("exit_code"), bool):
            summary["exit_code"] = evidence["exit_code"]
        for field in SCHEDULER_ARTIFACT_EVIDENCE_FIELDS:
            value = evidence.get(field)
            if isinstance(value, bool):
                summary[field] = value
            elif field in artifact_evidence:
                summary[field] = artifact_evidence[field]
        if latest_path is not None:
            summary["selected_artifact_is_latest"] = _path_value_matches(selected_path_value, latest_path_value)
            for field in SCHEDULER_ARTIFACT_EVIDENCE_FIELDS:
                if field in latest_evidence:
                    summary[f"latest_{field}"] = latest_evidence[field]
        return summary
    return {}


def _latest_scheduler_artifact(scheduler_dir: Path) -> Path | None:
    try:
        candidates = [path for path in scheduler_dir.glob("run_*.json") if path.is_file()]
    except OSError:
        return None
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
    payload = _load_scheduler_artifact(str(path), path.parent)
    if not payload:
        return None
    for field in ("finished_at", "ended_at", "started_at", "generated_at"):
        parsed = _parse_scheduler_artifact_datetime(payload.get(field))
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


def _parse_scheduler_artifact_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_scheduler_artifact(path_value: Any, scheduler_dir: Path) -> dict[str, Any]:
    if not isinstance(path_value, str) or not path_value.strip():
        return {}
    scheduler_path = Path(path_value)
    try:
        if not scheduler_path.resolve(strict=False).is_relative_to(scheduler_dir.resolve(strict=False)):
            return {}
        payload = json.loads(scheduler_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _scheduler_artifact_payload_evidence(payload: dict[str, Any], selected_path_value: Any) -> dict[str, bool]:
    if not payload:
        return {}
    artifact_path = payload.get("artifact_path")
    summary_fallback_used = payload.get("summary_fallback_used")
    summary_fallback_used_present = "summary_fallback_used" in payload
    return {
        "artifact_path_present": isinstance(artifact_path, str) and bool(artifact_path.strip()),
        "artifact_path_matches_latest": _path_value_matches(artifact_path, selected_path_value),
        "summary_fallback_used": summary_fallback_used if isinstance(summary_fallback_used, bool) else False,
        "summary_fallback_used_present": summary_fallback_used_present,
        "summary_fallback_used_valid": not summary_fallback_used_present or isinstance(summary_fallback_used, bool),
    }


def _path_value_matches(left: Any, right: Any) -> bool:
    if not isinstance(left, str) or not left.strip() or not isinstance(right, str) or not right.strip():
        return False
    try:
        return Path(left).resolve(strict=False) == Path(right).resolve(strict=False)
    except OSError:
        return False


def _launch_blocker_summary(rerun: bool, evidence_summary: dict[str, Any]) -> dict[str, Any]:
    readiness = _evidence_record(evidence_summary, "readiness")
    workspace_smoke = _evidence_record(evidence_summary, "workspace_smoke")
    readiness_summary = _summary_record(readiness)
    workspace_summary = _summary_record(workspace_smoke)
    expected_external_failures = _summary_count_int(workspace_summary.get("expected_external_failures"))
    unexpected_failures = _summary_count_int(workspace_summary.get("unexpected_failures"))
    readiness_status = _evidence_status(readiness)
    workspace_smoke_status = _evidence_status(workspace_smoke)
    operator_attention_kinds = _operator_attention_kinds(readiness)
    readiness_scheduler_stale = _readiness_scheduler_artifact_stale(readiness)
    latest_scheduler_complete = _latest_scheduler_artifact_evidence_complete(readiness)
    readiness_failed = (
        readiness_status in {"fail", "failed", "invalid", "unreadable", "error"}
        or bool(_summary_count_int(readiness_summary.get("failed")))
    )
    blocking_evidence_kinds = _blocking_evidence_kinds(
        rerun=rerun,
        readiness_failed=readiness_failed,
        readiness_status=readiness_status,
        unexpected_failures=unexpected_failures,
    )

    status = "clear"
    reason = "credential_inputs_unchanged_and_evidence_not_failing"
    operator_next_action = "monitor_existing_evidence"
    if rerun:
        status = "credential_input_changed"
        reason = "credential_or_env_mtime_signal_present"
        operator_next_action = "run_post_update_verification"
    elif readiness_failed:
        status = "external_readiness_blocked"
        reason = "readiness_failed_without_new_credential_input"
        operator_next_action = "stage_corrected_provider_console_database_url_then_run_local_update"
    elif unexpected_failures:
        status = "workspace_smoke_attention_required"
        reason = "workspace_smoke_has_unexpected_failures"
        operator_next_action = "investigate_workspace_smoke_unexpected_failures"
    elif readiness_status == "missing":
        status = "readiness_evidence_missing"
        reason = "readiness_artifact_missing"
        operator_next_action = "refresh_readiness_evidence_when_credentials_are_available"

    return {
        "status": status,
        "reason": reason,
        "readiness_status": readiness_status,
        "workspace_smoke_status": workspace_smoke_status,
        "expected_external_failures": expected_external_failures,
        "unexpected_failures": unexpected_failures,
        "blocking_evidence_kinds": blocking_evidence_kinds,
        "blocking_evidence_count": len(blocking_evidence_kinds),
        "operator_attention_kinds": operator_attention_kinds,
        "operator_attention_count": len(operator_attention_kinds),
        "readiness_scheduler_artifact_stale": readiness_scheduler_stale,
        "latest_scheduler_artifact_evidence_complete": latest_scheduler_complete,
        "strict_readiness_rerun_recommended": rerun,
        "operator_next_action": operator_next_action,
    }


def _readiness_scheduler_artifact_stale(readiness: dict[str, Any]) -> bool:
    scheduler_artifact = readiness.get("scheduler_artifact")
    return isinstance(scheduler_artifact, dict) and scheduler_artifact.get("selected_artifact_is_latest") is False


def _latest_scheduler_artifact_evidence_complete(readiness: dict[str, Any]) -> bool:
    scheduler_artifact = readiness.get("scheduler_artifact")
    if not isinstance(scheduler_artifact, dict):
        return False
    return (
        scheduler_artifact.get("latest_artifact_path_present") is True
        and scheduler_artifact.get("latest_artifact_path_matches_latest") is True
        and scheduler_artifact.get("latest_summary_fallback_used_present") is True
        and scheduler_artifact.get("latest_summary_fallback_used_valid") is True
    )


def _operator_attention_kinds(readiness: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    scheduler_artifact = readiness.get("scheduler_artifact")
    if not isinstance(scheduler_artifact, dict):
        return kinds
    if scheduler_artifact.get("selected_artifact_is_latest") is False:
        kinds.append("scheduler_artifact_evidence_stale")
    if (
        scheduler_artifact.get("artifact_path_present") is False
        and scheduler_artifact.get("latest_artifact_path_present") is True
    ):
        kinds.append("readiness_selected_scheduler_schema_older_than_latest")
    if (
        scheduler_artifact.get("summary_fallback_used_present") is False
        and scheduler_artifact.get("latest_summary_fallback_used_present") is True
    ):
        kinds.append("readiness_selected_scheduler_fallback_field_missing")
    return kinds


def _blocking_evidence_kinds(
    *,
    rerun: bool,
    readiness_failed: bool,
    readiness_status: str,
    unexpected_failures: int,
) -> list[str]:
    kinds: list[str] = []
    if rerun:
        kinds.append("credential_input_changed")
    if readiness_failed:
        kinds.append("readiness_failed")
    if unexpected_failures:
        kinds.append("workspace_smoke_unexpected_failures")
    if readiness_status == "missing":
        kinds.append("readiness_evidence_missing")
    return kinds


def _evidence_record(evidence_summary: dict[str, Any], key: str) -> dict[str, Any]:
    record = evidence_summary.get(key)
    return record if isinstance(record, dict) else {}


def _summary_record(evidence: dict[str, Any]) -> dict[str, Any]:
    summary = evidence.get("summary")
    return summary if isinstance(summary, dict) else {}


def _evidence_status(evidence: dict[str, Any]) -> str:
    if not evidence.get("exists"):
        return "missing"
    return str(evidence.get("status") or "unknown").lower()


def _read_database_url(args: argparse.Namespace) -> str:
    if args.database_url_stdin:
        value = sys.stdin.read().strip()
        _validate_database_url_input_value("stdin", value)
        return value
    value = _env_value("GETDAYTRENDS_NEW_DATABASE_URL")
    if _update_input_present("GETDAYTRENDS_NEW_DATABASE_URL"):
        _validate_database_url_input_value("GETDAYTRENDS_NEW_DATABASE_URL", value)
    return value


def _validate_database_url_input_value(source_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"DATABASE_URL from {source_name} must not be blank")


def build_update_report(
    *,
    env_path: Path,
    local_env_path: Path,
    dry_run: bool,
    database_shape_report: dict[str, Any] | None,
    warnings: list[str],
    supabase_url_source: str = "",
    backup_paths: list[Path] | None = None,
    updated_keys: list[str] | None = None,
    updated_key_sources: dict[str, str] | None = None,
    updated_key_source_scopes: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _update_status(dry_run),
        "ok": True,
        "dry_run": dry_run,
        "env_path": str(env_path),
        "local_env_path": str(local_env_path),
        "updated_keys": updated_keys or [],
        "updated_key_sources": updated_key_sources or {},
        "updated_key_source_scopes": updated_key_source_scopes or {},
        "new_database_url_shape": database_shape_report or {},
        "supabase_url_source": supabase_url_source,
        "warnings": warnings,
        "backup_paths": _path_strings(backup_paths),
        "secrets_redacted": True,
        "next_verification_after_local_update": POST_UPDATE_COMMAND,
    }


def _update_status(dry_run: bool) -> str:
    return "planned" if dry_run else "updated"


def _path_strings(paths: list[Path] | None) -> list[str]:
    return [str(path) for path in paths or []]


def update_credentials(args: argparse.Namespace) -> dict[str, Any]:
    env_path, local_env_path = _resolved_env_paths(args)
    validation_assignments, supabase_url_source = _validation_context(env_path, local_env_path)
    shape, warnings, updates, update_sources = _credential_updates(args, validation_assignments)
    backups = _write_update_backups(args, local_env_path, updates)
    return build_update_report(
        env_path=env_path,
        local_env_path=local_env_path,
        dry_run=not args.write,
        database_shape_report=shape,
        warnings=warnings,
        supabase_url_source=supabase_url_source,
        backup_paths=backups,
        updated_keys=sorted(updates),
        updated_key_sources={key: update_sources[key] for key in sorted(update_sources)},
        updated_key_source_scopes=_update_source_scopes(args, updates),
    )


def _resolved_env_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    return args.env_path.resolve(), args.local_env_path.resolve()


def _validation_context(env_path: Path, local_env_path: Path) -> tuple[dict[str, Assignment], str]:
    _, local_assignments = _read_lines(local_env_path)
    _, root_assignments = _read_lines(env_path)
    return _validation_assignments(local_assignments, root_assignments)


def _credential_updates(
    args: argparse.Namespace,
    validation_assignments: dict[str, Assignment],
) -> tuple[dict[str, Any] | None, list[str], dict[str, str], dict[str, str]]:
    database_url = _read_database_url(args)
    optional_updates = _optional_updates()
    validation_assignments = _validation_assignments_with_updates(validation_assignments, optional_updates)
    shape, warnings, updates = _database_url_update(args, database_url, validation_assignments)
    updates.update(optional_updates)
    if not updates:
        raise ValueError("no getdaytrends credential update inputs are present")
    return shape, warnings, updates, _update_sources(args, updates)


def _database_url_update(
    args: argparse.Namespace,
    database_url: str,
    validation_assignments: dict[str, Assignment],
) -> tuple[dict[str, Any] | None, list[str], dict[str, str]]:
    if not database_url:
        return None, [], {}
    shape, warnings = _validate_database_url(database_url, validation_assignments, allow_host_change=args.allow_host_change)
    return shape, warnings, {"DATABASE_URL": database_url.strip()}


def _optional_updates() -> dict[str, str]:
    updates: dict[str, str] = {}
    update_vars = _redacted_update_env_vars()
    for source_name, target_name in OPTIONAL_WRITE_ENV.items():
        if not update_vars.get(source_name, {}).get("present"):
            continue
        value = _env_value(source_name)
        _validate_optional_update_value(source_name, target_name, value)
        if target_name == "SUPABASE_URL":
            _project_ref_from_supabase_url(value)
        updates[target_name] = value
    return updates


def _validate_optional_update_value(source_name: str, target_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{target_name} from {source_name} must not be blank")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{target_name} from {source_name} must be a single line")


def _update_sources(args: argparse.Namespace, updates: dict[str, str]) -> dict[str, str]:
    sources: dict[str, str] = {}
    if "DATABASE_URL" in updates:
        sources["DATABASE_URL"] = "stdin" if args.database_url_stdin else "GETDAYTRENDS_NEW_DATABASE_URL"
    for source_name, target_name in OPTIONAL_WRITE_ENV.items():
        if target_name in updates:
            sources[target_name] = source_name
    return sources


def _update_source_scopes(args: argparse.Namespace, updates: dict[str, str]) -> dict[str, str]:
    scopes: dict[str, str] = {}
    if "DATABASE_URL" in updates:
        scopes["DATABASE_URL"] = "stdin" if args.database_url_stdin else _update_env_source_scope("GETDAYTRENDS_NEW_DATABASE_URL")
    for source_name, target_name in OPTIONAL_WRITE_ENV.items():
        if target_name in updates:
            scopes[target_name] = _update_env_source_scope(source_name)
    return {key: scopes[key] for key in sorted(scopes)}


def _update_env_source_scope(source_name: str) -> str:
    record = _redacted_update_env_vars().get(source_name, {})
    return str(record.get("source") or "")


def _validation_assignments_with_updates(
    validation_assignments: dict[str, Assignment],
    updates: dict[str, str],
) -> dict[str, Assignment]:
    if "SUPABASE_URL" not in updates:
        return validation_assignments
    merged = dict(validation_assignments)
    merged["SUPABASE_URL"] = Assignment(
        index=-1,
        prefix="",
        name="SUPABASE_URL",
        raw_value=updates["SUPABASE_URL"],
        newline="",
    )
    return merged


def _write_update_backups(args: argparse.Namespace, local_env_path: Path, updates: dict[str, str]) -> list[Path]:
    if not args.write:
        return []
    backup_path = _write_values(local_env_path, updates)
    return [backup_path] if backup_path is not None else []


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    input_signal = payload.get("input_signal", {})
    lines = [
        "# getdaytrends Credential Input Status",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Status: `{payload['status']}`",
        f"- Rerun recommended: `{payload.get('rerun_recommended', False)}`",
        "- Safe to skip strict readiness until credential inputs change: "
        f"`{payload.get('safe_to_skip_strict_readiness_until_credential_inputs_change', False)}`",
        f"- Input signal fingerprint: `{payload.get('input_signal_fingerprint', '')}`",
        f"- Process update env present: `{payload.get('process_update_env_var_present', False)}`",
        f"- Windows update env present: `{payload.get('windows_update_env_var_present', False)}`",
        f"- Credential update env vars: `{_markdown_list(input_signal.get('present_update_env_vars'))}`",
        f"- Windows update env vars: `{_markdown_list(input_signal.get('windows_present_update_env_vars'))}`",
        f"- Credential update env present: `{input_signal.get('credential_env_present', False)}`",
        f"- Env/artifact mtime signal present: `{input_signal.get('mtime_signal_present', False)}`",
        f"- Readiness evidence: `{_markdown_evidence_summary(payload, 'readiness')}`",
        f"- Workspace smoke evidence: `{_markdown_evidence_summary(payload, 'workspace_smoke')}`",
        f"- Launch blocker summary: `{_markdown_launch_blocker_summary(payload)}`",
        f"- Operator next action: `{payload.get('operator_next_action', '')}`",
        f"- Next command after provider fix: `{payload.get('next_command_after_provider_fix', '')}`",
        f"- Next verification after local update: `{payload.get('next_verification_after_local_update', '')}`",
        f"- Secrets redacted: `{payload.get('secrets_redacted', False)}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


def _markdown_evidence_summary(payload: dict[str, Any], key: str) -> str:
    evidence = payload.get("evidence_summary", {}).get(key, {})
    if not isinstance(evidence, dict) or not evidence.get("exists"):
        return "missing"
    summary = evidence.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        f"status={evidence.get('status') or 'unknown'}",
        f"generated_at={evidence.get('generated_at') or 'unknown'}",
    ]
    for field in ("total", "passed", "failed", "warnings", "expected_external_failures", "unexpected_failures"):
        if field in summary:
            parts.append(f"{field}={_summary_count(summary[field])}")
    scheduler_artifact = evidence.get("scheduler_artifact")
    if isinstance(scheduler_artifact, dict):
        for field in (
            "ok",
            "status",
            "selected_artifact_is_latest",
            "artifact_path_present",
            "artifact_path_matches_latest",
            "summary_fallback_used",
            "summary_fallback_used_present",
            "summary_fallback_used_valid",
            "latest_artifact_path_present",
            "latest_artifact_path_matches_latest",
            "latest_summary_fallback_used",
            "latest_summary_fallback_used_present",
            "latest_summary_fallback_used_valid",
        ):
            if field in scheduler_artifact:
                parts.append(f"scheduler_artifact_{field}={_markdown_summary_value(scheduler_artifact[field])}")
    return ", ".join(parts)


def _markdown_launch_blocker_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("launch_blocker_summary")
    if not isinstance(summary, dict):
        return "missing"
    fields = (
        "status",
        "reason",
        "readiness_status",
        "workspace_smoke_status",
        "expected_external_failures",
        "unexpected_failures",
        "blocking_evidence_count",
        "blocking_evidence_kinds",
        "operator_attention_count",
        "operator_attention_kinds",
        "readiness_scheduler_artifact_stale",
        "latest_scheduler_artifact_evidence_complete",
        "strict_readiness_rerun_recommended",
    )
    return ", ".join(f"{field}={_markdown_summary_value(summary.get(field))}" for field in fields if field in summary)


def _markdown_summary_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value) if value else "none"
    return value


def _summary_count(value: Any) -> Any:
    if isinstance(value, list):
        return len(value)
    return value


def _summary_count_int(value: Any) -> int:
    count = _summary_count(value)
    return count if isinstance(count, int) and not isinstance(count, bool) else 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or update getdaytrends credential inputs.")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT, help="Workspace root used for evidence lookup.")
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH, help="Workspace .env path used for read-only validation.")
    parser.add_argument(
        "--local-env-path",
        type=Path,
        default=DEFAULT_LOCAL_ENV_PATH,
        help="getdaytrends local .env path to update when --write is used.",
    )
    parser.add_argument(
        "--input-status",
        action="store_true",
        help="Write a redacted credential-input status report. By default this writes both dated and current JSON aliases.",
    )
    parser.add_argument("--database-url-stdin", action="store_true", help="Read the replacement DATABASE_URL from stdin.")
    parser.add_argument("--write", action="store_true", help="Apply validated credential updates to the local getdaytrends env file.")
    parser.add_argument("--allow-host-change", action="store_true", help="Allow intentional Supabase pooler host changes.")
    parser.add_argument("--json-out", type=Path, help="Write the JSON report to this path.")
    parser.add_argument("--current-json-out", type=Path, help="Also write an operator current-alias JSON report to this path.")
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT, help="Write the Markdown status report to this path.")
    args = parser.parse_args(argv)
    if args.input_status and args.json_out is None:
        args.json_out = DEFAULT_JSON_OUT
        if args.current_json_out is None:
            args.current_json_out = DEFAULT_CURRENT_JSON_OUT
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = _run_mode(args)
        _print_report(report)
        return 0
    except ValueError as exc:
        report = _invalid_report(args, exc)
        _write_json_if_requested(args, report)
        _print_report(report)
        return 1


def _run_mode(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_status:
        report = build_input_status(
            workspace_root=args.workspace_root,
            env_path=args.env_path,
            local_env_path=args.local_env_path,
        )
        _write_json_if_requested(args, report)
        _write_markdown(args.markdown_out, report)
        return report
    report = update_credentials(args)
    _write_json_if_requested(args, report)
    return report


def _write_json_if_requested(args: argparse.Namespace, report: dict[str, Any]) -> None:
    if args.json_out:
        write_json(args.json_out, report)
    current_json_out = getattr(args, "current_json_out", None)
    if current_json_out and current_json_out != args.json_out:
        write_json(current_json_out, report)


def _invalid_report(args: argparse.Namespace, exc: ValueError) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "invalid",
        "ok": False,
        "dry_run": not args.write,
        "error": str(exc),
        "attempted_update_sources": _attempted_update_sources(args),
        "attempted_update_source_scopes": _attempted_update_source_scopes(args),
        "secrets_redacted": True,
    }


def _attempted_update_sources(args: argparse.Namespace) -> dict[str, str]:
    sources: dict[str, str] = {}
    if args.database_url_stdin or _update_input_present("GETDAYTRENDS_NEW_DATABASE_URL"):
        sources["DATABASE_URL"] = "stdin" if args.database_url_stdin else "GETDAYTRENDS_NEW_DATABASE_URL"
    for source_name, target_name in OPTIONAL_WRITE_ENV.items():
        if _update_input_present(source_name):
            sources[target_name] = source_name
    return {key: sources[key] for key in sorted(sources)}


def _attempted_update_source_scopes(args: argparse.Namespace) -> dict[str, str]:
    scopes: dict[str, str] = {}
    if args.database_url_stdin or _update_input_present("GETDAYTRENDS_NEW_DATABASE_URL"):
        scopes["DATABASE_URL"] = "stdin" if args.database_url_stdin else _update_env_source_scope("GETDAYTRENDS_NEW_DATABASE_URL")
    for source_name, target_name in OPTIONAL_WRITE_ENV.items():
        if _update_input_present(source_name):
            scopes[target_name] = _update_env_source_scope(source_name)
    return {key: scopes[key] for key in sorted(scopes)}


def _update_input_present(source_name: str) -> bool:
    return bool(_redacted_update_env_vars().get(source_name, {}).get("present"))


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
