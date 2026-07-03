#!/usr/bin/env python3
"""Environment preflight checks for DSCI-DecentBio.

The script intentionally uses only the Python standard library so it can run on
an operator machine before dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_io import write_json_atomic

LLM_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")
FIREBASE_FRONTEND_KEYS = (
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_STORAGE_BUCKET",
    "VITE_FIREBASE_MESSAGING_SENDER_ID",
    "VITE_FIREBASE_APP_ID",
)
WEB3_CONTRACT_KEYS = (
    "DSCI_CONTRACT_ADDRESS",
    "NFT_CONTRACT_ADDRESS",
    "DESCI_DAO_CONTRACT_ADDRESS",
)
FRONTEND_WALLET_CONTRACT_KEYS = (
    "VITE_DSCI_TOKEN_ADDRESS",
    "VITE_RESEARCH_PAPER_NFT_ADDRESS",
)
FRONTEND_WALLET_RPC_KEY = "VITE_WALLET_RPC_URL"
STRIPE_LAUNCH_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO_MONTHLY",
    "STRIPE_PRICE_PRO_YEARLY",
)
FORBIDDEN_PRODUCTION_FLAGS = ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK", "MOCK_MODE")
FRONTEND_RETURN_URL_KEY = "DESCI_FRONTEND_URL"
POLYGON_AMOY_CHAIN_IDS = {"80002", "0x13882"}
ZERO_EVM_ADDRESS = "0x0000000000000000000000000000000000000000"

PLACEHOLDER_FRAGMENTS = (
    "your_",
    "your-",
    "YOUR_",
    "YOUR-",
    "change_me",
    "changeme",
    "example.com",
    ".example",
    "example_",
    "example.",
    ".invalid",
    ".test",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "*",
    "user:password@host",
    "user:pass@db",
    "your-project",
    "your_project",
    "use_secret_manager_not_plaintext",
    "<set-secure-value>",
    "set-secure-value",
    "0x0000000000000000000000000000000000000000",
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


def is_public_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    lowered = value.lower()
    return not any(fragment.lower() in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def is_public_https_origin(value: str) -> bool:
    parsed = urlparse(value.strip())
    return is_public_https_url(value) and parsed.path in ("", "/") and not (parsed.params or parsed.query or parsed.fragment)


def is_configured_public_https_url(env: dict[str, str], key: str) -> bool:
    value = (env.get(key) or "").strip()
    return bool(value and is_public_https_url(value))


def is_configured_public_https_origin(env: dict[str, str], key: str) -> bool:
    value = (env.get(key) or "").strip()
    return bool(value and is_public_https_origin(value))


def has_configured_public_https_url(env: dict[str, str], key: str) -> bool:
    return is_configured_public_https_url(env, key)


def csv_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def has_optional_public_https_urls(env: dict[str, str], key: str) -> bool:
    urls = csv_values(env.get(key))
    return not urls or all(is_public_https_url(url) for url in urls)


def url_origin(value: str) -> str:
    parsed = urlparse(value.strip())
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def has_public_https_origins(env: dict[str, str], key: str) -> bool:
    origins = [origin.strip() for origin in (env.get(key) or "").split(",") if origin.strip()]
    return bool(origins) and all(is_public_https_origin(origin) for origin in origins)


def cors_has_frontend_origin(env: dict[str, str]) -> bool:
    if not has_public_https_origins(env, "ALLOWED_ORIGINS"):
        return False
    api_base = (env.get("VITE_API_BASE_URL") or "").strip()
    if not api_base or not is_public_https_url(api_base):
        return False
    api_origin = url_origin(api_base)
    origins = [url_origin(origin) for origin in (env.get("ALLOWED_ORIGINS") or "").split(",") if origin.strip()]
    return any(origin != api_origin for origin in origins)


def configured_keys(env: dict[str, str], keys: Iterable[str]) -> tuple[str, ...]:
    return tuple(key for key in keys if is_configured(env, key))


def is_evm_address(value: str | None) -> bool:
    normalized = (value or "").strip()
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", normalized)) and normalized.lower() != ZERO_EVM_ADDRESS


def has_evm_addresses(env: dict[str, str], keys: Iterable[str], *, require_all: bool = False) -> bool:
    results = [is_evm_address(env.get(key)) for key in keys]
    return all(results) if require_all else any(results)


def normalize_chain_id(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""
    if normalized.startswith("0x"):
        return normalized
    if normalized.isdecimal():
        return f"0x{int(normalized):x}"
    return normalized


def is_polygon_amoy_chain_id(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in POLYGON_AMOY_CHAIN_IDS or normalize_chain_id(normalized) in POLYGON_AMOY_CHAIN_IDS


def has_firebase_service_account_json(env: dict[str, str]) -> bool:
    value = (env.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
    if not value or not is_configured(env, "FIREBASE_SERVICE_ACCOUNT_JSON"):
        return False
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return all(isinstance(payload.get(key), str) and payload.get(key) for key in ("project_id", "client_email", "private_key"))


def auth_keys_for_profile(profile: str) -> tuple[str, ...]:
    auth_keys = ("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON")
    if profile == "production":
        return auth_keys
    return (*auth_keys, "ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK")


def has_auth_config(env: dict[str, str], auth_keys: Iterable[str], *, production: bool) -> bool:
    has_backend_credentials = is_configured(env, "GOOGLE_APPLICATION_CREDENTIALS") or has_firebase_service_account_json(env)
    return has_backend_credentials or (not production and is_truthy(env.get("ALLOW_TEST_BYPASS")))


def has_frontend_firebase_config(env: dict[str, str]) -> bool:
    return all(is_configured(env, key) for key in FIREBASE_FRONTEND_KEYS)


def has_supabase_config(env: dict[str, str]) -> bool:
    return is_configured(env, "SUPABASE_URL") and is_configured(env, "SUPABASE_SERVICE_ROLE_KEY")


def has_ipfs_config(env: dict[str, str]) -> bool:
    return is_configured(env, "PINATA_JWT") or (
        is_configured(env, "PINATA_API_KEY") and is_configured(env, "PINATA_API_SECRET")
    )


def has_web3_config(env: dict[str, str], *, production: bool) -> bool:
    real_web3_config = has_configured_public_https_url(env, "WEB3_RPC_URL") and has_evm_addresses(env, WEB3_CONTRACT_KEYS)
    return real_web3_config or (not production and is_truthy(env.get("MOCK_MODE")))


def has_frontend_wallet_config(env: dict[str, str]) -> bool:
    return (
        is_polygon_amoy_chain_id(env.get("VITE_WALLET_CHAIN_ID"))
        and has_optional_public_https_urls(env, FRONTEND_WALLET_RPC_KEY)
        and has_evm_addresses(
            env,
            FRONTEND_WALLET_CONTRACT_KEYS,
            require_all=True,
        )
    )


def has_stripe_config(env: dict[str, str]) -> bool:
    return all(is_configured(env, key) for key in STRIPE_LAUNCH_KEYS)


def has_forbidden_production_flags(env: dict[str, str]) -> bool:
    return any(is_truthy(env.get(key)) for key in FORBIDDEN_PRODUCTION_FLAGS)


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
    auth_keys = auth_keys_for_profile(profile)

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
            ok=has_auth_config(env, auth_keys, production=production),
            keys=auth_keys,
            pass_message="Authentication runtime is configured.",
            missing_message="Authentication runtime is not configured.",
            remediation="Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON. Use ALLOW_TEST_BYPASS only for local smoke.",
        ),
        make_check(
            "production_safety_flags",
            "Production safety flags",
            required=production,
            ok=not (production and has_forbidden_production_flags(env)),
            keys=FORBIDDEN_PRODUCTION_FLAGS,
            pass_message="No local bypass or mock flags are enabled for production.",
            missing_message="Production runtime has local bypass or mock flags enabled.",
            remediation=(
                "Remove ALLOW_TEST_BYPASS, ALLOW_DEV_AUTH_FALLBACK, and MOCK_MODE from production "
                "runtime variables. Use real Firebase auth and deployed Web3 configuration instead."
            ),
        ),
        make_check(
            "frontend_firebase",
            "Frontend Firebase",
            required=production,
            ok=has_frontend_firebase_config(env),
            keys=FIREBASE_FRONTEND_KEYS,
            pass_message="Frontend Firebase config is complete.",
            missing_message="Frontend Firebase config is incomplete.",
            remediation="Set all VITE_FIREBASE_* values in the frontend deployment environment.",
        ),
        make_check(
            "api_base",
            "Frontend API base URL",
            required=production,
            ok=is_configured_public_https_url(env, "VITE_API_BASE_URL"),
            keys=("VITE_API_BASE_URL",),
            pass_message="Frontend API base URL is a public HTTPS URL.",
            missing_message="Frontend API base URL is missing or not a public HTTPS URL.",
            remediation="Set VITE_API_BASE_URL to the deployed FastAPI HTTPS URL.",
        ),
        make_check(
            "frontend_wallet",
            "Frontend wallet provider",
            required=production,
            ok=has_frontend_wallet_config(env),
            keys=("VITE_WALLET_CHAIN_ID", FRONTEND_WALLET_RPC_KEY, *FRONTEND_WALLET_CONTRACT_KEYS),
            pass_message="Frontend wallet provider targets Polygon Amoy with deployed contract addresses.",
            missing_message="Frontend wallet provider config is incomplete.",
            remediation=(
                "Set VITE_WALLET_CHAIN_ID=80002 plus non-zero VITE_DSCI_TOKEN_ADDRESS and "
                "VITE_RESEARCH_PAPER_NFT_ADDRESS values in the frontend deployment environment. "
                "If VITE_WALLET_RPC_URL is set, use comma-separated public HTTPS Polygon Amoy RPC URLs."
            ),
        ),
        make_check(
            "cors",
            "CORS allowlist",
            required=production,
            ok=cors_has_frontend_origin(env),
            keys=("ALLOWED_ORIGINS",),
            pass_message="CORS allowlist contains deployed frontend HTTPS origins.",
            missing_message="CORS allowlist is missing, malformed, or only points at the API origin.",
            remediation=(
                "Set ALLOWED_ORIGINS to deployed frontend HTTPS origins without paths, queries, or fragments; "
                "do not use the API origin as the only CORS origin."
            ),
        ),
        make_check(
            "frontend_return_url",
            "Checkout and billing return URL",
            required=production,
            ok=is_configured_public_https_origin(env, FRONTEND_RETURN_URL_KEY),
            keys=(FRONTEND_RETURN_URL_KEY,),
            pass_message="Checkout and Billing Portal return URL is a public HTTPS frontend origin.",
            missing_message="Checkout and Billing Portal return URL is missing or not a public HTTPS frontend origin.",
            remediation=(
                "Set DESCI_FRONTEND_URL to the deployed frontend HTTPS origin used for Stripe Checkout "
                "success/cancel URLs and Billing Portal return URLs."
            ),
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
            ok=has_supabase_config(env),
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
            ok=has_ipfs_config(env),
            keys=("PINATA_JWT", "PINATA_API_KEY", "PINATA_API_SECRET"),
            pass_message="IPFS credentials are configured.",
            missing_message="IPFS credentials are not configured.",
            remediation="Set PINATA_JWT, or PINATA_API_KEY plus PINATA_API_SECRET, before enabling public asset minting.",
        ),
        make_check(
            "web3",
            "Web3 contracts",
            required=False,
            ok=has_web3_config(env, production=production),
            keys=("MOCK_MODE", "WEB3_RPC_URL", *WEB3_CONTRACT_KEYS, "DISTRIBUTOR_PRIVATE_KEY"),
            pass_message="Web3 deployed contract configuration is present.",
            missing_message="Web3 contract config is incomplete.",
            remediation=(
                "Use MOCK_MODE=true only for local demos. For production, configure WEB3_RPC_URL plus at least "
                "one deployed DSCI/NFT/DAO contract address. Keep DISTRIBUTOR_PRIVATE_KEY in a secret manager."
            ),
        ),
        make_check(
            "stripe",
            "Stripe billing",
            required=production,
            ok=has_stripe_config(env),
            keys=STRIPE_LAUNCH_KEYS,
            pass_message="Stripe billing secrets and Pro price IDs are configured.",
            missing_message="Stripe billing launch config is incomplete.",
            remediation=(
                "Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO_MONTHLY, "
                "and STRIPE_PRICE_PRO_YEARLY before turning on paid checkout."
            ),
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


def json_report_payload(checks: list[EnvCheck], *, profile: str) -> dict[str, Any]:
    failed = [check for check in checks if check.status == "fail"]
    warned = [check for check in checks if check.status == "warn"]
    passed = [check for check in checks if check.status == "pass"]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failed,
        "profile": profile,
        "summary": {
            "total": len(checks),
            "passed": len(passed),
            "failed": len(failed),
            "warnings": len(warned),
            "failed_checks": [check.id for check in failed],
            "warning_checks": [check.id for check in warned],
        },
        "checks": [asdict(check) for check in checks],
    }


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    write_json_atomic(path, payload)


def env_source_report(paths: Iterable[Path], *, include_process_env: bool) -> dict[str, Any]:
    return {
        "env_files": [
            {
                "path": str(path),
                "resolved_path": str(path.expanduser().resolve()),
                "exists": path.exists(),
            }
            for path in paths
        ],
        "include_process_env": include_process_env,
    }


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
    parser.add_argument("--json-out", help="Write machine-readable JSON to a file.")
    args = parser.parse_args()

    paths = [Path(path) for path in args.env_file]
    if not paths:
        paths = [Path(".env"), Path("backend/.env"), Path("frontend/.env")]

    include_process_env = not args.ignore_process_env
    env = load_env(paths, include_process_env=include_process_env)
    checks = run_checks(env, profile=args.profile)
    failed = [check for check in checks if check.status == "fail"]
    payload = json_report_payload(checks, profile=args.profile)
    payload["sources"] = env_source_report(paths, include_process_env=include_process_env)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_text_report(checks, profile=args.profile)
    if args.json_out:
        write_json_report(Path(args.json_out), payload)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
