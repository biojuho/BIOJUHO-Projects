#!/usr/bin/env python3
"""Product smoke checks for DSCI-DecentBio.

The script uses only the Python standard library so it can run from a clean
operator machine after frontend/backend services are started.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_io import write_json_atomic

SECRET_SHAPED_PATTERNS = (
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"\brk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]+"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b0x[0-9a-fA-F]{40}\b"),
    re.compile(r"https?://\S+"),
)

WEB3_CONTRACT_ENV_KEYS = (
    "DSCI_CONTRACT_ADDRESS",
    "NFT_CONTRACT_ADDRESS",
    "DESCI_DAO_CONTRACT_ADDRESS",
)


@dataclass
class SmokeResponse:
    name: str
    url: str
    status: int
    elapsed_ms: float
    headers: dict[str, str]
    body: str
    data: dict[str, Any] | None


def _print_progress(message: str = "") -> None:
    print(message, flush=True)


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


def assert_api_root(response: SmokeResponse, failures: list[str]) -> None:
    if not response.data:
        failures.append("api: response is not JSON")
        return
    if response.data.get("service") != "DSCI-DecentBio":
        failures.append(f"api: unexpected service {response.data.get('service')!r}")


def assert_readiness(response: SmokeResponse, failures: list[str], *, strict_ready: bool) -> None:
    if not response.data:
        failures.append("ready: response is not JSON")
        return
    if response.data.get("status") not in {"ready", "degraded", "blocked"}:
        failures.append(f"ready: unexpected status {response.data.get('status')!r}")
    if not isinstance(response.data.get("checks"), list):
        failures.append("ready: checks must be a list")
    _assert_ready_web3_details(response.data, failures)
    if strict_ready and response.data.get("status") == "blocked":
        blockers = ", ".join(response.data.get("launch_blockers") or [])
        failures.append(f"ready: launch is blocked ({blockers or 'unknown blockers'})")


def _assert_ready_web3_details(data: dict[str, Any], failures: list[str]) -> None:
    web3_check = _ready_web3_check(data)
    if web3_check is None:
        return
    details = web3_check.get("details")
    if not isinstance(details, dict):
        failures.append("ready: web3 details must be an object")
        return

    for field in ("rpc_configured", "rpc_public_https", "mock_mode_enabled", "mock_mode_allowed"):
        if not isinstance(details.get(field), bool):
            failures.append(f"ready: web3 details.{field} must be a boolean")
    contract_count = details.get("contract_count")
    if not isinstance(contract_count, int) or contract_count < 0:
        failures.append("ready: web3 details.contract_count must be a non-negative integer")
    contracts = details.get("contracts")
    if not isinstance(contracts, dict) or not all(isinstance(value, bool) for value in contracts.values()):
        failures.append("ready: web3 details.contracts must map env keys to booleans")


def _ready_web3_check(data: dict[str, Any]) -> dict[str, Any] | None:
    checks = data.get("checks")
    if not isinstance(checks, list):
        return None
    return next((check for check in checks if isinstance(check, dict) and check.get("id") == "web3"), None)


def _ready_web3_details_report(details: Any) -> dict[str, Any] | None:
    if not isinstance(details, dict):
        return None
    contracts = details.get("contracts")
    if not isinstance(contracts, dict) or not all(isinstance(value, bool) for value in contracts.values()):
        return None
    report: dict[str, Any] = {}
    for field in ("rpc_configured", "rpc_public_https", "mock_mode_enabled", "mock_mode_allowed"):
        value = details.get(field)
        if isinstance(value, bool):
            report[field] = value
    contract_count = details.get("contract_count")
    if isinstance(contract_count, int) and contract_count >= 0:
        report["contract_count"] = contract_count
    report["contracts"] = {key: value for key, value in contracts.items() if isinstance(key, str)}
    return report


def ready_web3_response_report(data: dict[str, Any]) -> dict[str, Any] | None:
    web3_check = _ready_web3_check(data)
    if web3_check is None:
        return None
    report: dict[str, Any] = {}
    status = web3_check.get("status")
    if isinstance(status, str):
        report["status"] = status
    for field in ("required", "configured", "available"):
        value = web3_check.get(field)
        if isinstance(value, bool):
            report[field] = value
    details = _ready_web3_details_report(web3_check.get("details"))
    if details is not None:
        report["details"] = details
    return report


def assert_launch(response: SmokeResponse, failures: list[str], *, strict_ready: bool) -> None:
    if not response.data:
        failures.append("launch: response is not JSON")
        return

    _assert_launch_identity(response, failures)
    _assert_launch_decision(response, failures)
    _assert_launch_phase(response, failures)
    _assert_launch_readiness_status(response, failures)
    _assert_launch_score(response, failures)
    _assert_launch_summary(response, failures)
    _assert_launch_lists(response, failures)
    _assert_launch_consistency(response, failures)
    _assert_launch_strict(response, failures, strict_ready=strict_ready)


def _assert_launch_identity(response: SmokeResponse, failures: list[str]) -> None:
    product = response.data.get("product")
    if product != "DSCI-DecentBio":
        failures.append(f"launch: unexpected product {product!r}")


def _assert_launch_decision(response: SmokeResponse, failures: list[str]) -> None:
    decision = response.data.get("release_decision")
    if decision not in {"go", "go-with-watch", "no-go"}:
        failures.append(f"launch: unexpected release_decision {decision!r}")


def _assert_launch_phase(response: SmokeResponse, failures: list[str]) -> None:
    phase = response.data.get("operator_phase")
    if phase not in {"launch-ready", "operator-review", "blocked"}:
        failures.append(f"launch: unexpected operator_phase {phase!r}")


def _assert_launch_readiness_status(response: SmokeResponse, failures: list[str]) -> None:
    readiness_status = response.data.get("readiness_status")
    if readiness_status not in {"ready", "degraded", "blocked"}:
        failures.append(f"launch: unexpected readiness_status {readiness_status!r}")


def _assert_launch_score(response: SmokeResponse, failures: list[str]) -> None:
    score = response.data.get("score") or {}
    for key in ("overall_percent", "required_percent"):
        value = score.get(key)
        if not isinstance(value, int) or not 0 <= value <= 100:
            failures.append(f"launch: score.{key} must be an integer from 0 to 100")


def _assert_launch_summary(response: SmokeResponse, failures: list[str]) -> None:
    summary = response.data.get("summary")
    if not isinstance(summary, dict):
        failures.append("launch: summary must be an object")
        return

    required_fields = (
        "ready_count",
        "total",
        "required_ready_count",
        "required_total",
        "blocker_count",
        "warning_count",
    )
    for field in required_fields:
        value = summary.get(field)
        if not isinstance(value, int) or value < 0:
            failures.append(f"launch: summary.{field} must be a non-negative integer")

    ready_count = summary.get("ready_count")
    total = summary.get("total")
    required_ready_count = summary.get("required_ready_count")
    required_total = summary.get("required_total")
    if isinstance(total, int) and total <= 0:
        failures.append("launch: summary.total must be greater than zero")
    if isinstance(ready_count, int) and isinstance(total, int) and ready_count > total:
        failures.append("launch: summary.ready_count cannot exceed summary.total")
    if isinstance(required_ready_count, int) and isinstance(required_total, int) and required_ready_count > required_total:
        failures.append("launch: summary.required_ready_count cannot exceed summary.required_total")


def _assert_launch_lists(response: SmokeResponse, failures: list[str]) -> None:
    if not isinstance(response.data.get("launch_blockers"), list):
        failures.append("launch: launch_blockers must be a list")
    next_actions = response.data.get("next_actions")
    if not isinstance(next_actions, list):
        failures.append("launch: next_actions must be a list")
        return
    _assert_launch_next_actions(next_actions, failures)


def _assert_launch_next_actions(next_actions: list[Any], failures: list[str]) -> None:
    for index, action in enumerate(next_actions):
        prefix = f"launch: next_actions[{index}]"
        if not isinstance(action, dict):
            failures.append(f"{prefix} must be an object")
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            failures.append(f"{prefix}.id must be a non-empty string")
        required = action.get("required")
        if not isinstance(required, bool):
            failures.append(f"{prefix}.required must be a boolean")
        status = action.get("status")
        if status not in {"fail", "warn"}:
            failures.append(f"{prefix}.status must be fail or warn")
        remediation = action.get("remediation")
        if not isinstance(remediation, str) or not remediation.strip():
            failures.append(f"{prefix}.remediation must be a non-empty string")
        elif _contains_secret_shaped_value(remediation):
            failures.append(f"{prefix}.remediation must not contain raw URLs, addresses, or secret-shaped values")
        required_env = action.get("required_env")
        if not isinstance(required_env, list) or not all(isinstance(item, str) and item.strip() for item in required_env):
            failures.append(f"{prefix}.required_env must be a list of non-empty strings")
        elif any(_contains_secret_shaped_value(item) for item in required_env):
            failures.append(f"{prefix}.required_env must not contain raw URLs, addresses, or secret-shaped values")


def _contains_secret_shaped_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_SHAPED_PATTERNS)


def _assert_launch_consistency(response: SmokeResponse, failures: list[str]) -> None:
    summary = response.data.get("summary")
    score = response.data.get("score") or {}
    launch_blockers = response.data.get("launch_blockers")
    next_actions = response.data.get("next_actions")
    if not isinstance(summary, dict) or not isinstance(launch_blockers, list) or not isinstance(next_actions, list):
        return

    blocker_count = summary.get("blocker_count")
    warning_count = summary.get("warning_count")
    if isinstance(blocker_count, int) and blocker_count != len(launch_blockers):
        failures.append("launch: summary.blocker_count must match launch_blockers length")
    if isinstance(blocker_count, int) and isinstance(warning_count, int):
        expected_actions = blocker_count + warning_count
        if len(next_actions) != expected_actions:
            failures.append("launch: next_actions length must match blocker_count + warning_count")

    _assert_launch_decision_consistency(response, failures)
    _assert_launch_score_consistency(summary, score, failures)


def _assert_launch_decision_consistency(response: SmokeResponse, failures: list[str]) -> None:
    decision = response.data.get("release_decision")
    phase = response.data.get("operator_phase")
    readiness_status = response.data.get("readiness_status")
    summary = response.data.get("summary") or {}
    blocker_count = summary.get("blocker_count")
    warning_count = summary.get("warning_count")

    if decision == "go":
        if phase != "launch-ready" or readiness_status != "ready":
            failures.append("launch: go decision must use launch-ready phase and ready status")
        if blocker_count or warning_count:
            failures.append("launch: go decision cannot include blockers or warnings")
    if decision == "go-with-watch":
        if phase != "operator-review" or readiness_status == "blocked":
            failures.append("launch: go-with-watch decision must use operator-review phase without blocked readiness")
        if blocker_count:
            failures.append("launch: go-with-watch decision cannot include required blockers")
    if decision == "no-go":
        if phase != "blocked" or readiness_status != "blocked":
            failures.append("launch: no-go decision must use blocked phase and blocked readiness")
        if not blocker_count:
            failures.append("launch: no-go decision must include at least one required blocker")


def _assert_launch_score_consistency(summary: dict[str, Any], score: dict[str, Any], failures: list[str]) -> None:
    total = summary.get("total")
    ready_count = summary.get("ready_count")
    required_total = summary.get("required_total")
    required_ready_count = summary.get("required_ready_count")
    if isinstance(ready_count, int) and isinstance(total, int) and total > 0:
        expected_overall = round((ready_count / total) * 100)
        if score.get("overall_percent") != expected_overall:
            failures.append("launch: score.overall_percent must match summary ready_count/total")
    if isinstance(required_ready_count, int) and isinstance(required_total, int) and required_total > 0:
        expected_required = round((required_ready_count / required_total) * 100)
        if score.get("required_percent") != expected_required:
            failures.append("launch: score.required_percent must match summary required_ready_count/required_total")


def _assert_launch_strict(response: SmokeResponse, failures: list[str], *, strict_ready: bool) -> None:
    decision = response.data.get("release_decision")
    if strict_ready and decision == "no-go":
        blockers = ", ".join(response.data.get("launch_blockers") or [])
        failures.append(f"launch: release decision is no-go ({blockers or 'unknown blockers'})")


def print_result(response: SmokeResponse) -> None:
    suffix = ""
    if response.name == "ready" and response.data or response.name == "health" and response.data:
        suffix = f" status={response.data.get('status')}"
    if response.name == "launch" and response.data:
        suffix = f" decision={response.data.get('release_decision')}"
    _print_progress(f"[smoke] {response.name:<10} {response.status} {response.elapsed_ms:7.1f}ms{suffix}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run product smoke checks against DSCI-DecentBio.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="DSCI-DecentBio API base URL")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173", help="Frontend base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=1, help="Retries per check after transient request failures")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend URL check")
    parser.add_argument("--strict-ready", action="store_true", help="Fail when /ready status is blocked")
    parser.add_argument("--json-out", help="Optional JSON evidence output file")
    return parser.parse_args(argv)

def build_checks(args: argparse.Namespace) -> list[tuple[str, str]]:
    checks = [
        ("api", _url(args.api, "/")),
        ("health", _url(args.api, "/health")),
        ("ready", _url(args.api, "/ready")),
        ("launch", _url(args.api, "/launch")),
    ]
    if not args.skip_frontend:
        checks.append(("frontend", _url(args.frontend, "/")))
    return checks


def fetch_with_retries(name: str, url: str, args: argparse.Namespace) -> tuple[SmokeResponse | None, Exception | None]:
    last_error: Exception | None = None
    for attempt in range(max(args.retries, 0) + 1):
        try:
            return fetch(name, url, args.timeout), None
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max(args.retries, 0):
                time.sleep(0.5 * (attempt + 1))
    return None, last_error


def response_report(response: SmokeResponse) -> dict[str, Any]:
    report: dict[str, Any] = {
        "name": response.name,
        "url": response.url,
        "status": response.status,
        "elapsed_ms": round(response.elapsed_ms, 1),
    }
    if response.name == "api" and response.data:
        report["service"] = response.data.get("service")
    if response.name in {"health", "ready"} and response.data:
        report["runtime_status"] = response.data.get("status")
    if response.name == "ready" and response.data:
        web3 = ready_web3_response_report(response.data)
        if web3 is not None:
            report["web3"] = web3
    if response.name == "launch" and response.data:
        report["release_decision"] = response.data.get("release_decision")
        report["operator_phase"] = response.data.get("operator_phase")
        report["readiness_status"] = response.data.get("readiness_status")
        report["summary"] = response.data.get("summary")
        report["score"] = response.data.get("score")
        report["launch_blockers"] = response.data.get("launch_blockers") or []
        report["next_actions"] = response.data.get("next_actions") or []
    return report


def launch_handoff_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    launch_report = next((report for report in reports if report.get("name") == "launch"), None)
    if launch_report is None:
        return None
    return {
        "ok": launch_report.get("ok") is True,
        "release_decision": launch_report.get("release_decision"),
        "operator_phase": launch_report.get("operator_phase"),
        "readiness_status": launch_report.get("readiness_status"),
        "summary": launch_report.get("summary") if isinstance(launch_report.get("summary"), dict) else {},
        "score": launch_report.get("score") if isinstance(launch_report.get("score"), dict) else {},
        "launch_blockers": launch_report.get("launch_blockers") if isinstance(launch_report.get("launch_blockers"), list) else [],
        "next_actions": launch_report.get("next_actions") if isinstance(launch_report.get("next_actions"), list) else [],
        "failures": launch_report.get("failures") if isinstance(launch_report.get("failures"), list) else [],
    }


def ready_web3_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    ready_report = next((report for report in reports if report.get("name") == "ready"), None)
    if ready_report is None:
        return None
    web3 = ready_report.get("web3")
    if not isinstance(web3, dict):
        return None
    details = web3.get("details")
    return {
        "ok": ready_report.get("ok") is True,
        "status": web3.get("status"),
        "required": web3.get("required"),
        "configured": web3.get("configured"),
        "available": web3.get("available"),
        "details": details if isinstance(details, dict) else {},
        "failures": ready_report.get("failures") if isinstance(ready_report.get("failures"), list) else [],
    }


def ready_launch_action_coverage_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    launch_report = next((report for report in reports if report.get("name") == "launch"), None)
    if launch_report is None:
        return None
    coverage = launch_report.get("ready_launch_action_coverage")
    return coverage if isinstance(coverage, dict) else None


def collect_checks(args: argparse.Namespace) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    reports: list[dict[str, Any]] = []
    responses_by_name: dict[str, SmokeResponse] = {}

    for name, url in build_checks(args):
        response, last_error = fetch_with_retries(name, url, args)
        if response is None:
            failure = f"{name}: request failed ({url}): {last_error}"
            failures.append(failure)
            reports.append(
                {
                    "name": name,
                    "url": url,
                    "ok": False,
                    "error": str(last_error),
                    "failures": [failure],
                }
            )
            _print_progress(f"[smoke] {name:<10} ERROR   {last_error}")
            continue

        before_count = len(failures)
        print_result(response)
        responses_by_name[name] = response
        validate_response(response, failures, strict_ready=args.strict_ready)
        report = response_report(response)
        check_failures = failures[before_count:]
        report["ok"] = not check_failures
        report["failures"] = check_failures
        reports.append(report)

    assert_ready_launch_consistency(responses_by_name, failures, reports)
    return failures, reports


def assert_ready_launch_consistency(
    responses_by_name: dict[str, SmokeResponse],
    failures: list[str],
    reports: list[dict[str, Any]],
) -> None:
    ready = responses_by_name.get("ready")
    launch = responses_by_name.get("launch")
    if not ready or not launch or not ready.data or not launch.data:
        return

    ready_failures: list[str] = []
    coverage = ready_launch_action_coverage(ready.data, launch.data)
    _assert_ready_launch_status_consistency(ready.data, launch.data, ready_failures)
    _assert_ready_launch_summary_consistency(ready.data, launch.data, ready_failures)
    _assert_ready_launch_blocker_consistency(ready.data, launch.data, ready_failures)
    _assert_ready_launch_action_consistency(coverage, ready_failures)

    launch_report = next((report for report in reports if report.get("name") == "launch"), None)
    if launch_report is not None and coverage is not None:
        launch_report["ready_launch_action_coverage"] = coverage

    if not ready_failures:
        return

    failures.extend(ready_failures)
    if launch_report is not None:
        launch_report["ok"] = False
        launch_report.setdefault("failures", []).extend(ready_failures)


def _assert_ready_launch_status_consistency(ready_data: dict[str, Any], launch_data: dict[str, Any], failures: list[str]) -> None:
    if ready_data.get("status") != launch_data.get("readiness_status"):
        failures.append("launch: readiness_status must match /ready status")


def _assert_ready_launch_summary_consistency(ready_data: dict[str, Any], launch_data: dict[str, Any], failures: list[str]) -> None:
    ready_summary = ready_data.get("summary")
    launch_summary = launch_data.get("summary")
    if not isinstance(ready_summary, dict) or not isinstance(launch_summary, dict):
        return

    for field in ("ready_count", "total", "required_ready_count", "required_total"):
        if ready_summary.get(field) != launch_summary.get(field):
            failures.append(f"launch: summary.{field} must match /ready summary")


def _assert_ready_launch_blocker_consistency(ready_data: dict[str, Any], launch_data: dict[str, Any], failures: list[str]) -> None:
    ready_blockers = ready_data.get("launch_blockers")
    launch_blockers = launch_data.get("launch_blockers")
    if not isinstance(ready_blockers, list) or not isinstance(launch_blockers, list):
        return
    if ready_blockers != launch_blockers:
        failures.append("launch: launch_blockers must match /ready launch_blockers")


def _assert_ready_launch_action_consistency(coverage: dict[str, Any] | None, failures: list[str]) -> None:
    if coverage is None:
        return
    if coverage.get("action_ids_match") is not True:
        failures.append("launch: next_action_ids must match /ready failed/warning checks")
    if coverage.get("required_env_match") is not True:
        failures.append("launch: next_action_required_env must match /ready failed/warning check required_env")


def ready_launch_action_coverage(ready_data: dict[str, Any], launch_data: dict[str, Any]) -> dict[str, Any] | None:
    ready_checks = ready_data.get("checks")
    launch_actions = launch_data.get("next_actions")
    if not isinstance(ready_checks, list) or not isinstance(launch_actions, list):
        return None

    expected_actions = [
        check
        for check in ready_checks
        if isinstance(check, dict)
        and (check.get("status") == "warn" or (check.get("required") is True and check.get("status") == "fail"))
    ]
    expected_action_ids, expected_required_env = _launch_action_coverage(expected_actions, derive_ready_web3=True)
    actual_action_ids, actual_required_env = _launch_action_coverage(launch_actions)
    action_ids_match = set(expected_action_ids) == set(actual_action_ids)
    required_env_match = set(expected_required_env) == set(actual_required_env)

    return {
        "status": "match" if action_ids_match and required_env_match else "drift",
        "action_ids_match": action_ids_match,
        "required_env_match": required_env_match,
        "ready_action_ids": expected_action_ids,
        "launch_action_ids": actual_action_ids,
        "shared_action_ids": _ordered_intersection(expected_action_ids, actual_action_ids),
        "ready_only_action_ids": _ordered_difference(expected_action_ids, actual_action_ids),
        "launch_only_action_ids": _ordered_difference(actual_action_ids, expected_action_ids),
        "ready_required_env": expected_required_env,
        "launch_required_env": actual_required_env,
        "shared_required_env": _ordered_intersection(expected_required_env, actual_required_env),
        "ready_only_required_env": _ordered_difference(expected_required_env, actual_required_env),
        "launch_only_required_env": _ordered_difference(actual_required_env, expected_required_env),
    }


def _launch_action_coverage(actions: list[Any], *, derive_ready_web3: bool = False) -> tuple[list[str], list[str]]:
    action_ids: list[str] = []
    required_env: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id.strip():
            action_ids.append(action_id.strip())
        if derive_ready_web3 and action_id == "web3":
            required_env.extend(_ready_web3_launch_required_env(action))
            continue
        env_values = action.get("required_env")
        if isinstance(env_values, list):
            required_env.extend(item.strip() for item in env_values if isinstance(item, str) and item.strip())
    return _unique_strings(action_ids), _unique_strings(required_env)


def _ready_web3_launch_required_env(check: dict[str, Any]) -> list[str]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    contracts = details.get("contracts") if isinstance(details.get("contracts"), dict) else {}
    required_env: list[str] = []

    if details.get("mock_mode_enabled") is True and details.get("mock_mode_allowed") is False:
        required_env.append("MOCK_MODE")

    if details.get("rpc_configured") is not True:
        required_env.append("WEB3_RPC_URL")
    elif details.get("rpc_public_https") is not True:
        required_env.append("WEB3_RPC_URL")

    required_env.extend(key for key in WEB3_CONTRACT_ENV_KEYS if contracts.get(key) is not True)
    if required_env:
        return _unique_strings(required_env)

    fallback_env = check.get("required_env")
    return [item.strip() for item in fallback_env if isinstance(item, str) and item.strip()] if isinstance(fallback_env, list) else []


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _ordered_intersection(left: list[str], right: list[str]) -> list[str]:
    right_values = set(right)
    return [value for value in left if value in right_values]


def _ordered_difference(left: list[str], right: list[str]) -> list[str]:
    right_values = set(right)
    return [value for value in left if value not in right_values]


def validate_response(response: SmokeResponse, failures: list[str], *, strict_ready: bool) -> None:
    assert_ok(response, failures)

    if response.name in {"api", "health", "ready", "launch"}:
        assert_api_headers(response, failures)
    if response.name == "api":
        assert_api_root(response, failures)
    if response.name == "health":
        assert_health(response, failures)
    if response.name == "ready":
        assert_readiness(response, failures, strict_ready=strict_ready)
    if response.name == "launch":
        assert_launch(response, failures, strict_ready=strict_ready)


def run_checks(args: argparse.Namespace) -> list[str]:
    failures, _reports = collect_checks(args)
    return failures


def write_json_report(path: str | Path, *, failures: list[str], reports: list[dict[str, Any]], args: argparse.Namespace) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failures,
        "api": args.api,
        "frontend": args.frontend,
        "skip_frontend": bool(args.skip_frontend),
        "timeout_seconds": args.timeout,
        "retries": args.retries,
        "summary": {
            "total": len(reports),
            "passed": sum(1 for report in reports if report.get("ok") is True),
            "failed": sum(1 for report in reports if report.get("ok") is False),
            "strict_ready": bool(args.strict_ready),
        },
        "launch_handoff": launch_handoff_report(reports),
        "ready_web3": ready_web3_report(reports),
        "ready_launch_action_coverage": ready_launch_action_coverage_report(reports),
        "failures": failures,
        "checks": reports,
    }
    write_json_atomic(output_path, payload, trailing_newline=True)
    _print_progress(f"[smoke] json written: {output_path}")


def _launch_next_action_lines(reports: list[dict[str, Any]] | None) -> list[str]:
    if not reports:
        return []
    launch_report = next((report for report in reports if report.get("name") == "launch"), None)
    if not isinstance(launch_report, dict):
        return []
    next_actions = launch_report.get("next_actions")
    if not isinstance(next_actions, list):
        return []

    lines: list[str] = []
    for action in next_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        remediation = action.get("remediation")
        if not isinstance(action_id, str) or not action_id.strip():
            continue
        if not isinstance(remediation, str) or not remediation.strip():
            continue
        status = action.get("status") if isinstance(action.get("status"), str) else "unknown"
        required = "required" if action.get("required") is True else "optional"
        required_env = action.get("required_env")
        env_text = ""
        if isinstance(required_env, list):
            env_values = [item for item in required_env if isinstance(item, str) and item.strip()]
            if env_values:
                env_text = f" env={', '.join(env_values)}"
        lines.append(f"- {action_id.strip()} ({required} {status}): {remediation.strip()}{env_text}")
    return lines


def print_summary(failures: list[str], reports: list[dict[str, Any]] | None = None) -> int:
    if not failures:
        _print_progress("\n[smoke] OK")
        return 0

    _print_progress("\n[smoke] FAILED")
    for failure in failures:
        _print_progress(f"- {failure}")
    next_action_lines = _launch_next_action_lines(reports)
    if next_action_lines:
        _print_progress("[smoke] NEXT ACTIONS")
        for line in next_action_lines:
            _print_progress(line)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    failures, reports = collect_checks(args)
    if args.json_out:
        write_json_report(args.json_out, failures=failures, reports=reports, args=args)
    return print_summary(failures, reports)


if __name__ == "__main__":
    sys.exit(main())
