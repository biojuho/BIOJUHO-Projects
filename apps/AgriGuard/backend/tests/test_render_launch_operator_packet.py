from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "render_launch_operator_packet.py"
SPEC = importlib.util.spec_from_file_location("render_launch_operator_packet", SCRIPT_PATH)
assert SPEC is not None
render_launch_operator_packet = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(render_launch_operator_packet)


def test_operator_packet_maps_preflight_errors_to_redacted_actions(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "status": "fail",
                "errors": [
                    "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to a Firebase service account JSON before compose launch.",
                    "AGRIGUARD_SECRET_KEY uses a placeholder or development-only value.",
                    "AGRIGUARD_QR_TOKEN_PEPPER uses a placeholder or development-only value.",
                    "AGRIGUARD_PUBLIC_VERIFY_BASE_URL must use an https:// URL for launch.",
                    "AGRIGUARD_DB_PASSWORD uses a placeholder or development-only database password.",
                    "ALLOW_TEST_BYPASS must not be enabled for launch.",
                ],
                "warnings": [],
                "checks": {
                    "runtime": "compose",
                    "docker_checked": True,
                    "firebase_credentials_source": None,
                    "forbidden_launch_flags_enabled": ["ALLOW_TEST_BYPASS"],
                },
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=preflight,
        app_root=Path(__file__).resolve().parents[2],
    )

    action_ids = {action["id"] for action in packet["operator_actions"]}
    assert packet["status"] == "blocked"
    assert packet["secrets_redacted"] is True
    assert action_ids == {
        "set_firebase_service_account_file",
        "set_secret_key",
        "set_qr_token_pepper",
        "set_public_verify_base_url",
        "set_database_password",
        "disable_forbidden_auth_flags",
    }
    assert "password123" not in json.dumps(packet)
    assert packet["preflight_checks"]["runtime"] == "compose"
    assert packet["safe_rerun_commands"][0].startswith(
        "python apps/AgriGuard/scripts/validate_launch_env_template.py"
    )
    assert packet["safe_rerun_commands"][1] == (
        "python apps/AgriGuard/scripts/run_guarded_launch.py "
        "--env-file var/agriguard-launch-operator.env.template "
        "--emit-handoff "
        "--status-json-out var/agriguard-guarded-launch-status.json"
    )
    assert packet["operator_env_template"]["validation_command"] == packet["safe_rerun_commands"][0]
    assert packet["guarded_launch_evidence"]["wrapper_command"] == packet["safe_rerun_commands"][1]
    assert packet["guarded_launch_evidence"]["outputs"]["artifact_index_json"] == (
        "var/agriguard-guarded-launch-artifact-index.json"
    )
    assert packet["guarded_launch_evidence"]["outputs"]["handoff_markdown"] == (
        "var/agriguard-guarded-launch-handoff.md"
    )
    required_from_artifact_index = {
        render_launch_operator_packet.index_guarded_launch_artifacts.STATUS_ARTIFACT_ROLE,
        *render_launch_operator_packet.index_guarded_launch_artifacts.REQUIRED_CORE_ARTIFACT_ROLES,
        "artifact_index_json",
    }
    assert set(packet["guarded_launch_evidence"]["validation"]["required_output_keys"]) == required_from_artifact_index
    assert packet["guarded_launch_evidence"]["validation"] == {
        "status": "pass",
        "required_output_keys": list(render_launch_operator_packet.REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS),
        "missing_output_keys": [],
        "empty_output_keys": [],
    }


def test_operator_packet_preserves_env_file_in_safe_rerun_commands(tmp_path: Path) -> None:
    app_root = tmp_path / "apps" / "AgriGuard"
    env_file = tmp_path / "var" / "operator.env"
    preflight = tmp_path / "var" / "preflight.json"
    preflight.parent.mkdir(parents=True)
    preflight.write_text(
        json.dumps(
            {
                "status": "fail",
                "errors": [
                    "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to a Firebase service account JSON before compose launch.",
                ],
                "warnings": [],
                "checks": {"runtime": "compose", "docker_checked": True},
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=preflight,
        env_files=[env_file],
        app_root=app_root,
    )

    assert packet["operator_env_files"] == ["var/operator.env"]
    assert packet["safe_rerun_commands"][0] == (
        "python apps/AgriGuard/scripts/validate_launch_env_template.py "
        "--env-file var/operator.env "
        "--json-out var/agriguard-launch-env-template-validation.json "
        "--markdown-out var/agriguard-launch-env-template-validation.md"
    )
    assert packet["safe_rerun_commands"][1] == (
        "python apps/AgriGuard/scripts/run_guarded_launch.py "
        "--env-file var/operator.env "
        "--emit-handoff "
        "--status-json-out var/agriguard-guarded-launch-status.json"
    )
    assert packet["safe_rerun_commands"][2] == (
        "python apps/AgriGuard/scripts/launch_env_preflight.py "
        "--check-docker "
        "--json-out var/agriguard-launch-env-preflight-compose-launch.json "
        "--env-file var/operator.env"
    )
    assert packet["safe_rerun_commands"][3] == (
        "python apps/AgriGuard/scripts/launch_compose.py "
        "--env-file var/operator.env "
        "--run-browser-smoke "
        "--launch-report-json var/agriguard-compose-launch-report.json"
    )
    assert packet["guarded_launch_evidence"]["wrapper_command"] == packet["safe_rerun_commands"][1]


def test_operator_packet_can_target_custom_guarded_evidence_outputs(tmp_path: Path) -> None:
    app_root = tmp_path / "apps" / "AgriGuard"
    env_file = tmp_path / "var" / "operator.env"
    preflight = tmp_path / "var" / "preflight.json"
    output_dir = tmp_path / "launch-artifacts"
    status_json = tmp_path / "custom-status" / "guarded-status.json"
    artifact_index = output_dir / "custom-prefix-artifact-index.json"
    custom_handoff_dir = tmp_path / "custom-handoff"
    handoff_json = custom_handoff_dir / "current.handoff.json"
    handoff_markdown = custom_handoff_dir / "current.handoff.md"
    handoff_validation_json = custom_handoff_dir / "current.handoff.validation.json"
    handoff_consumer_json = custom_handoff_dir / "current.handoff.consumer.json"
    ready_gate_json = custom_handoff_dir / "current.ready-gate.json"
    preflight.parent.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    preflight.write_text(
        json.dumps(
            {
                "status": "fail",
                "errors": ["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."],
                "warnings": [],
                "checks": {"runtime": "compose", "docker_checked": True},
            }
        ),
        encoding="utf-8",
    )
    artifact_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "consumer_packet_validation_status": "pass",
                "recovery_command_status": "not_required",
                "recovery_summary": {
                    "required": False,
                    "action": None,
                    "status": "not_required",
                    "note": None,
                    "command": None,
                },
                "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                "consumer_readiness_env_validation_ready_for_preflight": True,
                "consumer_readiness_env_validation_placeholder_count": 0,
                "consumer_readiness_operator_packet_preflight_status": "fail",
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=preflight,
        env_files=[env_file],
        app_root=app_root,
        guarded_output_dir=output_dir,
        guarded_output_prefix="custom-prefix",
        guarded_status_json=status_json,
        guarded_handoff_json=handoff_json,
        guarded_handoff_markdown=handoff_markdown,
        guarded_handoff_validation_json=handoff_validation_json,
        guarded_handoff_consumer_json=handoff_consumer_json,
        guarded_ready_gate_json=ready_gate_json,
    )
    evidence = packet["guarded_launch_evidence"]
    summary = evidence["artifact_index_readiness_summary"]

    assert packet["safe_rerun_commands"][1] == (
        "python apps/AgriGuard/scripts/run_guarded_launch.py "
        "--env-file var/operator.env "
        "--output-dir launch-artifacts "
        "--output-prefix custom-prefix "
        "--emit-handoff "
        "--status-json-out custom-status/guarded-status.json "
        "--handoff-json-out custom-handoff/current.handoff.json "
        "--handoff-markdown-out custom-handoff/current.handoff.md "
        "--handoff-validation-json-out custom-handoff/current.handoff.validation.json "
        "--handoff-consumer-json-out custom-handoff/current.handoff.consumer.json "
        "--handoff-ready-gate-json-out custom-handoff/current.ready-gate.json"
    )
    assert evidence["outputs"]["status_json"] == "custom-status/guarded-status.json"
    assert evidence["outputs"]["launch_report_json"] == "launch-artifacts/custom-prefix-launch-report.json"
    assert evidence["outputs"]["handoff_json"] == "custom-handoff/current.handoff.json"
    assert evidence["outputs"]["handoff_markdown"] == "custom-handoff/current.handoff.md"
    assert evidence["outputs"]["handoff_validation_json"] == "custom-handoff/current.handoff.validation.json"
    assert evidence["outputs"]["handoff_consumer_json"] == "custom-handoff/current.handoff.consumer.json"
    assert evidence["outputs"]["artifact_index_json"] == "launch-artifacts/custom-prefix-artifact-index.json"
    assert summary["path"] == "launch-artifacts/custom-prefix-artifact-index.json"
    assert summary["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert summary["env_validation_ready_for_preflight"] is True
    assert summary["env_validation_placeholder_count"] == 0


def test_operator_packet_handles_missing_preflight_json(tmp_path: Path) -> None:
    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing.json",
        app_root=Path(__file__).resolve().parents[2],
    )

    assert packet["status"] == "blocked"
    assert packet["preflight_status"] == "missing_preflight"
    assert packet["operator_actions"][0]["id"] == "run_launch_preflight"


def test_operator_packet_maps_env_validation_failure_when_preflight_missing(tmp_path: Path) -> None:
    env_validation = tmp_path / "env-validation.json"
    env_validation.write_text(
        json.dumps(
            {
                "status": "fail",
                "ready_for_preflight": False,
                "missing_required_keys": ["AGRIGUARD_SECRET_KEY"],
                "placeholder_variables": [{"key": "AGRIGUARD_PUBLIC_VERIFY_BASE_URL", "reason": "sample_domain"}],
                "forbidden_flags_enabled": ["ALLOW_TEST_BYPASS"],
                "blocking_findings": [
                    "Missing required launch env key: AGRIGUARD_SECRET_KEY",
                    "Replace sample domain value for AGRIGUARD_PUBLIC_VERIFY_BASE_URL before launch preflight.",
                    "ALLOW_TEST_BYPASS must be false for launch.",
                ],
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing-preflight.json",
        env_validation_json=env_validation,
        app_root=Path(__file__).resolve().parents[2],
    )

    assert packet["status"] == "blocked"
    assert packet["preflight_status"] == "env_shape_blocked"
    assert packet["env_validation_status"] == "fail"
    assert packet["operator_actions"] == [
        {
            "id": "fix_env_shape_validation",
            "variables": [
                "AGRIGUARD_PUBLIC_VERIFY_BASE_URL",
                "AGRIGUARD_SECRET_KEY",
                "ALLOW_TEST_BYPASS",
            ],
            "operator_action": "Fix the launch env template findings before strict preflight can run.",
            "validation": "Env template validation must report ready_for_preflight=true.",
            "source_errors": [
                "Missing required launch env key: AGRIGUARD_SECRET_KEY",
                "Replace sample domain value for AGRIGUARD_PUBLIC_VERIFY_BASE_URL before launch preflight.",
                "ALLOW_TEST_BYPASS must be false for launch.",
            ],
        }
    ]


def test_operator_packet_markdown_contains_actions_and_safe_commands(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "status": "fail",
                "errors": ["SECRET_KEY=super-secret-value should be redacted."],
                "warnings": [],
                "checks": {},
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=preflight,
        app_root=Path(__file__).resolve().parents[2],
    )
    markdown = render_launch_operator_packet.render_markdown(packet)

    assert "# AgriGuard Launch Operator Packet" in markdown
    assert "SECRET_KEY=<redacted>" in markdown
    assert "super-secret-value" not in markdown
    assert "validate_launch_env_template.py --env-file var/agriguard-launch-operator.env.template" in markdown
    assert (
        "run_guarded_launch.py --env-file var/agriguard-launch-operator.env.template "
        "--emit-handoff --status-json-out var/agriguard-guarded-launch-status.json"
    ) in markdown
    assert "launch_env_preflight.py --check-docker" in markdown
    assert "launch_compose.py --run-browser-smoke" in markdown
    assert "## Guarded Launch Evidence Outputs" in markdown
    assert "`artifact_index_json` | `var/agriguard-guarded-launch-artifact-index.json`" in markdown
    assert "`handoff_markdown` | `var/agriguard-guarded-launch-handoff.md`" in markdown
    assert markdown.index("validate_launch_env_template.py") < markdown.index("run_guarded_launch.py")
    assert markdown.index("run_guarded_launch.py") < markdown.index("launch_env_preflight.py")


def test_operator_packet_markdown_evidence_table_matches_json_outputs(tmp_path: Path) -> None:
    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing.json",
        app_root=Path(__file__).resolve().parents[2],
    )
    markdown = render_launch_operator_packet.render_markdown(packet)

    validation = render_launch_operator_packet.validate_markdown_evidence_table(packet, markdown)

    assert validation == {
        "status": "pass",
        "expected_output_keys": list(packet["guarded_launch_evidence"]["outputs"]),
        "missing_rows": [],
        "extra_rows": [],
        "path_mismatches": [],
    }


def test_operator_packet_markdown_evidence_table_reports_path_drift(tmp_path: Path) -> None:
    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing.json",
        app_root=Path(__file__).resolve().parents[2],
    )
    markdown = render_launch_operator_packet.render_markdown(packet).replace(
        "var/agriguard-guarded-launch-artifact-index.json",
        "var/wrong-artifact-index.json",
    )

    validation = render_launch_operator_packet.validate_markdown_evidence_table(packet, markdown)

    assert validation["status"] == "fail"
    assert validation["missing_rows"] == []
    assert validation["extra_rows"] == []
    assert validation["path_mismatches"] == [
        {
            "key": "artifact_index_json",
            "expected": "var/agriguard-guarded-launch-artifact-index.json",
            "actual": "var/wrong-artifact-index.json",
        }
    ]


def test_operator_packet_mirrors_artifact_index_readiness_summary(tmp_path: Path) -> None:
    app_root = tmp_path / "apps" / "AgriGuard"
    artifact_index = tmp_path / "var" / "agriguard-guarded-launch-artifact-index.json"
    artifact_index.parent.mkdir(parents=True)
    artifact_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "consumer_packet_validation_status": "pass",
                "recovery_command_status": "not_required",
                "recovery_summary": {
                    "required": False,
                    "action": None,
                    "status": "not_required",
                    "note": None,
                    "command": None,
                },
                "consumer_readiness_operator_action_ids": ["fix_env_shape_validation"],
                "consumer_readiness_env_validation_ready_for_preflight": False,
                "consumer_readiness_env_validation_placeholder_count": 6,
                "consumer_readiness_operator_packet_preflight_status": "env_shape_blocked",
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing-preflight.json",
        app_root=app_root,
    )
    summary = packet["guarded_launch_evidence"]["artifact_index_readiness_summary"]
    markdown = render_launch_operator_packet.render_markdown(packet)

    assert summary == {
        "found": True,
        "path": "var/agriguard-guarded-launch-artifact-index.json",
        "status": "pass",
        "consumer_packet_validation_status": "pass",
        "recovery_command_status": "not_required",
        "recovery_command_note": None,
        "recovery_summary": {
            "required": False,
            "action": None,
            "status": "not_required",
            "note": None,
            "command": None,
        },
        "operator_action_ids": ["fix_env_shape_validation"],
        "env_validation_ready_for_preflight": False,
        "env_validation_placeholder_count": 6,
        "operator_packet_preflight_status": "env_shape_blocked",
        "missing_index_action": None,
        "missing_index_command": None,
    }
    assert "## Guarded Launch Readiness Summary" in markdown
    assert "Action IDs: `fix_env_shape_validation`" in markdown
    assert "Recovery command status: `not_required`" in markdown
    assert "Recovery summary required: `false`" in markdown
    assert "Packet preflight status: `env_shape_blocked`" in markdown


def test_operator_packet_reports_missing_artifact_index_hint(tmp_path: Path) -> None:
    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing-preflight.json",
        app_root=tmp_path / "apps" / "AgriGuard",
    )
    summary = packet["guarded_launch_evidence"]["artifact_index_readiness_summary"]
    markdown = render_launch_operator_packet.render_markdown(packet)

    assert summary["found"] is False
    assert summary["recovery_command_status"] is None
    assert summary["recovery_command_note"] == (
        "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
    )
    assert summary["recovery_summary"] == {
        "required": True,
        "action": "Run the guarded launch wrapper command to generate the artifact index evidence.",
        "status": None,
        "note": "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index.",
        "command": packet["guarded_launch_evidence"]["wrapper_command"],
    }
    assert summary["missing_index_action"] == (
        "Run the guarded launch wrapper command to generate the artifact index evidence."
    )
    assert summary["missing_index_command"] == packet["guarded_launch_evidence"]["wrapper_command"]
    assert "Recovery command note: `Artifact index recovery status is resolved" in markdown
    assert "Missing index action: `Run the guarded launch wrapper command" in markdown
    assert "Missing index command: `python apps/AgriGuard/scripts/run_guarded_launch.py" in markdown


def test_operator_packet_env_template_has_placeholders_and_safe_launch_flags(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "status": "fail",
                "errors": ["Set AGRIGUARD_SECRET_KEY before compose launch."],
                "warnings": [],
                "checks": {},
            }
        ),
        encoding="utf-8",
    )

    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=preflight,
        app_root=Path(__file__).resolve().parents[2],
    )
    template = render_launch_operator_packet.render_env_template(packet)

    assert "AGRIGUARD_SECRET_KEY=<set-strong-secret-32-plus-chars>" in template
    assert "AGRIGUARD_QR_TOKEN_PEPPER=<set-stable-qr-token-pepper-32-plus-chars>" in template
    assert "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>" in template
    assert "ALLOW_TEST_BYPASS=false" in template
    assert "ALLOW_DEV_AUTH_FALLBACK=false" in template
    assert "super-secret-value" not in template
    assert packet["operator_env_template"]["placeholder_values_must_be_replaced"] is True
    assert "validate_launch_env_template.py" in packet["operator_env_template"]["validation_command"]


def test_operator_packet_main_writes_outputs_and_exits_nonzero_when_blocked(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    json_out = tmp_path / "packet.json"
    markdown_out = tmp_path / "packet.md"
    env_template_out = tmp_path / "launch.env.template"
    preflight.write_text(json.dumps({"status": "fail", "errors": ["Set AGRIGUARD_SECRET_KEY before compose launch."]}), encoding="utf-8")

    result = render_launch_operator_packet.main(
        [
            "--app-root",
            str(Path(__file__).resolve().parents[2]),
            "--preflight-json",
            str(preflight),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--env-template-out",
            str(env_template_out),
        ]
    )

    assert result == 1
    packet = json.loads(json_out.read_text(encoding="utf-8"))
    assert packet["blocking_action_count"] == 1
    assert packet["guarded_launch_evidence"]["markdown_table_validation"]["status"] == "pass"
    assert packet["safe_rerun_commands"][0].startswith(
        "python apps/AgriGuard/scripts/validate_launch_env_template.py"
    )
    assert "run_guarded_launch.py" in packet["safe_rerun_commands"][1]
    assert "`set_secret_key`" in markdown_out.read_text(encoding="utf-8")
    assert "AGRIGUARD_SECRET_KEY=<set-strong-secret-32-plus-chars>" in env_template_out.read_text(encoding="utf-8")
