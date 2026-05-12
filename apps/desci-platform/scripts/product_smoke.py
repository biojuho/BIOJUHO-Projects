#!/usr/bin/env python3
"""Product smoke checks for DSCI-DecentBio.

The script uses only the Python standard library so it can run from a clean
operator machine after frontend/backend services are started.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class SmokeResponse:
    name: str
    url: str
    status: int
    elapsed_ms: float
    headers: dict[str, str]
    body: str
    data: dict[str, Any] | None


def _url(base_url: str, path: str = "") -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}" if path else base_url.rstrip("/")


def fetch(name: str, url: str, timeout: float) -> SmokeResponse:
    started_at = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "dsci-product-smoke/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
        headers = {key.lower(): value for key, value in exc.headers.items()}
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    try:
        data = json.loads(body) if body else None
    except json.JSONDecodeError:
        data = None

    return SmokeResponse(
        name=name,
        url=url,
        status=status,
        elapsed_ms=elapsed_ms,
        headers=headers,
        body=body,
        data=data if isinstance(data, dict) else None,
    )


def assert_ok(response: SmokeResponse, failures: list[str]) -> None:
    if response.status != 200:
        failures.append(f"{response.name}: expected 200, got {response.status} ({response.url})")


def assert_api_headers(response: SmokeResponse, failures: list[str]) -> None:
    if not response.headers.get("x-request-id"):
        failures.append(f"{response.name}: missing X-Request-ID")
    if response.headers.get("x-content-type-options") != "nosniff":
        failures.append(f"{response.name}: missing X-Content-Type-Options=nosniff")


def assert_health(response: SmokeResponse, failures: list[str]) -> None:
    if not response.data:
        failures.append("health: response is not JSON")
        return
    for key in ("status", "vector_store_backend", "chromadb_ok", "llm_available"):
        if key not in response.data:
            failures.append(f"health: missing key {key}")


def assert_readiness(response: SmokeResponse, failures: list[str], *, strict_ready: bool) -> None:
    if not response.data:
        failures.append("ready: response is not JSON")
        return
    if response.data.get("status") not in {"ready", "degraded", "blocked"}:
        failures.append(f"ready: unexpected status {response.data.get('status')!r}")
    if not isinstance(response.data.get("checks"), list):
        failures.append("ready: checks must be a list")
    if strict_ready and response.data.get("status") == "blocked":
        blockers = ", ".join(response.data.get("launch_blockers") or [])
        failures.append(f"ready: launch is blocked ({blockers or 'unknown blockers'})")


def print_result(response: SmokeResponse) -> None:
    suffix = ""
    if response.name == "ready" and response.data:
        suffix = f" status={response.data.get('status')}"
    elif response.name == "health" and response.data:
        suffix = f" status={response.data.get('status')}"
    print(f"[smoke] {response.name:<10} {response.status} {response.elapsed_ms:7.1f}ms{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product smoke checks against DSCI-DecentBio.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="BioLinker API base URL")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173", help="Frontend base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=1, help="Retries per check after transient request failures")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend URL check")
    parser.add_argument("--strict-ready", action="store_true", help="Fail when /ready status is blocked")
    args = parser.parse_args()

    failures: list[str] = []
    checks = [
        ("api", _url(args.api, "/")),
        ("health", _url(args.api, "/health")),
        ("ready", _url(args.api, "/ready")),
    ]
    if not args.skip_frontend:
        checks.append(("frontend", _url(args.frontend, "/")))

    for name, url in checks:
        response = None
        last_error: Exception | None = None
        for attempt in range(max(args.retries, 0) + 1):
            try:
                response = fetch(name, url, args.timeout)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < max(args.retries, 0):
                    time.sleep(0.5 * (attempt + 1))

        if response is None:
            failures.append(f"{name}: request failed ({url}): {last_error}")
            print(f"[smoke] {name:<10} ERROR   {last_error}")
            continue

        print_result(response)
        assert_ok(response, failures)

        if name in {"api", "health", "ready"}:
            assert_api_headers(response, failures)
        if name == "health":
            assert_health(response, failures)
        if name == "ready":
            assert_readiness(response, failures, strict_ready=args.strict_ready)

    if failures:
        print("\n[smoke] FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[smoke] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
