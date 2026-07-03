from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "github_modernization_sources.json"
ALLOWED_STATUSES = {"adopted", "partially_adopted", "watch"}
GIT_TRACKED_TIMEOUT_SECONDS = 10
GIT_REMOTE_TIMEOUT_SECONDS = 20
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
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def validate_manifest(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> list[str]:
    errors: list[str] = []
    tracked_paths = _git_tracked_paths(workspace_root)
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), errors)
    _validate_search_context(payload.get("search_context"), errors)
    _validate_sources(payload.get("sources"), workspace_root, errors, tracked_paths=tracked_paths)
    return errors


def _validate_sources(
    value: Any,
    workspace_root: Path,
    errors: list[str],
    *,
    tracked_paths: set[str] | None,
) -> None:
    if not isinstance(value, list) or not value:
        errors.append("sources must be a non-empty array")
        return

    seen_repos: set[str] = set()
    for index, source in enumerate(value):
        _validate_source_entry(
            source,
            index=index,
            seen_repos=seen_repos,
            workspace_root=workspace_root,
            errors=errors,
            tracked_paths=tracked_paths,
        )


def _validate_source_entry(
    source: Any,
    *,
    index: int,
    seen_repos: set[str],
    workspace_root: Path,
    errors: list[str],
    tracked_paths: set[str] | None,
) -> None:
    prefix = f"sources[{index}]"
    if not isinstance(source, dict):
        errors.append(f"{prefix} must be an object")
        return
    missing = REQUIRED_SOURCE_FIELDS - set(source)
    for field in sorted(missing):
        errors.append(f"{prefix}.{field} is required")
    _validate_source_repo(source, prefix, seen_repos, errors)
    _validate_source_scalar_fields(source, prefix, errors)
    _validate_string_list(source.get("observed_patterns"), f"{prefix}.observed_patterns", errors)
    _validate_evidence_paths(
        source.get("local_evidence"),
        f"{prefix}.local_evidence",
        workspace_root,
        errors,
        tracked_paths=tracked_paths,
    )


def _validate_source_scalar_fields(
    source: dict[str, Any], prefix: str, errors: list[str]
) -> None:
    url = _require_string(source.get("url"), f"{prefix}.url", errors)
    if url and not url.startswith("https://github.com/"):
        errors.append(f"{prefix}.url must be a GitHub HTTPS URL")
    _require_string(source.get("category"), f"{prefix}.category", errors)
    status = _require_string(source.get("adoption_status"), f"{prefix}.adoption_status", errors)
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"{prefix}.adoption_status must be adopted, partially_adopted, or watch")
    _require_string(source.get("why_similar"), f"{prefix}.why_similar", errors)
    _validate_optional_commit(source.get("latest_observed_commit"), f"{prefix}.latest_observed_commit", errors)
    _require_string(source.get("gap"), f"{prefix}.gap", errors)


def _validate_source_repo(
    source: dict[str, Any],
    prefix: str,
    seen_repos: set[str],
    errors: list[str],
) -> None:
    repo = _require_string(source.get("repo"), f"{prefix}.repo", errors)
    if not repo:
        return
    if "/" not in repo or repo.count("/") != 1:
        errors.append(f"{prefix}.repo must use owner/name format")
    if repo in seen_repos:
        errors.append(f"{prefix}.repo must be unique")
    seen_repos.add(repo)


def summarize_manifest(
    payload: dict[str, Any],
    *,
    rendered_at: str | None = None,
    latest_commit_refresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sources = payload["sources"]
    status_counts = Counter(source["adoption_status"] for source in sources)
    evidence_path_count = _evidence_path_count(sources)
    summary = {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "rendered_at": rendered_at or _current_rendered_at(),
        "source_count": len(sources),
        "adoption_status_counts": dict(sorted(status_counts.items())),
        "local_evidence_path_count": evidence_path_count,
        "local_evidence_git_tracked": True,
        "sources": [_summarize_source(source) for source in sources],
    }
    if latest_commit_refresh is not None:
        summary["latest_commit_refresh"] = latest_commit_refresh
    return summary


def _evidence_path_count(sources: list[dict[str, Any]]) -> int:
    return sum(len(source["local_evidence"]) for source in sources)


def _summarize_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo": source["repo"],
        "category": source["category"],
        "adoption_status": source["adoption_status"],
        "latest_observed_commit": source.get("latest_observed_commit", ""),
        "evidence_count": len(source["local_evidence"]),
        "pattern_count": len(source["observed_patterns"]),
        "gap": source["gap"],
    }


def format_markdown(payload: dict[str, Any], summary: dict[str, Any]) -> str:
    generated_date = _format_generated_date(summary["generated_at"])
    lines = [
        f"# GitHub Similar Systems Modernization Radar - {generated_date}",
        "",
        "## Summary",
        "",
        f"- Sources reviewed: {summary['source_count']}",
        f"- Adoption counts: {_format_status_counts(summary['adoption_status_counts'])}",
        f"- Local evidence tracking: {_format_evidence_tracking(summary)}",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Rendered at: `{summary['rendered_at']}`",
    ]
    latest_commit_refresh = summary.get("latest_commit_refresh")
    if latest_commit_refresh:
        lines.append(f"- Latest commit refresh: {_format_latest_commit_refresh(latest_commit_refresh)}")
    lines.extend(
        [
            "",
            "## Search Context",
            "",
            f"- Objective: {payload['search_context']['objective']}",
            "- Queries:",
        ]
    )
    lines.extend(f"  - `{query}`" for query in payload["search_context"]["queries"])
    lines.extend([""])
    lines.extend(_format_refresh_review_queue_markdown(latest_commit_refresh))
    lines.extend(["", "## Source Mapping", ""])
    for source in payload["sources"]:
        lines.extend(_format_source_markdown(source))
    lines.extend(
        [
            "## Operating Decision",
            "",
            "Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_evidence_tracking(summary: dict[str, Any]) -> str:
    path_count = summary.get("local_evidence_path_count", 0)
    if summary.get("local_evidence_git_tracked") is True:
        return f"all {path_count} paths exist and are git-tracked"
    return f"{path_count} paths checked; tracking incomplete"


def _format_latest_commit_refresh(refresh: dict[str, Any]) -> str:
    checked_count = refresh.get("checked_count", 0)
    updated_count = refresh.get("updated_count", 0)
    failed_count = refresh.get("failed_count", 0)
    review_required_count = refresh.get("review_required_count", 0)
    checked_at = refresh.get("checked_at", "")
    return (
        f"{checked_count} GitHub HEAD refs checked at `{checked_at}`; "
        f"updated={updated_count}, failed={failed_count}, review_required={review_required_count}"
    )


def _format_refresh_review_queue_markdown(refresh: dict[str, Any] | None) -> list[str]:
    if not refresh:
        return []
    review_items = [
        item for item in refresh.get("repositories", [])
        if item.get("review_required") is True
    ]
    lines = [
        "## Refresh Review Queue",
        "",
    ]
    if not review_items:
        return lines + ["- Review required: `0`", ""]
    lines.extend(
        [
        "| Repo | Status | Category | Local review targets | Compare |",
        "| --- | --- | --- | --- | --- |",
        ]
    )
    lines.extend(_format_refresh_review_row(item) for item in review_items)
    lines.append("")
    return lines


def _format_refresh_review_row(item: dict[str, Any]) -> str:
    compare_url = item.get("compare_url", "")
    compare = f"[compare]({compare_url})" if compare_url else ""
    return (
        f"| {item.get('repo', '')} | `{item.get('status', '')}` | "
        f"`{item.get('category', '')}` | {_format_review_targets(item)} | {compare} |"
    )


def _format_review_targets(item: dict[str, Any]) -> str:
    targets = item.get("local_review_targets")
    if not isinstance(targets, list) or not targets:
        return "`none`"
    return "<br>".join(f"`{target}`" for target in targets)


def _format_source_markdown(source: dict[str, Any]) -> list[str]:
    lines = [
        f"### {source['repo']}",
        "",
        f"- URL: {source['url']}",
        f"- Category: `{source['category']}`",
        f"- Adoption status: `{source['adoption_status']}`",
        f"- Why similar: {source['why_similar']}",
    ]
    latest_observed_commit = source.get("latest_observed_commit")
    if latest_observed_commit:
        lines.append(f"- Latest observed commit: `{latest_observed_commit}`")
    lines.append("- Observed patterns:")
    lines.extend(f"  - {pattern}" for pattern in source["observed_patterns"])
    lines.append("- Local evidence:")
    lines.extend(f"  - `{path}`" for path in source["local_evidence"])
    lines.extend([f"- Gap: {source['gap']}", ""])
    return lines


def _format_generated_date(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.date().isoformat()


def _current_rendered_at() -> str:
    return datetime.now(UTC).isoformat()


def run(
    manifest_path: Path,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    latest_commit_overrides: dict[str, str] | None = None,
    refresh_latest_commits: bool = False,
) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    latest_commit_refresh = refresh_manifest_latest_commits(payload) if refresh_latest_commits else None
    _apply_latest_commit_overrides(payload, latest_commit_overrides or {})
    errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    summary = summarize_manifest(payload, latest_commit_refresh=latest_commit_refresh)
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
    parser.add_argument(
        "--latest-observed-commit",
        action="append",
        default=[],
        metavar="REPO=SHA",
        help="Override a source latest_observed_commit in generated outputs without editing the manifest.",
    )
    parser.add_argument(
        "--refresh-latest-commits",
        action="store_true",
        help="Fetch each GitHub source HEAD with git ls-remote and update generated outputs only.",
    )
    args = parser.parse_args(argv)
    try:
        summary = run(
            args.manifest,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            latest_commit_overrides=_parse_latest_commit_overrides(args.latest_observed_commit),
            refresh_latest_commits=args.refresh_latest_commits,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"github modernization radar failed: {exc}", file=sys.stderr)
        return 1
    print(
        "github modernization radar valid: "
        f"{summary['source_count']} sources, {_format_status_counts(summary['adoption_status_counts'])}"
    )
    return 0


def _apply_latest_commit_overrides(payload: dict[str, Any], overrides: dict[str, str]) -> None:
    if not overrides:
        return
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return
    for source in sources:
        _apply_latest_commit_override(source, overrides)


def _apply_latest_commit_override(source: Any, overrides: dict[str, str]) -> None:
    if not isinstance(source, dict):
        return
    repo = source.get("repo")
    if isinstance(repo, str) and repo in overrides:
        source["latest_observed_commit"] = overrides[repo]


def refresh_manifest_latest_commits(payload: dict[str, Any]) -> dict[str, Any]:
    checked_at = _current_rendered_at()
    sources = payload.get("sources")
    repositories: list[dict[str, Any]] = []
    if isinstance(sources, list):
        repositories = [_refresh_source_latest_commit(source) for source in sources]
    return {
        "checked_at": checked_at,
        "checked_count": len(repositories),
        "updated_count": sum(
            1 for item in repositories if item["status"] in {"updated", "missing_previous"}
        ),
        "failed_count": sum(1 for item in repositories if item["status"] == "failed"),
        "review_required_count": sum(1 for item in repositories if item["review_required"] is True),
        "repositories": repositories,
    }


def _refresh_source_latest_commit(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return _latest_commit_refresh_result("", "", "", "failed", "source must be an object")
    repo = str(source.get("repo") or "")
    url = str(source.get("url") or "")
    previous_commit = str(source.get("latest_observed_commit") or "")
    source_context = _source_review_context(source)
    try:
        remote_head_commit = _fetch_remote_head_commit(url)
    except ValueError as exc:
        return _latest_commit_refresh_result(repo, previous_commit, "", "failed", str(exc), **source_context)
    if previous_commit == remote_head_commit:
        return _latest_commit_refresh_result(repo, previous_commit, remote_head_commit, "unchanged", **source_context)
    source["latest_observed_commit"] = remote_head_commit
    status = "updated" if previous_commit else "missing_previous"
    return _latest_commit_refresh_result(repo, previous_commit, remote_head_commit, status, url=url, **source_context)


def _source_review_context(source: dict[str, Any]) -> dict[str, Any]:
    local_evidence = source.get("local_evidence")
    evidence_paths = local_evidence if isinstance(local_evidence, list) else []
    return {
        "category": str(source.get("category") or ""),
        "adoption_status": str(source.get("adoption_status") or ""),
        "local_evidence_count": len(evidence_paths),
        "local_review_targets": [
            item for item in evidence_paths[:5] if isinstance(item, str) and item.strip()
        ],
        "gap": str(source.get("gap") or ""),
    }


def _latest_commit_refresh_result(
    repo: str,
    previous_commit: str,
    remote_head_commit: str,
    status: str,
    error: str = "",
    url: str = "",
    category: str = "",
    adoption_status: str = "",
    local_evidence_count: int = 0,
    local_review_targets: list[str] | None = None,
    gap: str = "",
) -> dict[str, Any]:
    result = {
        "repo": repo,
        "previous_commit": previous_commit,
        "remote_head_commit": remote_head_commit,
        "status": status,
        "review_required": status in {"updated", "missing_previous", "failed"},
        "category": category,
        "adoption_status": adoption_status,
        "local_evidence_count": local_evidence_count,
        "local_review_targets": local_review_targets or [],
        "gap": gap,
    }
    if previous_commit and remote_head_commit and url:
        result["compare_url"] = _github_compare_url(url, previous_commit, remote_head_commit)
    if error:
        result["error"] = error
    return result


def _github_compare_url(url: str, previous_commit: str, remote_head_commit: str) -> str:
    return f"{url.rstrip('/')}/compare/{previous_commit}...{remote_head_commit}"


def _fetch_remote_head_commit(url: str) -> str:
    if not url.startswith("https://github.com/"):
        raise ValueError("source URL must be a GitHub HTTPS URL")
    try:
        completed = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=GIT_REMOTE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"git ls-remote failed: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise ValueError(f"git ls-remote exited {completed.returncode}: {stderr}")
    commit = _parse_ls_remote_head(completed.stdout)
    if not commit:
        raise ValueError("git ls-remote did not return a valid HEAD commit")
    return commit


def _parse_ls_remote_head(stdout: str) -> str:
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "HEAD" and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            return parts[0]
    return ""


def _parse_latest_commit_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--latest-observed-commit must use REPO=SHA format: {value}")
        repo, commit = value.split("=", 1)
        if not repo.strip() or not commit.strip():
            raise ValueError(f"--latest-observed-commit must use REPO=SHA format: {value}")
        overrides[repo.strip()] = commit.strip()
    return overrides


def _validate_timestamp(value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append("generated_at must be a non-empty ISO timestamp")
        return
    parsed = _parse_generated_at_timestamp(value, errors)
    if parsed is None:
        return
    if not _is_aware_datetime(parsed):
        errors.append("generated_at must include a timezone offset")


def _is_aware_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _parse_generated_at_timestamp(
    value: str, errors: list[str]
) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("generated_at must be parseable as ISO datetime")
        return None


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


def _validate_optional_commit(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value.strip()):
        errors.append(f"{field} must be a 40-character lowercase git SHA when provided")


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        _validate_string_list_item(item, f"{field}[{index}]", errors)


def _validate_string_list_item(item: Any, field: str, errors: list[str]) -> None:
    if not isinstance(item, str) or not item.strip():
        errors.append(f"{field} must be a non-empty string")


def _validate_evidence_paths(
    value: Any,
    field: str,
    workspace_root: Path,
    errors: list[str],
    *,
    tracked_paths: set[str] | None,
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        _validate_evidence_path(
            item,
            f"{field}[{index}]",
            workspace_root,
            errors,
            tracked_paths=tracked_paths,
        )


def _validate_evidence_path(
    item: Any,
    path_field: str,
    workspace_root: Path,
    errors: list[str],
    *,
    tracked_paths: set[str] | None,
) -> None:
    path_value = _require_string(item, path_field, errors)
    if not path_value:
        return
    if not _is_repo_relative(path_value):
        errors.append(f"{path_field} must be a repo-relative path")
        return
    if not (workspace_root / path_value).exists():
        errors.append(f"{path_field} must exist in the workspace")
        return
    if not _is_git_tracked(workspace_root, path_value, tracked_paths=tracked_paths):
        errors.append(f"{path_field} must be tracked by git")


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return False
    if normalized.startswith("/") or _has_parent_directory_reference(normalized):
        return False
    return not Path(value).is_absolute()


def _has_parent_directory_reference(normalized: str) -> bool:
    return normalized.startswith("../") or "/../" in f"/{normalized}/"


def _git_tracked_paths(workspace_root: Path) -> set[str] | None:
    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=workspace_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            timeout=GIT_TRACKED_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return {_normalize_repo_path(line) for line in completed.stdout.splitlines() if line.strip()}


def _is_git_tracked(
    workspace_root: Path,
    path_value: str,
    *,
    tracked_paths: set[str] | None = None,
) -> bool:
    if tracked_paths is not None:
        return _normalize_repo_path(path_value) in tracked_paths
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path_value],
            cwd=workspace_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            timeout=GIT_TRACKED_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _normalize_repo_path(path_value: str) -> str:
    return path_value.replace("\\", "/").strip()


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
