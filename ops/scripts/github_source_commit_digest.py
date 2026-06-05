from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_QUEUE = WORKSPACE_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.json"
DEFAULT_CHANGE_SUMMARY = (
    WORKSPACE_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json"
)
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_TOP = 4
DEFAULT_MAX_COMMITS = 5

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import github_source_freshness as freshness  # noqa: E402

FetchCommits = Callable[[str, str, str, int, float], list[dict[str, Any]]]


def fetch_commit_delta(
    repo: str,
    since: str,
    until: str,
    limit: int = DEFAULT_MAX_COMMITS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    try:
        return _fetch_commit_api_delta(repo, since, until, limit, timeout_seconds)
    except freshness.GitHubApiError as exc:
        if exc.failure_type == freshness.RATE_LIMIT_FAILURE_TYPE:
            return fetch_commit_feed_delta(repo, since, until, limit, timeout_seconds)
        raise


def fetch_commit_feed_delta(
    repo: str,
    since: str,
    until: str,
    limit: int = DEFAULT_MAX_COMMITS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        f"https://github.com/{repo}/commits/main.atom",
        headers={"User-Agent": "BIOJUHO-AutoResearch-CommitDigest/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    return _parse_commit_feed(payload, since=since, until=until, limit=limit)


def _fetch_commit_api_delta(
    repo: str,
    since: str,
    until: str,
    limit: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"since": since, "until": until, "per_page": str(limit)})
    headers = freshness._github_headers()
    headers["User-Agent"] = "BIOJUHO-AutoResearch-CommitDigest/1.0"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits?{params}",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        failure_type, requires_token = freshness._classify_http_error(exc.code, body, exc.headers)
        raise freshness.GitHubApiError(
            repo,
            exc.code,
            body[:200],
            failure_type=failure_type,
            requires_token=requires_token,
        ) from exc
    if not isinstance(payload, list):
        raise RuntimeError(f"GitHub API returned non-array commit payload for {repo}")
    return [_simplify_commit(item) for item in payload if isinstance(item, dict)]


def build_commit_digest(
    queue_path: Path,
    change_summary_path: Path,
    *,
    top: int = DEFAULT_TOP,
    max_commits: int = DEFAULT_MAX_COMMITS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fetch_commits: FetchCommits = fetch_commit_delta,
) -> dict[str, Any]:
    queue = _load_json(queue_path)
    change_summary = _load_json(change_summary_path)
    errors = _validate_queue(queue)
    errors.extend(_validate_change_summary(change_summary))
    if errors:
        raise ValueError("\n".join(errors))

    change_records = {
        record["repo"]: record
        for record in change_summary["change_summary"]["records"]
        if isinstance(record, dict) and isinstance(record.get("repo"), str)
    }
    pushed_candidates = _pushed_queue_items(queue["items"])
    selected = pushed_candidates[:top]

    items = [
        _build_digest_item(
            item,
            change_records.get(item["repo"], {}),
            max_commits=max_commits,
            timeout_seconds=timeout_seconds,
            fetch_commits=fetch_commits,
        )
        for item in selected
    ]
    failed = [item for item in items if item["status"] != "pass"]

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if failed else "pass",
        "complete": not failed,
        "source_queue": _display_path(queue_path),
        "source_change_summary": _display_path(change_summary_path),
        "source_change_generated_at": change_summary["generated_at"],
        "baseline_generated_at": change_summary["change_summary"].get("baseline_generated_at", ""),
        "github_api_version": freshness.GITHUB_API_VERSION,
        "token_available": freshness._github_token_available(),
        "selected_repositories": len(items),
        "failed_repositories": len(failed),
        "commit_limit_per_repo": max_commits,
        "selection_batch": _selection_batch(pushed_candidates, selected, batch_size=top),
        "selection_policy": (
            "Select the highest-ranked queued repositories with pushed_at movement, then review live commit "
            "subjects before any local adoption decision. Repositories beyond the configured batch are "
            "reported as overflow for the next digest instead of being silently hidden."
        ),
        "items": items,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Source Commit Delta Digest",
        "",
        f"- Status: `{report['status']}`",
        f"- Complete: `{str(report.get('complete', False)).lower()}`",
        f"- Selected repositories: `{report['selected_repositories']}`",
        f"- Failed repositories: `{report['failed_repositories']}`",
        f"- Commit limit per repo: `{report['commit_limit_per_repo']}`",
        f"- Token available: `{str(report.get('token_available', False)).lower()}`",
        f"- Candidate repositories with pushed_at movement: `{report['selection_batch']['candidate_repositories']}`",
        f"- Overflow repositories: `{report['selection_batch']['overflow_repositories']}`",
        f"- Source queue: `{report['source_queue']}`",
        f"- Source change summary: `{report['source_change_summary']}`",
        f"- Baseline generated at: `{report['baseline_generated_at']}`",
        f"- Source change generated at: `{report['source_change_generated_at']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Digest",
        "",
        "| Rank | Repo | Window | Commits | Latest commit subjects | Decision |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for item in report["items"]:
        subjects = "<br>".join(_escape_table_text(commit["subject"]) for commit in item.get("latest_commits", [])[:3])
        if not subjects:
            subjects = _escape_table_text(item.get("error") or "none returned")
        lines.append(
            " | ".join(
                [
                    f"| {item['rank']}",
                    f"`{item['repo']}`",
                    f"`{item['window']['since']}` to `{item['window']['until']}`",
                    str(item["commit_count_returned"]),
                    subjects,
                    item["decision"] + " |",
                ]
            )
        )

    lines.extend(["", "## Selection Batch", ""])
    selection_batch = report["selection_batch"]
    lines.extend(
        [
            f"- Source signal: `{selection_batch['source_signal']}`",
            f"- Batch size: `{selection_batch['batch_size']}`",
            f"- Candidate repositories: `{selection_batch['candidate_repositories']}`",
            f"- Selected repositories: `{selection_batch['selected_repositories']}`",
            f"- Overflow repositories: `{selection_batch['overflow_repositories']}`",
            f"- Overflow policy: `{selection_batch['overflow_policy']}`",
        ]
    )
    if selection_batch["overflow_queue"]:
        lines.extend(["", "| Rank | Repo | Priority | Score |", "| ---: | --- | --- | ---: |"])
        for overflow_item in selection_batch["overflow_queue"]:
            lines.append(
                " | ".join(
                    [
                        f"| {overflow_item['rank']}",
                        f"`{overflow_item['repo']}`",
                        overflow_item["priority"],
                        f"{overflow_item['score']} |",
                    ]
                )
            )

    lines.extend(["", "## Repository Details", ""])
    for item in report["items"]:
        lines.extend(
            [
                f"### {item['repo']}",
                "",
                f"- Source: {item['url']}",
                f"- Category: `{item['category']}`",
                f"- Priority: `{item['priority']}` score `{item['score']}`",
                f"- Fetch source: `{item.get('fetch_source', '')}`",
                f"- Adoption signal: {item['adoption_signal']}",
            ]
        )
        if item.get("local_evidence"):
            lines.append("- Local evidence:")
            lines.extend(f"  - `{path}`" for path in item["local_evidence"])
        else:
            lines.append("- Local evidence: none mapped")
        if item.get("latest_commits"):
            lines.append("- Latest commits:")
            for commit in item["latest_commits"]:
                lines.append(
                    f"  - `{commit['sha']}` `{commit['committed_at']}` "
                    f"{commit['subject']} ({commit['html_url']})"
                )
        else:
            lines.append(f"- Latest commits: {item.get('error') or 'none returned'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run(
    queue_path: Path = DEFAULT_QUEUE,
    *,
    change_summary_path: Path = DEFAULT_CHANGE_SUMMARY,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    top: int = DEFAULT_TOP,
    max_commits: int = DEFAULT_MAX_COMMITS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    report = build_commit_digest(
        queue_path,
        change_summary_path,
        top=top,
        max_commits=max_commits,
        timeout_seconds=timeout_seconds,
    )
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] != "pass":
        raise ValueError(f"{report['failed_repositories']} GitHub commit digest fetches failed")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch live commit deltas for the GitHub source review queue.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--change-summary", type=Path, default=DEFAULT_CHANGE_SUMMARY)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--max-commits", type=int, default=DEFAULT_MAX_COMMITS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        report = run(
            args.queue,
            change_summary_path=args.change_summary,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            top=args.top,
            max_commits=args.max_commits,
            timeout_seconds=args.timeout,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"github source commit digest failed: {exc}", file=sys.stderr)
        return 1
    print(
        "github source commit digest valid: "
        f"selected={report['selected_repositories']}, failed={report['failed_repositories']}"
    )
    return 0


def _build_digest_item(
    item: dict[str, Any],
    change_record: dict[str, Any],
    *,
    max_commits: int,
    timeout_seconds: float,
    fetch_commits: FetchCommits,
) -> dict[str, Any]:
    repo = item["repo"]
    since = _changed_value(change_record, "pushed_at", "previous")
    until = _changed_value(change_record, "pushed_at", "current")
    commits: list[dict[str, Any]] = []
    error = ""
    failure_type = ""
    requires_token = False
    if not since or not until:
        error = "missing pushed_at previous/current window"
        failure_type = "missing_commit_window"
    else:
        try:
            commits = fetch_commits(repo, since, until, max_commits, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - keep per-repo failure visible in report.
            failure_type, requires_token = _classify_exception(exc)
            error = str(exc)
    status = "fail" if error else "pass"
    return {
        "rank": item["rank"],
        "repo": repo,
        "url": item.get("url", ""),
        "category": item.get("category", ""),
        "adoption_status": item.get("adoption_status", ""),
        "priority": item.get("priority", ""),
        "score": item.get("score", 0),
        "status": status,
        "error": error,
        "failure_type": failure_type,
        "requires_token": requires_token,
        "window": {"since": since, "until": until},
        "commit_count_returned": len(commits),
        "commit_limit": max_commits,
        "truncated": len(commits) >= max_commits,
        "fetch_source": _fetch_source(commits, error),
        "latest_commits": commits,
        "decision": _decision(status, commits),
        "adoption_signal": _adoption_signal(item.get("category", ""), commits),
        "local_evidence": item.get("local_evidence", [])[:5],
    }


def _pushed_queue_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in sorted(items, key=lambda value: int(value.get("rank", 999_999)))
        if "pushed_at" in item.get("changed_fields", [])
    ]


def _selection_batch(
    pushed_candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    batch_size: int,
) -> dict[str, Any]:
    selected_repos = {item["repo"] for item in selected}
    overflow = [item for item in pushed_candidates if item["repo"] not in selected_repos]
    return {
        "source_signal": "mastra-ai/mastra opt-in PubSub subscriber batching",
        "batch_size": batch_size,
        "candidate_repositories": len(pushed_candidates),
        "selected_repositories": len(selected),
        "overflow_repositories": len(overflow),
        "overflow_policy": "defer_to_next_digest_without_fetching",
        "overflow_queue": [
            {
                "rank": item["rank"],
                "repo": item["repo"],
                "priority": item.get("priority", ""),
                "score": item.get("score", 0),
            }
            for item in overflow
        ],
    }


def _simplify_commit(item: dict[str, Any]) -> dict[str, Any]:
    commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    commit_author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
    commit_committer = commit.get("committer") if isinstance(commit.get("committer"), dict) else {}
    message = str(commit.get("message") or "").strip()
    subject = message.splitlines()[0] if message else "<empty commit message>"
    return {
        "sha": str(item.get("sha") or "")[:12],
        "html_url": str(item.get("html_url") or ""),
        "subject": _clean_subject(subject),
        "author": str(author.get("login") or commit_author.get("name") or ""),
        "authored_at": str(commit_author.get("date") or ""),
        "committed_at": str(commit_committer.get("date") or ""),
        "source": "github_api",
    }


def _parse_commit_feed(payload: bytes, *, since: str, until: str, limit: int) -> list[dict[str, Any]]:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    since_dt = _parse_github_time(since)
    until_dt = _parse_github_time(until)
    root = ET.fromstring(payload)
    commits: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", namespace):
        updated = entry.findtext("atom:updated", default="", namespaces=namespace)
        updated_dt = _parse_github_time(updated)
        if not (since_dt <= updated_dt <= until_dt):
            continue
        commit_url = _entry_link(entry, namespace)
        sha = commit_url.rstrip("/").split("/")[-1] if commit_url else _entry_sha(entry, namespace)
        author = entry.findtext("atom:author/atom:name", default="", namespaces=namespace)
        subject = _clean_subject(entry.findtext("atom:title", default="", namespaces=namespace))
        commits.append(
            {
                "sha": sha[:12],
                "html_url": commit_url,
                "subject": subject or "<empty commit message>",
                "author": author,
                "authored_at": updated,
                "committed_at": updated,
                "source": "github_atom_feed",
            }
        )
        if len(commits) >= limit:
            break
    return commits


def _parse_github_time(value: str) -> datetime:
    if not value:
        raise ValueError("missing GitHub timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _entry_link(entry: ET.Element, namespace: dict[str, str]) -> str:
    for link in entry.findall("atom:link", namespace):
        if link.attrib.get("rel") == "alternate":
            return link.attrib.get("href", "")
    return ""


def _entry_sha(entry: ET.Element, namespace: dict[str, str]) -> str:
    entry_id = entry.findtext("atom:id", default="", namespaces=namespace)
    return entry_id.rstrip("/").split("/")[-1]


def _decision(status: str, commits: list[dict[str, Any]]) -> str:
    if status != "pass":
        return "blocked_until_commit_digest_fetch_passes"
    if not commits:
        return "no_local_adoption_commit_window_empty"
    return "review_required_before_local_adoption"


def _adoption_signal(category: str, commits: list[dict[str, Any]]) -> str:
    if not commits:
        return "No commit subjects returned for the pushed_at window."
    if category == "enterprise-agent-framework":
        return "Compare workflow and orchestration changes against local agent workflow gate evidence."
    if category in {"typescript-agent-application-framework", "typescript-ai-app-toolkit"}:
        return "Compare TypeScript agent-app changes against dashboard and Canva operator surfaces."
    if category == "mcp-browser-automation":
        return "Compare browser automation changes against direct app-click and browser smoke evidence."
    return "Review commit subjects against the mapped local evidence before adoption."


def _fetch_source(commits: list[dict[str, Any]], error: str) -> str:
    if error:
        return ""
    if commits:
        return str(commits[0].get("source") or "unknown")
    return "none"


def _validate_queue(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("status") != "pass":
        errors.append("queue status must be pass")
    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("queue.items must be an array")
    return errors


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
    if not isinstance(change_summary.get("records"), list):
        errors.append("change_summary.records must be an array")
    return errors


def _changed_value(record: dict[str, Any], field: str, side: str) -> str:
    changes = record.get("changes") if isinstance(record.get("changes"), dict) else {}
    field_change = changes.get(field) if isinstance(changes.get(field), dict) else {}
    value = field_change.get(side)
    return str(value or "")


def _classify_exception(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, freshness.GitHubApiError):
        return exc.failure_type, exc.requires_token
    if "rate limit" in str(exc).lower():
        return freshness.RATE_LIMIT_FAILURE_TYPE, True
    return freshness.FETCH_FAILURE_TYPE, False


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


def _escape_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _clean_subject(value: str) -> str:
    subject = " ".join(str(value or "").replace("\u2026", "...").split())
    if not subject:
        return "<empty commit message>"
    return subject.encode("ascii", errors="replace").decode("ascii")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
