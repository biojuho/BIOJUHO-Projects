from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_DESKTOP_VIEWPORT = "1440x960"
DEFAULT_MOBILE_VIEWPORT = "390x844"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
DASHBOARD_AUTH_COPY = "Paste a Firebase/operator token below, or save one in QR Tokens or Sensors."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a browser smoke check for dashboard auth recovery.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
        help=(
            "Operator token to save through the dashboard recovery form. Defaults to "
            "AGRIGUARD_BROWSER_OPERATOR_TOKEN or the local dev-fallback smoke token."
        ),
    )
    parser.add_argument("--json-out", default="var/agriguard-dashboard-auth-browser-smoke.json")
    parser.add_argument("--screenshot", default="var/agriguard-dashboard-auth-browser-smoke.png")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument(
        "--viewport",
        default=None,
        help=(
            "Viewport size as WIDTHxHEIGHT. Defaults to "
            f"{DEFAULT_DESKTOP_VIEWPORT}, or {DEFAULT_MOBILE_VIEWPORT} with --mobile."
        ),
    )
    parser.add_argument("--mobile", action="store_true", help="Use mobile browser emulation with touch enabled.")
    return parser.parse_args()


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def route_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


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


def resolve_viewport(*, mobile: bool, viewport: str | None) -> dict[str, int]:
    if viewport:
        return parse_viewport(viewport)
    return parse_viewport(DEFAULT_MOBILE_VIEWPORT if mobile else DEFAULT_DESKTOP_VIEWPORT)


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
              bodyTextLength: (body.textContent || '').trim().length,
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 800),
            };
        }"""
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def body_text(page: Page) -> str:
    return page.locator("body").inner_text(timeout=5_000)


def is_expected_auth_console(message: dict[str, str]) -> bool:
    text = message.get("text", "")
    return message.get("type") == "error" and "Failed to load resource" in text and "401" in text


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    dashboard_responses: list[dict[str, object]] = []
    viewport = resolve_viewport(mobile=args.mobile, viewport=args.viewport)
    screenshot = Path(args.screenshot)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport, is_mobile=args.mobile, has_touch=args.mobile)
        page.add_init_script("window.localStorage.removeItem('agriguard-operator-token');")
        page.on(
            "console",
            lambda message: console_messages.append({"type": message.type, "text": message.text})
            if message.type in {"error", "warning"}
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: request_failures.append(
                {"url": request.url, "failure": (request.failure or "unknown")},
            ),
        )
        page.on("pageerror", lambda error: page_errors.append({"message": str(error)}))
        page.on(
            "response",
            lambda response: dashboard_responses.append({"url": response.url, "status": response.status})
            if "/dashboard/summary" in response.url
            else None,
        )

        page.goto(route_url(args.base_url), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_role("heading", name="Operator authentication required").wait_for(timeout=args.timeout_ms)
        auth_text = body_text(page)
        auth_metrics = read_metrics(page)
        token_input = page.get_by_label("Operator bearer token")
        retry_button = page.get_by_role("button", name="Save and retry")
        checks.append(check("auth_error_visible", "Operator authentication required" in auth_text))
        checks.append(check("auth_recovery_copy_visible", DASHBOARD_AUTH_COPY in auth_text))
        checks.append(check("token_input_visible", token_input.is_visible()))
        checks.append(check("retry_button_visible", retry_button.is_visible()))
        checks.append(check("auth_body_not_blank", int(auth_metrics["bodyTextLength"]) > 0, str(auth_metrics)))
        checks.append(check("auth_no_horizontal_overflow", has_no_horizontal_overflow(auth_metrics), str(auth_metrics)))

        token_input.fill(args.operator_token, timeout=args.timeout_ms)
        retry_button.click(timeout=args.timeout_ms)
        page.get_by_text("Consumer QR KPIs").wait_for(timeout=args.timeout_ms)
        page.wait_for_timeout(500)
        dashboard_text = body_text(page)
        dashboard_metrics = read_metrics(page)
        saved_token = page.evaluate("() => window.localStorage.getItem('agriguard-operator-token')")
        checks.append(check("operator_token_saved", saved_token == args.operator_token))
        checks.append(check("dashboard_loaded_after_retry", "Consumer QR KPIs" in dashboard_text))
        checks.append(
            check(
                "dashboard_summary_success_after_retry",
                any(int(response["status"]) == 200 for response in dashboard_responses),
                str(dashboard_responses),
            )
        )
        checks.append(check("dashboard_no_horizontal_overflow", has_no_horizontal_overflow(dashboard_metrics), str(dashboard_metrics)))
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=False)
        checks.append(check("screenshot_written", screenshot.exists(), str(screenshot)))
        browser.close()

    unexpected_console_messages = [
        message for message in console_messages if not is_expected_auth_console(message)
    ]
    checks.append(check("no_request_failures", len(request_failures) == 0, str(request_failures[:3])))
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
        "url": route_url(args.base_url),
        "viewport": viewport,
        "mobile": bool(args.mobile),
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "operator_token_configured": bool(args.operator_token),
        "checks": checks,
        "dashboardResponses": dashboard_responses,
        "consoleMessages": console_messages,
        "unexpectedConsoleMessages": unexpected_console_messages,
        "requestFailures": request_failures,
        "pageErrors": page_errors,
        "screenshot": str(screenshot),
    }


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(f"dashboard auth browser smoke: {report['passed']}/{report['total']} PASS")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
