import importlib.util
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "ops" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "refresh_complete_goal_release_manifest.py"


def load_module(stamp: str = "2026-06-08"):
    os.environ["COMPLETE_GOAL_DATE_STAMP"] = stamp
    sys.path.insert(0, str(SCRIPT_DIR))
    sys.modules.pop("complete_goal_gate_common", None)
    spec = importlib.util.spec_from_file_location("refresh_complete_goal_release_manifest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_or_latest_var_artifact_prefers_exact_current_when_present(tmp_path):
    module = load_module("2026-06-11")
    current = tmp_path / "var" / "sample-current-2026-06-11.json"
    newer = tmp_path / "var" / "sample-current-2026-06-12.json"
    _write(current, {"generated_at": "2026-06-11T01:00:00+00:00"})
    _write(newer, {"generated_at": "2026-06-12T01:00:00+00:00"})

    selected = module._current_or_latest_var_artifact(
        tmp_path,
        "sample-current-2026-06-11.json",
        "sample-current-*.json",
    )

    assert selected == current


def _write_getdaytrends_readiness_sidecars(
    root: Path,
    *,
    generated_at: str,
    readiness: dict | None = None,
    provider: dict | None = None,
    supabase: dict | None = None,
) -> None:
    readiness_dir = root / "automation" / "getdaytrends" / "logs" / "readiness"
    readiness_payload = readiness or {"generated_at": generated_at, "status": "fail", "summary": {"failed": 2}}
    provider_payload = provider or {"generated_at": generated_at, "status": "clear", "issue_types": []}
    supabase_payload = supabase or {
        "generated_at": generated_at,
        "status": "blocked",
        "issue_types": ["live_db_doctor_failed"],
    }
    _write(readiness_dir / "readiness_latest.json", readiness_payload)
    _write(readiness_dir / "strict_readiness_latest.json", readiness_payload)
    _write(readiness_dir / "provider_auth_recovery_packet_latest.json", provider_payload)
    _write(readiness_dir / "strict_provider_auth_recovery_packet_latest.json", provider_payload)
    _write(readiness_dir / "supabase_recovery_packet_latest.json", supabase_payload)
    _write(readiness_dir / "strict_supabase_recovery_packet_latest.json", supabase_payload)


def _seed_core_gate_artifacts(root: Path, *, blockers: list[str] | None = None) -> None:
    _write(
        root / "var" / "complete-goal-status-audit-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:27+00:00",
            "completion_audit": {
                "status": "action_required" if blockers else "ok",
                "blocking_requirements": blockers or [],
            },
        },
    )
    _write(
        root / "var" / "mcp-inventory-health-bridge-config-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:26+00:00",
            "status": "ok",
            "ok": True,
            "health": {"live_ok_count": 0, "live_check_count": 0, "recommended_actions": []},
        },
    )
    _write(
        root / "var" / "mcp-inventory-health-bridge-live-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:28+00:00",
            "status": "action_required",
            "ok": False,
            "health": {
                "live_ok_count": 0,
                "live_check_count": 5,
                "live_failure_categories": {"child_process_terminated": 5},
                "recommended_actions": [{"category": "child_process_terminated", "count": 5}],
            },
        },
    )
    _write(
        root / "var" / "mcp-direct-session-probe-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:29+00:00",
            "status": "action_required",
            "ok": False,
            "summary": {"probe_count": 2, "ok_count": 1, "action_required_count": 1},
            "probes": [
                {"name": "figma", "ok": True, "status": "authenticated", "evidence": "figma ok"},
                {"name": "notion", "ok": False, "status": "auth_required", "evidence": "notion auth required"},
            ],
            "secrets_redacted": True,
            "approval_effect": "supplemental_only",
        },
    )
    _write(
        root / "var" / "mcp-stale-process-audit-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:31+00:00",
            "status": "action_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "cleanup_policy": {
                "execute_supported": False,
                "preview_supported": True,
                "preview_mode": "manual_whatif_only",
            },
            "cleanup_preview": {
                "mode": "manual_whatif_only",
                "execute_supported": False,
                "requires_operator_confirmation": True,
                "manual_selection_required": True,
                "destructive_actions_performed": False,
                "candidate_process_count": 1,
                "candidate_process_ids": [17104],
                "preview_commands": ["Stop-Process -Id 17104 -WhatIf"],
                "groups": [
                    {
                        "category": "canva_callback_port_bound",
                        "process_ids": [17104],
                        "preview_command": "Stop-Process -Id 17104 -WhatIf",
                        "verification": "python ops\\scripts\\mcp_stale_process_audit.py --allow-action-required",
                    }
                ],
            },
            "summary": {"finding_count": 1, "action_required_count": 1},
            "findings": [{"category": "canva_callback_port_bound"}],
        },
    )
    _write(
        root / "var" / "mcp-stale-process-cleanup-plan-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:32+00:00",
            "status": "manual_review_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "manual_confirmation_required": True,
            "requires_current_session_identification": True,
            "cleanup_policy": {
                "execute_supported": False,
                "auto_stop_supported": False,
                "auto_stop_candidate_count": 0,
                "manual_review_required": True,
            },
            "summary": {
                "stage_count": 1,
                "manual_review_count": 1,
                "candidate_process_count": 1,
                "auto_stop_candidate_count": 0,
            },
            "validation_failures": [],
            "post_cleanup_verification": [
                "python ops\\scripts\\mcp_stale_process_audit.py --allow-action-required",
                "direct MCP session probe refresh via connector tool calls",
                "python ops\\scripts\\check_mcp_health.py --json-out var\\mcp-health-live-current-2026-06-08.json",
            ],
            "stages": [
                {
                    "stage": "canva_callback_listener_review",
                    "category": "canva_callback_port_bound",
                    "manual_review_required": True,
                    "auto_stop_supported": False,
                    "process_ids": [17104],
                    "process_count": 1,
                }
            ],
        },
    )
    _write(
        root / "var" / "mcp-process-owner-detail-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:33+00:00",
            "source_cleanup_plan_generated_at": "2026-06-08T04:53:32+00:00",
            "status": "manual_review_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "cleanup_policy": {
                "execute_supported": False,
                "auto_stop_supported": False,
                "auto_stop_candidate_count": 0,
                "manual_review_required": True,
            },
            "summary": {
                "requested_parent_process_count": 1,
                "resolved_parent_process_count": 1,
                "missing_parent_process_count": 0,
                "owner_group_count": 1,
                "candidate_parent_overlap_count": 0,
                "auto_stop_candidate_count": 0,
                "active_session_identity_known": False,
                "command_line_marker_counts": {"codex": 1},
            },
            "validation_failures": [],
            "post_probe_verification": [
                "python ops\\scripts\\mcp_stale_process_cleanup_plan.py --allow-action-required",
                "python ops\\scripts\\check_mcp_health.py --json-out var\\mcp-health-live-current-2026-06-08.json",
            ],
            "owner_details": [
                {
                    "parent_process_id": 100,
                    "resolved": True,
                    "parent_process_id_of_parent": 1,
                    "name": "codex.exe",
                    "command_line_hash": "hash",
                    "command_line_markers": ["codex"],
                    "role_guess": "codex_session",
                    "child_process_ids": [17104],
                    "child_process_count": 1,
                    "categories": ["canva_callback_port_bound"],
                    "stages": ["canva_callback_listener_review"],
                    "parent_is_also_candidate": False,
                    "review": "manual review",
                }
            ],
        },
    )
    _write(
        root / "var" / "mcp-manual-cleanup-checklist-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:34+00:00",
            "source_owner_detail_generated_at": "2026-06-08T04:53:33+00:00",
            "status": "manual_review_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "cleanup_policy": {
                "execute_supported": False,
                "auto_stop_supported": False,
                "auto_stop_candidate_count": 0,
                "manual_review_required": True,
            },
            "manual_cleanup_contract": {
                "operator_confirmation_required": True,
                "active_session_identity_required": True,
                "active_session_identity_known": False,
                "stop_commands_included": False,
                "stop_commands_intentionally_omitted": True,
                "requires_post_cleanup_verification": True,
            },
            "summary": {
                "checklist_item_count": 1,
                "manual_review_required_count": 1,
                "high_risk_item_count": 1,
                "medium_risk_item_count": 0,
                "blocked_item_count": 0,
                "pre_check_count": 3,
                "post_check_count": 1,
                "manual_stop_command_count": 0,
                "auto_stop_candidate_count": 0,
                "active_session_identity_known": False,
            },
            "validation_failures": [],
            "post_cleanup_verification": [
                "python ops\\scripts\\mcp_stale_process_audit.py --allow-action-required",
            ],
            "checklist_items": [
                {
                    "parent_process_id": 100,
                    "role_guess": "codex_session",
                    "categories": ["canva_callback_port_bound"],
                    "child_process_ids": [17104],
                    "child_process_count": 1,
                    "parent_is_also_candidate": False,
                    "risk_level": "high",
                    "manual_review_required": True,
                    "auto_stop_supported": False,
                    "safe_to_close_decision": "unknown_until_operator_confirms_inactive_session",
                    "pre_checks": ["Confirm inactive session."],
                }
            ],
        },
    )
    _write(
        root / "var" / "mcp-cleanup-readiness-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:35+00:00",
            "status": "action_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "cleanup_policy": {
                "execute_supported": False,
                "auto_stop_supported": False,
                "auto_stop_candidate_count": 0,
                "manual_review_required": True,
            },
            "summary": {
                "checklist_item_count": 1,
                "stale_finding_count": 1,
                "direct_probe_count": 1,
                "direct_ok_count": 0,
                "direct_action_required_count": 1,
                "live_check_count": 1,
                "live_ok_count": 0,
                "unsafe_command_count": 0,
                "auto_stop_candidate_count": 0,
            },
            "validation_failures": [],
            "readiness_checks": [
                {"name": "source_evidence_contract_valid", "ok": True, "status": "pass"},
                {"name": "manual_cleanup_completed", "ok": False, "status": "action_required"},
                {"name": "stale_process_audit_clear", "ok": False, "status": "action_required"},
                {"name": "direct_mcp_probe_clear", "ok": False, "status": "action_required"},
                {"name": "canonical_live_mcp_health_clear", "ok": False, "status": "action_required"},
            ],
            "verification_commands": [
                "python ops\\scripts\\mcp_stale_process_audit.py --allow-action-required",
            ],
        },
    )
    _write(
        root / "var" / "mcp-connector-auth-readiness-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:36+00:00",
            "status": "action_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "summary": {
                "configured_count": 2,
                "config_probe_count": 2,
                "ok_count": 0,
                "probe_count": 2,
                "action_required_count": 2,
                "auth_required_count": 1,
                "oauth_required_count": 0,
                "transport_closed_count": 1,
                "unsafe_command_count": 0,
            },
            "validation_failures": [],
            "config_probes": [{"name": "notion_config"}, {"name": "canva_local_config"}],
            "probes": [{"name": "canva_local_auth_status"}, {"name": "notion_self_user"}],
            "readiness_checks": [
                {"name": "source_evidence_contract_valid", "ok": True, "status": "pass"},
                {"name": "target_configs_present", "ok": True, "status": "pass"},
                {"name": "connector_auth_ready", "ok": False, "status": "action_required"},
                {"name": "no_transport_closed", "ok": False, "status": "action_required"},
                {"name": "no_auth_required", "ok": False, "status": "action_required"},
            ],
            "verification_commands": [
                'cmd /c "codex mcp get notion && codex mcp get canva-local"',
                "Canva MCP auth_status tool call",
                "Notion MCP notion_get_users user_id=self tool call",
            ],
        },
    )
    _write(
        root / "var" / "mcp-auth-diagnostic-current-2026-06-08.json",
        {
            "schema_version": 1,
            "generated_at": "2026-06-08T04:53:37+00:00",
            "status": "action_required",
            "ok": False,
            "approval_effect": "supplemental_only",
            "secrets_redacted": True,
            "destructive_actions_performed": False,
            "execution_supported": False,
            "safe_to_execute": False,
            "summary": {
                "target_count": 3,
                "configured_count": 3,
                "ok_count": 0,
                "action_required_count": 3,
                "auth_required_count": 1,
                "oauth_required_count": 0,
                "transport_closed_count": 2,
                "profile_locked_count": 0,
                "not_checked_count": 0,
                "unsafe_command_count": 0,
            },
            "validation_failures": [],
            "targets": [
                {"name": "notion", "status": "auth_required", "ok": False},
                {"name": "canva-local", "status": "transport_closed", "ok": False},
                {"name": "playwright", "status": "transport_closed", "ok": False},
            ],
            "readiness_checks": [
                {"name": "source_evidence_valid", "status": "pass"},
                {"name": "target_configs_present", "status": "pass"},
                {"name": "target_auth_ready", "status": "action_required"},
                {"name": "verification_commands_safe", "status": "pass"},
            ],
            "verification_commands": [
                'cmd /c "codex mcp get notion"',
                'cmd /c "codex mcp get canva-local"',
                'cmd /c "codex mcp get playwright"',
            ],
        },
    )
    _write(
        root / "var" / "complete-goal-unblock-gate-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:35+00:00",
            "status": "blocked_external" if blockers else "ready",
            "rerun_recommended": False,
            "credential_signal_present": False,
        },
    )
    _write(
        root / "var" / "workspace-external-credential-recovery-refresh-preflight-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:39+00:00",
            "status": "action_required" if blockers else "complete",
            "summary": {"failed": 1 if blockers else 0},
        },
    )
    _write(
        root / "var" / "complete-goal-evidence-consistency-current-2026-06-08.json",
        {"generated_at": "2026-06-08T14:00:44+09:00", "status": "ok", "summary": {"failed": 0}},
    )
    _write(
        root / "var" / "complete-goal-local-credential-side-channel-audit-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:22+00:00",
            "status": "no_new_local_credential_signal",
            "ok": True,
            "secrets_redacted": True,
            "conclusion": {
                "new_local_credential_signal_present": False,
                "supabase_management_token_present": False,
                "postgres_side_channel_present": False,
                "external_operator_action_required": True,
            },
        },
    )
    _write(
        root / "var" / "complete-goal-no-credential-refresh-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:40+00:00",
            "status": "blocked_expected_external" if blockers else "ready_to_rerun",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "unblock": {
                    "status": "blocked_external" if blockers else "ready_to_rerun",
                },
                "release_evidence": {
                    "ran": bool(blockers),
                    "generated_at": "2026-06-08T04:53:39+00:00" if blockers else "",
                    "status": "blocked_expected_external" if blockers else None,
                    "unexpected_failed_step_count": 0 if blockers else None,
                    "release_generated_after_unblock": True if blockers else None,
                    "release_generated_after_side_channel": True if blockers else None,
                },
                "post_write_finalization": {
                    "ok": True,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_expected_external",
                    "release_approval_unexpected_failures": [],
                }
                if blockers
                else {},
            },
            **(
                {
                    "post_write_finalization": {
                        "ok": True,
                        "manifest": {
                            "no_credential_snapshot": {
                                "present": True,
                                "matches_report_generated_at": True,
                            }
                        },
                        "release_approval": {
                            "failure_analysis": {
                                "status": "blocked_expected_external",
                                "unexpected_failures": [],
                            }
                        },
                    }
                }
                if blockers
                else {}
            ),
        },
    )
    _write(
        root / "var" / "supabase-pooler-management-probe-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:23+00:00",
            "status": "token_missing",
            "ok": False,
            "token": {"present": False},
            "transaction_pooler_count": 0,
            "poolers": [],
            "secrets_redacted": True,
        },
    )
    _write(
        root / "var" / "supabase-pooler-shape-audit-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:21+00:00",
            "status": "matches_official_pooler_shape",
            "ok": True,
            "summary": {
                "any_transaction_pooler_shape_match_count": 1,
                "obvious_pooler_shape_fix_available": False,
            },
            "secrets_redacted": True,
        },
    )
    _write(
        root / "var" / "complete-goal-report-secret-scan-refresh-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:28+00:00",
            "status": "valid",
            "ok": True,
            "selected_report_paths": [
                "docs/reports/2026-06/COMPLETE_GOAL_CURRENT_BLOCKER_AUDIT_2026-06-08.md",
                "docs/reports/2026-06/COMPLETE_GOAL_PROMPT_TO_ARTIFACT_CHECKLIST_CURRENT_2026-06-08.md",
                "docs/reports/2026-06/COMPLETE_GOAL_OPERATOR_UNBLOCK_HANDOFF_CURRENT_2026-06-08.md",
                "docs/reports/2026-06/AUTO_RESEARCH_REPORT_SECRET_SCAN_REFRESH_DRIVER_2026-06-08.md",
            ],
            "missing_report_patterns": [],
            "dailynews": {"status": "valid", "ok": True},
            "getdaytrends": {"status": "valid", "ok": True},
        },
    )
    _write(
        root / "var" / "complete-goal-report-secret-scan-dailynews-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:29+00:00",
            "status": "valid",
            "ok": True,
            "findings": [],
        },
    )
    _write(
        root / "var" / "complete-goal-report-secret-scan-getdaytrends-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:30+00:00",
            "status": "valid",
            "ok": True,
            "findings": [],
        },
    )
    _write(
        root / "var" / "complete-goal-release-evidence-refresh-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:41+00:00",
            "status": "blocked_expected_external" if blockers else "approval_ready",
            "ok": not bool(blockers),
            "summary": {
                "unexpected_failed_step_count": 0,
                "operator_action_coverage": {"ok": True},
                "operator_action_markdown_command_coverage": {"ok": True},
                "operator_action_phase_coverage": {"ok": True},
                "operator_action_safety_coverage": {"ok": True},
                "operator_action_evidence_path_coverage": {"ok": True},
                "operator_action_command_output_coverage": {"ok": True},
                "current_artifact_unexpected_state_coverage": {"ok": True},
                "live_source_detail_coverage": {"ok": True},
                "consistency": {"ok": True, "status": "ok", "summary": {"failed": 0}},
                "release_approval": {
                    "ok": not blockers,
                    "generated_after_final_manifest_refresh": True,
                    "failure_analysis": {
                        "status": "blocked_expected_external" if blockers else "approved",
                        "unexpected_failures": [],
                    },
                },
            },
        },
    )


def _write_ok_full_matrix_recovery(root: Path) -> None:
    _write(
        root / "var" / "workspace-external-credential-recovery-refresh-current-full-matrix-2026-06-08.json",
        {
            "generated_at": "2026-06-08T06:30:00+00:00",
            "status": "ok",
            "ok": True,
            "dry_run": False,
            "preflight_unblock_gate": True,
            "execution_contract": {
                "approval_ready_requires_preflight_unblock_gate": True,
                "preflight_unblock_gate_present": True,
                "release_evidence_refresh_driver": "ops/scripts/complete_goal_release_evidence_refresh.py",
                "release_evidence_refresh_driver_step": "Ordered release evidence refresh",
            },
            "full_matrix_blocked": {"blocked": False, "reason": "", "skipped_steps": []},
            "summary": {"total": 14, "completed": 14, "planned": 0, "skipped": 0, "passed": 14, "failed": 0},
        },
    )


def _seed_minimal_current_gate_artifacts(root: Path, stamp: str) -> None:
    _write(
        root / "var" / f"complete-goal-status-audit-current-{stamp}.json",
        {"generated_at": f"{stamp}T00:00:00+00:00", "completion_audit": {"status": "ok", "blocking_requirements": []}},
    )
    _write(
        root / "var" / f"complete-goal-unblock-gate-current-{stamp}.json",
        {"generated_at": f"{stamp}T00:01:00+00:00", "status": "ready", "ok": True},
    )
    _write(
        root / "var" / f"workspace-external-credential-recovery-refresh-preflight-current-{stamp}.json",
        {"generated_at": f"{stamp}T00:02:00+00:00", "status": "complete", "ok": True, "summary": {"failed": 0}},
    )
    _write(
        root / "var" / f"complete-goal-evidence-consistency-current-{stamp}.json",
        {"generated_at": f"{stamp}T00:03:00+00:00", "status": "ok", "ok": True, "summary": {"failed": 0}},
    )


def test_refresh_manifest_pre_consistency_bootstrap_uses_latest_existing_current_artifacts(tmp_path):
    mod = load_module("2026-06-10")
    _seed_minimal_current_gate_artifacts(tmp_path, "2026-06-09")
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(
        workspace_root=tmp_path,
        manifest_path=manifest,
        allow_missing_release_evidence=True,
    )

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    assert refreshed["completion_audit_gate"]["evidence_path"] == "var/complete-goal-status-audit-current-2026-06-09.json"
    assert refreshed["unblock_preflight_gate"]["evidence_path"] == "var/complete-goal-unblock-gate-current-2026-06-09.json"
    assert refreshed["recovery_preflight_gate"]["evidence_path"] == (
        "var/workspace-external-credential-recovery-refresh-preflight-current-2026-06-09.json"
    )
    assert refreshed["evidence_consistency_gate"]["evidence_path"] == (
        "var/complete-goal-evidence-consistency-current-2026-06-09.json"
    )
    assert "2026-06-09T00:00:00+00:00" in refreshed["source_of_truth"]["note"]
    assert any(
        Path(item["path"]).name.startswith("complete-goal-status-audit-")
        and item["generated_at"] == "2026-06-09T00:00:00+00:00"
        for item in report["snapshot_paths"]
    )
    assert any(
        Path(item["path"]).name.startswith("complete-goal-unblock-gate-")
        and item["generated_at"] == "2026-06-09T00:01:00+00:00"
        for item in report["snapshot_paths"]
    )
    assert any(
        Path(item["path"]).name.startswith("workspace-external-credential-recovery-refresh-")
        and item["generated_at"] == "2026-06-09T00:02:00+00:00"
        for item in report["snapshot_paths"]
    )


def test_refresh_manifest_writes_snapshot_references_for_available_sources(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(
        manifest,
        {
            "external_steps": {"items": []},
            "worktree": {"changed_paths": []},
            "snapshot_paths": [{"path": "var/release-approval-snapshots/stale.json", "generated_at": "stale"}],
        },
    )
    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)
    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert report["snapshot_paths"]
    assert all("path" in item for item in report["snapshot_paths"])
    assert saved_manifest["snapshot_paths"] == report["snapshot_paths"]
    assert saved_manifest["missing_sources"] == report["missing_sources"]
    assert saved_manifest["allowed_missing_sources"] == report["allowed_missing_sources"]
    assert saved_manifest["evidence_references"]["items"] == report["snapshot_paths"]
    management_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("supabase-pooler-management-probe-")
    )
    side_channel_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("complete-goal-local-credential-side-channel-audit-")
    )
    no_credential_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("complete-goal-no-credential-refresh-")
    )
    release_evidence_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("complete-goal-release-evidence-refresh-")
    )
    mcp_config_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-inventory-health-bridge-config-")
    )
    mcp_live_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-inventory-health-bridge-live-")
    )
    mcp_direct_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-direct-session-probe-")
    )
    mcp_stale_process_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-stale-process-audit-")
    )
    mcp_cleanup_plan_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-stale-process-cleanup-plan-")
    )
    mcp_owner_detail_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-process-owner-detail-")
    )
    mcp_manual_checklist_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-manual-cleanup-checklist-")
    )
    mcp_cleanup_readiness_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-cleanup-readiness-")
    )
    mcp_connector_auth_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-connector-auth-readiness-")
    )
    mcp_auth_diagnostic_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("mcp-auth-diagnostic-")
    )
    shape_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("supabase-pooler-shape-audit-")
    )
    report_scan_refresh_snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-report-secret-scan-refresh-")
    )
    dailynews_report_scan_snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-report-secret-scan-dailynews-")
    )
    getdaytrends_report_scan_snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-report-secret-scan-getdaytrends-")
    )
    assert side_channel_snapshot["generated_at"] == "2026-06-08T04:53:22+00:00"
    assert no_credential_snapshot["generated_at"] == "2026-06-08T04:53:40+00:00"
    assert release_evidence_snapshot["generated_at"] == "2026-06-08T04:53:41+00:00"
    assert mcp_config_snapshot["generated_at"] == "2026-06-08T04:53:26+00:00"
    assert mcp_live_snapshot["generated_at"] == "2026-06-08T04:53:28+00:00"
    assert mcp_direct_snapshot["generated_at"] == "2026-06-08T04:53:29+00:00"
    assert mcp_stale_process_snapshot["generated_at"] == "2026-06-08T04:53:31+00:00"
    assert mcp_cleanup_plan_snapshot["generated_at"] == "2026-06-08T04:53:32+00:00"
    assert mcp_owner_detail_snapshot["generated_at"] == "2026-06-08T04:53:33+00:00"
    assert mcp_manual_checklist_snapshot["generated_at"] == "2026-06-08T04:53:34+00:00"
    assert mcp_cleanup_readiness_snapshot["generated_at"] == "2026-06-08T04:53:35+00:00"
    assert mcp_connector_auth_snapshot["generated_at"] == "2026-06-08T04:53:36+00:00"
    assert mcp_auth_diagnostic_snapshot["generated_at"] == "2026-06-08T04:53:37+00:00"
    assert shape_snapshot["generated_at"] == "2026-06-08T04:53:21+00:00"
    assert management_snapshot["generated_at"] == "2026-06-08T04:53:23+00:00"
    assert report_scan_refresh_snapshot["generated_at"] == "2026-06-08T04:53:28+00:00"
    assert dailynews_report_scan_snapshot["generated_at"] == "2026-06-08T04:53:29+00:00"
    assert getdaytrends_report_scan_snapshot["generated_at"] == "2026-06-08T04:53:30+00:00"


def test_refresh_manifest_snapshots_prompt_checklist_evidence_files(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    status_markdown = tmp_path / "docs" / "reports" / "2026-06" / "COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-06-08.md"
    status_markdown.parent.mkdir(parents=True, exist_ok=True)
    status_markdown.write_text("# Status\n\nCurrent blocker evidence.\n", encoding="utf-8")
    prompt_checklist = tmp_path / "var" / "complete-goal-prompt-to-artifact-checklist-current-2026-06-08.json"
    _write(
        prompt_checklist,
        {
            "generated_at": "2026-06-08T04:54:00+00:00",
            "current_verdict": "not complete",
            "ok": False,
            "summary": {"total": 1, "passed": 0, "blocked": 1, "action_required": 0, "missing_artifacts": ["var/missing.json"]},
            "checklist": [
                {
                    "requirement": "Completion audit green with no blockers",
                    "evidence": [
                        "var/complete-goal-status-audit-current-2026-06-08.json",
                        "docs/reports/2026-06/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-06-08.md",
                        "var/missing.json",
                    ],
                    "missing_evidence": ["var/missing.json"],
                    "artifact_status": ["action_required", "present"],
                    "artifact_status_by_path": {
                        "var/complete-goal-status-audit-current-2026-06-08.json": "action_required",
                        "docs/reports/2026-06/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-06-08.md": "present",
                        "var/missing.json": "missing",
                    },
                    "current_result": "status=action_required",
                    "verdict": "BLOCKED externally",
                }
            ],
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)
    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))

    snapshots_by_source = {item["source_path"]: item for item in report["prompt_checklist_evidence_snapshots"]}
    assert "var/complete-goal-status-audit-current-2026-06-08.json" in snapshots_by_source
    assert "docs/reports/2026-06/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-06-08.md" in snapshots_by_source
    assert "var/missing.json" not in snapshots_by_source
    markdown_snapshot = snapshots_by_source["docs/reports/2026-06/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-06-08.md"]
    assert markdown_snapshot["snapshot_path"].endswith(".md")
    assert (tmp_path / markdown_snapshot["snapshot_path"]).read_text(encoding="utf-8") == "# Status\n\nCurrent blocker evidence.\n"
    assert saved_manifest["prompt_checklist_evidence_snapshots"] == report["prompt_checklist_evidence_snapshots"]
    assert any(item["path"] == markdown_snapshot["snapshot_path"] for item in report["snapshot_paths"])
    assert any(item["path"] == markdown_snapshot["snapshot_path"] for item in saved_manifest["evidence_references"]["items"])


def test_refresh_manifest_falls_back_to_valid_no_credential_snapshot_when_current_failed(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    current = tmp_path / "var" / "complete-goal-no-credential-refresh-current-2026-06-08.json"
    _write(
        current,
        {
            "generated_at": "2026-06-08T05:30:00+00:00",
            "status": "failed_local_gate",
            "ok": False,
            "summary": {"failed_step_count": 1, "failed_steps": ["Ordered release evidence refresh"]},
        },
    )
    valid_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-08"
        / "complete-goal-no-credential-refresh-2026-06-08T052000KST.json"
    )
    _write(
        valid_snapshot,
        {
            "generated_at": "2026-06-08T05:20:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "release_evidence": {
                    "ran": True,
                    "status": "pending_bootstrap",
                    "unexpected_failed_step_count": 0,
                    "bootstrap_pending_release_evidence": True,
                },
                "post_write_finalization": {
                    "ok": True,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_expected_external",
                    "release_approval_unexpected_failures": [],
                    "bootstrap_pending_release_evidence": True,
                },
            },
            "post_write_finalization": {
                "ok": True,
                "manifest": {
                    "no_credential_snapshot": {
                        "present": True,
                        "matches_report_generated_at": True,
                    }
                },
                "release_approval": {
                    "failure_analysis": {
                        "status": "blocked_expected_external",
                        "unexpected_failures": [],
                    }
                },
                "bootstrap_pending_release_evidence": True,
            },
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-no-credential-refresh-")
    )
    assert snapshot["generated_at"] == "2026-06-08T05:20:00+00:00"
    copied = json.loads((tmp_path / snapshot["path"]).read_text(encoding="utf-8"))
    assert copied["status"] == "blocked_expected_external"


def test_refresh_manifest_falls_back_when_current_no_credential_finalization_failed(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    current = tmp_path / "var" / "complete-goal-no-credential-refresh-current-2026-06-08.json"
    _write(
        current,
        {
            "generated_at": "2026-06-08T05:30:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "release_evidence": {
                    "ran": True,
                    "status": "blocked_expected_external",
                    "unexpected_failed_step_count": 0,
                    "release_generated_after_unblock": True,
                    "release_generated_after_side_channel": True,
                },
                "post_write_finalization": {
                    "ok": False,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_unexpected",
                    "release_approval_unexpected_failures": ["self-cycle"],
                },
            },
            "post_write_finalization": {
                "ok": False,
                "manifest": {
                    "no_credential_snapshot": {
                        "present": True,
                        "matches_report_generated_at": True,
                    }
                },
                "release_approval": {
                    "failure_analysis": {
                        "status": "blocked_unexpected",
                        "unexpected_failures": ["self-cycle"],
                    }
                },
            },
        },
    )
    valid_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-08"
        / "complete-goal-no-credential-refresh-2026-06-08T052000KST.json"
    )
    _write(
        valid_snapshot,
        {
            "generated_at": "2026-06-08T05:20:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "release_evidence": {
                    "ran": True,
                    "status": "blocked_expected_external",
                    "unexpected_failed_step_count": 0,
                    "release_generated_after_unblock": True,
                    "release_generated_after_side_channel": True,
                },
                "post_write_finalization": {
                    "ok": True,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_expected_external",
                    "release_approval_unexpected_failures": [],
                },
            },
            "post_write_finalization": {
                "ok": True,
                "manifest": {
                    "no_credential_snapshot": {
                        "present": True,
                        "matches_report_generated_at": True,
                    }
                },
                "release_approval": {
                    "failure_analysis": {
                        "status": "blocked_expected_external",
                        "unexpected_failures": [],
                    }
                },
            },
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-no-credential-refresh-")
    )
    assert snapshot["generated_at"] == "2026-06-08T05:20:00+00:00"
    copied = json.loads((tmp_path / snapshot["path"]).read_text(encoding="utf-8"))
    assert copied["post_write_finalization"]["ok"] is True


def test_refresh_manifest_uses_current_no_credential_post_write_bootstrap(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    current = tmp_path / "var" / "complete-goal-no-credential-refresh-current-2026-06-08.json"
    _write(
        current,
        {
            "generated_at": "2026-06-08T05:30:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "release_evidence": {
                    "ran": True,
                    "status": "blocked_expected_external",
                    "unexpected_failed_step_count": 0,
                    "release_generated_after_unblock": True,
                    "release_generated_after_side_channel": True,
                },
                "post_write_finalization": {
                    "ok": True,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_expected_external",
                    "release_approval_unexpected_failures": [],
                    "bootstrap_pending_post_write_finalization": True,
                },
            },
            "post_write_finalization": {
                "ok": True,
                "manifest": {
                    "no_credential_snapshot": {
                        "present": True,
                        "matches_report_generated_at": True,
                    }
                },
                "release_approval": {
                    "failure_analysis": {
                        "status": "blocked_expected_external",
                        "unexpected_failures": [],
                    }
                },
                "bootstrap_pending_post_write_finalization": True,
            },
        },
    )
    older_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-08"
        / "complete-goal-no-credential-refresh-2026-06-08T052000KST.json"
    )
    _write(
        older_snapshot,
        {
            "generated_at": "2026-06-08T05:20:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "failed_step_count": 0,
                "failed_steps": [],
                "release_evidence": {
                    "ran": True,
                    "status": "blocked_expected_external",
                    "unexpected_failed_step_count": 0,
                    "release_generated_after_unblock": True,
                    "release_generated_after_side_channel": True,
                },
                "post_write_finalization": {
                    "ok": True,
                    "snapshot_matches_report_generated_at": True,
                    "release_approval_status": "blocked_expected_external",
                    "release_approval_unexpected_failures": [],
                },
            },
            "post_write_finalization": {
                "ok": True,
                "manifest": {
                    "no_credential_snapshot": {
                        "present": True,
                        "matches_report_generated_at": True,
                    }
                },
                "release_approval": {
                    "failure_analysis": {
                        "status": "blocked_expected_external",
                        "unexpected_failures": [],
                    }
                },
            },
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-no-credential-refresh-")
    )
    assert snapshot["generated_at"] == "2026-06-08T05:30:00+00:00"
    copied = json.loads((tmp_path / snapshot["path"]).read_text(encoding="utf-8"))
    assert copied["post_write_finalization"]["bootstrap_pending_post_write_finalization"] is True


def test_refresh_manifest_falls_back_to_valid_release_evidence_snapshot_when_current_failed(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    current = tmp_path / "var" / "complete-goal-release-evidence-refresh-current-2026-06-08.json"
    _write(
        current,
        {
            "generated_at": "2026-06-08T05:30:00+00:00",
            "status": "failed_local_gate",
            "ok": False,
            "summary": {
                "consistency": {"ok": False, "status": "fail", "summary": {"failed": 1}},
                "release_approval": {"generated_after_final_manifest_refresh": False},
            },
        },
    )
    valid_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-08"
        / "complete-goal-release-evidence-refresh-2026-06-08T052500KST.json"
    )
    _write(
        valid_snapshot,
        {
            "generated_at": "2026-06-08T05:25:00+00:00",
            "status": "blocked_expected_external",
            "ok": False,
            "summary": {
                "operator_action_coverage": {"ok": True},
                "operator_action_markdown_command_coverage": {"ok": True},
                "operator_action_phase_coverage": {"ok": True},
                "operator_action_safety_coverage": {"ok": True},
                "operator_action_evidence_path_coverage": {"ok": True},
                "operator_action_command_output_coverage": {"ok": True},
                "current_artifact_unexpected_state_coverage": {"ok": True},
                "live_source_detail_coverage": {"ok": True},
                "consistency": {"ok": True, "status": "ok", "summary": {"failed": 0}},
                "release_approval": {
                    "ok": False,
                    "generated_after_final_manifest_refresh": True,
                    "failure_analysis": {
                        "status": "blocked_expected_external",
                        "unexpected_failures": [],
                    },
                },
            },
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-release-evidence-refresh-")
    )
    assert snapshot["generated_at"] == "2026-06-08T05:25:00+00:00"
    copied = json.loads((tmp_path / snapshot["path"]).read_text(encoding="utf-8"))
    assert copied["status"] == "blocked_expected_external"


def test_refresh_manifest_uses_current_release_evidence_for_bootstrap_when_no_valid_snapshot(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    current = tmp_path / "var" / "complete-goal-release-evidence-refresh-current-2026-06-08.json"
    _write(
        current,
        {
            "generated_at": "2026-06-08T05:30:00+00:00",
            "status": "failed_local_gate",
            "ok": False,
            "summary": {
                "operator_action_phase_coverage": {"ok": True},
                "consistency": {"ok": False, "status": "fail", "summary": {"failed": 1}},
                "release_approval": {"generated_after_final_manifest_refresh": False},
            },
        },
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    assert "complete-goal-release-evidence-refresh" not in report["missing_sources"]
    snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("complete-goal-release-evidence-refresh-")
    )
    assert snapshot["generated_at"] == "2026-06-08T05:30:00+00:00"
    copied = json.loads((tmp_path / snapshot["path"]).read_text(encoding="utf-8"))
    assert copied["status"] == "failed_local_gate"


def test_source_or_latest_snapshot_prefers_current_date_snapshot_dir(tmp_path):
    mod = load_module("2026-06-08")
    current_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-08"
        / "mcp-auth-diagnostic-2026-06-08T010000Z.json"
    )
    older_snapshot = (
        tmp_path
        / "var"
        / "release-approval-snapshots"
        / "2026-06-07"
        / "mcp-auth-diagnostic-2026-06-07T235959Z.json"
    )
    _write(current_snapshot, {"generated_at": "2026-06-08T01:00:00+00:00"})
    _write(older_snapshot, {"generated_at": "2026-06-09T01:00:00+00:00"})

    selected = mod._source_or_latest_snapshot(
        tmp_path,
        "mcp-auth-diagnostic",
        tmp_path / "var" / "missing-current.json",
    )

    assert selected == current_snapshot


def test_valid_snapshot_candidates_bounds_validation_to_recent_paths(tmp_path):
    mod = load_module()
    snapshot_root = tmp_path / "snapshots"
    paths: list[Path] = []
    for index in range(mod.SNAPSHOT_FALLBACK_SCAN_LIMIT + 5):
        path = snapshot_root / f"snapshot-{index:03d}" / f"test-label-{index:03d}.json"
        _write(path, {"generated_at": f"2026-06-08T00:{index % 60:02d}:00+00:00"})
        os.utime(path, (index, index))
        paths.append(path)
    validated: list[Path] = []

    def validator(path: Path) -> bool:
        validated.append(path)
        return True

    candidates = mod._valid_snapshot_candidates(snapshot_root, ("*/test-label-*.json",), validator)

    assert len(validated) == mod.SNAPSHOT_FALLBACK_SCAN_LIMIT
    assert candidates == validated
    assert paths[-1] == validated[0]
    assert paths[0] not in validated
    assert paths[4] not in validated
    assert paths[5] in validated


def test_refresh_manifest_root_generated_at_follows_snapshot_payloads(tmp_path, monkeypatch):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=[])
    _write(
        tmp_path / "var" / "complete-goal-evidence-consistency-current-2026-06-08.json",
        {"generated_at": "2026-06-09T00:00:01+00:00", "status": "ok", "summary": {"failed": 0}},
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    class FrozenMoment:
        def __init__(self, iso_value: str, stamp_value: str):
            self.iso_value = iso_value
            self.stamp_value = stamp_value

        def astimezone(self):
            return self

        def isoformat(self):
            return self.iso_value

        def strftime(self, _format: str):
            return self.stamp_value

    class FrozenClock:
        moments = iter(
            [
                FrozenMoment("2026-06-08T23:59:58+00:00", "2026-06-08T235958KST"),
                FrozenMoment("2026-06-09T00:00:02+00:00", "2026-06-09T000002KST"),
            ]
        )

        @classmethod
        def now(cls):
            return next(cls.moments)

    monkeypatch.setattr(mod, "datetime", FrozenClock)

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    consistency_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("complete-goal-evidence-consistency-")
    )
    assert consistency_snapshot["generated_at"] == "2026-06-09T00:00:01+00:00"
    assert refreshed["generated_at"] == "2026-06-09T00:00:02+00:00"
    assert report["generated_at"] == refreshed["generated_at"]


def test_refresh_manifest_allows_missing_consistency_during_bootstrap(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    (tmp_path / "var" / "complete-goal-evidence-consistency-current-2026-06-08.json").unlink()
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest, allow_missing_consistency=True)

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    assert "complete-goal-evidence-consistency" not in report["missing_sources"]
    assert report["allowed_missing_sources"] == ["complete-goal-evidence-consistency"]
    assert refreshed["evidence_consistency_gate"]["ok"] is False
    assert "Evidence consistency pending=True" in refreshed["source_of_truth"]["note"]


def test_refresh_manifest_allows_missing_release_evidence_during_bootstrap(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["x"])
    (tmp_path / "var" / "complete-goal-release-evidence-refresh-current-2026-06-08.json").unlink()
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(
        workspace_root=tmp_path,
        manifest_path=manifest,
        allow_missing_release_evidence=True,
    )

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    assert "complete-goal-release-evidence-refresh" not in report["missing_sources"]
    assert report["allowed_missing_sources"] == ["complete-goal-release-evidence-refresh"]
    assert refreshed["allowed_missing_sources"] == ["complete-goal-release-evidence-refresh"]
    assert not any(
        Path(item["path"]).name.startswith("complete-goal-release-evidence-refresh-")
        for item in report["snapshot_paths"]
    )


def test_refresh_manifest_prefers_successful_full_matrix_recovery_report(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=[])
    _write_ok_full_matrix_recovery(tmp_path)
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    recovery_snapshot = next(
        item
        for item in report["snapshot_paths"]
        if Path(item["path"]).name.startswith("workspace-external-credential-recovery-refresh-")
    )
    assert recovery_snapshot["generated_at"] == "2026-06-08T06:30:00+00:00"
    assert refreshed["recovery_preflight_gate"]["ok"] is True
    assert refreshed["recovery_preflight_gate"]["evidence_path"] == (
        "var/workspace-external-credential-recovery-refresh-current-full-matrix-2026-06-08.json"
    )
    assert "--continue-on-failure" in refreshed["recovery_preflight_gate"]["command"]
    assert "--allow-blocked-external" in refreshed["recovery_preflight_gate"]["command"]
    assert "WORKSPACE_EXTERNAL_CREDENTIAL_RECOVERY_REFRESH_CURRENT_FULL_MATRIX_2026-06-08.md" in refreshed["recovery_preflight_gate"]["command"]


def test_refresh_manifest_gate_commands_follow_report_month(tmp_path):
    mod = load_module("2026-07-03")
    _seed_minimal_current_gate_artifacts(tmp_path, "2026-07-03")
    manifest = tmp_path / "docs" / "reports" / "2026-07" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-07-03.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    command_text = "\n".join(
        [
            refreshed["completion_audit_gate"]["command"],
            refreshed["unblock_preflight_gate"]["command"],
            refreshed["evidence_consistency_gate"]["command"],
        ]
    )
    assert "--check-live-sources" in refreshed["completion_audit_gate"]["command"]
    assert "--auto-refresh-radar" in refreshed["completion_audit_gate"]["command"]
    assert "--radar-markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md" in command_text
    assert "docs/reports/2026-07/COMPLETE_GOAL_STATUS_AUDIT_CURRENT_2026-07-03.md" in command_text
    assert "docs/reports/2026-07/COMPLETE_GOAL_UNBLOCK_GATE_CURRENT_2026-07-03.md" in command_text
    assert "docs/reports/2026-07/COMPLETE_GOAL_EVIDENCE_CONSISTENCY_CURRENT_2026-07-03.md" in command_text
    assert "docs/reports/2026-06/COMPLETE_GOAL_" not in command_text


def test_refresh_manifest_rebuilds_external_step_evidence_from_current_artifacts(tmp_path):
    mod = load_module()
    blockers = [
        "dailynews_first_run_launch_ready",
        "getdaytrends_strict_readiness_pass",
        "getdaytrends_canonical_smoke_pass",
    ]
    _seed_core_gate_artifacts(tmp_path, blockers=blockers)
    _write(
        tmp_path / "var" / "dailynews-post-supabase-credential-input-status-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:24+00:00",
            "status": "unchanged",
            "ok": True,
            "wrapper_rerun_recommended": False,
            "credential_source_signal_present": False,
        },
    )
    _write(
        tmp_path / "var" / "getdaytrends-credential-input-status-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:25+00:00",
            "status": "unchanged",
            "credential_source_signal_present": False,
            "safe_to_skip_strict_readiness_until_credential_inputs_change": True,
        },
    )
    _write(
        tmp_path / "var" / "getdaytrends-credential-input-status-current.json",
        {
            "generated_at": "2026-06-08T04:53:29+00:00",
            "status": "unchanged",
            "credential_source_signal_present": False,
            "safe_to_skip_strict_readiness_until_credential_inputs_change": True,
        },
    )
    _write(
        tmp_path / "var" / "dailynews-db-pooler-username-variant-probes-current-2026-06-08.json",
        {"generated_at": "2026-06-08T04:53:26+00:00", "variant_count": 4, "db_success_count": 0},
    )
    _write(
        tmp_path / "var" / "dailynews-db-direct-host-probe-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:53:27+00:00",
            "safe_to_share": True,
            "contains_secret_values": False,
            "source_shape": {"project_refs_match": True},
            "db_success_count": 0,
            "conclusion": {"direct_host_with_same_password_success": False},
        },
    )
    _write(
        tmp_path / "var" / "complete-goal-scheduled-task-resume-current-2026-06-08.json",
        {
            "generated_at": "2026-06-08T04:54:13+00:00",
            "status": "blocked",
            "ok": False,
            "dry_run": True,
            "gates": {"all_ok": False},
            "tasks": {
                "after": [
                    {
                        "task_name": "DailyNews_Morning_Insights",
                        "status": "Disabled",
                        "scheduled_task_state": "Disabled",
                    }
                ]
            },
        },
    )
    _write(
        tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json",
        {"generated_at": "2026-06-08T05:03:50+09:00", "status": "complete", "summary": {"failed": 1}},
    )
    _write_getdaytrends_readiness_sidecars(
        tmp_path,
        generated_at="2026-06-08T05:03:52+09:00",
        provider={"generated_at": "2026-06-08T05:03:53+09:00", "status": "clear", "issue_types": []},
        supabase={
            "generated_at": "2026-06-08T05:03:54+09:00",
            "status": "blocked",
            "issue_types": ["live_db_doctor_failed"],
        },
    )
    _write(
        tmp_path / "automation" / "getdaytrends" / "logs" / "smoke" / "dashboard_browser_latest.json",
        {"generated_at": "2026-06-08T05:03:55+09:00", "summary": {"failed": 0}},
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(
        manifest,
        {
            "external_steps": {
                "items": [
                    {"name": "stale", "status": "blocked", "evidence": "stale 2026-06-08T03:40:14+00:00"}
                ]
            },
            "worktree": {"changed_paths": []},
        },
    )

    mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    items = refreshed["external_steps"]["items"]
    assert [item["status"] for item in items] == ["not_applicable", "blocked", "blocked"]
    evidence = "\n".join(item["evidence"] for item in items)
    assert "stale" not in evidence
    assert "2026-06-08T03:40:14" not in evidence
    assert "2026-06-08T04:53:24+00:00" in evidence
    assert "getdaytrends credential input status generated 2026-06-08T04:53:29+00:00" in evidence
    assert "Sanitized direct DB host diagnostic probe generated 2026-06-08T04:53:27+00:00" in evidence
    assert "direct_host_with_same_password_success=False" in evidence
    assert "Supabase Management API pooler probe generated 2026-06-08T04:53:23+00:00" in evidence
    assert "transaction_pooler_count=0" in evidence
    assert "Local credential side-channel audit generated 2026-06-08T04:53:22+00:00" in evidence
    assert "new_local_credential_signal_present=False" in evidence
    assert "Ordered no-credential refresh generated 2026-06-08T04:53:40+00:00" in evidence
    assert "release_generated_after_unblock=True" in evidence
    assert "release_generated_after_side_channel=True" in evidence
    assert "Supabase pooler shape audit generated 2026-06-08T04:53:21+00:00" in evidence
    assert "obvious_pooler_shape_fix_available=False" in evidence
    assert "2026-06-08T05:03:54+09:00" in evidence
    assert "apply_workspace_supabase_pooler_url.ps1" in evidence
    assert "apply_workspace_supabase_pooler_url.ps1 -PreviewOnly -NonInteractive" in evidence
    assert "apply_workspace_supabase_pooler_url.ps1 -NonInteractive" in evidence
    assert "WORKSPACE_NEW_SUPABASE_POOLER_DATABASE_URL" in evidence
    assert "complete encoded URL" in evidence
    assert "redacted dry-run preview" in evidence
    assert "requires typing APPLY before writing" in evidence
    assert "same-run recovery is requested" in evidence
    assert "workspace-wide corrected Transaction pooler URL" in evidence
    assert "one shared corrected URL" not in evidence
    assert "ops/scripts/complete_goal_unblock_gate.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/complete_goal_gate_common.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_complete_goal_unblock_gate.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/complete_goal_no_credential_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_complete_goal_no_credential_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/complete_goal_release_evidence_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_complete_goal_release_evidence_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/release_approval_check.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_release_approval_check.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/complete_goal_resume_scheduled_tasks.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_complete_goal_resume_scheduled_tasks.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/apply_workspace_supabase_pooler_url.ps1" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/dailynews_update_database_url.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/getdaytrends_update_credentials.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/generate_context_snapshot.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/run_workspace_smoke.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/session_bootstrap.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/workspace_smoke_report.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/check_mcp_health.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/mcp_service_inventory.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/mcp_inventory_health_bridge.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/supabase_pooler_management_probe.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/supabase_pooler_shape_audit.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/auto_research_status.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/dailynews_launch_secret_scan.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/getdaytrends_launch_handoff_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "ops/scripts/getdaytrends_launch_secret_scan.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_auto_research_status.py" in refreshed["worktree"]["changed_paths"]
    assert "automation/getdaytrends/scripts/verify_supabase_recovery_packet.py" in refreshed["worktree"]["changed_paths"]
    assert "automation/getdaytrends/scripts/verify_provider_auth_recovery_packet.py" in refreshed["worktree"]["changed_paths"]
    assert "automation/getdaytrends/tests/test_verify_recovery_packet_scripts.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_dailynews_update_database_url.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_getdaytrends_update_credentials.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_workspace_smoke.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_ops_scripts_reports.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_mcp_service_inventory.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_mcp_inventory_health_bridge.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_supabase_pooler_management_probe.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_dailynews_launch_secret_scan.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_getdaytrends_launch_handoff_refresh.py" in refreshed["worktree"]["changed_paths"]
    assert "tests/test_getdaytrends_launch_secret_scan.py" in refreshed["worktree"]["changed_paths"]
    assert "docs/QUALITY_GATE.md" in refreshed["worktree"]["changed_paths"]


def test_refresh_manifest_uses_current_getdaytrends_packet_sources(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["getdaytrends_strict_readiness_pass"])
    readiness_dir = tmp_path / "automation" / "getdaytrends" / "logs" / "readiness"
    _write(readiness_dir / "provider_auth_recovery_latest.json", {"generated_at": "legacy-provider", "status": "legacy"})
    _write(readiness_dir / "supabase_recovery_latest.json", {"generated_at": "legacy-supabase", "status": "legacy"})
    _write(
        readiness_dir / "provider_auth_recovery_packet_latest.json",
        {"generated_at": "current-provider-packet", "status": "clear", "issue_types": []},
    )
    _write(
        readiness_dir / "strict_provider_auth_recovery_packet_latest.json",
        {"generated_at": "current-provider-packet", "status": "clear", "issue_types": []},
    )
    _write(
        readiness_dir / "supabase_recovery_packet_latest.json",
        {"generated_at": "current-supabase-packet", "status": "blocked", "issue_types": ["live_db_doctor_failed"]},
    )
    _write(
        readiness_dir / "strict_supabase_recovery_packet_latest.json",
        {"generated_at": "current-supabase-packet", "status": "blocked", "issue_types": ["live_db_doctor_failed"]},
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)

    provider_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("getdaytrends-provider-auth-recovery-packet-")
    )
    supabase_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("getdaytrends-supabase-recovery-packet-")
    )
    assert provider_snapshot["generated_at"] == "current-provider-packet"
    assert supabase_snapshot["generated_at"] == "current-supabase-packet"
    assert "legacy-provider" not in json.dumps(report, ensure_ascii=False)
    assert "legacy-supabase" not in json.dumps(report, ensure_ascii=False)


def test_refresh_manifest_dailynews_evidence_selectors_fall_back_to_latest_non_current_artifacts(tmp_path):
    mod = load_module()
    var_dir = tmp_path / "var"
    _write(
        var_dir / "dailynews-first-run-verifier-current-2026-06-08.json",
        {"generated_at": "2026-06-08T00:01:00+00:00", "launch_ready": False},
    )
    verifier = var_dir / "dailynews-first-run-verifier-loop12-final.json"
    _write(verifier, {"generated_at": "2026-06-08T00:03:00+00:00", "launch_ready": False})
    _write(
        var_dir / "dailynews-first-run-verifier-smoke-loop12-final.json",
        {"generated_at": "2026-06-08T00:04:00+00:00", "launch_ready": False},
    )
    _write(
        var_dir / "dailynews-x-ops-browser-smoke-current-2026-06-08.json",
        {"generated_at": "2026-06-08T00:01:00+00:00", "ok": True},
    )
    browser = var_dir / "dailynews-x-ops-browser-smoke-mcp.json"
    _write(browser, {"generated_at": "2026-06-08T00:03:00+00:00", "ok": True})

    assert mod._latest_dailynews_first_run_verifier(tmp_path) == verifier
    assert mod._latest_dailynews_x_ops_browser_smoke(tmp_path) == browser


def test_dailynews_evidence_selectors_use_prefix_metadata_before_full_json_load(tmp_path, monkeypatch):
    mod = load_module()
    var_dir = tmp_path / "var"
    older = var_dir / "dailynews-first-run-verifier-current-2026-06-08.json"
    verifier = var_dir / "dailynews-first-run-verifier-loop12-final.json"
    browser = var_dir / "dailynews-x-ops-browser-smoke-mcp.json"
    _write(older, {"generated_at": "2026-06-08T00:01:00+00:00", "launch_ready": False, "large": "x" * 100000})
    _write(verifier, {"generated_at": "2026-06-08T00:03:00+00:00", "launch_ready": False, "large": "x" * 100000})
    _write(browser, {"generated_at": "2026-06-08T00:04:00+00:00", "ok": True, "large": "x" * 100000})

    def fail_full_json_load(path):
        raise AssertionError(f"unexpected full JSON load for {path}")

    monkeypatch.setattr(mod, "load_json", fail_full_json_load)

    assert mod._latest_dailynews_first_run_verifier(tmp_path) == verifier
    assert mod._latest_dailynews_x_ops_browser_smoke(tmp_path) == browser


def test_release_evidence_snapshot_lookup_stops_after_newest_valid_date(tmp_path, monkeypatch):
    mod = load_module("2026-06-12")
    snapshot_root = tmp_path / "var" / "release-approval-snapshots"
    current = snapshot_root / "2026-06-12" / "2026-06-12T000000KST" / "complete-goal-release-evidence-refresh-current.json"
    valid = snapshot_root / "2026-06-11" / "2026-06-11T235959KST" / "complete-goal-release-evidence-refresh-valid.json"
    older = snapshot_root / "2026-06-10" / "2026-06-10T235959KST" / "complete-goal-release-evidence-refresh-older.json"
    for path in (current, valid, older):
        _write(path, {"generated_at": path.stem})
    visited: list[str] = []

    def validator(path):
        visited.append(path.as_posix())
        return path == valid

    monkeypatch.setattr(mod, "_release_evidence_refresh_status_valid", validator)

    assert mod._latest_valid_release_evidence_snapshot(tmp_path, "complete-goal-release-evidence-refresh") == valid
    assert any("2026-06-12" in path for path in visited)
    assert any("2026-06-11" in path for path in visited)
    assert not any("2026-06-10" in path for path in visited)


def test_refresh_manifest_uses_latest_complete_getdaytrends_workspace_smoke(tmp_path):
    mod = load_module()
    _seed_core_gate_artifacts(tmp_path, blockers=["getdaytrends_canonical_smoke_pass"])
    _write(
        tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json",
        {
            "generated_at": "2026-06-08T01:00:00+00:00",
            "status": "complete",
            "summary": {"total": 6, "completed": 6, "passed": 3, "failed": 3, "remaining": 0},
        },
    )
    _write(
        tmp_path / "var" / "workspace-smoke-getdaytrends-recovery-verifiers-2026-06-08.json",
        {
            "generated_at": "2026-06-08T06:46:12+00:00",
            "status": "complete",
            "summary": {"total": 6, "completed": 6, "passed": 5, "failed": 1, "remaining": 0},
        },
    )
    _write(
        tmp_path / "var" / "workspace-smoke-getdaytrends-newer-partial.json",
        {
            "generated_at": "2026-06-08T07:00:00+00:00",
            "status": "partial",
            "summary": {"total": 6, "completed": 3, "passed": 3, "failed": 0, "remaining": 3},
        },
    )
    _write(
        tmp_path / "var" / "workspace-smoke-getdaytrends-readiness-only-recheck.json",
        {
            "generated_at": "2026-06-08T07:30:00+00:00",
            "status": "complete",
            "summary": {"total": 1, "completed": 1, "passed": 0, "failed": 1, "remaining": 0},
        },
    )
    _write_getdaytrends_readiness_sidecars(
        tmp_path,
        generated_at="2026-06-08T06:47:52+00:00",
    )
    manifest = tmp_path / "docs" / "reports" / "2026-06" / "RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json"
    _write(manifest, {"external_steps": {"items": []}, "worktree": {"changed_paths": []}})

    report = mod.refresh_manifest(workspace_root=tmp_path, manifest_path=manifest)
    refreshed = json.loads(manifest.read_text(encoding="utf-8"))

    smoke_snapshot = next(
        item for item in report["snapshot_paths"] if Path(item["path"]).name.startswith("workspace-smoke-getdaytrends-launch-final-")
    )
    assert smoke_snapshot["generated_at"] == "2026-06-08T06:46:12+00:00"
    evidence = "\n".join(item["evidence"] for item in refreshed["external_steps"]["items"])
    assert "passed': 5" in evidence or '"passed": 5' in evidence
    assert "passed': 3" not in evidence
