from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib import error, parse, request

DEFAULT_BASE_URL = "http://127.0.0.1:5174"
DEFAULT_API_URL = "http://127.0.0.1:8002"
DEFAULT_OPERATOR_TOKEN = "browser-smoke-token"
REQUIRED_BACKEND_OPENAPI_PATHS = (
    "/products/",
    "/products/page",
    "/qr-events/kpis",
    "/qr-events/kpis/trend",
    "/qr-tokens/products/{product_id}",
    "/sensor-devices",
    "/sensor-devices/{sensor_id}",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_SCREENSHOT_BYTES = 512


class BrowserSmokeStep:
    def __init__(self, *, name: str, command: list[str], json_out: Path) -> None:
        self.name = name
        self.command = command
        self.json_out = json_out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AgriGuard live-backend browser smoke suite.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Frontend base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend API base URL. Defaults to {DEFAULT_API_URL}.")
    parser.add_argument(
        "--operator-token",
        default=os.getenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN") or DEFAULT_OPERATOR_TOKEN,
        help="Operator token for authenticated browser paths. Redacted from the aggregate report.",
    )
    parser.add_argument("--output-dir", default="var/agriguard-browser-smoke-suite")
    parser.add_argument("--json-out", default="var/agriguard-browser-smoke-suite.json")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--mobile", action="store_true", help="Run mobile variants where the child smoke supports it.")
    parser.add_argument(
        "--skip-backend-contract-check",
        action="store_true",
        help="Skip the live backend and frontend proxy prechecks before running browser steps.",
    )
    parser.add_argument(
        "--include-unavailable-check",
        action="store_true",
        help=(
            "Also run the consumer verify unavailable smoke. Use only when the frontend is up and "
            "the backend/proxy target is intentionally unavailable."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Write the aggregate command plan without executing it.")
    return parser.parse_args()


def route_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _script_path(name: str) -> str:
    return str(Path(__file__).resolve().parent / name)


def _json_path(output_dir: Path, name: str) -> Path:
    return output_dir / f"{name}.json"


def _add_mobile(command: list[str], *, mobile: bool) -> list[str]:
    if mobile:
        return command + ["--mobile"]
    return command


def build_steps(args: argparse.Namespace) -> list[BrowserSmokeStep]:
    output_dir = Path(args.output_dir)
    python = sys.executable
    steps = [
        BrowserSmokeStep(
            name="dashboard_auth_recovery",
            json_out=_json_path(output_dir, "dashboard-auth-recovery"),
            command=_add_mobile(
                [
                    python,
                    _script_path("dashboard_auth_browser_smoke.py"),
                    "--base-url",
                    args.base_url,
                    "--operator-token",
                    args.operator_token,
                    "--json-out",
                    str(_json_path(output_dir, "dashboard-auth-recovery")),
                    "--screenshot",
                    str(output_dir / "dashboard-auth-recovery.png"),
                    "--timeout-ms",
                    str(args.timeout_ms),
                ],
                mobile=args.mobile,
            ),
        ),
        BrowserSmokeStep(
            name="nav",
            json_out=_json_path(output_dir, "nav"),
            command=_add_mobile(
                [
                    python,
                    _script_path("nav_browser_smoke.py"),
                    "--base-url",
                    args.base_url,
                    "--operator-token",
                    args.operator_token,
                    "--click-nav",
                    "--json-out",
                    str(_json_path(output_dir, "nav")),
                    "--screenshot-dir",
                    str(output_dir / "nav-screens"),
                    "--timeout-ms",
                    str(args.timeout_ms),
                ],
                mobile=args.mobile,
            ),
        ),
        BrowserSmokeStep(
            name="supply_chain",
            json_out=_json_path(output_dir, "supply-chain"),
            command=_add_mobile(
                [
                    python,
                    _script_path("supply_chain_browser_smoke.py"),
                    "--url",
                    route_url(args.base_url, "/supply-chain"),
                    "--operator-token",
                    args.operator_token,
                    "--json-out",
                    str(_json_path(output_dir, "supply-chain")),
                    "--screenshot",
                    str(output_dir / "supply-chain.png"),
                    "--timeout-ms",
                    str(args.timeout_ms),
                ],
                mobile=args.mobile,
            ),
        ),
        BrowserSmokeStep(
            name="qr_path",
            json_out=_json_path(output_dir, "qr-path"),
            command=[
                python,
                _script_path("qr_path_browser_smoke.py"),
                "--base-url",
                args.base_url,
                "--api-url",
                args.api_url,
                "--operator-token",
                args.operator_token,
                "--json-out",
                str(_json_path(output_dir, "qr-path")),
                "--screenshot-dir",
                str(output_dir / "qr-path-screens"),
                "--timeout-ms",
                str(args.timeout_ms),
            ],
        ),
        BrowserSmokeStep(
            name="admin_routes",
            json_out=_json_path(output_dir, "admin-routes"),
            command=[
                python,
                _script_path("admin_routes_browser_smoke.py"),
                "--base-url",
                args.base_url,
                "--api-url",
                args.api_url,
                "--operator-token",
                args.operator_token,
                "--json-out",
                str(_json_path(output_dir, "admin-routes")),
                "--screenshot-dir",
                str(output_dir / "admin-routes-screens"),
                "--timeout-ms",
                str(args.timeout_ms),
            ],
        ),
        BrowserSmokeStep(
            name="product_detail",
            json_out=_json_path(output_dir, "product-detail"),
            command=_add_mobile(
                [
                    python,
                    _script_path("product_detail_browser_smoke.py"),
                    "--base-url",
                    args.base_url,
                    "--api-url",
                    args.api_url,
                    "--operator-token",
                    args.operator_token,
                    "--json-out",
                    str(_json_path(output_dir, "product-detail")),
                    "--screenshot-dir",
                    str(output_dir / "product-detail-screens"),
                    "--timeout-ms",
                    str(args.timeout_ms),
                ],
                mobile=args.mobile,
            ),
        ),
    ]

    if args.include_unavailable_check:
        steps.append(
            BrowserSmokeStep(
                name="consumer_verify_unavailable",
                json_out=_json_path(output_dir, "consumer-verify-unavailable"),
                command=[
                    python,
                    _script_path("consumer_verify_unavailable_browser_smoke.py"),
                    "--base-url",
                    args.base_url,
                    "--json-out",
                    str(_json_path(output_dir, "consumer-verify-unavailable")),
                    "--screenshot",
                    str(output_dir / "consumer-verify-unavailable.png"),
                    "--timeout-ms",
                    str(args.timeout_ms),
                ],
            )
        )
    return steps


def redact_command(command: list[str], *, operator_token: str) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for value in command:
        if skip_next:
            redacted.append("<redacted>")
            skip_next = False
            continue
        redacted.append(value)
        if value == "--operator-token":
            skip_next = True
    if operator_token:
        redacted = ["<redacted>" if value == operator_token else value for value in redacted]
    return redacted


def _tail(value: str, *, limit: int = 1200) -> str:
    value = value.strip()
    return value[-limit:] if len(value) > limit else value


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or not header.startswith(PNG_SIGNATURE) or header[12:16] != b"IHDR":
        return None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def _artifact_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def collect_screenshot_artifacts(payload: object) -> list[Path]:
    artifacts: list[Path] = []

    def walk(value: object, key: str = "") -> None:
        normalized_key = key.lower()
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                walk(child_value, str(child_key))
            return
        if isinstance(value, list):
            for item in value:
                walk(item, key)
            return
        if normalized_key == "screenshot":
            path = _artifact_path(value)
            if path is not None:
                artifacts.append(path)
            return
        if normalized_key in {"screenshotdir", "screenshot_dir"}:
            path = _artifact_path(value)
            if path is not None:
                if path.exists() and path.is_dir():
                    pngs = sorted(path.glob("*.png"))
                    artifacts.extend(pngs if pngs else [path / "*.png"])
                else:
                    artifacts.append(path)

    walk(payload)
    return _dedupe_paths(artifacts)


def validate_screenshot_artifacts(payload: object) -> dict[str, object]:
    artifact_reports: list[dict[str, object]] = []
    for path in collect_screenshot_artifacts(payload):
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        dimensions = _png_dimensions(path) if exists else None
        reason = ""
        if not exists:
            reason = "missing"
        elif path.is_dir():
            reason = "no PNG screenshots in directory"
        elif size_bytes < MIN_SCREENSHOT_BYTES:
            reason = f"too small: {size_bytes} bytes"
        elif dimensions is None:
            reason = "invalid PNG header"
        ok = exists and not path.is_dir() and size_bytes >= MIN_SCREENSHOT_BYTES and dimensions is not None
        artifact_reports.append(
            {
                "path": str(path),
                "ok": ok,
                "size_bytes": size_bytes,
                "width": dimensions[0] if dimensions is not None else None,
                "height": dimensions[1] if dimensions is not None else None,
                "reason": reason,
            }
        )

    failed = [report for report in artifact_reports if report["ok"] is not True]
    return {
        "screenshot_artifacts_total": len(artifact_reports),
        "screenshot_artifacts_passed": len(artifact_reports) - len(failed),
        "screenshot_artifacts_failed": len(failed),
        "failed_screenshot_artifacts": [str(report["path"]) for report in failed],
        "screenshot_artifacts": artifact_reports,
    }


def _openapi_url(api_url: str) -> str:
    return api_url.rstrip("/") + "/openapi.json"


def _frontend_api_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api"


def summarize_backend_openapi_contract(payload: dict[str, object]) -> dict[str, object]:
    paths = payload.get("paths")
    if not isinstance(paths, dict):
        return {
            "ok": False,
            "required_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
            "available_paths": [],
            "missing_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
            "detail": "openapi.json did not contain a paths object",
        }

    available_paths = sorted(str(path) for path in paths)
    missing_paths = [path for path in REQUIRED_BACKEND_OPENAPI_PATHS if path not in paths]
    return {
        "ok": not missing_paths,
        "required_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
        "available_paths": available_paths,
        "missing_paths": missing_paths,
        "detail": (
            "backend OpenAPI contract contains browser-smoke routes"
            if not missing_paths
            else "backend OpenAPI contract is missing browser-smoke routes; restart/rebuild the backend"
        ),
    }


def check_backend_contract(api_url: str, *, timeout_ms: int) -> dict[str, object]:
    url = _openapi_url(api_url)
    timeout_seconds = max(1, min(15, int(timeout_ms / 1000)))
    try:
        with request.urlopen(url, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        return {
            "name": "backend_contract",
            "ok": False,
            "url": url,
            "detail": f"openapi.json request failed with HTTP {exc.code}",
            "required_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
            "missing_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
        }
    except (OSError, TimeoutError) as exc:
        return {
            "name": "backend_contract",
            "ok": False,
            "url": url,
            "detail": f"openapi.json request failed: {exc}",
            "required_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
            "missing_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
        }

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "name": "backend_contract",
            "ok": False,
            "url": url,
            "detail": f"openapi.json was not valid JSON: {exc}",
            "required_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
            "missing_paths": list(REQUIRED_BACKEND_OPENAPI_PATHS),
        }

    summary = summarize_backend_openapi_contract(payload)
    summary["name"] = "backend_contract"
    summary["url"] = url
    return summary


def api_request(
    *,
    api_url: str,
    method: str,
    path: str,
    token: str,
    payload: dict[str, object] | None = None,
    timeout_seconds: int,
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
    with request.urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def summarize_backend_proxy_alignment(
    *,
    api_url: str,
    frontend_api_url: str,
    seeded_product: dict[str, object],
    proxy_product: dict[str, object] | None = None,
    proxy_error: str = "",
) -> dict[str, object]:
    product_id = str(seeded_product.get("id") or "")
    product_name = str(seeded_product.get("name") or "")
    summary = {
        "name": "backend_proxy_alignment",
        "api_url": api_url.rstrip("/"),
        "frontend_api_url": frontend_api_url.rstrip("/"),
        "product_id": product_id,
        "product_name": product_name,
    }
    if not product_id or not product_name:
        return {
            **summary,
            "ok": False,
            "detail": "api_url seed product response did not include an id and name",
        }
    if proxy_error:
        return {
            **summary,
            "ok": False,
            "detail": (
                "seeded product was not visible through frontend /api; "
                f"--api-url may target a different backend than the frontend proxy: {proxy_error}"
            ),
        }

    proxy_product = proxy_product or {}
    proxy_product_id = str(proxy_product.get("id") or "")
    proxy_product_name = str(proxy_product.get("name") or "")
    ok = proxy_product_id == product_id and proxy_product_name == product_name
    return {
        **summary,
        "ok": ok,
        "proxy_product_id": proxy_product_id,
        "proxy_product_name": proxy_product_name,
        "detail": (
            "backend API and frontend /api proxy share seeded product state"
            if ok
            else "frontend /api returned a different product than the one seeded through --api-url"
        ),
    }


def check_backend_proxy_alignment(
    *, base_url: str, api_url: str, operator_token: str, timeout_ms: int
) -> dict[str, object]:
    timeout_seconds = max(1, min(15, int(timeout_ms / 1000)))
    frontend_api_url = _frontend_api_url(base_url)
    owner_id = "browser-smoke-precheck"
    payload = {
        "name": f"Browser Smoke Proxy Precheck {uuid.uuid4().hex[:8]}",
        "description": "Precheck product used to verify that --api-url matches the frontend /api proxy state.",
        "category": "Precheck",
        "origin": "Browser Smoke Suite",
        "requires_cold_chain": False,
    }
    seed_path = f"/products/?owner_id={parse.quote(owner_id)}"
    try:
        seeded_product = api_request(
            api_url=api_url,
            method="POST",
            path=seed_path,
            token=operator_token,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "name": "backend_proxy_alignment",
            "ok": False,
            "api_url": api_url.rstrip("/"),
            "frontend_api_url": frontend_api_url.rstrip("/"),
            "detail": f"api_url seed request failed with HTTP {exc.code}: {detail}",
        }
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "name": "backend_proxy_alignment",
            "ok": False,
            "api_url": api_url.rstrip("/"),
            "frontend_api_url": frontend_api_url.rstrip("/"),
            "detail": f"api_url seed request failed: {exc}",
        }

    product_id = str(seeded_product.get("id") or "")
    proxy_product: dict[str, object] | None = None
    proxy_error = ""
    if product_id:
        try:
            proxy_product = api_request(
                api_url=frontend_api_url,
                method="GET",
                path=f"/products/{parse.quote(product_id)}",
                token=operator_token,
                timeout_seconds=timeout_seconds,
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            proxy_error = f"HTTP {exc.code}: {detail}"
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            proxy_error = str(exc)

    return summarize_backend_proxy_alignment(
        api_url=api_url,
        frontend_api_url=frontend_api_url,
        seeded_product=seeded_product,
        proxy_product=proxy_product,
        proxy_error=proxy_error,
    )


def summarize_child_report(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "report_found": False,
            "checks_total": 0,
            "checks_passed": 0,
            "checks_failed": 0,
            "failed_check_names": [],
            **validate_screenshot_artifacts({}),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifact_summary = validate_screenshot_artifacts(payload)
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {
            "report_found": True,
            "checks_total": 0,
            "checks_passed": 0,
            "checks_failed": 0,
            "failed_check_names": [],
            **artifact_summary,
        }
    checks_passed = sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is True)
    checks_total = len(checks)
    failed_check_names = [
        str(check.get("name") or f"check_{index}")
        for index, check in enumerate(checks, start=1)
        if isinstance(check, dict) and check.get("ok") is not True
    ]
    return {
        "report_found": True,
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "checks_failed": checks_total - checks_passed,
        "failed_check_names": failed_check_names,
        **artifact_summary,
    }


def run_step(step: BrowserSmokeStep, *, operator_token: str, timeout_ms: int, dry_run: bool) -> dict[str, object]:
    if dry_run:
        return {
            "name": step.name,
            "ok": True,
            "dry_run": True,
            "command": redact_command(step.command, operator_token=operator_token),
            "json_out": str(step.json_out),
        }
    completed = subprocess.run(
        step.command,
        capture_output=True,
        text=True,
        timeout=max(30, int(timeout_ms / 1000) + 30),
        check=False,
    )
    child_summary = summarize_child_report(step.json_out)
    return {
        "name": step.name,
        "ok": completed.returncode == 0
        and child_summary.get("checks_failed") == 0
        and child_summary.get("screenshot_artifacts_failed") == 0,
        "dry_run": False,
        "command": redact_command(step.command, operator_token=operator_token),
        "json_out": str(step.json_out),
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        **child_summary,
    }


def write_json(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_precheck_failure_report(args: argparse.Namespace, prechecks: list[dict[str, object]]) -> dict[str, object]:
    failed_precheck_names = [
        str(precheck.get("name") or f"precheck_{index}")
        for index, precheck in enumerate(prechecks, start=1)
        if precheck.get("ok") is not True
    ]
    prechecks_passed = len(prechecks) - len(failed_precheck_names)
    return {
        "status": "fail",
        "base_url": args.base_url,
        "api_url": args.api_url,
        "mobile": args.mobile,
        "include_unavailable_check": args.include_unavailable_check,
        "dry_run": args.dry_run,
        "skip_backend_contract_check": args.skip_backend_contract_check,
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "failed_step_names": [],
            "checks_total": 0,
            "checks_passed": 0,
            "checks_failed": 0,
            "failed_check_names": [],
            "prechecks_total": len(prechecks),
            "prechecks_passed": prechecks_passed,
            "prechecks_failed": len(failed_precheck_names),
            "failed_precheck_names": failed_precheck_names,
        },
        "prechecks": prechecks,
        "results": [],
    }


def main() -> int:
    args = parse_args()
    steps = build_steps(args)
    prechecks: list[dict[str, object]] = []

    if not args.dry_run and not args.skip_backend_contract_check:
        backend_contract = check_backend_contract(args.api_url, timeout_ms=args.timeout_ms)
        prechecks.append(backend_contract)
        if backend_contract.get("ok") is not True:
            report = build_precheck_failure_report(args, prechecks)
            write_json(args.json_out, report)
            print(json.dumps(report["summary"], indent=2, sort_keys=True))
            return 1

        backend_proxy_alignment = check_backend_proxy_alignment(
            base_url=args.base_url,
            api_url=args.api_url,
            operator_token=args.operator_token,
            timeout_ms=args.timeout_ms,
        )
        prechecks.append(backend_proxy_alignment)
        if backend_proxy_alignment.get("ok") is not True:
            report = build_precheck_failure_report(args, prechecks)
            write_json(args.json_out, report)
            print(json.dumps(report["summary"], indent=2, sort_keys=True))
            return 1

    results = [
        run_step(step, operator_token=args.operator_token, timeout_ms=args.timeout_ms, dry_run=args.dry_run)
        for step in steps
    ]
    passed = sum(1 for result in results if result.get("ok") is True)
    failed = len(results) - passed
    prechecks_passed = sum(1 for precheck in prechecks if precheck.get("ok") is True)
    prechecks_failed = len(prechecks) - prechecks_passed
    failed_step_names = [str(result.get("name")) for result in results if result.get("ok") is not True]
    failed_check_names = [
        f"{result.get('name')}:{check_name}"
        for result in results
        for check_name in result.get("failed_check_names", [])
        if isinstance(check_name, str)
    ]
    failed_screenshot_artifacts = [
        f"{result.get('name')}:{artifact}"
        for result in results
        for artifact in result.get("failed_screenshot_artifacts", [])
        if isinstance(artifact, str)
    ]
    failed_precheck_names = [
        str(precheck.get("name") or f"precheck_{index}")
        for index, precheck in enumerate(prechecks, start=1)
        if precheck.get("ok") is not True
    ]
    report = {
        "status": "pass" if failed == 0 and prechecks_failed == 0 else "fail",
        "base_url": args.base_url,
        "api_url": args.api_url,
        "mobile": args.mobile,
        "include_unavailable_check": args.include_unavailable_check,
        "dry_run": args.dry_run,
        "skip_backend_contract_check": args.skip_backend_contract_check,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "failed_step_names": failed_step_names,
            "checks_total": sum(int(result.get("checks_total", 0)) for result in results),
            "checks_passed": sum(int(result.get("checks_passed", 0)) for result in results),
            "checks_failed": sum(int(result.get("checks_failed", 0)) for result in results),
            "failed_check_names": failed_check_names,
            "screenshot_artifacts_total": sum(
                int(result.get("screenshot_artifacts_total", 0)) for result in results
            ),
            "screenshot_artifacts_passed": sum(
                int(result.get("screenshot_artifacts_passed", 0)) for result in results
            ),
            "screenshot_artifacts_failed": sum(
                int(result.get("screenshot_artifacts_failed", 0)) for result in results
            ),
            "failed_screenshot_artifacts": failed_screenshot_artifacts,
            "prechecks_total": len(prechecks),
            "prechecks_passed": prechecks_passed,
            "prechecks_failed": prechecks_failed,
            "failed_precheck_names": failed_precheck_names,
        },
        "prechecks": prechecks,
        "results": results,
    }
    write_json(args.json_out, report)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
