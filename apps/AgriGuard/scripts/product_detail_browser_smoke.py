from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, parse, request

from playwright.sync_api import Page, sync_playwright


DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_API_URL = "http://127.0.0.1:8002"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
DEFAULT_DESKTOP_VIEWPORT = "1440x960"
DEFAULT_MOBILE_VIEWPORT = "390x844"
MOBILE_VIEWPORT_MAX_WIDTH = 500
PUBLIC_QR_TOKEN_REDACTION = "<redacted-public-qr-token>"
PUBLIC_VERIFY_ROUTE_RE = re.compile(
    r"((?:agri://verify|/verify|/api/(?:api/)?qr)/)([^/?#\s]+)((?:/verify)?(?:[?#]\S*)?)"
)
PUBLIC_QR_SCREENSHOT_MASK_SCRIPT = r"""() => {
    const marker = '<redacted-public-qr-token>';
    const routePattern = /((?:agri:\/\/verify|\/verify|\/api\/(?:api\/)?qr)\/)[^/?#\s]+((?:\/verify)?(?:[?#]\S*)?)/g;
    const walker = document.createTreeWalker(document.body, window.NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
    }
    for (const node of textNodes) {
      node.nodeValue = (node.nodeValue || '').replace(routePattern, `$1${marker}$2`);
    }
    document.querySelectorAll('[aria-label="Product verification QR"]').forEach(element => {
      element.style.filter = 'blur(14px)';
      element.style.opacity = '0.35';
    });
}"""
MOBILE_FIRST_VIEWPORT_TARGETS = [
    {
        "name": "product_qr_first_viewport",
        "aria_label": "Product verification QR",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "public_verify_label_copy_action_first_viewport",
        "aria_label": "Copy public verify label URL",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "product_id_copy_action_first_viewport",
        "aria_label": "Copy product ID",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "operator_tracking_action_first_viewport",
        "text": "Add Tracking Event",
        "selector": "button",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "operator_certification_action_first_viewport",
        "text": "Add Certification",
        "selector": "button",
        "min_visible_ratio": 0.98,
    },
]


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exercise an AgriGuard product detail route in a browser.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend API base URL. Defaults to {DEFAULT_API_URL}.")
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
    )
    parser.add_argument("--json-out", default="var/agriguard-product-detail-browser-smoke.json")
    parser.add_argument("--screenshot-dir", default="var/agriguard-product-detail-browser-smoke-screens")
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


def actionable_request_failures(request_failures: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        failure
        for failure in request_failures
        if "ERR_ABORTED" not in failure.get("failure", "")
    ]


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redact_public_qr_route_tokens(text: str) -> str:
    return PUBLIC_VERIFY_ROUTE_RE.sub(
        lambda match: f"{match.group(1)}{PUBLIC_QR_TOKEN_REDACTION}{match.group(3)}",
        text,
    )


def extract_public_qr_route_tokens(value: object) -> set[str]:
    if isinstance(value, dict):
        tokens: set[str] = set()
        for item in value.values():
            tokens.update(extract_public_qr_route_tokens(item))
        return tokens
    if isinstance(value, list):
        tokens = set()
        for item in value:
            tokens.update(extract_public_qr_route_tokens(item))
        return tokens
    if isinstance(value, str):
        return {match.group(2) for match in PUBLIC_VERIFY_ROUTE_RE.finditer(value) if match.group(2)}
    return set()


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


def mask_public_qr_artifacts_for_screenshot(page: Page) -> None:
    page.evaluate(PUBLIC_QR_SCREENSHOT_MASK_SCRIPT)


def capture_screenshot(page: Page, path: Path) -> None:
    mask_public_qr_artifacts_for_screenshot(page)
    page.screenshot(path=str(path), full_page=False)


def route_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def api_request(
    *,
    api_url: str,
    method: str,
    path: str,
    token: str,
    payload: dict[str, object] | None = None,
    timeout: int = 20,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        api_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


def seed_product(api_url: str, token: str) -> dict[str, object]:
    owner_id = "dev-user-id"
    product_name = f"Detail Smoke Batch {uuid.uuid4().hex[:8]}"
    payload = {
        "name": product_name,
        "description": "Browser smoke product for detail route launch coverage.",
        "category": "Vegetables",
        "origin": "Detail Smoke Farm",
        "requires_cold_chain": True,
    }
    path = f"/products/?owner_id={parse.quote(owner_id)}"
    return api_request(api_url=api_url, method="POST", path=path, token=token, payload=payload)


def body_text(page: Page) -> str:
    return page.locator("body").inner_text(timeout=5_000)


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
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1000),
            };
        }"""
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def should_check_mobile_affordances(metrics: dict[str, object], *, mobile: bool) -> bool:
    return bool(mobile) or int(metrics["viewportWidth"]) <= MOBILE_VIEWPORT_MAX_WIDTH


def measure_first_viewport_target(page: Page, spec: dict[str, object]) -> dict[str, object]:
    measurement = page.evaluate(
        """spec => {
            const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
            let target = null;
            if (spec.aria_label) {
              target = Array.from(document.querySelectorAll('[aria-label]'))
                .find(element => element.getAttribute('aria-label') === spec.aria_label) || null;
            } else {
              const targetText = normalize(spec.text).toLowerCase();
              const selector = spec.selector || 'button,a,h1,h2,h3,label,p,span,div';
              const candidates = Array.from(document.querySelectorAll(selector))
                .filter(element => normalize(element.textContent).toLowerCase().includes(targetText));
              target = candidates.find(
                element => normalize(element.textContent).toLowerCase() === targetText
              ) || candidates[0] || null;
            }

            if (!target) {
              return {
                name: spec.name,
                text: spec.text || null,
                ariaLabel: spec.aria_label || null,
                found: false,
                ok: false,
                detail: 'matching element not found',
                viewportHeight: window.innerHeight,
                viewportWidth: window.innerWidth,
              };
            }

            const rect = target.getBoundingClientRect();
            const visibleWidth = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0));
            const visibleHeight = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
            const totalArea = Math.max(0, rect.width) * Math.max(0, rect.height);
            const visibleArea = visibleWidth * visibleHeight;
            const visibleRatio = totalArea > 0 ? visibleArea / totalArea : 0;
            const minVisibleHeight = Number(spec.min_visible_height || 1);
            const minVisibleRatio = Number(spec.min_visible_ratio || 0.01);
            const ok = visibleHeight >= minVisibleHeight && visibleRatio >= minVisibleRatio;

            return {
              name: spec.name,
              text: spec.text || null,
              ariaLabel: spec.aria_label || null,
              selector: spec.selector || null,
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
              minVisibleHeight,
              minVisibleRatio,
              viewportHeight: window.innerHeight,
              viewportWidth: window.innerWidth,
            };
        }""",
        spec,
    )
    return dict(measurement)


def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    external_qr_requests: list[str] = []
    page_errors: list[dict[str, str]] = []
    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    viewport = resolve_viewport(mobile=args.mobile, viewport=args.viewport)

    product = seed_product(args.api_url, args.operator_token)
    product_id = str(product.get("id") or "")
    product_name = str(product.get("name") or "")
    checks.append(check("seed_product", bool(product_id and product_name), product_id))
    observations["seed_product"] = {
        "id": product_id,
        "name": product_name,
        "qr_code_prefix": str(product.get("qr_code") or "")[:24],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport, is_mobile=args.mobile, has_touch=args.mobile)
        page.context.grant_permissions(["clipboard-write"], origin=args.base_url.rstrip("/"))
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
            lambda req: request_failures.append({"url": req.url, "failure": req.failure or "unknown"}),
        )
        page.on(
            "request",
            lambda req: external_qr_requests.append(req.url)
            if "api.qrserver.com" in req.url
            else None,
        )
        page.on("pageerror", lambda exc: page_errors.append({"message": str(exc)}))

        page.goto(route_url(args.base_url, f"/product/{product_id}"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_role("heading", name=product_name).wait_for(timeout=args.timeout_ms)
        page.get_by_role("img", name="Product verification QR").wait_for(timeout=args.timeout_ms)
        initial_text = body_text(page)
        initial_metrics = read_metrics(page)
        initial_mobile_affordances = []
        if should_check_mobile_affordances(initial_metrics, mobile=args.mobile):
            initial_mobile_affordances = [
                measure_first_viewport_target(page, spec)
                for spec in MOBILE_FIRST_VIEWPORT_TARGETS
            ]
        observations["initial"] = {
            "url": page.url,
            "metrics": initial_metrics,
            "mobileAffordances": initial_mobile_affordances,
            "screenshot": str(screenshot_dir / "product-detail-initial.png"),
        }
        checks.append(check("product_detail_loaded", product_name in initial_text, product_name))
        checks.append(check("product_id_visible", product_id in initial_text, product_id))
        checks.append(check("origin_visible", "Detail Smoke Farm" in initial_text))
        checks.append(check("cold_chain_visible", "Required (Strict)" in initial_text))
        checks.append(check("local_qr_code_visible", page.get_by_role("img", name="Product verification QR").is_visible()))
        checks.append(check("initial_no_horizontal_overflow", has_no_horizontal_overflow(initial_metrics), str(initial_metrics)))
        for item in initial_mobile_affordances:
            checks.append(check(str(item["name"]), bool(item["ok"]), json.dumps(item, sort_keys=True)))
        qr_copy_button = page.get_by_role("button", name="Copy public verify label URL")
        checks.append(check("public_verify_label_copy_action_visible", qr_copy_button.is_visible()))
        checks.append(check("public_verify_label_copy_action_enabled", qr_copy_button.is_enabled()))
        qr_copy_button.click(timeout=args.timeout_ms)
        page.get_by_role("button", name="Copied public verify label URL").wait_for(timeout=args.timeout_ms)
        checks.append(check("public_verify_label_copy_action_copied_state", True))
        capture_screenshot(page, screenshot_dir / "product-detail-initial.png")

        add_tracking = page.get_by_role("button", name=re.compile("add tracking event", re.I))
        add_certification = page.get_by_role("button", name=re.compile("add certification", re.I))
        checks.append(check("operator_tracking_button_enabled", add_tracking.is_enabled()))
        checks.append(check("operator_certification_button_enabled", add_certification.is_enabled()))

        add_tracking.click(timeout=args.timeout_ms)
        page.get_by_text("New Tracking Event").wait_for(timeout=args.timeout_ms)
        page.get_by_placeholder(re.compile("Location")).fill("Detail Smoke Distribution Center")
        page.get_by_placeholder(re.compile("Handler ID")).fill("HANDLER-DETAIL-SMOKE")
        page.get_by_role("button", name=re.compile("^Add Event$", re.I)).click(timeout=args.timeout_ms)
        try:
            page.wait_for_function(
                """() => {
                    const text = document.body.textContent || '';
                    return text.includes('Tracking event saved')
                      || text.includes('Tracking event could not be saved.')
                      || text.includes('Operator authentication required to save chain updates.');
                }""",
                timeout=args.timeout_ms,
            )
        except Exception:
            pass
        tracking_text = body_text(page)
        observations["trackingSubmit"] = {
            "bodyTextSample": tracking_text.replace("\n", " ")[:1000],
        }
        tracking_saved = "Tracking event saved" in tracking_text
        if tracking_saved:
            page.wait_for_function(
                "() => (document.body.textContent || '').includes('In Transit')",
                timeout=args.timeout_ms,
            )
        tracking_history_visible = tracking_saved and bool(page.evaluate("() => (document.body.textContent || '').includes('In Transit')"))
        raw_tracking_status_hidden = not bool(
            page.evaluate("() => (document.body.textContent || '').includes('IN_TRANSIT')")
        )
        checks.append(check("tracking_event_saved", tracking_saved, tracking_text[:500]))
        checks.append(check("tracking_event_visible_in_history", tracking_history_visible))
        checks.append(check("tracking_event_raw_status_hidden", raw_tracking_status_hidden))

        add_certification.click(timeout=args.timeout_ms)
        page.get_by_text("New Certification").wait_for(timeout=args.timeout_ms)
        page.get_by_placeholder(re.compile("Certification Type")).fill("GAP")
        page.get_by_placeholder(re.compile("Issued By")).fill("Detail Smoke Authority")
        page.get_by_role("button", name=re.compile("^Add Certificate$", re.I)).click(timeout=args.timeout_ms)
        try:
            page.wait_for_function(
                """() => {
                    const text = document.body.textContent || '';
                    return text.includes('Certificate saved')
                      || text.includes('Certificate could not be saved.')
                      || text.includes('Operator authentication required to save chain updates.');
                }""",
                timeout=args.timeout_ms,
            )
        except Exception:
            pass
        final_text = body_text(page)
        final_metrics = read_metrics(page)
        observations["final"] = {
            "url": page.url,
            "metrics": final_metrics,
            "screenshot": str(screenshot_dir / "product-detail-final.png"),
            "bodyTextSample": final_text.replace("\n", " ")[:1000],
        }
        certification_saved = "Certificate saved" in final_text
        checks.append(check("certification_saved", certification_saved, final_text[:500]))
        checks.append(check("certified_badge_visible", "Certified" in final_text))
        checks.append(
            check(
                "tracking_event_action_label_visible",
                "UNKNOWN EVENT" not in final_text and "In Transit" in final_text and "IN_TRANSIT" not in final_text,
            )
        )
        checks.append(check("final_no_horizontal_overflow", has_no_horizontal_overflow(final_metrics), str(final_metrics)))
        capture_screenshot(page, screenshot_dir / "product-detail-final.png")
        browser.close()

    critical_logs = [
        item
        for item in console_messages
        if item["type"] == "error" and "favicon" not in item["text"].lower()
    ]
    observations["actionable_request_failures"] = actionable_request_failures(request_failures)
    checks.append(check("no_page_errors", not page_errors, json.dumps(page_errors[:3])))
    checks.append(
        check(
            "no_request_failures",
            not observations["actionable_request_failures"],
            json.dumps(observations["actionable_request_failures"][:3]),
        )
    )
    checks.append(check("no_external_qr_requests", not external_qr_requests, json.dumps(external_qr_requests[:3])))
    checks.append(check("no_console_errors", not critical_logs, json.dumps(critical_logs[:3])))

    ok = all(item["ok"] for item in checks)
    report = {
        "schema_version": 1,
        "generated_at": _generated_timestamp_utc(),
        "status": "pass" if ok else "fail",
        "baseUrl": args.base_url,
        "apiUrl": args.api_url,
        "viewport": viewport,
        "mobile": bool(args.mobile),
        "checks": checks,
        "observations": observations,
        "consoleMessages": console_messages,
        "requestFailures": request_failures,
        "externalQrRequests": external_qr_requests,
        "pageErrors": page_errors,
        "screenshotDir": str(screenshot_dir),
    }
    return dict(redact_report_public_tokens(report, extract_public_qr_route_tokens(report)))


def main() -> int:
    args = parse_args()
    try:
        result = run_smoke(args)
    except Exception as exc:  # noqa: BLE001 - script evidence should capture unexpected browser/API failures.
        result = {
            "schema_version": 1,
            "generated_at": _generated_timestamp_utc(),
            "status": "fail",
            "checks": [check("unhandled_exception", False, str(exc))],
            "observations": {},
        }
    redacted_result = dict(redact_report_public_tokens(result, extract_public_qr_route_tokens(result)))
    write_json(args.json_out, redacted_result)
    print(f"product detail browser smoke {redacted_result['status']}: {args.json_out}")
    return 0 if redacted_result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
