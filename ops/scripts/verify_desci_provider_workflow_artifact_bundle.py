from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = "var/desci-provider-workflow-artifact-index-machine.json"
DEFAULT_JSON_OUT = "var/desci-provider-workflow-artifact-bundle-verify.json"
DEFAULT_MARKDOWN_OUT = "var/desci-provider-workflow-artifact-bundle-verify.md"

SECRET_PATTERNS = {
    "stripe_secret_key": re.compile(r"sk_(?:live|test)_[A-Za-z0-9_/-]+"),
    "stripe_webhook_secret": re.compile(r"whsec_[A-Za-z0-9_/-]+"),
    "github_token": re.compile(r"(?:github_pat|gh[pousr])_[A-Za-z0-9_/-]+"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]+"),
    "credential_url": re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|redis|amqp)://[^@\s\"']+:[^@\s\"']+@"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_index(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _secret_marker_names(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def _candidate_paths(indexed_path: str, *, artifact_root: Path) -> list[tuple[str, Path]]:
    raw_path = Path(indexed_path)
    if raw_path.is_absolute():
        return [("absolute", raw_path)]
    candidates: list[tuple[str, Path]] = [("index_path", artifact_root / raw_path)]
    parts = raw_path.parts
    if parts and parts[0] == "var":
        candidates.append(("stripped_var_prefix", artifact_root / Path(*parts[1:])))
    candidates.append(("basename", artifact_root / raw_path.name))
    seen: set[Path] = set()
    deduped: list[tuple[str, Path]] = []
    for source, path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append((source, path))
    return deduped


def _resolve_artifact_path(indexed_path: str, *, artifact_root: Path) -> tuple[str, Path]:
    candidates = _candidate_paths(indexed_path, artifact_root=artifact_root)
    for source, path in candidates:
        if path.is_file():
            return source, path
    return candidates[0] if candidates else ("missing", artifact_root / indexed_path)


def _verify_artifact_entry(item: dict[str, Any], *, artifact_root: Path) -> dict[str, Any]:
    indexed_path = str(item.get("path") or "")
    required = item.get("required_for_complete_bundle") is True
    expected_exists = item.get("exists") is True
    expected_size = item.get("size_bytes")
    expected_sha256 = str(item.get("sha256") or "")
    resolution_source, resolved_path = _resolve_artifact_path(indexed_path, artifact_root=artifact_root)
    current_exists = resolved_path.is_file()
    failures: list[str] = []
    secret_markers: list[str] = []
    current_size: int | None = None
    current_sha256: str | None = None

    if not item.get("id"):
        failures.append("artifact id is required")
    if not indexed_path:
        failures.append("artifact path is required")
    if required and expected_exists is not True:
        failures.append("required artifact index must report exists=true")
    if current_exists != expected_exists:
        failures.append("artifact exists state changed")
    if required and not current_exists:
        failures.append("required artifact is missing")
    if current_exists:
        current_size = resolved_path.stat().st_size
        current_sha256 = sha256_file(resolved_path)
        secret_markers = _secret_marker_names(resolved_path)
        if expected_size is None:
            failures.append("artifact expected size is missing")
        elif int(expected_size) != current_size:
            failures.append("artifact byte size mismatch")
        if not expected_sha256:
            failures.append("artifact expected sha256 is missing")
        elif expected_sha256 != current_sha256:
            failures.append("artifact sha256 mismatch")
        if secret_markers:
            failures.append("artifact contains secret-shaped markers")

    return {
        "id": item.get("id"),
        "path": indexed_path,
        "resolved_path": str(resolved_path),
        "resolution_source": resolution_source,
        "required_for_complete_bundle": required,
        "ok": not failures,
        "expected_exists": expected_exists,
        "current_exists": current_exists,
        "expected_size_bytes": expected_size,
        "current_size_bytes": current_size,
        "expected_sha256": expected_sha256,
        "current_sha256": current_sha256,
        "secret_marker_names": secret_markers,
        "secret_marker_count": len(secret_markers),
        "failures": failures,
    }


def verify_bundle(
    *,
    index_path: str | Path,
    artifact_root: str | Path = ".",
    require_complete_bundle: bool = True,
    require_workflow_ok: bool = False,
) -> dict[str, Any]:
    index = load_index(index_path)
    root = Path(artifact_root)
    artifacts = [item for item in _as_list(index.get("artifacts")) if isinstance(item, dict)]
    checked_artifacts = [_verify_artifact_entry(item, artifact_root=root) for item in artifacts]
    workflow = _as_dict(index.get("provider_apply_workflow"))
    failures: list[str] = []

    if index.get("schema_version") != 1:
        failures.append("artifact index must be schema_version=1")
    if not artifacts:
        failures.append("artifact index must include artifacts")
    if require_complete_bundle and index.get("all_required_artifacts_present") is not True:
        failures.append("artifact index all_required_artifacts_present must be true")
    if require_complete_bundle and int(index.get("missing_artifact_count") or 0) != 0:
        failures.append("artifact index missing_artifact_count must be 0")
    first_decision_artifact = str(index.get("first_decision_artifact") or "")
    if not first_decision_artifact:
        failures.append("artifact index first_decision_artifact is required")
    elif first_decision_artifact not in {str(item.get("path") or "") for item in artifacts}:
        failures.append("first_decision_artifact must be included in artifacts")
    if require_workflow_ok and workflow.get("ok") is not True:
        failures.append("provider apply workflow must be ok when require_workflow_ok is set")

    artifact_failure_count = sum(1 for item in checked_artifacts if item.get("ok") is not True)
    missing_required_count = sum(
        1
        for item in checked_artifacts
        if item.get("required_for_complete_bundle") is True and item.get("current_exists") is not True
    )
    digest_mismatch_count = sum(
        1 for item in checked_artifacts if "artifact sha256 mismatch" in _as_list(item.get("failures"))
    )
    size_mismatch_count = sum(
        1 for item in checked_artifacts if "artifact byte size mismatch" in _as_list(item.get("failures"))
    )
    secret_marker_count = sum(int(item.get("secret_marker_count") or 0) for item in checked_artifacts)
    required_artifact_count = sum(1 for item in checked_artifacts if item.get("required_for_complete_bundle") is True)

    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "ok": not failures and artifact_failure_count == 0,
        "index_path": str(index_path),
        "artifact_root": str(artifact_root),
        "require_complete_bundle": require_complete_bundle,
        "require_workflow_ok": require_workflow_ok,
        "first_decision_artifact": first_decision_artifact,
        "index_complete_bundle": index.get("all_required_artifacts_present") is True,
        "provider_apply_workflow": {
            "ok": workflow.get("ok"),
            "operator_phase": str(workflow.get("operator_phase") or ""),
            "ready_to_apply": workflow.get("ready_to_apply"),
            "all_commands_succeeded": workflow.get("all_commands_succeeded"),
            "promotion_receipt_ok": workflow.get("promotion_receipt_ok"),
            "failure_count": workflow.get("failure_count"),
            "results_command_failure_count": workflow.get("results_command_failure_count"),
        },
        "summary": {
            "failure_count": len(failures),
            "artifact_count": len(checked_artifacts),
            "required_artifact_count": required_artifact_count,
            "artifact_failure_count": artifact_failure_count,
            "missing_required_count": missing_required_count,
            "digest_mismatch_count": digest_mismatch_count,
            "size_mismatch_count": size_mismatch_count,
            "secret_marker_count": secret_marker_count,
        },
        "failures": failures,
        "artifacts": checked_artifacts,
    }


def _format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "unknown" if value is None else str(value)


def render_markdown_summary(payload: dict[str, Any]) -> str:
    summary = _as_dict(payload.get("summary"))
    workflow = _as_dict(payload.get("provider_apply_workflow"))
    lines = [
        "## DeSci Provider Workflow Artifact Bundle Verification",
        "",
        f"- OK: `{_format_bool(payload.get('ok'))}`",
        f"- Index: `{payload.get('index_path')}`",
        f"- Artifact root: `{payload.get('artifact_root')}`",
        f"- Complete bundle required: `{_format_bool(payload.get('require_complete_bundle'))}`",
        f"- Workflow go required: `{_format_bool(payload.get('require_workflow_ok'))}`",
        f"- Index complete bundle: `{_format_bool(payload.get('index_complete_bundle'))}`",
        f"- First decision artifact: `{payload.get('first_decision_artifact') or 'missing'}`",
        f"- Provider workflow ok: `{_format_bool(workflow.get('ok'))}`",
        f"- Provider workflow phase: `{workflow.get('operator_phase') or 'unknown'}`",
        f"- Artifact failures: `{summary.get('artifact_failure_count', 0)}`",
        f"- Missing required artifacts: `{summary.get('missing_required_count', 0)}`",
        f"- Digest mismatches: `{summary.get('digest_mismatch_count', 0)}`",
        f"- Size mismatches: `{summary.get('size_mismatch_count', 0)}`",
        f"- Secret marker count: `{summary.get('secret_marker_count', 0)}`",
        "",
        "| Artifact | Required | Exists | Size OK | SHA OK | Markers |",
        "|---|---|---|---|---|---:|",
    ]
    for item in _as_list(payload.get("artifacts")):
        if not isinstance(item, dict):
            continue
        size_ok = item.get("expected_size_bytes") == item.get("current_size_bytes")
        sha_ok = item.get("expected_sha256") == item.get("current_sha256")
        lines.append(
            f"| `{item.get('path')}` | {_format_bool(item.get('required_for_complete_bundle'))} | "
            f"{_format_bool(item.get('current_exists'))} | {_format_bool(size_ok)} | "
            f"{_format_bool(sha_ok)} | {int(item.get('secret_marker_count') or 0)} |"
        )
    failures = _as_list(payload.get("failures"))
    artifact_failures = [
        f"{item.get('path')}: {', '.join(_as_list(item.get('failures')))}"
        for item in _as_list(payload.get("artifacts"))
        if isinstance(item, dict) and _as_list(item.get("failures"))
    ]
    if failures or artifact_failures:
        lines.extend(["", "### Failures"])
        lines.extend(f"- {failure}" for failure in failures if isinstance(failure, str))
        lines.extend(f"- {failure}" for failure in artifact_failures)
    lines.append("")
    return "\n".join(lines)


def append_github_step_summary(content: str, summary_path: str | None = None) -> bool:
    target = summary_path or os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return False
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")
        stream.write(content)
        if not content.endswith("\n"):
            stream.write("\n")
    return True


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a DeSci provider workflow artifact bundle from its JSON index.",
    )
    parser.add_argument("--index", default=DEFAULT_INDEX_PATH, help="Artifact index JSON path.")
    parser.add_argument("--artifact-root", default=".", help="Directory containing indexed artifacts.")
    parser.add_argument("--json-out", default=DEFAULT_JSON_OUT, help="Verification JSON output path.")
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT, help="Verification Markdown output path.")
    parser.add_argument(
        "--allow-incomplete-bundle",
        action="store_true",
        help="Do not fail solely because the index reports missing required artifacts.",
    )
    parser.add_argument(
        "--require-workflow-ok",
        action="store_true",
        help="Fail unless provider_apply_workflow.ok is true in the index.",
    )
    parser.add_argument(
        "--append-github-step-summary",
        action="store_true",
        help="Append the Markdown summary to GITHUB_STEP_SUMMARY when available.",
    )
    return parser.parse_args(argv)


def _resolve_output(path: str | Path) -> Path:
    return Path(path).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = verify_bundle(
            index_path=args.index,
            artifact_root=args.artifact_root,
            require_complete_bundle=not args.allow_incomplete_bundle,
            require_workflow_ok=args.require_workflow_ok,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "schema_version": 1,
            "generated_at": utc_now_iso(),
            "ok": False,
            "index_path": str(args.index),
            "artifact_root": str(args.artifact_root),
            "require_complete_bundle": not args.allow_incomplete_bundle,
            "require_workflow_ok": args.require_workflow_ok,
            "first_decision_artifact": "",
            "index_complete_bundle": False,
            "provider_apply_workflow": {},
            "summary": {
                "failure_count": 1,
                "artifact_count": 0,
                "required_artifact_count": 0,
                "artifact_failure_count": 0,
                "missing_required_count": 0,
                "digest_mismatch_count": 0,
                "size_mismatch_count": 0,
                "secret_marker_count": 0,
            },
            "failures": [str(exc)],
            "artifacts": [],
        }
    markdown = render_markdown_summary(payload)
    if args.json_out:
        output_path = _resolve_output(args.json_out)
        write_json_atomic(output_path, payload)
        print(f"wrote DeSci provider workflow artifact bundle verification: {output_path}")
    if args.markdown_out:
        markdown_path = _resolve_output(args.markdown_out)
        write_text_atomic(markdown_path, markdown)
        print(f"wrote DeSci provider workflow artifact bundle verification summary: {markdown_path}")
    if args.append_github_step_summary:
        if append_github_step_summary(markdown):
            print("appended DeSci provider workflow artifact bundle verification to GITHUB_STEP_SUMMARY")
        else:
            print("GITHUB_STEP_SUMMARY is not set; skipped bundle verification summary append")
    if payload["ok"]:
        print("[desci-provider-workflow-bundle] ok=true")
        return 0
    print("[desci-provider-workflow-bundle] ok=false")
    for failure in _as_list(payload.get("failures")):
        print(f"  - {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
