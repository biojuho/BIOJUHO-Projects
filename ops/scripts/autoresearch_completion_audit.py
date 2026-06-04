from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_CONTRACT = WORKSPACE_ROOT / "ops" / "references" / "autoresearch_completion_contract.json"
ALLOWED_STATUSES = {"covered", "partial", "blocked", "future_scoped", "watch"}


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("contract root must be an object")
    return payload


def audit_contract(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), errors)
    _require_string(payload.get("objective"), "objective", errors)
    policy = _validate_policy(payload.get("global_completion_policy"), errors)
    criteria = _validate_criteria(payload.get("criteria"), workspace_root, errors)

    status_counts = Counter(item["status"] for item in criteria)
    missing_required = [
        item["id"]
        for item in criteria
        if item["required"] and item["status"] != "covered"
    ]
    explicit_blockers = [
        item["id"]
        for item in criteria
        if item["status"] in {"blocked", "future_scoped", "watch"}
    ]
    cycle_evidence_ready = not errors and not missing_required
    global_objective_complete = (
        cycle_evidence_ready
        and bool(policy.get("can_mark_complete"))
        and not bool(policy.get("open_ended_until_user_stop"))
        and not explicit_blockers
    )

    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "objective": payload.get("objective"),
        "valid": not errors,
        "cycle_evidence_ready": cycle_evidence_ready,
        "global_objective_complete": global_objective_complete,
        "status_counts": dict(sorted(status_counts.items())),
        "criterion_count": len(criteria),
        "missing_required": missing_required,
        "explicit_blockers": explicit_blockers,
        "errors": errors,
        "criteria": criteria,
    }


def format_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# AutoResearch Completion Audit Summary",
        "",
        f"- Valid: `{str(summary['valid']).lower()}`",
        f"- Cycle evidence ready: `{str(summary['cycle_evidence_ready']).lower()}`",
        f"- Global objective complete: `{str(summary['global_objective_complete']).lower()}`",
        f"- Criteria: `{summary['criterion_count']}`",
        f"- Status counts: `{_format_counts(summary['status_counts'])}`",
        "",
        "## Missing Required",
        "",
    ]
    if summary["missing_required"]:
        lines.extend(f"- `{item}`" for item in summary["missing_required"])
    else:
        lines.append("- none")

    lines.extend(["", "## Explicit Blockers", ""])
    if summary["explicit_blockers"]:
        lines.extend(f"- `{item}`" for item in summary["explicit_blockers"])
    else:
        lines.append("- none")

    lines.extend(["", "## Criteria", ""])
    for item in summary["criteria"]:
        lines.extend(
            [
                f"### {item['id']}",
                "",
                f"- Required: `{str(item['required']).lower()}`",
                f"- Status: `{item['status']}`",
                f"- Evidence paths: `{len(item['evidence'])}`",
                "",
            ]
        )

    if summary["errors"]:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error}" for error in summary["errors"])
        lines.append("")

    return "\n".join(lines)


def run(contract_path: Path, *, json_out: Path | None = None, markdown_out: Path | None = None) -> dict[str, Any]:
    payload = load_contract(contract_path)
    summary = audit_contract(payload)
    if json_out is not None:
        _write_json_atomic(json_out, summary)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(summary))
    if not summary["valid"]:
        raise ValueError("\n".join(summary["errors"]))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate AutoResearch objective-to-artifact completion evidence.")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.contract, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"autoresearch completion audit failed: {exc}", file=sys.stderr)
        return 1
    print(
        "autoresearch completion audit valid: "
        f"{summary['criterion_count']} criteria, "
        f"cycle_evidence_ready={str(summary['cycle_evidence_ready']).lower()}, "
        f"global_objective_complete={str(summary['global_objective_complete']).lower()}"
    )
    return 0


def _validate_policy(value: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("global_completion_policy must be an object")
        return {}
    for key in ["open_ended_until_user_stop", "can_mark_complete"]:
        if not isinstance(value.get(key), bool):
            errors.append(f"global_completion_policy.{key} must be a boolean")
    _require_string(value.get("reason"), "global_completion_policy.reason", errors)
    return value


def _validate_criteria(value: Any, workspace_root: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append("criteria must be a non-empty array")
        return []

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"criteria[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        criterion_id = _require_string(item.get("id"), f"{prefix}.id", errors)
        if criterion_id:
            if criterion_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(criterion_id)
        _require_string(item.get("requirement"), f"{prefix}.requirement", errors)
        required = item.get("required")
        if not isinstance(required, bool):
            errors.append(f"{prefix}.required must be a boolean")
            required = False
        status = _require_string(item.get("status"), f"{prefix}.status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        evidence = _validate_evidence(item.get("evidence"), f"{prefix}.evidence", workspace_root, errors)
        normalized.append(
            {
                "id": criterion_id,
                "required": required,
                "status": status,
                "evidence": evidence,
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
        required_terms = item.get("must_contain", [])
        if not isinstance(required_terms, list):
            errors.append(f"{prefix}.must_contain must be an array when present")
            required_terms = []
        for term_index, term in enumerate(required_terms):
            if not isinstance(term, str) or not term:
                errors.append(f"{prefix}.must_contain[{term_index}] must be a non-empty string")
                continue
            if content and term not in content:
                errors.append(f"{prefix}.must_contain[{term_index}] missing from {path_text}: {term}")
        git_freshness = item.get("git_freshness")
        if git_freshness is not None:
            _validate_git_freshness(git_freshness, f"{prefix}.git_freshness", workspace_root, errors)
        normalized.append(
            {
                "path": path_text,
                "term_count": len(required_terms),
                "git_freshness": bool(git_freshness),
            }
        )
    return normalized


def _validate_git_freshness(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object when present")
        return

    proof_commit = _require_string(value.get("proof_commit"), f"{field}.proof_commit", errors)
    remote_ref = _require_string(value.get("remote_ref"), f"{field}.remote_ref", errors)
    allowed_paths = value.get("allowed_paths_since_proof", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        errors.append(f"{field}.allowed_paths_since_proof must be a non-empty array")
        allowed_paths = []
    normalized_allowed: list[str] = []
    for index, path_text in enumerate(allowed_paths):
        if not isinstance(path_text, str) or not path_text.strip():
            errors.append(f"{field}.allowed_paths_since_proof[{index}] must be a non-empty string")
            continue
        normalized = _normalize_git_path(path_text)
        if normalized.startswith("../") or normalized == "..":
            errors.append(f"{field}.allowed_paths_since_proof[{index}] must be repo-relative")
            continue
        normalized_allowed.append(normalized)

    if not proof_commit or not remote_ref:
        return

    ancestor = _run_git(["merge-base", "--is-ancestor", proof_commit, remote_ref], workspace_root)
    if ancestor.returncode != 0:
        detail = ancestor.stderr.strip() or ancestor.stdout.strip() or f"exit {ancestor.returncode}"
        errors.append(f"{field}.proof_commit is not an ancestor of {remote_ref}: {detail}")
        return

    changed = _run_git(["diff", "--name-only", f"{proof_commit}..{remote_ref}"], workspace_root)
    if changed.returncode != 0:
        detail = changed.stderr.strip() or changed.stdout.strip() or f"exit {changed.returncode}"
        errors.append(f"{field} could not inspect changed paths since proof commit: {detail}")
        return

    changed_paths = [_normalize_git_path(line) for line in changed.stdout.splitlines() if line.strip()]
    disallowed = [
        path for path in changed_paths if not _is_allowed_since_proof(path, normalized_allowed)
    ]
    if disallowed:
        joined = ", ".join(disallowed[:10])
        if len(disallowed) > 10:
            joined += f", ... ({len(disallowed)} total)"
        errors.append(f"{field} has non-evidence changes after proof commit: {joined}")


def _run_git(args: list[str], workspace_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _normalize_git_path(path_text: str) -> str:
    return path_text.strip().replace("\\", "/").lstrip("./")


def _is_allowed_since_proof(path_text: str, allowed_paths: list[str]) -> bool:
    for allowed in allowed_paths:
        if allowed.endswith("/"):
            if path_text.startswith(allowed):
                return True
        elif path_text == allowed:
            return True
    return False


def _validate_timestamp(value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append("generated_at must be a non-empty ISO timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("generated_at must be parseable as ISO datetime")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append("generated_at must include a timezone offset")


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _is_repo_relative(path_text: str) -> bool:
    path = Path(path_text)
    return not path.is_absolute() and ".." not in path.parts


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
