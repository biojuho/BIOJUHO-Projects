from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, parse, request

from playwright.sync_api import Page, sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_API_URL = ""
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
LEGACY_FIXTURE_MANUAL_TOKEN = "mock-0"
DEFAULT_INVALID_MANUAL_VALUE = "not a valid AgriGuard QR"
DEFAULT_INVALID_TOKEN = "not-a-real-token"
PUBLIC_QR_TOKEN_REDACTION = "<redacted-public-qr-token>"
PUBLIC_VERIFY_ROUTE_RE = re.compile(
    r"((?:agri://verify|/verify|/api/(?:api/)?qr)/)[^/?#\s]+((?:/verify)?(?:[?#]\S*)?)"
)
FIRST_VIEWPORT_MAX_WIDTH = 500
PUBLIC_VERIFY_SUMMARY_TARGETS = [
    {
        "name": "manual_verify_origin_card_first_viewport",
        "text": "Origin",
        "closest_selector": ".rounded-md.border",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "manual_verify_batch_card_first_viewport",
        "text": "Batch",
        "closest_selector": ".rounded-md.border",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "manual_verify_temperature_card_first_viewport",
        "text": "Temperature",
        "closest_selector": ".rounded-md.border",
        "min_visible_ratio": 0.98,
    },
    {
        "name": "manual_verify_last_checked_card_first_viewport",
        "text": "Last checked",
        "closest_selector": ".rounded-md.border",
        "min_visible_ratio": 0.98,
    },
]


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AgriGuard QR scanner and consumer verification browser smoke.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Preview base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=(
            "Optional backend API URL used to seed a valid manual token when --manual-token is omitted. "
            "Defaults to AGRIGUARD_BROWSER_API_URL or BASE_URL/api."
        ),
    )
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
    )
    parser.add_argument("--manual-token", default=None)
    parser.add_argument("--invalid-manual-value", default=DEFAULT_INVALID_MANUAL_VALUE)
    parser.add_argument("--invalid-token", default=DEFAULT_INVALID_TOKEN)
    parser.add_argument("--json-out", default="var/agriguard-qr-path-browser-smoke.json")
    parser.add_argument("--screenshot-dir", default="var/agriguard-qr-path-browser-smoke-screens")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--viewport", default="390x844", help="Viewport size as WIDTHxHEIGHT. Defaults to 390x844.")
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


def route_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def resolve_seed_api_url(*, base_url: str, api_url: str) -> str:
    explicit_api_url = api_url.strip()
    if explicit_api_url:
        return explicit_api_url.rstrip("/")
    env_api_url = os.getenv("AGRIGUARD_BROWSER_API_URL", "").strip()
    if env_api_url:
        return env_api_url.rstrip("/")
    return route_url(base_url, "/api")


def check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def extract_verify_token(qr_code: str) -> str:
    value = str(qr_code or "").strip()
    if not value:
        return ""

    parsed = parse.urlparse(value)
    if parsed.scheme == "agri" and parsed.netloc == "verify":
        return parse.unquote(parsed.path.lstrip("/"))
    path = parsed.path if parsed.scheme or parsed.netloc else value
    path = path.lstrip("/")
    while path.startswith("verify/"):
        path = path.removeprefix("verify/")
    if path:
        return parse.unquote(path)
    return value


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


def seed_manual_verify_token(api_url: str, operator_token: str) -> dict[str, object]:
    owner_id = "dev-user-id"
    payload = {
        "name": f"QR Path Smoke Batch {uuid.uuid4().hex[:8]}",
        "description": "Browser smoke product for QR path public verification.",
        "category": "Vegetables",
        "origin": "QR Path Smoke Farm",
        "requires_cold_chain": True,
    }
    product = api_request(
        api_url=api_url,
        method="POST",
        path=f"/products/?owner_id={parse.quote(owner_id)}",
        token=operator_token,
        payload=payload,
    )
    token = extract_verify_token(str(product.get("qr_code") or ""))
    if not token:
        raise RuntimeError("Seeded product did not include a public verification token.")
    return {
        "token": token,
        "product_id": product.get("id"),
        "product_name": product.get("name"),
        "qr_code_prefix": str(product.get("qr_code") or "")[:48],
    }


def page_text(page: Page) -> str:
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
              bodyTextSample: (body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1000),
            };
        }"""
    )


def has_no_horizontal_overflow(metrics: dict[str, object]) -> bool:
    allowed_width = max(int(metrics["clientWidth"]), int(metrics["viewportWidth"]))
    return int(metrics["scrollWidth"]) <= allowed_width + 1


def should_check_first_viewport_targets(metrics: dict[str, object]) -> bool:
    return int(metrics["viewportWidth"]) <= FIRST_VIEWPORT_MAX_WIDTH


def measure_first_viewport_target(page: Page, spec: dict[str, object]) -> dict[str, object]:
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
            const ok = visibleHeight >= minVisibleHeight && visibleRatio >= minVisibleRatio;

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
              minVisibleHeight,
              minVisibleRatio,
              viewportHeight: window.innerHeight,
              viewportWidth: window.innerWidth,
            };
        }""",
        spec,
    )
    return dict(measurement)


def wait_for_public_verify(page: Page, timeout_ms: int) -> None:
    page.wait_for_function(
        """() => {
            const text = document.body.textContent || '';
            return text.includes('Public view') && !text.includes('Verifying QR');
        }""",
        timeout=timeout_ms,
    )


def verify_route_matches(url: str, token: str) -> bool:
    expected_path = f"/verify/{token}"
    current_path = parse.urlparse(url).path
    return current_path == expected_path or parse.unquote(current_path) == expected_path


def is_public_verify_api_response(url: str) -> bool:
    parts = [part for part in parse.urlparse(url).path.split("/") if part]
    return len(parts) >= 4 and parts[0] == "api" and parts[-3] == "qr" and parts[-1] == "verify"


def public_verify_response_cache_ok(response: dict[str, object]) -> bool:
    cache_control = str(response.get("cacheControl") or "").lower()
    directives = {part.strip() for part in cache_control.split(",")}
    return (
        "no-store" in directives
        and str(response.get("pragma") or "").lower() == "no-cache"
        and str(response.get("expires") or "") == "0"
    )


def wait_for_verify_route(page: Page, token: str, timeout_ms: int) -> None:
    expected_path = f"/verify/{token}"
    deadline = time.monotonic() + max(timeout_ms, 1) / 1000
    while time.monotonic() < deadline:
        if verify_route_matches(page.url, token):
            return
        page.wait_for_timeout(min(250, max(1, int((deadline - time.monotonic()) * 1000))))

    try:
        body_sample = page_text(page).replace("\n", " ").strip()[:500]
    except Exception:  # noqa: BLE001 - secondary diagnostics must not hide the route failure.
        body_sample = "<unavailable>"
    raise RuntimeError(
        "Manual verification route did not open "
        f"(expected_path={expected_path!r}, current_url={page.url!r}, body_sample={body_sample!r})."
    )


def capture(page: Page, screenshot_dir: Path, name: str) -> str:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = screenshot_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return str(path)


def run_browser(args: argparse.Namespace) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    observations: dict[str, object] = {}
    console_messages: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    public_verify_responses: list[dict[str, object]] = []
    screenshot_dir = Path(args.screenshot_dir)
    viewport = parse_viewport(args.viewport)
    manual_token = args.manual_token.strip() if args.manual_token else None
    seed_api_url = resolve_seed_api_url(base_url=args.base_url, api_url=args.api_url)

    if manual_token is None:
        seeded = seed_manual_verify_token(seed_api_url, args.operator_token)
        manual_token = str(seeded["token"])
        observations["seededManualToken"] = seeded
        checks.append(check("seed_manual_verify_token", bool(manual_token), str(seeded.get("product_id") or "")))

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

        def track_public_verify_response(response) -> None:
            if not is_public_verify_api_response(response.url):
                return
            headers = response.headers
            public_verify_responses.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "cacheControl": headers.get("cache-control", ""),
                    "pragma": headers.get("pragma", ""),
                    "expires": headers.get("expires", ""),
                }
            )

        page.on("response", track_public_verify_response)

        page.goto(route_url(args.base_url, "/scan"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        manual_input = page.get_by_label("Manual verification code")
        manual_input.wait_for(timeout=args.timeout_ms)
        verify_button = page.get_by_role("button", name="Verify code")
        initial_text = page_text(page)
        initial_metrics = read_metrics(page)
        observations["scan"] = {
            "url": page.url,
            "manualInputVisible": manual_input.is_visible(),
            "verifyButtonInitiallyDisabled": verify_button.is_disabled(),
            "showsCameraFallbackCopy": "No camera?" in initial_text,
            "showsScannerGuidance": "Scan Product QR" in initial_text,
            "metrics": initial_metrics,
            "screenshot": capture(page, screenshot_dir, "scan"),
        }
        checks.append(check("scan_manual_input_visible", bool(observations["scan"]["manualInputVisible"])))
        checks.append(check("scan_verify_button_disabled_until_input", bool(observations["scan"]["verifyButtonInitiallyDisabled"])))
        checks.append(check("scan_camera_fallback_copy_visible", bool(observations["scan"]["showsCameraFallbackCopy"])))
        checks.append(check("scan_no_horizontal_overflow", has_no_horizontal_overflow(initial_metrics), str(initial_metrics)))

        manual_input.fill(args.invalid_manual_value)
        verify_button.click(timeout=args.timeout_ms)
        invalid_manual_error = "Enter a valid AgriGuard verification link or token."
        page.get_by_text(invalid_manual_error).wait_for(timeout=args.timeout_ms)
        invalid_manual_text = page_text(page)
        observations["invalidManual"] = {
            "url": page.url,
            "value": args.invalid_manual_value,
            "errorVisible": invalid_manual_error in invalid_manual_text,
            "retryVisible": page.get_by_role("button", name="Retry scan").is_visible(),
            "scannerPausedVisible": "Scanner paused" in invalid_manual_text,
            "stillOnScanRoute": page.url.rstrip("/").endswith("/scan"),
        }
        checks.append(check("invalid_manual_error_visible", bool(observations["invalidManual"]["errorVisible"])))
        checks.append(check("invalid_manual_retry_visible", bool(observations["invalidManual"]["retryVisible"])))
        checks.append(check("invalid_manual_scanner_paused_visible", bool(observations["invalidManual"]["scannerPausedVisible"])))
        checks.append(check("invalid_manual_stays_on_scan_route", bool(observations["invalidManual"]["stillOnScanRoute"]), page.url))

        manual_input.fill(manual_token)
        verify_button.click(timeout=args.timeout_ms)
        wait_for_verify_route(page, manual_token, args.timeout_ms)
        wait_for_public_verify(page, args.timeout_ms)
        valid_text = page_text(page)
        valid_metrics = read_metrics(page)
        manual_verify_affordances = []
        if should_check_first_viewport_targets(valid_metrics):
            manual_verify_affordances = [
                measure_first_viewport_target(page, spec)
                for spec in PUBLIC_VERIFY_SUMMARY_TARGETS
            ]
        observations["manualVerify"] = {
            "url": page.url,
            "publicViewVisible": "Public view" in valid_text,
            "trustCopyVisible": any(value in valid_text for value in ["Safe", "Warning", "Unknown"]),
            "batchEvidenceVisible": "Batch and origin" in valid_text,
            "notUnavailable": "Verification unavailable" not in valid_text,
            "metrics": valid_metrics,
            "firstViewportTargets": manual_verify_affordances,
            "screenshot": capture(page, screenshot_dir, "manual-verify"),
        }
        checks.append(check("manual_verify_url_opened", f"/verify/{manual_token}" in page.url, page.url))
        checks.append(check("manual_verify_public_view_visible", bool(observations["manualVerify"]["publicViewVisible"])))
        checks.append(check("manual_verify_trust_copy_visible", bool(observations["manualVerify"]["trustCopyVisible"])))
        checks.append(check("manual_verify_batch_evidence_visible", bool(observations["manualVerify"]["batchEvidenceVisible"])))
        checks.append(check("manual_verify_not_unavailable", bool(observations["manualVerify"]["notUnavailable"])))
        checks.append(check("manual_verify_no_horizontal_overflow", has_no_horizontal_overflow(valid_metrics), str(valid_metrics)))
        for item in manual_verify_affordances:
            checks.append(check(str(item["name"]), bool(item["ok"]), json.dumps(item, sort_keys=True)))

        page.goto(route_url(args.base_url, f"/verify/{args.invalid_token}"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        wait_for_public_verify(page, args.timeout_ms)
        invalid_text = page_text(page)
        invalid_metrics = read_metrics(page)
        observations["invalidVerify"] = {
            "url": page.url,
            "publicViewVisible": "Public view" in invalid_text,
            "invalidCopyVisible": any(value in invalid_text for value in ["Unverified AgriGuard QR", "QR not verified"]),
            "notUnavailable": "Verification unavailable" not in invalid_text,
            "metrics": invalid_metrics,
            "screenshot": capture(page, screenshot_dir, "invalid-verify"),
        }
        checks.append(check("invalid_verify_public_view_visible", bool(observations["invalidVerify"]["publicViewVisible"])))
        checks.append(check("invalid_verify_blocks_trust", bool(observations["invalidVerify"]["invalidCopyVisible"])))
        checks.append(check("invalid_verify_not_unavailable", bool(observations["invalidVerify"]["notUnavailable"])))
        checks.append(check("invalid_verify_no_horizontal_overflow", has_no_horizontal_overflow(invalid_metrics), str(invalid_metrics)))

        browser.close()

    public_verify_cache_ok = (
        len(public_verify_responses) >= 2
        and all(public_verify_response_cache_ok(response) for response in public_verify_responses)
    )
    observations["publicVerifyResponses"] = public_verify_responses
    checks.append(
        check(
            "public_verify_api_responses_no_store",
            public_verify_cache_ok,
            json.dumps(public_verify_responses, sort_keys=True),
        )
    )

    actionable_request_failures = [
        failure for failure in request_failures if "ERR_ABORTED" not in failure.get("failure", "")
    ]
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
    report = {
        "schema_version": 1,
        "generated_at": _generated_timestamp_utc(),
        "baseUrl": args.base_url,
        "apiUrl": seed_api_url,
        "viewport": viewport,
        "manualToken": manual_token,
        "invalidToken": args.invalid_token,
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "checks": checks,
        "observations": observations,
        "consoleMessages": console_messages,
        "requestFailures": request_failures,
        "actionableRequestFailures": actionable_request_failures,
        "pageErrors": page_errors,
        "screenshotDir": str(screenshot_dir),
    }
    return dict(redact_report_public_tokens(report, {manual_token}))


def main() -> int:
    args = parse_args()
    try:
        report = run_browser(args)
    except Exception as exc:  # noqa: BLE001 - browser smoke evidence should capture unexpected API/UI failures.
        report = {
            "schema_version": 1,
            "generated_at": _generated_timestamp_utc(),
            "baseUrl": args.base_url,
            "apiUrl": resolve_seed_api_url(base_url=args.base_url, api_url=args.api_url),
            "viewport": parse_viewport(args.viewport),
            "manualToken": args.manual_token,
            "invalidToken": args.invalid_token,
            "passed": 0,
            "total": 1,
            "ok": False,
            "checks": [check("unhandled_exception", False, str(exc))],
            "observations": {},
            "consoleMessages": [],
            "requestFailures": [],
            "actionableRequestFailures": [],
            "pageErrors": [],
            "screenshotDir": args.screenshot_dir,
        }
        report = dict(redact_report_public_tokens(report, {args.manual_token.strip() if args.manual_token else ""}))
    write_json(args.json_out, report)
    print(f"agriguard qr path browser smoke: {report['passed']}/{report['total']} PASS")
    print(f"json written: {args.json_out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
