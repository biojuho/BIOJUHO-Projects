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
        raise RuntimeError(f"GitHub API returned {exc.code} for {repo}: {body[:200]}") from exc
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
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep per-repo failure visible in report.
            records.append(
                {
                    "repo": repo,
                    "category": source["category"],
                    "adoption_status": source["adoption_status"],
                    "status": "fail",
                    "metadata": {},
                    "error": str(exc),
                }
            )
    failed = [record for record in records if record["status"] != "pass"]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if failed else "pass",
        "source_count": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "manifest_generated_at": payload.get("generated_at"),
        "github_api_version": GITHUB_API_VERSION,
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Source Freshness Snapshot",
        "",
        f"- Status: `{report['status']}`",
        f"- Sources: `{report['source_count']}`",
        f"- Passed: `{report['passed']}`",
        f"- Failed: `{report['failed']}`",
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
        lines.extend(f"- `{record['repo']}`: {record['error']}" for record in failures)
    else:
        lines.append("- none")
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
        raise ValueError(f"{report['failed']} GitHub source checks failed")
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
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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
