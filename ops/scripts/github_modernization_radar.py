from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "github_modernization_sources.json"
ALLOWED_STATUSES = {"adopted", "partially_adopted", "watch"}
REQUIRED_SOURCE_FIELDS = {
    "repo",
    "url",
    "category",
    "adoption_status",
    "why_similar",
    "observed_patterns",
    "local_evidence",
    "gap",
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def validate_manifest(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), errors)
    _validate_search_context(payload.get("search_context"), errors)
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty array")
        return errors

    seen_repos: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_SOURCE_FIELDS - set(source)
        for field in sorted(missing):
            errors.append(f"{prefix}.{field} is required")
        repo = _require_string(source.get("repo"), f"{prefix}.repo", errors)
        if repo:
            if "/" not in repo or repo.count("/") != 1:
                errors.append(f"{prefix}.repo must use owner/name format")
            if repo in seen_repos:
                errors.append(f"{prefix}.repo must be unique")
            seen_repos.add(repo)
        url = _require_string(source.get("url"), f"{prefix}.url", errors)
        if url and not url.startswith("https://github.com/"):
            errors.append(f"{prefix}.url must be a GitHub HTTPS URL")
        _require_string(source.get("category"), f"{prefix}.category", errors)
        status = _require_string(source.get("adoption_status"), f"{prefix}.adoption_status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.adoption_status must be adopted, partially_adopted, or watch")
        _require_string(source.get("why_similar"), f"{prefix}.why_similar", errors)
        _require_string(source.get("gap"), f"{prefix}.gap", errors)
        _validate_string_list(source.get("observed_patterns"), f"{prefix}.observed_patterns", errors)
        _validate_evidence_paths(source.get("local_evidence"), f"{prefix}.local_evidence", workspace_root, errors)
    return errors


def summarize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    sources = payload["sources"]
    status_counts = Counter(source["adoption_status"] for source in sources)
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "source_count": len(sources),
        "adoption_status_counts": dict(sorted(status_counts.items())),
        "sources": [
            {
                "repo": source["repo"],
                "category": source["category"],
                "adoption_status": source["adoption_status"],
                "evidence_count": len(source["local_evidence"]),
                "pattern_count": len(source["observed_patterns"]),
                "gap": source["gap"],
            }
            for source in sources
        ],
    }


def format_markdown(payload: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# GitHub Similar Systems Modernization Radar - 2026-06-04",
        "",
        "## Summary",
        "",
        f"- Sources reviewed: {summary['source_count']}",
        f"- Adoption counts: {_format_status_counts(summary['adoption_status_counts'])}",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Search Context",
        "",
        f"- Objective: {payload['search_context']['objective']}",
        "- Queries:",
    ]
    lines.extend(f"  - `{query}`" for query in payload["search_context"]["queries"])
    lines.extend(["", "## Source Mapping", ""])
    for source in payload["sources"]:
        lines.extend(
            [
                f"### {source['repo']}",
                "",
                f"- URL: {source['url']}",
                f"- Category: `{source['category']}`",
                f"- Adoption status: `{source['adoption_status']}`",
                f"- Why similar: {source['why_similar']}",
                "- Observed patterns:",
            ]
        )
        lines.extend(f"  - {pattern}" for pattern in source["observed_patterns"])
        lines.append("- Local evidence:")
        lines.extend(f"  - `{path}`" for path in source["local_evidence"])
        lines.extend([f"- Gap: {source['gap']}", ""])
    lines.extend(
        [
            "## Operating Decision",
            "",
            "Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.",
            "",
        ]
    )
    return "\n".join(lines)


def run(manifest_path: Path, *, json_out: Path | None = None, markdown_out: Path | None = None) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    summary = summarize_manifest(payload)
    if json_out is not None:
        _write_json_atomic(json_out, summary)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(payload, summary))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub-similar modernization sources against local evidence.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.manifest, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"github modernization radar failed: {exc}", file=sys.stderr)
        return 1
    print(
        "github modernization radar valid: "
        f"{summary['source_count']} sources, {_format_status_counts(summary['adoption_status_counts'])}"
    )
    return 0


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


def _validate_search_context(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("search_context must be an object")
        return
    _require_string(value.get("objective"), "search_context.objective", errors)
    _validate_string_list(value.get("queries"), "search_context.queries", errors)


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")


def _validate_evidence_paths(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        path_field = f"{field}[{index}]"
        path_value = _require_string(item, path_field, errors)
        if not path_value:
            continue
        if not _is_repo_relative(path_value):
            errors.append(f"{path_field} must be a repo-relative path")
            continue
        if not (workspace_root / path_value).exists():
            errors.append(f"{path_field} must exist in the workspace")


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return False
    if normalized.startswith("/") or normalized.startswith("../"):
        return False
    if "/../" in f"/{normalized}/":
        return False
    return not Path(value).is_absolute()


def _format_status_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{status}={counts.get(status, 0)}" for status in sorted(ALLOWED_STATUSES))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
