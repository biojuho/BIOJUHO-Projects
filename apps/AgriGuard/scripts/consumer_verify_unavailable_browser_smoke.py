from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_VIEWPORT = "390x844"
DEFAULT_TOKEN = "unavailable-smoke-token"
PUBLIC_QR_TOKEN_REDACTION = "<redacted-public-qr-token>"
PUBLIC_VERIFY_ROUTE_RE = re.compile(
    r"((?:/verify|/api/(?:api/)?qr)/)[^/?#\s]+((?:/verify)?(?:[?#]\S*)?)"
)


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    parser.add_argument(
        "--intercept-api-failure",
        action="store_true",
        help="Fulfill the public verify API request with a synthetic 503 so the normal backend can stay online.",
    )
    return parser.parse_args()


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def summarize_checks(checks: list[dict[str, object]]) -> dict[str, object]:
    passed = sum(1 for item in checks if item.get("ok") is True)
    failed_check_names = [
        str(item.get("name") or f"check_{index}")
        for index, item in enumerate(checks, start=1)
        if item.get("ok") is not True
    ]
    return {
        "passed": passed,
        "failed": len(checks) - passed,
        "total": len(checks),
        "failed_check_names": failed_check_names,
    }


def mobile_viewport(viewport: dict[str, object]) -> bool:
    width = viewport.get("width")
    return isinstance(width, int) and width <= 500


def enrich_launch_evidence_contract(report: dict[str, object]) -> dict[str, object]:
    raw_checks = report.get("checks", [])
    checks = [item for item in raw_checks if isinstance(item, dict)] if isinstance(raw_checks, list) else []
    summary = summarize_checks(checks)
    status = "pass" if summary["failed"] == 0 else "fail"
    viewport = report.get("viewport")
    viewport_dict = viewport if isinstance(viewport, dict) else {}
    report.update(
        {
            "status": status,
            "base_url": report.get("baseUrl", ""),
            "mobile": mobile_viewport(viewport_dict),
            "passed": summary["passed"],
            "failed": summary["failed"],
            "total": summary["total"],
            "ok": status == "pass",
            "summary": {
                **summary,
                "base_url": report.get("baseUrl", ""),
                "url": report.get("url", ""),
                "screenshot": report.get("screenshot", ""),
            },
            "screenshot_path": report.get("screenshot", ""),
        }
    )
    return report


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redact_public_qr_route_tokens(text: str) -> str:
    return PUBLIC_VERIFY_ROUTE_RE.sub(
        lambda match: f"{match.group(1)}{PUBLIC_QR_TOKEN_REDACTION}{match.group(2)}",
        text,
    )


def redact_report_public_tokens(value: object, tokens: set[str]) -> object:
    if isinstance(value, dict):
        return {key: redact_report_public_tokens(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_report_public_tokens(item, tokens) for item in value]
    if isinstance(value, str):
        redacted = value
        for token in tokens:
            if token:
                redacted = redacted.replace(token, PUBLIC_QR_TOKEN_REDACTION)
        return redact_public_qr_route_tokens(redacted)
    return value


def route_url(base_url: str, token: str) -> str:
    return (
        f"{base_url.rstrip('/')}/verify/{token}"
        "?scan_source=unavailable_smoke&scan_session=unavailable-smoke&scan_variant=qr_unavailable_smoke"
    )


def verify_api_route_patterns(token: str) -> tuple[str, str]:
    encoded_token = quote(token, safe="")
    return (
        f"**/api/api/qr/{encoded_token}/verify**",
        f"**/api/qr/{encoded_token}/verify**",
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
    if message.get("type") == "warning" and text == "Service Worker registration blocked by Playwright":
        return True
    if message.get("type") != "error":
        return False
    if "Failed to load resource" in text and any(value in text for value in ["500", "502", "503", "504"]):
        return True
    return text.startswith("Failed to verify QR token") and any(
        value in text for value in ["500", "502", "503", "504", "Network Error", "ERR_FAILED"]
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
    intercepted_api_failures: list[dict[str, object]] = []
    page_errors: list[dict[str, str]] = []
    viewport = parse_viewport(args.viewport)
    screenshot = Path(args.screenshot)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=viewport,
            is_mobile=True,
            has_touch=True,
            service_workers="block",
        )
        page = context.new_page()
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

        if args.intercept_api_failure:
            def fulfill_unavailable(route) -> None:  # type: ignore[no-untyped-def]
                intercepted_api_failures.append({"url": route.request.url, "status": 503})
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body=json.dumps({"detail": "Simulated verification service unavailable"}),
                )

            for route_pattern in verify_api_route_patterns(args.token):
                page.route(route_pattern, fulfill_unavailable)

        page.goto(route_url(args.base_url, args.token), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_role("heading", name="Verification unavailable").wait_for(timeout=args.timeout_ms)
        initial_text = page_text(page)
        initial_metrics = read_metrics(page)
        checks.append(check("unavailable_state_visible", "Verification unavailable" in initial_text))
        checks.append(check("consumer_recovery_copy_visible", "Try again in a moment or scan again" in initial_text))
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
        if args.intercept_api_failure:
            checks.append(
                check(
                    "intercepted_api_failure_observed",
                    len(intercepted_api_failures) >= 2,
                    f"count={len(intercepted_api_failures)}",
                )
            )

        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=False)
        checks.append(check("screenshot_written", screenshot.exists(), str(screenshot)))
        context.close()
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

    report = {
        "schema_version": 1,
        "generated_at": _generated_timestamp_utc(),
        "baseUrl": args.base_url,
        "url": route_url(args.base_url, args.token),
        "viewport": viewport,
        "checks": checks,
        "consoleMessages": console_messages,
        "unexpectedConsoleMessages": unexpected_console_messages,
        "requestFailures": request_failures,
        "apiRequestFailures": api_request_failures,
        "apiResponses": api_responses,
        "interceptApiFailure": args.intercept_api_failure,
        "interceptedApiFailures": intercepted_api_failures,
        "serviceWorkers": "block",
        "pageErrors": page_errors,
        "screenshot": str(screenshot),
    }
    return dict(redact_report_public_tokens(enrich_launch_evidence_contract(report), {args.token}))


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(
        f"consumer verify unavailable browser smoke {report['status']}: "
        f"{report['passed']}/{report['total']} checks passed"
    )
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
