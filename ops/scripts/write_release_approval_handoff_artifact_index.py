from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = "var/release-approval-handoff-artifact-index-machine.json"
DEFAULT_MARKDOWN_SUMMARY_PATH = "var/release-approval-handoff-artifact-index-summary.md"

REVIEW_ORDER = [
    {
        "id": "product_release_gate_parent",
        "path": "var/desci-release-gate-release-approval-handoff-machine.json",
        "purpose": "DeSci parent release-gate JSON with release_approval_handoff_summary",
    },
    {
        "id": "operator_markdown_summary",
        "path": "docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md",
        "purpose": "operator-facing GitHub job summary Markdown",
    },
    {
        "id": "raw_release_approval_analysis",
        "path": "var/release-approval-check-machine.json",
        "purpose": "raw approval failure analysis",
    },
    {
        "id": "session_bootstrap_context",
        "path": "var/session-bootstrap-release-approval-machine.json",
        "purpose": "session bootstrap context",
    },
    {
        "id": "workspace_smoke_context",
        "path": "var/workspace-smoke-workspace-release-approval-machine.json",
        "purpose": "workspace smoke proof",
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_metadata(item: dict[str, str], *, root: Path) -> dict[str, Any]:
    artifact_path = root / item["path"]
    exists = artifact_path.is_file()
    digest = sha256_file(artifact_path) if exists else None
    return {
        **item,
        "required_for_complete_bundle": True,
        "exists": exists,
        "size_bytes": artifact_path.stat().st_size if exists else None,
        "sha256": digest,
        "sha256_short": digest[:12] if digest else None,
    }


def build_payload(
    *,
    root: Path,
    json_out: str,
    wrapper_exit_code: str | None,
    release_gate_exit_code: str | None,
) -> dict[str, Any]:
    artifacts = [artifact_metadata(item, root=root) for item in REVIEW_ORDER]
    missing_artifacts = [item["path"] for item in artifacts if not item["exists"]]
    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "index_path": json_out,
        "first_decision_artifact": REVIEW_ORDER[0]["path"],
        "upload_before_fail_closed": True,
        "all_required_artifacts_present": not missing_artifacts,
        "missing_artifact_count": len(missing_artifacts),
        "missing_artifacts": missing_artifacts,
        "exit_codes": {
            "release_approval_wrapper": wrapper_exit_code,
            "desci_release_gate_handoff": release_gate_exit_code,
        },
        "review_order": REVIEW_ORDER,
        "artifacts": artifacts,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def render_markdown_summary(payload: dict[str, Any]) -> str:
    lines = [
        "## Release Approval Handoff Artifact Index",
        "",
        f"- Index: `{payload['index_path']}`",
        f"- First decision artifact: `{payload['first_decision_artifact']}`",
        f"- Upload before fail-closed: `{format_bool(bool(payload['upload_before_fail_closed']))}`",
        f"- Complete bundle: `{format_bool(bool(payload['all_required_artifacts_present']))}`",
        f"- Missing artifacts: `{payload['missing_artifact_count']}`",
        f"- Wrapper exit code: `{payload['exit_codes'].get('release_approval_wrapper') or 'missing'}`",
        f"- DeSci release-gate handoff exit code: `{payload['exit_codes'].get('desci_release_gate_handoff') or 'missing'}`",
        "",
        "| Order | Artifact | Exists | Size bytes | SHA-256 | Purpose |",
        "|---:|---|---|---:|---|---|",
    ]
    for index, item in enumerate(payload["artifacts"], start=1):
        size_bytes = item["size_bytes"] if item["size_bytes"] is not None else ""
        digest = item.get("sha256_short") or ""
        lines.append(
            f"| {index} | `{item['path']}` | {format_bool(bool(item['exists']))} | {size_bytes} | {digest} | {item['purpose']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


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
        description="Write a machine-readable index for release approval handoff artifacts.",
    )
    parser.add_argument("--json-out", default=DEFAULT_INDEX_PATH, help="Repo-relative JSON index output path.")
    parser.add_argument(
        "--markdown-summary-out",
        default="",
        help="Optional repo-relative Markdown summary output path.",
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
        "--wrapper-exit-code",
        default=os.environ.get("WRAPPER_EXIT_CODE") or None,
        help="Release approval wrapper exit code. Defaults to WRAPPER_EXIT_CODE.",
    )
    parser.add_argument(
        "--release-gate-exit-code",
        default=os.environ.get("RELEASE_GATE_HANDOFF_EXIT_CODE") or None,
        help="DeSci release-gate handoff exit code. Defaults to RELEASE_GATE_HANDOFF_EXIT_CODE.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.workspace_root).resolve()
    payload = build_payload(
        root=root,
        json_out=args.json_out,
        wrapper_exit_code=args.wrapper_exit_code,
        release_gate_exit_code=args.release_gate_exit_code,
    )
    output_path = Path(args.json_out)
    if not output_path.is_absolute():
        output_path = root / output_path
    write_json_atomic(output_path, payload)
    markdown = render_markdown_summary(payload)
    if args.markdown_summary_out:
        markdown_path = Path(args.markdown_summary_out)
        if not markdown_path.is_absolute():
            markdown_path = root / markdown_path
        write_text_atomic(markdown_path, markdown)
        print(f"wrote release approval handoff artifact summary: {markdown_path}")
    if args.append_github_step_summary:
        if append_github_step_summary(markdown):
            print("appended release approval handoff artifact index to GITHUB_STEP_SUMMARY")
        else:
            print("GITHUB_STEP_SUMMARY is not set; skipped artifact index summary append")
    print(f"wrote release approval handoff artifact index: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
