from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from external_credential_boundary_audit import DEFAULT_REGISTRY, audit_registry, load_registry  # noqa: E402


def build_handoff(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    registry = load_registry(registry_path)
    audit = audit_registry(registry, workspace_root=WORKSPACE_ROOT, env=env_map)
    boundaries = sorted(
        audit["boundaries"],
        key=lambda item: (0 if item["missing_required_env"] else 1, item["id"]),
    )
    required_env = sorted({name for item in boundaries for name in item["required_env"]})
    optional_env = sorted({name for item in boundaries for name in item["optional_env_any_of"]})
    status = "operator_action_required" if audit["missing_required_env"] else "ready_for_live_verification"
    unblock_queue = _build_unblock_queue(boundaries)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "registry_path": _repo_relative(registry_path),
        "registry_generated_at": audit["registry_generated_at"],
        "status": status,
        "boundary_count": audit["boundary_count"],
        "missing_required_env": audit["missing_required_env"],
        "missing_required_env_count": audit["missing_required_env_count"],
        "required_env": [
            {"name": name, "present": bool(env_map.get(name))}
            for name in required_env
        ],
        "optional_env_any_of": [
            {"name": name, "present": bool(env_map.get(name))}
            for name in optional_env
        ],
        "verification_sequence": [
            {"boundary_id": item["id"], "command": command}
            for item in boundaries
            for command in item["verification_commands"]
        ],
        "unblock_queue": unblock_queue,
        "boundaries": [
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "owner": item["owner"],
                "required_env": item["required_env"],
                "missing_required_env": item["missing_required_env"],
                "optional_env_any_of": item["optional_env_any_of"],
                "optional_env_available": item["optional_env_available"],
                "operator_approval_required": item["operator_approval_required"],
                "operator_approval_env": item["operator_approval_env"],
                "operator_approval_available": item["operator_approval_available"],
                "operator_consent_items": item["operator_consent_items"],
                "blocked_until": item["blocked_until"],
                "verification_commands": item["verification_commands"],
                "claim_policy": item["claim_policy"],
            }
            for item in boundaries
        ],
    }


def format_markdown(handoff: dict[str, Any]) -> str:
    lines = [
        "# External Credential Handoff",
        "",
        f"- Status: `{handoff['status']}`",
        f"- Boundaries: `{handoff['boundary_count']}`",
        f"- Missing required env names: `{handoff['missing_required_env_count']}`",
        "- Secret values: not emitted; this handoff contains env names only.",
        "",
        "## Missing Required Env",
        "",
    ]
    if handoff["missing_required_env"]:
        lines.extend(f"- `{name}`" for name in handoff["missing_required_env"])
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Prioritized Unblock Queue",
            "",
            "| Rank | Boundary | Operator action | Env names | Verify after unblock |",
            "| ---: | --- | --- | --- | --- |",
        ]
    )
    for item in handoff["unblock_queue"]:
        lines.append(
            " | ".join(
                [
                    f"| `{item['rank']}`",
                    f"`{item['boundary_id']}`",
                    item["operator_action"],
                    _format_env_names(item["env_names"]),
                    f"{_format_inline_commands(item['verify_after_unblock'])} |",
                ]
            )
        )

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "| Boundary | Status | Missing required env | Verification commands |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for item in handoff["boundaries"]:
        lines.append(
            " | ".join(
                [
                    f"| `{item['id']}`",
                    f"`{item['status']}`",
                    f"`{len(item['missing_required_env'])}`",
                    f"`{len(item['verification_commands'])}` |",
                ]
            )
        )

    lines.extend(["", "## Operator Verification", ""])
    for item in handoff["boundaries"]:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Boundary id: `{item['id']}`",
                f"- Owner: `{item['owner']}`",
                f"- Required env: {_format_env_names(item['required_env'])}",
                f"- Optional env: {_format_env_names(item['optional_env_any_of'])}",
                f"- Missing required env: {_format_env_names(item['missing_required_env'])}",
                f"- Consent items: `{len(item['operator_consent_items'])}`",
                f"- Claim policy: {item['claim_policy']}",
                "",
                "Blocked until:",
            ]
        )
        lines.extend(f"- {text}" for text in item["blocked_until"])
        if item["operator_consent_items"]:
            lines.extend(["", "Consent items:"])
            lines.extend(
                f"- `{consent['name']}` (`{consent['type']}`): {consent['reason']}"
                for consent in item["operator_consent_items"]
            )
        lines.extend(["", "Commands:"])
        lines.extend(f"- `{command}`" for command in item["verification_commands"])
        lines.append("")

    return "\n".join(lines)


def format_env_template(handoff: dict[str, Any]) -> str:
    lines = [
        "# External credential handoff env template",
        f"# Generated at: {handoff['generated_at']}",
        "# Fill values locally; do not commit populated secrets.",
        "",
    ]
    emitted: set[str] = set()
    boundary_by_id = {item["id"]: item for item in handoff["boundaries"]}
    for queue_item in handoff["unblock_queue"]:
        item = boundary_by_id[queue_item["boundary_id"]]
        lines.extend(
            [
                f"# Queue rank: {queue_item['rank']}",
                f"# Boundary: {item['title']}",
                f"# Status: {item['status']}",
            ]
        )
        for name in item["required_env"]:
            if name not in emitted:
                lines.append(f"{name}=")
                emitted.add(name)
        if item["operator_approval_env"] and item["operator_approval_env"] not in emitted:
            lines.append("# Non-secret operator approval marker")
            lines.append(f"{item['operator_approval_env']}=")
            emitted.add(item["operator_approval_env"])
        for name in item["optional_env_any_of"]:
            if name not in emitted:
                lines.append(f"# Optional alternative")
                lines.append(f"{name}=")
                emitted.add(name)
        lines.append("")
    return "\n".join(lines)


def build_operator_checklist(handoff: dict[str, Any]) -> dict[str, Any]:
    boundary_by_id = {item["id"]: item for item in handoff["boundaries"]}
    items = [
        _operator_checklist_item(boundary_by_id[queue_item["boundary_id"]], queue_item)
        for queue_item in handoff["unblock_queue"]
    ]
    ready_count = sum(1 for item in items if item["ready_to_execute"])
    blocked_count = len(items) - ready_count
    next_action = next((item for item in items if not item["ready_to_execute"]), None)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "handoff_generated_at": handoff["generated_at"],
        "registry_path": handoff["registry_path"],
        "status": "operator_action_required" if blocked_count else "ready_for_live_verification",
        "summary": {
            "item_count": len(items),
            "ready_to_execute": ready_count,
            "blocked": blocked_count,
            "next_boundary_id": next_action["boundary_id"] if next_action else None,
            "secret_values_emitted": False,
        },
        "items": items,
    }


def format_operator_checklist_markdown(checklist: dict[str, Any]) -> str:
    summary = checklist["summary"]
    lines = [
        "# External Credential Operator Checklist",
        "",
        f"- Status: `{checklist['status']}`",
        f"- Items: `{summary['item_count']}`",
        f"- Ready to execute: `{summary['ready_to_execute']}`",
        f"- Blocked: `{summary['blocked']}`",
        f"- Next boundary: `{summary['next_boundary_id'] or 'none'}`",
        "- Secret values: not emitted; checklist contains env names only.",
        "",
        "## Queue",
        "",
        "| Rank | Boundary | Live status | Ready now | Blocked reason | Env names | Commands |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    for item in checklist["items"]:
        lines.append(
            " | ".join(
                [
                    f"| `{item['rank']}`",
                    f"`{item['boundary_id']}`",
                    f"`{item['live_status']}`",
                    f"`{str(item['ready_to_execute']).lower()}`",
                    item["blocked_reason"] or "none",
                    _format_env_names(item["env_names"]),
                    f"`{len(item['verify_after_unblock'])}` |",
                ]
            )
        )

    lines.extend(["", "## Boundary Steps", ""])
    for item in checklist["items"]:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Boundary id: `{item['boundary_id']}`",
                f"- Registry status: `{item['registry_status']}`",
                f"- Live status: `{item['live_status']}`",
                f"- Ready to execute: `{str(item['ready_to_execute']).lower()}`",
                f"- Operator action: {item['operator_action']}",
                f"- Claim policy: {item['claim_policy']}",
                "",
                "Checklist:",
            ]
        )
        lines.extend(
            f"- `{step['state']}` {step['label']}: {step['detail']}"
            for step in item["checklist"]
        )
        lines.extend(["", "Verify after unblock:"])
        lines.extend(f"- `{command}`" for command in item["verify_after_unblock"])
        lines.append("")
    return "\n".join(lines)


def run(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    env_template_out: Path | None = None,
    operator_checklist_json_out: Path | None = None,
    operator_checklist_markdown_out: Path | None = None,
) -> dict[str, Any]:
    handoff = build_handoff(registry_path)
    if json_out is not None:
        _write_json_atomic(json_out, handoff)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(handoff))
    if env_template_out is not None:
        _write_text_atomic(env_template_out, format_env_template(handoff))
    if operator_checklist_json_out is not None or operator_checklist_markdown_out is not None:
        checklist = build_operator_checklist(handoff)
        if operator_checklist_json_out is not None:
            _write_json_atomic(operator_checklist_json_out, checklist)
        if operator_checklist_markdown_out is not None:
            _write_text_atomic(operator_checklist_markdown_out, format_operator_checklist_markdown(checklist))
    return handoff


def check_outputs(
    handoff: dict[str, Any],
    *,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
    env_template_path: Path | None = None,
    operator_checklist_json_path: Path | None = None,
    operator_checklist_markdown_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    checklist = build_operator_checklist(handoff)
    if json_path is not None:
        try:
            actual_json = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{json_path} is not readable JSON: {exc}")
        else:
            if _normalize_generated_at(actual_json) != _normalize_generated_at(handoff):
                errors.append(f"{json_path} is stale; regenerate the credential handoff JSON")
    if markdown_path is not None:
        try:
            actual_markdown = markdown_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{markdown_path} is not readable: {exc}")
        else:
            expected_markdown = format_markdown(handoff)
            if _normalize_newlines(actual_markdown) != _normalize_newlines(expected_markdown):
                errors.append(f"{markdown_path} is stale; regenerate the credential handoff Markdown")
    if env_template_path is not None:
        try:
            actual_template = env_template_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{env_template_path} is not readable: {exc}")
        else:
            expected_template = format_env_template(handoff)
            if _normalize_env_template(actual_template) != _normalize_env_template(expected_template):
                errors.append(f"{env_template_path} is stale; regenerate the credential handoff env template")
    if operator_checklist_json_path is not None:
        try:
            actual_checklist_json = json.loads(operator_checklist_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{operator_checklist_json_path} is not readable JSON: {exc}")
        else:
            if _normalize_generated_at(actual_checklist_json) != _normalize_generated_at(checklist):
                errors.append(
                    f"{operator_checklist_json_path} is stale; regenerate the operator checklist JSON"
                )
    if operator_checklist_markdown_path is not None:
        try:
            actual_checklist_markdown = operator_checklist_markdown_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{operator_checklist_markdown_path} is not readable: {exc}")
        else:
            expected_checklist_markdown = format_operator_checklist_markdown(checklist)
            if _normalize_newlines(actual_checklist_markdown) != _normalize_newlines(expected_checklist_markdown):
                errors.append(
                    f"{operator_checklist_markdown_path} is stale; regenerate the operator checklist Markdown"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a redacted external credential handoff package.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--env-template-out", type=Path)
    parser.add_argument("--operator-checklist-json-out", type=Path)
    parser.add_argument("--operator-checklist-markdown-out", type=Path)
    parser.add_argument("--check-json", type=Path)
    parser.add_argument("--check-markdown", type=Path)
    parser.add_argument("--check-env-template", type=Path)
    parser.add_argument("--check-operator-checklist-json", type=Path)
    parser.add_argument("--check-operator-checklist-markdown", type=Path)
    args = parser.parse_args(argv)
    try:
        check_requested = any(
            [
                args.check_json,
                args.check_markdown,
                args.check_env_template,
                args.check_operator_checklist_json,
                args.check_operator_checklist_markdown,
            ]
        )
        handoff = build_handoff(args.registry, env={} if check_requested else None)
        if args.json_out is not None:
            _write_json_atomic(args.json_out, handoff)
        if args.markdown_out is not None:
            _write_text_atomic(args.markdown_out, format_markdown(handoff))
        if args.env_template_out is not None:
            _write_text_atomic(args.env_template_out, format_env_template(handoff))
        if args.operator_checklist_json_out is not None or args.operator_checklist_markdown_out is not None:
            checklist = build_operator_checklist(handoff)
            if args.operator_checklist_json_out is not None:
                _write_json_atomic(args.operator_checklist_json_out, checklist)
            if args.operator_checklist_markdown_out is not None:
                _write_text_atomic(
                    args.operator_checklist_markdown_out,
                    format_operator_checklist_markdown(checklist),
                )
        errors = check_outputs(
            handoff,
            json_path=args.check_json,
            markdown_path=args.check_markdown,
            env_template_path=args.check_env_template,
            operator_checklist_json_path=args.check_operator_checklist_json,
            operator_checklist_markdown_path=args.check_operator_checklist_markdown,
        )
        if errors:
            raise ValueError("\n".join(errors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"external credential handoff failed: {exc}", file=sys.stderr)
        return 1
    if any([args.check_json, args.check_markdown, args.check_env_template]):
        print(
            "external credential handoff check valid: "
            f"{handoff['boundary_count']} boundaries, "
            f"status={handoff['status']}, "
            f"missing_required_env={handoff['missing_required_env_count']}"
        )
        return 0
    print(
        "external credential handoff generated: "
        f"{handoff['boundary_count']} boundaries, "
        f"status={handoff['status']}, "
        f"missing_required_env={handoff['missing_required_env_count']}"
    )
    return 0


def _format_env_names(names: list[str]) -> str:
    if not names:
        return "none"
    return ", ".join(f"`{name}`" for name in names)


def _format_inline_commands(commands: list[str]) -> str:
    if not commands:
        return "none"
    return "<br>".join(f"`{command}`" for command in commands)


def _build_unblock_queue(boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = sorted(boundaries, key=_unblock_sort_key)
    return [
        {
            "rank": index + 1,
            "boundary_id": item["id"],
            "title": item["title"],
            "status": item["status"],
            "operator_action": _operator_action(item),
            "env_names": _queue_env_names(item),
            "operator_consent_items": item["operator_consent_items"],
            "verify_after_unblock": item["verification_commands"],
            "claim_policy": item["claim_policy"],
        }
        for index, item in enumerate(queue)
    ]


def _unblock_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    status_priority = {
        "external_auth_blocked": 0,
        "optional_token_absent": 1,
        "credential_gated": 2,
        "future_scoped": 3,
    }
    if item["missing_required_env"]:
        env_gap_priority = 0
    elif item["optional_env_any_of"]:
        env_gap_priority = 1
    else:
        env_gap_priority = 2
    return (status_priority.get(item["status"], 99), env_gap_priority, item["id"])


def _operator_action(item: dict[str, Any]) -> str:
    blockers = "; ".join(value.rstrip(".") for value in item["blocked_until"])
    if item["missing_required_env"]:
        return "Set required env and complete operator approval: " + blockers
    if item["operator_approval_required"] and not item["operator_approval_available"]:
        return "Set operator approval marker after runtime/policy decision: " + item["operator_approval_env"]
    if item["optional_env_any_of"] and not item["optional_env_available"]:
        return "Set one optional token/env value, then rerun verification: " + ", ".join(item["optional_env_any_of"])
    return "Choose the runtime or policy decision, then rerun verification: " + blockers


def _queue_env_names(item: dict[str, Any]) -> list[str]:
    names = [*item["required_env"], *item["optional_env_any_of"]]
    if item.get("operator_approval_env"):
        names.append(item["operator_approval_env"])
    return list(dict.fromkeys(names))


def _operator_checklist_item(boundary: dict[str, Any], queue_item: dict[str, Any]) -> dict[str, Any]:
    live_status = _checklist_live_status(boundary)
    ready_to_execute = live_status == "ready_for_execution"
    blocked_reason = "" if ready_to_execute else _checklist_blocked_reason(boundary, live_status)
    return {
        "rank": queue_item["rank"],
        "boundary_id": boundary["id"],
        "title": boundary["title"],
        "owner": boundary["owner"],
        "registry_status": boundary["status"],
        "live_status": live_status,
        "ready_to_execute": ready_to_execute,
        "blocked_reason": blocked_reason,
        "operator_action": queue_item["operator_action"],
        "required_env": boundary["required_env"],
        "missing_required_env": boundary["missing_required_env"],
        "optional_env_any_of": boundary["optional_env_any_of"],
        "optional_env_available": boundary["optional_env_available"],
        "operator_approval_required": boundary["operator_approval_required"],
        "operator_approval_env": boundary["operator_approval_env"],
        "operator_approval_available": boundary["operator_approval_available"],
        "operator_consent_items": boundary["operator_consent_items"],
        "env_names": queue_item["env_names"],
        "verify_after_unblock": queue_item["verify_after_unblock"],
        "claim_policy": boundary["claim_policy"],
        "checklist": _operator_checklist_steps(boundary, live_status),
    }


def _checklist_live_status(boundary: dict[str, Any]) -> str:
    if boundary["missing_required_env"]:
        return "blocked_missing_required_env"
    if boundary["operator_approval_required"] and not boundary["operator_approval_available"]:
        return "blocked_operator_approval"
    if (
        boundary["operator_approval_required"]
        and boundary["optional_env_any_of"]
        and not boundary["optional_env_available"]
    ):
        return "blocked_missing_optional_env"
    if (
        boundary["status"] == "optional_token_absent"
        and boundary["optional_env_any_of"]
        and not boundary["optional_env_available"]
    ):
        return "blocked_missing_optional_env"
    return "ready_for_execution"


def _checklist_blocked_reason(boundary: dict[str, Any], live_status: str) -> str:
    if live_status == "blocked_missing_required_env":
        return "missing required env: " + ", ".join(boundary["missing_required_env"])
    if live_status == "blocked_missing_optional_env":
        return "missing optional env: " + ", ".join(boundary["optional_env_any_of"])
    if live_status == "blocked_operator_approval":
        return "missing operator approval marker: " + boundary["operator_approval_env"]
    blockers = "; ".join(value.rstrip(".") for value in boundary["blocked_until"])
    return blockers or live_status


def _operator_checklist_steps(boundary: dict[str, Any], live_status: str) -> list[dict[str, str]]:
    required_detail = _plain_env_names(boundary["required_env"])
    optional_detail = _plain_env_names(boundary["optional_env_any_of"])
    approval_detail = boundary["operator_approval_env"] or "none required"
    return [
        {
            "id": "required_env",
            "state": "missing" if boundary["missing_required_env"] else "ready",
            "label": "Required env",
            "detail": required_detail if boundary["required_env"] else "none required",
        },
        {
            "id": "optional_env",
            "state": "blocked" if live_status == "blocked_missing_optional_env" else "not_blocking",
            "label": "Optional env",
            "detail": optional_detail if boundary["optional_env_any_of"] else "none",
        },
        {
            "id": "operator_approval",
            "state": _operator_approval_step_state(boundary),
            "label": "Operator approval",
            "detail": "; ".join(value.rstrip(".") for value in boundary["blocked_until"]),
        },
        {
            "id": "operator_approval_marker",
            "state": "ready" if boundary["operator_approval_available"] else "blocked",
            "label": "Operator approval marker",
            "detail": approval_detail,
        },
        {
            "id": "operator_consent_items",
            "state": (
                "blocked"
                if boundary["operator_consent_items"] and not boundary["operator_approval_available"]
                else "ready"
            ),
            "label": "Operator consent items",
            "detail": _plain_consent_item_names(boundary["operator_consent_items"]),
        },
        {
            "id": "verify_commands",
            "state": "ready" if live_status == "ready_for_execution" else "blocked",
            "label": "Verification commands",
            "detail": f"{len(boundary['verification_commands'])} command(s)",
        },
    ]


def _operator_approval_step_state(boundary: dict[str, Any]) -> str:
    if not boundary["operator_approval_required"]:
        return "not_blocking"
    return "ready" if boundary["operator_approval_available"] else "blocked"


def _plain_env_names(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def _plain_consent_item_names(items: list[dict[str, str]]) -> str:
    return ", ".join(item["name"] for item in items) if items else "none"


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _normalize_generated_at(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<ignored>" if key in {"generated_at", "handoff_generated_at"} else _normalize_generated_at(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_generated_at(item) for item in value]
    return value


def _normalize_env_template(value: str) -> str:
    lines = _normalize_newlines(value).split("\n")
    return "\n".join(
        "# Generated at: <ignored>" if line.startswith("# Generated at:") else line
        for line in lines
    )


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
