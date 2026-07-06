from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "index_guarded_launch_artifacts.py"
SPEC = importlib.util.spec_from_file_location("index_guarded_launch_artifacts", SCRIPT_PATH)
assert SPEC is not None
index_guarded_launch_artifacts = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(index_guarded_launch_artifacts)

RUN_WRAPPER = index_guarded_launch_artifacts.run_guarded_launch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_core_artifacts(output_dir: Path, prefix: str) -> dict[str, Path]:
    paths = index_guarded_launch_artifacts._artifact_paths(output_dir.resolve(), prefix, None)
    _write_json(
        paths["launch_report_json"],
        {
            "generated_at": "2026-07-06T12:54:58Z",
            "status": "fail",
            "stage": "preflight",
            "stop_reason": "preflight_failed",
            "results": [{"name": "preflight"}],
        },
    )
    _write_json(paths["handoff_json"], {"generated_at": "2026-07-06T12:54:59Z", "status": "blocked"})
    paths["handoff_markdown"].write_text("# Handoff\n", encoding="utf-8")
    _write_json(
        paths["handoff_validation_json"],
        {
            "generated_at": "2026-07-06T12:55:00Z",
            "status": "pass",
            "blocker_class": "ready",
            "errors": [],
            "handoff_sha256": "abc",
            "schema_sha256": "def",
        },
    )
    _write_json(
        paths["handoff_consumer_json"],
        {
            "generated_at": "2026-07-06T12:55:01Z",
            "status": "fail",
            "blocker_class": "preflight_blocked",
            "validation_matches_handoff": True,
            "validation_status": "pass",
            "packet_validation_status": "pass",
            "packet_evidence_outputs_status": "pass",
            "packet_evidence_outputs_blocker_class": "ready",
            "packet_markdown_table_status": "pass",
            "packet_markdown_table_blocker_class": "ready",
            "packet_path_mismatch_count": 0,
            "ready_gate_command_shell": "powershell",
            "ready_gate_command_text": (
                "& python run_guarded_launch.py --status-only --env-file operator.env "
                "--require-ready --status-json-out ready-gate.json"
            ),
            "operator_command_count": 2,
            "operator_command_text_count": 2,
            "operator_commands": [
                {
                    "id": "inspect_status",
                    "description": "Print the compact guarded-launch status view.",
                    "command_shell": "powershell",
                    "command_text": "& python run_guarded_launch.py --status-only --env-file operator.env",
                },
                {
                    "id": "require_ready",
                    "description": "Fail closed unless the selected guarded-launch prefix is ready.",
                    "command_shell": "powershell",
                    "command_text": (
                        "& python run_guarded_launch.py --status-only --env-file operator.env "
                        "--require-ready --status-json-out ready-gate.json"
                    ),
                },
            ],
            "handoff_validation_command_shell": "powershell",
            "handoff_validation_command_text": "& python validate_guarded_launch_handoff.py handoff.json",
            "readiness_operator_action_ids": ["fix_env_shape_validation"],
            "readiness_next_actions": [
                "Replace env template placeholders and sample domains.",
                "Rerun validate_launch_env_template.py on the filled env file.",
            ],
            "readiness_next_commands": [
                {
                    "name": "validate_env_template",
                    "command": "& python validate_launch_env_template.py",
                    "shell": "powershell",
                }
            ],
            "readiness_env_validation_blocker_class": "env_shape_blocked",
            "readiness_env_validation_ready_for_preflight": False,
            "readiness_env_validation_placeholder_count": 6,
            "readiness_operator_packet_preflight_status": "env_shape_blocked",
            "readiness_operator_packet_consumer_command_metadata_status": "pass",
            "errors": [],
        },
    )
    return paths


def test_index_guarded_launch_artifacts_passes_complete_blocked_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_core_artifacts(output_dir, "blocked")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)
    artifacts_by_role = {
        artifact["role"]: artifact
        for artifact in index["artifacts"]
        if isinstance(artifact, dict)
    }

    assert index["status"] == "pass"
    assert index["generated_at"].endswith("Z")
    index["generated_at"].encode("ascii")
    assert " " not in index["generated_at"]
    assert index["blocker_class"] == "ready"
    assert index["consumer_status"] == "fail"
    assert index["consumer_blocker_class"] == "preflight_blocked"
    assert index["validation_status"] == "pass"
    assert index["validation_blocker_class"] == "ready"
    assert index["consumer_packet_validation_status"] == "pass"
    assert index["consumer_packet_evidence_outputs_status"] == "pass"
    assert index["consumer_packet_evidence_outputs_blocker_class"] == "ready"
    assert index["consumer_packet_markdown_table_status"] == "pass"
    assert index["consumer_packet_markdown_table_blocker_class"] == "ready"
    assert index["consumer_readiness_operator_action_ids"] == ["fix_env_shape_validation"]
    assert index["consumer_readiness_next_actions"] == [
        "Replace env template placeholders and sample domains.",
        "Rerun validate_launch_env_template.py on the filled env file.",
    ]
    assert index["consumer_readiness_next_commands"] == [
        {
            "name": "validate_env_template",
            "command": "& python validate_launch_env_template.py",
            "shell": "powershell",
        }
    ]
    assert index["consumer_command_metadata_status"] == "pass"
    assert index["consumer_readiness_env_validation_blocker_class"] == "env_shape_blocked"
    assert index["consumer_ready_gate_command_shell"] == "powershell"
    assert index["consumer_ready_gate_command_text"] == (
        "& python run_guarded_launch.py --status-only --env-file operator.env "
        "--require-ready --status-json-out ready-gate.json"
    )
    assert index["consumer_ready_gate_command_missing_flags"] == []
    assert index["consumer_operator_command_count"] == 2
    assert index["consumer_operator_command_text_count"] == 2
    assert index["consumer_operator_commands"][0]["id"] == "inspect_status"
    assert index["consumer_operator_commands"][0]["command_text"] == (
        "& python run_guarded_launch.py --status-only --env-file operator.env"
    )
    assert index["consumer_handoff_validation_command_shell"] == "powershell"
    assert index["consumer_handoff_validation_command_text"] == "& python validate_guarded_launch_handoff.py handoff.json"
    assert artifacts_by_role["handoff_validation_json"]["generated_at"] == "2026-07-06T12:55:00Z"
    assert artifacts_by_role["handoff_consumer_json"]["generated_at"] == "2026-07-06T12:55:01Z"
    assert artifacts_by_role["handoff_markdown"]["generated_at"] is None
    assert index["consumer_readiness_operator_packet_preflight_status"] == "env_shape_blocked"
    assert index["consumer_readiness_operator_packet_consumer_command_metadata_status"] == "pass"
    assert index["missing_required_roles"] == []
    assert index["missing_generated_at_roles"] == []
    assert index["stale_generated_at_roles"] == []
    assert index["stale_generated_at_details"] == []
    assert index["recovery_action"] is None
    assert index["recovery_command"] is None
    assert index["recovery_command_shell"] is None
    assert index["recovery_command_text"] is None
    assert index["recovery_command_status"] == "not_required"
    assert index["recovery_command_note"] is None
    assert index["recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "blocker_class": "ready",
        "note": None,
        "command": None,
    }
    assert "Blocker class: `ready`" in markdown
    assert f"Generated: `{index['generated_at']}`" in markdown
    assert "Launch stage: `preflight`" in markdown
    assert "Launch browser smoke launch gate enforced: `-`" in markdown
    assert "Consumer readiness next action count: `2`" in markdown
    assert "Consumer readiness next command count: `1`" in markdown
    assert "Validation blocker class: `ready`" in markdown
    assert "Consumer packet evidence outputs blocker class: `ready`" in markdown
    assert "Consumer packet Markdown table blocker class: `ready`" in markdown
    assert "Consumer command metadata: `pass`" in markdown
    assert "Consumer ready gate command missing flags: `-`" in markdown
    assert "Consumer readiness command metadata: `pass`" in markdown
    assert "Consumer ready gate command shell: `powershell`" in markdown
    assert "Consumer operator command text count: `2`" in markdown
    assert "Consumer handoff validation command: `& python validate_guarded_launch_handoff.py handoff.json`" in markdown
    assert "## Consumer Operator Commands" in markdown
    assert "## Consumer Readiness Next Actions" in markdown
    assert "- Replace env template placeholders and sample domains." in markdown
    assert "`inspect_status` (powershell): `& python run_guarded_launch.py --status-only --env-file operator.env`" in markdown
    assert "`validate_env_template` (powershell): `& python validate_launch_env_template.py`" in markdown
    assert "| Role | Required | Exists | Size | Generated | SHA-256 | Path |" in markdown
    assert "`2026-07-06T12:55:00Z`" in markdown
    assert "Missing generated_at roles: `-`" in markdown
    assert "Stale generated_at roles: `-`" in markdown


def test_index_guarded_launch_artifacts_prefers_status_view_command_metadata(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    consumer["consumer_readiness_operator_packet_consumer_command_metadata_status"] = "pass"
    consumer["readiness_operator_packet_consumer_command_metadata_status"] = "fail"
    _write_json(paths["handoff_consumer_json"], consumer)

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["consumer_readiness_operator_packet_consumer_command_metadata_status"] == "pass"


def test_index_guarded_launch_artifacts_renders_browser_smoke_found_false(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    launch = json.loads(paths["launch_report_json"].read_text(encoding="utf-8"))
    launch["child_reports"] = {
        "browser_smoke": {
            "found": False,
            "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
        }
    }
    paths["launch_report_json"].write_text(json.dumps(launch), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["launch_browser_smoke"]["found"] is False
    assert "Launch browser smoke found: `false`" in markdown
    assert "Launch browser smoke path: `var/agriguard-browser-smoke-suite-compose-launch.json`" in markdown


def test_index_guarded_launch_artifacts_mirrors_browser_smoke_precheck_failure(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    launch = json.loads(paths["launch_report_json"].read_text(encoding="utf-8"))
    launch["stage"] = "browser_smoke"
    launch["child_reports"] = {
        "browser_smoke": {
            "found": True,
            "status": "fail",
            "evidence_class": "launch_precheck_blocked",
            "launch_gate": {
                "launch_gate_enforced": True,
                "operator_action": "resolve failed prechecks before running launch browser smoke",
            },
            "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
            "base_url": "http://127.0.0.1:5174",
            "api_url": "http://127.0.0.1:8002",
            "mobile": False,
            "include_unavailable_check": True,
            "summary": {
                "steps_total": 0,
                "steps_passed": 0,
                "steps_failed": 0,
                "checks_total": 0,
                "checks_passed": 0,
                "checks_failed": 0,
                "prechecks_total": 3,
                "prechecks_passed": 2,
                "prechecks_failed": 1,
                "failed_precheck_names": ["public_verify_cache_headers"],
                "failed_targets": ["backend", "frontend_proxy"],
            },
        }
    }
    paths["launch_report_json"].write_text(json.dumps(launch), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["launch_stage"] == "browser_smoke"
    assert index["launch_browser_smoke"] == {
        "found": True,
        "status": "fail",
        "evidence_class": "launch_precheck_blocked",
        "launch_gate_enforced": True,
        "operator_action": "resolve failed prechecks before running launch browser smoke",
        "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
        "base_url": "http://127.0.0.1:5174",
        "api_url": "http://127.0.0.1:8002",
        "mobile": False,
        "include_unavailable_check": True,
        "steps_total": 0,
        "steps_passed": 0,
        "steps_failed": 0,
        "checks_total": 0,
        "checks_passed": 0,
        "checks_failed": 0,
        "prechecks_total": 3,
        "prechecks_passed": 2,
        "prechecks_failed": 1,
        "screenshot_artifacts_total": None,
        "screenshot_artifacts_passed": None,
        "screenshot_artifacts_failed": None,
        "failed_step_names": [],
        "failed_check_names": [],
        "failed_precheck_names": ["public_verify_cache_headers"],
        "failed_targets": ["backend", "frontend_proxy"],
    }
    assert "Launch browser smoke status: `fail`" in markdown
    assert "Launch stage: `browser_smoke`" in markdown
    assert "Launch browser smoke found: `true`" in markdown
    assert "Launch browser smoke evidence class: `launch_precheck_blocked`" in markdown
    assert "Launch browser smoke launch gate enforced: `true`" in markdown
    assert "Launch browser smoke prechecks: `2/3`" in markdown
    assert "Launch browser smoke failed prechecks: `public_verify_cache_headers`" in markdown
    assert "Launch browser smoke failed targets: `backend, frontend_proxy`" in markdown
    assert (
        "Launch browser smoke operator action: "
        "`resolve failed prechecks before running launch browser smoke`"
    ) in markdown


def test_index_guarded_launch_artifacts_accepts_custom_handoff_paths(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    custom_dir = tmp_path / "custom-handoff"
    custom_paths = {
        "handoff_json": custom_dir / "current.handoff.json",
        "handoff_markdown": custom_dir / "current.handoff.md",
        "handoff_validation_json": custom_dir / "current.handoff.validation.json",
        "handoff_consumer_json": custom_dir / "current.handoff.consumer.json",
        "ready_gate_json": custom_dir / "current.ready-gate.json",
    }
    paths = index_guarded_launch_artifacts._artifact_paths(
        output_dir.resolve(),
        "blocked",
        None,
        **custom_paths,
    )
    _write_json(
        paths["launch_report_json"],
        {
            "generated_at": "2026-07-06T12:56:00Z",
            "status": "fail",
            "stage": "preflight",
            "results": [{"name": "preflight"}],
        },
    )
    _write_json(paths["handoff_json"], {"generated_at": "2026-07-06T12:56:01Z", "status": "blocked"})
    paths["handoff_markdown"].parent.mkdir(parents=True, exist_ok=True)
    paths["handoff_markdown"].write_text("# Custom handoff\n", encoding="utf-8")
    _write_json(
        paths["handoff_validation_json"],
        {"generated_at": "2026-07-06T12:56:02Z", "status": "pass", "errors": []},
    )
    _write_json(
        paths["handoff_consumer_json"],
        {
            "generated_at": "2026-07-06T12:56:03Z",
            "status": "fail",
            "blocker_class": "preflight_blocked",
            "validation_matches_handoff": True,
            "validation_status": "pass",
            "packet_validation_status": "pass",
            "packet_evidence_outputs_status": "pass",
            "packet_markdown_table_status": "pass",
            "packet_path_mismatch_count": 0,
            "ready_gate_command_shell": "powershell",
            "ready_gate_command_text": (
                "& python run_guarded_launch.py --status-only --env-file operator.env "
                "--require-ready --status-json-out current.ready-gate.json"
            ),
            "operator_command_count": 1,
            "operator_command_text_count": 1,
            "operator_commands": [
                {
                    "id": "require_ready",
                    "command_shell": "powershell",
                    "command_text": (
                        "& python run_guarded_launch.py --status-only --env-file operator.env "
                        "--require-ready --status-json-out current.ready-gate.json"
                    ),
                }
            ],
            "handoff_validation_command_shell": "powershell",
            "handoff_validation_command_text": "& python validate_guarded_launch_handoff.py current.handoff.json",
            "readiness_operator_action_ids": ["fix_env_shape_validation"],
            "errors": [],
        },
    )

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        handoff_json=custom_paths["handoff_json"],
        handoff_markdown=custom_paths["handoff_markdown"],
        handoff_validation_json=custom_paths["handoff_validation_json"],
        handoff_consumer_json=custom_paths["handoff_consumer_json"],
        ready_gate_json=custom_paths["ready_gate_json"],
    )

    artifacts_by_role = {
        artifact["role"]: artifact
        for artifact in index["artifacts"]
        if isinstance(artifact, dict)
    }
    assert index["status"] == "pass"
    assert index["blocker_class"] == "ready"
    assert index["missing_required_roles"] == []
    assert artifacts_by_role["handoff_json"]["path"] == str(custom_paths["handoff_json"].resolve())
    assert artifacts_by_role["handoff_consumer_json"]["path"] == str(custom_paths["handoff_consumer_json"].resolve())


def test_index_guarded_launch_artifacts_fails_stale_consumer_command_metadata(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    for key in (
        "ready_gate_command_shell",
        "ready_gate_command_text",
        "operator_command_count",
        "operator_command_text_count",
        "operator_commands",
        "handoff_validation_command_shell",
        "handoff_validation_command_text",
    ):
        consumer.pop(key)
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["consumer_command_metadata_status"] == "fail"
    assert index["recovery_command_status"] == "pass"


def test_index_guarded_launch_artifacts_fails_ready_gate_command_without_env_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    stale_command = "& python run_guarded_launch.py --status-only --require-ready --status-json-out ready-gate.json"
    consumer["ready_gate_command_text"] = stale_command
    consumer["operator_commands"][1]["command_text"] = stale_command
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["consumer_command_metadata_status"] == "fail"
    assert index["consumer_ready_gate_command_missing_flags"] == ["--env-file"]
    assert "Consumer ready gate command missing flags: `--env-file`" in markdown
    assert index["recovery_command_status"] == "pass"


def test_index_guarded_launch_artifacts_fails_missing_json_generated_at(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    consumer.pop("generated_at")
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["missing_generated_at_roles"] == ["handoff_consumer_json"]
    assert index["recovery_command_status"] == "pass"
    assert "Missing generated_at roles: `handoff_consumer_json`" in markdown


def test_index_guarded_launch_artifacts_fails_stale_ready_gate_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    _write_json(
        paths["ready_gate_json"],
        {
            "generated_at": "2026-07-06T12:52:04Z",
            "status": "blocked",
            "blocker_class": "preflight_blocked",
        },
    )

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["stale_generated_at_roles"] == ["ready_gate_json"]
    assert index["stale_generated_at_details"] == [
        {
            "role": "ready_gate_json",
            "generated_at": "2026-07-06T12:52:04Z",
            "minimum_role": "handoff_consumer_json",
            "minimum_generated_at": "2026-07-06T12:55:01Z",
        }
    ]
    assert index["recovery_command_status"] == "pass"
    assert "Stale generated_at roles: `ready_gate_json`" in markdown


def test_index_guarded_launch_artifacts_fails_packet_validation_drift(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    consumer["packet_validation_status"] = "fail"
    consumer["packet_markdown_table_status"] = "fail"
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["consumer_packet_validation_status"] == "fail"
    assert index["consumer_packet_markdown_table_status"] == "fail"
    assert index["recovery_action"] == (
        "Run the guarded launch wrapper command to regenerate required artifact-index evidence."
    )
    assert index["recovery_command_status"] == "pass"
    assert index["recovery_command_note"] == (
        "Recovery command is present because this artifact index did not meet pass criteria."
    )
    assert index["recovery_summary"]["required"] is True
    assert index["recovery_summary"]["action"] == index["recovery_action"]
    assert index["recovery_summary"]["status"] == "pass"
    assert index["recovery_summary"]["blocker_class"] == "ready"
    assert index["recovery_summary"]["note"] == index["recovery_command_note"]
    assert index["recovery_summary"]["command"] == index["recovery_command"]
    assert "--emit-handoff" in index["recovery_command"]


def test_index_guarded_launch_artifacts_markdown_exposes_consumer_errors(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    consumer["errors"] = ["blocked handoff has ready_gate status 'pass'"]
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )
    markdown = index_guarded_launch_artifacts.render_markdown(index)

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["consumer_errors"] == ["blocked handoff has ready_gate status 'pass'"]
    assert "Consumer errors: `blocked handoff has ready_gate status 'pass'`" in markdown
    assert "Recovery command status: `pass`" in markdown


def test_index_guarded_launch_artifacts_fails_missing_consumer(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    paths["handoff_consumer_json"].unlink()

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "fail"
    assert index["blocker_class"] == "artifact_index_blocked"
    assert index["missing_required_roles"] == ["handoff_consumer_json"]
    assert index["recovery_command_status"] == "pass"
    assert index["recovery_command_note"] == (
        "Recovery command is present because this artifact index did not meet pass criteria."
    )
    recovery_command = index["recovery_command"]
    markdown = index_guarded_launch_artifacts.render_markdown(index)
    assert recovery_command[:2] == [
        sys.executable,
        str(APP_ROOT / "scripts" / "run_guarded_launch.py"),
    ]
    assert "--dry-run" not in recovery_command
    assert "--emit-handoff" in recovery_command
    assert recovery_command[recovery_command.index("--output-prefix") + 1] == "blocked"
    assert recovery_command[recovery_command.index("--output-dir") + 1] == str(output_dir.resolve())
    expected_recovery_command_text = index_guarded_launch_artifacts._format_powershell_command(recovery_command)
    assert index["recovery_command_shell"] == "powershell"
    assert index["recovery_command_text"] == expected_recovery_command_text
    assert expected_recovery_command_text is not None
    assert expected_recovery_command_text.startswith("& ")
    assert f"'{output_dir.resolve()}'" in expected_recovery_command_text
    assert f"Recovery command: `{expected_recovery_command_text}`" in markdown
    assert "Recovery command shell: `powershell`" in markdown
    assert "Recovery command note: `Recovery command is present" in markdown
    assert "run_guarded_launch.py" in markdown


def test_index_guarded_launch_artifacts_recovery_command_preserves_env_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    env_file = tmp_path / "operator.env"
    paths = _write_core_artifacts(output_dir, "blocked")
    paths["handoff_consumer_json"].unlink()

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        env_file=env_file,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    recovery_command = index["recovery_command"]
    assert recovery_command[recovery_command.index("--env-file") + 1] == str(env_file.resolve())
    assert recovery_command[recovery_command.index("--output-prefix") + 1] == "blocked"
    assert recovery_command[recovery_command.index("--output-dir") + 1] == str(output_dir.resolve())


def test_index_guarded_launch_artifacts_can_require_status_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    status_json = tmp_path / "status.json"
    _write_core_artifacts(output_dir, "blocked")

    missing_index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        status_json=status_json,
    )
    _write_json(status_json, {"generated_at": "2026-07-06T12:57:00Z", "status": "blocked"})
    present_index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        status_json=status_json,
    )

    assert missing_index["status"] == "fail"
    assert missing_index["blocker_class"] == "artifact_index_blocked"
    assert "status_json" in missing_index["missing_required_roles"]
    assert present_index["status"] == "pass"
    assert present_index["blocker_class"] == "ready"


def test_index_guarded_launch_artifacts_main_writes_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    json_out = tmp_path / "index.json"
    markdown_out = tmp_path / "index.md"
    _write_core_artifacts(output_dir, "blocked")

    result = index_guarded_launch_artifacts.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["status"] == "pass"
    assert payload["blocker_class"] == "ready"
    assert "Consumer packet validation: `pass`" in markdown
    assert "Consumer readiness action IDs: `fix_env_shape_validation`" in markdown
    assert "Consumer errors: `-`" in markdown
    assert "Recovery summary required: `false`" in markdown
    assert "Recovery command status: `not_required`" in markdown
    assert "Recovery command note: `-`" in markdown
    assert "Recovery command shell: `-`" in markdown
    assert "Recovery command: `-`" in markdown
    assert "`handoff_consumer_json`" in markdown
