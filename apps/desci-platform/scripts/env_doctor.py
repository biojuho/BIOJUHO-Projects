#!/usr/bin/env python3
"""Environment preflight checks for DSCI-DecentBio.

The script intentionally uses only the Python standard library so it can run on
an operator machine before dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


LLM_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")
FIREBASE_FRONTEND_KEYS = (
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_STORAGE_BUCKET",
    "VITE_FIREBASE_MESSAGING_SENDER_ID",
    "VITE_FIREBASE_APP_ID",
)

PLACEHOLDER_FRAGMENTS = (
    "your_",
    "your-",
    "YOUR_",
    "YOUR-",
    "change_me",
    "changeme",
    "example.com",
    "example_",
    "...",
    "0x...",
)


@dataclass(frozen=True)
class EnvCheck:
    id: str
    label: str
    status: str
    required: bool
    keys: tuple[str, ...]
    message: str
    remediation: str


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value
    return values


def load_env(paths: Iterable[Path], *, include_process_env: bool = True) -> dict[str, str]:
    env: dict[str, str] = {}
    for path in paths:
        env.update(parse_env_file(path))
    if include_process_env:
        env.update(os.environ)
    return env


def is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_configured(env: dict[str, str], key: str) -> bool:
    value = (env.get(key) or "").strip()
    if not value:
        return False
    lowered = value.lower()
    return not any(fragment.lower() in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def configured_keys(env: dict[str, str], keys: Iterable[str]) -> tuple[str, ...]:
    return tuple(key for key in keys if is_configured(env, key))


def make_check(
    check_id: str,
    label: str,
    *,
    required: bool,
    ok: bool,
    keys: Iterable[str],
    pass_message: str,
    missing_message: str,
    remediation: str,
) -> EnvCheck:
    status = "pass" if ok else "fail" if required else "warn"
    return EnvCheck(
        id=check_id,
        label=label,
        status=status,
        required=required,
        keys=tuple(keys),
        message=pass_message if ok else missing_message,
        remediation="" if ok else remediation,
    )


def run_checks(env: dict[str, str], *, profile: str) -> list[EnvCheck]:
    production = profile == "production"
    auth_keys = ("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_PROJECT_ID", "FIREBASE_SERVICE_ACCOUNT_JSON")
    if not production:
        auth_keys = (*auth_keys, "ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK")

    checks = [
        make_check(
            "runtime",
            "Runtime profile",
            required=production,
            ok=(env.get("ENV") == "production") if production else True,
            keys=("ENV",),
            pass_message=f"ENV is set for {profile} checks.",
            missing_message="ENV is not set to production.",
            remediation="Set ENV=production in the backend runtime before public launch.",
        ),
        make_check(
            "llm",
            "LLM provider",
            required=production,
            ok=bool(configured_keys(env, LLM_KEYS)),
            keys=LLM_KEYS,
            pass_message="At least one LLM provider key is configured.",
            missing_message="No non-placeholder LLM provider key is configured.",
            remediation="Set one of GEMINI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY.",
        ),
        make_check(
            "auth",
            "Firebase/Auth",
            required=production,
            ok=bool(configured_keys(env, auth_keys)) or (not production and is_truthy(env.get("ALLOW_TEST_BYPASS"))),
            keys=auth_keys,
            pass_message="Authentication runtime is configured.",
            missing_message="Authentication runtime is not configured.",
            remediation="Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON. Use ALLOW_TEST_BYPASS only for local smoke.",
        ),
        make_check(
            "frontend_firebase",
            "Frontend Firebase",
            required=production,
            ok=all(is_configured(env, key) for key in FIREBASE_FRONTEND_KEYS),
            keys=FIREBASE_FRONTEND_KEYS,
            pass_message="Frontend Firebase config is complete.",
            missing_message="Frontend Firebase config is incomplete.",
            remediation="Set all VITE_FIREBASE_* values in the frontend deployment environment.",
        ),
        make_check(
            "api_base",
            "Frontend API base URL",
            required=production,
            ok=is_configured(env, "VITE_API_BASE_URL"),
            keys=("VITE_API_BASE_URL",),
            pass_message="Frontend API base URL is configured.",
            missing_message="Frontend API base URL is missing.",
            remediation="Set VITE_API_BASE_URL to the deployed FastAPI origin.",
        ),
        make_check(
            "cors",
            "CORS allowlist",
            required=production,
            ok=is_configured(env, "ALLOWED_ORIGINS"),
            keys=("ALLOWED_ORIGINS",),
            pass_message="CORS allowlist is configured.",
            missing_message="CORS allowlist is missing.",
            remediation="Set ALLOWED_ORIGINS to the deployed frontend origin list.",
        ),
        make_check(
            "postgres",
            "PostgreSQL",
            required=production,
            ok=is_configured(env, "DATABASE_URL"),
            keys=("DATABASE_URL",),
            pass_message="PostgreSQL connection string is configured.",
            missing_message="PostgreSQL connection string is missing.",
            remediation="Set DATABASE_URL to the production PostgreSQL connection string.",
        ),
        make_check(
            "supabase",
            "Supabase",
            required=production,
            ok=is_configured(env, "SUPABASE_URL") and is_configured(env, "SUPABASE_SERVICE_ROLE_KEY"),
            keys=("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
            pass_message="Supabase service credentials are configured.",
            missing_message="Supabase service credentials are incomplete.",
            remediation="Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for server-side data operations.",
        ),
        make_check(
            "redis",
            "Redis",
            required=production,
            ok=is_configured(env, "REDIS_URL"),
            keys=("REDIS_URL",),
            pass_message="Redis URL is configured.",
            missing_message="Redis URL is missing.",
            remediation="Set REDIS_URL for cache and job-state operations.",
        ),
        make_check(
            "rabbitmq",
            "RabbitMQ",
            required=production,
            ok=is_configured(env, "RABBITMQ_URL"),
            keys=("RABBITMQ_URL",),
            pass_message="RabbitMQ URL is configured.",
            missing_message="RabbitMQ URL is missing.",
            remediation="Set RABBITMQ_URL for background job dispatch.",
        ),
        make_check(
            "ipfs",
            "IPFS/Pinata",
            required=False,
            ok=is_configured(env, "PINATA_JWT") or (is_configured(env, "PINATA_API_KEY") and is_configured(env, "PINATA_API_SECRET")),
            keys=("PINATA_JWT", "PINATA_API_KEY", "PINATA_API_SECRET"),
            pass_message="IPFS credentials are configured.",
            missing_message="IPFS credentials are not configured.",
            remediation="Set PINATA_JWT, or PINATA_API_KEY plus PINATA_API_SECRET, before enabling public asset minting.",
        ),
        make_check(
            "web3",
            "Web3 contracts",
            required=False,
            ok=is_configured(env, "WEB3_RPC_URL") and is_configured(env, "DSCI_CONTRACT_ADDRESS"),
            keys=("WEB3_RPC_URL", "DSCI_CONTRACT_ADDRESS", "NFT_CONTRACT_ADDRESS", "DISTRIBUTOR_PRIVATE_KEY"),
            pass_message="Web3 RPC and contract address are configured.",
            missing_message="Web3 contract config is incomplete.",
            remediation="Set WEB3_RPC_URL and contract addresses after deployment. Keep DISTRIBUTOR_PRIVATE_KEY in a secret manager.",
        ),
        make_check(
            "stripe",
            "Stripe billing",
            required=False,
            ok=is_configured(env, "STRIPE_SECRET_KEY") and is_configured(env, "STRIPE_WEBHOOK_SECRET"),
            keys=("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
            pass_message="Stripe billing secrets are configured.",
            missing_message="Stripe billing secrets are not configured.",
            remediation="Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET before turning on paid checkout.",
        ),
    ]
    return checks


def print_text_report(checks: list[EnvCheck], *, profile: str) -> None:
    print(f"[env-doctor] profile={profile}")
    for check in checks:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[check.status]
        required = "required" if check.required else "recommended"
        print(f"[{marker}] {check.label} ({required}) - {check.message}")
        if check.remediation:
            print(f"       {check.remediation}")

    failed = [check for check in checks if check.status == "fail"]
    warned = [check for check in checks if check.status == "warn"]
    print(f"\n[env-doctor] {len(failed)} failed, {len(warned)} warning(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DSCI-DecentBio launch environment variables.")
    parser.add_argument("--profile", choices=("local", "production"), default="local")
    parser.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Env file to load. Can be passed multiple times; later files override earlier files.",
    )
    parser.add_argument("--ignore-process-env", action="store_true", help="Do not overlay current process environment.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    paths = [Path(path) for path in args.env_file]
    if not paths:
        paths = [Path(".env"), Path("biolinker/.env"), Path("frontend/.env")]

    env = load_env(paths, include_process_env=not args.ignore_process_env)
    checks = run_checks(env, profile=args.profile)
    failed = [check for check in checks if check.status == "fail"]

    if args.json:
        print(json.dumps({"profile": args.profile, "checks": [asdict(check) for check in checks]}, indent=2))
    else:
        print_text_report(checks, profile=args.profile)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
