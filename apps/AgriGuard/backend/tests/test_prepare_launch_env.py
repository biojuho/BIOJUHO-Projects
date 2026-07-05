from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "prepare_launch_env.py"
SPEC = importlib.util.spec_from_file_location("prepare_launch_env", SCRIPT_PATH)
assert SPEC is not None
prepare_launch_env = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prepare_launch_env)


def _outside_repo_secret_root(tmp_path: Path) -> Path:
    firebase_root = Path(tempfile.gettempdir()) / "agriguard-pytest-secrets" / tmp_path.name
    repo_root = prepare_launch_env.launch_env_preflight._find_repository_root(APP_ROOT)  # noqa: SLF001
    if repo_root and prepare_launch_env.launch_env_preflight._is_relative_to(firebase_root, repo_root):  # noqa: SLF001
        firebase_root = repo_root.parent / "agriguard-pytest-secrets" / tmp_path.name
    return firebase_root


def _firebase_credentials_json() -> str:
    begin = "-----BEGIN " + "PRIVATE KEY-----"
    end = "-----END " + "PRIVATE KEY-----"
    return "\n".join(
        [
            "{",
            '  "type": "service_account",',
            '  "project_id": "agriguard-test",',
            f'  "private_key": "{begin}\\nFAKE\\n{end}\\n",',
            '  "client_email": "firebase-adminsdk-test@agriguard-test.iam.gserviceaccount.com",',
            '  "token_uri": "https://oauth2.googleapis.com/token"',
            "}",
            "",
        ]
    )


def test_prepare_launch_env_generates_secrets_and_redacted_report(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    markdown_out = tmp_path / "prepared.md"
    firebase_file = _outside_repo_secret_root(tmp_path) / "firebase-service-account.json"
    firebase_file.parent.mkdir(parents=True, exist_ok=True)
    firebase_file.write_text(_firebase_credentials_json(), encoding="utf-8")

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
    assert result == 0, report
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
        "firebase_service_account_file_valid": True,
        "firebase_service_account_file_path": "<redacted>",
    }
    assert env["ALLOW_TEST_BYPASS"] == "false"
    assert env["ALLOW_DEV_AUTH_FALLBACK"] == "false"
    assert env["AGRIGUARD_DB_PASSWORD"] not in encoded_report
    assert env["AGRIGUARD_SECRET_KEY"] not in encoded_report
    assert env["AGRIGUARD_QR_TOKEN_PEPPER"] not in encoded_report
    assert report["guarded_output_prefix"] == prepare_launch_env.run_guarded_launch.DEFAULT_OUTPUT_PREFIX
    assert all(command.startswith("& ") for command in report["safe_next_commands"])
    assert "Ready for preflight: `true`" in markdown_out.read_text(encoding="utf-8")


def test_prepare_launch_env_safe_next_commands_can_target_guarded_bundle(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    output_dir = tmp_path / "launch-artifacts"
    status_json = tmp_path / "status" / "launch-ready-status.json"
    missing_firebase_file = _outside_repo_secret_root(tmp_path) / "missing-firebase-service-account.json"

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
            "--allow-missing-firebase-file",
            "--guarded-output-dir",
            str(output_dir),
            "--guarded-output-prefix",
            "launch-ready",
            "--guarded-status-json",
            str(status_json),
            "--json-out",
            str(json_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert result == 0, report
    assert report["guarded_output_dir"] == output_dir.resolve().relative_to(APP_ROOT.parents[1]).as_posix()
    assert report["guarded_output_prefix"] == "launch-ready"
    assert report["guarded_status_json"] == status_json.resolve().relative_to(APP_ROOT.parents[1]).as_posix()
    assert report["safe_next_commands"][0] == prepare_launch_env._format_powershell_command(
        [
            prepare_launch_env.sys.executable,
            str(APP_ROOT / "scripts" / "validate_launch_env_template.py"),
            "--app-root",
            str(APP_ROOT),
            "--env-file",
            str(env_file.resolve()),
            "--json-out",
            str(output_dir.resolve() / "launch-ready-env-validation.json"),
            "--markdown-out",
            str(output_dir.resolve() / "launch-ready-env-validation.md"),
        ]
    )
    assert report["safe_next_commands"][1] == prepare_launch_env._format_powershell_command(
        [
            prepare_launch_env.sys.executable,
            str(APP_ROOT / "scripts" / "run_guarded_launch.py"),
            "--app-root",
            str(APP_ROOT),
            "--env-file",
            str(env_file.resolve()),
            "--output-dir",
            str(output_dir.resolve()),
            "--output-prefix",
            "launch-ready",
            "--emit-handoff",
            "--status-json-out",
            str(status_json.resolve()),
        ]
    )


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
        "firebase_service_account_file_valid": False,
        "firebase_service_account_file_path": "<redacted>",
    }
    assert (
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."
        in report["validation"]["blocking_findings"]
    )


def test_prepare_launch_env_can_allow_missing_firebase_file_for_planning(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    missing_firebase_file = _outside_repo_secret_root(tmp_path) / "missing-firebase-service-account.json"

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
    assert report["local_file_checks"]["firebase_service_account_file_valid"] is False


def test_prepare_launch_env_fails_closed_on_invalid_firebase_file_shape(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / "operator.env"
    json_out = tmp_path / "prepared.json"
    firebase_file = tmp_path / "firebase-service-account.json"
    firebase_file.write_text("{}", encoding="utf-8")

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
            str(firebase_file),
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
        "firebase_service_account_file_exists": True,
        "firebase_service_account_file_valid": False,
        "firebase_service_account_file_path": "<redacted>",
    }
    assert (
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE is missing required service account fields: "
        "type, project_id, private_key, client_email, token_uri."
    ) in report["validation"]["blocking_findings"]
