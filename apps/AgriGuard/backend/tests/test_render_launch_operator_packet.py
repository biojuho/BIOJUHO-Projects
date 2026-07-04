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


def test_operator_packet_handles_missing_preflight_json(tmp_path: Path) -> None:
    packet = render_launch_operator_packet.build_operator_packet(
        preflight_json=tmp_path / "missing.json",
        app_root=Path(__file__).resolve().parents[2],
    )

    assert packet["status"] == "blocked"
    assert packet["preflight_status"] == "missing_preflight"
    assert packet["operator_actions"][0]["id"] == "run_launch_preflight"


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
    assert "launch_env_preflight.py --check-docker" in markdown
    assert "launch_compose.py --run-browser-smoke" in markdown


def test_operator_packet_main_writes_outputs_and_exits_nonzero_when_blocked(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    json_out = tmp_path / "packet.json"
    markdown_out = tmp_path / "packet.md"
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
        ]
    )

    assert result == 1
    assert json.loads(json_out.read_text(encoding="utf-8"))["blocking_action_count"] == 1
    assert "`set_secret_key`" in markdown_out.read_text(encoding="utf-8")
