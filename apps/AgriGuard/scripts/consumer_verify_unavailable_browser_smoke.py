from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_VIEWPORT = "390x844"
DEFAULT_TOKEN = "unavailable-smoke-token"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a browser smoke check for the public verify unavailable-service state."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--json-out", default="var/agriguard-consumer-verify-unavailable-browser-smoke.json")
    parser.add_argument("--screenshot", default="var/agriguard-consumer-verify-unavailable-browser-smoke.png")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--viewport", default=DEFAULT_VIEWPORT, help="Viewport size as WIDTHxHEIGHT. Defaults to 390x844.")
    return parser.parse_args()


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def route_url(base_url: str, token: str) -> str:
    return (
        f"{base_url.rstrip('/')}/verify/{token}"
        "?scan_source=unavailable_smoke&scan_session=unavailable-smoke&scan_variant=qr_unavailable_smoke"
    )


def parse_viewport(value: str) -> dict[str, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Viewport must use WIDTHxHEIGHT, for example 390x844.") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("Viewport width and height must be positive integers.")
    return {"width": width, "height": height}


def read_metrics(page: Page) -> dict[str, object]:
    return page.evaluate(
        """() => {
            const doc = document.documentElement;
            const body = document.body;
            return {
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              scrollWidth: Math.max(doc.scrollWidth, body.scrollWidth),
              clientWidth: doc.clientWidth,
              scrollHeight: Math.max(doc.scrollHeight, body.scrollHeight),
              bodyTextLength: (body.textContent || '').trim().length,
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 800),
            };
        }"""
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def page_text(page: Page) -> str:
    return page.locator("body").inner_text(timeout=5_000)


def api_attempt_count(api_responses: list[dict[str, object]], api_request_failures: list[dict[str, str]]) -> int:
    return len(api_responses) + len(api_request_failures)


def is_expected_unavailable_console(message: dict[str, str]) -> bool:
    text = message.get("text", "")
    return message.get("type") == "error" and "Failed to load resource" in text and any(
        value in text for value in ["500", "502", "503", "504"]
    )


def has_unavailable_api_failure(
    api_responses: list[dict[str, object]],
    api_request_failures: list[dict[str, str]],
) -> bool:
    if api_request_failures:
        return True
    return any(int(response.get("status", 0)) >= 500 for response in api_responses)


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    api_request_failures: list[dict[str, str]] = []
    api_responses: list[dict[str, object]] = []
    page_errors: list[dict[str, str]] = []
    viewport = parse_viewport(args.viewport)
    screenshot = Path(args.screenshot)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport, is_mobile=True, has_touch=True)
        page.on(
            "console",
            lambda message: console_messages.append({"type": message.type, "text": message.text})
            if message.type in {"error", "warning"}
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: (
                request_failures.append({"url": request.url, "failure": (request.failure or "unknown")}),
                api_request_failures.append({"url": request.url, "failure": (request.failure or "unknown")})
                if "/api/" in request.url
                else None,
            ),
        )
        page.on(
            "response",
            lambda response: api_responses.append({"url": response.url, "status": response.status})
            if "/api/" in response.url
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append({"message": str(error)}))

        page.goto(route_url(args.base_url, args.token), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_role("heading", name="Verification unavailable").wait_for(timeout=args.timeout_ms)
        initial_text = page_text(page)
        initial_metrics = read_metrics(page)
        checks.append(check("unavailable_state_visible", "Verification unavailable" in initial_text))
        checks.append(check("network_recovery_copy_visible", "Retry with network access or scan again" in initial_text))
        checks.append(check("retry_button_visible", page.get_by_role("button", name="Retry").is_visible()))
        checks.append(check("scan_recovery_link_visible", page.get_by_role("link", name="Scan").is_visible()))
        checks.append(check("no_product_evidence_rendered", "Batch and origin" not in initial_text and "Evidence hash:" not in initial_text))
        checks.append(check("body_not_blank", int(initial_metrics["bodyTextLength"]) > 0, str(initial_metrics)))
        checks.append(check("no_horizontal_overflow", has_no_horizontal_overflow(initial_metrics), str(initial_metrics)))

        attempts_before_retry = api_attempt_count(api_responses, api_request_failures)
        page.get_by_role("button", name="Retry").click(timeout=args.timeout_ms)
        page.get_by_role("heading", name="Verification unavailable").wait_for(timeout=args.timeout_ms)
        page.wait_for_timeout(500)
        retry_text = page_text(page)
        attempts_after_retry = api_attempt_count(api_responses, api_request_failures)
        retry_metrics = read_metrics(page)
        checks.append(check("retry_keeps_unavailable_state_visible", "Verification unavailable" in retry_text))
        checks.append(
            check(
                "retry_attempted_verification_request",
                attempts_after_retry > attempts_before_retry,
                f"{attempts_before_retry}->{attempts_after_retry}",
            )
        )
        checks.append(check("retry_no_horizontal_overflow", has_no_horizontal_overflow(retry_metrics), str(retry_metrics)))

        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=False)
        checks.append(check("screenshot_written", screenshot.exists(), str(screenshot)))
        browser.close()

    unexpected_console_messages = [
        message for message in console_messages if not is_expected_unavailable_console(message)
    ]
    checks.append(check("expected_api_failure_observed", has_unavailable_api_failure(api_responses, api_request_failures)))
    checks.append(
        check(
            "no_unexpected_console_warnings_or_errors",
            len(unexpected_console_messages) == 0,
            str(unexpected_console_messages[:3]),
        )
    )
    checks.append(check("no_page_errors", len(page_errors) == 0, str(page_errors[:3])))

    passed = sum(1 for item in checks if item["ok"])
    return {
        "schema_version": 1,
        "baseUrl": args.base_url,
        "url": route_url(args.base_url, args.token),
        "viewport": viewport,
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "checks": checks,
        "consoleMessages": console_messages,
        "unexpectedConsoleMessages": unexpected_console_messages,
        "requestFailures": request_failures,
        "apiRequestFailures": api_request_failures,
        "apiResponses": api_responses,
        "pageErrors": page_errors,
        "screenshot": str(screenshot),
    }


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(f"consumer verify unavailable browser smoke: {report['passed']}/{report['total']} PASS")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
