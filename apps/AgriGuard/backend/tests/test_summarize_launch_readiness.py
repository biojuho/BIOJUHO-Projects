from __future__ import annotations

import importlib.util
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "summarize_launch_readiness.py"
SPEC = importlib.util.spec_from_file_location("summarize_launch_readiness", SCRIPT_PATH)
assert SPEC is not None
summarize_launch_readiness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(summarize_launch_readiness)


def test_launch_readiness_summary_classifies_missing_evidence(tmp_path: Path) -> None:
    summary = summarize_launch_readiness.build_summary(
        launch_report_json=tmp_path / "missing-launch.json",
        env_validation_json=tmp_path / "missing-validation.json",
        operator_packet_json=tmp_path / "missing-packet.json",
        app_root=APP_ROOT,
    )

    assert summary["status"] == "unknown"
    assert summary["blocker_class"] == "no_launch_evidence"
    assert summary["secrets_redacted"] is True


def test_launch_readiness_summary_classifies_env_shape_blocker(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps(
            {
                "status": "fail",
                "blocker_class": "env_shape_blocked",
                "ready_for_preflight": False,
                "placeholder_count": 6,
                "missing_required_keys": ["AGRIGUARD_SECRET_KEY"],
                "forbidden_flags_enabled": [],
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_launch_readiness.build_summary(
        launch_report_json=tmp_path / "missing-launch.json",
        env_validation_json=validation,
        operator_packet_json=tmp_path / "missing-packet.json",
        app_root=APP_ROOT,
    )

    assert summary["status"] == "blocked"
    assert summary["blocker_class"] == "env_shape_blocked"
    assert summary["reports"]["env_validation"]["blocker_class"] == "env_shape_blocked"
    assert summary["reports"]["env_validation"]["placeholder_count"] == 6
    assert "AGRIGUARD_SECRET_KEY" in summary["reports"]["env_validation"]["missing_required_keys"]


def test_launch_readiness_markdown_summarizes_env_shape_action_ids(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    packet = tmp_path / "packet.json"
    validation.write_text(
        json.dumps(
            {
                "status": "fail",
                "blocker_class": "env_shape_blocked",
                "ready_for_preflight": False,
                "placeholder_count": 6,
                "missing_required_keys": ["AGRIGUARD_SECRET_KEY"],
                "forbidden_flags_enabled": [],
            }
        ),
        encoding="utf-8",
    )
    packet.write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "env_shape_blocked",
                "preflight_status": "env_shape_blocked",
                "blocking_action_count": 1,
                "operator_actions": [{"id": "fix_env_shape_validation"}],
                "safe_rerun_commands": [
                    "& python validate_launch_env_template.py",
                    "& python run_guarded_launch.py",
                ],
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
    summary = summarize_launch_readiness.build_summary(
        launch_report_json=tmp_path / "missing-launch.json",
        env_validation_json=validation,
        operator_packet_json=packet,
        app_root=APP_ROOT,
    )

    markdown = summarize_launch_readiness.render_markdown(summary)

    assert "- Env validation ready for preflight: `false`" in markdown
    assert "- Env validation blocker class: `env_shape_blocked`" in markdown
    assert "- Env validation placeholder count: `6`" in markdown
    assert "- Operator packet blocker class: `env_shape_blocked`" in markdown
    assert "- Operator packet preflight status: `env_shape_blocked`" in markdown
    assert "- Operator action IDs: `fix_env_shape_validation`" in markdown
    assert "## Next Commands" in markdown
    assert "`validate_env_template` (powershell): `& python validate_launch_env_template.py`" in markdown
    assert "`guarded_launch` (powershell): `& python run_guarded_launch.py`" in markdown


def test_launch_readiness_markdown_filters_malformed_next_actions() -> None:
    markdown = summarize_launch_readiness.render_markdown(
        {
            "status": "blocked",
            "blocker_class": "preflight_blocked",
            "secrets_redacted": True,
            "reports": {},
            "next_actions": [
                "Open the operator packet.",
                {"action": "not markdown-safe"},
            ],
            "next_commands": [],
        }
    )

    assert "- Open the operator packet." in markdown
    assert "not markdown-safe" not in markdown
    assert "{'action':" not in markdown


def test_launch_readiness_summary_classifies_preflight_blocker(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    launch = tmp_path / "launch.json"
    packet = tmp_path / "packet.json"
    validation.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "ready_for_preflight": True,
                "placeholder_count": 0,
            }
        ),
        encoding="utf-8",
    )
    launch.write_text(
        json.dumps(
            {
                "status": "fail",
                "blocker_class": "preflight_blocked",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
                "run_browser_smoke": True,
                "results": [{"name": "env_validation"}, {"name": "preflight"}, {"name": "operator_packet"}],
                "child_reports": {
                    "env_validation": {
                        "status": "pass",
                        "blocker_class": "ready",
                        "ready_for_preflight": True,
                    },
                    "preflight": {"status": "fail"},
                    "operator_packet": {
                        "status": "blocked",
                        "operator_action_ids": ["set_firebase_service_account_file"],
                    },
                    "browser_smoke": {
                        "found": False,
                        "path": str(tmp_path / "browser-smoke.json"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    packet.write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "operator_values_required",
                "preflight_status": "fail",
                "blocking_action_count": 1,
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
                "preflight_checks": {
                    "runtime": "compose",
                    "docker_checked": True,
                    "firebase_credentials_source": "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
                    "firebase_credentials_resolved_path": "C:/secure/missing-firebase.json",
                },
                "safe_rerun_commands": [
                    "& python validate_launch_env_template.py",
                    "& python run_guarded_launch.py",
                    "& python launch_env_preflight.py",
                    "& python launch_compose.py",
                ],
                "guarded_launch_evidence": {
                    "artifact_index_readiness_summary": {
                        "status": "pass",
                        "blocker_class": "ready",
                        "consumer_packet_validation_status": "pass",
                        "consumer_command_metadata_status": "pass",
                        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                        "recovery_command_status": "not_required",
                    }
                },
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_launch_readiness.build_summary(
        launch_report_json=launch,
        env_validation_json=validation,
        operator_packet_json=packet,
        app_root=APP_ROOT,
    )

    assert summary["status"] == "blocked"
    assert summary["blocker_class"] == "preflight_blocked"
    assert summary["reports"]["launch"]["blocker_class"] == "preflight_blocked"
    assert summary["reports"]["env_validation"]["blocker_class"] == "ready"
    assert summary["reports"]["launch"]["env_validation_blocker_class"] == "ready"
    assert summary["reports"]["launch"]["result_names"] == ["env_validation", "preflight", "operator_packet"]
    assert summary["reports"]["launch"]["browser_smoke"]["found"] is False
    assert summary["reports"]["launch"]["browser_smoke"]["path"].endswith("browser-smoke.json")
    assert summary["reports"]["operator_packet"]["blocker_class"] == "operator_values_required"
    assert summary["reports"]["operator_packet"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert summary["reports"]["operator_packet"]["preflight_checks"]["firebase_credentials_resolved_path"] == (
        "C:/secure/missing-firebase.json"
    )
    assert summary["reports"]["operator_packet"]["artifact_index_status"] == "pass"
    assert summary["reports"]["operator_packet"]["artifact_index_blocker_class"] == "ready"
    assert summary["reports"]["operator_packet"]["consumer_packet_validation_status"] == "pass"
    assert summary["reports"]["operator_packet"]["consumer_command_metadata_status"] == "pass"
    assert (
        summary["reports"]["operator_packet"]["consumer_readiness_operator_packet_consumer_command_metadata_status"]
        == "pass"
    )
    assert summary["reports"]["operator_packet"]["artifact_index_recovery_command_status"] == "not_required"
    assert summary["next_actions"] == [
        "Open the operator packet for exact variables and validation commands.",
        (
            "Provide a real Firebase Admin service-account .json at an absolute host path outside the repo for "
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE."
        ),
        "Rerun strict preflight before compose.",
    ]
    assert summary["next_commands"] == [
        {
            "name": "validate_env_template",
            "command": "& python validate_launch_env_template.py",
            "shell": "powershell",
        },
        {"name": "guarded_launch", "command": "& python run_guarded_launch.py", "shell": "powershell"},
        {"name": "strict_preflight", "command": "& python launch_env_preflight.py", "shell": "powershell"},
        {"name": "compose_launch", "command": "& python launch_compose.py", "shell": "powershell"},
    ]
    markdown = summarize_launch_readiness.render_markdown(summary)
    assert "- Artifact index status: `pass`" in markdown
    assert "- Artifact index blocker class: `ready`" in markdown
    assert "- Launch report blocker class: `preflight_blocked`" in markdown
    assert "- Operator packet blocker class: `operator_values_required`" in markdown
    assert "- Artifact index consumer packet validation: `pass`" in markdown
    assert "- Consumer command metadata: `pass`" in markdown
    assert "- Consumer readiness command metadata: `pass`" in markdown
    assert "- Artifact index recovery command status: `not_required`" in markdown
    assert "## Operator Packet Preflight Checks" in markdown
    assert "| `firebase_credentials_resolved_path` | `C:/secure/missing-firebase.json` |" in markdown
    assert "Provide a real Firebase Admin service-account .json at an absolute host path outside the repo" in markdown


def test_launch_readiness_summary_classifies_ready_launch(tmp_path: Path) -> None:
    launch = tmp_path / "launch.json"
    validation = tmp_path / "validation.json"
    launch.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "stage": "browser_smoke",
                "stop_reason": None,
                "results": [],
                "child_reports": {
                    "browser_smoke": {
                        "found": True,
                        "path": str(tmp_path / "browser-smoke.json"),
                        "status": "pass",
                        "base_url": "http://127.0.0.1:5330",
                        "api_url": "http://127.0.0.1:8060",
                        "mobile": True,
                        "include_unavailable_check": True,
                        "summary": {
                            "total": 7,
                            "passed": 7,
                            "failed": 0,
                            "checks_total": 191,
                            "checks_passed": 191,
                            "checks_failed": 0,
                            "prechecks_total": 3,
                            "prechecks_passed": 3,
                            "prechecks_failed": 0,
                            "screenshot_artifacts_total": 19,
                            "screenshot_artifacts_passed": 19,
                            "screenshot_artifacts_failed": 0,
                            "failed_step_names": [],
                            "failed_precheck_names": [],
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    validation.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "ready_for_preflight": True,
                "placeholder_count": 0,
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_launch_readiness.build_summary(
        launch_report_json=launch,
        env_validation_json=validation,
        operator_packet_json=tmp_path / "missing-packet.json",
        app_root=APP_ROOT,
    )

    assert summary["status"] == "ready"
    assert summary["blocker_class"] == "ready"
    browser_smoke = summary["reports"]["launch"]["browser_smoke"]
    assert browser_smoke["status"] == "pass"
    assert browser_smoke["mobile"] is True
    assert browser_smoke["steps_passed"] == 7
    assert browser_smoke["checks_passed"] == 191
    markdown = summarize_launch_readiness.render_markdown(summary)
    assert "## Browser Smoke Evidence" in markdown
    assert "| `status` | `pass` |" in markdown
    assert "| `checks` | `191/191` |" in markdown
    assert "| `screenshots` | `19/19` |" in markdown


def test_launch_readiness_summary_main_writes_outputs_and_exits_nonzero_when_blocked(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    json_out = tmp_path / "summary.json"
    markdown_out = tmp_path / "summary.md"
    validation.write_text(json.dumps({"status": "fail", "ready_for_preflight": False}), encoding="utf-8")

    result = summarize_launch_readiness.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--launch-report-json",
            str(tmp_path / "missing-launch.json"),
            "--env-validation-json",
            str(validation),
            "--operator-packet-json",
            str(tmp_path / "missing-packet.json"),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert result == 1
    assert json.loads(json_out.read_text(encoding="utf-8"))["blocker_class"] == "env_shape_blocked"
    assert "Blocker class: `env_shape_blocked`" in markdown_out.read_text(encoding="utf-8")
