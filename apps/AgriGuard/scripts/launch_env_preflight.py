from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

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


def validate_launch_env(env: dict[str, str], *, runtime: str = "compose") -> dict[str, object]:
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

    auto_create_schema = (env.get("AUTO_CREATE_SCHEMA") or "").strip().lower()
    if auto_create_schema in {"1", "true", "yes", "on"}:
        errors.append("AUTO_CREATE_SCHEMA must not be enabled for launch.")

    database_url, database_url_source = _database_url_for_runtime(env, runtime)
    if database_url.lower().startswith("sqlite"):
        errors.append(f"Use a PostgreSQL {database_url_source} for launch, not SQLite.")

    origins = _split_origins(env.get("AGRIGUARD_ALLOWED_ORIGINS") or env.get("ALLOWED_ORIGINS") or "")
    if "*" in origins:
        errors.append("ALLOWED_ORIGINS/AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'.")
    elif not origins:
        warnings.append("No explicit allowed origins configured; compose defaults may be used.")

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "runtime": runtime,
            "secret_source": secret_source if secret else None,
            "secret_min_length": MIN_SECRET_LENGTH,
            "auto_create_schema": auto_create_schema or None,
            "database_url_present": bool(database_url),
            "database_url_source": database_url_source,
            "allowed_origins_count": len(origins),
        },
    }


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
    parser.add_argument("--json-out", type=Path, help="Optional path to write the JSON preflight report.")
    args = parser.parse_args(argv)

    env_files = args.env_file if args.env_file is not None else _default_env_files()
    report = validate_launch_env(build_effective_env(env_files), runtime=args.runtime)

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
