from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "github_modernization_sources.json"
DEFAULT_TIMEOUT_SECONDS = 20.0
GITHUB_API_VERSION = "2022-11-28"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import github_modernization_radar as radar  # noqa: E402

FetchRepo = Callable[[str, float], dict[str, Any]]
FETCH_FAILURE_TYPE = "fetch_error"
RATE_LIMIT_FAILURE_TYPE = "github_api_rate_limit"
VIABILITY_FAILURE_TYPE = "metadata_viability"


class GitHubApiError(RuntimeError):
    def __init__(self, repo: str, status_code: int, message: str, *, failure_type: str, requires_token: bool) -> None:
        self.repo = repo
        self.status_code = status_code
        self.failure_type = failure_type
        self.requires_token = requires_token
        super().__init__(f"GitHub API returned {status_code} for {repo}: {message}")


def fetch_repo_metadata(repo: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}",
        headers=_github_headers(),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        failure_type, requires_token = _classify_http_error(exc.code, body, exc.headers)
        raise GitHubApiError(
            repo,
            exc.code,
            body[:200],
            failure_type=failure_type,
            requires_token=requires_token,
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"GitHub API returned non-object payload for {repo}")
    return {
        "repo": repo,
        "html_url": payload.get("html_url"),
        "default_branch": payload.get("default_branch"),
        "pushed_at": payload.get("pushed_at"),
        "updated_at": payload.get("updated_at"),
        "archived": payload.get("archived"),
        "disabled": payload.get("disabled"),
        "visibility": payload.get("visibility"),
        "stargazers_count": payload.get("stargazers_count"),
        "forks_count": payload.get("forks_count"),
        "open_issues_count": payload.get("open_issues_count"),
        "license": _license_spdx(payload.get("license")),
    }


def collect_source_freshness(
    manifest_path: Path,
    *,
    fetch_repo: FetchRepo = fetch_repo_metadata,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    payload = radar.load_manifest(manifest_path)
    errors = radar.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))

    records: list[dict[str, Any]] = []
    for source in payload["sources"]:
        repo = source["repo"]
        try:
            metadata = fetch_repo(repo, timeout_seconds)
            viability_error = _metadata_viability_error(metadata)
            records.append(
                {
                    "repo": repo,
                    "category": source["category"],
                    "adoption_status": source["adoption_status"],
                    "status": "fail" if viability_error else "pass",
                    "metadata": metadata,
                    "error": viability_error,
                    "failure_type": VIABILITY_FAILURE_TYPE if viability_error else "",
                    "requires_token": False,
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep per-repo failure visible in report.
            failure_type, requires_token = _classify_exception(exc)
            records.append(
                {
                    "repo": repo,
                    "category": source["category"],
                    "adoption_status": source["adoption_status"],
                    "status": "fail",
                    "metadata": {},
                    "error": str(exc),
                    "failure_type": failure_type,
                    "requires_token": requires_token,
                }
            )
    failed = [record for record in records if record["status"] != "pass"]
    rate_limited = [record for record in failed if record.get("failure_type") == RATE_LIMIT_FAILURE_TYPE]
    token_available = _github_token_available()
    token_required = bool(rate_limited) and not token_available
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if failed else "pass",
        "complete": not failed,
        "partial": bool(failed) and len(failed) < len(records),
        "source_count": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "rate_limited": bool(rate_limited),
        "rate_limited_count": len(rate_limited),
        "token_available": token_available,
        "token_required": token_required,
        "token_hint": _token_hint(token_required),
        "manifest_generated_at": payload.get("generated_at"),
        "github_api_version": GITHUB_API_VERSION,
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Source Freshness Snapshot",
        "",
        f"- Status: `{report['status']}`",
        f"- Complete: `{str(report.get('complete', report['status'] == 'pass')).lower()}`",
        f"- Partial: `{str(report.get('partial', False)).lower()}`",
        f"- Sources: `{report['source_count']}`",
        f"- Passed: `{report['passed']}`",
        f"- Failed: `{report['failed']}`",
        f"- Rate-limited failures: `{report.get('rate_limited_count', 0)}`",
        f"- Token available: `{str(report.get('token_available', False)).lower()}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- GitHub API version: `{report['github_api_version']}`",
        "",
        "## Repositories",
        "",
        "| Repo | Status | Default branch | Pushed at | Updated at | Stars | Forks | Archived | Disabled |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for record in report["records"]:
        metadata = record.get("metadata", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    record["repo"],
                    record["status"],
                    str(metadata.get("default_branch", "")),
                    str(metadata.get("pushed_at", "")),
                    str(metadata.get("updated_at", "")),
                    str(metadata.get("stargazers_count", "")),
                    str(metadata.get("forks_count", "")),
                    str(metadata.get("archived", "")),
                    str(metadata.get("disabled", "")),
                ]
            )
            + " |"
        )
    failures = [record for record in report["records"] if record["status"] != "pass"]
    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(
            f"- `{record['repo']}`: [{record.get('failure_type') or 'unknown'}] {record['error']}"
            for record in failures
        )
    else:
        lines.append("- none")
    if report.get("token_hint"):
        lines.extend(["", "## Token Boundary", "", f"- {report['token_hint']}"])
    return "\n".join(lines).rstrip() + "\n"


def run(
    manifest_path: Path,
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    report = collect_source_freshness(manifest_path, timeout_seconds=timeout_seconds)
    if json_out:
        _write_json_atomic(json_out, report)
    if markdown_out:
        _write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] != "pass":
        detail = f"{report['failed']} GitHub source checks failed"
        if report.get("rate_limited_count"):
            detail += f"; rate_limited={report['rate_limited_count']}; {report.get('token_hint')}"
        raise ValueError(detail)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check live GitHub metadata for modernization radar sources.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        report = run(args.manifest, json_out=args.json_out, markdown_out=args.markdown_out, timeout_seconds=args.timeout)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"github source freshness failed: {exc}", file=sys.stderr)
        return 1
    print(
        "github source freshness valid: "
        f"{report['source_count']} sources, passed={report['passed']}, failed={report['failed']}"
    )
    return 0


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BIOJUHO-AutoResearch-Freshness/1.0",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_token_available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))


def _classify_http_error(status_code: int, body: str, headers: Any) -> tuple[str, bool]:
    if _is_rate_limit_error(status_code, body, headers):
        return RATE_LIMIT_FAILURE_TYPE, True
    return FETCH_FAILURE_TYPE, False


def _classify_exception(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, GitHubApiError):
        return exc.failure_type, exc.requires_token
    if _is_rate_limit_text(str(exc)):
        return RATE_LIMIT_FAILURE_TYPE, True
    return FETCH_FAILURE_TYPE, False


def _is_rate_limit_error(status_code: int, body: str, headers: Any) -> bool:
    if status_code not in {403, 429}:
        return False
    remaining = _header_value(headers, "X-RateLimit-Remaining")
    return remaining == "0" or _is_rate_limit_text(body)


def _is_rate_limit_text(value: str) -> bool:
    lower = value.lower()
    return "rate limit" in lower or "rate-limited" in lower or "rate limited" in lower


def _header_value(headers: Any, name: str) -> str:
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        return str(value) if value is not None else ""
    return ""


def _token_hint(token_required: bool) -> str:
    if not token_required:
        return ""
    return "Set GITHUB_TOKEN or GH_TOKEN before adopting this live source snapshot."


def _license_spdx(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    spdx = value.get("spdx_id")
    return spdx if isinstance(spdx, str) else None


def _metadata_viability_error(metadata: dict[str, Any]) -> str:
    if metadata.get("archived") is True:
        return "repository is archived"
    if metadata.get("disabled") is True:
        return "repository is disabled"
    for field in ["html_url", "default_branch", "pushed_at", "updated_at"]:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"missing {field}"
    return ""


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
