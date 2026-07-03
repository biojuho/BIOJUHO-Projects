#!/usr/bin/env python3
"""Build an operator handoff from DeSci external release gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_handoff
from evidence_io import write_json_atomic
from post_apply_evidence_gate import secret_marker_names_in_text, verify_promotion_receipt

DEFAULT_EXTERNAL_GATE_JSON = Path("var/external-release-gate-provider-2026-07-04.json")
DEFAULT_PROVIDER = "operator"
DEFAULT_PROVIDER_APPLY_PLAN_JSON = Path("var/external-gate-provider-apply-plan.json")
PROVIDER_APPLY_PLAN_VERIFY_CONDITION = "provider_apply_plan_verification.ok=true"
PROVIDER_APPLY_PLAN_READY_CONDITION = (
    "provider_apply_plan_verification.ok=true and provider_apply_plan.ready_to_apply=true"
)
PROVIDER_APPLY_RESULTS_CONDITION = (
    "provider_apply_results_verification.ok=true and provider_apply_results.all_commands_succeeded=true"
)
PROVIDER_APPLY_WORKFLOW_CONDITION = (
    "provider_apply_plan_verification.ready_to_apply=true and "
    "provider_apply_results_verification.ok=true and "
    "provider_apply_results.all_commands_succeeded=true and "
    "post_apply_promotion_receipt.ok=true"
)


def load_external_gate_payload(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path} must be schema_version=1 external release gate evidence")
    if "deploy_readiness" not in payload or "provider_preflight" not in payload:
        raise ValueError(f"{path} is missing external release gate child evidence")
    return payload


def load_provider_apply_plan(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_provider_apply_results(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
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
                "template_filename": release_handoff.PROVIDER_TEMPLATE_FILENAMES.get(provider, f"{provider}.env"),
                "has_env_template": False,
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
                group["has_env_template"] = True
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


def write_provider_templates(
    directory: str | Path,
    payload: dict[str, Any],
    *,
    overwrite: bool = True,
) -> dict[str, Path]:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for provider in _provider_template_names(payload):
        filename = release_handoff.PROVIDER_TEMPLATE_FILENAMES.get(provider, f"{provider}.env")
        path = output_dir / filename
        if overwrite or not path.exists():
            write_text_report(path, render_provider_env_template(payload, provider))
        written[provider] = path
    return written


def _env_template_audit(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    keys: list[str] = []
    populated_keys: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key not in keys:
            keys.append(key)
        if value.strip() and key not in populated_keys:
            populated_keys.append(key)
    return {
        "path": str(path),
        "bytes": len(body.encode("utf-8")),
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "env_keys": keys,
        "env_key_count": len(keys),
        "populated_key_count": len(populated_keys),
        "populated_keys": populated_keys,
    }


def provider_template_index_payload(payload: dict[str, Any], provider_paths: dict[str, Path]) -> dict[str, Any]:
    providers: list[dict[str, Any]] = []
    rollup_by_provider = {
        str(item.get("provider") or ""): item
        for item in _as_list(payload.get("provider_rollup"))
        if isinstance(item, dict)
    }
    for provider in sorted(provider_paths):
        path = provider_paths[provider]
        audit = _env_template_audit(path)
        rollup = _as_dict(rollup_by_provider.get(provider))
        providers.append(
            {
                "provider": provider,
                "label": _provider_label(provider),
                "template_filename": rollup.get("template_filename")
                or release_handoff.PROVIDER_TEMPLATE_FILENAMES.get(provider, f"{provider}.env"),
                "has_env_template": rollup.get("has_env_template") is True,
                **audit,
            }
        )
    populated_total = sum(int(item.get("populated_key_count") or 0) for item in providers)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": populated_total == 0,
        "safe_to_commit": populated_total == 0,
        "release_decision": payload.get("release_decision"),
        "external_gate_json": payload.get("external_gate_json"),
        "provider_template_count": len(providers),
        "populated_key_count": populated_total,
        "providers": providers,
    }


def write_provider_template_index(
    path: str | Path,
    payload: dict[str, Any],
    provider_paths: dict[str, Path],
) -> Path:
    return write_json_report(path, provider_template_index_payload(payload, provider_paths))


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_path_with_suffix(path: str | Path, suffix: str) -> str:
    output_path = Path(path)
    file_suffix = output_path.suffix or ".json"
    return str(output_path.with_name(f"{output_path.stem}{suffix}{file_suffix}"))


def _same_path_text(left: str | Path, right: str | Path) -> bool:
    return Path(str(left)) == Path(str(right))


def _metadata_path(metadata: dict[str, Any], key: str, fallback: str | Path) -> tuple[str, str]:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value, "plan_metadata"
    return str(fallback), "fallback"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _provider_apply_commands(provider: str, template_path: str, keys: list[str]) -> list[dict[str, Any]]:
    if provider == "github":
        return [
            {
                "id": "github_secret_env_file",
                "command": f"gh secret set --env-file {template_path}",
                "powershell_command": f"gh secret set --env-file {_powershell_single_quoted(template_path)}",
                "posix_command": f"gh secret set --env-file {template_path}",
                "stdin_required": False,
                "value_placeholder": "",
            }
        ]
    if provider == "railway":
        return [
            {
                "id": f"railway_variable_set_{key.lower()}",
                "command": f"railway variable set {key} --stdin",
                "powershell_command": (
                    f"Get-Content -Raw {_powershell_single_quoted(f'<private-values/{key}.txt>')} "
                    f"| railway variable set {key} --stdin"
                ),
                "posix_command": f"railway variable set {key} --stdin < <private-values/{key}.txt>",
                "stdin_required": True,
                "value_placeholder": "<private-value-on-stdin>",
            }
            for key in keys
        ]
    if provider == "vercel":
        return [
            {
                "id": f"vercel_env_add_{key.lower()}",
                "command": f"vercel env add {key} production < <private-value-file>",
                "powershell_command": (
                    f"Get-Content -Raw {_powershell_single_quoted(f'<private-values/{key}.txt>')} "
                    f"| vercel env add {key} production"
                ),
                "posix_command": f"vercel env add {key} production < <private-values/{key}.txt>",
                "stdin_required": True,
                "value_placeholder": "<private-value-file>",
            }
            for key in keys
        ]
    return []


def _provider_apply_operator_status(index: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
    provider_count = len(providers)
    ready_provider_count = sum(1 for provider in providers if provider.get("ready_to_apply") is True)
    blocked_provider_count = max(provider_count - ready_provider_count, 0)
    populated_key_count = int(index.get("populated_key_count") or 0)
    ready_to_apply = provider_count > 0 and blocked_provider_count == 0
    if provider_count == 0:
        stage = "no_provider_templates"
        next_required_action = "Regenerate the handoff with --provider-template-dir after external gate evidence exists."
    elif not ready_to_apply:
        stage = "fill_provider_templates"
        next_required_action = (
            "Fill blank provider templates in a private local directory, then regenerate this apply plan with "
            "--preserve-provider-templates."
        )
    else:
        stage = "apply_provider_values"
        next_required_action = (
            "Run the provider apply commands, then rerun scripts/external_release_gate.py with the filled "
            "provider template directory."
        )
    return {
        "stage": stage,
        "ready_to_apply": ready_to_apply,
        "ready_provider_count": ready_provider_count,
        "blocked_provider_count": blocked_provider_count,
        "provider_templates_safe_to_commit": index.get("safe_to_commit") is True,
        "apply_plan_safe_to_commit": True,
        "private_template_values_present": populated_key_count > 0,
        "completion_marker": "external_release_gate.ok=true",
        "next_required_action": next_required_action,
    }


def _provider_apply_plan_verification(plan_path: str | Path) -> dict[str, Any]:
    verify_json_out = _json_path_with_suffix(plan_path, "-verify")
    require_ready_json_out = _json_path_with_suffix(plan_path, "-require-ready")
    plan_json = str(plan_path)
    return {
        "success_condition": PROVIDER_APPLY_PLAN_VERIFY_CONDITION,
        "ready_success_condition": PROVIDER_APPLY_PLAN_READY_CONDITION,
        "provider_apply_plan_json": plan_json,
        "verify_json_out": verify_json_out,
        "require_ready_json_out": require_ready_json_out,
        "verify_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-plan {plan_json} --json-out {verify_json_out}"
        ),
        "require_ready_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-plan {plan_json} --require-ready-to-apply "
            f"--json-out {require_ready_json_out}"
        ),
    }


def _provider_apply_results_verification(plan_path: str | Path) -> dict[str, Any]:
    results_json = _json_path_with_suffix(plan_path, "-results")
    verify_json_out = _json_path_with_suffix(plan_path, "-results-verify")
    template_json_out = _json_path_with_suffix(plan_path, "-results-template")
    dry_run_json_out = _json_path_with_suffix(plan_path, "-results-dry-run")
    plan_json = str(plan_path)
    return {
        "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
        "provider_apply_plan_json": plan_json,
        "provider_apply_results_json": results_json,
        "template_json_out": template_json_out,
        "dry_run_json_out": dry_run_json_out,
        "verify_json_out": verify_json_out,
        "template_command": (
            "python scripts/external_gate_handoff.py "
            f"--provider-apply-results-template-from-plan {plan_json} --json-out {template_json_out}"
        ),
        "dry_run_command": (
            "python scripts/external_gate_handoff.py "
            f"--record-provider-apply-results-from-plan {plan_json} --json-out {dry_run_json_out}"
        ),
        "execute_command": (
            "python scripts/external_gate_handoff.py "
            f"--record-provider-apply-results-from-plan {plan_json} --execute-provider-apply-commands "
            f"--json-out {results_json}"
        ),
        "verify_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-results {results_json} --provider-apply-plan {plan_json} "
            f"--json-out {verify_json_out}"
        ),
    }


def _provider_apply_workflow_verification(plan_path: str | Path) -> dict[str, Any]:
    plan_json = str(plan_path)
    results_json = _json_path_with_suffix(plan_path, "-results")
    workflow_json_out = _json_path_with_suffix(plan_path, "-workflow-verify")
    promotion_receipt_json = "var/post-apply-promotion-receipt.json"
    return {
        "success_condition": PROVIDER_APPLY_WORKFLOW_CONDITION,
        "provider_apply_plan_json": plan_json,
        "provider_apply_results_json": results_json,
        "promotion_receipt_json": promotion_receipt_json,
        "verify_json_out": workflow_json_out,
        "default_verify_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-workflow {plan_json} --json-out {workflow_json_out}"
        ),
        "default_require_go_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-workflow {plan_json} "
            f"--require-promotion-go --json-out {workflow_json_out}"
        ),
        "verify_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-workflow {plan_json} "
            f"--provider-apply-results {results_json} "
            f"--promotion-receipt {promotion_receipt_json} "
            f"--json-out {workflow_json_out}"
        ),
        "require_go_command": (
            "python scripts/external_gate_handoff.py "
            f"--verify-provider-apply-workflow {plan_json} "
            f"--provider-apply-results {results_json} "
            f"--promotion-receipt {promotion_receipt_json} "
            f"--require-promotion-go --json-out {workflow_json_out}"
        ),
    }


def _post_apply_verify_command(template_dir: str, provider: str) -> str:
    json_out = f"var/external-release-gate-post-apply-{provider}.json"
    return (
        "python scripts/external_release_gate.py "
        f"--provider-template-dir {template_dir} --target {provider} --json-out {json_out}"
    )


def _post_apply_completion_evidence(template_dir: str, providers: list[dict[str, Any]]) -> dict[str, Any]:
    provider_keys = [
        str(provider.get("provider") or "")
        for provider in providers
        if str(provider.get("provider") or "") in {"amoy", "github", "railway", "vercel"}
    ]
    aggregate_json_out = "var/external-release-gate-post-apply-all.json"
    aggregate_command = (
        "python scripts/external_release_gate.py "
        f"--provider-template-dir {template_dir} --target all --json-out {aggregate_json_out}"
    )
    promotion_gate_json_out = "var/post-apply-evidence-gate.json"
    promotion_manifest_json_out = "var/post-apply-evidence-manifest.json"
    promotion_manifest_verify_json_out = "var/post-apply-evidence-manifest-verify.json"
    promotion_receipt_json_out = "var/post-apply-promotion-receipt.json"
    promotion_receipt_verify_json_out = "var/post-apply-promotion-receipt-verify.json"
    promotion_receipt_require_go_json_out = "var/post-apply-promotion-receipt-require-go.json"
    promotion_gate_command = (
        "python scripts/post_apply_evidence_gate.py "
        f"--external-gate-json {aggregate_json_out} "
        f"--json-out {promotion_gate_json_out} "
        f"--manifest-out {promotion_manifest_json_out} "
        f"--verify-manifest-out {promotion_manifest_verify_json_out} "
        f"--promotion-receipt-out {promotion_receipt_json_out}"
    )
    promotion_manifest_verify_command = (
        "python scripts/post_apply_evidence_gate.py "
        f"--verify-manifest {promotion_manifest_json_out} "
        f"--json-out {promotion_manifest_verify_json_out}"
    )
    promotion_receipt_verify_command = (
        "python scripts/post_apply_evidence_gate.py "
        f"--verify-promotion-receipt {promotion_receipt_json_out} "
        f"--json-out {promotion_receipt_verify_json_out}"
    )
    promotion_receipt_require_go_command = (
        "python scripts/post_apply_evidence_gate.py "
        f"--verify-promotion-receipt {promotion_receipt_json_out} "
        f"--require-go --json-out {promotion_receipt_require_go_json_out}"
    )
    return {
        "required": bool(template_dir and provider_keys),
        "success_condition": (
            "post_apply_evidence_gate.ok=true and evidence_manifest_verification.ok=true and "
            "post_apply_promotion_receipt.ok=true"
        ),
        "aggregate_json_out": aggregate_json_out if template_dir else "",
        "aggregate_command": aggregate_command if template_dir else "",
        "promotion_gate_json_out": promotion_gate_json_out if template_dir else "",
        "promotion_manifest_json_out": promotion_manifest_json_out if template_dir else "",
        "promotion_manifest_verify_json_out": promotion_manifest_verify_json_out if template_dir else "",
        "promotion_receipt_json_out": promotion_receipt_json_out if template_dir else "",
        "promotion_receipt_verify_json_out": promotion_receipt_verify_json_out if template_dir else "",
        "promotion_receipt_require_go_json_out": promotion_receipt_require_go_json_out if template_dir else "",
        "promotion_gate_command": promotion_gate_command if template_dir else "",
        "promotion_single_command": promotion_gate_command if template_dir else "",
        "promotion_manifest_verify_command": promotion_manifest_verify_command if template_dir else "",
        "promotion_receipt_verify_command": promotion_receipt_verify_command if template_dir else "",
        "promotion_receipt_require_go_command": promotion_receipt_require_go_command if template_dir else "",
        "provider_json_outputs": {
            provider: f"var/external-release-gate-post-apply-{provider}.json" for provider in provider_keys
        },
    }


def provider_apply_plan_payload(
    payload: dict[str, Any],
    provider_paths: dict[str, Path],
    *,
    plan_path: str | Path | None = None,
) -> dict[str, Any]:
    index = provider_template_index_payload(payload, provider_paths)
    template_dirs = sorted({str(Path(provider["path"]).parent) for provider in _as_list(index.get("providers"))})
    template_dir = template_dirs[0] if len(template_dirs) == 1 else ""
    providers: list[dict[str, Any]] = []
    for provider in _as_list(index.get("providers")):
        if not isinstance(provider, dict):
            continue
        provider_key = str(provider.get("provider") or "")
        keys = _string_list(provider.get("env_keys"))
        env_key_count = int(provider.get("env_key_count") or 0)
        populated_key_count = int(provider.get("populated_key_count") or 0)
        ready_to_apply = env_key_count > 0 and populated_key_count == env_key_count
        guidance = _provider_guidance(provider_key)
        providers.append(
            {
                "provider": provider_key,
                "label": provider.get("label") or _provider_label(provider_key),
                "template_path": provider.get("path"),
                "template_filename": provider.get("template_filename"),
                "docs_url": guidance.get("docs_url") if isinstance(guidance.get("docs_url"), str) else "",
                "preflight_commands": _string_list(guidance.get("preflight_commands")),
                "env_keys": keys,
                "env_key_count": env_key_count,
                "populated_key_count": populated_key_count,
                "blank_key_count": max(env_key_count - populated_key_count, 0),
                "ready_to_apply": ready_to_apply,
                "blocked_reason": "" if ready_to_apply else "template has blank values",
                "commands": _provider_apply_commands(provider_key, str(provider.get("path") or ""), keys),
                "post_apply_verify_commands": [
                    _post_apply_verify_command(template_dir, provider_key)
                ]
                if template_dir and provider_key in {"amoy", "github", "railway", "vercel"}
                else [],
            }
        )
    operator_status = _provider_apply_operator_status(index, providers)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": True,
        "release_decision": payload.get("release_decision"),
        "external_gate_json": payload.get("external_gate_json"),
        "provider_template_index": {
            "safe_to_commit": index.get("safe_to_commit") is True,
            "provider_template_count": index.get("provider_template_count"),
            "populated_key_count": index.get("populated_key_count"),
        },
        "operator_status": operator_status,
        "provider_apply_plan_verification": _provider_apply_plan_verification(
            plan_path or DEFAULT_PROVIDER_APPLY_PLAN_JSON
        ),
        "provider_apply_results_verification": _provider_apply_results_verification(
            plan_path or DEFAULT_PROVIDER_APPLY_PLAN_JSON
        ),
        "provider_apply_workflow_verification": _provider_apply_workflow_verification(
            plan_path or DEFAULT_PROVIDER_APPLY_PLAN_JSON
        ),
        "post_apply_completion_evidence": _post_apply_completion_evidence(template_dir, providers),
        "ready_provider_count": operator_status["ready_provider_count"],
        "provider_count": len(providers),
        "providers": providers,
    }


def _expected_apply_commands(plan: dict[str, Any]) -> list[dict[str, Any]]:
    expected: list[dict[str, Any]] = []
    for provider in _as_list(plan.get("providers")):
        if not isinstance(provider, dict):
            continue
        provider_key = str(provider.get("provider") or "")
        for command in _as_list(provider.get("commands")):
            if not isinstance(command, dict):
                continue
            command_id = str(command.get("id") or "")
            if not provider_key or not command_id:
                continue
            expected.append(
                {
                    "provider": provider_key,
                    "command_id": command_id,
                    "command": str(command.get("command") or ""),
                    "stdin_required": command.get("stdin_required") is True,
                }
            )
    return expected


def provider_apply_results_template_payload(
    plan: dict[str, Any],
    *,
    plan_path: str | Path,
) -> dict[str, Any]:
    expected = _expected_apply_commands(plan)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": False,
        "provider_apply_plan_json": str(plan_path),
        "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
        "provider_count": int(plan.get("provider_count") or 0),
        "command_count": len(expected),
        "results": [
            {
                "provider": item["provider"],
                "command_id": item["command_id"],
                "status": "pending",
                "exit_code": None,
                "started_at": "",
                "finished_at": "",
                "stdout_excerpt": "",
                "stderr_excerpt": "",
            }
            for item in expected
        ],
    }


def write_provider_apply_results_template(
    path: str | Path,
    plan: dict[str, Any],
    *,
    plan_path: str | Path,
) -> Path:
    return write_json_report(path, provider_apply_results_template_payload(plan, plan_path=plan_path))


def _read_env_template_values(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _provider_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(provider.get("provider") or ""): provider
        for provider in _as_list(plan.get("providers"))
        if isinstance(provider, dict) and str(provider.get("provider") or "")
    }


def _provider_env_values(plan: dict[str, Any]) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for provider_key, provider in _provider_lookup(plan).items():
        template_path = str(provider.get("template_path") or "")
        if not template_path:
            continue
        try:
            values[provider_key] = _read_env_template_values(template_path)
        except OSError:
            values[provider_key] = {}
    return values


def _env_key_for_command(provider: dict[str, Any], command_id: str, prefix: str) -> str:
    raw_key = command_id.removeprefix(prefix)
    lower_to_key = {key.lower(): key for key in _string_list(provider.get("env_keys"))}
    return lower_to_key.get(raw_key, raw_key.upper())


def _recorded_excerpt(value: Any, *, limit: int = 800) -> tuple[str, list[str]]:
    text = str(value or "")
    markers = secret_marker_names_in_text(text)
    if markers:
        return "[redacted secret-shaped output]", markers
    compact = " ".join(text.replace("\r", "\n").split())
    return compact[:limit], []


def _provider_apply_invocation(
    plan: dict[str, Any],
    command: dict[str, Any],
    env_values: dict[str, dict[str, str]],
) -> tuple[list[str] | str | None, str | None, str]:
    provider_key = str(command.get("provider") or "")
    command_id = str(command.get("command_id") or "")
    providers = _provider_lookup(plan)
    provider = providers.get(provider_key, {})
    if provider_key == "github" and command_id == "github_secret_env_file":
        template_path = str(provider.get("template_path") or "")
        if not template_path:
            return None, None, "github provider template path is missing"
        return ["gh", "secret", "set", "--env-file", template_path], None, ""
    if provider_key == "railway" and command_id.startswith("railway_variable_set_"):
        key = _env_key_for_command(provider, command_id, "railway_variable_set_")
        value = env_values.get(provider_key, {}).get(key, "")
        if not value:
            return None, None, f"{provider_key}/{command_id} private stdin value is blank"
        return ["railway", "variable", "set", key, "--stdin"], value, ""
    if provider_key == "vercel" and command_id.startswith("vercel_env_add_"):
        key = _env_key_for_command(provider, command_id, "vercel_env_add_")
        value = env_values.get(provider_key, {}).get(key, "")
        if not value:
            return None, None, f"{provider_key}/{command_id} private stdin value is blank"
        return ["vercel", "env", "add", key, "production"], value, ""
    command_text = str(command.get("command") or "")
    if not command_text:
        return None, None, f"{provider_key}/{command_id} command is missing"
    return command_text, None, ""


def _record_provider_command_result(
    plan: dict[str, Any],
    command: dict[str, Any],
    env_values: dict[str, dict[str, str]],
    *,
    execute: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    provider = str(command.get("provider") or "")
    command_id = str(command.get("command_id") or "")
    result: dict[str, Any] = {
        "provider": provider,
        "command_id": command_id,
        "status": "dry_run",
        "exit_code": None,
        "started_at": "",
        "finished_at": "",
        "stdout_excerpt": "dry run only; command not executed",
        "stderr_excerpt": "",
        "redacted_secret_marker_names": [],
    }
    if not execute:
        return result

    invocation, stdin_value, blocked_reason = _provider_apply_invocation(plan, command, env_values)
    result["started_at"] = _iso_now()
    if blocked_reason:
        result.update(
            {
                "status": "blocked",
                "finished_at": _iso_now(),
                "stdout_excerpt": "",
                "stderr_excerpt": blocked_reason,
            }
        )
        return result

    try:
        completed = subprocess.run(
            invocation,
            input=stdin_value,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=isinstance(invocation, str),
            check=False,
        )
        stdout_excerpt, stdout_markers = _recorded_excerpt(completed.stdout)
        stderr_excerpt, stderr_markers = _recorded_excerpt(completed.stderr)
        markers = _dedupe([*stdout_markers, *stderr_markers])
        result.update(
            {
                "status": "success" if completed.returncode == 0 and not markers else "failure",
                "exit_code": completed.returncode,
                "finished_at": _iso_now(),
                "stdout_excerpt": stdout_excerpt,
                "stderr_excerpt": stderr_excerpt,
                "redacted_secret_marker_names": markers,
            }
        )
    except subprocess.TimeoutExpired as exc:
        stdout_excerpt, stdout_markers = _recorded_excerpt(exc.stdout)
        stderr_excerpt, stderr_markers = _recorded_excerpt(exc.stderr)
        result.update(
            {
                "status": "timeout",
                "exit_code": None,
                "finished_at": _iso_now(),
                "stdout_excerpt": stdout_excerpt,
                "stderr_excerpt": stderr_excerpt,
                "redacted_secret_marker_names": _dedupe([*stdout_markers, *stderr_markers]),
            }
        )
    except OSError as exc:
        result.update(
            {
                "status": "failure",
                "exit_code": None,
                "finished_at": _iso_now(),
                "stdout_excerpt": "",
                "stderr_excerpt": str(exc),
            }
        )
    return result


def record_provider_apply_results(
    plan_path: str | Path,
    *,
    execute: bool = False,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    plan = load_provider_apply_plan(plan_path)
    expected = _expected_apply_commands(plan)
    env_values = _provider_env_values(plan)
    operator_status = _as_dict(plan.get("operator_status"))
    plan_not_ready = execute and operator_status and operator_status.get("ready_to_apply") is not True
    results: list[dict[str, Any]] = []
    for command in expected:
        if plan_not_ready:
            results.append(
                {
                    "provider": command["provider"],
                    "command_id": command["command_id"],
                    "status": "blocked",
                    "exit_code": None,
                    "started_at": "",
                    "finished_at": "",
                    "stdout_excerpt": "",
                    "stderr_excerpt": "provider apply plan is not ready_to_apply",
                    "redacted_secret_marker_names": [],
                }
            )
            continue
        results.append(
            _record_provider_command_result(
                plan,
                command,
                env_values,
                execute=execute,
                timeout_seconds=timeout_seconds,
            )
        )
    all_succeeded = bool(results) and all(
        result.get("status") == "success" and result.get("exit_code") == 0 for result in results
    )
    return {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "ok": all_succeeded,
        "execution_mode": "execute" if execute else "dry_run",
        "provider_apply_plan_json": str(plan_path),
        "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
        "provider_count": int(plan.get("provider_count") or 0),
        "command_count": len(expected),
        "results": results,
    }


def write_recorded_provider_apply_results(
    path: str | Path,
    plan_path: str | Path,
    *,
    execute: bool = False,
    timeout_seconds: float = 120.0,
) -> Path:
    return write_json_report(
        path,
        record_provider_apply_results(plan_path, execute=execute, timeout_seconds=timeout_seconds),
    )


def write_provider_apply_plan(
    path: str | Path,
    payload: dict[str, Any],
    provider_paths: dict[str, Path],
) -> Path:
    return write_json_report(path, provider_apply_plan_payload(payload, provider_paths, plan_path=path))


def _provider_apply_plan_provider_verification(provider: dict[str, Any]) -> dict[str, Any]:
    provider_key = str(provider.get("provider") or "")
    template_path = str(provider.get("template_path") or "")
    env_keys = _string_list(provider.get("env_keys"))
    env_key_count = int(provider.get("env_key_count") or 0)
    populated_key_count = int(provider.get("populated_key_count") or 0)
    blank_key_count = int(provider.get("blank_key_count") or 0)
    expected_blank_key_count = max(env_key_count - populated_key_count, 0)
    ready_to_apply = provider.get("ready_to_apply") is True
    expected_ready = env_key_count > 0 and populated_key_count == env_key_count
    failures: list[str] = []
    template_audit: dict[str, Any] = {
        "exists": False,
        "env_key_count": 0,
        "populated_key_count": 0,
        "blank_key_count": 0,
    }

    if not provider_key:
        failures.append("provider is required")
    if env_key_count < 0 or populated_key_count < 0 or blank_key_count < 0:
        failures.append("provider env counts must be non-negative")
    if populated_key_count > env_key_count:
        failures.append("provider populated_key_count must not exceed env_key_count")
    if blank_key_count != expected_blank_key_count:
        failures.append("provider blank_key_count must equal env_key_count minus populated_key_count")
    if ready_to_apply is not expected_ready:
        failures.append("provider ready_to_apply does not match env counts")
    if not template_path:
        failures.append("provider template_path is required")
    else:
        path = Path(template_path)
        template_audit["exists"] = path.exists()
        if not path.exists():
            failures.append("provider template_path is missing")
        else:
            try:
                audit = _env_template_audit(path)
                audit_env_key_count = int(audit.get("env_key_count") or 0)
                audit_populated_key_count = int(audit.get("populated_key_count") or 0)
                template_audit.update(
                    {
                        "env_key_count": audit_env_key_count,
                        "populated_key_count": audit_populated_key_count,
                        "blank_key_count": max(audit_env_key_count - audit_populated_key_count, 0),
                    }
                )
                if _string_list(audit.get("env_keys")) != env_keys:
                    failures.append("provider template env_keys do not match apply plan")
                if audit_populated_key_count != populated_key_count:
                    failures.append("provider template populated_key_count does not match apply plan")
            except OSError as exc:
                failures.append(f"provider template could not be read: {exc}")

    for command in [item for item in _as_list(provider.get("commands")) if isinstance(item, dict)]:
        placeholder = str(command.get("value_placeholder") or "")
        if placeholder and not (placeholder.startswith("<") and placeholder.endswith(">")):
            failures.append("provider command value_placeholder must be redacted")

    return {
        "provider": provider_key,
        "template_path": template_path,
        "ready_to_apply": ready_to_apply,
        "env_key_count": env_key_count,
        "populated_key_count": populated_key_count,
        "blank_key_count": blank_key_count,
        "template_audit": template_audit,
        "ok": not failures,
        "failures": failures,
    }


def verify_provider_apply_plan(
    plan_path: str | Path,
    *,
    require_ready_to_apply: bool = False,
) -> dict[str, Any]:
    plan = load_provider_apply_plan(plan_path)
    operator_status = _as_dict(plan.get("operator_status"))
    template_index = _as_dict(plan.get("provider_template_index"))
    providers = [item for item in _as_list(plan.get("providers")) if isinstance(item, dict)]
    provider_checks = [_provider_apply_plan_provider_verification(provider) for provider in providers]
    ready_provider_count = sum(1 for provider in providers if provider.get("ready_to_apply") is True)
    blocked_provider_count = max(len(providers) - ready_provider_count, 0)
    failures: list[str] = []
    serialized = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    secret_markers = secret_marker_names_in_text(serialized)

    if plan.get("schema_version") != 1:
        failures.append("provider apply plan must be schema_version=1")
    if plan.get("ok") is not True:
        failures.append("provider apply plan ok must be true")
    if secret_markers:
        failures.append("provider apply plan contains secret-shaped markers")
    if int(plan.get("provider_count") or 0) != len(providers):
        failures.append("provider_count must match providers length")
    if int(plan.get("ready_provider_count") or 0) != ready_provider_count:
        failures.append("ready_provider_count must match ready providers")
    if int(template_index.get("provider_template_count") or 0) != len(providers):
        failures.append("provider_template_count must match providers length")
    if int(template_index.get("populated_key_count") or 0) != sum(
        int(provider.get("populated_key_count") or 0) for provider in providers
    ):
        failures.append("provider_template_index populated_key_count must match providers")

    expected_ready = len(providers) > 0 and blocked_provider_count == 0
    if operator_status.get("ready_to_apply") is not expected_ready:
        failures.append("operator_status.ready_to_apply does not match provider readiness")
    if int(operator_status.get("ready_provider_count") or 0) != ready_provider_count:
        failures.append("operator_status.ready_provider_count does not match providers")
    if int(operator_status.get("blocked_provider_count") or 0) != blocked_provider_count:
        failures.append("operator_status.blocked_provider_count does not match providers")
    if operator_status.get("apply_plan_safe_to_commit") is not True:
        failures.append("operator_status.apply_plan_safe_to_commit must be true")
    if operator_status.get("completion_marker") != "external_release_gate.ok=true":
        failures.append("operator_status.completion_marker is not recognized")
    if require_ready_to_apply and operator_status.get("ready_to_apply") is not True:
        failures.append("provider apply plan must be ready_to_apply")
    if require_ready_to_apply:
        for provider in provider_checks:
            if provider.get("ready_to_apply") is not True:
                provider.setdefault("failures", []).append("provider template has blank values")
                provider["ok"] = False

    provider_failure_count = sum(1 for provider in provider_checks if provider.get("ok") is not True)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failures and provider_failure_count == 0,
        "provider_apply_plan_json": str(plan_path),
        "require_ready_to_apply": require_ready_to_apply,
        "ready_to_apply": operator_status.get("ready_to_apply") is True,
        "operator_stage": operator_status.get("stage"),
        "success_condition": PROVIDER_APPLY_PLAN_VERIFY_CONDITION
        if not require_ready_to_apply
        else PROVIDER_APPLY_PLAN_READY_CONDITION,
        "summary": {
            "failure_count": len(failures),
            "provider_count": len(providers),
            "ready_provider_count": ready_provider_count,
            "blocked_provider_count": blocked_provider_count,
            "provider_failure_count": provider_failure_count,
            "secret_marker_count": len(secret_markers),
        },
        "secret_marker_names": secret_markers,
        "failures": failures,
        "providers": provider_checks,
    }


def verify_provider_apply_results(
    results_path: str | Path,
    *,
    plan_path: str | Path,
) -> dict[str, Any]:
    plan = load_provider_apply_plan(plan_path)
    results = load_provider_apply_results(results_path)
    expected_commands = _expected_apply_commands(plan)
    expected_by_key = {
        (item["provider"], item["command_id"]): item
        for item in expected_commands
    }
    result_items = [item for item in _as_list(results.get("results")) if isinstance(item, dict)]
    seen_keys: set[tuple[str, str]] = set()
    command_checks: list[dict[str, Any]] = []
    failures: list[str] = []
    serialized = json.dumps(results, ensure_ascii=False, sort_keys=True)
    secret_markers = secret_marker_names_in_text(serialized)

    if results.get("schema_version") != 1:
        failures.append("provider apply results must be schema_version=1")
    if not _same_path_text(str(results.get("provider_apply_plan_json") or ""), plan_path):
        failures.append("provider_apply_plan_json must match the verified plan path")
    if secret_markers:
        failures.append("provider apply results contain secret-shaped markers")
    if int(results.get("command_count") or 0) != len(expected_commands):
        failures.append("provider apply results command_count must match expected commands")

    for item in result_items:
        provider = str(item.get("provider") or "")
        command_id = str(item.get("command_id") or "")
        key = (provider, command_id)
        item_failures: list[str] = []
        expected = expected_by_key.get(key)
        status = str(item.get("status") or "")
        exit_code = item.get("exit_code")

        if key in seen_keys:
            item_failures.append("duplicate provider command result")
        seen_keys.add(key)
        if expected is None:
            item_failures.append("provider command result is not expected by the apply plan")
        if status != "success":
            item_failures.append("provider command status must be success")
        if exit_code != 0:
            item_failures.append("provider command exit_code must be 0")
        if str(item.get("stdout_excerpt") or "").strip() and secret_marker_names_in_text(
            str(item.get("stdout_excerpt"))
        ):
            item_failures.append("provider command stdout_excerpt contains secret-shaped markers")
        if str(item.get("stderr_excerpt") or "").strip() and secret_marker_names_in_text(
            str(item.get("stderr_excerpt"))
        ):
            item_failures.append("provider command stderr_excerpt contains secret-shaped markers")
        command_checks.append(
            {
                "provider": provider,
                "command_id": command_id,
                "expected": expected is not None,
                "status": status,
                "exit_code": exit_code,
                "ok": not item_failures,
                "failures": item_failures,
            }
        )

    missing_expected = [
        {"provider": provider, "command_id": command_id}
        for provider, command_id in sorted(expected_by_key)
        if (provider, command_id) not in seen_keys
    ]
    if missing_expected:
        failures.append("provider apply results are missing expected commands")
        for item in missing_expected:
            command_checks.append(
                {
                    "provider": item["provider"],
                    "command_id": item["command_id"],
                    "expected": True,
                    "status": "missing",
                    "exit_code": None,
                    "ok": False,
                    "failures": ["provider command result is missing"],
                }
            )

    command_failure_count = sum(1 for item in command_checks if item.get("ok") is not True)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failures and command_failure_count == 0,
        "provider_apply_results_json": str(results_path),
        "provider_apply_plan_json": str(plan_path),
        "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
        "all_commands_succeeded": command_failure_count == 0 and len(command_checks) == len(expected_commands),
        "summary": {
            "failure_count": len(failures),
            "expected_command_count": len(expected_commands),
            "reported_command_count": len(result_items),
            "checked_command_count": len(command_checks),
            "missing_command_count": len(missing_expected),
            "command_failure_count": command_failure_count,
            "secret_marker_count": len(secret_markers),
        },
        "secret_marker_names": secret_markers,
        "failures": failures,
        "commands": command_checks,
    }


def _missing_artifact_verification(path: str | Path, label: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "ok": False,
        "path": str(path),
        "summary": {"failure_count": 1},
        "failures": [f"{label} is required"],
    }


def verify_provider_apply_workflow(
    plan_path: str | Path,
    *,
    results_path: str | Path | None = None,
    promotion_receipt_path: str | Path | None = None,
    require_promotion_go: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    plan = load_provider_apply_plan(plan_path)
    workflow_metadata = _as_dict(plan.get("provider_apply_workflow_verification"))
    default_results_path, results_path_source = _metadata_path(
        workflow_metadata,
        "provider_apply_results_json",
        _json_path_with_suffix(plan_path, "-results"),
    )
    default_promotion_receipt_path, promotion_receipt_path_source = _metadata_path(
        workflow_metadata,
        "promotion_receipt_json",
        "var/post-apply-promotion-receipt.json",
    )
    resolved_results_path = str(results_path) if results_path is not None else default_results_path
    resolved_promotion_receipt_path = (
        str(promotion_receipt_path) if promotion_receipt_path is not None else default_promotion_receipt_path
    )
    if results_path is not None:
        results_path_source = "argument"
    if promotion_receipt_path is not None:
        promotion_receipt_path_source = "argument"

    plan_verification = verify_provider_apply_plan(plan_path, require_ready_to_apply=True)
    if plan_verification.get("ok") is not True:
        failures.append("provider apply plan is not ready")

    if resolved_results_path and Path(resolved_results_path).exists():
        results_verification = verify_provider_apply_results(resolved_results_path, plan_path=plan_path)
    else:
        results_verification = _missing_artifact_verification(
            resolved_results_path,
            "provider apply results receipt",
        )
    if results_verification.get("ok") is not True:
        failures.append("provider apply results are not successful")
    if results_verification.get("all_commands_succeeded") is not True:
        failures.append("provider apply results must have all_commands_succeeded=true")

    if resolved_promotion_receipt_path and Path(resolved_promotion_receipt_path).exists():
        promotion_verification = verify_promotion_receipt(
            resolved_promotion_receipt_path,
            require_go=require_promotion_go,
        )
    else:
        promotion_verification = _missing_artifact_verification(
            resolved_promotion_receipt_path,
            "post-apply promotion receipt",
        )
    if promotion_verification.get("ok") is not True:
        failures.append("post-apply promotion receipt verification failed")
    if promotion_verification.get("promotion_receipt_ok") is not True:
        failures.append("post-apply promotion receipt must be go")

    ready_to_apply = plan_verification.get("ready_to_apply") is True
    all_commands_succeeded = results_verification.get("all_commands_succeeded") is True
    promotion_receipt_ok = promotion_verification.get("promotion_receipt_ok") is True
    workflow_ok = ready_to_apply and all_commands_succeeded and promotion_receipt_ok and not failures
    return {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "ok": workflow_ok,
        "provider_apply_plan_json": str(plan_path),
        "provider_apply_results_json": resolved_results_path,
        "promotion_receipt_json": resolved_promotion_receipt_path,
        "artifact_resolution": {
            "provider_apply_results_json": results_path_source,
            "promotion_receipt_json": promotion_receipt_path_source,
        },
        "require_promotion_go": require_promotion_go,
        "success_condition": PROVIDER_APPLY_WORKFLOW_CONDITION,
        "operator_phase": "provider_apply_workflow_ready" if workflow_ok else "provider_apply_workflow_blocked",
        "ready_to_apply": ready_to_apply,
        "all_commands_succeeded": all_commands_succeeded,
        "promotion_receipt_ok": promotion_receipt_ok,
        "summary": {
            "failure_count": len(failures),
            "plan_ok": plan_verification.get("ok") is True,
            "results_ok": results_verification.get("ok") is True,
            "promotion_verification_ok": promotion_verification.get("ok") is True,
            "plan_failure_count": int(_as_dict(plan_verification.get("summary")).get("failure_count") or 0),
            "results_failure_count": int(_as_dict(results_verification.get("summary")).get("failure_count") or 0),
            "results_command_failure_count": int(
                _as_dict(results_verification.get("summary")).get("command_failure_count") or 0
            ),
            "promotion_failure_count": int(
                _as_dict(promotion_verification.get("summary")).get("failure_count") or 0
            ),
        },
        "failures": failures,
        "provider_apply_plan_verification": plan_verification,
        "provider_apply_results_verification": results_verification,
        "post_apply_promotion_receipt_verification": promotion_verification,
    }


def render_provider_apply_plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DeSci Provider Apply Plan",
        "",
        "## Summary",
        f"- Release decision: `{_markdown_scalar(payload.get('release_decision'))}`",
        f"- Providers ready to apply: `{_markdown_scalar(payload.get('ready_provider_count', 0))}`/"
        f"`{_markdown_scalar(payload.get('provider_count', 0))}`",
        "",
        "## Operator Status",
    ]
    operator_status = _as_dict(payload.get("operator_status"))
    if operator_status:
        lines.extend(
            [
                f"- Stage: `{_markdown_scalar(operator_status.get('stage'))}`",
                f"- Ready to apply: `{_markdown_scalar(operator_status.get('ready_to_apply'))}`",
                f"- Blocked providers: `{_markdown_scalar(operator_status.get('blocked_provider_count', 0))}`",
                f"- Provider templates safe to commit: "
                f"`{_markdown_scalar(operator_status.get('provider_templates_safe_to_commit'))}`",
                f"- Apply plan safe to commit: "
                f"`{_markdown_scalar(operator_status.get('apply_plan_safe_to_commit'))}`",
                f"- Completion marker: `{_markdown_scalar(operator_status.get('completion_marker'))}`",
                f"- Next required action: {operator_status.get('next_required_action')}",
                "",
            ]
        )
    else:
        lines.extend(["- Unknown.", ""])
    plan_verification = _as_dict(payload.get("provider_apply_plan_verification"))
    if plan_verification:
        lines.extend(
            [
                "## Provider Apply Plan Verification",
                f"- Success condition: `{_markdown_scalar(plan_verification.get('success_condition'))}`",
                f"- Ready success condition: "
                f"`{_markdown_scalar(plan_verification.get('ready_success_condition'))}`",
                f"- Verify JSON: `{_markdown_scalar(plan_verification.get('verify_json_out'))}`",
                f"- Require-ready JSON: `{_markdown_scalar(plan_verification.get('require_ready_json_out'))}`",
                f"- Verify command: `{_markdown_scalar(plan_verification.get('verify_command'))}`",
                f"- Require-ready command: "
                f"`{_markdown_scalar(plan_verification.get('require_ready_command'))}`",
                "",
            ]
        )
    results_verification = _as_dict(payload.get("provider_apply_results_verification"))
    if results_verification:
        lines.extend(
            [
                "## Provider Apply Results Verification",
                f"- Success condition: `{_markdown_scalar(results_verification.get('success_condition'))}`",
                f"- Results JSON: `{_markdown_scalar(results_verification.get('provider_apply_results_json'))}`",
                f"- Results template JSON: `{_markdown_scalar(results_verification.get('template_json_out'))}`",
                f"- Dry-run results JSON: `{_markdown_scalar(results_verification.get('dry_run_json_out'))}`",
                f"- Verify JSON: `{_markdown_scalar(results_verification.get('verify_json_out'))}`",
                f"- Template command: `{_markdown_scalar(results_verification.get('template_command'))}`",
                f"- Dry-run recorder command: `{_markdown_scalar(results_verification.get('dry_run_command'))}`",
                f"- Execute recorder command: `{_markdown_scalar(results_verification.get('execute_command'))}`",
                f"- Verify command: `{_markdown_scalar(results_verification.get('verify_command'))}`",
                "",
            ]
        )
    workflow_verification = _as_dict(payload.get("provider_apply_workflow_verification"))
    if workflow_verification:
        lines.extend(
            [
                "## Provider Apply Workflow Verification",
                f"- Success condition: `{_markdown_scalar(workflow_verification.get('success_condition'))}`",
                f"- Provider apply plan JSON: `{_markdown_scalar(workflow_verification.get('provider_apply_plan_json'))}`",
                f"- Provider apply results JSON: `{_markdown_scalar(workflow_verification.get('provider_apply_results_json'))}`",
                f"- Promotion receipt JSON: `{_markdown_scalar(workflow_verification.get('promotion_receipt_json'))}`",
                f"- Verify JSON: `{_markdown_scalar(workflow_verification.get('verify_json_out'))}`",
                f"- Default verify command: `{_markdown_scalar(workflow_verification.get('default_verify_command'))}`",
                f"- Default require-go command: "
                f"`{_markdown_scalar(workflow_verification.get('default_require_go_command'))}`",
                f"- Verify command: `{_markdown_scalar(workflow_verification.get('verify_command'))}`",
                f"- Require-go command: `{_markdown_scalar(workflow_verification.get('require_go_command'))}`",
                "",
            ]
        )
    completion_evidence = _as_dict(payload.get("post_apply_completion_evidence"))
    lines.append("## Post-Apply Evidence")
    if completion_evidence and completion_evidence.get("required") is True:
        lines.extend(
            [
                f"- Success condition: `{_markdown_scalar(completion_evidence.get('success_condition'))}`",
                f"- Aggregate JSON: `{_markdown_scalar(completion_evidence.get('aggregate_json_out'))}`",
                f"- Aggregate command: `{_markdown_scalar(completion_evidence.get('aggregate_command'))}`",
                f"- Promotion gate JSON: `{_markdown_scalar(completion_evidence.get('promotion_gate_json_out'))}`",
                f"- Promotion manifest JSON: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_manifest_json_out'))}`",
                f"- Promotion gate command: `{_markdown_scalar(completion_evidence.get('promotion_gate_command'))}`",
                f"- Promotion single command: `{_markdown_scalar(completion_evidence.get('promotion_single_command'))}`",
                f"- Promotion manifest verify JSON: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_manifest_verify_json_out'))}`",
                f"- Promotion receipt JSON: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_receipt_json_out'))}`",
                f"- Promotion receipt verify JSON: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_receipt_verify_json_out'))}`",
                f"- Promotion receipt require-go JSON: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_receipt_require_go_json_out'))}`",
                f"- Promotion manifest verify command: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_manifest_verify_command'))}`",
                f"- Promotion receipt verify command: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_receipt_verify_command'))}`",
                f"- Promotion receipt require-go command: "
                f"`{_markdown_scalar(completion_evidence.get('promotion_receipt_require_go_command'))}`",
            ]
        )
        provider_outputs = _as_dict(completion_evidence.get("provider_json_outputs"))
        if provider_outputs:
            lines.append("- Provider JSON outputs:")
            for provider in sorted(provider_outputs):
                lines.append(f"  - {provider}: `{provider_outputs[provider]}`")
        lines.append("")
    else:
        lines.extend(["- Not required because no provider templates were generated.", ""])
    lines.append("## Providers")
    providers = [provider for provider in _as_list(payload.get("providers")) if isinstance(provider, dict)]
    if not providers:
        lines.append("- None.")
    for provider in providers:
        commands = [item for item in _as_list(provider.get("commands")) if isinstance(item, dict)]
        lines.append(f"### {provider.get('label')}")
        lines.append(f"- Template: `{_markdown_scalar(provider.get('template_path'))}`")
        lines.append(f"- Ready to apply: `{_markdown_scalar(provider.get('ready_to_apply'))}`")
        if provider.get("blocked_reason"):
            lines.append(f"- Blocked reason: `{provider.get('blocked_reason')}`")
        docs_url = provider.get("docs_url") if isinstance(provider.get("docs_url"), str) else ""
        if docs_url:
            lines.append(f"- Docs: {docs_url}")
        lines.append(f"- Preflight commands: {_markdown_values(provider.get('preflight_commands'))}")
        if commands:
            lines.append("- Apply command templates:")
            for command in commands:
                powershell_command = command.get("powershell_command") or command.get("command")
                posix_command = command.get("posix_command") or command.get("command")
                lines.append(f"  - PowerShell: `{powershell_command}`")
                lines.append(f"  - POSIX: `{posix_command}`")
        verify_commands = _string_list(provider.get("post_apply_verify_commands"))
        if verify_commands:
            lines.append("- Verify after apply:")
            for command in verify_commands:
                lines.append(f"  - `{command}`")
    return "\n".join(lines).rstrip() + "\n"


def write_provider_apply_plan_markdown(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_text_report(path, render_provider_apply_plan_markdown(payload))


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


def print_provider_apply_plan_verification_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[external-gate-handoff] provider_apply_plan_ok={payload.get('ok')}")
    print(
        "[external-gate-handoff] "
        f"ready_to_apply={payload.get('ready_to_apply')} "
        f"require_ready={payload.get('require_ready_to_apply')} "
        f"providers={summary.get('ready_provider_count')}/{summary.get('provider_count')} "
        f"provider_failures={summary.get('provider_failure_count')} "
        f"failures={summary.get('failure_count')} "
        f"secret_markers={summary.get('secret_marker_count')}"
    )
    for failure in _string_list(payload.get("failures")):
        print(f"  - {failure}")
    for provider in _as_list(payload.get("providers")):
        if isinstance(provider, dict) and provider.get("ok") is not True:
            label = provider.get("provider") or "provider"
            for failure in _string_list(provider.get("failures")):
                print(f"  - {label}: {failure}")


def print_provider_apply_results_verification_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[external-gate-handoff] provider_apply_results_ok={payload.get('ok')}")
    print(
        "[external-gate-handoff] "
        f"all_commands_succeeded={payload.get('all_commands_succeeded')} "
        f"expected={summary.get('expected_command_count')} "
        f"reported={summary.get('reported_command_count')} "
        f"command_failures={summary.get('command_failure_count')} "
        f"failures={summary.get('failure_count')} "
        f"secret_markers={summary.get('secret_marker_count')}"
    )
    for failure in _string_list(payload.get("failures")):
        print(f"  - {failure}")
    for command in _as_list(payload.get("commands")):
        if isinstance(command, dict) and command.get("ok") is not True:
            label = f"{command.get('provider')}/{command.get('command_id')}"
            for failure in _string_list(command.get("failures")):
                print(f"  - {label}: {failure}")


def print_provider_apply_results_record_report(payload: dict[str, Any]) -> None:
    results = [item for item in _as_list(payload.get("results")) if isinstance(item, dict)]
    failed = [item for item in results if item.get("status") != "success" or item.get("exit_code") != 0]
    print(f"[external-gate-handoff] provider_apply_results_recorded={payload.get('ok')}")
    print(
        "[external-gate-handoff] "
        f"execution_mode={payload.get('execution_mode')} "
        f"command_count={payload.get('command_count')} "
        f"failed_commands={len(failed)}"
    )
    for command in failed:
        label = f"{command.get('provider')}/{command.get('command_id')}"
        status = command.get("status")
        exit_code = command.get("exit_code")
        stderr = command.get("stderr_excerpt")
        print(f"  - {label}: status={status} exit_code={exit_code} stderr={stderr}")


def print_provider_apply_workflow_verification_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[external-gate-handoff] provider_apply_workflow_ok={payload.get('ok')}")
    print(
        "[external-gate-handoff] "
        f"ready_to_apply={payload.get('ready_to_apply')} "
        f"all_commands_succeeded={payload.get('all_commands_succeeded')} "
        f"promotion_receipt_ok={payload.get('promotion_receipt_ok')} "
        f"failures={summary.get('failure_count')}"
    )
    for failure in _string_list(payload.get("failures")):
        print(f"  - {failure}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DeSci external gate operator handoff.")
    parser.add_argument(
        "--external-gate-json",
        default=str(DEFAULT_EXTERNAL_GATE_JSON),
        help="Path to external_release_gate.py JSON evidence.",
    )
    parser.add_argument("--verify-provider-apply-plan", help="Path to a redacted provider apply plan to verify.")
    parser.add_argument(
        "--provider-apply-results-template-from-plan",
        help="Path to a provider apply plan used to write a redacted apply-results template.",
    )
    parser.add_argument(
        "--record-provider-apply-results-from-plan",
        help="Path to a provider apply plan used to write a dry-run or execution apply-results receipt.",
    )
    parser.add_argument(
        "--execute-provider-apply-commands",
        action="store_true",
        help="With --record-provider-apply-results-from-plan, actually run provider apply commands.",
    )
    parser.add_argument(
        "--provider-apply-command-timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds for each provider apply command in execute mode.",
    )
    parser.add_argument("--verify-provider-apply-results", help="Path to redacted provider apply results to verify.")
    parser.add_argument("--verify-provider-apply-workflow", help="Path to a provider apply plan to verify end-to-end.")
    parser.add_argument("--provider-apply-results", help="Provider apply results path used with workflow verification.")
    parser.add_argument("--promotion-receipt", help="Post-apply promotion receipt path used with workflow verification.")
    parser.add_argument(
        "--require-promotion-go",
        action="store_true",
        help="With --verify-provider-apply-workflow, require the promotion receipt to be go.",
    )
    parser.add_argument(
        "--provider-apply-plan",
        help="Provider apply plan path used with --verify-provider-apply-results.",
    )
    parser.add_argument(
        "--require-ready-to-apply",
        action="store_true",
        help="In --verify-provider-apply-plan mode, fail unless all provider templates are filled.",
    )
    parser.add_argument("--json", action="store_true", help="Print the handoff as JSON.")
    parser.add_argument("--json-out", help="Write handoff JSON evidence.")
    parser.add_argument("--markdown-out", help="Write a human-readable handoff packet.")
    parser.add_argument("--provider-template-dir", help="Write no-secret env templates split by provider target.")
    parser.add_argument("--preserve-provider-templates", action="store_true", help="Do not overwrite existing provider templates.")
    parser.add_argument("--provider-template-index-out", help="Write an audit index for generated provider templates.")
    parser.add_argument("--provider-apply-plan-out", help="Write a redacted provider apply plan JSON.")
    parser.add_argument("--provider-apply-plan-markdown-out", help="Write a redacted provider apply plan Markdown file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_modes = [
        bool(args.verify_provider_apply_plan),
        bool(args.provider_apply_results_template_from_plan),
        bool(args.record_provider_apply_results_from_plan),
        bool(args.verify_provider_apply_results),
        bool(args.verify_provider_apply_workflow),
    ]
    if sum(1 for item in source_modes if item) > 1:
        print(
            "[external-gate-handoff] provider verification/template modes are mutually exclusive",
            file=sys.stderr,
        )
        return 2
    if args.require_ready_to_apply and not args.verify_provider_apply_plan:
        print(
            "[external-gate-handoff] --require-ready-to-apply requires --verify-provider-apply-plan",
            file=sys.stderr,
        )
        return 2
    if args.provider_apply_plan and not args.verify_provider_apply_results:
        print(
            "[external-gate-handoff] --provider-apply-plan requires --verify-provider-apply-results",
            file=sys.stderr,
        )
        return 2
    if (args.provider_apply_results or args.promotion_receipt or args.require_promotion_go) and not (
        args.verify_provider_apply_workflow
    ):
        print(
            "[external-gate-handoff] workflow artifact flags require --verify-provider-apply-workflow",
            file=sys.stderr,
        )
        return 2
    if args.execute_provider_apply_commands and not args.record_provider_apply_results_from_plan:
        print(
            "[external-gate-handoff] --execute-provider-apply-commands requires "
            "--record-provider-apply-results-from-plan",
            file=sys.stderr,
        )
        return 2
    if args.verify_provider_apply_plan:
        disallowed_outputs = any(
            (
                args.markdown_out,
                args.provider_template_dir,
                args.provider_template_index_out,
                args.provider_apply_plan_out,
                args.provider_apply_plan_markdown_out,
            )
        )
        if disallowed_outputs:
            print(
                "[external-gate-handoff] --verify-provider-apply-plan only accepts --json and --json-out outputs",
                file=sys.stderr,
            )
            return 2
        try:
            verification = verify_provider_apply_plan(
                args.verify_provider_apply_plan,
                require_ready_to_apply=args.require_ready_to_apply,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            verification = {
                "schema_version": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "provider_apply_plan_json": str(args.verify_provider_apply_plan),
                "require_ready_to_apply": args.require_ready_to_apply,
                "ready_to_apply": False,
                "operator_stage": "",
                "success_condition": PROVIDER_APPLY_PLAN_VERIFY_CONDITION
                if not args.require_ready_to_apply
                else PROVIDER_APPLY_PLAN_READY_CONDITION,
                "summary": {
                    "failure_count": 1,
                    "provider_count": 0,
                    "ready_provider_count": 0,
                    "blocked_provider_count": 0,
                    "provider_failure_count": 0,
                    "secret_marker_count": 0,
                },
                "secret_marker_names": [],
                "failures": [str(exc)],
                "providers": [],
            }
        if args.json:
            print(json.dumps(verification, indent=2))
        else:
            print_provider_apply_plan_verification_report(verification)
        if args.json_out:
            output_path = write_json_report(args.json_out, verification)
            print(f"[external-gate-handoff] provider apply plan verification written: {output_path}")
        return 0 if verification["ok"] else 1

    if args.provider_apply_results_template_from_plan:
        if not args.json_out:
            print(
                "[external-gate-handoff] --provider-apply-results-template-from-plan requires --json-out",
                file=sys.stderr,
            )
            return 2
        plan_path = Path(args.provider_apply_results_template_from_plan)
        plan = load_provider_apply_plan(plan_path)
        output_path = write_provider_apply_results_template(args.json_out, plan, plan_path=plan_path)
        print(f"[external-gate-handoff] provider apply results template written: {output_path}")
        return 0

    if args.record_provider_apply_results_from_plan:
        if not args.json_out:
            print(
                "[external-gate-handoff] --record-provider-apply-results-from-plan requires --json-out",
                file=sys.stderr,
            )
            return 2
        try:
            payload = record_provider_apply_results(
                args.record_provider_apply_results_from_plan,
                execute=args.execute_provider_apply_commands,
                timeout_seconds=args.provider_apply_command_timeout,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            payload = {
                "schema_version": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "execution_mode": "execute" if args.execute_provider_apply_commands else "dry_run",
                "provider_apply_plan_json": str(args.record_provider_apply_results_from_plan),
                "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
                "provider_count": 0,
                "command_count": 0,
                "results": [
                    {
                        "provider": "operator",
                        "command_id": "record_provider_apply_results",
                        "status": "failure",
                        "exit_code": None,
                        "started_at": "",
                        "finished_at": "",
                        "stdout_excerpt": "",
                        "stderr_excerpt": str(exc),
                    }
                ],
            }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_provider_apply_results_record_report(payload)
        output_path = write_json_report(args.json_out, payload)
        print(f"[external-gate-handoff] provider apply results receipt written: {output_path}")
        return 0 if payload["ok"] else 1

    if args.verify_provider_apply_workflow:
        try:
            verification = verify_provider_apply_workflow(
                args.verify_provider_apply_workflow,
                results_path=args.provider_apply_results,
                promotion_receipt_path=args.promotion_receipt,
                require_promotion_go=args.require_promotion_go,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            verification = {
                "schema_version": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "provider_apply_plan_json": str(args.verify_provider_apply_workflow),
                "provider_apply_results_json": str(args.provider_apply_results or ""),
                "promotion_receipt_json": str(args.promotion_receipt or ""),
                "artifact_resolution": {
                    "provider_apply_results_json": "argument" if args.provider_apply_results else "unresolved",
                    "promotion_receipt_json": "argument" if args.promotion_receipt else "unresolved",
                },
                "require_promotion_go": args.require_promotion_go,
                "success_condition": PROVIDER_APPLY_WORKFLOW_CONDITION,
                "operator_phase": "provider_apply_workflow_blocked",
                "ready_to_apply": False,
                "all_commands_succeeded": False,
                "promotion_receipt_ok": False,
                "summary": {
                    "failure_count": 1,
                    "plan_ok": False,
                    "results_ok": False,
                    "promotion_verification_ok": False,
                    "plan_failure_count": 1,
                    "results_failure_count": 0,
                    "results_command_failure_count": 0,
                    "promotion_failure_count": 0,
                },
                "failures": [str(exc)],
                "provider_apply_plan_verification": {},
                "provider_apply_results_verification": {},
                "post_apply_promotion_receipt_verification": {},
            }
        if args.json:
            print(json.dumps(verification, indent=2))
        else:
            print_provider_apply_workflow_verification_report(verification)
        if args.json_out:
            output_path = write_json_report(args.json_out, verification)
            print(f"[external-gate-handoff] provider apply workflow verification written: {output_path}")
        return 0 if verification["ok"] else 1

    if args.verify_provider_apply_results:
        if not args.provider_apply_plan:
            print(
                "[external-gate-handoff] --verify-provider-apply-results requires --provider-apply-plan",
                file=sys.stderr,
            )
            return 2
        try:
            verification = verify_provider_apply_results(
                args.verify_provider_apply_results,
                plan_path=args.provider_apply_plan,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            verification = {
                "schema_version": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "provider_apply_results_json": str(args.verify_provider_apply_results),
                "provider_apply_plan_json": str(args.provider_apply_plan),
                "success_condition": PROVIDER_APPLY_RESULTS_CONDITION,
                "all_commands_succeeded": False,
                "summary": {
                    "failure_count": 1,
                    "expected_command_count": 0,
                    "reported_command_count": 0,
                    "checked_command_count": 0,
                    "missing_command_count": 0,
                    "command_failure_count": 0,
                    "secret_marker_count": 0,
                },
                "secret_marker_names": [],
                "failures": [str(exc)],
                "commands": [],
            }
        if args.json:
            print(json.dumps(verification, indent=2))
        else:
            print_provider_apply_results_verification_report(verification)
        if args.json_out:
            output_path = write_json_report(args.json_out, verification)
            print(f"[external-gate-handoff] provider apply results verification written: {output_path}")
        return 0 if verification["ok"] else 1

    needs_provider_templates = any(
        (
            args.provider_template_index_out,
            args.provider_apply_plan_out,
            args.provider_apply_plan_markdown_out,
        )
    )
    if needs_provider_templates and not args.provider_template_dir:
        print(
            "[external-gate-handoff] provider template outputs require --provider-template-dir",
            file=sys.stderr,
        )
        return 2
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
    provider_paths: dict[str, Path] = {}
    if args.provider_template_dir:
        provider_paths = write_provider_templates(
            args.provider_template_dir,
            payload,
            overwrite=not args.preserve_provider_templates,
        )
        for provider, path in provider_paths.items():
            print(f"[external-gate-handoff] provider template written: {provider}={path}")
    if args.provider_template_index_out:
        index_path = write_provider_template_index(args.provider_template_index_out, payload, provider_paths)
        print(f"[external-gate-handoff] provider template index written: {index_path}")
    apply_plan_payload: dict[str, Any] | None = None
    if args.provider_apply_plan_out:
        apply_plan_payload = provider_apply_plan_payload(
            payload,
            provider_paths,
            plan_path=args.provider_apply_plan_out,
        )
        output_path = write_json_report(args.provider_apply_plan_out, apply_plan_payload)
        print(f"[external-gate-handoff] provider apply plan written: {output_path}")
    if args.provider_apply_plan_markdown_out:
        if apply_plan_payload is None:
            apply_plan_payload = provider_apply_plan_payload(payload, provider_paths)
        markdown_path = write_provider_apply_plan_markdown(args.provider_apply_plan_markdown_out, apply_plan_payload)
        print(f"[external-gate-handoff] provider apply plan markdown written: {markdown_path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
