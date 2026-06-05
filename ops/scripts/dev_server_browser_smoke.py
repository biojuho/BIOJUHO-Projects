#!/usr/bin/env python3
"""Manifest-backed browser smoke checks for local dev-server frontends."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_BROWSER_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "dev_server_browser_checks.json"
DEFAULT_TARGETS_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "dev_server_targets.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dev_server_status import load_manifest as load_targets_manifest  # noqa: E402

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depends on operator machine
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


@dataclass(frozen=True)
class RouteResult:
    target_id: str
    name: str
    path: str
    ok: bool
    failures: list[str]
    websocket_count: int = 0
    websocket_failures: list[str] | None = None
    expected_text_count: int = 0
    matched_expected_text: list[str] | None = None
    missing_expected_text: list[str] | None = None
    status_code: int | None = None
    final_path: str | None = None


def browser_isolation_policy() -> dict[str, Any]:
    return {
        "mode": "ephemeral_context",
        "persistent_profile": False,
        "user_data_dir": "",
        "reason": "Each browser-smoke run creates a fresh context to avoid persistent profile lock contention.",
    }


def load_browser_manifest(path: Path = DEFAULT_BROWSER_MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("browser manifest root must be an object")
    return payload


def target_map(targets_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {target["id"]: target for target in targets_manifest.get("targets", []) if isinstance(target, dict)}


def validate_manifest(browser_manifest: dict[str, Any], targets_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if browser_manifest.get("schema_version") != 1 or isinstance(browser_manifest.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _require_string(browser_manifest.get("generated_at"), "generated_at", errors)
    _require_string(browser_manifest.get("description"), "description", errors)
    targets = target_map(targets_manifest)
    checks = browser_manifest.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty array")
        return errors

    seen_target_ids: set[str] = set()
    for check_index, check in enumerate(checks):
        prefix = f"checks[{check_index}]"
        if not isinstance(check, dict):
            errors.append(f"{prefix} must be an object")
            continue
        target_id = _require_string(check.get("target_id"), f"{prefix}.target_id", errors)
        target = targets.get(target_id)
        if target_id:
            if target_id in seen_target_ids:
                errors.append(f"{prefix}.target_id must be unique")
            seen_target_ids.add(target_id)
            if target is None:
                errors.append(f"{prefix}.target_id references unknown target: {target_id}")
            elif target.get("kind") != "frontend":
                errors.append(f"{prefix}.target_id must reference a frontend target")
        routes = check.get("routes")
        if not isinstance(routes, list) or not routes:
            errors.append(f"{prefix}.routes must be a non-empty array")
            continue
        seen_route_names: set[str] = set()
        for route_index, route in enumerate(routes):
            route_prefix = f"{prefix}.routes[{route_index}]"
            if not isinstance(route, dict):
                errors.append(f"{route_prefix} must be an object")
                continue
            name = _require_string(route.get("name"), f"{route_prefix}.name", errors)
            if name:
                if name in seen_route_names:
                    errors.append(f"{route_prefix}.name must be unique within target")
                seen_route_names.add(name)
            path = route.get("path")
            if not isinstance(path, str):
                errors.append(f"{route_prefix}.path must be a string")
            elif path and not path.startswith("/"):
                errors.append(f"{route_prefix}.path must be empty or start with /")
            _validate_string_list(route.get("expected_text"), f"{route_prefix}.expected_text", errors)
            expected_url_path = route.get("expected_url_path")
            if expected_url_path is not None and (
                not isinstance(expected_url_path, str) or not expected_url_path.startswith("/")
            ):
                errors.append(f"{route_prefix}.expected_url_path must start with / when present")
    return errors


def selected_checks(browser_manifest: dict[str, Any], target_ids: list[str] | None = None) -> list[dict[str, Any]]:
    checks = list(browser_manifest["checks"])
    if not target_ids:
        return checks
    selected = [check for check in checks if check["target_id"] in target_ids]
    missing = sorted(set(target_ids) - {check["target_id"] for check in selected})
    if missing:
        raise ValueError(f"unknown browser check target(s): {', '.join(missing)}")
    return selected


def run_browser_smoke(
    browser_manifest: dict[str, Any],
    targets_manifest: dict[str, Any],
    *,
    target_ids: list[str] | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    checks = selected_checks(browser_manifest, target_ids)
    if sync_playwright is None:
        return build_report(checks, [], status="blocked", blocker="Playwright is not installed")

    targets = target_map(targets_manifest)
    timeout_ms = int(timeout_seconds * 1000)
    results: list[RouteResult] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            page = context.new_page()
            for check in checks:
                target = targets[check["target_id"]]
                for route in check["routes"]:
                    results.append(run_route(page, target, route, timeout_ms))
        finally:
            context.close()
            browser.close()

    failed = any(not result.ok for result in results)
    return build_report(checks, results, status="fail" if failed else "pass")


def run_route(page, target: dict[str, Any], route: dict[str, Any], timeout_ms: int) -> RouteResult:
    target_id = target["id"]
    route_name = route["name"]
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_failures: list[str] = []
    websocket_count = 0
    websocket_failures: list[str] = []
    status_code: int | None = None
    final_path: str | None = None
    expected_text = [str(item) for item in route.get("expected_text", [])]
    matched_expected_text: list[str] = []
    missing_expected_text: list[str] = []

    def mark_unchecked_expected_text() -> None:
        for expected in expected_text:
            if expected not in matched_expected_text and expected not in missing_expected_text:
                missing_expected_text.append(expected)

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request_failed(request) -> None:
        failure = request.failure or {}
        error_text = failure.get("errorText") if isinstance(failure, dict) else str(failure)
        request_failures.append(f"{request.url}: {error_text}")

    def collect_websocket(websocket) -> None:
        nonlocal websocket_count
        websocket_count += 1

        def collect_socket_error(error) -> None:
            websocket_failures.append(f"{websocket.url}: {error}")

        websocket.on("socketerror", collect_socket_error)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("requestfailed", collect_request_failed)
    page.on("websocket", collect_websocket)
    try:
        response = page.goto(route_url(target["url"], route["path"]), wait_until="networkidle", timeout=timeout_ms)
        status_code = response.status if response is not None else 0
        if status_code >= 400:
            failures.append(f"{target_id}/{route_name}: HTTP status {status_code}")
        body_text = page.locator("body").inner_text(timeout=timeout_ms)
        for expected in expected_text:
            if expected not in body_text:
                missing_expected_text.append(expected)
                failures.append(f"{target_id}/{route_name}: missing expected text {expected!r}")
            else:
                matched_expected_text.append(expected)
        final_path = path_from_url(page.url)
        expected_url_path = route.get("expected_url_path")
        if expected_url_path and final_path != expected_url_path:
            failures.append(f"{target_id}/{route_name}: expected final path {expected_url_path}, got {final_path}")
    except PlaywrightTimeoutError as exc:
        mark_unchecked_expected_text()
        failures.append(f"{target_id}/{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        mark_unchecked_expected_text()
        failures.append(f"{target_id}/{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("requestfailed", collect_request_failed)
        page.remove_listener("websocket", collect_websocket)

    for message in console_errors[:5]:
        failures.append(f"{target_id}/{route_name}: console error: {message[:300]}")
    for message in page_errors[:5]:
        failures.append(f"{target_id}/{route_name}: page error: {message[:300]}")
    for message in request_failures[:5]:
        failures.append(f"{target_id}/{route_name}: request failed: {message[:300]}")
    for message in websocket_failures[:5]:
        failures.append(f"{target_id}/{route_name}: websocket failed: {message[:300]}")

    return RouteResult(
        target_id=target_id,
        name=route_name,
        path=route["path"],
        ok=not failures,
        failures=failures,
        websocket_count=websocket_count,
        websocket_failures=websocket_failures,
        expected_text_count=len(expected_text),
        matched_expected_text=matched_expected_text,
        missing_expected_text=missing_expected_text,
        status_code=status_code,
        final_path=final_path,
    )


def route_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    origin = base_url.split("://", 1)
    if len(origin) == 2:
        scheme, rest = origin
        host = rest.split("/", 1)[0]
        return f"{scheme}://{host}{path}"
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def path_from_url(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    path = without_scheme.split("/", 1)[-1] if "/" in without_scheme else ""
    path = f"/{path.split('?', 1)[0].split('#', 1)[0]}"
    return path.rstrip("/") or "/"


def build_report(
    checks: list[dict[str, Any]],
    results: list[RouteResult],
    *,
    status: str,
    blocker: str | None = None,
) -> dict[str, Any]:
    failures = [failure for result in results for failure in result.failures]
    if blocker:
        failures.insert(0, blocker)
    route_count = sum(len(check["routes"]) for check in checks)
    websocket_failures = [
        failure
        for result in results
        for failure in (result.websocket_failures or [])
    ]
    return {
        "schema_version": 1,
        "tool": "dev_server_browser_smoke",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "summary": {
            "targets": len(checks),
            "routes": route_count,
            "completed": len(results),
            "passed": sum(1 for result in results if result.ok),
            "failed": sum(1 for result in results if not result.ok),
            "blocked": 1 if blocker else 0,
            "websockets": sum(result.websocket_count for result in results),
            "websocket_failures": len(websocket_failures),
        },
        "browser_isolation": browser_isolation_policy(),
        "results": [asdict(result) for result in results],
        "failures": failures,
    }


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Dev-Server Browser Smoke",
        "",
        f"- Status: `{report['status']}`",
        f"- Targets: `{summary['targets']}`",
        f"- Routes: `{summary['routes']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Blocked: `{summary['blocked']}`",
        f"- WebSockets observed: `{summary.get('websockets', 0)}`",
        f"- WebSocket failures: `{summary.get('websocket_failures', 0)}`",
        f"- Browser isolation: `{report['browser_isolation']['mode']}`",
        f"- Persistent profile: `{str(report['browser_isolation']['persistent_profile']).lower()}`",
        "",
        "## Results",
        "",
    ]
    if not report["results"]:
        lines.append("- none")
    for result in report["results"]:
        state = "PASS" if result["ok"] else "FAIL"
        matched_count = len(result.get("matched_expected_text") or [])
        expected_count = int(result.get("expected_text_count") or 0)
        lines.append(
            f"- `{state}` `{result['target_id']}` `{result['name']}` `{result['path']}` "
            f"expected=`{matched_count}/{expected_count}` "
            f"websocket_failures=`{len(result.get('websocket_failures') or [])}`"
        )
    expected_results = [
        result for result in report["results"] if int(result.get("expected_text_count") or 0) > 0
    ]
    if expected_results:
        lines.extend(["", "## Expected Text Evidence", ""])
        for result in expected_results:
            matched_text = result.get("matched_expected_text") or []
            missing_text = result.get("missing_expected_text") or []
            matched_count = len(matched_text)
            expected_count = int(result.get("expected_text_count") or 0)
            lines.append(
                f"- `{result['target_id']}` `{result['name']}` matched=`{matched_count}/{expected_count}`"
            )
            if matched_text:
                lines.extend(f"  - matched: `{_markdown_inline_text(item)}`" for item in matched_text)
            if missing_text:
                lines.extend(f"  - missing: `{_markdown_inline_text(item)}`" for item in missing_text)
            if not missing_text:
                lines.append("  - missing: none")
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    lines.append("")
    return "\n".join(lines)


def _markdown_inline_text(value: Any) -> str:
    return str(value).replace("`", "'").replace("\r", " ").replace("\n", " ")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run manifest-backed browser smoke checks for local dev servers.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_BROWSER_MANIFEST)
    parser.add_argument("--targets-manifest", type=Path, default=DEFAULT_TARGETS_MANIFEST)
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    browser_manifest = load_browser_manifest(args.manifest)
    targets_manifest = load_targets_manifest(args.targets_manifest)
    errors = validate_manifest(browser_manifest, targets_manifest)
    if errors:
        print("dev-server browser smoke manifest invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    try:
        checks = selected_checks(browser_manifest, args.targets)
    except ValueError as exc:
        print(f"dev-server browser smoke failed: {exc}", file=sys.stderr)
        return 1
    if args.validate_only:
        report = build_report(checks, [], status="valid")
    else:
        report = run_browser_smoke(
            browser_manifest,
            targets_manifest,
            target_ids=args.targets,
            timeout_seconds=args.timeout,
        )

    if args.json_out:
        write_json(args.json_out, report)
    if args.markdown_out:
        write_text(args.markdown_out, format_markdown(report))

    summary = report["summary"]
    print(
        "dev-server browser smoke "
        f"{report['status']}: {summary['completed']}/{summary['routes']} routes, failed={summary['failed']}"
    )
    if report["status"] == "blocked":
        return 2
    return 0 if report["status"] in {"pass", "valid"} else 1


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")


if __name__ == "__main__":
    raise SystemExit(main())
