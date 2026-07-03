#!/usr/bin/env python3
"""Combine DeSci external deploy readiness with provider CLI preflight."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import deploy_readiness
import provider_preflight
from evidence_io import write_json_atomic

DEFAULT_TARGETS = ("railway", "vercel", "amoy", "github")
PROVIDER_TARGETS = ("railway", "vercel", "github")


def normalize_targets(targets: list[str] | tuple[str, ...] | None) -> list[str]:
    selected = list(targets or ("all",))
    if "all" in selected:
        return list(DEFAULT_TARGETS)
    return selected


def provider_targets_for(targets: list[str] | tuple[str, ...]) -> list[str]:
    return [target for target in targets if target in PROVIDER_TARGETS]


def deploy_readiness_payload(
    *,
    targets: list[str],
    env_files: list[Path],
    include_process_env: bool,
    check_cli: bool,
) -> dict[str, Any]:
    env = deploy_readiness.load_env(env_files, include_process_env=include_process_env)
    checks = deploy_readiness.run_checks(env, targets=targets, check_cli=check_cli)
    payload = deploy_readiness.json_report_payload(checks, targets=targets)
    payload["sources"] = deploy_readiness.env_source_report(env_files, include_process_env=include_process_env)
    return payload


def run_external_gate(
    *,
    targets: list[str] | tuple[str, ...] | None = None,
    env_files: list[Path] | None = None,
    include_process_env: bool = True,
    check_cli: bool = False,
    provider_timeout_seconds: int = 12,
    provider_runner: provider_preflight.CommandRunner = provider_preflight.execute_command,
) -> dict[str, Any]:
    normalized_targets = normalize_targets(list(targets or ("all",)))
    resolved_env_files = env_files or [
        Path(".env.production"),
        Path(".env"),
        Path("backend/.env"),
        Path("frontend/.env"),
        Path("contracts/.env"),
    ]
    deploy_payload = deploy_readiness_payload(
        targets=normalized_targets,
        env_files=resolved_env_files,
        include_process_env=include_process_env,
        check_cli=check_cli,
    )
    providers = provider_targets_for(normalized_targets)
    provider_payload: dict[str, Any]
    if providers:
        provider_payload = provider_preflight.run_preflight(
            tuple(providers),
            timeout_seconds=provider_timeout_seconds,
            include_output_preview=False,
            runner=provider_runner,
        )
    else:
        provider_payload = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "ok": True,
            "skipped": True,
            "skip_reason": "no selected targets have provider CLI preflight checks",
            "summary": {
                "provider_count": 0,
                "ready_provider_count": 0,
                "check_count": 0,
                "passed_check_count": 0,
                "failed_check_count": 0,
                "missing_cli_count": 0,
                "auth_context_missing_count": 0,
            },
            "providers": [],
            "failed_checks": [],
        }

    failed_surfaces = []
    if not deploy_payload.get("ok"):
        failed_surfaces.append("deploy_readiness")
    if not provider_payload.get("ok"):
        failed_surfaces.append("provider_preflight")

    deploy_summary = deploy_payload.get("summary") if isinstance(deploy_payload.get("summary"), dict) else {}
    provider_summary = provider_payload.get("summary") if isinstance(provider_payload.get("summary"), dict) else {}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failed_surfaces,
        "targets": normalized_targets,
        "provider_targets": providers,
        "summary": {
            "deploy_failed": deploy_summary.get("failed", 0),
            "deploy_warnings": deploy_summary.get("warnings", 0),
            "provider_ready": provider_summary.get("ready_provider_count", 0),
            "provider_count": provider_summary.get("provider_count", 0),
            "provider_failed_checks": provider_summary.get("failed_check_count", 0),
            "failed_surface_count": len(failed_surfaces),
        },
        "failed_surfaces": failed_surfaces,
        "deploy_readiness": deploy_payload,
        "provider_preflight": provider_payload,
    }


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload, trailing_newline=True)


def print_text_report(payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(f"[external-release-gate] ok={payload.get('ok')}")
    print(
        "[external-release-gate] "
        f"deploy_failed={summary.get('deploy_failed')} "
        f"deploy_warnings={summary.get('deploy_warnings')} "
        f"provider_ready={summary.get('provider_ready')}/{summary.get('provider_count')} "
        f"provider_failed_checks={summary.get('provider_failed_checks')}"
    )
    failed_surfaces = payload.get("failed_surfaces")
    if isinstance(failed_surfaces, list) and failed_surfaces:
        print(f"[external-release-gate] failed_surfaces={', '.join(str(item) for item in failed_surfaces)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeSci external deploy and provider CLI readiness gates.")
    parser.add_argument(
        "--target",
        action="append",
        choices=(*DEFAULT_TARGETS, "all"),
        default=[],
        help="Deployment target to check. Repeatable. Defaults to all.",
    )
    parser.add_argument("--env-file", action="append", default=[], help="Env file to load; repeatable.")
    parser.add_argument("--ignore-process-env", action="store_true")
    parser.add_argument("--check-cli", action="store_true", help="Also check local deployment CLI availability in deploy readiness.")
    parser.add_argument("--provider-timeout", type=int, default=12, help="Timeout per provider CLI command in seconds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--json-out", help="Write machine-readable JSON to a file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    env_files = [Path(path) for path in args.env_file] if args.env_file else None
    payload = run_external_gate(
        targets=tuple(args.target or ("all",)),
        env_files=env_files,
        include_process_env=not args.ignore_process_env,
        check_cli=args.check_cli,
        provider_timeout_seconds=args.provider_timeout,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_text_report(payload)
    if args.json_out:
        write_json_report(args.json_out, payload)
        print(f"[external-release-gate] json written: {args.json_out}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
