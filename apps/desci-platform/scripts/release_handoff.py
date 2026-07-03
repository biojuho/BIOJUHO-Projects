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
    "railway_grobid": ("GROBID", "PDF parsing"),
    "railway_ipfs": ("Pinata/IPFS", "Public asset minting"),
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
    "grobid": ("railway_grobid",),
    "ipfs": ("railway_ipfs",),
    "llm": ("railway_llm",),
    "web3": ("vercel_wallet_contracts", "amoy_rpc", "amoy_private_key", "amoy_explorer"),
}
PRODUCT_ONLY_SURFACE = ("Product runtime", "Manual launch follow-up")
PROVIDER_TEMPLATE_FILENAMES = {
    "railway": "railway.env",
    "vercel": "vercel.env",
    "github": "github.env",
    "amoy": "amoy.env",
    "product": "product.env",
}
PROVIDER_LABELS = {
    "railway": "Railway",
    "vercel": "Vercel",
    "github": "GitHub",
    "amoy": "Polygon Amoy",
    "product": "Product runtime",
}


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
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


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


def write_text_report(path: str | Path, body: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(output_path)
    return output_path


def _append_env_template_group(
    lines: list[str],
    seen_keys: set[str],
    *,
    owner: str,
    surface: str,
    action_id: str,
    status: str,
    keys: list[str],
    remediation: str,
) -> None:
    unresolved_keys = [key for key in keys if key not in seen_keys]
    if not unresolved_keys:
        return
    if lines and lines[-1]:
        lines.append("")
    lines.append(f"# {owner} / {surface}")
    detail = f"# {action_id} ({status})"
    if remediation:
        detail = f"{detail}: {remediation}"
    lines.append(detail)
    for key in unresolved_keys:
        lines.append(f"{key}=")
        seen_keys.add(key)


def unresolved_surface_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in payload.get("operator_checklist") or []:
        if not isinstance(item, dict):
            continue
        for surface in item.get("deploy_surfaces") or []:
            if not isinstance(surface, dict) or surface.get("status") not in {"fail", "warn"}:
                continue
            actions.append(surface)
    for action in payload.get("deploy_only_actions") or []:
        if isinstance(action, dict):
            actions.append(action)
    return actions


def _append_unresolved_actions(lines: list[str], actions: list[dict[str, Any]], seen_keys: set[str]) -> None:
    for action in actions:
        _append_env_template_group(
            lines,
            seen_keys,
            owner=str(action.get("owner") or "Deployment"),
            surface=str(action.get("surface") or "Unmapped surface"),
            action_id=str(action.get("id") or "unknown"),
            status=str(action.get("status") or "unknown"),
            keys=_string_list(action.get("keys")),
            remediation=action.get("remediation") if isinstance(action.get("remediation"), str) else "",
        )


def render_env_template(payload: dict[str, Any]) -> str:
    lines = [
        "# Generated by scripts/release_handoff.py.",
        "# Fill values in your secret manager or deployment provider; do not commit populated secrets.",
        f"# Release decision: {payload.get('release_decision')}",
    ]
    _append_unresolved_actions(lines, unresolved_surface_actions(payload), set())
    return "\n".join(lines).rstrip() + "\n"


def write_env_template(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_text_report(path, render_env_template(payload))


def provider_for_action(action: dict[str, Any]) -> str:
    target = str(action.get("target") or "").strip().lower()
    return target if target in PROVIDER_TEMPLATE_FILENAMES else "product"


def provider_actions(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for action in unresolved_surface_actions(payload):
        if not _string_list(action.get("keys")):
            continue
        provider = provider_for_action(action)
        grouped.setdefault(provider, []).append(action)
    return {provider: grouped[provider] for provider in sorted(grouped)}


def render_provider_env_template(payload: dict[str, Any], provider: str) -> str:
    provider_key = provider.strip().lower()
    actions = provider_actions(payload).get(provider_key, [])
    lines = [
        "# Generated by scripts/release_handoff.py.",
        "# Fill values in the target provider; do not commit populated secrets.",
        f"# Provider: {PROVIDER_LABELS.get(provider_key, provider_key or 'unknown')}",
        f"# Release decision: {payload.get('release_decision')}",
    ]
    _append_unresolved_actions(lines, actions, set())
    return "\n".join(lines).rstrip() + "\n"


def write_provider_templates(directory: str | Path, payload: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for provider, actions in provider_actions(payload).items():
        if not actions:
            continue
        filename = PROVIDER_TEMPLATE_FILENAMES.get(provider, f"{provider}.env")
        path = write_text_report(output_dir / filename, render_provider_env_template(payload, provider))
        written[provider] = path
    return written


def _markdown_values(values: Any) -> str:
    items = _string_list(values)
    return ", ".join(f"`{item}`" for item in items) if items else "`none`"


def _markdown_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "unknown"
    return str(value)


def render_markdown_report(payload: dict[str, Any]) -> str:
    launch = _as_dict(payload.get("launch"))
    coverage = _as_dict(payload.get("coverage"))
    lines = [
        "# DeSci Release Handoff",
        "",
        "## Decision",
        f"- Release decision: `{_markdown_scalar(payload.get('release_decision'))}`",
        f"- Overall ok: `{_markdown_scalar(payload.get('ok'))}`",
        f"- Product smoke ok: `{_markdown_scalar(payload.get('product_smoke_ok'))}`",
        f"- Deploy readiness ok: `{_markdown_scalar(payload.get('deploy_readiness_ok'))}`",
        f"- Operator phase: `{_markdown_scalar(launch.get('operator_phase'))}`",
        f"- Readiness status: `{_markdown_scalar(launch.get('readiness_status'))}`",
        f"- Launch blockers: {_markdown_values(launch.get('launch_blockers'))}",
        "",
        "## Coverage",
        f"- Product actions: `{_markdown_scalar(coverage.get('product_action_count', 0))}`",
        f"- Covered product actions: {_markdown_values(coverage.get('covered_product_actions'))}",
        f"- Product-only actions: {_markdown_values(coverage.get('product_only_actions'))}",
        f"- Missing required coverage: {_markdown_values(coverage.get('missing_required_coverage'))}",
        f"- Deploy-only action count: `{_markdown_scalar(coverage.get('deploy_only_action_count', 0))}`",
        "",
        "## Product Action Checklist",
    ]

    checklist = [item for item in payload.get("operator_checklist") or [] if isinstance(item, dict)]
    if not checklist:
        lines.append("- None.")
    for item in checklist:
        lines.extend(
            [
                f"### {item.get('id')}",
                f"- Status: `{_markdown_scalar(item.get('status'))}`",
                f"- Required: `{_markdown_scalar(item.get('required'))}`",
                f"- Coverage: `{_markdown_scalar(item.get('coverage'))}`",
                f"- Required env: {_markdown_values(item.get('required_env'))}",
            ]
        )
        remediation = item.get("remediation")
        if isinstance(remediation, str) and remediation:
            lines.append(f"- Product remediation: {remediation}")
        surfaces = [surface for surface in item.get("deploy_surfaces") or [] if isinstance(surface, dict)]
        if surfaces:
            lines.append("- Deploy surfaces:")
            for surface in surfaces:
                keys = _markdown_values(surface.get("keys"))
                remediation = surface.get("remediation")
                suffix = f" - {remediation}" if isinstance(remediation, str) and remediation else ""
                lines.append(
                    f"  - {surface.get('owner')} / {surface.get('surface')}: "
                    f"`{_markdown_scalar(surface.get('id'))}` `{_markdown_scalar(surface.get('status'))}` env={keys}{suffix}"
                )
        lines.append("")

    lines.append("## Deploy-Only Actions")
    deploy_only = [action for action in payload.get("deploy_only_actions") or [] if isinstance(action, dict)]
    if not deploy_only:
        lines.append("- None.")
    for action in deploy_only:
        keys = _markdown_values(action.get("keys"))
        remediation = action.get("remediation")
        suffix = f" - {remediation}" if isinstance(remediation, str) and remediation else ""
        lines.append(
            f"- {action.get('owner')} / {action.get('surface')}: "
            f"`{_markdown_scalar(action.get('id'))}` `{_markdown_scalar(action.get('status'))}` env={keys}{suffix}"
        )

    lines.extend(["", "## Evidence Sources"])
    sources = _as_dict(payload.get("sources"))
    if not sources:
        lines.append("- None.")
    for key in sorted(sources):
        lines.append(f"- {key}: `{sources[key]}`")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_text_report(path, render_markdown_report(payload))


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
    parser.add_argument("--env-template-out", help="Write a no-secret env template for unresolved handoff actions.")
    parser.add_argument("--markdown-out", help="Write a human-readable Markdown release handoff packet.")
    parser.add_argument("--provider-template-dir", help="Write no-secret env templates split by provider target.")
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
    if args.env_template_out:
        template_path = write_env_template(args.env_template_out, payload)
        print(f"[release-handoff] env template written: {template_path}")
    if args.markdown_out:
        markdown_path = write_markdown_report(args.markdown_out, payload)
        print(f"[release-handoff] markdown written: {markdown_path}")
    if args.provider_template_dir:
        provider_paths = write_provider_templates(args.provider_template_dir, payload)
        for provider, path in provider_paths.items():
            print(f"[release-handoff] provider template written: {provider}={path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
