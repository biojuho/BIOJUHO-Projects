from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_ROUTES = [
    {"name": "dashboard", "path": "/", "expected": ["Consumer QR KPIs"]},
    {"name": "registry", "path": "/registry", "expected": ["Crop Registry"]},
    {"name": "supply_chain", "path": "/supply-chain", "expected": ["Supply Chain Overview"]},
    {"name": "qr_tokens", "path": "/qr-tokens", "expected": ["QR Token Management"]},
    {"name": "sensors", "path": "/sensor-devices", "expected": ["Sensor Device Registry"]},
    {"name": "cold_chain", "path": "/cold-chain", "expected": ["Cold-Chain Monitor"]},
    {"name": "scanner", "path": "/scan", "expected": ["Scan Product QR"]},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a browser smoke check across AgriGuard launch routes.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--json-out", default="var/agriguard-nav-browser-smoke.json")
    parser.add_argument("--screenshot-dir", default="var/agriguard-nav-browser-smoke-screens")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", ""),
        help="Optional operator token to store in localStorage before opening the app.",
    )
    return parser.parse_args()


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def route_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


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


def wait_for_expected_text(page: Page, expected: list[str], timeout_ms: int) -> None:
    page.wait_for_function(
        """values => values.some(value => (document.body.textContent || '').includes(value))""",
        arg=expected,
        timeout=timeout_ms,
    )


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {"routes": []}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    screenshot_dir = Path(args.screenshot_dir)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        if args.operator_token:
            page.add_init_script(
                "window.localStorage.setItem('agriguard-operator-token', "
                f"{json.dumps(args.operator_token)});",
            )

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
        page.on(
            "pageerror",
            lambda error: page_errors.append(
                {
                    "message": str(error),
                    "stack": getattr(error, "stack", None) or "",
                },
            ),
        )

        for route in DEFAULT_ROUTES:
            name = str(route["name"])
            expected = list(route["expected"])
            path = str(route["path"])
            screenshot = screenshot_dir / f"{name}.png"
            route_errors_before = len(page_errors)
            try:
                page.goto(route_url(args.base_url, path), wait_until="domcontentloaded", timeout=args.timeout_ms)
                wait_for_expected_text(page, expected, args.timeout_ms)
                page.wait_for_timeout(500)
                metrics = read_metrics(page)
                headings = page.locator("h1,h2,h3").all_inner_texts()
                visible_expected = page.evaluate(
                    """values => values.some(value => (document.body.textContent || '').includes(value))""",
                    expected,
                )
                no_horizontal_overflow = int(metrics["scrollWidth"]) <= int(metrics["clientWidth"]) + 1
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=False)
                route_report = {
                    "name": name,
                    "path": path,
                    "url": route_url(args.base_url, path),
                    "expected": expected,
                    "ok": visible_expected
                    and int(metrics["bodyTextLength"]) > 0
                    and no_horizontal_overflow
                    and len(page_errors) == route_errors_before,
                    "headings": headings,
                    "metrics": metrics,
                    "pageErrorsDuringRoute": page_errors[route_errors_before:],
                    "screenshot": str(screenshot),
                }
                checks.append(check(f"{name}_expected_text_visible", visible_expected, ", ".join(expected)))
                checks.append(check(f"{name}_body_not_blank", int(metrics["bodyTextLength"]) > 0, str(metrics)))
                checks.append(check(f"{name}_no_horizontal_overflow", no_horizontal_overflow, str(metrics)))
                checks.append(check(f"{name}_screenshot_written", screenshot.exists(), str(screenshot)))
                checks.append(
                    check(
                        f"{name}_no_page_errors",
                        len(page_errors) == route_errors_before,
                        str(len(page_errors) - route_errors_before),
                    )
                )
            except Exception as exc:
                route_report = {
                    "name": name,
                    "path": path,
                    "url": route_url(args.base_url, path),
                    "expected": expected,
                    "ok": False,
                    "error": str(exc),
                    "pageErrorsDuringRoute": page_errors[route_errors_before:],
                    "screenshot": str(screenshot),
                }
                checks.append(check(f"{name}_route_rendered", False, str(exc)))
                try:
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot), full_page=False)
                except Exception:
                    pass
            observations["routes"].append(route_report)

        browser.close()

    actionable_request_failures = [
        failure for failure in request_failures if "ERR_ABORTED" not in failure.get("failure", "")
    ]
    checks.append(check("all_routes_visited", len(observations["routes"]) == len(DEFAULT_ROUTES), str(len(observations["routes"]))))
    checks.append(check("all_routes_rendered", all(route.get("ok") for route in observations["routes"]), ""))
    checks.append(check("no_console_warnings_or_errors", len(console_messages) == 0, str(len(console_messages))))
    checks.append(
        check(
            "no_actionable_request_failures",
            len(actionable_request_failures) == 0,
            f"{len(actionable_request_failures)} actionable / {len(request_failures)} total",
        )
    )
    checks.append(check("no_page_errors", len(page_errors) == 0, str(len(page_errors))))

    passed = sum(1 for item in checks if item["ok"])
    return {
        "schema_version": 1,
        "baseUrl": args.base_url,
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "operator_token_configured": bool(args.operator_token),
        "checks": checks,
        "observations": observations,
        "consoleMessages": console_messages,
        "requestFailures": request_failures,
        "actionableRequestFailures": actionable_request_failures,
        "pageErrors": page_errors,
        "screenshotDir": str(screenshot_dir),
    }


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(f"agriguard nav browser smoke: {report['passed']}/{report['total']} PASS")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
