from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_source_commit_digest.py"
DIGEST_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json"
DIGEST_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md"


def load_module():
    spec = importlib.util.spec_from_file_location("github_source_commit_digest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_commit_digest_selects_pushed_queue_items_and_windows(tmp_path: Path) -> None:
    digest = load_module()
    queue_path = tmp_path / "queue.json"
    change_summary_path = tmp_path / "change-summary.json"
    queue_path.write_text(json.dumps(_queue_payload()), encoding="utf-8")
    change_summary_path.write_text(json.dumps(_change_summary_payload()), encoding="utf-8")
    calls = []

    def fake_fetch(repo: str, since: str, until: str, limit: int, timeout_seconds: float):
        calls.append((repo, since, until, limit, timeout_seconds))
        return [
            {
                "sha": f"{repo[:4]}12345678",
                "html_url": f"https://github.com/{repo}/commit/abc",
                "subject": f"update {repo}",
                "author": "bot",
                "authored_at": until,
                "committed_at": until,
            }
        ]

    report = digest.build_commit_digest(
        queue_path,
        change_summary_path,
        top=2,
        max_commits=3,
        timeout_seconds=7,
        fetch_commits=fake_fetch,
    )

    assert report["status"] == "pass"
    assert report["selected_repositories"] == 2
    assert report["selection_batch"]["candidate_repositories"] == 2
    assert report["selection_batch"]["overflow_repositories"] == 0
    assert [item["repo"] for item in report["items"]] == [
        "microsoft/agent-framework",
        "mastra-ai/mastra",
    ]
    assert calls == [
        ("microsoft/agent-framework", "2026-06-04T18:52:34Z", "2026-06-04T22:36:03Z", 3, 7),
        ("mastra-ai/mastra", "2026-06-04T18:53:13Z", "2026-06-04T23:01:11Z", 3, 7),
    ]
    assert report["items"][0]["decision"] == "review_required_before_local_adoption"


def test_build_commit_digest_reports_unfetched_overflow_queue(tmp_path: Path) -> None:
    digest = load_module()
    queue_path = tmp_path / "queue.json"
    change_summary_path = tmp_path / "change-summary.json"
    queue_path.write_text(json.dumps(_queue_payload()), encoding="utf-8")
    change_summary_path.write_text(json.dumps(_change_summary_payload()), encoding="utf-8")

    report = digest.build_commit_digest(
        queue_path,
        change_summary_path,
        top=1,
        fetch_commits=lambda repo, since, until, limit, timeout_seconds: [],
    )

    assert report["selected_repositories"] == 1
    assert report["selection_batch"]["candidate_repositories"] == 2
    assert report["selection_batch"]["overflow_repositories"] == 1
    assert report["selection_batch"]["overflow_policy"] == "defer_to_next_digest_without_fetching"
    assert report["selection_batch"]["overflow_queue"] == [
        {
            "rank": 2,
            "repo": "mastra-ai/mastra",
            "priority": "high",
            "score": 46,
        }
    ]


def test_build_commit_digest_records_fetch_failures(tmp_path: Path) -> None:
    digest = load_module()
    queue_path = tmp_path / "queue.json"
    change_summary_path = tmp_path / "change-summary.json"
    queue_path.write_text(json.dumps(_queue_payload()), encoding="utf-8")
    change_summary_path.write_text(json.dumps(_change_summary_payload()), encoding="utf-8")

    def fake_fetch(repo: str, since: str, until: str, limit: int, timeout_seconds: float):
        raise RuntimeError("rate limit exceeded")

    report = digest.build_commit_digest(
        queue_path,
        change_summary_path,
        top=1,
        fetch_commits=fake_fetch,
    )

    assert report["status"] == "fail"
    assert report["failed_repositories"] == 1
    assert report["items"][0]["failure_type"] == "github_api_rate_limit"
    assert report["items"][0]["requires_token"] is True
    assert report["items"][0]["decision"] == "blocked_until_commit_digest_fetch_passes"


def test_render_markdown_includes_commit_digest_decisions(tmp_path: Path) -> None:
    digest = load_module()
    queue_path = tmp_path / "queue.json"
    change_summary_path = tmp_path / "change-summary.json"
    queue_path.write_text(json.dumps(_queue_payload()), encoding="utf-8")
    change_summary_path.write_text(json.dumps(_change_summary_payload()), encoding="utf-8")

    report = digest.build_commit_digest(
        queue_path,
        change_summary_path,
        top=1,
        fetch_commits=lambda repo, since, until, limit, timeout_seconds: [],
    )
    markdown = digest.render_markdown(report)

    assert "GitHub Source Commit Delta Digest" in markdown
    assert "Selection Batch" in markdown
    assert "Overflow repositories: `1`" in markdown
    assert "mastra-ai/mastra" in markdown
    assert "microsoft/agent-framework" in markdown
    assert "no_local_adoption_commit_window_empty" in markdown
    assert "No commit subjects returned for the pushed_at window." in markdown


def test_fetch_commit_delta_falls_back_to_atom_feed_on_rate_limit(monkeypatch) -> None:
    digest = load_module()

    def fake_api(repo: str, since: str, until: str, limit: int, timeout_seconds: float):
        raise digest.freshness.GitHubApiError(
            repo,
            403,
            "rate limit",
            failure_type=digest.freshness.RATE_LIMIT_FAILURE_TYPE,
            requires_token=True,
        )

    def fake_feed(repo: str, since: str, until: str, limit: int, timeout_seconds: float):
        return [
            {
                "sha": "abc123",
                "html_url": f"https://github.com/{repo}/commit/abc123",
                "subject": "fallback commit",
                "author": "bot",
                "authored_at": until,
                "committed_at": until,
                "source": "github_atom_feed",
            }
        ]

    monkeypatch.setattr(digest, "_fetch_commit_api_delta", fake_api)
    monkeypatch.setattr(digest, "fetch_commit_feed_delta", fake_feed)

    commits = digest.fetch_commit_delta(
        "microsoft/agent-framework",
        "2026-06-04T18:52:34Z",
        "2026-06-04T22:36:03Z",
    )

    assert commits[0]["source"] == "github_atom_feed"
    assert commits[0]["subject"] == "fallback commit"


def test_fetch_commit_feed_delta_tries_master_when_main_feed_404(monkeypatch) -> None:
    digest = load_module()
    seen_urls: list[str] = []
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>fix: branch fallback</title>
    <updated>2026-06-04T20:00:00Z</updated>
    <author><name>bot</name></author>
    <link rel="alternate" href="https://github.com/Significant-Gravitas/AutoGPT/commit/abc123456789"/>
    <id>tag:github.com,2008:Grit::Commit/abc123456789</id>
  </entry>
</feed>"""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return payload

    def fake_urlopen(request, timeout: float):
        seen_urls.append(request.full_url)
        if request.full_url.endswith("/commits/main.atom"):
            raise digest.urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO())
        return FakeResponse()

    monkeypatch.setattr(digest.urllib.request, "urlopen", fake_urlopen)

    commits = digest.fetch_commit_feed_delta(
        "Significant-Gravitas/AutoGPT",
        "2026-06-04T19:00:00Z",
        "2026-06-04T21:00:00Z",
    )

    assert seen_urls == [
        "https://github.com/Significant-Gravitas/AutoGPT/commits/main.atom",
        "https://github.com/Significant-Gravitas/AutoGPT/commits/master.atom",
    ]
    assert commits[0]["subject"] == "fix: branch fallback"
    assert commits[0]["source"] == "github_atom_feed"


def test_checked_in_commit_digest_matches_renderer() -> None:
    digest = load_module()
    payload = json.loads(DIGEST_JSON_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "pass"
    assert payload["selected_repositories"] == 4
    assert payload["failed_repositories"] == 0
    assert payload["selection_batch"]["candidate_repositories"] >= payload["selected_repositories"]
    assert payload["selection_batch"]["overflow_policy"] == "defer_to_next_digest_without_fetching"
    assert [item["repo"] for item in payload["items"]] == [
        "microsoft/agent-framework",
        "mastra-ai/mastra",
        "microsoft/playwright-mcp",
        "vercel/ai",
    ]
    decisions = {item["repo"]: item["decision"] for item in payload["items"]}
    assert decisions["microsoft/agent-framework"] == "review_required_before_local_adoption"
    assert decisions["mastra-ai/mastra"] == "review_required_before_local_adoption"
    assert decisions["microsoft/playwright-mcp"] == "no_local_adoption_commit_window_empty"
    assert decisions["vercel/ai"] == "review_required_before_local_adoption"
    assert DIGEST_MARKDOWN_PATH.read_text(encoding="utf-8") == digest.render_markdown(payload)


def _queue_payload() -> dict:
    return {
        "status": "pass",
        "items": [
            {
                "rank": 1,
                "repo": "microsoft/agent-framework",
                "url": "https://github.com/microsoft/agent-framework",
                "category": "enterprise-agent-framework",
                "adoption_status": "partially_adopted",
                "priority": "high",
                "score": 47,
                "changed_fields": ["pushed_at", "updated_at"],
                "local_evidence": ["docs/reports/agent-framework.md"],
            },
            {
                "rank": 2,
                "repo": "mastra-ai/mastra",
                "url": "https://github.com/mastra-ai/mastra",
                "category": "typescript-agent-application-framework",
                "adoption_status": "partially_adopted",
                "priority": "high",
                "score": 46,
                "changed_fields": ["pushed_at", "updated_at"],
                "local_evidence": ["apps/dashboard"],
            },
            {
                "rank": 3,
                "repo": "modelcontextprotocol/python-sdk",
                "url": "https://github.com/modelcontextprotocol/python-sdk",
                "category": "official-mcp-python-sdk",
                "adoption_status": "partially_adopted",
                "priority": "medium",
                "score": 20,
                "changed_fields": ["updated_at"],
                "local_evidence": [],
            },
        ],
    }


def _change_summary_payload() -> dict:
    return {
        "status": "pass",
        "generated_at": "2026-06-04T23:01:51.324669+00:00",
        "change_summary": {
            "compared": True,
            "baseline_generated_at": "2026-06-04T18:54:22.968302+00:00",
            "records": [
                {
                    "repo": "microsoft/agent-framework",
                    "changes": {
                        "pushed_at": {
                            "previous": "2026-06-04T18:52:34Z",
                            "current": "2026-06-04T22:36:03Z",
                        }
                    },
                },
                {
                    "repo": "mastra-ai/mastra",
                    "changes": {
                        "pushed_at": {
                            "previous": "2026-06-04T18:53:13Z",
                            "current": "2026-06-04T23:01:11Z",
                        }
                    },
                },
            ],
        },
    }
