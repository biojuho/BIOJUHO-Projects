"""Scan getdaytrends launch handoff artifacts for value-shaped secrets."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_research_status import (
    GETDAYTRENDS_SECRET_VALUE_PATTERNS,
    _scan_secret_value_paths,
)
from workspace_paths import find_workspace_root

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = find_workspace_root(Path(__file__))
EXPECTED_TRANSACTION_POOLER_SHAPES = {
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


def build_getdaytrends_launch_secret_scan(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    extra_paths: list[Path] | None = None,
    include_current_artifacts: bool = False,
) -> dict[str, Any]:
    """Build a no-value secret scan report for getdaytrends launch handoff files."""
    candidates = _getdaytrends_launch_secret_scan_targets(
        workspace_root,
        extra_paths=extra_paths,
        include_current_artifacts=include_current_artifacts,
    )
    result = _scan_secret_value_paths(
        workspace_root,
        candidates,
        GETDAYTRENDS_SECRET_VALUE_PATTERNS,
    )
    packet_errors = _packet_contract_errors(workspace_root, include_current_artifacts=include_current_artifacts)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "getdaytrends_launch_handoff",
        "include_current_artifacts": include_current_artifacts,
        "status": result["status"],
        "ok": _report_ok(result, packet_errors),
        "supabase_recovery_packet_contract_ok": (not packet_errors) if include_current_artifacts else None,
        "supabase_recovery_packet_contract_errors": packet_errors,
        **result,
    }


def _getdaytrends_launch_secret_scan_targets(
    workspace_root: Path,
    *,
    extra_paths: list[Path] | None,
    include_current_artifacts: bool,
) -> list[tuple[str, Path | None]]:
    candidates = _default_getdaytrends_launch_secret_scan_targets(workspace_root)
    if include_current_artifacts:
        candidates.extend(_current_getdaytrends_launch_artifact_targets(workspace_root))
    candidates.extend(_extra_path_targets(extra_paths))
    return candidates


def _extra_path_targets(extra_paths: list[Path] | None) -> list[tuple[str, Path]]:
    return [(f"extra_{index}", path) for index, path in enumerate(extra_paths or [], start=1)]


def _packet_contract_errors(workspace_root: Path, *, include_current_artifacts: bool) -> list[str]:
    return _validate_supabase_recovery_packet_contract(workspace_root) if include_current_artifacts else []


def _report_ok(result: dict[str, Any], packet_errors: list[str]) -> bool:
    return result["status"] == "valid" and not result["findings"] and not result["missing_paths"] and not packet_errors


def _validate_supabase_recovery_packet_contract(workspace_root: Path) -> list[str]:
    readiness_dir = workspace_root / "automation" / "getdaytrends" / "logs" / "readiness"
    packet_path = readiness_dir / "supabase_recovery_packet_latest.json"
    strict_packet_path = readiness_dir / "strict_supabase_recovery_packet_latest.json"
    errors = _validate_one_supabase_recovery_packet_contract(packet_path)
    errors.extend(_validate_one_supabase_recovery_packet_contract(strict_packet_path))
    return errors


def _validate_one_supabase_recovery_packet_contract(packet_path: Path) -> list[str]:
    payload, load_error = _load_supabase_recovery_packet(packet_path)
    if load_error:
        return [f"{packet_path.name} {load_error}"]
    errors = _supabase_recovery_packet_field_errors(payload)
    errors.extend(_accepted_transaction_pooler_shape_errors(payload.get("accepted_transaction_pooler_shapes")))
    return [f"{packet_path.name} {error}" for error in errors]


def _load_supabase_recovery_packet(packet_path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}, "supabase_recovery_packet_json missing"
    except json.JSONDecodeError:
        return {}, "supabase_recovery_packet_json invalid_json"
    except OSError as exc:
        return {}, f"supabase_recovery_packet_json unreadable:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "supabase_recovery_packet_json root_not_object"
    return payload, ""


def _supabase_recovery_packet_field_errors(payload: dict[str, Any]) -> list[str]:
    errors = _status_value_errors(payload)
    errors.extend(_expected_value_error(payload, "required_env", ["DATABASE_URL", "SUPABASE_URL"], "required_env must be DATABASE_URL and SUPABASE_URL"))
    errors.extend(_secret_hygiene_errors(_dict_child(payload, "secret_hygiene")))
    errors.extend(_expected_value_error(payload, "accepts_shared_supavisor_transaction_pooler", True, "accepts_shared_supavisor_transaction_pooler must be true"))
    errors.extend(_expected_value_error(payload, "accepts_dedicated_pgbouncer_transaction_pooler", True, "accepts_dedicated_pgbouncer_transaction_pooler must be true"))
    return errors


def _status_value_errors(payload: dict[str, Any]) -> list[str]:
    if payload.get("status") in {"blocked", "clear", "not_evaluated"}:
        return []
    return ["supabase_recovery_packet_json status must be blocked, clear, or not_evaluated"]


def _expected_value_error(payload: dict[str, Any], key: str, expected: Any, message: str) -> list[str]:
    return [] if payload.get(key) == expected else [f"supabase_recovery_packet_json {message}"]


def _dict_child(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _secret_hygiene_errors(secret_hygiene: dict[str, Any]) -> list[str]:
    errors = _expected_value_error(secret_hygiene, "masked_postgres_urls", True, "secret_hygiene.masked_postgres_urls must be true")
    errors.extend(_expected_value_error(secret_hygiene, "masked_supabase_pooler_users", True, "secret_hygiene.masked_supabase_pooler_users must be true"))
    errors.extend(_expected_value_error(secret_hygiene, "contains_plaintext_secret_values", False, "secret_hygiene.contains_plaintext_secret_values must be false"))
    return errors


def _accepted_transaction_pooler_shape_errors(shapes: Any) -> list[str]:
    if not isinstance(shapes, list):
        return ["supabase_recovery_packet_json accepted_transaction_pooler_shapes must be list"]
    shape_by_kind = {shape.get("kind"): shape for shape in shapes if isinstance(shape, dict)}
    errors: list[str] = []
    for kind, expected_shape in EXPECTED_TRANSACTION_POOLER_SHAPES.items():
        errors.extend(_transaction_pooler_shape_errors(kind, expected_shape, shape_by_kind.get(kind)))
    return errors


def _transaction_pooler_shape_errors(kind: str, expected_shape: dict[str, Any], shape: Any) -> list[str]:
    if not isinstance(shape, dict):
        return [f"supabase_recovery_packet_json accepted_transaction_pooler_shapes missing {kind}"]
    return [
        f"supabase_recovery_packet_json {kind}.{key} must match official passwordless shape"
        for key, expected_value in expected_shape.items()
        if shape.get(key) != expected_value
    ]


def _default_getdaytrends_launch_secret_scan_targets(workspace_root: Path) -> list[tuple[str, Path | None]]:
    reports_root = workspace_root / "docs" / "reports"
    var_root = workspace_root / "var"
    return [
        ("next_actions", workspace_root / "next-actions.md"),
        ("handoff", workspace_root / "HANDOFF.md"),
        ("getdaytrends_qc_log", workspace_root / "automation" / "getdaytrends" / "QC_LOG.md"),
        ("getdaytrends_credential_update_script", workspace_root / "ops" / "scripts" / "getdaytrends_update_credentials.py"),
        ("shared_pooler_update_script", workspace_root / "ops" / "scripts" / "apply_workspace_supabase_pooler_url.py"),
        ("shared_pooler_update_wrapper", workspace_root / "ops" / "scripts" / "apply_workspace_supabase_pooler_url.ps1"),
        ("supabase_pooler_management_probe", workspace_root / "ops" / "scripts" / "supabase_pooler_management_probe.py"),
        ("supabase_pooler_shape_audit", workspace_root / "ops" / "scripts" / "supabase_pooler_shape_audit.py"),
        (
            "complete_goal_local_credential_side_channel_audit",
            workspace_root / "ops" / "scripts" / "complete_goal_local_credential_side_channel_audit.py",
        ),
        (
            "complete_goal_no_credential_refresh",
            workspace_root / "ops" / "scripts" / "complete_goal_no_credential_refresh.py",
        ),
        (
            "getdaytrends_supabase_recovery_packet_verifier",
            workspace_root / "automation" / "getdaytrends" / "scripts" / "verify_supabase_recovery_packet.py",
        ),
        (
            "getdaytrends_provider_auth_recovery_packet_verifier",
            workspace_root / "automation" / "getdaytrends" / "scripts" / "verify_provider_auth_recovery_packet.py",
        ),
        (
            "getdaytrends_github_benchmark",
            workspace_root
            / "automation"
            / "getdaytrends"
            / "docs"
            / "GITHUB_BENCHMARK_2026-06-04.md",
        ),
        (
            "launch_audit",
            _latest_existing_match(
                reports_root,
                "20*/GETDAYTRENDS_LAUNCH_COMPLETION_AUDIT*.md",
                "20*/COMPLETE_GOAL_STATUS_AUDIT_CURRENT*.md",
                "20*/COMPLETE_GOAL_PROMPT_TO_ARTIFACT_CHECKLIST_CURRENT*.md",
                "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS_STATUS_GATE*.md",
                "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS*.md",
            ),
        ),
        (
            "cycle_report",
            _latest_existing_match(
                reports_root,
                "20*/AUTO_RESEARCH_GETDAYTRENDS_*.md",
                "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS*.md",
                exclude_name_contains=("_STATUS_",),
            ),
        ),
        (
            "operator_status",
            _latest_existing_match(
                reports_root,
                "20*/AUTO_RESEARCH_GETDAYTRENDS_*STATUS*.md",
                "20*/COMPLETE_GOAL_STATUS_AUDIT_CURRENT*.md",
                "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS_STATUS_GATE*.md",
                "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS*.md",
            ),
        ),
        (
            "supabase_external_repair_packet",
            _latest_match(reports_root, "20*/GETDAYTRENDS_SUPABASE_EXTERNAL_REPAIR_PACKET*.md"),
        ),
        (
            "completion_blocker_model_split",
            _latest_existing_match(reports_root, "20*/AUTO_RESEARCH_COMPLETION_BLOCKER_MODEL_SPLIT*.md"),
        ),
        (
            "modernization_report",
            _latest_match(reports_root, "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS*.md"),
        ),
        (
            "operator_status_json",
            _latest_match(var_root, "auto-research-status-getdaytrends*.json"),
        ),
        (
            "modernization_json",
            _latest_match(var_root, "github-modernization-radar-getdaytrends*.json"),
        ),
    ]


def _current_getdaytrends_launch_artifact_targets(workspace_root: Path) -> list[tuple[str, Path]]:
    project_root = workspace_root / "automation" / "getdaytrends"
    logs_root = project_root / "logs"
    var_root = workspace_root / "var"
    return [
        ("current_radar", _latest_match(var_root, "github-modernization-radar-getdaytrends*.json")),
        ("current_workspace_smoke", _latest_workspace_smoke_match(var_root)),
        ("current_cli_smoke", logs_root / "smoke" / "cli_smoke_latest.json"),
        ("current_dashboard_browser_smoke", _latest_dashboard_browser_smoke_match(logs_root / "smoke")),
        ("current_tap_fixture_browser_smoke", logs_root / "smoke" / "dashboard_browser_tap_source_evidence.json"),
        ("current_readiness", logs_root / "readiness" / "readiness_latest.json"),
        ("current_strict_readiness", logs_root / "readiness" / "strict_readiness_latest.json"),
        ("current_supabase_recovery_packet", logs_root / "readiness" / "supabase_recovery_packet_latest.json"),
        (
            "current_strict_supabase_recovery_packet",
            logs_root / "readiness" / "strict_supabase_recovery_packet_latest.json",
        ),
        (
            "current_provider_auth_recovery_packet",
            logs_root / "readiness" / "provider_auth_recovery_packet_latest.json",
        ),
        (
            "current_strict_provider_auth_recovery_packet",
            logs_root / "readiness" / "strict_provider_auth_recovery_packet_latest.json",
        ),
        ("current_text_hygiene", logs_root / "hygiene" / "text_hygiene_latest.json"),
    ]


def _latest_workspace_smoke_match(var_root: Path) -> Path:
    matches = [
        path
        for path in var_root.glob("workspace-smoke-getdaytrends*.json")
        if path.is_file()
    ]
    if not matches:
        return var_root / "workspace-smoke-getdaytrendsmissing.json"
    return max(matches, key=_workspace_smoke_recency_key)


def _workspace_smoke_recency_key(path: Path) -> tuple[int, int, int, int, float, float]:
    payload = _json_payload(path)
    generated_ts = _payload_generated_timestamp(payload)
    complete_rank, total_rank = _workspace_smoke_completion_rank(payload)
    return (
        complete_rank,
        total_rank,
        _workspace_smoke_runtime_proof_rank(path),
        _timestamp_rank(generated_ts),
        generated_ts,
        _path_mtime(path),
    )


def _json_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_generated_timestamp(payload: dict[str, Any]) -> float:
    generated_at = str(payload.get("generated_at") or "").strip()
    if not generated_at:
        return float("-inf")
    try:
        return datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def _workspace_smoke_completion_rank(payload: dict[str, Any]) -> tuple[int, int]:
    summary = _dict_child(payload, "summary")
    total = _coerce_int(summary.get("total"))
    completed = _coerce_int(summary.get("completed"))
    remaining = _coerce_int(summary.get("remaining"))
    if _workspace_smoke_complete(payload, total, completed, remaining):
        return 1, total
    return 0, 0


def _workspace_smoke_complete(payload: dict[str, Any], total: int, completed: int, remaining: int) -> bool:
    return _status_is_complete(payload) and _completion_count_is_complete(total, completed) and remaining == 0


def _status_is_complete(payload: dict[str, Any]) -> bool:
    return str(payload.get("status") or "").strip().lower() == "complete"


def _completion_count_is_complete(total: int, completed: int) -> bool:
    return total == 0 or completed == 0 or completed >= total


def _workspace_smoke_runtime_proof_rank(path: Path) -> int:
    return 0 if path.name == "workspace-smoke-getdaytrends-launch-final.json" else 1


def _timestamp_rank(generated_ts: float) -> int:
    return 1 if generated_ts != float("-inf") else 0


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _latest_dashboard_browser_smoke_match(smoke_root: Path) -> Path:
    matches = [
        path
        for path in smoke_root.glob("dashboard_browser*.json")
        if path.is_file() and "tap_source" not in path.name
    ]
    if not matches:
        return smoke_root / "dashboard_browser_latest.json"
    return max(matches, key=_json_artifact_recency_key)


def _json_artifact_recency_key(path: Path) -> tuple[int, float, float]:
    generated_ts = _payload_generated_timestamp(_json_payload(path))
    return (_timestamp_rank(generated_ts), generated_ts, _path_mtime(path))


def _latest_match(
    root: Path,
    pattern: str,
    *,
    exclude_name_contains: tuple[str, ...] = (),
) -> Path:
    return _latest_or_missing(_matching_files(root, pattern, exclude_name_contains), root, pattern)


def _latest_existing_match(
    root: Path,
    *patterns: str,
    exclude_name_contains: tuple[str, ...] = (),
) -> Path | None:
    for pattern in patterns:
        matches = _matching_files(root, pattern, exclude_name_contains)
        if matches:
            return max(matches, key=lambda path: path.stat().st_mtime)
    return None


def _matching_files(root: Path, pattern: str, exclude_name_contains: tuple[str, ...]) -> list[Path]:
    return [path for path in root.glob(pattern) if _path_matches(path, exclude_name_contains)]


def _path_matches(path: Path, exclude_name_contains: tuple[str, ...]) -> bool:
    return path.is_file() and not any(marker in path.name for marker in exclude_name_contains)


def _latest_or_missing(matches: list[Path], root: Path, pattern: str) -> Path:
    if matches:
        return max(matches, key=lambda path: path.stat().st_mtime)
    # Return a deterministic path so the scan reports the missing target.
    return root / pattern.replace("*", "missing")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan getdaytrends launch handoff artifacts for value-shaped secrets.")
    parser.add_argument("--path", action="append", type=Path, default=[], help="Additional file to scan.")
    parser.add_argument("--json-out", type=Path, help="Write the machine-readable scan report.")
    parser.add_argument(
        "--include-current-artifacts",
        action="store_true",
        help="Also scan current readiness, recovery, browser, CLI smoke, and workspace-smoke artifacts.",
    )
    parser.add_argument("--allow-missing", action="store_true", help="Do not fail when a default scan target is missing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, workspace_root: Path = WORKSPACE_ROOT) -> int:
    args = _parse_args(argv)
    report = build_getdaytrends_launch_secret_scan(
        workspace_root=workspace_root,
        extra_paths=args.path,
        include_current_artifacts=args.include_current_artifacts,
    )
    _write_report_if_requested(args.json_out, report)
    findings = _list_child(report, "findings")
    missing = _list_child(report, "missing_paths")
    contract_errors = _list_child(report, "supabase_recovery_packet_contract_errors")
    ok = _cli_scan_passed(report, findings, missing, contract_errors, allow_missing=args.allow_missing)
    _print_scan_summary(report, findings, missing)
    _print_finding_patterns(findings)
    _print_missing_paths(missing, allow_missing=args.allow_missing)
    _print_contract_errors(contract_errors)
    return 0 if ok else 1


def _write_report_if_requested(json_out: Path | None, report: dict[str, Any]) -> None:
    if json_out:
        _write_json(json_out, report)


def _list_child(report: dict[str, Any], key: str) -> list[Any]:
    value = report.get(key)
    return value if isinstance(value, list) else []


def _cli_scan_passed(
    report: dict[str, Any],
    findings: list[Any],
    missing: list[Any],
    contract_errors: list[Any],
    *,
    allow_missing: bool,
) -> bool:
    return report.get("status") == "valid" and not findings and (allow_missing or not missing) and not contract_errors


def _print_scan_summary(report: dict[str, Any], findings: list[Any], missing: list[Any]) -> None:
    print(
        "getdaytrends launch secret scan: "
        f"status={report.get('status')} "
        f"findings={len(findings)} "
        f"missing={len(missing)} "
        f"scanned={len(report.get('scanned_paths') or [])}"
    )


def _print_finding_patterns(findings: list[Any]) -> None:
    if findings:
        print(f"finding patterns: {','.join(_finding_patterns(findings)) or 'none'}", file=sys.stderr)


def _finding_patterns(findings: list[Any]) -> list[str]:
    return sorted(
        {
            pattern
            for finding in findings
            for pattern in _finding_pattern_values(finding)
            if isinstance(pattern, str)
        }
    )


def _finding_pattern_values(finding: Any) -> list[Any]:
    return finding.get("patterns", []) if isinstance(finding, dict) else []


def _print_missing_paths(missing: list[Any], *, allow_missing: bool) -> None:
    if missing and not allow_missing:
        print(f"missing paths: {','.join(str(path) for path in missing)}", file=sys.stderr)


def _print_contract_errors(contract_errors: list[Any]) -> None:
    if contract_errors:
        print("supabase recovery packet contract errors:", file=sys.stderr)
        for error in contract_errors:
            print(f"- {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
