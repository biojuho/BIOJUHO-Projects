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
DEFAULT_MARKDOWN_SUMMARY_PATH = "var/desci-provider-workflow-artifact-index-summary.md"
DEFAULT_VERIFY_JSON = "var/external-gate-provider-workflow-machine-verify.json"
PROVIDER_TEMPLATE_DIR = "var/external-gate-provider-workflow-machine"

REVIEW_ORDER = [
    {
        "id": "external_release_gate",
        "path": "var/external-release-gate-provider-workflow-machine.json",
        "purpose": "external release gate JSON",
    },
    {
        "id": "provider_handoff_json",
        "path": "var/external-gate-handoff-provider-workflow-machine.json",
        "purpose": "provider handoff JSON",
    },
    {
        "id": "provider_handoff_markdown",
        "path": "var/external-gate-handoff-provider-workflow-machine.md",
        "purpose": "provider handoff Markdown",
    },
    {
        "id": "provider_template_index",
        "path": "var/external-gate-provider-workflow-index-machine.json",
        "purpose": "provider template index JSON",
    },
    {
        "id": "provider_apply_plan_json",
        "path": "var/external-gate-provider-workflow-machine.json",
        "purpose": "provider apply plan JSON",
    },
    {
        "id": "provider_apply_plan_markdown",
        "path": "var/external-gate-provider-workflow-machine.md",
        "purpose": "provider apply plan Markdown",
    },
    {
        "id": "provider_apply_results",
        "path": "var/external-gate-provider-workflow-machine-results.json",
        "purpose": "provider apply results receipt",
    },
    {
        "id": "provider_workflow_verification_json",
        "path": DEFAULT_VERIFY_JSON,
        "purpose": "provider apply workflow verification JSON",
    },
    {
        "id": "provider_workflow_verification_markdown",
        "path": "var/external-gate-provider-workflow-machine-verify.md",
        "purpose": "provider apply workflow verification Markdown",
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_metadata(
    item: dict[str, str],
    *,
    root: Path,
    required_for_complete_bundle: bool,
) -> dict[str, Any]:
    artifact_path = root / item["path"]
    exists = artifact_path.is_file()
    digest = sha256_file(artifact_path) if exists else None
    return {
        **item,
        "required_for_complete_bundle": required_for_complete_bundle,
        "exists": exists,
        "size_bytes": artifact_path.stat().st_size if exists else None,
        "sha256": digest,
        "sha256_short": digest[:12] if digest else None,
    }


def _artifact_id_from_path(path: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", path.name.lower()).strip("_")
    return f"provider_template_{slug or 'env'}"


def _repo_relative_path(path: Path, *, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def discover_provider_templates(*, root: Path, template_dir: str) -> list[dict[str, Any]]:
    directory = root / template_dir
    if not directory.is_dir():
        return []
    templates: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.env")):
        item = {
            "id": _artifact_id_from_path(path),
            "path": _repo_relative_path(path, root=root),
            "purpose": "provider environment template",
        }
        templates.append(
            artifact_metadata(
                item,
                root=root,
                required_for_complete_bundle=False,
            )
        )
    return templates


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, f"{path} must contain a JSON object"
    return payload, None


def provider_apply_workflow_summary(*, root: Path, verify_json: str) -> dict[str, Any]:
    path = root / verify_json
    if not path.is_file():
        return {
            "ok": None,
            "operator_phase": "",
            "ready_to_apply": None,
            "all_commands_succeeded": None,
            "promotion_receipt_ok": None,
            "failure_count": None,
            "results_command_failure_count": None,
            "failures": [],
            "parse_error": None,
        }
    payload, parse_error = _load_json_object(path)
    if payload is None:
        return {
            "ok": None,
            "operator_phase": "",
            "ready_to_apply": None,
            "all_commands_succeeded": None,
            "promotion_receipt_ok": None,
            "failure_count": None,
            "results_command_failure_count": None,
            "failures": [],
            "parse_error": parse_error,
        }
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    return {
        "ok": payload.get("ok"),
        "operator_phase": str(payload.get("operator_phase") or ""),
        "ready_to_apply": payload.get("ready_to_apply"),
        "all_commands_succeeded": payload.get("all_commands_succeeded"),
        "promotion_receipt_ok": payload.get("promotion_receipt_ok"),
        "failure_count": summary.get("failure_count"),
        "results_command_failure_count": summary.get("results_command_failure_count"),
        "failures": [item for item in failures if isinstance(item, str)],
        "parse_error": None,
    }


def build_payload(
    *,
    root: Path,
    json_out: str,
    external_exit_code: str | None,
    handoff_exit_code: str | None,
    results_exit_code: str | None,
    verify_exit_code: str | None,
    verify_json: str = DEFAULT_VERIFY_JSON,
    provider_template_dir: str = PROVIDER_TEMPLATE_DIR,
) -> dict[str, Any]:
    required_artifacts = [
        artifact_metadata(item, root=root, required_for_complete_bundle=True) for item in REVIEW_ORDER
    ]
    provider_templates = discover_provider_templates(root=root, template_dir=provider_template_dir)
    artifacts = [*required_artifacts, *provider_templates]
    missing_artifacts = [
        item["path"]
        for item in artifacts
        if item["required_for_complete_bundle"] and not item["exists"]
    ]
    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "index_path": json_out,
        "first_decision_artifact": verify_json,
        "provider_template_dir": provider_template_dir,
        "upload_before_fail_closed": True,
        "all_required_artifacts_present": not missing_artifacts,
        "missing_artifact_count": len(missing_artifacts),
        "missing_artifacts": missing_artifacts,
        "exit_codes": {
            "external_release_gate": external_exit_code,
            "provider_handoff": handoff_exit_code,
            "provider_apply_results": results_exit_code,
            "provider_apply_workflow_verifier": verify_exit_code,
        },
        "provider_apply_workflow": provider_apply_workflow_summary(root=root, verify_json=verify_json),
        "review_order": REVIEW_ORDER,
        "artifacts": artifacts,
        "provider_templates": provider_templates,
    }


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


def format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "unknown" if value is None else str(value)


def format_exit_code(value: str | None) -> str:
    return value if value not in {None, ""} else "missing"


def render_markdown_summary(payload: dict[str, Any]) -> str:
    workflow = payload["provider_apply_workflow"]
    lines = [
        "## DeSci Provider Apply Workflow Artifact Index",
        "",
        f"- Index: `{payload['index_path']}`",
        f"- First decision artifact: `{payload['first_decision_artifact']}`",
        f"- Provider template dir: `{payload['provider_template_dir']}`",
        f"- Upload before fail-closed: `{format_bool(payload['upload_before_fail_closed'])}`",
        f"- Complete bundle: `{format_bool(payload['all_required_artifacts_present'])}`",
        f"- Missing artifacts: `{payload['missing_artifact_count']}`",
        f"- Provider workflow ok: `{format_bool(workflow.get('ok'))}`",
        f"- Provider workflow phase: `{workflow.get('operator_phase') or 'unknown'}`",
        f"- Ready to apply: `{format_bool(workflow.get('ready_to_apply'))}`",
        f"- Provider commands succeeded: `{format_bool(workflow.get('all_commands_succeeded'))}`",
        f"- Promotion receipt go: `{format_bool(workflow.get('promotion_receipt_ok'))}`",
        f"- Workflow failure count: `{workflow.get('failure_count') if workflow.get('failure_count') is not None else 'unknown'}`",
        (
            "- Results command failure count: "
            f"`{workflow.get('results_command_failure_count') if workflow.get('results_command_failure_count') is not None else 'unknown'}`"
        ),
        "",
        "| Exit Code | Value |",
        "|---|---:|",
    ]
    for key, value in payload["exit_codes"].items():
        lines.append(f"| `{key}` | `{format_exit_code(value)}` |")
    lines.extend(
        [
            "",
            "| Order | Artifact | Required | Exists | Size bytes | SHA-256 | Purpose |",
            "|---:|---|---|---|---:|---|---|",
        ]
    )
    for index, item in enumerate(payload["artifacts"], start=1):
        size_bytes = item["size_bytes"] if item["size_bytes"] is not None else ""
        digest = item.get("sha256_short") or ""
        lines.append(
            f"| {index} | `{item['path']}` | {format_bool(item['required_for_complete_bundle'])} | "
            f"{format_bool(item['exists'])} | {size_bytes} | {digest} | {item['purpose']} |"
        )
    failures = workflow.get("failures") if isinstance(workflow.get("failures"), list) else []
    if workflow.get("parse_error"):
        lines.extend(["", f"- Verify JSON parse error: `{workflow['parse_error']}`"])
    if failures:
        lines.extend(["", "### Workflow Failures"])
        lines.extend(f"- {failure}" for failure in failures)
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
        description="Write a machine-readable index for DeSci provider workflow artifacts.",
    )
    parser.add_argument("--json-out", default=DEFAULT_INDEX_PATH, help="Repo-relative JSON index output path.")
    parser.add_argument(
        "--markdown-summary-out",
        default=DEFAULT_MARKDOWN_SUMMARY_PATH,
        help="Repo-relative Markdown summary output path.",
    )
    parser.add_argument(
        "--append-github-step-summary",
        action="store_true",
        help="Append the Markdown summary to GITHUB_STEP_SUMMARY when available.",
    )
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="Workspace root used to resolve artifact paths.",
    )
    parser.add_argument(
        "--verify-json",
        default=DEFAULT_VERIFY_JSON,
        help="Repo-relative provider workflow verification JSON path.",
    )
    parser.add_argument(
        "--provider-template-dir",
        default=PROVIDER_TEMPLATE_DIR,
        help="Repo-relative provider template directory.",
    )
    parser.add_argument(
        "--external-exit-code",
        default=os.environ.get("EXTERNAL_RELEASE_GATE_EXIT_CODE") or None,
        help="External release gate exit code. Defaults to EXTERNAL_RELEASE_GATE_EXIT_CODE.",
    )
    parser.add_argument(
        "--handoff-exit-code",
        default=os.environ.get("PROVIDER_HANDOFF_EXIT_CODE") or None,
        help="Provider handoff exit code. Defaults to PROVIDER_HANDOFF_EXIT_CODE.",
    )
    parser.add_argument(
        "--results-exit-code",
        default=os.environ.get("PROVIDER_APPLY_RESULTS_EXIT_CODE") or None,
        help="Provider apply results exit code. Defaults to PROVIDER_APPLY_RESULTS_EXIT_CODE.",
    )
    parser.add_argument(
        "--verify-exit-code",
        default=os.environ.get("PROVIDER_WORKFLOW_VERIFY_EXIT_CODE") or None,
        help="Provider workflow verifier exit code. Defaults to PROVIDER_WORKFLOW_VERIFY_EXIT_CODE.",
    )
    return parser.parse_args(argv)


def _resolve_output_path(root: Path, path: str) -> Path:
    output_path = Path(path)
    if not output_path.is_absolute():
        output_path = root / output_path
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.workspace_root).resolve()
    payload = build_payload(
        root=root,
        json_out=args.json_out,
        external_exit_code=args.external_exit_code,
        handoff_exit_code=args.handoff_exit_code,
        results_exit_code=args.results_exit_code,
        verify_exit_code=args.verify_exit_code,
        verify_json=args.verify_json,
        provider_template_dir=args.provider_template_dir,
    )
    output_path = _resolve_output_path(root, args.json_out)
    write_json_atomic(output_path, payload)
    markdown = render_markdown_summary(payload)
    if args.markdown_summary_out:
        markdown_path = _resolve_output_path(root, args.markdown_summary_out)
        write_text_atomic(markdown_path, markdown)
        print(f"wrote DeSci provider workflow artifact summary: {markdown_path}")
    if args.append_github_step_summary:
        if append_github_step_summary(markdown):
            print("appended DeSci provider workflow artifact index to GITHUB_STEP_SUMMARY")
        else:
            print("GITHUB_STEP_SUMMARY is not set; skipped artifact index summary append")
    print(f"wrote DeSci provider workflow artifact index: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
