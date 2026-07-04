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
    assert summary["reports"]["env_validation"]["placeholder_count"] == 6
    assert "AGRIGUARD_SECRET_KEY" in summary["reports"]["env_validation"]["missing_required_keys"]


def test_launch_readiness_summary_classifies_preflight_blocker(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    launch = tmp_path / "launch.json"
    packet = tmp_path / "packet.json"
    validation.write_text(
        json.dumps({"status": "pass", "ready_for_preflight": True, "placeholder_count": 0}),
        encoding="utf-8",
    )
    launch.write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
                "run_browser_smoke": True,
                "results": [{"name": "env_validation"}, {"name": "preflight"}, {"name": "operator_packet"}],
                "child_reports": {
                    "env_validation": {"status": "pass", "ready_for_preflight": True},
                    "preflight": {"status": "fail"},
                    "operator_packet": {
                        "status": "blocked",
                        "operator_action_ids": ["set_firebase_service_account_file"],
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
                "preflight_status": "fail",
                "blocking_action_count": 1,
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
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
    assert summary["reports"]["launch"]["result_names"] == ["env_validation", "preflight", "operator_packet"]
    assert summary["reports"]["operator_packet"]["operator_action_ids"] == ["set_firebase_service_account_file"]


def test_launch_readiness_summary_classifies_ready_launch(tmp_path: Path) -> None:
    launch = tmp_path / "launch.json"
    validation = tmp_path / "validation.json"
    launch.write_text(
        json.dumps({"status": "pass", "stage": "browser_smoke", "stop_reason": None, "results": []}),
        encoding="utf-8",
    )
    validation.write_text(
        json.dumps({"status": "pass", "ready_for_preflight": True, "placeholder_count": 0}),
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
