#!/usr/bin/env python3
"""Build an operator handoff from DeSci external release gate evidence."""

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

import release_handoff
from evidence_io import write_json_atomic

DEFAULT_EXTERNAL_GATE_JSON = Path("var/external-release-gate-provider-2026-07-04.json")
DEFAULT_PROVIDER = "operator"


def load_external_gate_payload(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path} must be schema_version=1 external release gate evidence")
    if "deploy_readiness" not in payload or "provider_preflight" not in payload:
        raise ValueError(f"{path} is missing external release gate child evidence")
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _provider_for_target(target: str) -> str:
    normalized = target.strip().lower()
    return normalized if normalized in release_handoff.PROVIDER_TEMPLATE_FILENAMES else DEFAULT_PROVIDER


def _provider_label(provider: str) -> str:
    return release_handoff.PROVIDER_LABELS.get(provider, provider.title())


def _provider_guidance(provider: str) -> dict[str, Any]:
    if provider in release_handoff.PROVIDER_TEMPLATE_FILENAMES:
        return release_handoff.provider_apply_guidance(provider)
    return {
        "docs_url": "",
        "preflight_commands": [],
        "apply_steps": ["Resolve the listed external launch blockers, then regenerate the external gate handoff."],
    }


def deploy_surface_actions(deploy_payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for surface in _as_list(deploy_payload.get("owner_surface_summary")):
        if not isinstance(surface, dict):
            continue
        failed = int(surface.get("failed") or 0)
        warnings = int(surface.get("warnings") or 0)
        if failed == 0 and warnings == 0:
            continue
        action_items = [item for item in _as_list(surface.get("actions")) if isinstance(item, dict)]
        target_values = _dedupe(
            [str(item.get("target") or "").strip().lower() for item in action_items if item.get("target")]
        )
        provider = _provider_for_target(target_values[0]) if len(target_values) == 1 else DEFAULT_PROVIDER
        actions.append(
            {
                "source": "deploy_readiness",
                "provider": provider,
                "label": _provider_label(provider),
                "owner": str(surface.get("owner") or "Deployment"),
                "surface": str(surface.get("surface") or "Unmapped surface"),
                "failed": failed,
                "warnings": warnings,
                "failed_checks": _string_list(surface.get("failed_checks")),
                "warning_checks": _string_list(surface.get("warning_checks")),
                "required_env": _string_list(surface.get("required_env")),
                "actions": [
                    {
                        "id": item.get("id"),
                        "target": item.get("target"),
                        "status": item.get("status"),
                        "required": item.get("required") is True,
                        "keys": _string_list(item.get("keys")),
                        "remediation": item.get("remediation") if isinstance(item.get("remediation"), str) else "",
                    }
                    for item in action_items
                    if item.get("status") in {"fail", "warn"}
                ],
            }
        )
    return actions


def provider_preflight_actions(provider_payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for check in _as_list(provider_payload.get("failed_checks")):
        if not isinstance(check, dict):
            continue
        provider = str(check.get("provider") or DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
        group = grouped.setdefault(
            provider,
            {
                "source": "provider_preflight",
                "provider": provider,
                "label": _provider_label(provider),
                "owner": _provider_label(provider),
                "surface": "Provider CLI and authentication",
                "failed": 0,
                "warnings": 0,
                "failure_reasons": [],
                "commands": [],
                "actions": [],
            },
        )
        group["failed"] += 1
        failure_reason = str(check.get("failure_reason") or "unknown")
        command = str(check.get("command") or "").strip()
        if failure_reason not in group["failure_reasons"]:
            group["failure_reasons"].append(failure_reason)
        if command and command not in group["commands"]:
            group["commands"].append(command)
        group["actions"].append(
            {
                "id": check.get("id"),
                "command": command,
                "failure_reason": failure_reason,
            }
        )
    return [grouped[provider] for provider in sorted(grouped)]


def provider_rollup(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for action in actions:
        provider = str(action.get("provider") or DEFAULT_PROVIDER)
        group = grouped.setdefault(
            provider,
            {
                "provider": provider,
                "label": _provider_label(provider),
                "failed": 0,
                "warnings": 0,
                "required_env": [],
                "failure_reasons": [],
                "commands": [],
                "action_count": 0,
                "apply_guidance": _provider_guidance(provider),
            },
        )
        group["failed"] += int(action.get("failed") or 0)
        group["warnings"] += int(action.get("warnings") or 0)
        group["action_count"] += 1
        for key in _string_list(action.get("required_env")):
            if key not in group["required_env"]:
                group["required_env"].append(key)
        for reason in _string_list(action.get("failure_reasons")):
            if reason not in group["failure_reasons"]:
                group["failure_reasons"].append(reason)
        for command in _string_list(action.get("commands")):
            if command not in group["commands"]:
                group["commands"].append(command)
    return [grouped[provider] for provider in sorted(grouped)]


def build_handoff_payload(gate_payload: dict[str, Any], *, evidence_path: str | Path) -> dict[str, Any]:
    deploy_payload = _as_dict(gate_payload.get("deploy_readiness"))
    provider_payload = _as_dict(gate_payload.get("provider_preflight"))
    actions = [*deploy_surface_actions(deploy_payload), *provider_preflight_actions(provider_payload)]
    gate_summary = _as_dict(gate_payload.get("summary"))
    ok = gate_payload.get("ok") is True
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "release_decision": "go" if ok else "no-go",
        "operator_phase": "external_launch_ready" if ok else "external_launch_blocked",
        "external_gate_json": str(evidence_path),
        "targets": _string_list(gate_payload.get("targets")),
        "provider_targets": _string_list(gate_payload.get("provider_targets")),
        "failed_surfaces": _string_list(gate_payload.get("failed_surfaces")),
        "summary": {
            "deploy_failed": int(gate_summary.get("deploy_failed") or 0),
            "deploy_warnings": int(gate_summary.get("deploy_warnings") or 0),
            "provider_ready": int(gate_summary.get("provider_ready") or 0),
            "provider_count": int(gate_summary.get("provider_count") or 0),
            "provider_failed_checks": int(gate_summary.get("provider_failed_checks") or 0),
            "failed_surface_count": int(gate_summary.get("failed_surface_count") or 0),
            "next_action_count": len(actions),
        },
        "next_actions": actions,
        "provider_rollup": provider_rollup(actions),
    }


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload, trailing_newline=True)


def _markdown_values(values: Any) -> str:
    items = _string_list(values)
    return ", ".join(f"`{item}`" for item in items) if items else "`none`"


def _markdown_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "unknown"
    return str(value)


def _provider_actions_with_env(payload: dict[str, Any], provider: str) -> list[dict[str, Any]]:
    provider_key = provider.strip().lower()
    actions: list[dict[str, Any]] = []
    for action in _as_list(payload.get("next_actions")):
        if not isinstance(action, dict):
            continue
        if action.get("provider") != provider_key:
            continue
        if not _string_list(action.get("required_env")):
            continue
        actions.append(action)
    return actions


def _provider_template_names(payload: dict[str, Any]) -> list[str]:
    providers = {
        str(action.get("provider") or "").strip().lower()
        for action in _as_list(payload.get("next_actions"))
        if isinstance(action, dict) and _string_list(action.get("required_env"))
    }
    return sorted(provider for provider in providers if provider)


def render_provider_env_template(payload: dict[str, Any], provider: str) -> str:
    provider_key = provider.strip().lower()
    label = _provider_label(provider_key)
    lines = [
        "# Generated by scripts/external_gate_handoff.py.",
        "# Fill values in the target provider; do not commit populated secrets.",
        f"# Provider: {label}",
        f"# Release decision: {_markdown_scalar(payload.get('release_decision'))}",
        f"# External gate evidence: {_markdown_scalar(payload.get('external_gate_json'))}",
    ]
    seen_keys: set[str] = set()
    for action in _provider_actions_with_env(payload, provider_key):
        keys = [key for key in _string_list(action.get("required_env")) if key not in seen_keys]
        if not keys:
            continue
        if lines and lines[-1]:
            lines.append("")
        lines.append(f"# {action.get('owner') or label} / {action.get('surface') or 'Unmapped surface'}")
        status = f"failed={_markdown_scalar(action.get('failed', 0))} warnings={_markdown_scalar(action.get('warnings', 0))}"
        lines.append(f"# {action.get('source')}: {status}")
        for item in _as_list(action.get("actions")):
            if not isinstance(item, dict):
                continue
            remediation = item.get("remediation") if isinstance(item.get("remediation"), str) else ""
            if remediation:
                lines.append(f"# {item.get('id')}: {remediation}")
        for key in keys:
            lines.append(f"{key}=")
            seen_keys.add(key)
    return "\n".join(lines).rstrip() + "\n"


def write_text_report(path: str | Path, body: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(output_path)
    return output_path


def write_provider_templates(directory: str | Path, payload: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for provider in _provider_template_names(payload):
        filename = release_handoff.PROVIDER_TEMPLATE_FILENAMES.get(provider, f"{provider}.env")
        written[provider] = write_text_report(output_dir / filename, render_provider_env_template(payload, provider))
    return written


def render_markdown_report(payload: dict[str, Any]) -> str:
    summary = _as_dict(payload.get("summary"))
    lines = [
        "# DeSci External Gate Handoff",
        "",
        "## Decision",
        f"- Release decision: `{_markdown_scalar(payload.get('release_decision'))}`",
        f"- Overall ok: `{_markdown_scalar(payload.get('ok'))}`",
        f"- Operator phase: `{_markdown_scalar(payload.get('operator_phase'))}`",
        f"- Failed surfaces: {_markdown_values(payload.get('failed_surfaces'))}",
        f"- Evidence: `{_markdown_scalar(payload.get('external_gate_json'))}`",
        "",
        "## Summary",
        f"- Deploy failed: `{_markdown_scalar(summary.get('deploy_failed', 0))}`",
        f"- Deploy warnings: `{_markdown_scalar(summary.get('deploy_warnings', 0))}`",
        f"- Provider ready: `{_markdown_scalar(summary.get('provider_ready', 0))}`/"
        f"`{_markdown_scalar(summary.get('provider_count', 0))}`",
        f"- Provider failed checks: `{_markdown_scalar(summary.get('provider_failed_checks', 0))}`",
        f"- Next actions: `{_markdown_scalar(summary.get('next_action_count', 0))}`",
        "",
        "## Provider Rollup",
    ]
    rollups = [item for item in _as_list(payload.get("provider_rollup")) if isinstance(item, dict)]
    if not rollups:
        lines.append("- None.")
    for item in rollups:
        lines.append(
            f"- {item.get('label')}: failed=`{_markdown_scalar(item.get('failed', 0))}`, "
            f"warnings=`{_markdown_scalar(item.get('warnings', 0))}`, "
            f"env={_markdown_values(item.get('required_env'))}, "
            f"reasons={_markdown_values(item.get('failure_reasons'))}"
        )
    lines.extend(["", "## Provider Apply Guidance"])
    if not rollups:
        lines.append("- None.")
    for item in rollups:
        guidance = _as_dict(item.get("apply_guidance"))
        lines.append(f"### {item.get('label')}")
        docs_url = guidance.get("docs_url") if isinstance(guidance.get("docs_url"), str) else ""
        if docs_url:
            lines.append(f"- Docs: {docs_url}")
        lines.append(f"- Preflight commands: {_markdown_values(guidance.get('preflight_commands'))}")
        steps = _string_list(guidance.get("apply_steps"))
        if steps:
            lines.append("- Apply steps:")
            for step in steps:
                lines.append(f"  - {step}")
    lines.extend(["", "## Next Actions"])
    actions = [item for item in _as_list(payload.get("next_actions")) if isinstance(item, dict)]
    if not actions:
        lines.append("- None.")
    for item in actions:
        failed_checks = _markdown_values(item.get("failed_checks"))
        warning_checks = _markdown_values(item.get("warning_checks"))
        reasons = _markdown_values(item.get("failure_reasons"))
        commands = _markdown_values(item.get("commands"))
        lines.append(
            f"- {item.get('label')} / {item.get('surface')}: "
            f"source=`{item.get('source')}`, failed=`{_markdown_scalar(item.get('failed', 0))}`, "
            f"warnings=`{_markdown_scalar(item.get('warnings', 0))}`, "
            f"checks={failed_checks}, warnings={warning_checks}, reasons={reasons}, commands={commands}, "
            f"env={_markdown_values(item.get('required_env'))}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_text_report(path, render_markdown_report(payload))


def print_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[external-gate-handoff] decision={payload['release_decision']} ok={payload['ok']}")
    print(
        "[external-gate-handoff] "
        f"deploy_failed={summary.get('deploy_failed')} "
        f"deploy_warnings={summary.get('deploy_warnings')} "
        f"provider_ready={summary.get('provider_ready')}/{summary.get('provider_count')} "
        f"provider_failed_checks={summary.get('provider_failed_checks')} "
        f"next_actions={summary.get('next_action_count')}"
    )
    if payload.get("failed_surfaces"):
        print(f"[external-gate-handoff] failed_surfaces={', '.join(payload['failed_surfaces'])}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DeSci external gate operator handoff.")
    parser.add_argument(
        "--external-gate-json",
        default=str(DEFAULT_EXTERNAL_GATE_JSON),
        help="Path to external_release_gate.py JSON evidence.",
    )
    parser.add_argument("--json", action="store_true", help="Print the handoff as JSON.")
    parser.add_argument("--json-out", help="Write handoff JSON evidence.")
    parser.add_argument("--markdown-out", help="Write a human-readable handoff packet.")
    parser.add_argument("--provider-template-dir", help="Write no-secret env templates split by provider target.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gate_path = Path(args.external_gate_json)
    payload = build_handoff_payload(load_external_gate_payload(gate_path), evidence_path=gate_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_report(payload)
    if args.json_out:
        output_path = write_json_report(args.json_out, payload)
        print(f"[external-gate-handoff] json written: {output_path}")
    if args.markdown_out:
        markdown_path = write_markdown_report(args.markdown_out, payload)
        print(f"[external-gate-handoff] markdown written: {markdown_path}")
    if args.provider_template_dir:
        provider_paths = write_provider_templates(args.provider_template_dir, payload)
        for provider, path in provider_paths.items():
            print(f"[external-gate-handoff] provider template written: {provider}={path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
