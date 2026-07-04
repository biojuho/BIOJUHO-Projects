from __future__ import annotations

import importlib.util
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]

VALIDATOR_PATH = APP_ROOT / "scripts" / "validate_launch_env_template.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_launch_env_template", VALIDATOR_PATH)
assert VALIDATOR_SPEC is not None
validate_launch_env_template = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validate_launch_env_template)

PACKET_PATH = APP_ROOT / "scripts" / "render_launch_operator_packet.py"
PACKET_SPEC = importlib.util.spec_from_file_location("render_launch_operator_packet", PACKET_PATH)
assert PACKET_SPEC is not None
render_launch_operator_packet = importlib.util.module_from_spec(PACKET_SPEC)
assert PACKET_SPEC.loader is not None
PACKET_SPEC.loader.exec_module(render_launch_operator_packet)


def _write_shape_safe_env(path: Path) -> dict[str, str]:
    values = {
        "AGRIGUARD_DB_USER": "agriguard",
        "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        "AGRIGUARD_DB_NAME": "agriguard",
        "AGRIGUARD_AUTO_CREATE_SCHEMA": "false",
        "AGRIGUARD_ALLOWED_ORIGINS": "https://app.agriguard.example.org",
        "AGRIGUARD_SECRET_KEY": "s" * 32,
        "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
        "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example.org",
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "C:/secure/firebase-service-account.json",
        "ALLOW_TEST_BYPASS": "false",
        "ALLOW_DEV_AUTH_FALLBACK": "false",
    }
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return values


def test_validate_launch_env_template_rejects_generated_placeholder_template(tmp_path: Path) -> None:
    packet = {
        "status": "blocked",
        "operator_actions": [{"id": "set_secret_key"}],
    }
    env_file = tmp_path / "launch.env.template"
    env_file.write_text(render_launch_operator_packet.render_env_template(packet), encoding="utf-8")

    report = validate_launch_env_template.build_validation_report(env_file=env_file, app_root=APP_ROOT)

    placeholder_keys = {item["key"] for item in report["placeholder_variables"]}
    assert report["status"] == "fail"
    assert report["ready_for_preflight"] is False
    assert report["placeholder_count"] == 6
    assert {
        "AGRIGUARD_DB_PASSWORD",
        "AGRIGUARD_ALLOWED_ORIGINS",
        "AGRIGUARD_SECRET_KEY",
        "AGRIGUARD_QR_TOKEN_PEPPER",
        "AGRIGUARD_PUBLIC_VERIFY_BASE_URL",
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
    }.issubset(placeholder_keys)
    assert report["secrets_redacted"] is True


def test_validate_launch_env_template_accepts_shape_safe_env(tmp_path: Path) -> None:
    env_file = tmp_path / "launch.env"
    _write_shape_safe_env(env_file)

    report = validate_launch_env_template.build_validation_report(env_file=env_file, app_root=APP_ROOT)

    assert report["status"] == "pass"
    assert report["ready_for_preflight"] is True
    assert report["placeholder_count"] == 0
    assert report["missing_required_keys"] == []
    assert report["forbidden_flags_enabled"] == []
    assert report["launch_validation"]["status"] == "pass"


def test_validate_launch_env_template_rejects_forbidden_launch_flags(tmp_path: Path) -> None:
    env_file = tmp_path / "launch.env"
    _write_shape_safe_env(env_file)
    with env_file.open("a", encoding="utf-8") as handle:
        handle.write("ALLOW_TEST_BYPASS=true\n")

    report = validate_launch_env_template.build_validation_report(env_file=env_file, app_root=APP_ROOT)

    assert report["status"] == "fail"
    assert report["ready_for_preflight"] is False
    assert report["forbidden_flags_enabled"] == ["ALLOW_TEST_BYPASS"]
    assert "ALLOW_TEST_BYPASS must be false for launch." in report["blocking_findings"]


def test_validate_launch_env_template_redacts_sensitive_values(tmp_path: Path) -> None:
    env_file = tmp_path / "launch.env"
    values = _write_shape_safe_env(env_file)

    report = validate_launch_env_template.build_validation_report(env_file=env_file, app_root=APP_ROOT)
    encoded = json.dumps(report)

    assert values["AGRIGUARD_SECRET_KEY"] not in encoded
    assert values["AGRIGUARD_QR_TOKEN_PEPPER"] not in encoded
    assert values["AGRIGUARD_DB_PASSWORD"] not in encoded
    assert values["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE"] not in encoded
    assert all(item["value"] == "<redacted>" for item in report["variables"])
    assert next(
        item for item in report["variables"] if item["key"] == "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE"
    )["sensitive"] is True


def test_validate_launch_env_template_main_writes_json_and_markdown(tmp_path: Path) -> None:
    env_file = tmp_path / "launch.env"
    json_out = tmp_path / "validation.json"
    markdown_out = tmp_path / "validation.md"
    _write_shape_safe_env(env_file)

    result = validate_launch_env_template.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--env-file",
            str(env_file),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert result == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["ready_for_preflight"] is True
    markdown = markdown_out.read_text(encoding="utf-8")
    assert "Ready for preflight: `true`" in markdown
    assert "ssssssssssssssssssssssssssssssss" not in markdown
    assert "dbpassword1234567890" not in markdown
