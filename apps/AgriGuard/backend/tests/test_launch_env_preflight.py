from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "launch_env_preflight.py"
SPEC = importlib.util.spec_from_file_location("launch_env_preflight", SCRIPT_PATH)
assert SPEC is not None
launch_env_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launch_env_preflight)


def _healthy_env() -> dict[str, str]:
    return {
        "AGRIGUARD_SECRET_KEY": "s" * 32,
        "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
        "AGRIGUARD_DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@postgres:5432/agriguard",
        "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
    }


def _runner_from_results(
    results: dict[tuple[str, ...], subprocess.CompletedProcess[str]],
):
    def runner(command, **kwargs):
        return results[tuple(command)]

    return runner


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


def _write_firebase_credentials_path(credentials_path: Path, *, encoding: str = "utf-8") -> Path:
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(_firebase_credentials_json(), encoding=encoding)
    return credentials_path


def _write_firebase_credentials_file(app_root: Path, *, encoding: str = "utf-8") -> Path:
    return _write_firebase_credentials_path(app_root / "firebase-service-account.json", encoding=encoding)


def _write_external_firebase_credentials_file(tmp_path: Path, *, encoding: str = "utf-8") -> Path:
    target_root = Path(tempfile.gettempdir()) / "agriguard-pytest-secrets" / tmp_path.name
    repo_root = launch_env_preflight._find_repository_root(tmp_path)  # noqa: SLF001
    if repo_root and launch_env_preflight._is_relative_to(target_root, repo_root):  # noqa: SLF001
        target_root = repo_root.parent / "agriguard-pytest-secrets" / tmp_path.name
    return _write_firebase_credentials_path(target_root / "firebase-service-account.json", encoding=encoding)


def _fake_repo_app_root(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "AgriGuard"
    app_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    return repo_root, app_root


def test_launch_env_preflight_default_env_files_include_backend_env_before_app_env() -> None:
    env_files = launch_env_preflight._default_env_files()

    assert [path.name for path in env_files] == [".env", ".env"]
    assert env_files[0].parent.name == "backend"
    assert env_files[1].parent.name == "AgriGuard"


def test_launch_env_preflight_fails_without_secret() -> None:
    report = launch_env_preflight.validate_launch_env({})

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_SECRET_KEY before compose launch." in report["errors"]


def test_launch_env_preflight_compose_rejects_generic_secret_by_default() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_SECRET_KEY for compose launch instead of relying on generic SECRET_KEY." in report["errors"]
    assert report["checks"]["secret_source"] is None


def test_launch_env_preflight_compose_can_allow_generic_secret_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_generic_secret_key=True,
    )

    assert report["status"] == "pass"
    assert report["checks"]["secret_source"] == "SECRET_KEY"
    assert report["checks"]["allow_generic_secret_key"] is True


def test_launch_env_preflight_direct_mode_requires_backend_secret_key() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Set SECRET_KEY for direct backend launch; AGRIGUARD_SECRET_KEY is only bridged by compose." in report["errors"]


def test_launch_env_preflight_rejects_placeholder_secret() -> None:
    report = launch_env_preflight.validate_launch_env({"AGRIGUARD_SECRET_KEY": "change_me"})

    assert report["status"] == "fail"
    assert "AGRIGUARD_SECRET_KEY uses a placeholder or development-only value." in report["errors"]


def test_launch_env_preflight_rejects_test_bypass_enabled() -> None:
    env = _healthy_env() | {"ALLOW_TEST_BYPASS": "true"}

    report = launch_env_preflight.validate_launch_env(env)

    assert report["status"] == "fail"
    assert "ALLOW_TEST_BYPASS must not be enabled for launch." in report["errors"]
    assert report["checks"]["forbidden_launch_flags_enabled"] == ["ALLOW_TEST_BYPASS"]


def test_launch_env_preflight_rejects_dev_auth_fallback_enabled() -> None:
    env = _healthy_env() | {"ALLOW_DEV_AUTH_FALLBACK": "yes"}

    report = launch_env_preflight.validate_launch_env(env)

    assert report["status"] == "fail"
    assert "ALLOW_DEV_AUTH_FALLBACK must not be enabled for launch." in report["errors"]
    assert report["checks"]["forbidden_launch_flags_enabled"] == ["ALLOW_DEV_AUTH_FALLBACK"]


def test_launch_env_preflight_rejects_dev_auth_fallback_role() -> None:
    env = _healthy_env() | {"DEV_AUTH_FALLBACK_ROLE": "operator"}

    report = launch_env_preflight.validate_launch_env(env)

    assert report["status"] == "fail"
    assert "DEV_AUTH_FALLBACK_ROLE must not be set for launch." in report["errors"]
    assert report["checks"]["dev_auth_fallback_role_set"] is True


def test_launch_env_preflight_requires_firebase_credentials() -> None:
    env = _healthy_env()
    env.pop("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE")

    report = launch_env_preflight.validate_launch_env(env)

    assert report["status"] == "fail"
    assert (
        "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to a Firebase service account JSON before compose launch."
        in report["errors"]
    )
    assert report["checks"]["firebase_credentials_source"] is None


def test_launch_env_preflight_compose_rejects_generic_firebase_credentials_by_default() -> None:
    env = _healthy_env()
    env.pop("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE")
    env["GOOGLE_APPLICATION_CREDENTIALS"] = "firebase-service-account.json"

    report = launch_env_preflight.validate_launch_env(env)

    assert report["status"] == "fail"
    assert (
        "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE for compose launch instead of relying on generic GOOGLE_APPLICATION_CREDENTIALS."
        in report["errors"]
    )
    assert report["checks"]["firebase_credentials_source"] is None


def test_launch_env_preflight_rejects_placeholder_firebase_credentials() -> None:
    report = launch_env_preflight.validate_launch_env(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "change_me"}
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE uses a placeholder or development-only value." in report["errors"]


def test_launch_env_preflight_can_allow_missing_firebase_credentials_for_local_checks() -> None:
    env = _healthy_env()
    env.pop("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE")

    report = launch_env_preflight.validate_launch_env_with_options(
        env,
        allow_missing_firebase_credentials=True,
    )

    assert report["status"] == "pass"
    assert (
        "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to a Firebase service account JSON before compose launch."
        in report["warnings"]
    )
    assert report["checks"]["allow_missing_firebase_credentials"] is True


def test_launch_env_preflight_rejects_missing_qr_token_pepper() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        }
    )

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_QR_TOKEN_PEPPER before compose launch." in report["errors"]


def test_launch_env_preflight_compose_rejects_generic_qr_token_pepper_by_default() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert (
        "Set AGRIGUARD_QR_TOKEN_PEPPER for compose launch instead of relying on generic QR_TOKEN_PEPPER."
        in report["errors"]
    )
    assert report["checks"]["qr_token_pepper_source"] is None


def test_launch_env_preflight_compose_can_allow_generic_qr_token_pepper_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_generic_qr_token_pepper=True,
    )

    assert report["status"] == "pass"
    assert report["checks"]["qr_token_pepper_source"] == "QR_TOKEN_PEPPER"
    assert report["checks"]["allow_generic_qr_token_pepper"] is True


def test_launch_env_preflight_direct_mode_requires_backend_qr_token_pepper() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert (
        "Set QR_TOKEN_PEPPER for direct backend launch; AGRIGUARD_QR_TOKEN_PEPPER is only bridged by compose."
        in report["errors"]
    )


def test_launch_env_preflight_rejects_placeholder_qr_token_pepper() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "change_me_qr_token_hash_pepper",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_QR_TOKEN_PEPPER uses a placeholder or development-only value." in report["errors"]


def test_launch_env_preflight_rejects_short_qr_token_pepper() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "too-short",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_QR_TOKEN_PEPPER must be at least 32 characters." in report["errors"]


def test_launch_env_preflight_requires_public_verify_base_url_by_default() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        }
    )

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_PUBLIC_VERIFY_BASE_URL before compose launch." in report["errors"]


def test_launch_env_preflight_compose_rejects_generic_public_verify_base_url_by_default() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert (
        "Set AGRIGUARD_PUBLIC_VERIFY_BASE_URL for compose launch instead of relying on generic PUBLIC_VERIFY_BASE_URL."
        in report["errors"]
    )
    assert report["checks"]["public_verify_base_url_source"] is None


def test_launch_env_preflight_compose_can_allow_generic_public_verify_base_url_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_generic_public_verify_base_url=True,
    )

    assert report["status"] == "pass"
    assert report["checks"]["public_verify_base_url_source"] == "PUBLIC_VERIFY_BASE_URL"
    assert report["checks"]["allow_generic_public_verify_base_url"] is True


def test_launch_env_preflight_direct_mode_requires_backend_public_verify_base_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert (
        "Set PUBLIC_VERIFY_BASE_URL for direct backend launch; AGRIGUARD_PUBLIC_VERIFY_BASE_URL is only bridged by compose."
        in report["errors"]
    )


def test_launch_env_preflight_rejects_insecure_public_verify_base_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "http://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_PUBLIC_VERIFY_BASE_URL must use an https:// URL for launch." in report["errors"]


def test_launch_env_preflight_rejects_public_verify_base_url_with_path() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example/app",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_PUBLIC_VERIFY_BASE_URL must be a base URL without a path." in report["errors"]


def test_launch_env_preflight_can_allow_local_public_verify_base_url_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://localhost:5173",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_local_public_verify_base_url=True,
    )

    assert report["status"] == "pass"
    assert report["checks"]["allow_local_public_verify_base_url"] is True


def test_launch_env_preflight_can_allow_legacy_qr_scheme_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_legacy_qr_scheme=True,
    )

    assert report["status"] == "pass"
    assert "PUBLIC_VERIFY_BASE_URL is unset; new labels will use the legacy agri:// QR scheme." in report["warnings"]


def test_launch_env_preflight_rejects_short_secret() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "too-short",
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_SECRET_KEY must be at least 32 characters." in report["errors"]


def test_launch_env_preflight_rejects_production_unsafe_runtime_values() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "a" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_DATABASE_URL": "sqlite:///local.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "*",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_AUTO_CREATE_SCHEMA must not be enabled for launch." in report["errors"]
    assert "Use a PostgreSQL AGRIGUARD_DATABASE_URL for launch, not SQLite." in report["errors"]
    assert "AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'." in report["errors"]


def test_launch_env_preflight_compose_mode_ignores_host_auto_create_schema() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        }
    )

    assert report["status"] == "pass"
    assert report["checks"]["runtime"] == "compose"
    assert report["checks"]["auto_create_schema"] is None
    assert report["checks"]["auto_create_schema_source"] == "AGRIGUARD_AUTO_CREATE_SCHEMA"


def test_launch_env_preflight_direct_mode_rejects_host_auto_create_schema() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "AUTO_CREATE_SCHEMA must not be enabled for launch." in report["errors"]


def test_launch_env_preflight_compose_mode_ignores_host_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "DATABASE_URL": "sqlite:///workspace-default.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        }
    )

    assert report["status"] == "pass"
    assert report["checks"]["runtime"] == "compose"
    assert report["checks"]["database_url_present"] is False
    assert report["checks"]["database_url_source"] is None


def test_launch_env_preflight_requires_explicit_allowed_origins_by_default() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
        }
    )

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_ALLOWED_ORIGINS for launch instead of relying on runtime defaults." in report["errors"]


def test_launch_env_preflight_can_allow_runtime_default_origins_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
            "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": "firebase-service-account.json",
        },
        allow_runtime_default_origins=True,
    )

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert "Set AGRIGUARD_ALLOWED_ORIGINS for launch instead of relying on runtime defaults." in report["warnings"]


def test_launch_env_preflight_compose_mode_ignores_host_allowed_origins_but_requires_app_scope() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
        }
    )

    assert report["status"] == "fail"
    assert report["checks"]["allowed_origins_count"] == 0
    assert report["checks"]["allowed_origins_source"] is None
    assert (
        "Set AGRIGUARD_ALLOWED_ORIGINS for compose launch instead of relying on generic ALLOWED_ORIGINS."
        in report["errors"]
    )


def test_launch_env_preflight_direct_mode_rejects_app_scoped_allowed_origins() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://app-scoped.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert report["checks"]["allowed_origins_count"] == 0
    assert report["checks"]["allowed_origins_source"] is None
    assert (
        "Set ALLOWED_ORIGINS for direct backend launch; AGRIGUARD_ALLOWED_ORIGINS is only bridged by compose."
        in report["errors"]
    )


def test_launch_env_preflight_direct_mode_accepts_host_allowed_origins() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
            "GOOGLE_APPLICATION_CREDENTIALS": "firebase-service-account.json",
        },
        runtime="direct",
    )

    assert report["status"] == "pass"
    assert report["checks"]["allowed_origins_count"] == 1
    assert report["checks"]["allowed_origins_source"] == "ALLOWED_ORIGINS"


def test_launch_env_preflight_direct_mode_requires_explicit_allowed_origins_by_default() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@localhost:5432/agriguard",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Set ALLOWED_ORIGINS for launch instead of relying on runtime defaults." in report["errors"]


def test_launch_env_preflight_compose_mode_rejects_app_scoped_wildcard_origin() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "*",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'." in report["errors"]


def test_launch_env_preflight_rejects_insecure_allowed_origin_for_launch() -> None:
    report = launch_env_preflight.validate_launch_env(
        _healthy_env() | {"AGRIGUARD_ALLOWED_ORIGINS": "http://agriguard.example"}
    )

    assert report["status"] == "fail"
    assert (
        "AGRIGUARD_ALLOWED_ORIGINS origin 'http://agriguard.example' must use an https:// URL for launch."
        in report["errors"]
    )


def test_launch_env_preflight_rejects_local_allowed_origin_for_launch() -> None:
    report = launch_env_preflight.validate_launch_env(
        _healthy_env() | {"AGRIGUARD_ALLOWED_ORIGINS": "http://localhost:5174"}
    )

    assert report["status"] == "fail"
    assert (
        "AGRIGUARD_ALLOWED_ORIGINS origin 'http://localhost:5174' must use an https:// URL for launch."
        in report["errors"]
    )
    assert (
        "AGRIGUARD_ALLOWED_ORIGINS origin 'http://localhost:5174' must not use a local host for launch."
        in report["errors"]
    )


def test_launch_env_preflight_rejects_allowed_origin_with_path_or_query() -> None:
    report = launch_env_preflight.validate_launch_env(
        _healthy_env() | {"AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example/app?debug=1"}
    )

    assert report["status"] == "fail"
    assert (
        "AGRIGUARD_ALLOWED_ORIGINS origin 'https://agriguard.example/app?debug=1' must not include a path."
        in report["errors"]
    )
    assert (
        "AGRIGUARD_ALLOWED_ORIGINS origin 'https://agriguard.example/app?debug=1' must not include params, query, or fragment."
        in report["errors"]
    )


def test_launch_env_preflight_can_allow_local_allowed_origins_for_local_checks() -> None:
    report = launch_env_preflight.validate_launch_env_with_options(
        _healthy_env() | {"AGRIGUARD_ALLOWED_ORIGINS": "http://localhost:5174"},
        allow_local_allowed_origins=True,
    )

    assert report["status"] == "pass"
    assert report["checks"]["allow_local_allowed_origins"] is True


def test_launch_env_preflight_direct_mode_rejects_host_sqlite_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "DATABASE_URL": "sqlite:///workspace-default.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Use a PostgreSQL DATABASE_URL for launch, not SQLite." in report["errors"]


def test_launch_env_preflight_compose_requires_database_password_without_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        }
    )

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_DB_PASSWORD or AGRIGUARD_DATABASE_URL before compose launch." in report["errors"]


def test_launch_env_preflight_compose_rejects_default_database_password() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
            "AGRIGUARD_DB_PASSWORD": "agriguard_secret",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_DB_PASSWORD uses a placeholder or development-only database password." in report["errors"]


def test_launch_env_preflight_rejects_database_url_without_password() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_DATABASE_URL": "postgresql://agriguard@postgres:5432/agriguard",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
            "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_DATABASE_URL password must include a database password for launch." in report["errors"]


def test_launch_env_preflight_direct_mode_requires_backend_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Set DATABASE_URL before direct backend launch." in report["errors"]


def test_launch_env_preflight_direct_mode_rejects_app_scoped_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "SECRET_KEY": "s" * 32,
            "QR_TOKEN_PEPPER": "p" * 32,
            "AGRIGUARD_DATABASE_URL": "postgresql://agriguard:dbpassword1234567890@postgres:5432/agriguard",
            "ALLOWED_ORIGINS": "https://generic.example",
            "PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Set DATABASE_URL for direct backend launch; AGRIGUARD_DATABASE_URL is only bridged by compose." in report["errors"]


def test_launch_env_preflight_passes_with_strong_secret_and_scoped_origins() -> None:
    report = launch_env_preflight.validate_launch_env(_healthy_env())

    assert report["status"] == "pass"
    assert report["blocker_class"] == "ready"
    assert report["errors"] == []


def test_launch_env_preflight_loads_env_file_and_environment_override(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AGRIGUARD_SECRET_KEY=change_me",
                "AGRIGUARD_QR_TOKEN_PEPPER=change_me_qr_token_hash_pepper",
                "AGRIGUARD_DATABASE_URL=postgresql://agriguard:dbpassword1234567890@postgres:5432/agriguard",
                "AGRIGUARD_ALLOWED_ORIGINS=https://agriguard.example",
                "AGRIGUARD_PUBLIC_VERIFY_BASE_URL=https://verify.agriguard.example",
                "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=firebase-service-account.json",
            ]
        ),
        encoding="utf-8",
    )

    effective = launch_env_preflight.build_effective_env(
        [env_file],
        environ={
            "AGRIGUARD_SECRET_KEY": "o" * 32,
            "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
        },
    )
    report = launch_env_preflight.validate_launch_env(effective)

    assert effective["AGRIGUARD_SECRET_KEY"] == "o" * 32
    assert report["status"] == "pass"


def test_launch_env_preflight_loads_utf8_bom_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AGRIGUARD_DB_USER=agriguard",
                "AGRIGUARD_SECRET_KEY=" + ("s" * 32),
            ]
        ),
        encoding="utf-8-sig",
    )

    env = launch_env_preflight.load_env_file(env_file)

    assert "AGRIGUARD_DB_USER" in env
    assert "\ufeffAGRIGUARD_DB_USER" not in env
    assert env["AGRIGUARD_SECRET_KEY"] == "s" * 32


def test_launch_report_skips_docker_checks_by_default(tmp_path: Path) -> None:
    credentials_path = _write_external_firebase_credentials_file(tmp_path)
    report = launch_env_preflight.build_launch_report(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path)},
        app_root=tmp_path,
    )

    assert report["status"] == "pass"
    assert report["blocker_class"] == "ready"
    assert report["checks"]["docker_checked"] is False
    assert "docker" not in report["checks"]


def test_launch_report_accepts_utf8_bom_firebase_credentials_file(tmp_path: Path) -> None:
    credentials_path = _write_external_firebase_credentials_file(tmp_path, encoding="utf-8-sig")

    report = launch_env_preflight.build_launch_report(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path)},
        app_root=tmp_path,
    )

    assert report["status"] == "pass"
    assert report["checks"]["firebase_credentials_file_exists"] is True
    assert report["checks"]["firebase_credentials_file_valid"] is True


def test_launch_report_rejects_repo_local_firebase_credentials_file(tmp_path: Path) -> None:
    repo_root, app_root = _fake_repo_app_root(tmp_path)
    credentials_path = _write_firebase_credentials_path(repo_root / "firebase-service-account.json")

    report = launch_env_preflight.build_launch_report(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path)},
        app_root=app_root,
    )

    assert report["status"] == "fail"
    assert (
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE must point to a Firebase service account file outside the repository."
        in report["errors"]
    )
    assert report["checks"]["firebase_credentials_file_exists"] is True
    assert report["checks"]["firebase_credentials_file_valid"] is False


def test_launch_report_accepts_firebase_credentials_file_outside_repository(tmp_path: Path) -> None:
    _, app_root = _fake_repo_app_root(tmp_path)
    credentials_path = _write_firebase_credentials_path(tmp_path / "secrets" / "firebase-service-account.json")

    report = launch_env_preflight.build_launch_report(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path)},
        app_root=app_root,
    )

    assert report["status"] == "pass"
    assert report["checks"]["firebase_credentials_file_exists"] is True
    assert report["checks"]["firebase_credentials_file_valid"] is True


def test_launch_report_rejects_missing_compose_firebase_credentials_file(tmp_path: Path) -> None:
    report = launch_env_preflight.build_launch_report(_healthy_env(), app_root=tmp_path)

    assert report["status"] == "fail"
    assert report["blocker_class"] == "preflight_blocked"
    assert "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist." in report["errors"]
    assert report["checks"]["firebase_credentials_file_checked"] is True
    assert report["checks"]["firebase_credentials_file_exists"] is False
    assert report["checks"]["firebase_credentials_file_valid"] is False


def test_launch_report_rejects_malformed_firebase_credentials_json(tmp_path: Path) -> None:
    credentials_path = tmp_path / "firebase-service-account.json"
    credentials_path.write_text("{not json", encoding="utf-8")

    report = launch_env_preflight.build_launch_report(_healthy_env(), app_root=tmp_path)

    assert report["status"] == "fail"
    assert "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE must contain valid JSON." in report["errors"]
    assert report["checks"]["firebase_credentials_file_exists"] is True
    assert report["checks"]["firebase_credentials_file_valid"] is False


def test_launch_report_rejects_placeholder_firebase_credentials_json(tmp_path: Path) -> None:
    credentials_path = tmp_path / "firebase-service-account.json"
    credentials_path.write_text('{"type":"service_account"}\n', encoding="utf-8")

    report = launch_env_preflight.build_launch_report(_healthy_env(), app_root=tmp_path)

    assert report["status"] == "fail"
    assert (
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE is missing required service account fields: "
        "project_id, private_key, client_email, token_uri."
    ) in report["errors"]
    assert report["checks"]["firebase_credentials_file_exists"] is True
    assert report["checks"]["firebase_credentials_file_valid"] is False


def test_launch_report_can_allow_runtime_default_origins_for_local_checks(tmp_path: Path) -> None:
    credentials_path = _write_external_firebase_credentials_file(tmp_path)
    env = {
        "AGRIGUARD_SECRET_KEY": "s" * 32,
        "AGRIGUARD_QR_TOKEN_PEPPER": "p" * 32,
        "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path),
    }

    report = launch_env_preflight.build_launch_report(
        env,
        allow_runtime_default_origins=True,
        app_root=tmp_path,
    )

    assert report["status"] == "pass"
    assert report["checks"]["allow_runtime_default_origins"] is True


def test_launch_report_can_allow_generic_secret_for_local_compose_checks(tmp_path: Path) -> None:
    credentials_path = _write_external_firebase_credentials_file(tmp_path)
    env = {
        "SECRET_KEY": "s" * 32,
        "QR_TOKEN_PEPPER": "p" * 32,
        "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        "AGRIGUARD_PUBLIC_VERIFY_BASE_URL": "https://verify.agriguard.example",
        "AGRIGUARD_DB_PASSWORD": "dbpassword1234567890",
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path),
    }

    report = launch_env_preflight.build_launch_report(
        env,
        allow_generic_secret_key=True,
        allow_generic_qr_token_pepper=True,
        app_root=tmp_path,
    )

    assert report["status"] == "pass"
    assert report["checks"]["secret_source"] == "SECRET_KEY"


def test_launch_report_docker_check_passes_when_daemon_and_compose_config_pass(tmp_path: Path) -> None:
    app_root = tmp_path
    credentials_path = _write_external_firebase_credentials_file(tmp_path)
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="29.2.1\n",
                stderr="",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env() | {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path)},
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "pass"
    assert report["checks"]["docker_checked"] is True
    assert report["checks"]["docker"]["docker_info"]["ok"] is True
    assert report["checks"]["docker"]["compose_config"]["ok"] is True


def test_launch_report_docker_check_passes_effective_env_to_compose_config(tmp_path: Path) -> None:
    app_root = tmp_path
    credentials_path = _write_external_firebase_credentials_file(tmp_path)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    env = _healthy_env() | {
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE": str(credentials_path),
        "AGRIGUARD_TEST_COMPOSE_ENV_MARKER": "from-effective-env",
    }
    report = launch_env_preflight.build_launch_report(
        env,
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "pass"
    assert calls[0][0] == ["docker", "info", "--format", "{{.ServerVersion}}"]
    assert "env" not in calls[0][1]
    assert calls[1][0] == ["docker", "compose", "-f", str(app_root / "docker-compose.yml"), "config", "--quiet"]
    compose_env = calls[1][1]["env"]
    assert isinstance(compose_env, dict)
    assert compose_env["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE"] == str(credentials_path)
    assert compose_env["AGRIGUARD_TEST_COMPOSE_ENV_MARKER"] == "from-effective-env"


def test_launch_report_docker_check_fails_when_daemon_unreachable(tmp_path: Path) -> None:
    app_root = tmp_path
    _write_firebase_credentials_file(app_root)
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="failed to connect to the docker API",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env(),
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "fail"
    assert "Docker daemon is not reachable for launch compose startup." in report["errors"]
    assert report["checks"]["docker"]["docker_info"]["stderr_tail"] == "failed to connect to the docker API"


def test_launch_report_docker_check_classifies_missing_firebase_compose_interpolation(
    tmp_path: Path,
) -> None:
    app_root = tmp_path
    compose_path = str(app_root / "docker-compose.yml")
    stderr = (
        "error while interpolating secrets.agriguard_firebase_service_account.file: "
        "required variable AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE is missing a value: "
        "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to an outside-repo Firebase service account JSON"
    )
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="29.2.1\n",
                stderr="",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=stderr,
            ),
        }
    )
    env = _healthy_env()
    env.pop("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE")

    report = launch_env_preflight.build_launch_report(
        env,
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "fail"
    assert (
        "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE before compose config validation; "
        "docker-compose.yml requires the outside-repo Firebase service account path."
    ) in report["errors"]
    assert "AgriGuard docker-compose.yml failed compose config validation." not in report["errors"]
    assert report["checks"]["docker"]["compose_config"]["stderr_tail"] == stderr


def test_launch_report_docker_check_fails_when_compose_config_is_invalid(tmp_path: Path) -> None:
    app_root = tmp_path
    _write_firebase_credentials_file(app_root)
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="29.2.1\n",
                stderr="",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=15,
                stdout="",
                stderr="invalid compose file",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env(),
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "fail"
    assert "AgriGuard docker-compose.yml failed compose config validation." in report["errors"]
    assert report["checks"]["docker"]["compose_config"]["stderr_tail"] == "invalid compose file"
