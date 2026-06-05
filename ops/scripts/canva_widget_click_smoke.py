#!/usr/bin/env python3
"""Click and keyboard smoke checks for the Canva widget preview."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depends on operator machine
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

DEFAULT_URL = "http://127.0.0.1:5176/src/dev/preview.html"


@dataclass(frozen=True)
class ActionResult:
    name: str
    ok: bool
    detail: str


def run_click_smoke(url: str = DEFAULT_URL, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
    if sync_playwright is None:
        return build_report(url, [], [], ["Playwright is not installed"], status="blocked")

    timeout_ms = int(timeout_seconds * 1000)
    actions: list[ActionResult] = []
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_failures: list[str] = []
    messages: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        def collect_console(message) -> None:
            if message.type == "error":
                console_errors.append(message.text)

        def collect_page_error(error) -> None:
            page_errors.append(str(error))

        def collect_request_failed(request) -> None:
            failure = request.failure or {}
            error_text = failure.get("errorText") if isinstance(failure, dict) else str(failure)
            request_failures.append(f"{request.url}: {error_text}")

        page.on("console", collect_console)
        page.on("pageerror", collect_page_error)
        page.on("requestfailed", collect_request_failed)
        page.add_init_script(
            """
            window.__canvaClickMessages = [];
            window.__canvaClickMessageSequence = 0;
            window.addEventListener('message', (event) => {
              const data = event.data || {};
              window.__canvaClickMessages.push({
                capture_index: window.__canvaClickMessageSequence++,
                type: data.type || null,
                data: data.data || null
              });
            });
            """
        )

        _record_action(
            actions,
            failures,
            "load-preview",
            lambda: _load_preview(page, url, timeout_ms),
        )
        _record_action(
            actions,
            failures,
            "toggle-theme",
            lambda: _toggle_theme(page, timeout_ms),
        )
        _record_action(
            actions,
            failures,
            "scroll-candidates-right",
            lambda: _click_label(page, "Scroll design candidates right", timeout_ms),
        )
        _record_action(
            actions,
            failures,
            "scroll-candidates-left",
            lambda: _click_label(page, "Scroll design candidates left", timeout_ms),
        )
        _record_action(
            actions,
            failures,
            "select-candidate-click",
            lambda: _click_and_wait_message(
                page,
                "Select design candidate 1",
                "canva-create-from-candidate",
                "candidateId",
                "candidate_1",
                timeout_ms,
            ),
        )
        _record_action(
            actions,
            failures,
            "select-candidate-keyboard",
            lambda: _keyboard_and_wait_message(
                page,
                "Select design candidate 2",
                "Enter",
                "canva-create-from-candidate",
                "candidateId",
                "candidate_2",
                timeout_ms,
            ),
        )
        _record_action(
            actions,
            failures,
            "open-design-click",
            lambda: _click_and_wait_message(
                page,
                "Open Canva design Modern Business Flyer",
                "canva-design-clicked",
                "designId",
                "design_1",
                timeout_ms,
            ),
        )
        _record_action(
            actions,
            failures,
            "open-design-keyboard",
            lambda: _keyboard_and_wait_message(
                page,
                "Open Canva design Corporate Presentation",
                "Space",
                "canva-design-clicked",
                "designId",
                "design_2",
                timeout_ms,
            ),
        )
        _record_action(
            actions,
            failures,
            "load-more-click",
            lambda: _click_and_wait_message(
                page,
                "Load more Canva designs",
                "canva-load-more",
                "continuation",
                "next_page_token_xyz",
                timeout_ms,
            ),
        )

        messages = _captured_messages(page)
        browser.close()

    for message in console_errors[:5]:
        failures.append(f"console error: {message[:300]}")
    for message in page_errors[:5]:
        failures.append(f"page error: {message[:300]}")
    for message in request_failures[:5]:
        failures.append(f"request failed: {message[:300]}")

    return build_report(url, actions, messages, failures, status="fail" if failures else "pass")


def _record_action(
    actions: list[ActionResult],
    failures: list[str],
    name: str,
    action: Callable[[], str],
) -> None:
    try:
        actions.append(ActionResult(name=name, ok=True, detail=action()))
    except Exception as exc:
        detail = str(exc).replace("\r", " ").replace("\n", " ")[:500]
        actions.append(ActionResult(name=name, ok=False, detail=detail))
        failures.append(f"{name}: {detail}")


def _load_preview(page, url: str, timeout_ms: int) -> str:
    response = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    status_code = response.status if response is not None else 0
    if status_code >= 400:
        raise AssertionError(f"HTTP status {status_code}")
    body_text = page.locator("body").inner_text(timeout=timeout_ms)
    for expected in ("Canva Design Widgets", "Modern Business Flyer", "Corporate Presentation"):
        if expected not in body_text:
            raise AssertionError(f"missing expected text {expected!r}")
    return f"loaded status={status_code}"


def _toggle_theme(page, timeout_ms: int) -> str:
    before = _is_dark(page)
    page.get_by_label("Toggle theme").click(timeout=timeout_ms)
    page.wait_for_function(
        "(before) => document.documentElement.classList.contains('dark') !== before",
        arg=before,
        timeout=timeout_ms,
    )
    after = _is_dark(page)
    return f"dark_before={str(before).lower()} dark_after={str(after).lower()}"


def _is_dark(page) -> bool:
    return bool(page.evaluate("document.documentElement.classList.contains('dark')"))


def _click_label(page, label: str, timeout_ms: int) -> str:
    page.get_by_label(label).click(timeout=timeout_ms)
    return f"clicked {label}"


def _click_and_wait_message(
    page,
    label: str,
    message_type: str,
    id_field: str,
    expected_id: str,
    timeout_ms: int,
) -> str:
    page.get_by_label(label).click(timeout=timeout_ms)
    _wait_for_message(page, message_type, id_field, expected_id, timeout_ms)
    return f"{message_type}.{id_field}={expected_id}"


def _keyboard_and_wait_message(
    page,
    label: str,
    key: str,
    message_type: str,
    id_field: str,
    expected_id: str,
    timeout_ms: int,
) -> str:
    page.get_by_label(label).focus(timeout=timeout_ms)
    page.keyboard.press(key)
    _wait_for_message(page, message_type, id_field, expected_id, timeout_ms)
    return f"{message_type}.{id_field}={expected_id} via {key}"


def _wait_for_message(page, message_type: str, id_field: str, expected_id: str, timeout_ms: int) -> None:
    page.wait_for_function(
        """
        ([messageType, idField, expectedId]) =>
          Array.isArray(window.__canvaClickMessages) &&
          window.__canvaClickMessages.some((message) =>
            message.type === messageType && message.data && message.data[idField] === expectedId
          )
        """,
        arg=[message_type, id_field, expected_id],
        timeout=timeout_ms,
    )


def _captured_messages(page) -> list[dict[str, Any]]:
    messages = page.evaluate("window.__canvaClickMessages || []")
    return _normalize_messages(messages if isinstance(messages, list) else [])


def _normalize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        item = dict(message)
        capture_index = item.get("capture_index")
        if not isinstance(capture_index, int) or isinstance(capture_index, bool):
            item["capture_index"] = index
        normalized.append(item)
    return normalized


def build_report(
    url: str,
    actions: list[ActionResult],
    messages: list[dict[str, Any]],
    failures: list[str],
    *,
    status: str,
) -> dict[str, Any]:
    normalized_messages = _normalize_messages(messages)
    return {
        "schema_version": 1,
        "tool": "canva_widget_click_smoke",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "url": url,
        "status": status,
        "summary": {
            "actions": len(actions),
            "passed": sum(1 for action in actions if action.ok),
            "failed": sum(1 for action in actions if not action.ok),
            "messages": len(normalized_messages),
        },
        "actions": [asdict(action) for action in actions],
        "messages": normalized_messages,
        "failures": failures,
    }


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Canva Widget Click Smoke",
        "",
        f"- Status: `{report['status']}`",
        f"- URL: `{report['url']}`",
        f"- Actions: `{summary['actions']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Messages: `{summary['messages']}`",
        "",
        "## Actions",
        "",
    ]
    if not report["actions"]:
        lines.append("- none")
    for action in report["actions"]:
        state = "PASS" if action["ok"] else "FAIL"
        lines.append(f"- `{state}` `{action['name']}` - {action['detail']}")

    lines.extend(["", "## Messages", ""])
    if not report["messages"]:
        lines.append("- none")
    for message in report["messages"]:
        data = message.get("data") if isinstance(message, dict) else None
        lines.append(f"- `{message.get('capture_index')}` `{message.get('type')}` `{_message_id(data)}`")

    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    lines.append("")
    return "\n".join(lines)


def _message_id(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    return str(data.get("candidateId") or data.get("designId") or data.get("continuation") or "")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run click and keyboard smoke checks for the Canva widget preview.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    report = run_click_smoke(args.url, timeout_seconds=args.timeout)
    if args.json_out:
        write_json(args.json_out, report)
    if args.markdown_out:
        write_text(args.markdown_out, format_markdown(report))

    summary = report["summary"]
    print(
        "canva widget click smoke "
        f"{report['status']}: {summary['passed']}/{summary['actions']} actions, failed={summary['failed']}"
    )
    if report["status"] == "blocked":
        return 2
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
