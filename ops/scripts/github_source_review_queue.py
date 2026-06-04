from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "github_modernization_sources.json"
DEFAULT_CHANGE_SUMMARY = (
    WORKSPACE_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json"
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import github_modernization_radar as radar  # noqa: E402

FIELD_WEIGHTS = {
    "archived": 100,
    "disabled": 100,
    "visibility": 80,
    "default_branch": 40,
    "license": 25,
    "pushed_at": 20,
    "updated_at": 8,
    "open_issues_count": 6,
    "stargazers_count": 2,
    "forks_count": 1,
}

CATEGORY_WEIGHTS = {
    "openai-agent-runtime-sdk": 8,
    "enterprise-agent-framework": 8,
    "official-mcp-python-sdk": 7,
    "mcp-agent-workflow-framework": 7,
    "typescript-agent-application-framework": 6,
    "typescript-ai-app-toolkit": 6,
    "mcp-browser-automation": 6,
    "agent-workflow-runtime": 6,
    "stateful-agent-orchestration": 6,
}

ADOPTION_STATUS_WEIGHTS = {
    "watch": 5,
    "partially_adopted": 3,
    "adopted": 1,
}


def build_review_queue(change_summary_path: Path, manifest_path: Path) -> dict[str, Any]:
    source_summary = _load_json(change_summary_path)
    manifest = radar.load_manifest(manifest_path)
    errors = radar.validate_manifest(manifest, workspace_root=WORKSPACE_ROOT)
    errors.extend(_validate_change_summary(source_summary))
    if errors:
        raise ValueError("\n".join(errors))

    manifest_sources = {source["repo"]: source for source in manifest["sources"]}
    change_summary = source_summary["change_summary"]
    items = [
        _build_queue_item(record, manifest_sources.get(record["repo"], {}))
        for record in change_summary["records"]
        if isinstance(record, dict) and isinstance(record.get("repo"), str)
    ]
    items.sort(key=lambda item: (-item["score"], item["repo"].lower()))
    for index, item in enumerate(items, start=1):
        item["rank"] = index

    return {
        "schema_version": 1,
        "status": "pass",
        "source_change_summary": _display_path(change_summary_path),
        "source_change_generated_at": source_summary["generated_at"],
        "baseline_generated_at": change_summary.get("baseline_generated_at", ""),
        "source_count": source_summary["source_count"],
        "changed_repositories": change_summary["changed_repositories"],
        "queued_repositories": len(items),
        "new_repositories": change_summary.get("new_repositories", []),
        "removed_repositories": change_summary.get("removed_repositories", []),
        "ranking_policy": {
            "field_weights": FIELD_WEIGHTS,
            "category_weights": CATEGORY_WEIGHTS,
            "adoption_status_weights": ADOPTION_STATUS_WEIGHTS,
            "decision_rule": "Review pushed_at, repository policy, and high-impact runtime framework changes before passive community-metric changes.",
        },
        "items": items,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Source Review Queue",
        "",
        f"- Status: `{report['status']}`",
        f"- Source count: `{report['source_count']}`",
        f"- Changed repositories: `{report['changed_repositories']}`",
        f"- Queued repositories: `{report['queued_repositories']}`",
        f"- New repositories: `{len(report.get('new_repositories', []))}`",
        f"- Removed repositories: `{len(report.get('removed_repositories', []))}`",
        f"- Baseline generated at: `{report['baseline_generated_at']}`",
        f"- Source change generated at: `{report['source_change_generated_at']}`",
        "",
        "## Queue",
        "",
        "| Rank | Priority | Score | Repo | Changed fields | Next action |",
        "| ---: | --- | ---: | --- | --- | --- |",
    ]
    for item in report["items"]:
        lines.append(
            " | ".join(
                [
                    f"| {item['rank']}",
                    item["priority"],
                    str(item["score"]),
                    f"`{item['repo']}`",
                    ", ".join(item["changed_fields"]),
                    item["next_action"] + " |",
                ]
            )
        )

    lines.extend(["", "## Decision Rule", "", f"- {report['ranking_policy']['decision_rule']}"])
    lines.append("")
    return "\n".join(lines)


def run(
    change_summary_path: Path = DEFAULT_CHANGE_SUMMARY,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    report = build_review_queue(change_summary_path, manifest_path)
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, render_markdown(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank changed GitHub source metadata into a review queue.")
    parser.add_argument("--change-summary", type=Path, default=DEFAULT_CHANGE_SUMMARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(
            args.change_summary,
            manifest_path=args.manifest,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"github source review queue failed: {exc}", file=sys.stderr)
        return 1
    print(
        "github source review queue valid: "
        f"queued={report['queued_repositories']}, changed={report['changed_repositories']}"
    )
    return 0


def _build_queue_item(record: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    changed_fields = [field for field in record.get("changed_fields", []) if isinstance(field, str)]
    category = source.get("category") or record.get("category") or ""
    adoption_status = source.get("adoption_status") or record.get("adoption_status") or ""
    score = (
        sum(FIELD_WEIGHTS.get(field, 0) for field in changed_fields)
        + CATEGORY_WEIGHTS.get(category, 4)
        + ADOPTION_STATUS_WEIGHTS.get(adoption_status, 0)
    )
    return {
        "rank": 0,
        "repo": record["repo"],
        "url": source.get("url", ""),
        "category": category,
        "adoption_status": adoption_status,
        "priority": _priority(score),
        "score": score,
        "changed_fields": changed_fields,
        "review_reason": _review_reason(changed_fields),
        "next_action": _next_action(changed_fields),
        "local_evidence": source.get("local_evidence", [])[:5],
    }


def _priority(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 30:
        return "high"
    if score >= 15:
        return "medium"
    return "low"


def _review_reason(changed_fields: list[str]) -> str:
    policy_fields = {"archived", "disabled", "visibility", "default_branch", "license"}
    if policy_fields.intersection(changed_fields):
        return "repository policy or viability metadata changed"
    if "pushed_at" in changed_fields:
        return "upstream source code moved since the baseline snapshot"
    if "open_issues_count" in changed_fields:
        return "issue volume changed since the baseline snapshot"
    return "community or activity metadata changed since the baseline snapshot"


def _next_action(changed_fields: list[str]) -> str:
    policy_fields = {"archived", "disabled", "visibility", "default_branch", "license"}
    if policy_fields.intersection(changed_fields):
        return "Re-check viability before relying on this source."
    if "pushed_at" in changed_fields:
        return "Review upstream commits or release notes before the next adoption decision."
    if "open_issues_count" in changed_fields:
        return "Review issue movement when selecting the next source-backed experiment."
    return "Keep on the watchlist unless code or policy metadata changes."


def _validate_change_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("status") != "pass":
        errors.append("change summary status must be pass")
    change_summary = payload.get("change_summary")
    if not isinstance(change_summary, dict):
        errors.append("change_summary must be an object")
        return errors
    if change_summary.get("compared") is not True:
        errors.append("change_summary.compared must be true")
    records = change_summary.get("records")
    if not isinstance(records, list):
        errors.append("change_summary.records must be an array")
    changed = change_summary.get("changed_repositories")
    if isinstance(records, list) and changed != len(records):
        errors.append("change_summary.changed_repositories must match records length")
    return errors


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
