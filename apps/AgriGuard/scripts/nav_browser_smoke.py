from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_DESKTOP_VIEWPORT = "1440x960"
DEFAULT_MOBILE_VIEWPORT = "390x844"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
DEFAULT_ROUTES = [
    {"name": "dashboard", "label": "Dashboard", "path": "/", "expected": ["Consumer QR KPIs"]},
    {"name": "registry", "label": "Registry", "path": "/registry", "expected": ["Crop Registry"]},
    {"name": "supply_chain", "label": "Supply Chain", "path": "/supply-chain", "expected": ["Supply Chain Overview"]},
    {"name": "qr_tokens", "label": "QR Tokens", "path": "/qr-tokens", "expected": ["QR Token Management"]},
    {"name": "sensors", "label": "Sensors", "path": "/sensor-devices", "expected": ["Sensor Device Registry"]},
    {"name": "cold_chain", "label": "Cold-Chain", "path": "/cold-chain", "expected": ["Cold-Chain Monitor"]},
    {"name": "scanner", "label": "Scanner", "path": "/scan", "expected": ["Scan Product QR"]},
]
MOBILE_VIEWPORT_MAX_WIDTH = 500
MOBILE_ROUTE_AFFORDANCES = {
    "registry": [
        {
            "name": "register_harvest_cta_first_viewport",
            "text": "Register Harvest",
            "selector": "button",
            "min_visible_ratio": 0.98,
            "min_bottom_margin": 16,
        },
    ],
    "qr_tokens": [
        {
            "name": "product_qr_tokens_card_first_viewport",
            "text": "Product QR tokens",
            "closest_selector": ".rounded-lg.border",
            "min_visible_height": 220,
        },
    ],
    "cold_chain": [
        {
            "name": "temperature_timeline_card_first_viewport",
            "text": "Temperature Timeline",
            "closest_selector": ".rounded-lg.border",
            "min_visible_height": 220,
        },
    ],
    "scanner": [
        {
            "name": "verify_code_cta_first_viewport",
            "text": "Verify code",
            "selector": "button",
            "min_visible_ratio": 0.98,
            "min_bottom_margin": 16,
        },
    ],
}


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a browser smoke check across AgriGuard launch routes.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--json-out", default="var/agriguard-nav-browser-smoke.json")
    parser.add_argument("--screenshot-dir", default="var/agriguard-nav-browser-smoke-screens")
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
    parser.add_argument(
        "--click-nav",
        action="store_true",
        help="Navigate by clicking visible navigation links instead of opening each route URL directly.",
    )
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
        help=(
            "Operator token to store in localStorage before opening the app. Defaults to "
            "AGRIGUARD_BROWSER_OPERATOR_TOKEN or the local dev-fallback smoke token."
        ),
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


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def route_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


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
            const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
            const isVisible = element => {
              const style = window.getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return style.visibility !== 'hidden'
                && style.display !== 'none'
                && rect.width > 0
                && rect.height > 0;
            };
            const describeElement = element => ({
              tag: element.tagName.toLowerCase(),
              id: element.id || null,
              role: element.getAttribute('role'),
              type: element.getAttribute('type'),
              ariaLabel: element.getAttribute('aria-label'),
              placeholder: element.getAttribute('placeholder'),
              text: normalize(element.textContent).slice(0, 120),
            });
            const accessibleName = element => {
              const labelledBy = normalize(
                (element.getAttribute('aria-labelledby') || '')
                  .split(/\\s+/)
                  .map(id => document.getElementById(id)?.textContent || '')
                  .join(' ')
              );
              if (labelledBy) return labelledBy;
              const ariaLabel = normalize(element.getAttribute('aria-label'));
              if (ariaLabel) return ariaLabel;
              if (element.id) {
                const explicitLabel = Array.from(document.querySelectorAll('label'))
                  .find(label => label.htmlFor === element.id);
                const explicitLabelText = normalize(explicitLabel?.textContent);
                if (explicitLabelText) return explicitLabelText;
              }
              const wrappedLabelText = normalize(element.closest('label')?.textContent);
              if (wrappedLabelText) return wrappedLabelText;
              const title = normalize(element.getAttribute('title'));
              if (title) return title;
              if (element.tagName.toLowerCase() === 'img') {
                const alt = normalize(element.getAttribute('alt'));
                if (alt) return alt;
              }
              if (element.tagName.toLowerCase() === 'svg') {
                const svgTitle = normalize(element.querySelector('title')?.textContent);
                if (svgTitle) return svgTitle;
                const svgDesc = normalize(element.querySelector('desc')?.textContent);
                if (svgDesc) return svgDesc;
              }
              if (element.tagName.toLowerCase() === 'input') {
                const type = (element.getAttribute('type') || '').toLowerCase();
                if (['button', 'submit', 'reset'].includes(type)) {
                  return normalize(element.value);
                }
              }
              const imageAlt = normalize(Array.from(element.querySelectorAll('img'))
                .map(image => image.getAttribute('alt') || '')
                .join(' '));
              if (imageAlt) return imageAlt;
              return normalize(element.textContent);
            };
            const interactiveSelector = [
              'button',
              'a[href]',
              'input:not([type="hidden"])',
              'select',
              'textarea',
              '[role="button"]',
              '[role="link"]',
              '[role="checkbox"]',
              '[role="combobox"]',
              '[role="switch"]',
              '[role="textbox"]',
              'svg[tabindex]',
            ].join(',');
            const visibleInteractive = Array.from(document.querySelectorAll(interactiveSelector))
              .filter(isVisible);
            const fieldSelector = 'input:not([type="hidden"]),select,textarea,[role="combobox"],[role="textbox"]';
            const visibleFields = Array.from(document.querySelectorAll(fieldSelector)).filter(isVisible);
            const touchTargetSelector = [
              'button',
              'a[href]',
              'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])',
              'select',
              'textarea',
              '[role="button"]',
              '[role="link"]',
            ].join(',');
            const visibleTouchTargets = Array.from(document.querySelectorAll(touchTargetSelector))
              .filter(element => {
                if (!isVisible(element)) return false;
                const rect = element.getBoundingClientRect();
                return rect.bottom > 0 && rect.top < window.innerHeight;
              });
            const undersizedTouchTargets = visibleTouchTargets
              .map(element => {
                const rect = element.getBoundingClientRect();
                return {
                  ...describeElement(element),
                  width: Math.round(rect.width),
                  height: Math.round(rect.height),
                };
              })
              .filter(item => item.width < 44 || item.height < 44);
            const credentialFieldSelector = [
              'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])',
              'textarea',
            ].join(',');
            const isCredentialLikeField = element => {
              const labels = Array.from(element.labels || []).map(label => label.textContent || '').join(' ');
              const text = normalize([
                element.id,
                element.getAttribute('name'),
                element.getAttribute('placeholder'),
                element.getAttribute('aria-label'),
                labels,
              ].join(' ')).toLowerCase();
              return element.getAttribute('type') === 'password'
                || /token|secret|password|bearer|credential/.test(text);
            };
            const credentialAutocompleteGaps = Array.from(document.querySelectorAll(credentialFieldSelector))
              .filter(isVisible)
              .filter(isCredentialLikeField)
              .filter(element => !normalize(element.getAttribute('autocomplete')))
              .map(describeElement);
            const ids = Array.from(document.querySelectorAll('[id]'))
              .map(element => element.id)
              .filter(Boolean);
            const duplicateIds = Array.from(new Set(ids.filter((id, index) => ids.indexOf(id) !== index))).sort();
            return {
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              scrollWidth: Math.max(doc.scrollWidth, body.scrollWidth),
              clientWidth: doc.clientWidth,
              scrollHeight: Math.max(doc.scrollHeight, body.scrollHeight),
              bodyTextLength: (body.textContent || '').trim().length,
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 800),
              navWidth: Math.round(document.querySelector('nav')?.getBoundingClientRect().width || 0),
              hasMain: Boolean(document.querySelector('main')),
              hasNav: Boolean(document.querySelector('nav')),
              h1Count: document.querySelectorAll('h1').length,
              duplicateIds,
              unnamedInteractive: visibleInteractive
                .filter(element => !accessibleName(element))
                .map(describeElement),
              unlabeledFields: visibleFields
                .filter(element => !accessibleName(element))
                .map(describeElement),
              undersizedTouchTargets,
              credentialAutocompleteGaps,
              menuButton: document.querySelector('button[aria-label="Open menu"],button[aria-label="Close menu"]')
                ?.getAttribute('aria-label') || null,
            };
        }"""
    )


def wait_for_expected_text(page: Page, expected: list[str], timeout_ms: int) -> None:
    page.wait_for_function(
        """values => values.some(value => (document.body.textContent || '').includes(value))""",
        arg=expected,
        timeout=timeout_ms,
    )


def route_expected_is_visible(page: Page, expected: list[str]) -> bool:
    return bool(
        page.evaluate(
            """values => values.some(value => (document.body.textContent || '').includes(value))""",
            expected,
        )
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def _metric_int(metrics: dict[str, object], name: str) -> int:
    try:
        return int(metrics.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def route_semantics_detail(metrics: dict[str, object]) -> dict[str, object]:
    return {
        "hasMain": bool(metrics.get("hasMain")),
        "hasNav": bool(metrics.get("hasNav")),
        "h1Count": _metric_int(metrics, "h1Count"),
        "duplicateIds": metrics.get("duplicateIds") or [],
        "unnamedInteractive": metrics.get("unnamedInteractive") or [],
        "unlabeledFields": metrics.get("unlabeledFields") or [],
        "credentialAutocompleteGaps": metrics.get("credentialAutocompleteGaps") or [],
    }


def route_semantics_ok(metrics: dict[str, object]) -> bool:
    detail = route_semantics_detail(metrics)
    return (
        bool(detail["hasMain"])
        and bool(detail["hasNav"])
        and int(detail["h1Count"]) >= 1
        and not detail["duplicateIds"]
        and not detail["unnamedInteractive"]
        and not detail["unlabeledFields"]
        and not detail["credentialAutocompleteGaps"]
    )


def should_check_mobile_affordances(metrics: dict[str, object], *, mobile: bool) -> bool:
    return bool(mobile) or _metric_int(metrics, "viewportWidth") > 0


def mobile_touch_targets_detail(metrics: dict[str, object]) -> dict[str, object]:
    return {
        "viewportWidth": _metric_int(metrics, "viewportWidth"),
        "undersizedTouchTargets": metrics.get("undersizedTouchTargets") or [],
    }


def mobile_touch_targets_ok(metrics: dict[str, object]) -> bool:
    return not mobile_touch_targets_detail(metrics)["undersizedTouchTargets"]


def measure_mobile_affordance(page: Page, spec: dict[str, object]) -> dict[str, object]:
    measurement = page.evaluate(
        """spec => {
            const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
            const targetText = normalize(spec.text).toLowerCase();
            const selector = spec.selector || 'button,a,h1,h2,h3,label,p,span,div';
            const candidates = Array.from(document.querySelectorAll(selector))
              .filter(element => normalize(element.textContent).toLowerCase().includes(targetText));
            const textMatch = candidates.find(
              element => normalize(element.textContent).toLowerCase() === targetText
            ) || candidates[0] || null;

            if (!textMatch) {
              return {
                name: spec.name,
                text: spec.text,
                selector,
                found: false,
                ok: false,
                detail: 'matching element not found',
                viewportHeight: window.innerHeight,
                viewportWidth: window.innerWidth,
              };
            }

            const measuredElement = spec.closest_selector
              ? (textMatch.closest(spec.closest_selector) || textMatch)
              : textMatch;
            const rect = measuredElement.getBoundingClientRect();
            const visibleWidth = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0));
            const visibleHeight = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
            const totalArea = Math.max(0, rect.width) * Math.max(0, rect.height);
            const visibleArea = visibleWidth * visibleHeight;
            const visibleRatio = totalArea > 0 ? visibleArea / totalArea : 0;
            const minVisibleHeight = Number(spec.min_visible_height || 1);
            const minVisibleRatio = Number(spec.min_visible_ratio || 0.01);
            const hasBottomMarginRequirement = spec.min_bottom_margin !== undefined
              && spec.min_bottom_margin !== null;
            const minBottomMargin = hasBottomMarginRequirement ? Number(spec.min_bottom_margin) : 0;
            const bottomMargin = Math.round(window.innerHeight - rect.bottom);
            const ok = visibleHeight >= minVisibleHeight
              && visibleRatio >= minVisibleRatio
              && (!hasBottomMarginRequirement || bottomMargin >= minBottomMargin);

            return {
              name: spec.name,
              text: spec.text,
              selector,
              closestSelector: spec.closest_selector || null,
              found: true,
              ok,
              rect: {
                top: Math.round(rect.top),
                bottom: Math.round(rect.bottom),
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
              },
              visibleWidth: Math.round(visibleWidth),
              visibleHeight: Math.round(visibleHeight),
              visibleRatio: Math.round(visibleRatio * 1000) / 1000,
              bottomMargin,
              minVisibleHeight,
              minVisibleRatio,
              minBottomMargin,
              viewportHeight: window.innerHeight,
              viewportWidth: window.innerWidth,
            };
        }""",
        spec,
    )
    return dict(measurement)


def open_route(page: Page, args: argparse.Namespace, route: dict[str, object]) -> None:
    path = str(route["path"])
    if not args.click_nav:
        page.goto(route_url(args.base_url, path), wait_until="domcontentloaded", timeout=args.timeout_ms)
        return

    if page.url == "about:blank":
        page.goto(route_url(args.base_url, "/"), wait_until="domcontentloaded", timeout=args.timeout_ms)

    if args.mobile:
        page.get_by_role("button", name="Open menu").click(timeout=args.timeout_ms)
        page.get_by_role("button", name="Close menu").wait_for(timeout=args.timeout_ms)

    page.get_by_role("link", name=str(route["label"]), exact=True).click(timeout=args.timeout_ms)
    page.wait_for_url(route_url(args.base_url, path), timeout=args.timeout_ms)


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {"routes": []}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    screenshot_dir = Path(args.screenshot_dir)
    viewport = resolve_viewport(mobile=args.mobile, viewport=args.viewport)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport, is_mobile=args.mobile, has_touch=args.mobile)
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
            label = str(route["label"])
            expected = list(route["expected"])
            path = str(route["path"])
            screenshot = screenshot_dir / f"{name}.png"
            route_errors_before = len(page_errors)
            try:
                open_route(page, args, route)
                wait_for_expected_text(page, expected, args.timeout_ms)
                page.wait_for_timeout(500)
                metrics = read_metrics(page)
                headings = page.locator("h1,h2,h3").all_inner_texts()
                visible_expected = route_expected_is_visible(page, expected)
                no_horizontal_overflow = has_no_horizontal_overflow(metrics)
                semantic_accessibility = route_semantics_ok(metrics)
                menu_closed_after_click = not args.click_nav or not args.mobile or metrics["menuButton"] == "Open menu"
                mobile_affordances = []
                check_mobile_targets = should_check_mobile_affordances(metrics, mobile=args.mobile)
                if should_check_mobile_affordances(metrics, mobile=args.mobile):
                    mobile_affordances = [
                        measure_mobile_affordance(page, spec)
                        for spec in MOBILE_ROUTE_AFFORDANCES.get(name, [])
                    ]
                mobile_affordances_ok = all(item["ok"] for item in mobile_affordances)
                mobile_touch_targets_pass = not check_mobile_targets or mobile_touch_targets_ok(metrics)
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=False)
                route_report = {
                    "name": name,
                    "label": label,
                    "path": path,
                    "url": route_url(args.base_url, path),
                    "expected": expected,
                    "ok": visible_expected
                    and int(metrics["bodyTextLength"]) > 0
                    and no_horizontal_overflow
                    and semantic_accessibility
                    and menu_closed_after_click
                    and mobile_affordances_ok
                    and mobile_touch_targets_pass
                    and len(page_errors) == route_errors_before,
                    "headings": headings,
                    "metrics": metrics,
                    "semanticAccessibility": route_semantics_detail(metrics),
                    "mobileAffordances": mobile_affordances,
                    "mobileTouchTargets": mobile_touch_targets_detail(metrics),
                    "menuClosedAfterClick": menu_closed_after_click,
                    "pageErrorsDuringRoute": page_errors[route_errors_before:],
                    "screenshot": str(screenshot),
                }
                checks.append(check(f"{name}_expected_text_visible", visible_expected, ", ".join(expected)))
                checks.append(check(f"{name}_body_not_blank", int(metrics["bodyTextLength"]) > 0, str(metrics)))
                checks.append(check(f"{name}_no_horizontal_overflow", no_horizontal_overflow, str(metrics)))
                checks.append(
                    check(
                        f"{name}_semantic_accessibility",
                        semantic_accessibility,
                        json.dumps(route_semantics_detail(metrics), sort_keys=True),
                    )
                )
                checks.append(check(f"{name}_nav_state_valid", menu_closed_after_click, str(metrics)))
                if check_mobile_targets:
                    checks.append(
                        check(
                            f"{name}_mobile_touch_targets",
                            mobile_touch_targets_pass,
                            json.dumps(mobile_touch_targets_detail(metrics), sort_keys=True),
                        )
                    )
                checks.append(check(f"{name}_screenshot_written", screenshot.exists(), str(screenshot)))
                checks.append(
                    check(
                        f"{name}_no_page_errors",
                        len(page_errors) == route_errors_before,
                        str(len(page_errors) - route_errors_before),
                    )
                )
                for item in mobile_affordances:
                    checks.append(
                        check(
                            f"{name}_{item['name']}",
                            bool(item["ok"]),
                            json.dumps(item, sort_keys=True),
                        )
                    )
            except Exception as exc:
                route_report = {
                    "name": name,
                    "label": label,
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

    summary = summarize_checks(checks)
    ok = summary["failed"] == 0
    return {
        "schema_version": 1,
        "generated_at": _generated_timestamp_utc(),
        "status": "pass" if ok else "fail",
        "baseUrl": args.base_url,
        "base_url": args.base_url,
        "mode": "click-nav" if args.click_nav else "direct-route",
        "viewport": viewport,
        "mobile": bool(args.mobile),
        "passed": summary["passed"],
        "failed": summary["failed"],
        "total": summary["total"],
        "ok": ok,
        "summary": {
            **summary,
            "mode": "click-nav" if args.click_nav else "direct-route",
            "base_url": args.base_url,
            "screenshot_dir": str(screenshot_dir),
        },
        "operator_token_configured": bool(args.operator_token),
        "checks": checks,
        "observations": observations,
        "consoleMessages": console_messages,
        "requestFailures": request_failures,
        "actionableRequestFailures": actionable_request_failures,
        "pageErrors": page_errors,
        "screenshotDir": str(screenshot_dir),
        "screenshot_dir": str(screenshot_dir),
    }


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(f"agriguard nav browser smoke {report['status']}: {report['passed']}/{report['total']} checks passed")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
