from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib import error, parse, request

from playwright.sync_api import Page, sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_API_URL = "http://127.0.0.1:8002"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
DEFAULT_DESKTOP_VIEWPORT = "1440x960"
DEFAULT_MOBILE_VIEWPORT = "390x844"
MISSING_AUTH_DETAIL = "Authorization header missing"
EXPECTED_AUTH_CONSOLE_FRAGMENT = "401 (Unauthorized)"
PUBLIC_QR_TOKEN_REDACTION = "<redacted-public-qr-token>"
PUBLIC_VERIFY_ROUTE_RE = re.compile(
    r"((?:agri://verify|/verify|/api/(?:api/)?qr)/)([^/?#\s]+)((?:/verify)?(?:[?#]\S*)?)"
)
PUBLIC_QR_TOKEN_TABLE_RE = re.compile(r"(?<=Token)[A-Za-z0-9_-]{16,}(?=State)")
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
    document.querySelectorAll('[data-testid="qr-token-row"] td:first-child div.font-mono').forEach(element => {
      const value = (element.textContent || '').trim();
      if (value.length >= 8) {
        element.textContent = marker;
      }
    });
}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exercise AgriGuard QR-token and sensor admin routes in a browser.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend API base URL. Defaults to {DEFAULT_API_URL}.")
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
    )
    parser.add_argument("--json-out", default="var/agriguard-admin-routes-browser-smoke.json")
    parser.add_argument("--screenshot-dir", default="var/agriguard-admin-routes-browser-smoke-screens")
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


def redact_public_qr_route_tokens(text: str) -> str:
    redacted = PUBLIC_VERIFY_ROUTE_RE.sub(
        lambda match: f"{match.group(1)}{PUBLIC_QR_TOKEN_REDACTION}{match.group(3)}",
        text,
    )
    return PUBLIC_QR_TOKEN_TABLE_RE.sub(PUBLIC_QR_TOKEN_REDACTION, redacted)


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
    product_name = f"Browser Smoke Batch {uuid.uuid4().hex[:8]}"
    payload = {
        "name": product_name,
        "description": "Browser smoke product for QR token administration.",
        "category": "Fruit",
        "origin": "Smoke Farm",
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
              bodyTextLength: (body.textContent || '').trim().length,
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 800),
            };
        }"""
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def capture_screenshot(page: Page, path: Path, *, mobile: bool) -> None:
    # Viewport captures keep fixed navigation from being burned into the middle
    # of desktop full-page evidence after action-driven scroll positioning.
    mask_public_qr_artifacts_for_screenshot(page)
    page.screenshot(path=str(path), full_page=False)


def attach_page_diagnostics(
    page: Page,
    *,
    console_messages: list[dict[str, str]],
    request_failures: list[dict[str, str]],
    page_errors: list[dict[str, str]],
) -> None:
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
    page.on("pageerror", lambda exc: page_errors.append({"message": str(exc)}))


def is_expected_missing_auth_console(message: dict[str, str]) -> bool:
    text = message.get("text", "")
    return message.get("type") == "error" and EXPECTED_AUTH_CONSOLE_FRAGMENT in text


def actionable_request_failures(request_failures: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        failure
        for failure in request_failures
        if "ERR_ABORTED" not in failure.get("failure", "")
    ]


def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    viewport = resolve_viewport(mobile=args.mobile, viewport=args.viewport)

    product = seed_product(args.api_url, args.operator_token)
    product_id = str(product.get("id") or "")
    checks.append(check("seed_product", bool(product_id), product_id))
    observations["seed_product"] = {
        "id": product_id,
        "name": product.get("name"),
        "qr_code_prefix": str(product.get("qr_code") or "")[:24],
    }

    sensor_id = f"smoke-probe-{uuid.uuid4().hex[:8]}"
    sensor_zone = f"Smoke Zone {uuid.uuid4().hex[:8]}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        anonymous_page = browser.new_page(viewport=viewport, is_mobile=args.mobile, has_touch=args.mobile)
        attach_page_diagnostics(
            anonymous_page,
            console_messages=console_messages,
            request_failures=request_failures,
            page_errors=page_errors,
        )
        anonymous_page.add_init_script("window.localStorage.removeItem('agriguard-operator-token');")
        anonymous_page.goto(route_url(args.base_url, "/qr-tokens"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        anonymous_page.get_by_text("QR Token Management").wait_for(timeout=args.timeout_ms)
        anonymous_page.get_by_text("No token saved. Protected actions will return 401.").wait_for(timeout=args.timeout_ms)
        anonymous_page.get_by_label("Product ID").fill(product_id)
        with anonymous_page.expect_response(
            lambda response: "/qr-tokens/products/" in response.url and response.status == 401,
            timeout=args.timeout_ms,
        ):
            anonymous_page.get_by_role("button", name=re.compile("load tokens", re.I)).click(timeout=args.timeout_ms)
        anonymous_page.get_by_text(MISSING_AUTH_DETAIL).first.wait_for(timeout=args.timeout_ms)
        anonymous_qr_metrics = read_metrics(anonymous_page)
        observations["qr_tokens_missing_token"] = {
            "metrics": anonymous_qr_metrics,
            "screenshot": str(screenshot_dir / "qr-tokens-missing-token.png"),
        }
        checks.append(check("qr_tokens_missing_token_notice_visible", True))
        checks.append(check("qr_tokens_missing_token_blocked", True, MISSING_AUTH_DETAIL))
        checks.append(check("qr_tokens_missing_token_no_horizontal_overflow", has_no_horizontal_overflow(anonymous_qr_metrics), str(anonymous_qr_metrics)))
        capture_screenshot(anonymous_page, screenshot_dir / "qr-tokens-missing-token.png", mobile=args.mobile)

        anonymous_page.goto(route_url(args.base_url, "/sensor-devices"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        anonymous_page.get_by_text("Sensor Device Registry").wait_for(timeout=args.timeout_ms)
        anonymous_page.get_by_text("No token saved. Protected actions will return 401.").wait_for(timeout=args.timeout_ms)
        anonymous_page.get_by_label("Sensor ID", exact=True).fill(f"{sensor_id}-anon")
        anonymous_page.get_by_label("Label").fill("Anonymous browser smoke probe")
        anonymous_page.get_by_label("Assigned zone").fill("Packhouse")
        anonymous_page.get_by_label("Expected interval minutes").fill("5")
        with anonymous_page.expect_response(
            lambda response: "/sensor-devices/" in response.url
            and response.request.method == "PUT"
            and response.status == 401,
            timeout=args.timeout_ms,
        ):
            anonymous_page.get_by_role("button", name=re.compile("register sensor", re.I)).click(timeout=args.timeout_ms)
        anonymous_page.get_by_text(MISSING_AUTH_DETAIL).first.wait_for(timeout=args.timeout_ms)
        anonymous_sensor_metrics = read_metrics(anonymous_page)
        observations["sensor_devices_missing_token"] = {
            "metrics": anonymous_sensor_metrics,
            "screenshot": str(screenshot_dir / "sensor-devices-missing-token.png"),
        }
        checks.append(check("sensor_devices_missing_token_notice_visible", True))
        checks.append(check("sensor_devices_missing_token_blocked", True, MISSING_AUTH_DETAIL))
        checks.append(check("sensor_devices_missing_token_no_horizontal_overflow", has_no_horizontal_overflow(anonymous_sensor_metrics), str(anonymous_sensor_metrics)))
        capture_screenshot(anonymous_page, screenshot_dir / "sensor-devices-missing-token.png", mobile=args.mobile)
        anonymous_page.close()

        page = browser.new_page(viewport=viewport, is_mobile=args.mobile, has_touch=args.mobile)
        page.add_init_script(
            "window.localStorage.setItem('agriguard-operator-token', "
            f"{json.dumps(args.operator_token)});",
        )
        attach_page_diagnostics(
            page,
            console_messages=console_messages,
            request_failures=request_failures,
            page_errors=page_errors,
        )

        page.goto(route_url(args.base_url, "/qr-tokens"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_text("QR Token Management").wait_for(timeout=args.timeout_ms)
        page.get_by_label("Product ID").fill(product_id)
        page.get_by_role("button", name=re.compile("load tokens", re.I)).click(timeout=args.timeout_ms)
        page.get_by_text(re.compile(rf"matching tokens for {re.escape(product_id)}")).wait_for(timeout=args.timeout_ms)
        checks.append(check("qr_tokens_loaded", True, product_id))

        page.get_by_role("button", name=re.compile("reissue label", re.I)).click(timeout=args.timeout_ms)
        page.get_by_text("Confirm QR token reissue").wait_for(timeout=args.timeout_ms)
        page.get_by_role("button", name=re.compile("confirm", re.I)).click(timeout=args.timeout_ms)
        page.get_by_text("New label URL ready").wait_for(timeout=args.timeout_ms)
        qr_text = body_text(page)
        qr_reissued = "QR token reissued" in qr_text and "/verify/" in qr_text
        qr_tokens_metrics = read_metrics(page)
        observations["qr_tokens"] = {
            "metrics": qr_tokens_metrics,
            "reissued": qr_reissued,
            "screenshot": str(screenshot_dir / "qr-tokens.png"),
        }
        checks.append(check("qr_token_reissued", qr_reissued, "one-time public verify label URL rendered"))
        checks.append(check("qr_tokens_no_horizontal_overflow", has_no_horizontal_overflow(qr_tokens_metrics), str(qr_tokens_metrics)))
        capture_screenshot(page, screenshot_dir / "qr-tokens.png", mobile=args.mobile)

        page.goto(route_url(args.base_url, "/sensor-devices"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_text("Sensor Device Registry").wait_for(timeout=args.timeout_ms)
        page.get_by_label("Sensor ID", exact=True).fill(sensor_id)
        page.get_by_label("Label").fill("Browser smoke probe")
        page.get_by_label("Assigned zone").fill(sensor_zone)
        page.get_by_label("Owner ID").fill("tenant-browser-smoke")
        page.get_by_label("Expected interval minutes").fill("5")
        page.get_by_role("button", name=re.compile("register sensor", re.I)).click(timeout=args.timeout_ms)
        page.get_by_text(f"Sensor {sensor_id} saved.").wait_for(timeout=args.timeout_ms)
        page.get_by_label("Zone filter").fill(sensor_zone)
        page.get_by_role("button", name=re.compile("apply filters", re.I)).click(timeout=args.timeout_ms)
        page.get_by_text(sensor_id, exact=True).wait_for(timeout=args.timeout_ms)
        checks.append(check("sensor_registered", True, sensor_id))

        page.get_by_text("MQTT broker provisioning").wait_for(timeout=args.timeout_ms)
        page.locator("code").filter(has_text=f"user {sensor_id}").first.wait_for(timeout=args.timeout_ms)
        provisioning_text = body_text(page)
        provisioning_ok = (
            f"user {sensor_id}" in provisioning_text
            and f"topic write agriguard/sensors/{sensor_id}" in provisioning_text
            and f"mosquitto_passwd /etc/mosquitto/passwd {sensor_id}" in provisioning_text
        )
        sensor_devices_metrics = read_metrics(page)
        observations["sensor_devices"] = {
            "metrics": sensor_devices_metrics,
            "registered": sensor_id in provisioning_text,
            "screenshot": str(screenshot_dir / "sensor-devices.png"),
        }
        checks.append(check("mqtt_broker_provisioning_rendered", provisioning_ok, sensor_id))
        checks.append(check("sensor_devices_no_horizontal_overflow", has_no_horizontal_overflow(sensor_devices_metrics), str(sensor_devices_metrics)))
        capture_screenshot(page, screenshot_dir / "sensor-devices.png", mobile=args.mobile)
        browser.close()

    observations["sensor_id"] = sensor_id
    observations["sensor_zone"] = sensor_zone
    observations["console_messages"] = console_messages
    observations["request_failures"] = request_failures
    observations["page_errors"] = page_errors
    observations["actionable_request_failures"] = actionable_request_failures(request_failures)

    expected_auth_console_messages = [
        item for item in console_messages if is_expected_missing_auth_console(item)
    ]
    critical_logs = [
        item for item in console_messages if item["type"] == "error" and "favicon" not in item["text"].lower()
        and not is_expected_missing_auth_console(item)
    ]
    checks.append(check("no_page_errors", not page_errors, json.dumps(page_errors[:3])))
    checks.append(
        check(
            "no_request_failures",
            not observations["actionable_request_failures"],
            json.dumps(observations["actionable_request_failures"][:3]),
        )
    )
    checks.append(
        check(
            "expected_missing_auth_console_errors",
            len(expected_auth_console_messages) == 2,
            json.dumps(expected_auth_console_messages[:3]),
        )
    )
    checks.append(check("no_console_errors", not critical_logs, json.dumps(critical_logs[:3])))

    ok = all(item["ok"] for item in checks)
    report = {
        "status": "pass" if ok else "fail",
        "checks": checks,
        "viewport": viewport,
        "mobile": bool(args.mobile),
        "observations": observations,
        "screenshotDir": str(screenshot_dir),
    }
    return dict(redact_report_public_tokens(report, extract_public_qr_route_tokens(report)))


def main() -> int:
    args = parse_args()
    try:
        result = run_smoke(args)
    except Exception as exc:  # noqa: BLE001 - script evidence should capture unexpected browser/API failures.
        result = {
            "status": "fail",
            "checks": [check("unhandled_exception", False, str(exc))],
            "viewport": resolve_viewport(mobile=args.mobile, viewport=args.viewport),
            "mobile": bool(args.mobile),
            "observations": {},
            "screenshotDir": args.screenshot_dir,
        }
    redacted_result = dict(redact_report_public_tokens(result, extract_public_qr_route_tokens(result)))
    write_json(args.json_out, redacted_result)
    print(f"admin routes browser smoke {redacted_result['status']}: {args.json_out}")
    return 0 if redacted_result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
