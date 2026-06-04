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
                f"- Claim policy: {item['claim_policy']}",
                "",
                "Blocked until:",
            ]
        )
        lines.extend(f"- {text}" for text in item["blocked_until"])
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
    for item in handoff["boundaries"]:
        lines.extend([f"# Boundary: {item['title']}", f"# Status: {item['status']}"])
        for name in item["required_env"]:
            if name not in emitted:
                lines.append(f"{name}=")
                emitted.add(name)
        for name in item["optional_env_any_of"]:
            if name not in emitted:
                lines.append(f"# Optional alternative")
                lines.append(f"{name}=")
                emitted.add(name)
        lines.append("")
    return "\n".join(lines)


def run(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    env_template_out: Path | None = None,
) -> dict[str, Any]:
    handoff = build_handoff(registry_path)
    if json_out is not None:
        _write_json_atomic(json_out, handoff)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(handoff))
    if env_template_out is not None:
        _write_text_atomic(env_template_out, format_env_template(handoff))
    return handoff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a redacted external credential handoff package.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--env-template-out", type=Path)
    args = parser.parse_args(argv)
    try:
        handoff = run(
            args.registry,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            env_template_out=args.env_template_out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"external credential handoff failed: {exc}", file=sys.stderr)
        return 1
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


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
