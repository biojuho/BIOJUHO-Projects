from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "github_source_review_queue.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "github_modernization_sources.json"
CHANGE_SUMMARY_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json"
QUEUE_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.json"
QUEUE_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.md"


def load_module():
    spec = importlib.util.spec_from_file_location("github_source_review_queue", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_review_queue_prioritizes_source_code_movement(tmp_path: Path) -> None:
    queue = load_module()
    change_summary = _change_summary(
        [
            {
                "repo": "modelcontextprotocol/python-sdk",
                "category": "official-mcp-python-sdk",
                "adoption_status": "partially_adopted",
                "changed_fields": ["updated_at", "stargazers_count"],
                "changes": {},
            },
            {
                "repo": "mastra-ai/mastra",
                "category": "typescript-agent-application-framework",
                "adoption_status": "partially_adopted",
                "changed_fields": ["pushed_at", "updated_at", "stargazers_count"],
                "changes": {},
            },
        ]
    )
    path = tmp_path / "change-summary.json"
    path.write_text(json.dumps(change_summary), encoding="utf-8")

    report = queue.build_review_queue(path, MANIFEST_PATH)

    assert report["queued_repositories"] == 2
    assert report["items"][0]["repo"] == "mastra-ai/mastra"
    assert report["items"][0]["priority"] == "high"
    assert report["items"][0]["review_reason"] == "upstream source code moved since the baseline snapshot"
    assert report["items"][1]["repo"] == "modelcontextprotocol/python-sdk"
    assert report["items"][1]["priority"] == "medium"


def test_build_review_queue_rejects_uncompared_change_summary(tmp_path: Path) -> None:
    queue = load_module()
    change_summary = _change_summary([])
    change_summary["change_summary"]["compared"] = False
    path = tmp_path / "change-summary.json"
    path.write_text(json.dumps(change_summary), encoding="utf-8")

    try:
        queue.build_review_queue(path, MANIFEST_PATH)
    except ValueError as exc:
        assert "change_summary.compared must be true" in str(exc)
    else:
        raise AssertionError("expected uncompared summary to fail")


def test_cli_writes_review_queue_outputs(tmp_path: Path) -> None:
    queue = load_module()
    json_out = tmp_path / "queue.json"
    markdown_out = tmp_path / "queue.md"

    result = queue.main(
        [
            "--change-summary",
            str(CHANGE_SUMMARY_PATH),
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["status"] == "pass"
    assert payload["queued_repositories"] == payload["changed_repositories"] == 27
    assert payload["items"][0]["rank"] == 1
    assert "GitHub Source Review Queue" in markdown
    assert "Review upstream commits or release notes" in markdown


def test_checked_in_review_queue_matches_change_summary_and_renderer() -> None:
    queue = load_module()

    expected = queue.build_review_queue(CHANGE_SUMMARY_PATH, MANIFEST_PATH)
    expected_json = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    expected_markdown = queue.render_markdown(expected)

    assert QUEUE_JSON_PATH.read_text(encoding="utf-8") == expected_json
    assert QUEUE_MARKDOWN_PATH.read_text(encoding="utf-8") == expected_markdown


def _change_summary(records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T00:00:00+00:00",
        "status": "pass",
        "source_count": 30,
        "passed": 30,
        "failed": 0,
        "change_summary": {
            "compared": True,
            "baseline_generated_at": "2026-06-04T18:54:22.968302+00:00",
            "changed_repositories": len(records),
            "new_repositories": [],
            "removed_repositories": [],
            "records": records,
        },
    }
