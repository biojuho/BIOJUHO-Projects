from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_REGISTRY = WORKSPACE_ROOT / "ops" / "references" / "external_credential_boundaries.json"
ALLOWED_STATUSES = {
    "credential_gated",
    "external_auth_blocked",
    "future_scoped",
    "optional_token_absent",
}


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("registry root must be an object")
    return payload


def audit_registry(
    payload: dict[str, Any],
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), "generated_at", errors)
    _require_string(payload.get("objective"), "objective", errors)
    boundaries = _validate_boundaries(payload.get("boundaries"), workspace_root, env_map, errors)
    status_counts = Counter(item["status"] for item in boundaries)
    missing_required_env = sorted(
        {name for item in boundaries for name in item["missing_required_env"]}
    )
    optional_env_available = [
        item["id"]
        for item in boundaries
        if item["optional_env_any_of"] and item["optional_env_available"]
    ]
    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": datetime.now(UTC).isoformat(),
        "registry_generated_at": payload.get("generated_at"),
        "status": "pass" if not errors else "fail",
        "valid": not errors,
        "boundary_count": len(boundaries),
        "status_counts": dict(sorted(status_counts.items())),
        "missing_required_env": missing_required_env,
        "missing_required_env_count": len(missing_required_env),
        "optional_env_available_boundaries": optional_env_available,
        "errors": errors,
        "boundaries": boundaries,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# External Credential Boundary Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Boundaries: `{report['boundary_count']}`",
        f"- Status counts: `{_format_counts(report['status_counts'])}`",
        f"- Missing required env names: `{report['missing_required_env_count']}`",
        "",
        "## Boundaries",
        "",
        "| Boundary | Status | Required env missing | Optional env available | Evidence paths |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for boundary in report["boundaries"]:
        lines.append(
            " | ".join(
                [
                    f"| `{boundary['id']}`",
                    f"`{boundary['status']}`",
                    f"`{len(boundary['missing_required_env'])}`",
                    f"`{str(boundary['optional_env_available']).lower()}`",
                    f"`{boundary['evidence_count']}` |",
                ]
            )
        )

    lines.extend(["", "## Missing Required Env", ""])
    if report["missing_required_env"]:
        lines.extend(f"- `{name}`" for name in report["missing_required_env"])
    else:
        lines.append("- none")

    lines.extend(["", "## Claim Policies", ""])
    for boundary in report["boundaries"]:
        lines.extend(
            [
                f"### {boundary['id']}",
                "",
                f"- Owner: `{boundary['owner']}`",
                f"- Policy: {boundary['claim_policy']}",
                f"- Blocked until: {'; '.join(boundary['blocked_until'])}",
                "",
            ]
        )

    lines.extend(["## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def run(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    report = audit_registry(load_registry(registry_path))
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(report))
    if report["status"] != "pass":
        raise ValueError("\n".join(report["errors"]))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate external credential and operator-owned launch boundaries.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args.registry, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"external credential boundary audit failed: {exc}", file=sys.stderr)
        return 1
    print(
        "external credential boundary audit valid: "
        f"{report['boundary_count']} boundaries, "
        f"missing_required_env={report['missing_required_env_count']}"
    )
    return 0


def _validate_boundaries(
    value: Any,
    workspace_root: Path,
    env: Mapping[str, str],
    errors: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append("boundaries must be a non-empty array")
        return []

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"boundaries[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        boundary_id = _require_string(item.get("id"), f"{prefix}.id", errors)
        if boundary_id:
            if boundary_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(boundary_id)
        title = _require_string(item.get("title"), f"{prefix}.title", errors)
        status = _require_string(item.get("status"), f"{prefix}.status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        owner = _require_string(item.get("owner"), f"{prefix}.owner", errors)
        claim_policy = _require_string(item.get("claim_policy"), f"{prefix}.claim_policy", errors)
        if claim_policy and "do not claim" not in claim_policy.lower():
            errors.append(f"{prefix}.claim_policy must include 'do not claim'")
        blocked_until = _validate_string_list(item.get("blocked_until"), f"{prefix}.blocked_until", errors)
        required_env = _validate_string_list(item.get("required_env", []), f"{prefix}.required_env", errors)
        optional_env_any_of = _validate_string_list(
            item.get("optional_env_any_of", []),
            f"{prefix}.optional_env_any_of",
            errors,
        )
        evidence = _validate_evidence(item.get("evidence"), f"{prefix}.evidence", workspace_root, errors)
        missing_required_env = [name for name in required_env if not env.get(name)]
        optional_env_available = any(env.get(name) for name in optional_env_any_of)
        normalized.append(
            {
                "id": boundary_id,
                "title": title,
                "status": status,
                "owner": owner,
                "claim_policy": claim_policy,
                "blocked_until": blocked_until,
                "required_env": required_env,
                "missing_required_env": missing_required_env,
                "optional_env_any_of": optional_env_any_of,
                "optional_env_available": optional_env_available,
                "evidence_count": len(evidence),
            }
        )
    return normalized


def _validate_evidence(value: Any, field: str, workspace_root: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        path_text = _require_string(item.get("path"), f"{prefix}.path", errors)
        if path_text and not _is_repo_relative(path_text):
            errors.append(f"{prefix}.path must be repo-relative")
        path = workspace_root / path_text if path_text else workspace_root
        if path_text and not path.exists():
            errors.append(f"{prefix}.path does not exist: {path_text}")
        content = path.read_text(encoding="utf-8", errors="replace") if path_text and path.exists() and path.is_file() else ""
        required_terms = _validate_string_list(item.get("must_contain", []), f"{prefix}.must_contain", errors)
        for term in required_terms:
            if term not in content:
                errors.append(f"{prefix}.must_contain missing from {path_text}: {term}")
        normalized.append({"path": path_text, "term_count": len(required_terms)})
    return normalized


def _validate_timestamp(value: Any, field: str, errors: list[str]) -> None:
    text = _require_string(value, field, errors)
    if not text:
        return
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be ISO-8601")


def _validate_string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        result.append(item)
    return result


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value


def _is_repo_relative(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
