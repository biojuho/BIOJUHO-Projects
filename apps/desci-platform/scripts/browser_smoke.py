#!/usr/bin/env python3
"""Browser-level smoke checks for the DSCI-DecentBio frontend.

Unlike ``product_smoke.py``, this script runs the client JavaScript in Chromium
and catches broken routes, runtime exceptions, and console errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depends on operator machine
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


@dataclass(frozen=True)
class RouteCheck:
    name: str
    path: str
    expected_text: tuple[str, ...]
    expected_url_path: str | None = None


@dataclass(frozen=True)
class RouteCheckResult:
    name: str
    path: str
    ok: bool
    failures: tuple[str, ...]
    status_code: int | None
    final_path: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "ok": self.ok,
            "failures": list(self.failures),
            "status_code": self.status_code,
            "final_path": self.final_path,
        }


PUBLIC_CHECKS = (
    RouteCheck("home", "/", ("DSCI",)),
    RouteCheck("pricing", "/pricing", ("Starter", "Pro", "Enterprise")),
    RouteCheck("explore", "/explore", ("CRISPR-Cas9", "IPFS")),
    RouteCheck("login", "/login", ("DSCI",)),
    RouteCheck("not-found", "/does-not-exist", ("404",)),
)

PROTECTED_REDIRECT_CHECKS = (
    RouteCheck("dashboard-redirect", "/dashboard", ("DSCI",), expected_url_path="/login"),
    RouteCheck("upload-redirect", "/upload", ("DSCI",), expected_url_path="/login"),
)


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}" if path != "/" else base_url.rstrip("/")


def _path_from_url(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    path = without_scheme.split("/", 1)[-1] if "/" in without_scheme else ""
    path = f"/{path.split('?', 1)[0].split('#', 1)[0]}"
    return path.rstrip("/") or "/"


def _run_check(page, base_url: str, check: RouteCheck, timeout_ms: int) -> RouteCheckResult:
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    status_code: int | None = None
    final_path: str | None = None

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = page.goto(_url(base_url, check.path), wait_until="networkidle", timeout=timeout_ms)
        status_code = response.status if response is not None else 0
        if status_code >= 400:
            failures.append(f"{check.name}: HTTP status {status_code}")

        body_text = page.locator("body").inner_text(timeout=timeout_ms)
        if len(body_text.strip()) < 20:
            failures.append(f"{check.name}: body is unexpectedly short")

        for expected in check.expected_text:
            if expected not in body_text:
                failures.append(f"{check.name}: missing expected text {expected!r}")

        if "Support ID" in body_text or "지원 ID" in body_text:
            failures.append(f"{check.name}: rendered the error boundary")

        if check.expected_url_path:
            final_path = _path_from_url(page.url)
            if final_path != check.expected_url_path:
                failures.append(
                    f"{check.name}: expected final path {check.expected_url_path}, got {final_path}",
                )
        elif page.url:
            final_path = _path_from_url(page.url)
    except PlaywrightTimeoutError as exc:
        failures.append(f"{check.name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{check.name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    if console_errors:
        for message in console_errors[:5]:
            failures.append(f"{check.name}: console error: {message[:300]}")
    if page_errors:
        for message in page_errors[:5]:
            failures.append(f"{check.name}: page error: {message[:300]}")

    return RouteCheckResult(
        name=check.name,
        path=check.path,
        ok=not failures,
        failures=tuple(failures),
        status_code=status_code,
        final_path=final_path,
    )


def build_report(
    frontend: str,
    checks: list[RouteCheck],
    results: list[RouteCheckResult],
    timeout_seconds: float,
    *,
    playwright_available: bool,
    blocker: str | None = None,
) -> dict[str, object]:
    failures = [failure for result in results for failure in result.failures]
    if blocker:
        failures.insert(0, blocker)

    failed = sum(1 for result in results if not result.ok)
    blocked = 1 if blocker else 0
    status = "blocked" if blocker else ("fail" if failed else "pass")
    return {
        "schema_version": 1,
        "tool": "desci_browser_smoke",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "frontend": frontend,
        "timeout_seconds": timeout_seconds,
        "playwright_available": playwright_available,
        "status": status,
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result.ok),
            "failed": failed,
            "blocked": blocked,
            "planned": len(checks),
        },
        "checks": [result.to_payload() for result in results],
        "failures": failures,
    }


def write_json_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_output()

    parser = argparse.ArgumentParser(description="Run browser smoke checks against the DSCI frontend.")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173", help="Frontend base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout per route in seconds")
    parser.add_argument("--skip-protected", action="store_true", help="Skip protected route redirect checks")
    parser.add_argument("--json-out", type=Path, help="Write machine-readable smoke evidence to this path")
    args = parser.parse_args(argv)

    checks = list(PUBLIC_CHECKS)
    if not args.skip_protected:
        checks.extend(PROTECTED_REDIRECT_CHECKS)

    if sync_playwright is None:
        blocker = "Playwright is not installed. Install with: python -m pip install playwright"
        if args.json_out:
            report = build_report(
                args.frontend,
                checks,
                [],
                args.timeout,
                playwright_available=False,
                blocker=blocker,
            )
            write_json_report(args.json_out, report)
        print(f"[browser-smoke] {blocker}")
        return 2

    failures: list[str] = []
    results: list[RouteCheckResult] = []
    timeout_ms = int(args.timeout * 1000)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        for check in checks:
            result = _run_check(page, args.frontend, check, timeout_ms)
            results.append(result)
            status = "FAIL" if result.failures else "OK"
            print(f"[browser-smoke] {check.name:<18} {status} {check.path}")
            failures.extend(result.failures)
        browser.close()

    if args.json_out:
        report = build_report(
            args.frontend,
            checks,
            results,
            args.timeout,
            playwright_available=True,
        )
        write_json_report(args.json_out, report)

    if failures:
        print("\n[browser-smoke] FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[browser-smoke] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
