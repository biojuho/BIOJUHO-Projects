from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_widget_click_smoke.py"


def load_click_smoke_module():
    spec = importlib.util.spec_from_file_location("canva_widget_click_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_report_counts_actions_and_messages() -> None:
    smoke = load_click_smoke_module()
    report = smoke.build_report(
        "http://127.0.0.1:5176/src/dev/preview.html",
        [
            smoke.ActionResult("toggle-theme", True, "dark_before=false dark_after=true"),
            smoke.ActionResult("open-design-keyboard", False, "timeout"),
        ],
        [{"type": "canva-design-clicked", "data": {"designId": "design_1"}}],
        ["open-design-keyboard: timeout"],
        status="fail",
    )

    assert report["tool"] == "canva_widget_click_smoke"
    assert report["summary"] == {"actions": 2, "passed": 1, "failed": 1, "messages": 1}
    assert report["messages"][0]["capture_index"] == 0
    assert report["failures"] == ["open-design-keyboard: timeout"]


def test_format_markdown_lists_actions_messages_and_failures() -> None:
    smoke = load_click_smoke_module()
    report = smoke.build_report(
        "http://127.0.0.1:5176/src/dev/preview.html",
        [smoke.ActionResult("select-candidate-keyboard", True, "canva-create-from-candidate.candidateId=candidate_2 via Enter")],
        [{"type": "canva-create-from-candidate", "data": {"candidateId": "candidate_2"}}],
        [],
        status="pass",
    )

    markdown = smoke.format_markdown(report)

    assert "Canva Widget Click Smoke" in markdown
    assert "Status: `pass`" in markdown
    assert "`PASS` `select-candidate-keyboard`" in markdown
    assert "`0` `canva-create-from-candidate` `candidate_2`" in markdown


def test_format_markdown_renders_continuation_message_identity() -> None:
    smoke = load_click_smoke_module()
    report = smoke.build_report(
        "http://127.0.0.1:5176/src/dev/preview.html",
        [smoke.ActionResult("load-more-click", True, "canva-load-more.continuation=next_page_token_xyz")],
        [
            {
                "type": "canva-load-more",
                "data": {
                    "toolName": "search-designs",
                    "arguments": {"query": "business flyer", "continuation": "next_page_token_xyz"},
                    "continuation": "next_page_token_xyz",
                },
            }
        ],
        [],
        status="pass",
    )

    markdown = smoke.format_markdown(report)

    assert "`PASS` `load-more-click`" in markdown
    assert "`0` `canva-load-more` `next_page_token_xyz`" in markdown


def test_build_report_preserves_capture_order_over_payload_timestamps() -> None:
    smoke = load_click_smoke_module()
    first_message = {
        "capture_index": 0,
        "type": "canva-create-from-candidate",
        "data": {
            "candidateId": "candidate_1",
            "createdAt": "2026-06-05T10:00:00Z",
            "parts": [{"createdAt": "2026-06-05T10:00:30Z"}],
        },
    }
    second_message = {
        "capture_index": 1,
        "type": "canva-design-clicked",
        "data": {
            "designId": "design_1",
            "createdAt": "2026-06-05T10:00:03Z",
        },
    }

    report = smoke.build_report(
        "http://127.0.0.1:5176/src/dev/preview.html",
        [],
        [first_message, second_message],
        [],
        status="pass",
    )

    assert [message["capture_index"] for message in report["messages"]] == [0, 1]
    assert [message["type"] for message in report["messages"]] == [
        "canva-create-from-candidate",
        "canva-design-clicked",
    ]
    assert report["messages"][0]["data"]["parts"][0]["createdAt"] == "2026-06-05T10:00:30Z"


def test_record_action_captures_unexpected_exceptions() -> None:
    smoke = load_click_smoke_module()
    actions = []
    failures = []

    smoke._record_action(actions, failures, "bad-action", lambda: (_ for _ in ()).throw(TypeError("bad arg")))

    assert actions == [smoke.ActionResult(name="bad-action", ok=False, detail="bad arg")]
    assert failures == ["bad-action: bad arg"]


def test_cli_writes_blocked_reports_when_playwright_missing(monkeypatch, tmp_path: Path) -> None:
    smoke = load_click_smoke_module()
    monkeypatch.setattr(smoke, "sync_playwright", None)
    json_out = tmp_path / "click-smoke.json"
    markdown_out = tmp_path / "click-smoke.md"

    result = smoke.main(["--json-out", str(json_out), "--markdown-out", str(markdown_out)])

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 2
    assert payload["status"] == "blocked"
    assert "Playwright is not installed" in payload["failures"]
    assert "Status: `blocked`" in markdown
