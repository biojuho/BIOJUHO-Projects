from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.sync_api import Page, Response, sync_playwright


DEFAULT_URL = "http://127.0.0.1:5174/supply-chain"
DEFAULT_DESKTOP_VIEWPORT = "1440x960"
DEFAULT_MOBILE_VIEWPORT = "390x844"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
RANGE_RE = re.compile(r"Showing\s+(\d+)-(\d+)\s+of\s+(\d+)\s+products")


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a browser smoke check for the AgriGuard supply-chain route.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Supply-chain URL to open. Defaults to {DEFAULT_URL}.")
    parser.add_argument("--json-out", default="var/agriguard-supply-chain-browser-smoke.json")
    parser.add_argument("--screenshot", default="var/agriguard-supply-chain-browser-smoke.png")
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
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
        help=(
            "Operator token to store in localStorage before opening the app. Defaults to "
            "AGRIGUARD_BROWSER_OPERATOR_TOKEN or the local dev-fallback smoke token."
        ),
    )
    parser.add_argument(
        "--allow-unpaginated-fallback",
        action="store_true",
        help="Allow legacy GET /products fallback when /products/page is unavailable.",
    )
    return parser.parse_args()


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


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def parse_range(text: str | None) -> dict[str, object] | None:
    match = RANGE_RE.search(text or "")
    if not match:
        return None
    return {
        "first": int(match.group(1)),
        "last": int(match.group(2)),
        "total": int(match.group(3)),
        "text": match.group(0),
    }


def read_range(page: Page, timeout_ms: int) -> dict[str, object] | None:
    locator = page.get_by_text(RANGE_RE).first
    locator.wait_for(timeout=timeout_ms)
    return parse_range(locator.text_content())


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
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 800),
            };
        }"""
    )


def product_response_snapshot(response: Response) -> dict[str, object]:
    payload: object | None = None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("items"), list):
                items = payload["items"]
                payload = {
                    "items_count": len(items),
                    "sample_item_ids": [
                        str(item.get("id", ""))
                        for item in items[:3]
                        if isinstance(item, dict) and item.get("id")
                    ],
                    "page": payload.get("page"),
                    "page_size": payload.get("page_size"),
                    "total": payload.get("total"),
                    "total_pages": payload.get("total_pages"),
                }
        except Exception as exc:  # pragma: no cover - defensive browser instrumentation
            payload = {"parse_error": str(exc)}
    return {
        "url": response.url,
        "method": response.request.method,
        "status": response.status,
        "payload": payload,
    }


def response_path(response: dict[str, object]) -> str:
    try:
        return urlparse(str(response["url"])).path.rstrip("/")
    except Exception:
        return ""


def api_response_path(response: dict[str, object]) -> str:
    path = response_path(response)
    if path.startswith("/api/"):
        return path.removeprefix("/api")
    return path


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    product_api_responses: list[dict[str, object]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        viewport = resolve_viewport(mobile=args.mobile, viewport=args.viewport)
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
                {"url": request.url, "failure": (request.failure or "unknown")}
            ),
        )
        page.on(
            "pageerror",
            lambda error: page_errors.append(
                {
                    "message": str(error),
                    "stack": getattr(error, "stack", None) or "",
                }
            ),
        )
        page.on(
            "response",
            lambda response: product_api_responses.append(product_response_snapshot(response))
            if "/products" in response.url
            else None,
        )

        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            page.get_by_role("heading", name="Supply Chain Overview").wait_for(timeout=args.timeout_ms)
            checks.append(check("page_loaded", True, args.url))

            initial_range = read_range(page, args.timeout_ms)
            initial_links = page.locator('a[href^="/product/"]').count()
            initial_unknown_statuses = page.get_by_text("Unknown Status", exact=True).count()
            initial_metrics = read_metrics(page)
            observations["initial"] = {
                "range": initial_range,
                "productLinks": initial_links,
                "unknownStatuses": initial_unknown_statuses,
                "metrics": initial_metrics,
            }
            checks.append(check("initial_range_visible", bool(initial_range), str(initial_range)))
            checks.append(
                check(
                    "initial_page_starts_at_first_product",
                    bool(initial_range and initial_range["first"] == 1),
                    str(initial_range),
                )
            )
            checks.append(
                check(
                    "initial_renders_at_most_twenty_product_cards",
                    0 < initial_links <= 20,
                    f"{initial_links} product links",
                )
            )
            checks.append(
                check("initial_page_height_bounded", int(initial_metrics["scrollHeight"]) < 16_000, str(initial_metrics))
            )
            checks.append(
                check(
                    "no_horizontal_overflow",
                    int(initial_metrics["scrollWidth"]) <= int(initial_metrics["clientWidth"]) + 1,
                    str(initial_metrics),
                )
            )
            checks.append(
                check(
                    "initial_statuses_are_normalized",
                    initial_links == 0 or initial_unknown_statuses == 0,
                    f"{initial_unknown_statuses} Unknown Status labels",
                )
            )

            first_href = page.locator('a[href^="/product/"]').first.get_attribute("href")
            search_term = unquote((first_href or "").removeprefix("/product/"))
            observations["searchTerm"] = search_term
            checks.append(check("first_product_link_captured", bool(search_term), search_term))
            if not search_term:
                raise RuntimeError("missing product link for search reset check")

            if initial_range and int(initial_range["total"]) > 20:
                page.get_by_role("button", name="Next").click(timeout=args.timeout_ms)
                page.wait_for_function(
                    "() => /Showing\\s+21-\\d+\\s+of\\s+\\d+\\s+products/.test(document.body.textContent || '')",
                    timeout=args.timeout_ms,
                )
                next_range = read_range(page, args.timeout_ms)
                next_links = page.locator('a[href^="/product/"]').count()
                observations["next"] = {"range": next_range, "productLinks": next_links}
                checks.append(check("next_page_advances_range", bool(next_range and next_range["first"] == 21), str(next_range)))
                checks.append(
                    check(
                        "next_page_renders_at_most_twenty_product_cards",
                        0 < next_links <= 20,
                        f"{next_links} product links",
                    )
                )
            else:
                checks.append(check("next_page_not_required", True, str(initial_range)))

            page.get_by_placeholder("Search products or locations...").fill(search_term, timeout=args.timeout_ms)
            page.wait_for_function(
                """term => {
                    const text = document.body.textContent || '';
                    return text.includes(term) && /Showing\\s+1-\\d+\\s+of\\s+\\d+\\s+products/.test(text);
                }""",
                arg=search_term,
                timeout=args.timeout_ms,
            )
            search_range = read_range(page, args.timeout_ms)
            search_links = page.locator('a[href^="/product/"]').count()
            search_unknown_statuses = page.get_by_text("Unknown Status", exact=True).count()
            search_metrics = read_metrics(page)
            observations["search"] = {
                "range": search_range,
                "productLinks": search_links,
                "unknownStatuses": search_unknown_statuses,
                "metrics": search_metrics,
            }
            checks.append(check("search_resets_to_first_page", bool(search_range and search_range["first"] == 1), str(search_range)))
            checks.append(check("search_filters_to_visible_product", bool(search_range and search_range["total"] >= 1), str(search_range)))
            checks.append(
                check(
                    "search_renders_at_most_twenty_product_cards",
                    0 < search_links <= 20,
                    f"{search_links} product links",
                )
            )
            checks.append(
                check(
                    "search_status_is_normalized",
                    search_links == 0 or search_unknown_statuses == 0,
                    f"{search_unknown_statuses} Unknown Status labels",
                )
            )

            clear_button = page.get_by_role("button", name="Clear supply chain search")
            clear_button.wait_for(timeout=args.timeout_ms)
            checks.append(check("search_clear_button_visible", clear_button.is_visible(), search_term))
            clear_button.click(timeout=args.timeout_ms)
            page.wait_for_function(
                """() => {
                    const input = document.querySelector('#supply-chain-search');
                    const text = document.body.textContent || '';
                    return input && input.value === '' && /Showing\\s+1-\\d+\\s+of\\s+\\d+\\s+products/.test(text);
                }""",
                timeout=args.timeout_ms,
            )
            clear_range = read_range(page, args.timeout_ms)
            clear_metrics = read_metrics(page)
            observations["clear"] = {
                "range": clear_range,
                "metrics": clear_metrics,
            }
            checks.append(check("search_clear_restores_empty_input", page.locator("#supply-chain-search").input_value() == ""))
            checks.append(check("search_clear_resets_to_first_page", bool(clear_range and clear_range["first"] == 1), str(clear_range)))
            checks.append(
                check(
                    "search_clear_restores_unfiltered_total",
                    bool(initial_range and clear_range and clear_range["total"] == initial_range["total"]),
                    f"initial={initial_range} clear={clear_range}",
                )
            )
            checks.append(
                check(
                    "search_clear_has_no_horizontal_overflow",
                    int(clear_metrics["scrollWidth"]) <= int(clear_metrics["clientWidth"]) + 1,
                    str(clear_metrics),
                )
            )

            ensure_parent(args.screenshot)
            page.screenshot(path=args.screenshot, full_page=False)
            checks.append(check("screenshot_written", True, args.screenshot))
        except Exception as exc:
            checks.append(check("browser_flow_completed", False, str(exc)))
            try:
                ensure_parent(args.screenshot)
                page.screenshot(path=args.screenshot, full_page=False)
            except Exception:
                pass
        finally:
            browser.close()

    actionable_request_failures = [
        failure for failure in request_failures if "ERR_ABORTED" not in failure.get("failure", "")
    ]
    product_page_responses = [
        response for response in product_api_responses if api_response_path(response) == "/products/page"
    ]
    successful_product_page_responses = [
        response for response in product_page_responses if 200 <= int(response["status"]) < 300
    ]
    unpaginated_responses = [
        response
        for response in product_api_responses
        if response.get("method") == "GET" and api_response_path(response) == "/products"
    ]
    page_payloads_bounded = all(
        isinstance(response.get("payload"), dict)
        and isinstance(response["payload"].get("items_count"), int)
        and response["payload"]["items_count"] <= 20
        and isinstance(response["payload"].get("page_size"), int)
        and response["payload"]["page_size"] <= 20
        and isinstance(response["payload"].get("total"), int)
        for response in successful_product_page_responses
    )
    non_fallback_console_messages = (
        [
            message
            for message in console_messages
            if not (
                message.get("type") == "error"
                and "Failed to load resource" in message.get("text", "")
                and "404" in message.get("text", "")
            )
        ]
        if args.allow_unpaginated_fallback
        else console_messages
    )

    checks.append(
        check(
            "products_page_endpoint_used",
            bool(successful_product_page_responses) or (args.allow_unpaginated_fallback and bool(unpaginated_responses)),
            f"{len(successful_product_page_responses)} successful page / {len(unpaginated_responses)} fallback",
        )
    )
    checks.append(
        check(
            "unpaginated_products_endpoint_not_used",
            not unpaginated_responses or args.allow_unpaginated_fallback,
            str(len(unpaginated_responses)),
        )
    )
    checks.append(
        check(
            "products_page_payloads_bounded",
            (bool(successful_product_page_responses) and page_payloads_bounded)
            or (args.allow_unpaginated_fallback and bool(unpaginated_responses)),
            f"{len(successful_product_page_responses)} successful page responses",
        )
    )
    checks.append(
        check("no_console_warnings_or_errors", len(non_fallback_console_messages) == 0, str(len(non_fallback_console_messages)))
    )
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
        "generated_at": _generated_timestamp_utc(),
        "url": args.url,
        "viewport": resolve_viewport(mobile=args.mobile, viewport=args.viewport),
        "mobile": bool(args.mobile),
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "allow_unpaginated_fallback": args.allow_unpaginated_fallback,
        "operator_token_configured": bool(args.operator_token),
        "checks": checks,
        "observations": observations,
        "productApiResponses": product_api_responses,
        "consoleMessages": console_messages,
        "nonFallbackConsoleMessages": non_fallback_console_messages,
        "requestFailures": request_failures,
        "actionableRequestFailures": actionable_request_failures,
        "pageErrors": page_errors,
        "screenshot": args.screenshot,
    }


def main() -> int:
    args = parse_args()
    report = run_browser(args)
    write_json(args.json_out, report)
    print(f"agriguard supply-chain browser smoke: {report['passed']}/{report['total']} PASS")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
