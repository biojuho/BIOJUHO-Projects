from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

MIN_SECRET_LENGTH = 32
PLACEHOLDER_SECRETS = {
    "change_me",
    "changeme",
    "change-me",
    "change_me_in_production",
    "secret",
    "secret_key",
    "test",
    "password",
}


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


def _database_url_for_runtime(env: dict[str, str], runtime: str) -> tuple[str, str | None]:
    if runtime == "compose":
        value = (env.get("AGRIGUARD_DATABASE_URL") or "").strip()
        return value, "AGRIGUARD_DATABASE_URL" if value else None

    value = (env.get("AGRIGUARD_DATABASE_URL") or "").strip()
    if value:
        return value, "AGRIGUARD_DATABASE_URL"
    value = (env.get("DATABASE_URL") or "").strip()
    return value, "DATABASE_URL" if value else None


def _auto_create_schema_for_runtime(env: dict[str, str], runtime: str) -> tuple[str, str]:
    if runtime == "compose":
        return (env.get("AGRIGUARD_AUTO_CREATE_SCHEMA") or "").strip().lower(), "AGRIGUARD_AUTO_CREATE_SCHEMA"
    return (env.get("AUTO_CREATE_SCHEMA") or "").strip().lower(), "AUTO_CREATE_SCHEMA"


def _allowed_origins_for_runtime(env: dict[str, str], runtime: str) -> tuple[list[str], str | None]:
    if runtime == "compose":
        raw_value = env.get("AGRIGUARD_ALLOWED_ORIGINS") or ""
        return _split_origins(raw_value), "AGRIGUARD_ALLOWED_ORIGINS" if raw_value.strip() else None

    raw_value = env.get("AGRIGUARD_ALLOWED_ORIGINS") or ""
    if raw_value.strip():
        return _split_origins(raw_value), "AGRIGUARD_ALLOWED_ORIGINS"
    raw_value = env.get("ALLOWED_ORIGINS") or ""
    return _split_origins(raw_value), "ALLOWED_ORIGINS" if raw_value.strip() else None


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def validate_launch_env(env: dict[str, str], *, runtime: str = "compose") -> dict[str, object]:
    return validate_launch_env_with_options(env, runtime=runtime)


def validate_launch_env_with_options(
    env: dict[str, str],
    *,
    runtime: str = "compose",
    allow_runtime_default_origins: bool = False,
) -> dict[str, object]:
    if runtime not in {"compose", "direct"}:
        raise ValueError("runtime must be 'compose' or 'direct'")

    errors: list[str] = []
    warnings: list[str] = []

    secret_source = "AGRIGUARD_SECRET_KEY" if env.get("AGRIGUARD_SECRET_KEY") else "SECRET_KEY"
    secret = (env.get(secret_source) or "").strip()
    normalized_secret = secret.lower()

    if not secret:
        errors.append("Set AGRIGUARD_SECRET_KEY or SECRET_KEY before launch.")
    elif normalized_secret in PLACEHOLDER_SECRETS or normalized_secret.startswith("insecure-dev-only"):
        errors.append(f"{secret_source} uses a placeholder or development-only value.")
    elif len(secret) < MIN_SECRET_LENGTH:
        errors.append(f"{secret_source} must be at least {MIN_SECRET_LENGTH} characters.")

    auto_create_schema, auto_create_schema_source = _auto_create_schema_for_runtime(env, runtime)
    if auto_create_schema in {"1", "true", "yes", "on"}:
        errors.append(f"{auto_create_schema_source} must not be enabled for launch.")

    database_url, database_url_source = _database_url_for_runtime(env, runtime)
    if database_url.lower().startswith("sqlite"):
        errors.append(f"Use a PostgreSQL {database_url_source} for launch, not SQLite.")

    origins, origins_source = _allowed_origins_for_runtime(env, runtime)
    if "*" in origins:
        errors.append(f"{origins_source} must not include wildcard '*'.")
    elif not origins:
        message = "Set AGRIGUARD_ALLOWED_ORIGINS for launch instead of relying on runtime defaults."
        if allow_runtime_default_origins:
            warnings.append(message)
        else:
            errors.append(message)

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "runtime": runtime,
            "secret_source": secret_source if secret else None,
            "secret_min_length": MIN_SECRET_LENGTH,
            "auto_create_schema": auto_create_schema or None,
            "auto_create_schema_source": auto_create_schema_source,
            "database_url_present": bool(database_url),
            "database_url_source": database_url_source,
            "allowed_origins_count": len(origins),
            "allowed_origins_source": origins_source,
            "allow_runtime_default_origins": allow_runtime_default_origins,
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
    app_root: Path | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, object]:
    report = validate_launch_env_with_options(
        env,
        runtime=runtime,
        allow_runtime_default_origins=allow_runtime_default_origins,
    )
    checks = report["checks"]
    assert isinstance(checks, dict)
    checks["docker_checked"] = check_docker

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
    return [app_root / ".env"]


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
    parser.add_argument("--json-out", type=Path, help="Optional path to write the JSON preflight report.")
    args = parser.parse_args(argv)

    env_files = args.env_file if args.env_file is not None else _default_env_files()
    report = build_launch_report(
        build_effective_env(env_files),
        runtime=args.runtime,
        check_docker=args.check_docker,
        allow_runtime_default_origins=args.allow_runtime_default_origins,
    )

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
