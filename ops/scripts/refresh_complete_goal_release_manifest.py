from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from complete_goal_gate_common import (
    CURRENT_DATE_STAMP,
    RECOVERY_FULL_MATRIX_JSON_REL,
    RECOVERY_FULL_MATRIX_MARKDOWN_REL,
    RECOVERY_PREFLIGHT_JSON_REL,
    RECOVERY_PREFLIGHT_MARKDOWN_REL,
    REPORT_MONTH,
    WORKSPACE_ROOT,
    copy_snapshot,
    current_recovery_report_path,
    latest_match,
    load_json,
    parse_dt,
    rel_path,
    write_json,
)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_MANIFEST = WORKSPACE_ROOT / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
DEFAULT_JSON_OUT = WORKSPACE_ROOT / "var" / f"complete-goal-release-manifest-refresh-current-{CURRENT_DATE_STAMP}.json"
NO_CREDENTIAL_REFRESH_VALID_STATUSES = {"blocked_expected_external", "ready_to_rerun"}
RELEASE_EVIDENCE_REFRESH_VALID_STATUSES = {"approval_ready", "blocked_expected_external"}
JSON_METADATA_PREFIX_CHARS = 64 * 1024
SNAPSHOT_FALLBACK_SCAN_LIMIT = 80

SNAPSHOT_SOURCES = [
    (
        "complete-goal-status-audit",
        lambda root: _current_or_latest_var_artifact(
            root, f"complete-goal-status-audit-current-{CURRENT_DATE_STAMP}.json", "complete-goal-status-audit-current-*.json"
        ),
    ),
    ("mcp-inventory-health-bridge-config", lambda root: latest_match(root / "var", "mcp-inventory-health-bridge-config*.json")),
    ("mcp-inventory-health-bridge-live", lambda root: latest_match(root / "var", "mcp-inventory-health-bridge-live*.json")),
    (
        "mcp-direct-session-probe",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-direct-session-probe-current-{CURRENT_DATE_STAMP}.json", "mcp-direct-session-probe-current-*.json"
        ),
    ),
    (
        "mcp-stale-process-audit",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-stale-process-audit-current-{CURRENT_DATE_STAMP}.json", "mcp-stale-process-audit-current-*.json"
        ),
    ),
    (
        "mcp-stale-process-cleanup-plan",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-stale-process-cleanup-plan-current-{CURRENT_DATE_STAMP}.json", "mcp-stale-process-cleanup-plan-current-*.json"
        ),
    ),
    (
        "mcp-process-owner-detail",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-process-owner-detail-current-{CURRENT_DATE_STAMP}.json", "mcp-process-owner-detail-current-*.json"
        ),
    ),
    (
        "mcp-manual-cleanup-checklist",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-manual-cleanup-checklist-current-{CURRENT_DATE_STAMP}.json", "mcp-manual-cleanup-checklist-current-*.json"
        ),
    ),
    (
        "mcp-cleanup-readiness",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-cleanup-readiness-current-{CURRENT_DATE_STAMP}.json", "mcp-cleanup-readiness-current-*.json"
        ),
    ),
    (
        "mcp-connector-auth-readiness",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-connector-auth-readiness-current-{CURRENT_DATE_STAMP}.json", "mcp-connector-auth-readiness-current-*.json"
        ),
    ),
    (
        "mcp-auth-diagnostic",
        lambda root: _current_or_latest_var_artifact(
            root, f"mcp-auth-diagnostic-current-{CURRENT_DATE_STAMP}.json", "mcp-auth-diagnostic-current-*.json"
        ),
    ),
    (
        "complete-goal-unblock-gate",
        lambda root: _current_or_latest_var_artifact(
            root, f"complete-goal-unblock-gate-current-{CURRENT_DATE_STAMP}.json", "complete-goal-unblock-gate-current-*.json"
        ),
    ),
    (
        "workspace-external-credential-recovery-refresh",
        lambda root: _current_or_latest_recovery_report(root),
    ),
    (
        "complete-goal-local-credential-side-channel-audit",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-local-credential-side-channel-audit-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-local-credential-side-channel-audit-current-*.json",
        ),
    ),
    (
        "complete-goal-no-credential-refresh",
        lambda root: _current_or_latest_var_artifact(
            root, f"complete-goal-no-credential-refresh-current-{CURRENT_DATE_STAMP}.json", "complete-goal-no-credential-refresh-current-*.json"
        ),
    ),
    (
        "complete-goal-release-evidence-refresh",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-release-evidence-refresh-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-release-evidence-refresh-current-*.json",
        ),
    ),
    (
        "supabase-pooler-shape-audit",
        lambda root: _current_or_latest_var_artifact(
            root, f"supabase-pooler-shape-audit-current-{CURRENT_DATE_STAMP}.json", "supabase-pooler-shape-audit-current-*.json"
        ),
    ),
    ("complete-goal-scheduled-task-pause", lambda root: latest_match(root / "var", "complete-goal-scheduled-task-pause-current*.json")),
    (
        "complete-goal-scheduled-task-resume",
        lambda root: _current_or_latest_var_artifact(
            root, f"complete-goal-scheduled-task-resume-current-{CURRENT_DATE_STAMP}.json", "complete-goal-scheduled-task-resume-current-*.json"
        ),
    ),
    (
        "dailynews-post-supabase-credential-input-status",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"dailynews-post-supabase-credential-input-status-current-{CURRENT_DATE_STAMP}.json",
            "dailynews-post-supabase-credential-input-status-current-*.json",
        ),
    ),
    ("dailynews-supabase-external-repair-packet", lambda root: root / "var" / "dailynews-supabase-external-repair-packet-2026-06-06.json"),
    ("dailynews-db-pooler-username-variant-probes", lambda root: latest_match(root / "var", "dailynews-db-pooler-username-variant-probes-current-*.json")),
    ("dailynews-db-direct-host-probe", lambda root: latest_match(root / "var", "dailynews-db-direct-host-probe-current-*.json")),
    ("dailynews-first-run-verifier", lambda root: _latest_dailynews_first_run_verifier(root)),
    ("dailynews-x-ops-browser-smoke", lambda root: _latest_dailynews_x_ops_browser_smoke(root)),
    ("dailynews-runner-preflight-morning", lambda root: latest_match(root / "var", "dailynews-runner-preflight-morning-*.json")),
    (
        "dailynews-launch-secret-scan-final",
        lambda root: _current_or_latest_var_artifact(
            root, f"dailynews-launch-secret-scan-final-{CURRENT_DATE_STAMP}.json", "dailynews-launch-secret-scan-final-*.json"
        ),
    ),
    (
        "complete-goal-report-secret-scan-refresh",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-report-secret-scan-refresh-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-report-secret-scan-refresh-current-*.json",
        ),
    ),
    (
        "complete-goal-prompt-to-artifact-checklist",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-prompt-to-artifact-checklist-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-prompt-to-artifact-checklist-current-*.json",
        ),
    ),
    (
        "complete-goal-report-secret-scan-dailynews",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-report-secret-scan-dailynews-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-report-secret-scan-dailynews-current-*.json",
        ),
    ),
    (
        "supabase-pooler-management-probe",
        lambda root: _current_or_latest_var_artifact(
            root, f"supabase-pooler-management-probe-current-{CURRENT_DATE_STAMP}.json", "supabase-pooler-management-probe-current-*.json"
        ),
    ),
    (
        "getdaytrends-credential-input-status",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"getdaytrends-credential-input-status-current-{CURRENT_DATE_STAMP}.json",
            "getdaytrends-credential-input-status-current-*.json",
            alias_name="getdaytrends-credential-input-status-current.json",
        ),
    ),
    (
        "getdaytrends-launch-secret-scan-final",
        lambda root: _current_or_latest_var_artifact(
            root, f"getdaytrends-launch-secret-scan-final-{CURRENT_DATE_STAMP}.json", "getdaytrends-launch-secret-scan-final-*.json"
        ),
    ),
    (
        "complete-goal-report-secret-scan-getdaytrends",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-report-secret-scan-getdaytrends-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-report-secret-scan-getdaytrends-current-*.json",
        ),
    ),
    ("getdaytrends-readiness", lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json"),
    (
        "getdaytrends-strict-readiness",
        lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "strict_readiness_latest.json",
    ),
    (
        "getdaytrends-provider-auth-recovery-packet",
        lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json",
    ),
    (
        "getdaytrends-strict-provider-auth-recovery-packet",
        lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "strict_provider_auth_recovery_packet_latest.json",
    ),
    (
        "getdaytrends-supabase-recovery-packet",
        lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "supabase_recovery_packet_latest.json",
    ),
    (
        "getdaytrends-strict-supabase-recovery-packet",
        lambda root: root / "automation" / "getdaytrends" / "logs" / "readiness" / "strict_supabase_recovery_packet_latest.json",
    ),
    ("workspace-smoke-getdaytrends-launch-final", lambda root: _latest_getdaytrends_workspace_smoke(root)),
    ("getdaytrends-dashboard-browser", lambda root: root / "automation" / "getdaytrends" / "logs" / "smoke" / "dashboard_browser_latest.json"),
    (
        "complete-goal-evidence-consistency",
        lambda root: _current_or_latest_var_artifact(
            root,
            f"complete-goal-evidence-consistency-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-evidence-consistency-current-*.json",
        ),
    ),
]

REQUIRED_CHANGED_PATHS = [
    "ops/scripts/complete_goal_gate_common.py",
    "ops/scripts/apply_workspace_supabase_pooler_url.py",
    "ops/scripts/apply_workspace_supabase_pooler_url.ps1",
    "ops/scripts/dailynews_update_database_url.py",
    "ops/scripts/getdaytrends_update_credentials.py",
    "ops/scripts/generate_context_snapshot.py",
    "ops/scripts/run_workspace_smoke.py",
    "ops/scripts/session_bootstrap.py",
    "ops/scripts/workspace_smoke_report.py",
    "ops/scripts/check_mcp_health.py",
    "ops/scripts/mcp_service_inventory.py",
    "ops/scripts/mcp_inventory_health_bridge.py",
    "ops/scripts/mcp_stale_process_audit.py",
    "ops/scripts/mcp_stale_process_cleanup_plan.py",
    "ops/scripts/mcp_process_owner_detail_probe.py",
    "ops/scripts/mcp_manual_cleanup_checklist.py",
    "ops/scripts/mcp_cleanup_readiness_verifier.py",
    "ops/scripts/mcp_connector_auth_readiness_report.py",
    "ops/scripts/diagnose_mcp_auth.py",
    "ops/scripts/supabase_pooler_management_probe.py",
    "ops/scripts/supabase_pooler_shape_audit.py",
    "ops/scripts/auto_research_status.py",
    "ops/scripts/dailynews_launch_secret_scan.py",
    "ops/scripts/getdaytrends_launch_handoff_refresh.py",
    "ops/scripts/getdaytrends_launch_secret_scan.py",
    "ops/scripts/complete_goal_report_secret_scan_refresh.py",
    "ops/scripts/complete_goal_prompt_to_artifact_checklist.py",
    "ops/scripts/refresh_complete_goal_release_manifest.py",
    "ops/scripts/complete_goal_evidence_consistency_check.py",
    "ops/scripts/complete_goal_no_credential_refresh.py",
    "ops/scripts/complete_goal_release_evidence_refresh.py",
    "ops/scripts/release_approval_check.py",
    "ops/scripts/complete_goal_unblock_gate.py",
    "ops/scripts/complete_goal_resume_scheduled_tasks.py",
    "automation/getdaytrends/scripts/verify_supabase_recovery_packet.py",
    "automation/getdaytrends/scripts/verify_provider_auth_recovery_packet.py",
    "tests/test_apply_workspace_supabase_pooler_url.py",
    "tests/test_dailynews_update_database_url.py",
    "tests/test_getdaytrends_update_credentials.py",
    "tests/test_workspace_smoke.py",
    "tests/test_ops_scripts_reports.py",
    "tests/test_mcp_service_inventory.py",
    "tests/test_mcp_inventory_health_bridge.py",
    "tests/test_mcp_stale_process_audit.py",
    "tests/test_mcp_stale_process_cleanup_plan.py",
    "tests/test_mcp_process_owner_detail_probe.py",
    "tests/test_mcp_manual_cleanup_checklist.py",
    "tests/test_mcp_cleanup_readiness_verifier.py",
    "tests/test_mcp_connector_auth_readiness_report.py",
    "tests/test_diagnose_mcp_auth.py",
    "tests/test_supabase_pooler_management_probe.py",
    "tests/test_supabase_pooler_shape_audit.py",
    "tests/test_auto_research_status.py",
    "tests/test_dailynews_launch_secret_scan.py",
    "tests/test_getdaytrends_launch_handoff_refresh.py",
    "tests/test_getdaytrends_launch_secret_scan.py",
    "tests/test_complete_goal_report_secret_scan_refresh.py",
    "tests/test_complete_goal_prompt_to_artifact_checklist.py",
    "tests/test_refresh_complete_goal_release_manifest.py",
    "tests/test_complete_goal_evidence_consistency_check.py",
    "tests/test_complete_goal_no_credential_refresh.py",
    "tests/test_complete_goal_release_evidence_refresh.py",
    "tests/test_release_approval_check.py",
    "tests/test_complete_goal_unblock_gate.py",
    "tests/test_complete_goal_resume_scheduled_tasks.py",
    "automation/getdaytrends/tests/test_verify_recovery_packet_scripts.py",
    "docs/QUALITY_GATE.md",
]


def _snapshot_recency_key(path: Path) -> tuple[float, float]:
    generated = None
    try:
        generated = parse_dt(load_json(path).get("generated_at"))
    except Exception:
        generated = None
    return (generated.timestamp() if generated else float("-inf"), path.stat().st_mtime)


def _snapshot_file_order_key(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return float("-inf")


def _no_credential_refresh_status_valid(path: Path | None) -> bool:
    payload = _load_existing_json(path)
    if not payload:
        return False
    status = payload.get("status")
    if status == "ready_to_rerun":
        return _ready_to_rerun_no_credential_refresh_valid(payload)
    if status == "blocked_expected_external":
        return _blocked_no_credential_refresh_valid(payload)
    return False


def _ready_to_rerun_no_credential_refresh_valid(payload: dict[str, Any]) -> bool:
    summary = _dict_child(payload, "summary")
    unblock = _dict_child(summary, "unblock")
    release_evidence = _dict_child(summary, "release_evidence")
    return (
        payload.get("ok") is False
        and unblock.get("status") in {"ready_to_rerun", "complete_ready"}
        and release_evidence.get("ran") is False
        and "post_write_finalization" not in payload
    )


def _blocked_no_credential_refresh_valid(payload: dict[str, Any]) -> bool:
    summary = _dict_child(payload, "summary")
    release_evidence = _dict_child(summary, "release_evidence")
    post_summary = _dict_child(summary, "post_write_finalization")
    finalization = _dict_child(payload, "post_write_finalization")
    return (
        payload.get("ok") is False
        and summary.get("failed_step_count") == 0
        and summary.get("failed_steps") == []
        and release_evidence.get("ran") is True
        and _blocked_no_credential_release_evidence_valid(release_evidence, post_summary, finalization)
        and _no_credential_post_write_summary_valid(post_summary)
        and _no_credential_finalization_valid(finalization)
    )


def _blocked_no_credential_release_evidence_valid(
    release_evidence: dict[str, Any],
    post_summary: dict[str, Any],
    finalization: dict[str, Any],
) -> bool:
    if release_evidence.get("status") == "blocked_expected_external":
        return (
            release_evidence.get("unexpected_failed_step_count") == 0
            and release_evidence.get("release_generated_after_unblock") is True
            and release_evidence.get("release_generated_after_side_channel") is True
        )
    return (
        release_evidence.get("status") == "pending_bootstrap"
        and release_evidence.get("unexpected_failed_step_count") == 0
        and release_evidence.get("bootstrap_pending_release_evidence") is True
        and post_summary.get("bootstrap_pending_release_evidence") is True
        and finalization.get("bootstrap_pending_release_evidence") is True
    )


def _no_credential_post_write_summary_valid(post_summary: dict[str, Any]) -> bool:
    return (
        post_summary.get("ok") is True
        and post_summary.get("snapshot_matches_report_generated_at") is True
        and post_summary.get("release_approval_status") == "blocked_expected_external"
        and post_summary.get("release_approval_unexpected_failures") == []
    )


def _no_credential_finalization_valid(finalization: dict[str, Any]) -> bool:
    manifest = _dict_child(finalization, "manifest")
    snapshot = _dict_child(manifest, "no_credential_snapshot")
    approval = _dict_child(finalization, "release_approval")
    analysis = _dict_child(approval, "failure_analysis")
    return (
        finalization.get("ok") is True
        and snapshot.get("present") is True
        and snapshot.get("matches_report_generated_at") is True
        and analysis.get("status") == "blocked_expected_external"
        and analysis.get("unexpected_failures") == []
    )


def _release_evidence_refresh_status_valid(path: Path | None) -> bool:
    payload = _load_existing_json(path)
    if not payload:
        return False
    status = payload.get("status")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    release_approval = _dict_child(summary, "release_approval")
    failure_analysis = _dict_child(release_approval, "failure_analysis")
    checks = [
        _release_evidence_status_allowed(status),
        _local_release_gates_ok(summary),
        _release_consistency_ok(summary),
        _release_approval_generated_after_manifest(release_approval),
        _release_approval_status_valid(status, release_approval, failure_analysis),
    ]
    return all(checks)


def _release_evidence_status_allowed(status: Any) -> bool:
    return status in RELEASE_EVIDENCE_REFRESH_VALID_STATUSES


def _load_existing_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        payload = load_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _dict_child(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _local_release_gates_ok(summary: dict[str, Any]) -> bool:
    return all(_summary_gate_ok(summary, name) for name in _local_release_gate_names())


def _local_release_gate_names() -> list[str]:
    return [
        "operator_action_coverage",
        "operator_action_markdown_command_coverage",
        "operator_action_phase_coverage",
        "operator_action_safety_coverage",
        "operator_action_evidence_path_coverage",
        "operator_action_command_output_coverage",
        "current_artifact_unexpected_state_coverage",
        "live_source_detail_coverage",
        "consistency",
    ]


def _summary_gate_ok(summary: dict[str, Any], name: str) -> bool:
    return _dict_child(summary, name).get("ok") is True


def _release_consistency_ok(summary: dict[str, Any]) -> bool:
    consistency = _dict_child(summary, "consistency")
    consistency_summary = _dict_child(consistency, "summary")
    return consistency.get("status") in {"ok", None} and consistency_summary.get("failed", 0) == 0


def _release_approval_generated_after_manifest(release_approval: dict[str, Any]) -> bool:
    return release_approval.get("generated_after_final_manifest_refresh") is True


def _release_approval_status_valid(
    status: Any,
    release_approval: dict[str, Any],
    failure_analysis: dict[str, Any],
) -> bool:
    if status == "approval_ready":
        return release_approval.get("ok") is True and failure_analysis.get("status") == "approved"
    return _blocked_expected_external_release_approval(release_approval, failure_analysis)


def _blocked_expected_external_release_approval(
    release_approval: dict[str, Any],
    failure_analysis: dict[str, Any],
) -> bool:
    return (
        release_approval.get("ok") is False
        and failure_analysis.get("status") == "blocked_expected_external"
        and failure_analysis.get("unexpected_failures") == []
    )


def _latest_valid_no_credential_snapshot(root: Path, label: str) -> Path | None:
    return _latest_valid_snapshot_from_recent_dirs(root, label, _no_credential_refresh_status_valid)


def _latest_valid_release_evidence_snapshot(root: Path, label: str) -> Path | None:
    return _latest_valid_snapshot_from_recent_dirs(root, label, _release_evidence_refresh_status_valid)


def _latest_valid_snapshot_from_recent_dirs(root: Path, label: str, validator: Any) -> Path | None:
    snapshot_root = root / "var" / "release-approval-snapshots"
    current_snapshot_dir = snapshot_root / CURRENT_DATE_STAMP
    selected = _latest_valid_snapshot_in_date_dir(current_snapshot_dir, label, validator)
    if selected:
        return selected
    for date_dir in _snapshot_date_dirs_newest_first(snapshot_root, exclude=current_snapshot_dir):
        selected = _latest_valid_snapshot_in_date_dir(date_dir, label, validator)
        if selected:
            return selected
    return None


def _snapshot_date_dirs_newest_first(snapshot_root: Path, *, exclude: Path) -> list[Path]:
    if not snapshot_root.exists():
        return []
    excluded = exclude.resolve()
    dirs = [path for path in snapshot_root.iterdir() if path.is_dir() and _resolved_path(path) != excluded]
    return sorted(dirs, key=_snapshot_dir_recency_key, reverse=True)


def _latest_valid_snapshot_in_date_dir(date_dir: Path, label: str, validator: Any) -> Path | None:
    if not date_dir.exists():
        return None
    for search_dir in _snapshot_search_dirs_newest_first(date_dir):
        candidates = _valid_snapshot_candidates(search_dir, (f"{label}-*.json",), validator)
        if candidates:
            return _latest_snapshot_candidate(candidates)
    return None


def _snapshot_search_dirs_newest_first(date_dir: Path) -> list[Path]:
    run_dirs = [path for path in date_dir.iterdir() if path.is_dir()]
    return [*sorted(run_dirs, key=_snapshot_dir_recency_key, reverse=True), date_dir]


def _snapshot_dir_recency_key(path: Path) -> tuple[str, float]:
    return (path.name, path.stat().st_mtime)


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _valid_snapshot_candidates(
    root: Path,
    patterns: Sequence[str],
    validator: Any,
) -> list[Path]:
    paths = [path for pattern in patterns for path in root.glob(pattern) if path.is_file()]
    return [path for path in _most_recent_snapshot_paths(paths) if validator(path)]


def _most_recent_snapshot_paths(paths: list[Path]) -> list[Path]:
    unique_paths = sorted(set(paths), key=_snapshot_file_order_key, reverse=True)
    return unique_paths[:SNAPSHOT_FALLBACK_SCAN_LIMIT]


def _latest_snapshot_candidate(candidates: list[Path]) -> Path | None:
    return max(candidates, key=_snapshot_recency_key) if candidates else None


def _current_or_latest_var_artifact(
    root: Path,
    current_name: str,
    fallback_pattern: str,
    *,
    alias_name: str | None = None,
) -> Path:
    current = root / "var" / current_name
    alias = root / "var" / alias_name if alias_name else None
    current_candidates = [path for path in (current, alias) if path is not None and path.exists()]
    if current_candidates:
        return max(current_candidates, key=_json_artifact_recency_key)
    latest = latest_match(root / "var", fallback_pattern)
    if latest is not None and latest.exists():
        return latest
    return current


def _latest_dailynews_first_run_verifier(root: Path) -> Path | None:
    return _latest_json_artifact(
        root / "var",
        "dailynews-first-run-verifier-operator-recheck-*.json",
        "dailynews-first-run-verifier-current-*.json",
        "dailynews-first-run-verifier*.json",
        exclude_name_contains=("-smoke-",),
        required_key="launch_ready",
    )


def _latest_dailynews_x_ops_browser_smoke(root: Path) -> Path | None:
    return _latest_json_artifact(
        root / "var",
        "dailynews-x-ops-browser-smoke-current-*.json",
        "dailynews-x-ops-browser-smoke*.json",
    )


def _latest_json_artifact(
    root: Path,
    *patterns: str,
    exclude_name_contains: tuple[str, ...] = (),
    required_key: str = "",
) -> Path | None:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file() or path in seen:
                continue
            if any(marker in path.name for marker in exclude_name_contains):
                continue
            if required_key and not _json_payload_has_key(path, required_key):
                continue
            seen.add(path)
            candidates.append(path)
    return max(candidates, key=_json_artifact_recency_key) if candidates else None


def _json_payload_has_key(path: Path, key: str) -> bool:
    if _json_prefix_has_top_level_key(path, key):
        return True
    try:
        return key in load_json(path)
    except Exception:
        return False


def _json_artifact_recency_key(path: Path) -> tuple[float, float]:
    generated = None
    generated_at = _json_prefix_string_value(path, "generated_at")
    if generated_at:
        generated = parse_dt(generated_at)
    if generated is None:
        try:
            generated = parse_dt(load_json(path).get("generated_at"))
        except Exception:
            generated = None
    return (generated.timestamp() if generated else float("-inf"), path.stat().st_mtime)


def _json_prefix_has_top_level_key(path: Path, key: str) -> bool:
    prefix = _json_metadata_prefix(path)
    if not prefix:
        return False
    return _json_top_level_key_pattern(key).search(prefix) is not None


def _json_prefix_string_value(path: Path, key: str) -> str:
    prefix = _json_metadata_prefix(path)
    if not prefix:
        return ""
    match = _json_top_level_string_pattern(key).search(prefix)
    if not match:
        return ""
    try:
        return str(json.loads(f'"{match.group(1)}"'))
    except json.JSONDecodeError:
        return ""


def _json_metadata_prefix(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            return handle.read(JSON_METADATA_PREFIX_CHARS)
    except OSError:
        return ""


def _json_top_level_key_pattern(key: str) -> re.Pattern[str]:
    return re.compile(rf'(?:^|[{{,])\s*"{re.escape(key)}"\s*:')


def _json_top_level_string_pattern(key: str) -> re.Pattern[str]:
    return re.compile(rf'(?:^|[{{,])\s*"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"')


def _current_or_latest_recovery_report(root: Path) -> Path:
    current = current_recovery_report_path(root)
    if current.exists():
        return current
    return (
        latest_match(
            root / "var",
            "workspace-external-credential-recovery-refresh-current-full-matrix-*.json",
            "workspace-external-credential-recovery-refresh-preflight-current-*.json",
        )
        or current
    )


def _source_or_latest_snapshot(root: Path, label: str, source: Path | None) -> Path | None:
    if label == "complete-goal-no-credential-refresh":
        return _no_credential_source_or_latest(root, label, source)
    if label == "complete-goal-release-evidence-refresh":
        return _release_evidence_source_or_latest(root, label, source)
    if source and source.exists():
        return source
    return _latest_generic_snapshot(root, label)


def _no_credential_source_or_latest(root: Path, label: str, source: Path | None) -> Path | None:
    if _no_credential_refresh_status_valid(source):
        return source
    return _latest_valid_no_credential_snapshot(root, label)


def _release_evidence_source_or_latest(root: Path, label: str, source: Path | None) -> Path | None:
    if _release_evidence_refresh_status_valid(source):
        return source
    return _latest_valid_release_evidence_snapshot(root, label) or (source if source and source.exists() else None)


def _latest_generic_snapshot(root: Path, label: str) -> Path | None:
    snapshot_root = root / "var" / "release-approval-snapshots"
    current_snapshot_dir = snapshot_root / CURRENT_DATE_STAMP
    current_match = latest_match(current_snapshot_dir, f"{label}-*.json", f"*/{label}-*.json")
    if current_match:
        return current_match
    return latest_match(snapshot_root, f"*/{label}-*.json", f"*/*/{label}-*.json")


def _safe_snapshot_label(value: str, *, index: int) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower()
    safe = _collapse_snapshot_label_dashes(safe)
    safe = _truncate_snapshot_label(safe)
    return f"prompt-checklist-evidence-{index:02d}-{safe or 'artifact'}"


def _collapse_snapshot_label_dashes(value: str) -> str:
    while "--" in value:
        value = value.replace("--", "-")
    return value


def _truncate_snapshot_label(value: str) -> str:
    if len(value) > 80:
        return value[:80].rstrip("-")
    return value


def _prompt_checklist_evidence_sources(root: Path) -> list[Path]:
    checklist_path = _current_or_latest_var_artifact(
        root,
        f"complete-goal-prompt-to-artifact-checklist-current-{CURRENT_DATE_STAMP}.json",
        "complete-goal-prompt-to-artifact-checklist-current-*.json",
    )
    checklist = _prompt_checklist_items(checklist_path)
    sources: list[Path] = []
    seen: set[str] = set()
    for item in checklist:
        _append_prompt_evidence_sources(root, item, sources, seen)
    return sources


def _prompt_checklist_items(checklist_path: Path) -> list[dict[str, Any]]:
    payload = _load_optional_json(checklist_path)
    if not payload:
        return []
    checklist = payload.get("checklist")
    return _dict_items(checklist)


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _append_prompt_evidence_sources(
    root: Path,
    item: dict[str, Any],
    sources: list[Path],
    seen: set[str],
) -> None:
    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        return
    missing = _missing_evidence_paths(item)
    for raw_path in evidence:
        source = _prompt_evidence_source(root, raw_path, missing)
        if source is not None:
            _append_unique_source(root, source, sources, seen)


def _missing_evidence_paths(item: dict[str, Any]) -> set[str]:
    missing = item.get("missing_evidence")
    if not isinstance(missing, list):
        return set()
    return {str(path).strip() for path in missing if str(path).strip()}


def _prompt_evidence_source(root: Path, raw_path: Any, missing: set[str]) -> Path | None:
    rel = str(raw_path).strip()
    if _prompt_evidence_missing(rel, missing):
        return None
    path = Path(rel)
    source = path if path.is_absolute() else root / path
    if _existing_file(source):
        return source
    return None


def _prompt_evidence_missing(rel: str, missing: set[str]) -> bool:
    return not rel or rel in missing


def _existing_file(path: Path) -> bool:
    return path.exists() and path.is_file()


def _append_unique_source(root: Path, source: Path, sources: list[Path], seen: set[str]) -> None:
    key = rel_path(source, root)
    if key not in seen:
        seen.add(key)
        sources.append(source)


def _copy_prompt_checklist_evidence_snapshots(
    *,
    workspace_root: Path,
    snapshot_dir: Path,
    stamp: str,
) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []
    for index, source in enumerate(_prompt_checklist_evidence_sources(workspace_root), start=1):
        source_rel = rel_path(source, workspace_root)
        snapshot = copy_snapshot(
            source,
            snapshot_dir,
            _safe_snapshot_label(source_rel, index=index),
            stamp,
            workspace_root,
        )
        snapshots.append({"source_path": source_rel, "snapshot_path": snapshot["path"], "generated_at": snapshot["generated_at"]})
    return snapshots


def _recovery_refresh_command(path: Path, root: Path) -> str:
    selected = rel_path(path, root)
    if selected == RECOVERY_FULL_MATRIX_JSON_REL:
        return (
            "python ops/scripts/workspace_external_credential_recovery_refresh.py --execute --continue-on-failure "
            f"--preflight-unblock-gate --allow-blocked-external --json-out {RECOVERY_FULL_MATRIX_JSON_REL} "
            f"--markdown-out {RECOVERY_FULL_MATRIX_MARKDOWN_REL}"
        )
    return (
        "python ops/scripts/workspace_external_credential_recovery_refresh.py --execute "
        f"--preflight-unblock-gate --allow-blocked-external --json-out {RECOVERY_PREFLIGHT_JSON_REL} "
        f"--markdown-out {RECOVERY_PREFLIGHT_MARKDOWN_REL}"
    )


def _completion_audit_command() -> str:
    radar_markdown = f"docs/reports/{REPORT_MONTH}/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md"
    return (
        "python ops/scripts/auto_research_status.py --check-live-sources --auto-refresh-radar "
        f"--radar-markdown-out {radar_markdown} --require-completion-audit "
        f"--json-out var/complete-goal-status-audit-current-{CURRENT_DATE_STAMP}.json "
        f"--markdown-out docs/reports/{REPORT_MONTH}/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_{CURRENT_DATE_STAMP}.md"
    )


def _gate_ok_from_payload(path: Path | None, *, require_ok: bool = True) -> bool:
    if not path or not path.exists():
        return False
    try:
        payload = load_json(path)
    except Exception:
        return False
    return payload.get("ok") is True if require_ok else payload.get("status") == "complete"


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = load_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _workspace_smoke_recency_key(path: Path) -> tuple[int, int, int, int, float, float]:
    payload = _load_optional_json(path)
    generated_ts = _workspace_smoke_generated_ts(payload)
    summary = _dict_child(payload, "summary")
    total = _coerce_int(summary.get("total"))
    completed = _coerce_int(summary.get("completed"))
    remaining = _coerce_int(summary.get("remaining"))
    complete_rank = _workspace_smoke_complete_rank(payload, total, completed, remaining)
    mtime = _safe_mtime(path)
    return (complete_rank, total, completed, 1 if generated_ts != float("-inf") else 0, generated_ts, mtime, len(path.name))


def _workspace_smoke_generated_ts(payload: dict[str, Any]) -> float:
    generated_at = str(payload.get("generated_at") or "").strip()
    if not generated_at:
        return float("-inf")
    try:
        return datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def _workspace_smoke_complete_rank(payload: dict[str, Any], total: int, completed: int, remaining: int) -> int:
    if _workspace_smoke_is_complete(payload, total, completed, remaining):
        return 1
    return 0


def _workspace_smoke_is_complete(payload: dict[str, Any], total: int, completed: int, remaining: int) -> bool:
    return _workspace_smoke_status_complete(payload) and _workspace_smoke_completion_counts_done(total, completed, remaining)


def _workspace_smoke_status_complete(payload: dict[str, Any]) -> bool:
    return str(payload.get("status") or "").strip().lower() == "complete"


def _workspace_smoke_completion_counts_done(total: int, completed: int, remaining: int) -> bool:
    return (total == 0 or completed == 0 or completed >= total) and remaining == 0


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _latest_getdaytrends_workspace_smoke(root: Path) -> Path:
    var_root = root / "var"
    matches = [path for path in var_root.glob("workspace-smoke-getdaytrends*.json") if path.is_file()]
    if not matches:
        return var_root / "workspace-smoke-getdaytrends-launch-final.json"
    return max(matches, key=_workspace_smoke_recency_key)


def _completion_blockers(status_payload: dict[str, Any]) -> list[str]:
    audit = _dict_child(status_payload, "completion_audit")
    blockers = audit.get("blocking_requirements") or status_payload.get("blocking_requirements") or []
    return [str(item) for item in blockers] if isinstance(blockers, list) else []


def _status_for_blockers(blockers: list[str], names: set[str]) -> str:
    return "blocked" if any(name in blockers for name in names) else "resolved"


def _external_steps(root: Path) -> dict[str, list[dict[str, str]]]:
    context = _external_steps_context(root)
    return {
        "items": [
            _provider_auth_external_step(context),
            _dailynews_external_step(context),
            _getdaytrends_external_step(context),
        ]
    }


def _external_steps_context(root: Path) -> dict[str, Any]:
    status_payload = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"complete-goal-status-audit-current-{CURRENT_DATE_STAMP}.json", "complete-goal-status-audit-current-*.json"
        )
    )
    blockers = _completion_blockers(status_payload)
    daily_input = _load_optional_json(
        _current_or_latest_var_artifact(
            root,
            f"dailynews-post-supabase-credential-input-status-current-{CURRENT_DATE_STAMP}.json",
            "dailynews-post-supabase-credential-input-status-current-*.json",
        )
    )
    get_input = _load_optional_json(
        _current_or_latest_var_artifact(
            root,
            f"getdaytrends-credential-input-status-current-{CURRENT_DATE_STAMP}.json",
            "getdaytrends-credential-input-status-current-*.json",
            alias_name="getdaytrends-credential-input-status-current.json",
        )
    )
    unblock = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"complete-goal-unblock-gate-current-{CURRENT_DATE_STAMP}.json", "complete-goal-unblock-gate-current-*.json"
        )
    )
    recovery_report_path = _current_or_latest_recovery_report(root)
    recovery = _load_optional_json(recovery_report_path)
    side_channel_audit = _load_optional_json(
        _current_or_latest_var_artifact(
            root,
            f"complete-goal-local-credential-side-channel-audit-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-local-credential-side-channel-audit-current-*.json",
        )
    )
    no_credential_refresh = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"complete-goal-no-credential-refresh-current-{CURRENT_DATE_STAMP}.json", "complete-goal-no-credential-refresh-current-*.json"
        )
    )
    shape_audit = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"supabase-pooler-shape-audit-current-{CURRENT_DATE_STAMP}.json", "supabase-pooler-shape-audit-current-*.json"
        )
    )
    resume = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"complete-goal-scheduled-task-resume-current-{CURRENT_DATE_STAMP}.json", "complete-goal-scheduled-task-resume-current-*.json"
        )
    )
    probe = _load_optional_json(latest_match(root / "var", "dailynews-db-pooler-username-variant-probes-current-*.json") or root / "var" / "_missing.json")
    direct_probe = _load_optional_json(latest_match(root / "var", "dailynews-db-direct-host-probe-current-*.json") or root / "var" / "_missing.json")
    management_probe = _load_optional_json(
        _current_or_latest_var_artifact(
            root, f"supabase-pooler-management-probe-current-{CURRENT_DATE_STAMP}.json", "supabase-pooler-management-probe-current-*.json"
        )
    )
    workspace_smoke = _load_optional_json(_latest_getdaytrends_workspace_smoke(root))
    readiness = _load_optional_json(root / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json")
    provider_auth = _load_optional_json(root / "automation" / "getdaytrends" / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json")
    supabase = _load_optional_json(root / "automation" / "getdaytrends" / "logs" / "readiness" / "supabase_recovery_packet_latest.json")
    dashboard = _load_optional_json(root / "automation" / "getdaytrends" / "logs" / "smoke" / "dashboard_browser_latest.json")
    no_credential_release = _dict_child(_dict_child(no_credential_refresh, "summary"), "release_evidence")
    return {
        "root": root,
        "blockers": blockers,
        "daily_input": daily_input,
        "get_input": get_input,
        "unblock": unblock,
        "recovery_report_path": recovery_report_path,
        "recovery": recovery,
        "side_channel_audit": side_channel_audit,
        "no_credential_refresh": no_credential_refresh,
        "no_credential_release": no_credential_release,
        "shape_audit": shape_audit,
        "resume": resume,
        "probe": probe,
        "direct_probe": direct_probe,
        "management_probe": management_probe,
        "workspace_smoke": workspace_smoke,
        "readiness": readiness,
        "provider_auth": provider_auth,
        "supabase": supabase,
        "dashboard": dashboard,
        "resume_statuses": _resume_statuses(resume),
        "guarded_apply": _guarded_apply_text(),
        "daily_status": _status_for_blockers(blockers, {"dailynews_first_run_launch_ready"}),
        "get_status": _status_for_blockers(blockers, {"getdaytrends_strict_readiness_pass", "getdaytrends_canonical_smoke_pass"}),
        "provider_issue_types": _list_child(provider_auth, "issue_types"),
    }


def _provider_auth_external_step(context: dict[str, Any]) -> dict[str, str]:
    provider_auth = context["provider_auth"]
    issue_types = context["provider_issue_types"]
    return {
        "name": "Google provider auth",
        "status": "blocked" if issue_types else "not_applicable",
        "evidence": (
            f"Provider-auth packet generated {provider_auth.get('generated_at')} reports status={provider_auth.get('status')} "
            f"and issue_types={issue_types}. Remaining current completion blockers are {context['blockers']}."
        ),
    }


def _dailynews_external_step(context: dict[str, Any]) -> dict[str, str]:
    daily_input = context["daily_input"]
    probe = context["probe"]
    direct_probe = context["direct_probe"]
    management_probe = context["management_probe"]
    side_channel_audit = context["side_channel_audit"]
    shape_audit = context["shape_audit"]
    unblock = context["unblock"]
    recovery = context["recovery"]
    no_credential_refresh = context["no_credential_refresh"]
    no_credential_release = context["no_credential_release"]
    resume = context["resume"]
    return {
        "name": "DailyNews Supabase live database readiness",
        "status": context["daily_status"],
        "evidence": (
            f"DailyNews credential input status generated {daily_input.get('generated_at')} reports status={daily_input.get('status')}, "
            f"ok={daily_input.get('ok')}, wrapper_rerun_recommended={daily_input.get('wrapper_rerun_recommended')}, "
            f"and credential_source_signal_present={daily_input.get('credential_source_signal_present')}. "
            f"Current completion blockers are {context['blockers']}. Sanitized pooler username variant probe generated {probe.get('generated_at')} "
            f"reports variant_count={probe.get('variant_count')} and db_success_count={probe.get('db_success_count')}. "
            f"Sanitized direct DB host diagnostic probe generated {direct_probe.get('generated_at')} reports "
            f"project_refs_match={_dict_child(direct_probe, 'source_shape').get('project_refs_match')}, "
            f"db_success_count={direct_probe.get('db_success_count')}, and "
            f"direct_host_with_same_password_success={_dict_child(direct_probe, 'conclusion').get('direct_host_with_same_password_success')}. "
            f"Supabase Management API pooler probe generated {management_probe.get('generated_at')} reports status={management_probe.get('status')}, "
            f"token_present={_dict_child(management_probe, 'token').get('present')}, "
            f"and transaction_pooler_count={management_probe.get('transaction_pooler_count')}. "
            f"Local credential side-channel audit generated {side_channel_audit.get('generated_at')} reports status={side_channel_audit.get('status')}, "
            f"new_local_credential_signal_present={_dict_child(side_channel_audit, 'conclusion').get('new_local_credential_signal_present')}, "
            f"and external_operator_action_required={_dict_child(side_channel_audit, 'conclusion').get('external_operator_action_required')}. "
            f"Supabase pooler shape audit generated {shape_audit.get('generated_at')} reports status={shape_audit.get('status')}, "
            f"any_transaction_pooler_shape_match_count={_dict_child(shape_audit, 'summary').get('any_transaction_pooler_shape_match_count')}, "
            f"and obvious_pooler_shape_fix_available={_dict_child(shape_audit, 'summary').get('obvious_pooler_shape_fix_available')}. "
            f"Unblock gate generated {unblock.get('generated_at')} reports status={unblock.get('status')}, "
            f"rerun_recommended={unblock.get('rerun_recommended')}, and credential_signal_present={unblock.get('credential_signal_present')}. "
            f"Recovery report `{rel_path(context['recovery_report_path'], context['root'])}` generated {recovery.get('generated_at')} reports status={recovery.get('status')} with summary={recovery.get('summary')}. "
            f"Ordered no-credential refresh generated {no_credential_refresh.get('generated_at')} reports status={no_credential_refresh.get('status')}, "
            f"release_generated_after_unblock={no_credential_release.get('release_generated_after_unblock')}, "
            f"and release_generated_after_side_channel={no_credential_release.get('release_generated_after_side_channel')}. "
            f"Scheduled task resume guard generated {resume.get('generated_at')} reports status={resume.get('status')}, ok={resume.get('ok')}, "
            f"dry_run={resume.get('dry_run')}, gates.all_ok={_dict_child(resume, 'gates').get('all_ok')}, "
            f"and task states={context['resume_statuses']}. External operator action is still required while this step is blocked: apply a corrected DailyNews "
            f"Transaction pooler credential with `python ops/scripts/dailynews_update_database_url.py --stdin --write`, or apply one workspace-wide corrected Transaction pooler URL with {context['guarded_apply']}"
        ),
    }


def _getdaytrends_external_step(context: dict[str, Any]) -> dict[str, str]:
    workspace_smoke = context["workspace_smoke"]
    readiness = context["readiness"]
    provider_auth = context["provider_auth"]
    supabase = context["supabase"]
    dashboard = context["dashboard"]
    get_input = context["get_input"]
    shape_audit = context["shape_audit"]
    no_credential_refresh = context["no_credential_refresh"]
    no_credential_release = context["no_credential_release"]
    resume = context["resume"]
    return {
        "name": "getdaytrends Supabase launch readiness",
        "status": context["get_status"],
        "evidence": (
            f"getdaytrends canonical workspace smoke generated {workspace_smoke.get('generated_at')} reports status={workspace_smoke.get('status')} "
            f"with summary={workspace_smoke.get('summary')}. Strict readiness generated {readiness.get('generated_at')} reports status={readiness.get('status')} "
            f"with summary={readiness.get('summary')}. Provider-auth packet generated {provider_auth.get('generated_at')} reports status={provider_auth.get('status')} "
            f"and issue_types={context['provider_issue_types']}. Supabase recovery packet generated {supabase.get('generated_at')} reports status={supabase.get('status')} "
            f"with issue_types={supabase.get('issue_types')}. Dashboard browser smoke generated {dashboard.get('generated_at')} reports summary={dashboard.get('summary')}. "
            f"getdaytrends credential input status generated {get_input.get('generated_at')} reports status={get_input.get('status')}, "
            f"credential_source_signal_present={get_input.get('credential_source_signal_present')}, and "
            f"safe_to_skip_strict_readiness_until_credential_inputs_change={get_input.get('safe_to_skip_strict_readiness_until_credential_inputs_change')}. "
            f"Supabase pooler shape audit generated {shape_audit.get('generated_at')} reports status={shape_audit.get('status')} "
            f"and obvious_pooler_shape_fix_available={_dict_child(shape_audit, 'summary').get('obvious_pooler_shape_fix_available')}. "
            f"Ordered no-credential refresh generated {no_credential_refresh.get('generated_at')} reports status={no_credential_refresh.get('status')}, "
            f"release_generated_after_unblock={no_credential_release.get('release_generated_after_unblock')}, "
            f"and release_generated_after_side_channel={no_credential_release.get('release_generated_after_side_channel')}. "
            f"Scheduled task resume guard generated {resume.get('generated_at')} reports status={resume.get('status')}, ok={resume.get('ok')}, dry_run={resume.get('dry_run')}, "
            f"and task states={context['resume_statuses']}. External operator action is still required while this step is blocked: apply a corrected getdaytrends "
            f"Transaction pooler credential with `python ops/scripts/getdaytrends_update_credentials.py --database-url-stdin --write`, or apply one workspace-wide corrected Transaction pooler URL with {context['guarded_apply']}"
        ),
    }


def _resume_statuses(resume: dict[str, Any]) -> list[str]:
    resume_tasks = _dict_child(resume, "tasks")
    resume_after = resume_tasks.get("after") if isinstance(resume_tasks.get("after"), list) else []
    return [
        f"{item.get('task_name')}={item.get('status')}/{item.get('scheduled_task_state')}"
        for item in resume_after
        if isinstance(item, dict) and item.get("task_name")
    ]


def _list_child(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _guarded_apply_text() -> str:
    return (
        "`powershell.exe -NoProfile -ExecutionPolicy Bypass -File ops/scripts/apply_workspace_supabase_pooler_url.ps1 -PreviewOnly -NonInteractive`, "
        "then `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ops/scripts/apply_workspace_supabase_pooler_url.ps1 -NonInteractive` "
        "after setting process-scope `WORKSPACE_NEW_SUPABASE_POOLER_DATABASE_URL` to the complete encoded URL; "
        "the wrapper shows a redacted dry-run preview, requires typing APPLY before writing, "
        "or the env-based fallback `python ops/scripts/apply_workspace_supabase_pooler_url.py --write --run-recovery --resume-scheduled-tasks`; "
        "the shared updater rejects scheduled-task resume unless same-run recovery is requested."
    )


def _source_note(root: Path, snapshots: list[dict[str, str]]) -> str:
    context = _source_note_context(root)
    status = context["status"]
    unblock = context["unblock"]
    recovery_report_path = context["recovery_report_path"]
    recovery = context["recovery"]
    consistency = context["consistency"]
    no_credential_refresh = context["no_credential_refresh"]
    no_credential_release = context["no_credential_release"]
    audit = context["audit"]
    live_source = context["live_source"]
    live_sources = context["live_sources"]
    radar_auto_refresh = context["radar_auto_refresh"]
    return (
        "Completion readiness is sourced from current completion audit, MCP health bridge, direct MCP session probe, MCP stale process audit, unblock gate, recovery report, "
        "credential input status, getdaytrends readiness/smoke/browser evidence, and evidence consistency. "
        f"Completion audit generated {status.get('generated_at')} is {audit.get('status') or status.get('status')} "
        f"with blockers {audit.get('blocking_requirements')}. "
        f"Veritas live source status is {live_source.get('status')} with checked={live_source.get('checked')} "
        f"and tracked source set status is {live_sources.get('status')} "
        f"({live_sources.get('current_count')}/{live_sources.get('checked_count')} current); "
        f"radar_auto_refreshed={radar_auto_refresh.get('auto_refreshed')}. "
        f"Unblock gate generated {unblock.get('generated_at')} is {unblock.get('status')} with "
        f"rerun_recommended={unblock.get('rerun_recommended')} and credential_signal_present={unblock.get('credential_signal_present')}. "
        f"Recovery report `{rel_path(recovery_report_path, root)}` generated {recovery.get('generated_at')} is {recovery.get('status')} with summary={recovery.get('summary')}. "
        f"Ordered no-credential refresh generated {no_credential_refresh.get('generated_at')} is {no_credential_refresh.get('status')} with "
        f"release_generated_after_unblock={no_credential_release.get('release_generated_after_unblock')} and "
        f"release_generated_after_side_channel={no_credential_release.get('release_generated_after_side_channel')}. "
        f"Evidence consistency generated {consistency.get('generated_at')} is {consistency.get('status')} with summary={consistency.get('summary')}. "
        f"Evidence consistency pending={not bool(consistency)} during pre-consistency manifest bootstrap. "
        "External Supabase Transaction pooler credentials remain the expected blocker set; release approval remains blocked until "
        "completion_audit_gate.ok is true and blocked external steps 1 and 2 are resolved."
    )


def _source_note_context(root: Path) -> dict[str, Any]:
    status = load_json(
        _current_or_latest_var_artifact(
            root,
            f"complete-goal-status-audit-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-status-audit-current-*.json",
        )
    )
    unblock = load_json(
        _current_or_latest_var_artifact(
            root,
            f"complete-goal-unblock-gate-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-unblock-gate-current-*.json",
        )
    )
    recovery_report_path = _current_or_latest_recovery_report(root)
    recovery = load_json(recovery_report_path)
    consistency = _load_optional_json(
        _current_or_latest_var_artifact(
            root,
            f"complete-goal-evidence-consistency-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-evidence-consistency-current-*.json",
        )
    )
    no_credential_refresh = _load_optional_json(
        _current_or_latest_var_artifact(
            root,
            f"complete-goal-no-credential-refresh-current-{CURRENT_DATE_STAMP}.json",
            "complete-goal-no-credential-refresh-current-*.json",
        )
    )
    no_credential_summary = _dict_child(no_credential_refresh, "summary")
    source = _dict_child(status, "source")
    return {
        "status": status,
        "unblock": unblock,
        "recovery_report_path": recovery_report_path,
        "recovery": recovery,
        "consistency": consistency,
        "no_credential_refresh": no_credential_refresh,
        "no_credential_release": _dict_child(no_credential_summary, "release_evidence"),
        "audit": _dict_child(status, "completion_audit"),
        "live_source": _dict_child(source, "live_source"),
        "live_sources": _dict_child(source, "live_sources"),
        "radar_auto_refresh": _dict_child(source, "radar_auto_refresh"),
    }


def _worktree_with_required_changed_paths(existing: dict[str, Any]) -> dict[str, Any]:
    worktree = _dict_child(existing, "worktree")
    merged = {
        "status": "reviewed_in_progress",
        "changed_paths": [],
        **worktree,
    }
    paths = merged.get("changed_paths") if isinstance(merged.get("changed_paths"), list) else []
    merged["changed_paths"] = _ordered_unique_strings([*paths, *REQUIRED_CHANGED_PATHS])
    return merged


def _ordered_unique_strings(items: Sequence[Any]) -> list[str]:
    ordered: list[str] = []
    for item in items:
        _append_ordered_unique_string(ordered, item)
    return ordered


def _append_ordered_unique_string(ordered: list[str], item: Any) -> None:
    text = str(item).strip()
    if text and text not in ordered:
        ordered.append(text)


def refresh_manifest(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    allow_missing_consistency: bool = False,
    allow_missing_release_evidence: bool = False,
) -> dict[str, Any]:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%SKST")
    snapshot_dir = workspace_root / "var" / "release-approval-snapshots" / CURRENT_DATE_STAMP / stamp
    snapshots, missing, allowed_missing = _copy_manifest_snapshots(
        workspace_root=workspace_root,
        snapshot_dir=snapshot_dir,
        stamp=stamp,
        allow_missing_consistency=allow_missing_consistency,
        allow_missing_release_evidence=allow_missing_release_evidence,
    )
    prompt_evidence_snapshots = _copy_prompt_checklist_evidence_snapshots(
        workspace_root=workspace_root,
        snapshot_dir=snapshot_dir,
        stamp=stamp,
    )
    snapshots.extend({"path": item["snapshot_path"], "generated_at": item["generated_at"]} for item in prompt_evidence_snapshots)
    existing = load_json(manifest_path) if manifest_path.exists() else {}
    completion_path = _current_or_latest_var_artifact(
        workspace_root,
        f"complete-goal-status-audit-current-{CURRENT_DATE_STAMP}.json",
        "complete-goal-status-audit-current-*.json",
    )
    unblock_path = _current_or_latest_var_artifact(
        workspace_root,
        f"complete-goal-unblock-gate-current-{CURRENT_DATE_STAMP}.json",
        "complete-goal-unblock-gate-current-*.json",
    )
    recovery_report_path = _current_or_latest_recovery_report(workspace_root)
    consistency_path = _current_or_latest_var_artifact(
        workspace_root,
        f"complete-goal-evidence-consistency-current-{CURRENT_DATE_STAMP}.json",
        "complete-goal-evidence-consistency-current-*.json",
    )
    source_note = _source_note(workspace_root, snapshots)
    external_steps = _external_steps(workspace_root)
    worktree = _worktree_with_required_changed_paths(existing)
    generated_at = datetime.now().astimezone().isoformat()
    manifest = {
        **existing,
        "schema_version": 1,
        "generated_at": generated_at,
        "release_candidate": "workspace-completion-audit",
        "affected_scope": "workspace",
        "deterministic_gate": existing.get(
            "deterministic_gate",
            {
                "ok": True,
                "command": "python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-complete-goal-audit-2026-06-06.json",
                "evidence_path": "var/workspace-smoke-complete-goal-audit-2026-06-06.json",
            },
        ),
        "completion_audit_gate": {
            "ok": _gate_ok_from_payload(completion_path),
            "command": _completion_audit_command(),
            "evidence_path": rel_path(completion_path, workspace_root),
        },
        "unblock_preflight_gate": {
            "ok": _gate_ok_from_payload(unblock_path),
            "command": f"python ops/scripts/complete_goal_unblock_gate.py --allow-blocked-external --allow-ready-to-rerun --json-out var/complete-goal-unblock-gate-current-{CURRENT_DATE_STAMP}.json --markdown-out docs/reports/{REPORT_MONTH}/COMPLETE_GOAL_UNBLOCK_GATE_CURRENT_{CURRENT_DATE_STAMP}.md",
            "evidence_path": rel_path(unblock_path, workspace_root),
        },
        "recovery_preflight_gate": {
            "ok": _gate_ok_from_payload(recovery_report_path),
            "command": _recovery_refresh_command(recovery_report_path, workspace_root),
            "evidence_path": rel_path(recovery_report_path, workspace_root),
        },
        "evidence_consistency_gate": {
            "ok": _gate_ok_from_payload(consistency_path),
            "command": f"python ops/scripts/complete_goal_evidence_consistency_check.py --json-out var/complete-goal-evidence-consistency-current-{CURRENT_DATE_STAMP}.json --markdown-out docs/reports/{REPORT_MONTH}/COMPLETE_GOAL_EVIDENCE_CONSISTENCY_CURRENT_{CURRENT_DATE_STAMP}.md",
            "evidence_path": rel_path(consistency_path, workspace_root),
        },
        "source_of_truth": {"status": "reviewed", "note": source_note},
        "snapshot_paths": snapshots,
        "prompt_checklist_evidence_snapshots": prompt_evidence_snapshots,
        "missing_sources": missing,
        "allowed_missing_sources": allowed_missing,
        "evidence_references": {"items": snapshots},
        "external_steps": external_steps,
        "worktree": worktree,
        "compatibility_warnings": existing.get("compatibility_warnings", {"status": "reviewed"}),
    }
    write_json(manifest_path, manifest)
    return {
        "manifest_path": str(manifest_path),
        "generated_at": generated_at,
        "snapshot_paths": snapshots,
        "prompt_checklist_evidence_snapshots": prompt_evidence_snapshots,
        "missing_sources": missing,
        "allowed_missing_sources": allowed_missing,
    }


def _copy_manifest_snapshots(
    *,
    workspace_root: Path,
    snapshot_dir: Path,
    stamp: str,
    allow_missing_consistency: bool,
    allow_missing_release_evidence: bool,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    snapshots: list[dict[str, str]] = []
    missing: list[str] = []
    allowed_missing: list[str] = []
    for label, resolver in SNAPSHOT_SOURCES:
        source = _source_or_latest_snapshot(workspace_root, label, resolver(workspace_root))
        if source is None or not source.exists():
            _record_missing_snapshot_source(
                label,
                missing,
                allowed_missing,
                allow_missing_consistency=allow_missing_consistency,
                allow_missing_release_evidence=allow_missing_release_evidence,
            )
            continue
        snapshots.append(copy_snapshot(source, snapshot_dir, label, stamp, workspace_root))
    return snapshots, missing, allowed_missing


def _record_missing_snapshot_source(
    label: str,
    missing: list[str],
    allowed_missing: list[str],
    *,
    allow_missing_consistency: bool,
    allow_missing_release_evidence: bool,
) -> None:
    if _allowed_missing_snapshot_source(
        label,
        allow_missing_consistency=allow_missing_consistency,
        allow_missing_release_evidence=allow_missing_release_evidence,
    ):
        allowed_missing.append(label)
        return
    missing.append(label)


def _allowed_missing_snapshot_source(
    label: str,
    *,
    allow_missing_consistency: bool,
    allow_missing_release_evidence: bool,
) -> bool:
    return (
        allow_missing_consistency
        and label == "complete-goal-evidence-consistency"
        or allow_missing_release_evidence
        and label == "complete-goal-release-evidence-refresh"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the complete-goal release approval manifest and evidence snapshots.")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument(
        "--allow-missing-consistency",
        action="store_true",
        help="Permit the current evidence-consistency artifact to be absent during pre-consistency bootstrap refreshes.",
    )
    parser.add_argument(
        "--allow-missing-release-evidence",
        action="store_true",
        help="Permit the current release-evidence artifact to be absent while the release-evidence driver is bootstrapping it.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = refresh_manifest(
        workspace_root=args.workspace_root,
        manifest_path=args.manifest_path,
        allow_missing_consistency=args.allow_missing_consistency,
        allow_missing_release_evidence=args.allow_missing_release_evidence,
    )
    write_json(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["missing_sources"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
