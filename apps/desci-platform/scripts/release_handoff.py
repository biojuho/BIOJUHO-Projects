#!/usr/bin/env python3
"""Build a unified DeSci launch handoff from smoke and deploy evidence."""

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

from evidence_io import write_json_atomic

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
    "railway_stripe": ("Stripe", "Paid checkout"),
    "vercel_firebase": ("Firebase + Vercel", "Frontend authentication"),
    "github_gitleaks_license": ("GitHub repository", "Secret scanning"),
}
PRODUCT_ACTION_TO_DEPLOY_CHECKS = {
    "auth": ("railway_auth", "vercel_firebase"),
    "stripe": ("railway_stripe", "railway_frontend_return_url"),
    "cors": ("railway_cors",),
    "rabbitmq": ("railway_queue",),
    "database": ("railway_database",),
    "llm": ("railway_llm",),
    "web3": ("vercel_wallet_contracts", "amoy_rpc", "amoy_private_key", "amoy_explorer"),
}
PRODUCT_ONLY_SURFACE = ("Product runtime", "Manual launch follow-up")


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def extract_launch_handoff(product_payload: dict[str, Any]) -> dict[str, Any]:
    handoff = product_payload.get("launch_handoff")
    if isinstance(handoff, dict):
        return handoff

    launch = next(
        (check for check in _as_list(product_payload.get("checks")) if isinstance(check, dict) and check.get("name") == "launch"),
        None,
    )
    return launch if isinstance(launch, dict) else {}


def _surface_for_check(check: dict[str, Any]) -> tuple[str, str]:
    check_id = str(check.get("id") or "")
    if check_id in SURFACE_BY_CHECK_ID:
        return SURFACE_BY_CHECK_ID[check_id]
    target = str(check.get("target") or "")
    return DEFAULT_SURFACE_BY_TARGET.get(target, ("Deployment", "Unmapped surface"))


def _deploy_checks_by_id(deploy_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for check in _as_list(deploy_payload.get("checks")):
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            continue
        owner, surface = _surface_for_check(check)
        checks[check["id"]] = {
            "id": check["id"],
            "target": check.get("target"),
            "owner": owner,
            "surface": surface,
            "label": check.get("label"),
            "status": check.get("status"),
            "required": check.get("required") is True,
            "keys": _string_list(check.get("keys")),
            "remediation": check.get("remediation") if isinstance(check.get("remediation"), str) else "",
        }
    return checks


def _product_action_report(action: dict[str, Any], deploy_checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    action_id = str(action.get("id") or "").strip()
    mapped_check_ids = PRODUCT_ACTION_TO_DEPLOY_CHECKS.get(action_id, ())
    mapped_checks = [deploy_checks[check_id] for check_id in mapped_check_ids if check_id in deploy_checks]
    deploy_surfaces = mapped_checks

    coverage = "covered" if deploy_surfaces else "product_only"
    if not deploy_surfaces:
        deploy_surfaces = [
            {
                "id": f"product_only_{action_id or 'unknown'}",
                "target": "product",
                "owner": PRODUCT_ONLY_SURFACE[0],
                "surface": PRODUCT_ONLY_SURFACE[1],
                "label": action.get("id") or "product action",
                "status": action.get("status"),
                "required": action.get("required") is True,
                "keys": _string_list(action.get("required_env")),
                "remediation": action.get("remediation") if isinstance(action.get("remediation"), str) else "",
            }
        ]

    return {
        "id": action_id,
        "status": action.get("status"),
        "required": action.get("required") is True,
        "remediation": action.get("remediation") if isinstance(action.get("remediation"), str) else "",
        "required_env": _string_list(action.get("required_env")),
        "coverage": coverage,
        "deploy_surfaces": deploy_surfaces,
    }


def _deploy_only_actions(
    deploy_checks: dict[str, dict[str, Any]],
    product_check_ids: set[str],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for check_id in sorted(deploy_checks):
        check = deploy_checks[check_id]
        if check_id in product_check_ids:
            continue
        if check.get("status") not in {"fail", "warn"}:
            continue
        actions.append(check)
    return actions


def build_handoff(
    product_payload: dict[str, Any],
    deploy_payload: dict[str, Any],
    *,
    sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    launch_handoff = extract_launch_handoff(product_payload)
    launch_actions = [action for action in _as_list(launch_handoff.get("next_actions")) if isinstance(action, dict)]
    deploy_checks = _deploy_checks_by_id(deploy_payload)

    checklist = [_product_action_report(action, deploy_checks) for action in launch_actions]
    product_check_ids = {
        check_id
        for item in checklist
        for check_id in PRODUCT_ACTION_TO_DEPLOY_CHECKS.get(item["id"], ())
        if check_id in deploy_checks
    }
    deploy_only = _deploy_only_actions(deploy_checks, product_check_ids)
    missing_required_coverage = [
        item["id"] for item in checklist if item["required"] and item["coverage"] != "covered"
    ]

    product_ok = product_payload.get("ok") is True
    deploy_ok = deploy_payload.get("ok") is True
    ok = product_ok and deploy_ok and not missing_required_coverage
    release_decision = launch_handoff.get("release_decision") if isinstance(launch_handoff.get("release_decision"), str) else None
    if not ok:
        release_decision = "no-go"

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "release_decision": release_decision or "no-go",
        "strict_ready_ok": product_ok and deploy_ok,
        "product_smoke_ok": product_ok,
        "deploy_readiness_ok": deploy_ok,
        "launch": {
            "release_decision": launch_handoff.get("release_decision"),
            "operator_phase": launch_handoff.get("operator_phase"),
            "readiness_status": launch_handoff.get("readiness_status"),
            "summary": _as_dict(launch_handoff.get("summary")),
            "score": _as_dict(launch_handoff.get("score")),
            "launch_blockers": _string_list(launch_handoff.get("launch_blockers")),
        },
        "coverage": {
            "product_action_count": len(checklist),
            "covered_product_actions": [item["id"] for item in checklist if item["coverage"] == "covered"],
            "product_only_actions": [item["id"] for item in checklist if item["coverage"] == "product_only"],
            "missing_required_coverage": missing_required_coverage,
            "deploy_only_action_count": len(deploy_only),
        },
        "operator_checklist": checklist,
        "deploy_only_actions": deploy_only,
        "failures": _string_list(product_payload.get("failures")),
        "deploy_failed_checks": _string_list(_as_dict(deploy_payload.get("summary")).get("failed_checks")),
        "sources": sources or {},
    }


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload, trailing_newline=True)


def print_report(payload: dict[str, Any]) -> None:
    print("[release-handoff] RELEASE HANDOFF")
    print(f"[release-handoff] decision={payload['release_decision']} ok={payload['ok']}")
    print(
        "[release-handoff] product_smoke_ok="
        f"{payload['product_smoke_ok']} deploy_readiness_ok={payload['deploy_readiness_ok']}"
    )
    print("[release-handoff] PRODUCT ACTION CHECKLIST")
    for item in payload["operator_checklist"]:
        required = "required" if item["required"] else "optional"
        env_text = f" env={', '.join(item['required_env'])}" if item["required_env"] else ""
        print(f"- {item['id']}: {item['status']} {required} coverage={item['coverage']}{env_text}")
        for surface in item["deploy_surfaces"]:
            print(
                f"  - {surface['owner']} / {surface['surface']} :: "
                f"{surface['id']} ({surface['status']}) {surface['remediation']}"
            )
    deploy_only = payload.get("deploy_only_actions") or []
    if deploy_only:
        print("[release-handoff] DEPLOY-ONLY ACTIONS")
        for action in deploy_only:
            env_text = f" env={', '.join(action['keys'])}" if action["keys"] else ""
            print(
                f"- {action['owner']} / {action['surface']} :: "
                f"{action['id']} ({action['status']}) {action['remediation']}{env_text}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DeSci launch handoff evidence from existing smoke reports.")
    parser.add_argument("--product-smoke-json", required=True, help="Path to product_smoke.py JSON evidence.")
    parser.add_argument("--deploy-readiness-json", required=True, help="Path to deploy_readiness.py JSON evidence.")
    parser.add_argument("--json", action="store_true", help="Print the handoff as JSON.")
    parser.add_argument("--json-out", help="Write the handoff JSON to a file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_path = Path(args.product_smoke_json)
    deploy_path = Path(args.deploy_readiness_json)
    payload = build_handoff(
        load_json(product_path),
        load_json(deploy_path),
        sources={
            "product_smoke_json": str(product_path),
            "deploy_readiness_json": str(deploy_path),
        },
    )

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_report(payload)
    if args.json_out:
        output_path = write_json_report(args.json_out, payload)
        print(f"[release-handoff] json written: {output_path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
