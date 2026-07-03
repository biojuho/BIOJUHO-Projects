#!/usr/bin/env python3
"""Deployment readiness preflight for DeSci Platform.

This script is intentionally offline and standard-library only. It checks
whether the operator has provided the secrets/configuration needed for the
external deployment steps before running Railway, Vercel, or Amoy commands.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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
    "0x...",
)

FIREBASE_FRONTEND_KEYS = (
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_STORAGE_BUCKET",
    "VITE_FIREBASE_MESSAGING_SENDER_ID",
    "VITE_FIREBASE_APP_ID",
)
FRONTEND_WALLET_CONTRACT_KEYS = (
    "VITE_DSCI_TOKEN_ADDRESS",
    "VITE_RESEARCH_PAPER_NFT_ADDRESS",
)
FRONTEND_WALLET_RPC_KEY = "VITE_WALLET_RPC_URL"
LLM_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")
AUTH_KEYS = ("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON")
EXPLORER_KEYS = ("POLYGONSCAN_API_KEY", "ETHERSCAN_API_KEY")
STRIPE_LAUNCH_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO_MONTHLY",
    "STRIPE_PRICE_PRO_YEARLY",
)
PINATA_KEYS = ("PINATA_JWT", "PINATA_API_KEY", "PINATA_API_SECRET")
GROBID_KEYS = ("GROBID_ENABLED", "GROBID_URL")
FORBIDDEN_PRODUCTION_FLAGS = ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK", "MOCK_MODE")
FRONTEND_RETURN_URL_KEY = "DESCI_FRONTEND_URL"
POLYGON_AMOY_CHAIN_IDS = {"80002", "0x13882"}
ZERO_EVM_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_SURFACE_BY_TARGET = {
    "railway": ("Railway backend", "Backend runtime"),
    "vercel": ("Vercel frontend", "Frontend deployment"),
    "amoy": ("Polygon Amoy", "Contracts and Web3"),
    "github": ("GitHub repository", "CI and repository secrets"),
}
SURFACE_BY_CHECK_ID = {
    "railway_auth": ("Firebase", "Backend authentication"),
    "railway_cors": ("Railway + Vercel", "CORS allowlist"),
    "railway_frontend_return_url": ("Stripe + Railway", "Checkout return URLs"),
    "railway_grobid": ("GROBID", "PDF parsing"),
    "railway_ipfs": ("Pinata/IPFS", "Public asset minting"),
    "railway_stripe": ("Stripe", "Paid checkout"),
    "vercel_firebase": ("Firebase + Vercel", "Frontend authentication"),
    "github_gitleaks_license": ("GitHub repository", "Secret scanning"),
}


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    target: str
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


def has_configured_public_https_url(env: dict[str, str], keys: Iterable[str]) -> bool:
    return any(is_configured_public_https_url(env, key) for key in keys)


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


def has_pinata_credentials(env: dict[str, str]) -> bool:
    return is_configured(env, "PINATA_JWT") or (
        is_configured(env, "PINATA_API_KEY") and is_configured(env, "PINATA_API_SECRET")
    )


def has_grobid_config(env: dict[str, str]) -> bool:
    return is_truthy(env.get("GROBID_ENABLED")) and is_configured(env, "GROBID_URL")


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


def has_firebase_backend_credentials(env: dict[str, str]) -> bool:
    if is_configured(env, "GOOGLE_APPLICATION_CREDENTIALS"):
        return True
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


def is_private_key(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip()
    if not normalized.startswith("0x"):
        normalized = f"0x{normalized}"
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{64}", normalized))


def has_forbidden_production_flags(env: dict[str, str]) -> bool:
    return any(is_truthy(env.get(key)) for key in FORBIDDEN_PRODUCTION_FLAGS)


def check(
    check_id: str,
    target: str,
    label: str,
    *,
    required: bool,
    ok: bool,
    keys: Iterable[str],
    message: str,
    remediation: str,
) -> ReadinessCheck:
    status = "pass" if ok else "fail" if required else "warn"
    return ReadinessCheck(
        id=check_id,
        target=target,
        label=label,
        status=status,
        required=required,
        keys=tuple(keys),
        message=message if ok else "Not ready.",
        remediation="" if ok else remediation,
    )


def cli_check(target: str, cli_name: str, *, required: bool) -> ReadinessCheck:
    ok = shutil.which(cli_name) is not None
    return check(
        f"{target}_cli",
        target,
        f"{cli_name} CLI",
        required=required,
        ok=ok,
        keys=(),
        message=f"{cli_name} is available on PATH.",
        remediation=f"Install and authenticate {cli_name} before running the {target} deployment.",
    )


def railway_checks(env: dict[str, str], *, check_cli: bool) -> list[ReadinessCheck]:
    checks = [
        check(
            "railway_env",
            "railway",
            "Production runtime profile",
            required=True,
            ok=env.get("ENV") == "production",
            keys=("ENV",),
            message="ENV=production is set.",
            remediation="Set ENV=production in Railway variables.",
        ),
        check(
            "railway_llm",
            "railway",
            "LLM provider",
            required=True,
            ok=bool(configured_keys(env, LLM_KEYS)),
            keys=LLM_KEYS,
            message="At least one LLM provider key is configured.",
            remediation="Set one real LLM provider key in Railway variables.",
        ),
        check(
            "railway_auth",
            "railway",
            "Backend authentication",
            required=True,
            ok=has_firebase_backend_credentials(env),
            keys=AUTH_KEYS,
            message="Backend auth secret is configured.",
            remediation=(
                "Set GOOGLE_APPLICATION_CREDENTIALS or a complete FIREBASE_SERVICE_ACCOUNT_JSON "
                "with project_id, client_email, and private_key via Railway secrets."
            ),
        ),
        check(
            "railway_production_safety_flags",
            "railway",
            "Production safety flags",
            required=True,
            ok=not has_forbidden_production_flags(env),
            keys=FORBIDDEN_PRODUCTION_FLAGS,
            message="No local bypass or mock flags are enabled for Railway production.",
            remediation=(
                "Remove ALLOW_TEST_BYPASS, ALLOW_DEV_AUTH_FALLBACK, and MOCK_MODE from Railway "
                "production variables. Use real Firebase auth and deployed Web3 configuration instead."
            ),
        ),
        check(
            "railway_database",
            "railway",
            "PostgreSQL",
            required=True,
            ok=is_configured(env, "DATABASE_URL"),
            keys=("DATABASE_URL",),
            message="DATABASE_URL is configured.",
            remediation="Attach Railway PostgreSQL or set DATABASE_URL to a managed Postgres connection string.",
        ),
        check(
            "railway_cors",
            "railway",
            "CORS allowlist",
            required=True,
            ok=cors_has_frontend_origin(env),
            keys=("ALLOWED_ORIGINS",),
            message="ALLOWED_ORIGINS contains deployed frontend HTTPS origins.",
            remediation=(
                "Set ALLOWED_ORIGINS to deployed Vercel HTTPS origins without paths, queries, or fragments; "
                "do not use the API origin as the only CORS origin."
            ),
        ),
        check(
            "railway_frontend_return_url",
            "railway",
            "Checkout and billing return URL",
            required=True,
            ok=is_configured_public_https_origin(env, FRONTEND_RETURN_URL_KEY),
            keys=(FRONTEND_RETURN_URL_KEY,),
            message="DESCI_FRONTEND_URL is a public HTTPS frontend origin.",
            remediation=(
                "Set DESCI_FRONTEND_URL to the deployed frontend HTTPS origin used for Stripe Checkout "
                "success/cancel URLs and Billing Portal return URLs."
            ),
        ),
        check(
            "railway_queue",
            "railway",
            "Queue/cache services",
            required=True,
            ok=is_configured(env, "REDIS_URL") and is_configured(env, "RABBITMQ_URL"),
            keys=("REDIS_URL", "RABBITMQ_URL"),
            message="Redis and RabbitMQ URLs are configured.",
            remediation="Set REDIS_URL and RABBITMQ_URL for cache/job dispatch.",
        ),
        check(
            "railway_ipfs",
            "railway",
            "Pinata/IPFS asset storage",
            required=False,
            ok=has_pinata_credentials(env),
            keys=PINATA_KEYS,
            message="Pinata credentials are configured for public asset minting.",
            remediation="Set PINATA_JWT, or PINATA_API_KEY plus PINATA_API_SECRET, before public asset minting.",
        ),
        check(
            "railway_grobid",
            "railway",
            "GROBID PDF parsing",
            required=False,
            ok=has_grobid_config(env),
            keys=GROBID_KEYS,
            message="GROBID parsing is enabled and points at a configured service URL.",
            remediation="Set GROBID_ENABLED=true and GROBID_URL to a reachable GROBID service.",
        ),
        check(
            "railway_stripe",
            "railway",
            "Stripe paid checkout",
            required=True,
            ok=all(is_configured(env, key) for key in STRIPE_LAUNCH_KEYS),
            keys=STRIPE_LAUNCH_KEYS,
            message="Stripe secret, webhook secret, and Pro price IDs are configured.",
            remediation=(
                "Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO_MONTHLY, "
                "and STRIPE_PRICE_PRO_YEARLY in Railway variables before enabling paid checkout."
            ),
        ),
    ]
    if check_cli:
        checks.append(cli_check("railway", "railway", required=False))
    return checks


def vercel_checks(env: dict[str, str], *, check_cli: bool) -> list[ReadinessCheck]:
    checks = [
        check(
            "vercel_api_base",
            "vercel",
            "API base URL",
            required=True,
            ok=is_configured_public_https_url(env, "VITE_API_BASE_URL"),
            keys=("VITE_API_BASE_URL",),
            message="VITE_API_BASE_URL is a public HTTPS URL.",
            remediation="Set VITE_API_BASE_URL to the Railway backend HTTPS URL in Vercel variables.",
        ),
        check(
            "vercel_firebase",
            "vercel",
            "Firebase frontend config",
            required=True,
            ok=all(is_configured(env, key) for key in FIREBASE_FRONTEND_KEYS),
            keys=FIREBASE_FRONTEND_KEYS,
            message="All VITE_FIREBASE_* values are configured.",
            remediation="Set every VITE_FIREBASE_* value in Vercel variables.",
        ),
        check(
            "vercel_wallet_network",
            "vercel",
            "Wallet network target",
            required=True,
            ok=is_polygon_amoy_chain_id(env.get("VITE_WALLET_CHAIN_ID")),
            keys=("VITE_WALLET_CHAIN_ID",),
            message="VITE_WALLET_CHAIN_ID targets Polygon Amoy.",
            remediation="Set VITE_WALLET_CHAIN_ID to 80002 or 0x13882 in Vercel variables.",
        ),
        check(
            "vercel_wallet_rpc",
            "vercel",
            "Wallet RPC override",
            required=True,
            ok=has_optional_public_https_urls(env, FRONTEND_WALLET_RPC_KEY),
            keys=(FRONTEND_WALLET_RPC_KEY,),
            message="VITE_WALLET_RPC_URL is absent or contains public HTTPS RPC URL values.",
            remediation=(
                "Leave VITE_WALLET_RPC_URL unset to use the bundled Polygon Amoy default, or set it to "
                "comma-separated public HTTPS Polygon Amoy RPC URL values."
            ),
        ),
        check(
            "vercel_wallet_contracts",
            "vercel",
            "Wallet contract addresses",
            required=True,
            ok=has_evm_addresses(env, FRONTEND_WALLET_CONTRACT_KEYS, require_all=True),
            keys=FRONTEND_WALLET_CONTRACT_KEYS,
            message="Frontend wallet contract addresses are non-zero EVM addresses.",
            remediation=(
                "Set VITE_DSCI_TOKEN_ADDRESS and VITE_RESEARCH_PAPER_NFT_ADDRESS to the deployed "
                "DeSciToken and ResearchPaperNFT addresses; do not rely on frontend zero-address defaults."
            ),
        ),
    ]
    if check_cli:
        checks.append(cli_check("vercel", "vercel", required=False))
    return checks


def amoy_checks(env: dict[str, str]) -> list[ReadinessCheck]:
    return [
        check(
            "amoy_rpc",
            "amoy",
            "Polygon Amoy RPC",
            required=True,
            ok=has_configured_public_https_url(env, ("AMOY_RPC_URL", "WEB3_RPC_URL")),
            keys=("AMOY_RPC_URL", "WEB3_RPC_URL"),
            message="Amoy RPC URL is configured as a public HTTPS URL.",
            remediation="Set AMOY_RPC_URL or WEB3_RPC_URL to a public HTTPS Polygon Amoy RPC endpoint.",
        ),
        check(
            "amoy_private_key",
            "amoy",
            "Deployment signer",
            required=True,
            ok=is_private_key(env.get("PRIVATE_KEY")),
            keys=("PRIVATE_KEY",),
            message="PRIVATE_KEY is a valid 32-byte hex key.",
            remediation="Set a funded testnet wallet PRIVATE_KEY. Never commit it.",
        ),
        check(
            "amoy_explorer",
            "amoy",
            "Explorer verification key",
            required=True,
            ok=bool(configured_keys(env, EXPLORER_KEYS)),
            keys=EXPLORER_KEYS,
            message="Explorer API key is configured.",
            remediation="Set POLYGONSCAN_API_KEY, or ETHERSCAN_API_KEY as a fallback.",
        ),
        check(
            "amoy_funding",
            "amoy",
            "Wallet funding",
            required=False,
            ok=False,
            keys=("PRIVATE_KEY",),
            message="Wallet funding was not checked offline.",
            remediation="Before deploy, confirm the signer address has Amoy MATIC from the Polygon faucet.",
        ),
    ]


def github_checks(env: dict[str, str]) -> list[ReadinessCheck]:
    return [
        check(
            "github_gitleaks_license",
            "github",
            "Gitleaks license secret",
            required=True,
            ok=is_configured(env, "GITLEAKS_LICENSE"),
            keys=("GITLEAKS_LICENSE",),
            message="GITLEAKS_LICENSE is configured.",
            remediation="Add GITLEAKS_LICENSE as a GitHub repository or organization secret.",
        )
    ]


def run_checks(env: dict[str, str], *, targets: Iterable[str], check_cli: bool = False) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    for target in targets:
        if target == "railway":
            checks.extend(railway_checks(env, check_cli=check_cli))
        elif target == "vercel":
            checks.extend(vercel_checks(env, check_cli=check_cli))
        elif target == "amoy":
            checks.extend(amoy_checks(env))
        elif target == "github":
            checks.extend(github_checks(env))
        else:
            raise ValueError(f"unknown target: {target}")
    return checks


def print_report(checks: list[ReadinessCheck]) -> None:
    for item in checks:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[item.status]
        required = "required" if item.required else "recommended"
        print(f"[{marker}] {item.target}: {item.label} ({required}) - {item.message}")
        if item.remediation:
            print(f"       {item.remediation}")
    failed = sum(1 for item in checks if item.status == "fail")
    warned = sum(1 for item in checks if item.status == "warn")
    print(f"\n[deploy-readiness] {failed} failed, {warned} warning(s)")
    print_owner_surface_summary(checks)


def owner_surface_for_check(item: ReadinessCheck) -> tuple[str, str]:
    return SURFACE_BY_CHECK_ID.get(item.id, DEFAULT_SURFACE_BY_TARGET[item.target])


def owner_surface_summary(checks: list[ReadinessCheck]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for item in checks:
        owner, surface = owner_surface_for_check(item)
        group = groups.setdefault(
            (owner, surface),
            {
                "owner": owner,
                "surface": surface,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "failed_checks": [],
                "warning_checks": [],
                "required_env": [],
                "actions": [],
            },
        )
        group["total"] += 1
        if item.status == "pass":
            group["passed"] += 1
            continue
        if item.status == "fail":
            group["failed"] += 1
            group["failed_checks"].append(item.id)
        if item.status == "warn":
            group["warnings"] += 1
            group["warning_checks"].append(item.id)
        for key in item.keys:
            if key not in group["required_env"]:
                group["required_env"].append(key)
        group["actions"].append(
            {
                "id": item.id,
                "target": item.target,
                "label": item.label,
                "status": item.status,
                "required": item.required,
                "keys": list(item.keys),
                "remediation": item.remediation,
            }
        )
    return [groups[key] for key in sorted(groups)]


def print_owner_surface_summary(checks: list[ReadinessCheck]) -> None:
    actionable = [group for group in owner_surface_summary(checks) if group["failed"] or group["warnings"]]
    if not actionable:
        return
    print("\n[deploy-readiness] ACTION BY SURFACE")
    for group in actionable:
        print(f"- {group['owner']} / {group['surface']}: {group['failed']} failed, {group['warnings']} warning(s)")
        for action in group["actions"]:
            env_text = f" env={', '.join(action['keys'])}" if action["keys"] else ""
            print(f"  - {action['id']}: {action['remediation']}{env_text}")


def json_report_payload(checks: list[ReadinessCheck], *, targets: Iterable[str]) -> dict[str, Any]:
    failed = [item for item in checks if item.status == "fail"]
    warned = [item for item in checks if item.status == "warn"]
    passed = [item for item in checks if item.status == "pass"]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failed,
        "targets": list(targets),
        "summary": {
            "total": len(checks),
            "passed": len(passed),
            "failed": len(failed),
            "warnings": len(warned),
            "failed_checks": [item.id for item in failed],
            "warning_checks": [item.id for item in warned],
        },
        "owner_surface_summary": owner_surface_summary(checks),
        "checks": [asdict(item) for item in checks],
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
    parser = argparse.ArgumentParser(description="Check DeSci external deployment readiness.")
    parser.add_argument(
        "--target",
        action="append",
        choices=("railway", "vercel", "amoy", "github", "all"),
        default=[],
        help="Deployment target to check. Repeatable. Defaults to all.",
    )
    parser.add_argument("--env-file", action="append", default=[], help="Env file to load; repeatable.")
    parser.add_argument("--ignore-process-env", action="store_true")
    parser.add_argument("--check-cli", action="store_true", help="Also check local deployment CLI availability.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--json-out", help="Write machine-readable JSON to a file.")
    args = parser.parse_args()

    targets = args.target or ["all"]
    if "all" in targets:
        targets = ["railway", "vercel", "amoy", "github"]
    paths = [Path(path) for path in args.env_file] or [
        Path(".env.production"),
        Path(".env"),
        Path("backend/.env"),
        Path("frontend/.env"),
        Path("contracts/.env"),
    ]

    include_process_env = not args.ignore_process_env
    env = load_env(paths, include_process_env=include_process_env)
    checks = run_checks(env, targets=targets, check_cli=args.check_cli)
    failed = [item for item in checks if item.status == "fail"]
    payload = json_report_payload(checks, targets=targets)
    payload["sources"] = env_source_report(paths, include_process_env=include_process_env)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_report(checks)
    if args.json_out:
        write_json_report(Path(args.json_out), payload)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
