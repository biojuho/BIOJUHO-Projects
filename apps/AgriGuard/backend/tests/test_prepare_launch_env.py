from __future__ import annotations

import importlib.util
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "prepare_launch_env.py"
SPEC = importlib.util.spec_from_file_location("prepare_launch_env", SCRIPT_PATH)
assert SPEC is not None
prepare_launch_env = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prepare_launch_env)


def test_prepare_launch_env_generates_secrets_and_redacted_report(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    markdown_out = tmp_path / "prepared.md"
    firebase_file = tmp_path / "firebase-service-account.json"
    firebase_file.write_text("{}", encoding="utf-8")

    result = prepare_launch_env.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--out",
            str(env_file),
            "--allowed-origins",
            "https://app.agriguard.io,https://admin.agriguard.io",
            "--public-verify-base-url",
            "https://verify.agriguard.io",
            "--firebase-service-account-file",
            str(firebase_file),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    env = prepare_launch_env.launch_env_preflight.load_env_file(env_file)
    encoded_report = json.dumps(report)
    capsys.readouterr()
    assert result == 0
    assert report["status"] == "pass"
    assert report["ready_for_preflight"] is True
    assert report["secrets_redacted"] is True
    assert report["validation"]["placeholder_count"] == 0
    assert report["validation"]["blocking_findings"] == []
    assert set(report["generated_fields"]) == set(prepare_launch_env.GENERATED_FIELDS)
    assert len(env["AGRIGUARD_DB_PASSWORD"]) >= 16
    assert len(env["AGRIGUARD_SECRET_KEY"]) >= 32
    assert len(env["AGRIGUARD_QR_TOKEN_PEPPER"]) >= 32
    assert env["AGRIGUARD_ALLOWED_ORIGINS"] == "https://app.agriguard.io,https://admin.agriguard.io"
    assert env["AGRIGUARD_PUBLIC_VERIFY_BASE_URL"] == "https://verify.agriguard.io"
    assert env["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE"] == str(firebase_file)
    assert report["local_file_checks"] == {
        "allow_missing_firebase_file": False,
        "firebase_service_account_file_exists": True,
        "firebase_service_account_file_path": "<redacted>",
    }
    assert env["ALLOW_TEST_BYPASS"] == "false"
    assert env["ALLOW_DEV_AUTH_FALLBACK"] == "false"
    assert env["AGRIGUARD_DB_PASSWORD"] not in encoded_report
    assert env["AGRIGUARD_SECRET_KEY"] not in encoded_report
    assert env["AGRIGUARD_QR_TOKEN_PEPPER"] not in encoded_report
    assert "Ready for preflight: `true`" in markdown_out.read_text(encoding="utf-8")


def test_prepare_launch_env_refuses_overwrite_without_force(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    env_file.write_text("EXISTING=true\n", encoding="utf-8")

    result = prepare_launch_env.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--out",
            str(env_file),
            "--allowed-origins",
            "https://app.agriguard.io",
            "--public-verify-base-url",
            "https://verify.agriguard.io",
            "--firebase-service-account-file",
            "C:/secure/firebase-service-account.json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "already exists" in captured.err
    assert env_file.read_text(encoding="utf-8") == "EXISTING=true\n"


def test_prepare_launch_env_fails_closed_on_sample_domains(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"

    result = prepare_launch_env.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--out",
            str(env_file),
            "--allowed-origins",
            "https://app.example.com",
            "--public-verify-base-url",
            "https://verify.example.com",
            "--firebase-service-account-file",
            "C:/secure/firebase-service-account.json",
            "--json-out",
            str(json_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert result == 1
    assert report["status"] == "fail"
    assert report["ready_for_preflight"] is False
    assert report["validation"]["placeholder_count"] == 2
    assert (
        "Replace sample domain value for AGRIGUARD_ALLOWED_ORIGINS before launch preflight."
        in report["validation"]["blocking_findings"]
    )
    assert (
        "Replace sample domain value for AGRIGUARD_PUBLIC_VERIFY_BASE_URL before launch preflight."
        in report["validation"]["blocking_findings"]
    )


def test_prepare_launch_env_fails_closed_on_missing_firebase_file(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    missing_firebase_file = tmp_path / "missing-firebase-service-account.json"

    result = prepare_launch_env.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--out",
            str(env_file),
            "--allowed-origins",
            "https://app.agriguard.io",
            "--public-verify-base-url",
            "https://verify.agriguard.io",
            "--firebase-service-account-file",
            str(missing_firebase_file),
            "--json-out",
            str(json_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert result == 1
    assert report["status"] == "fail"
    assert report["ready_for_preflight"] is False
    assert report["local_file_checks"] == {
        "allow_missing_firebase_file": False,
        "firebase_service_account_file_exists": False,
        "firebase_service_account_file_path": "<redacted>",
    }
    assert (
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist on this host."
        in report["validation"]["blocking_findings"]
    )


def test_prepare_launch_env_can_allow_missing_firebase_file_for_planning(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"

    result = prepare_launch_env.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--out",
            str(env_file),
            "--allowed-origins",
            "https://app.agriguard.io",
            "--public-verify-base-url",
            "https://verify.agriguard.io",
            "--firebase-service-account-file",
            str(tmp_path / "missing-firebase-service-account.json"),
            "--allow-missing-firebase-file",
            "--json-out",
            str(json_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert result == 0
    assert report["status"] == "pass"
    assert report["ready_for_preflight"] is True
    assert report["local_file_checks"]["allow_missing_firebase_file"] is True
    assert report["local_file_checks"]["firebase_service_account_file_exists"] is False
