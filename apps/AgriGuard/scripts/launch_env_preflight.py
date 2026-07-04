from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

MIN_SECRET_LENGTH = 32
MIN_QR_TOKEN_PEPPER_LENGTH = 32
MIN_DATABASE_PASSWORD_LENGTH = 16
PLACEHOLDER_SECRETS = {
    "agriguard_secret",
    "change_me",
    "changeme",
    "change-me",
    "change_me_in_production",
    "secret",
    "secret_key",
    "test",
    "password",
}
PLACEHOLDER_PREFIXES = ("change_me", "changeme", "your_", "insecure-dev")
LOCAL_PUBLIC_VERIFY_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
FORBIDDEN_LAUNCH_TRUE_FLAGS = ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK")
COMPOSE_FIREBASE_CREDENTIALS_FILE = "/run/secrets/agriguard_firebase_service_account"
FIREBASE_SERVICE_ACCOUNT_REQUIRED_FIELDS = (
    "type",
    "project_id",
    "private_key",
    "client_email",
    "token_uri",
)


def _strip_optional_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        env[key] = _strip_optional_quotes(value)
    return env


def build_effective_env(env_files: Iterable[Path], environ: dict[str, str] | None = None) -> dict[str, str]:
    effective: dict[str, str] = {}
    for env_file in env_files:
        effective.update(load_env_file(env_file))
    effective.update(dict(os.environ if environ is None else environ))
    return effective


def _split_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def _env_flag_enabled(env: dict[str, str], name: str) -> bool:
    return (env.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_placeholder_value(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_SECRETS or any(
        normalized.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES
    )


def _database_url_for_runtime(env: dict[str, str], runtime: str) -> tuple[str, str | None]:
    if runtime == "compose":
        value = (env.get("AGRIGUARD_DATABASE_URL") or "").strip()
        return value, "AGRIGUARD_DATABASE_URL" if value else None

    value = (env.get("DATABASE_URL") or "").strip()
    return value, "DATABASE_URL" if value else None


def _is_postgresql_url(value: str) -> bool:
    scheme = urlparse(value).scheme.lower().split("+", 1)[0]
    return scheme in {"postgres", "postgresql"}


def _database_password_errors(password: str, *, source: str) -> list[str]:
    if not password:
        return [f"{source} must include a database password for launch."]
    if _is_placeholder_value(password):
        return [f"{source} uses a placeholder or development-only database password."]
    if len(password) < MIN_DATABASE_PASSWORD_LENGTH:
        return [f"{source} database password must be at least {MIN_DATABASE_PASSWORD_LENGTH} characters."]
    return []


def _database_credential_errors(
    env: dict[str, str],
    *,
    runtime: str,
    database_url: str,
    database_url_source: str | None,
) -> tuple[list[str], str | None]:
    if database_url:
        parsed = urlparse(database_url)
        password_source = f"{database_url_source} password"
        return _database_password_errors(parsed.password or "", source=password_source), password_source

    if runtime == "compose":
        db_password = (env.get("AGRIGUARD_DB_PASSWORD") or "").strip()
        if not db_password:
            return [
                "Set AGRIGUARD_DB_PASSWORD or AGRIGUARD_DATABASE_URL before compose launch."
            ], None
        return _database_password_errors(db_password, source="AGRIGUARD_DB_PASSWORD"), "AGRIGUARD_DB_PASSWORD"

    if (env.get("AGRIGUARD_DATABASE_URL") or "").strip():
        return [
            "Set DATABASE_URL for direct backend launch; AGRIGUARD_DATABASE_URL is only bridged by compose."
        ], None
    return ["Set DATABASE_URL before direct backend launch."], None


def _auto_create_schema_for_runtime(env: dict[str, str], runtime: str) -> tuple[str, str]:
    if runtime == "compose":
        return (env.get("AGRIGUARD_AUTO_CREATE_SCHEMA") or "").strip().lower(), "AGRIGUARD_AUTO_CREATE_SCHEMA"
    return (env.get("AUTO_CREATE_SCHEMA") or "").strip().lower(), "AUTO_CREATE_SCHEMA"


def _allowed_origins_for_runtime(env: dict[str, str], runtime: str) -> tuple[list[str], str | None, str | None]:
    if runtime == "compose":
        raw_value = env.get("AGRIGUARD_ALLOWED_ORIGINS") or ""
        if raw_value.strip():
            return _split_origins(raw_value), "AGRIGUARD_ALLOWED_ORIGINS", None
        if (env.get("ALLOWED_ORIGINS") or "").strip():
            return (
                [],
                None,
                "Set AGRIGUARD_ALLOWED_ORIGINS for compose launch instead of relying on generic ALLOWED_ORIGINS.",
            )
        return [], None, None

    raw_value = env.get("ALLOWED_ORIGINS") or ""
    if raw_value.strip():
        return _split_origins(raw_value), "ALLOWED_ORIGINS", None
    if (env.get("AGRIGUARD_ALLOWED_ORIGINS") or "").strip():
        return (
            [],
            None,
            "Set ALLOWED_ORIGINS for direct backend launch; AGRIGUARD_ALLOWED_ORIGINS is only bridged by compose.",
        )
    return [], None, None


def _secret_for_runtime(
    env: dict[str, str],
    runtime: str,
    *,
    allow_generic_secret_key: bool,
) -> tuple[str, str | None, str | None]:
    if runtime == "compose":
        app_scoped_secret = (env.get("AGRIGUARD_SECRET_KEY") or "").strip()
        if app_scoped_secret:
            return app_scoped_secret, "AGRIGUARD_SECRET_KEY", None
        generic_secret = (env.get("SECRET_KEY") or "").strip()
        if generic_secret and allow_generic_secret_key:
            return generic_secret, "SECRET_KEY", None
        if generic_secret:
            return "", None, "Set AGRIGUARD_SECRET_KEY for compose launch instead of relying on generic SECRET_KEY."
        return "", None, "Set AGRIGUARD_SECRET_KEY before compose launch."

    direct_secret = (env.get("SECRET_KEY") or "").strip()
    if direct_secret:
        return direct_secret, "SECRET_KEY", None
    if (env.get("AGRIGUARD_SECRET_KEY") or "").strip():
        return "", None, "Set SECRET_KEY for direct backend launch; AGRIGUARD_SECRET_KEY is only bridged by compose."
    return "", None, "Set SECRET_KEY before direct backend launch."


def _qr_token_pepper_for_runtime(
    env: dict[str, str],
    runtime: str,
    *,
    allow_generic_qr_token_pepper: bool,
) -> tuple[str, str | None, str | None]:
    if runtime == "compose":
        app_scoped_pepper = (env.get("AGRIGUARD_QR_TOKEN_PEPPER") or "").strip()
        if app_scoped_pepper:
            return app_scoped_pepper, "AGRIGUARD_QR_TOKEN_PEPPER", None
        generic_pepper = (env.get("QR_TOKEN_PEPPER") or "").strip()
        if generic_pepper and allow_generic_qr_token_pepper:
            return generic_pepper, "QR_TOKEN_PEPPER", None
        if generic_pepper:
            return "", None, "Set AGRIGUARD_QR_TOKEN_PEPPER for compose launch instead of relying on generic QR_TOKEN_PEPPER."
        return "", None, "Set AGRIGUARD_QR_TOKEN_PEPPER before compose launch."

    direct_pepper = (env.get("QR_TOKEN_PEPPER") or "").strip()
    if direct_pepper:
        return direct_pepper, "QR_TOKEN_PEPPER", None
    if (env.get("AGRIGUARD_QR_TOKEN_PEPPER") or "").strip():
        return "", None, "Set QR_TOKEN_PEPPER for direct backend launch; AGRIGUARD_QR_TOKEN_PEPPER is only bridged by compose."
    return "", None, "Set QR_TOKEN_PEPPER before direct backend launch."


def _public_verify_base_url_for_runtime(
    env: dict[str, str],
    runtime: str,
    *,
    allow_generic_public_verify_base_url: bool,
    allow_legacy_qr_scheme: bool,
) -> tuple[str, str | None, str | None]:
    if runtime == "compose":
        app_scoped_url = (env.get("AGRIGUARD_PUBLIC_VERIFY_BASE_URL") or "").strip()
        if app_scoped_url:
            return app_scoped_url, "AGRIGUARD_PUBLIC_VERIFY_BASE_URL", None
        generic_url = (env.get("PUBLIC_VERIFY_BASE_URL") or "").strip()
        if generic_url and allow_generic_public_verify_base_url:
            return generic_url, "PUBLIC_VERIFY_BASE_URL", None
        if generic_url:
            return (
                "",
                None,
                "Set AGRIGUARD_PUBLIC_VERIFY_BASE_URL for compose launch instead of relying on generic PUBLIC_VERIFY_BASE_URL.",
            )
        if allow_legacy_qr_scheme:
            return "", None, None
        return "", None, "Set AGRIGUARD_PUBLIC_VERIFY_BASE_URL before compose launch."

    direct_url = (env.get("PUBLIC_VERIFY_BASE_URL") or "").strip()
    if direct_url:
        return direct_url, "PUBLIC_VERIFY_BASE_URL", None
    if (env.get("AGRIGUARD_PUBLIC_VERIFY_BASE_URL") or "").strip():
        return (
            "",
            None,
            "Set PUBLIC_VERIFY_BASE_URL for direct backend launch; AGRIGUARD_PUBLIC_VERIFY_BASE_URL is only bridged by compose.",
        )
    if allow_legacy_qr_scheme:
        return "", None, None
    return "", None, "Set PUBLIC_VERIFY_BASE_URL before direct backend launch."


def _firebase_credentials_for_runtime(env: dict[str, str], runtime: str) -> tuple[str, str | None, str | None]:
    if runtime == "compose":
        host_file = (env.get("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE") or "").strip()
        if host_file:
            return host_file, "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE", None
        if (env.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip():
            return (
                "",
                None,
                "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE for compose launch instead of relying on generic GOOGLE_APPLICATION_CREDENTIALS.",
            )
        return (
            "",
            None,
            "Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to a Firebase service account JSON before compose launch.",
        )

    credentials = (env.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if credentials:
        return credentials, "GOOGLE_APPLICATION_CREDENTIALS", None
    if (env.get("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE") or "").strip():
        return (
            "",
            None,
            "Set GOOGLE_APPLICATION_CREDENTIALS for direct backend launch; AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE is only mounted by compose.",
        )
    return "", None, "Set GOOGLE_APPLICATION_CREDENTIALS to a Firebase service account file before launch."


def _resolve_app_relative_path(value: str, *, app_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (app_root / path).resolve()


def _firebase_credentials_file_check(value: str, *, source: str, app_root: Path) -> tuple[list[str], bool]:
    path = _resolve_app_relative_path(value, app_root=app_root)
    errors: list[str] = []
    if path.suffix.lower() != ".json":
        errors.append(f"{source} must point to a JSON Firebase service account file.")
    if not path.is_file():
        errors.append(f"{source} file does not exist.")
        return errors, False

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        errors.append(f"{source} must contain valid JSON.")
        return errors, True
    except OSError as exc:
        errors.append(f"{source} could not be read: {exc}.")
        return errors, True

    if not isinstance(payload, dict):
        errors.append(f"{source} must contain a JSON object.")
        return errors, True

    missing_fields = [
        field
        for field in FIREBASE_SERVICE_ACCOUNT_REQUIRED_FIELDS
        if not isinstance(payload.get(field), str) or not payload[field].strip()
    ]
    if missing_fields:
        errors.append(f"{source} is missing required service account fields: {', '.join(missing_fields)}.")

    if payload.get("type") != "service_account":
        errors.append(f"{source} must be a Google service account JSON file with type=service_account.")

    private_key = payload.get("private_key")
    if isinstance(private_key, str) and "BEGIN PRIVATE KEY" not in private_key:
        errors.append(f"{source} private_key must look like a PEM private key.")

    client_email = payload.get("client_email")
    if isinstance(client_email, str) and not client_email.endswith(".iam.gserviceaccount.com"):
        errors.append(f"{source} client_email must be a service account email.")

    token_uri = payload.get("token_uri")
    if isinstance(token_uri, str) and not token_uri.startswith("https://"):
        errors.append(f"{source} token_uri must use https://.")

    return errors, True


def _public_verify_base_url_errors(
    value: str,
    *,
    source: str,
    allow_local_public_verify_base_url: bool,
) -> list[str]:
    parsed = urlparse(value)
    errors: list[str] = []
    if parsed.scheme != "https":
        errors.append(f"{source} must use an https:// URL for launch.")
    if not parsed.netloc:
        errors.append(f"{source} must include a host.")
    if parsed.path not in {"", "/"}:
        errors.append(f"{source} must be a base URL without a path.")
    if parsed.params or parsed.query or parsed.fragment:
        errors.append(f"{source} must not include params, query, or fragment.")
    hostname = parsed.hostname or ""
    if hostname.lower() in LOCAL_PUBLIC_VERIFY_HOSTS and not allow_local_public_verify_base_url:
        errors.append(f"{source} must not use a local host for launch.")
    return errors


def _allowed_origin_errors(
    origins: list[str],
    *,
    source: str,
    allow_local_allowed_origins: bool,
) -> list[str]:
    errors: list[str] = []
    for origin in origins:
        parsed = urlparse(origin)
        hostname = parsed.hostname or ""
        is_local = hostname.lower() in LOCAL_PUBLIC_VERIFY_HOSTS
        if parsed.scheme != "https" and not (
            allow_local_allowed_origins and parsed.scheme == "http" and is_local
        ):
            errors.append(f"{source} origin {origin!r} must use an https:// URL for launch.")
        if not parsed.netloc:
            errors.append(f"{source} origin {origin!r} must include a host.")
        if parsed.path not in {"", "/"}:
            errors.append(f"{source} origin {origin!r} must not include a path.")
        if parsed.params or parsed.query or parsed.fragment:
            errors.append(f"{source} origin {origin!r} must not include params, query, or fragment.")
        if is_local and not allow_local_allowed_origins:
            errors.append(f"{source} origin {origin!r} must not use a local host for launch.")
    return errors


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def validate_launch_env(env: dict[str, str], *, runtime: str = "compose") -> dict[str, object]:
    return validate_launch_env_with_options(env, runtime=runtime)


def validate_launch_env_with_options(
    env: dict[str, str],
    *,
    runtime: str = "compose",
    allow_runtime_default_origins: bool = False,
    allow_generic_secret_key: bool = False,
    allow_generic_qr_token_pepper: bool = False,
    allow_generic_public_verify_base_url: bool = False,
    allow_legacy_qr_scheme: bool = False,
    allow_local_public_verify_base_url: bool = False,
    allow_local_allowed_origins: bool = False,
    allow_missing_firebase_credentials: bool = False,
) -> dict[str, object]:
    if runtime not in {"compose", "direct"}:
        raise ValueError("runtime must be 'compose' or 'direct'")

    errors: list[str] = []
    warnings: list[str] = []

    forbidden_enabled_flags = [name for name in FORBIDDEN_LAUNCH_TRUE_FLAGS if _env_flag_enabled(env, name)]
    for flag_name in forbidden_enabled_flags:
        errors.append(f"{flag_name} must not be enabled for launch.")
    dev_auth_fallback_role_set = bool((env.get("DEV_AUTH_FALLBACK_ROLE") or "").strip())
    if dev_auth_fallback_role_set:
        errors.append("DEV_AUTH_FALLBACK_ROLE must not be set for launch.")

    firebase_credentials, firebase_credentials_source, firebase_credentials_error = _firebase_credentials_for_runtime(
        env,
        runtime,
    )
    if firebase_credentials_error:
        message = firebase_credentials_error
        if allow_missing_firebase_credentials:
            warnings.append(message)
        else:
            errors.append(message)
    elif _is_placeholder_value(firebase_credentials):
        errors.append(f"{firebase_credentials_source} uses a placeholder or development-only value.")

    secret, secret_source, secret_error = _secret_for_runtime(
        env,
        runtime,
        allow_generic_secret_key=allow_generic_secret_key,
    )
    if secret_error:
        errors.append(secret_error)
    elif _is_placeholder_value(secret):
        errors.append(f"{secret_source} uses a placeholder or development-only value.")
    elif len(secret) < MIN_SECRET_LENGTH:
        errors.append(f"{secret_source} must be at least {MIN_SECRET_LENGTH} characters.")

    qr_token_pepper, qr_token_pepper_source, qr_token_pepper_error = _qr_token_pepper_for_runtime(
        env,
        runtime,
        allow_generic_qr_token_pepper=allow_generic_qr_token_pepper,
    )
    if qr_token_pepper_error:
        errors.append(qr_token_pepper_error)
    elif _is_placeholder_value(qr_token_pepper):
        errors.append(f"{qr_token_pepper_source} uses a placeholder or development-only value.")
    elif len(qr_token_pepper) < MIN_QR_TOKEN_PEPPER_LENGTH:
        errors.append(f"{qr_token_pepper_source} must be at least {MIN_QR_TOKEN_PEPPER_LENGTH} characters.")

    public_verify_base_url, public_verify_base_url_source, public_verify_base_url_error = (
        _public_verify_base_url_for_runtime(
            env,
            runtime,
            allow_generic_public_verify_base_url=allow_generic_public_verify_base_url,
            allow_legacy_qr_scheme=allow_legacy_qr_scheme,
        )
    )
    if public_verify_base_url_error:
        errors.append(public_verify_base_url_error)
    elif public_verify_base_url_source:
        errors.extend(
            _public_verify_base_url_errors(
                public_verify_base_url,
                source=public_verify_base_url_source,
                allow_local_public_verify_base_url=allow_local_public_verify_base_url,
            )
        )
    elif allow_legacy_qr_scheme:
        warnings.append("PUBLIC_VERIFY_BASE_URL is unset; new labels will use the legacy agri:// QR scheme.")

    auto_create_schema, auto_create_schema_source = _auto_create_schema_for_runtime(env, runtime)
    if auto_create_schema in {"1", "true", "yes", "on"}:
        errors.append(f"{auto_create_schema_source} must not be enabled for launch.")

    database_url, database_url_source = _database_url_for_runtime(env, runtime)
    if database_url.lower().startswith("sqlite"):
        errors.append(f"Use a PostgreSQL {database_url_source} for launch, not SQLite.")
    elif database_url and not _is_postgresql_url(database_url):
        errors.append(f"Use a PostgreSQL {database_url_source} for launch.")
    database_credential_errors, database_password_source = _database_credential_errors(
        env,
        runtime=runtime,
        database_url=database_url,
        database_url_source=database_url_source,
    )
    errors.extend(database_credential_errors)

    origins, origins_source, origins_error = _allowed_origins_for_runtime(env, runtime)
    if "*" in origins:
        errors.append(f"{origins_source} must not include wildcard '*'.")
    elif origins_error:
        errors.append(origins_error)
    elif not origins:
        if runtime == "compose":
            message = "Set AGRIGUARD_ALLOWED_ORIGINS for launch instead of relying on runtime defaults."
        else:
            message = "Set ALLOWED_ORIGINS for launch instead of relying on runtime defaults."
        if allow_runtime_default_origins:
            warnings.append(message)
        else:
            errors.append(message)
    elif origins_source:
        errors.extend(
            _allowed_origin_errors(
                origins,
                source=origins_source,
                allow_local_allowed_origins=allow_local_allowed_origins,
            )
        )

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "runtime": runtime,
            "forbidden_launch_flags_enabled": forbidden_enabled_flags,
            "dev_auth_fallback_role_set": dev_auth_fallback_role_set,
            "firebase_credentials_source": firebase_credentials_source,
            "compose_firebase_credentials_file": COMPOSE_FIREBASE_CREDENTIALS_FILE,
            "allow_missing_firebase_credentials": allow_missing_firebase_credentials,
            "secret_source": secret_source,
            "secret_min_length": MIN_SECRET_LENGTH,
            "allow_generic_secret_key": allow_generic_secret_key,
            "qr_token_pepper_source": qr_token_pepper_source,
            "qr_token_pepper_min_length": MIN_QR_TOKEN_PEPPER_LENGTH,
            "allow_generic_qr_token_pepper": allow_generic_qr_token_pepper,
            "public_verify_base_url_source": public_verify_base_url_source,
            "allow_generic_public_verify_base_url": allow_generic_public_verify_base_url,
            "allow_legacy_qr_scheme": allow_legacy_qr_scheme,
            "allow_local_public_verify_base_url": allow_local_public_verify_base_url,
            "auto_create_schema": auto_create_schema or None,
            "auto_create_schema_source": auto_create_schema_source,
            "database_url_present": bool(database_url),
            "database_url_source": database_url_source,
            "database_password_source": database_password_source,
            "database_password_min_length": MIN_DATABASE_PASSWORD_LENGTH,
            "allowed_origins_count": len(origins),
            "allowed_origins_source": origins_source,
            "allow_runtime_default_origins": allow_runtime_default_origins,
            "allow_local_allowed_origins": allow_local_allowed_origins,
        },
    }


def _tail(value: str | bytes | None, *, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = value.strip()
    return value[-limit:] if len(value) > limit else value


def _run_preflight_command(
    command: list[str],
    *,
    cwd: Path,
    command_runner: CommandRunner,
) -> dict[str, object]:
    try:
        result = command_runner(command, cwd=str(cwd), capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        return {
            "command": command,
            "returncode": None,
            "ok": False,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "ok": False,
            "stdout_tail": _tail(exc.stdout or ""),
            "stderr_tail": "command timed out",
        }

    return {
        "command": command,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout_tail": _tail(result.stdout or ""),
        "stderr_tail": _tail(result.stderr or ""),
    }


def check_docker_readiness(
    *,
    app_root: Path,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, object]:
    docker_info = _run_preflight_command(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        cwd=app_root,
        command_runner=command_runner,
    )
    compose_config = _run_preflight_command(
        ["docker", "compose", "-f", str(app_root / "docker-compose.yml"), "config", "--quiet"],
        cwd=app_root,
        command_runner=command_runner,
    )

    errors: list[str] = []
    if not docker_info["ok"]:
        errors.append("Docker daemon is not reachable for launch compose startup.")
    if not compose_config["ok"]:
        errors.append("AgriGuard docker-compose.yml failed compose config validation.")

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "checks": {
            "docker_info": docker_info,
            "compose_config": compose_config,
        },
    }


def build_launch_report(
    env: dict[str, str],
    *,
    runtime: str = "compose",
    check_docker: bool = False,
    allow_runtime_default_origins: bool = False,
    allow_generic_secret_key: bool = False,
    allow_generic_qr_token_pepper: bool = False,
    allow_generic_public_verify_base_url: bool = False,
    allow_legacy_qr_scheme: bool = False,
    allow_local_public_verify_base_url: bool = False,
    allow_local_allowed_origins: bool = False,
    allow_missing_firebase_credentials: bool = False,
    app_root: Path | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, object]:
    report = validate_launch_env_with_options(
        env,
        runtime=runtime,
        allow_runtime_default_origins=allow_runtime_default_origins,
        allow_generic_secret_key=allow_generic_secret_key,
        allow_generic_qr_token_pepper=allow_generic_qr_token_pepper,
        allow_generic_public_verify_base_url=allow_generic_public_verify_base_url,
        allow_legacy_qr_scheme=allow_legacy_qr_scheme,
        allow_local_public_verify_base_url=allow_local_public_verify_base_url,
        allow_local_allowed_origins=allow_local_allowed_origins,
        allow_missing_firebase_credentials=allow_missing_firebase_credentials,
    )
    checks = report["checks"]
    assert isinstance(checks, dict)
    checks["docker_checked"] = check_docker

    firebase_credentials_source = checks.get("firebase_credentials_source")
    if firebase_credentials_source in {"AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS"}:
        firebase_credentials = (
            env.get(str(firebase_credentials_source)) or ""
        ).strip()
        firebase_credential_errors, firebase_credentials_file_exists = _firebase_credentials_file_check(
            firebase_credentials,
            source=str(firebase_credentials_source),
            app_root=app_root or Path(__file__).resolve().parents[1],
        )
        if firebase_credential_errors and not (allow_missing_firebase_credentials and not firebase_credentials_file_exists):
            errors = report["errors"]
            assert isinstance(errors, list)
            errors.extend(firebase_credential_errors)
            report["status"] = "fail"
        checks["firebase_credentials_file_checked"] = True
        checks["firebase_credentials_file_exists"] = firebase_credentials_file_exists
        checks["firebase_credentials_file_valid"] = not firebase_credential_errors
    else:
        checks["firebase_credentials_file_checked"] = False

    if check_docker:
        docker_report = check_docker_readiness(
            app_root=app_root or Path(__file__).resolve().parents[1],
            command_runner=command_runner,
        )
        checks["docker"] = docker_report["checks"]
        errors = report["errors"]
        assert isinstance(errors, list)
        errors.extend(docker_report["errors"])
        report["status"] = "fail" if errors else "pass"

    return report


def _default_env_files() -> list[Path]:
    app_root = Path(__file__).resolve().parents[1]
    return [app_root / "backend" / ".env", app_root / ".env"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed AgriGuard launch environment preflight.")
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=None,
        help="Optional env file to load before process environment values. May be repeated.",
    )
    parser.add_argument(
        "--runtime",
        choices=["compose", "direct"],
        default="compose",
        help="Launch runtime to validate. Compose mode ignores host DATABASE_URL unless AGRIGUARD_DATABASE_URL is set.",
    )
    parser.add_argument(
        "--check-docker",
        action="store_true",
        help="Also require Docker daemon reachability and compose config validation.",
    )
    parser.add_argument(
        "--allow-runtime-default-origins",
        action="store_true",
        help="Permit missing explicit allowed origins and report a warning instead of a launch-blocking error.",
    )
    parser.add_argument(
        "--allow-generic-secret-key",
        action="store_true",
        help="Permit compose launch preflight to accept generic SECRET_KEY when AGRIGUARD_SECRET_KEY is not set.",
    )
    parser.add_argument(
        "--allow-generic-qr-token-pepper",
        action="store_true",
        help="Permit compose launch preflight to accept generic QR_TOKEN_PEPPER when AGRIGUARD_QR_TOKEN_PEPPER is not set.",
    )
    parser.add_argument(
        "--allow-generic-public-verify-base-url",
        action="store_true",
        help="Permit compose launch preflight to accept generic PUBLIC_VERIFY_BASE_URL when AGRIGUARD_PUBLIC_VERIFY_BASE_URL is not set.",
    )
    parser.add_argument(
        "--allow-legacy-qr-scheme",
        action="store_true",
        help="Permit missing PUBLIC_VERIFY_BASE_URL and report a warning that new labels will use agri:// URLs.",
    )
    parser.add_argument(
        "--allow-local-public-verify-base-url",
        action="store_true",
        help="Permit localhost/loopback PUBLIC_VERIFY_BASE_URL values for local smoke checks.",
    )
    parser.add_argument(
        "--allow-local-allowed-origins",
        action="store_true",
        help="Permit localhost/loopback HTTP allowed origins for local smoke checks.",
    )
    parser.add_argument(
        "--allow-missing-firebase-credentials",
        action="store_true",
        help="Permit missing Firebase Admin credentials for local auth-fallback diagnostics.",
    )
    parser.add_argument("--json-out", type=Path, help="Optional path to write the JSON preflight report.")
    args = parser.parse_args(argv)

    env_files = args.env_file if args.env_file is not None else _default_env_files()
    report = build_launch_report(
        build_effective_env(env_files),
        runtime=args.runtime,
        check_docker=args.check_docker,
        allow_runtime_default_origins=args.allow_runtime_default_origins,
        allow_generic_secret_key=args.allow_generic_secret_key,
        allow_generic_qr_token_pepper=args.allow_generic_qr_token_pepper,
        allow_generic_public_verify_base_url=args.allow_generic_public_verify_base_url,
        allow_legacy_qr_scheme=args.allow_legacy_qr_scheme,
        allow_local_public_verify_base_url=args.allow_local_public_verify_base_url,
        allow_local_allowed_origins=args.allow_local_allowed_origins,
        allow_missing_firebase_credentials=args.allow_missing_firebase_credentials,
    )

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
