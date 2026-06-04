from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_REQUIREMENTS = WORKSPACE_ROOT / "ops" / "references" / "autoresearch_objective_requirements.json"
ALLOWED_STATUSES = {"covered_current_cycle", "continuous", "blocked_external"}


def load_requirements(path: Path = DEFAULT_REQUIREMENTS) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("requirements root must be an object")
    return payload


def audit_requirements(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), "generated_at", errors)
    _require_string(payload.get("objective_original"), "objective_original", errors)
    policy = _validate_policy(payload.get("policy"), errors)
    completion_contract_path = _repo_relative_path(payload.get("completion_contract"), "completion_contract", errors)
    completion_criteria = _load_completion_criteria(completion_contract_path, workspace_root, errors)
    requirements = _validate_requirements(
        payload.get("requirements"),
        workspace_root,
        completion_criteria,
        errors,
    )
    status_counts = Counter(item["status"] for item in requirements)
    blocked = [item["id"] for item in requirements if item["status"] == "blocked_external"]
    continuous = [item["id"] for item in requirements if item["status"] == "continuous"]
    covered = [item["id"] for item in requirements if item["status"] == "covered_current_cycle"]
    cycle_prompt_covered = not errors and bool(requirements) and not [
        item["id"]
        for item in requirements
        if item["status"] not in {"covered_current_cycle", "continuous", "blocked_external"}
    ]
    global_objective_complete = (
        cycle_prompt_covered
        and not blocked
        and not continuous
        and bool(policy.get("global_completion_expected"))
    )
    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": datetime.now(UTC).isoformat(),
        "valid": not errors,
        "cycle_prompt_covered": cycle_prompt_covered,
        "global_objective_complete": global_objective_complete,
        "requirement_count": len(requirements),
        "status_counts": dict(sorted(status_counts.items())),
        "covered_current_cycle": covered,
        "continuous_requirements": continuous,
        "blocked_requirements": blocked,
        "errors": errors,
        "requirements": requirements,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AutoResearch Objective Coverage Audit",
        "",
        f"- Valid: `{str(report['valid']).lower()}`",
        f"- Cycle prompt covered: `{str(report['cycle_prompt_covered']).lower()}`",
        f"- Global objective complete: `{str(report['global_objective_complete']).lower()}`",
        f"- Requirements: `{report['requirement_count']}`",
        f"- Status counts: `{_format_counts(report['status_counts'])}`",
        "",
        "## Requirements",
        "",
        "| Requirement | Status | Criteria | Evidence paths |",
        "| --- | --- | ---: | ---: |",
    ]
    for item in report["requirements"]:
        lines.append(
            " | ".join(
                [
                    f"| `{item['id']}`",
                    f"`{item['status']}`",
                    f"`{len(item['completion_criteria'])}`",
                    f"`{len(item['evidence'])}` |",
                ]
            )
        )

    lines.extend(["", "## Continuous Requirements", ""])
    if report["continuous_requirements"]:
        lines.extend(f"- `{item}`" for item in report["continuous_requirements"])
    else:
        lines.append("- none")

    lines.extend(["", "## Blocked Requirements", ""])
    if report["blocked_requirements"]:
        lines.extend(f"- `{item}`" for item in report["blocked_requirements"])
    else:
        lines.append("- none")

    lines.extend(["", "## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def run(
    requirements_path: Path = DEFAULT_REQUIREMENTS,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    report = audit_requirements(load_requirements(requirements_path))
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(report))
    if not report["valid"]:
        raise ValueError("\n".join(report["errors"]))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate user prompt requirements against AutoResearch artifacts.")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args.requirements, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"autoresearch objective coverage audit failed: {exc}", file=sys.stderr)
        return 1
    print(
        "autoresearch objective coverage audit valid: "
        f"{report['requirement_count']} requirements, "
        f"cycle_prompt_covered={str(report['cycle_prompt_covered']).lower()}, "
        f"global_objective_complete={str(report['global_objective_complete']).lower()}"
    )
    return 0


def _validate_policy(value: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("policy must be an object")
        return {}
    if not isinstance(value.get("global_completion_expected"), bool):
        errors.append("policy.global_completion_expected must be a boolean")
    _require_string(value.get("reason"), "policy.reason", errors)
    return value


def _load_completion_criteria(path_text: str, workspace_root: Path, errors: list[str]) -> set[str]:
    if not path_text:
        return set()
    path = workspace_root / path_text
    if not path.exists():
        errors.append(f"completion_contract path does not exist: {path_text}")
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"completion_contract is not valid JSON: {exc}")
        return set()
    criteria = payload.get("criteria")
    if not isinstance(criteria, list):
        errors.append("completion_contract.criteria must be an array")
        return set()
    return {
        item["id"]
        for item in criteria
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    }


def _validate_requirements(
    value: Any,
    workspace_root: Path,
    completion_criteria: set[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append("requirements must be a non-empty array")
        return []
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"requirements[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        requirement_id = _require_string(item.get("id"), f"{prefix}.id", errors)
        if requirement_id:
            if requirement_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(requirement_id)
        status = _require_string(item.get("status"), f"{prefix}.status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        prompt_terms = _validate_string_list(item.get("prompt_terms"), f"{prefix}.prompt_terms", errors)
        _require_string(item.get("requirement"), f"{prefix}.requirement", errors)
        criteria = _validate_string_list(item.get("completion_criteria"), f"{prefix}.completion_criteria", errors)
        for criterion_id in criteria:
            if criterion_id not in completion_criteria:
                errors.append(f"{prefix}.completion_criteria unknown id: {criterion_id}")
        evidence = _validate_evidence(item.get("evidence"), f"{prefix}.evidence", workspace_root, errors)
        blockers = _validate_string_list(item.get("blockers", []), f"{prefix}.blockers", errors)
        if status == "blocked_external" and not blockers:
            errors.append(f"{prefix}.blockers must be non-empty when status is blocked_external")
        normalized.append(
            {
                "id": requirement_id,
                "status": status,
                "prompt_terms": prompt_terms,
                "completion_criteria": criteria,
                "evidence": evidence,
                "blockers": blockers,
                "residual_risk": item.get("residual_risk", ""),
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
        path_text = _repo_relative_path(item.get("path"), f"{prefix}.path", errors)
        path = workspace_root / path_text if path_text else workspace_root
        if path_text and not path.exists():
            errors.append(f"{prefix}.path does not exist: {path_text}")
        content = path.read_text(encoding="utf-8", errors="replace") if path_text and path.exists() and path.is_file() else ""
        terms = _validate_string_list(item.get("must_contain", []), f"{prefix}.must_contain", errors)
        for term in terms:
            if content and term not in content:
                errors.append(f"{prefix}.must_contain missing from {path_text}: {term}")
        normalized.append({"path": path_text, "term_count": len(terms)})
    return normalized


def _repo_relative_path(value: Any, field: str, errors: list[str]) -> str:
    text = _require_string(value, field, errors)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field} must be repo-relative")
        return ""
    return text


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
