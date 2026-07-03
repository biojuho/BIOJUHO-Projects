#!/usr/bin/env python3
"""Browser-level smoke checks for the DSCI-DecentBio frontend.

Unlike ``product_smoke.py``, this script runs the client JavaScript in Chromium
and catches broken routes, runtime exceptions, and console errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ai_lab_output_quality import parse_review_packet, parse_review_packet_topic, score_ai_lab_output
from evidence_io import write_json_atomic

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
class BrowserCheckReport:
    name: str
    path: str
    ok: bool
    failures: list[str]
    trace_path: str | None = None


@dataclass(frozen=True)
class FreshPageResult:
    failures: list[str]
    trace_path: str | None = None


RAW_TRANSPORT_ERROR_TEXT = (
    "Failed to fetch",
    "Network Error",
    "Load failed",
    "ERR_CONNECTION_REFUSED",
    "ERR_NETWORK",
    "API Error",
)

DIAGNOSTIC_RESOURCE_TYPES = {"document", "fetch", "xhr"}
DASHBOARD_READINESS_MOCKED_ENDPOINTS = (
    "/ready",
    "/launch",
    "/me",
    "/papers/me",
    "/health",
    "/vcs",
    "/notices",
)


PUBLIC_CHECKS = (
    RouteCheck("home", "/", ("DSCI",)),
    RouteCheck("pricing", "/pricing", ("Starter", "Pro", "Enterprise")),
    RouteCheck("explore", "/explore", ("IPFS", "AI")),
    RouteCheck("investors", "/investors", ("투자자 디렉터리", "Bio VC")),
    RouteCheck("login", "/login", ("DSCI",)),
    RouteCheck("not-found", "/does-not-exist", ("404",)),
)

PROTECTED_REDIRECT_CHECKS = (
    RouteCheck("dashboard-redirect", "/dashboard", ("DSCI",), expected_url_path="/login"),
    RouteCheck("upload-redirect", "/upload", ("DSCI",), expected_url_path="/login"),
)

AUTHENTICATED_CHECKS = (
    RouteCheck("dashboard-authenticated", "/dashboard", ("새 연구 제출", "출시 준비도", "dev-auth@desci.local")),
    RouteCheck("biolinker-authenticated", "/biolinker", ("Match Studio",)),
    RouteCheck("upload-authenticated", "/upload", ("Research Submission", "IPFS에 저장하고 제출 등록")),
    RouteCheck("mylab-authenticated", "/mylab", ("Research Vault",)),
    RouteCheck("vc-portal-authenticated", "/vc-portal", ("Investor View",)),
    RouteCheck("notices-authenticated", "/notices", ("펀딩 공고", "공고 매칭 에이전트")),
    RouteCheck("ai-lab-authenticated", "/ai-lab", ("AI Workbench",)),
    RouteCheck("peer-review-authenticated", "/peer-review", ("Peer Review|피어 리뷰",)),
    RouteCheck("wallet-authenticated", "/wallet", ("보상 지갑을 연결하세요", "지갑 연결")),
    RouteCheck("assets-authenticated", "/assets", ("Asset Library",)),
    RouteCheck("governance-authenticated", "/governance", ("Governance Hub|거버넌스 허브",)),
)

LOGIN_SHORT_PASSWORD_MESSAGES = (
    "비밀번호는 6자 이상이어야 합니다.",
    "Password must be at least 6 characters.",
)
POLYGON_AMOY_CHAIN_ID = "0x13882"
POLYGON_AMOY_RPC_URL = "https://polygon-amoy.drpc.org"
POLYGON_AMOY_EXPLORER_URL = "https://amoy.polygonscan.com"
MOCK_WALLET_ADDRESS = "0x1234567890123456789012345678901234567890"
AI_LAB_DECISION_READY_FIXTURE = """
# Browser Smoke AI Lab deep analysis

## 1-minute Executive Summary
Recommendation: proceed with the scorer-ready packet workflow before relying on live-provider reuse.
Evidence basis: "specific, measurable requirements" [1], copied Markdown, source IDs, source URLs,
source snippets, and "Risk Owner, Time Plan, Expected Effect" [2] prove the offline packet path. Confidence is medium because live provider quality and
external source freshness remain uncertain. Next action: AI Lab maintainer attaches the copied review packet,
strict quality report, and follow-up live-packet artifact to the release meeting note.

## Audience & Use Case
Audience: platform operator, AI Lab maintainer, and launch reviewer validating the research result.
Use case: turn the browser-rendered answer into a scorer-ready review packet and launch-review handoff.
Decision context: decide whether the local AI Lab result can be copied and reused while live provider
credentials are still blocked. Destination: release meeting note, strict quality report, and follow-up
live-packet artifact.

## Recommendation / Decision
Recommendation: proceed with the scorer-ready packet workflow before relying on live-provider reuse.
Rationale: NASA source-backed acceptance criteria support measurable readiness checks and formal readiness decisions
for the copied review-packet workflow.
Quoted evidence: "specific, measurable requirements" [1]. Browser evidence proves the rendered result,
copied packet, and quality gate path. Confidence: medium.
Change condition: hold before launch review if source evidence quality scoring or copied source packet parsing cannot be verified in the browser smoke path.
Confidence calibration: medium because copied Markdown, evidence source snippets, and strict local scoring
prove the offline packet path, while NASA measurable acceptance criteria support the readiness threshold [1].
Live provider quality remains uncertain; a live provider packet with fresh sources would raise confidence,
while stale source freshness or unsupported claims would lower confidence.

## Key Findings
- Claim: AI Lab research output should preserve evidence framing, not only conclusions. Evidence:
  NASA acceptance-criteria guidance treats acceptance criteria as testable readiness requirements [1].
  Uncertainty: real provider outputs may vary in wording. Action meaning: keep a reusable offline scorer
  aligned with the prompt contract. Quoted evidence: "specific, measurable requirements" [1].
- Claim: Successful output should include an owner handoff path for the review-packet workflow. Evidence: UNDP risk-recording guidance ties
  risk treatment to owner, time plan, expected effect, responsible treatment, and status [2]. Uncertainty:
  provider recovery may still be blocked by credentials. Action meaning: require a seven-day action plan
  in the fixture and prompt. Quoted evidence: "objectively evaluate if the actions have been done" [2].
- Claim: Reviewers need fixture limits and source freshness before trusting reuse. Evidence: UNDP risk
  quality guidance requires risk treatment owner and time plan details to stay specific, measurable, and time-bound [2]. Uncertainty:
  fixture-only verification cannot prove live-provider quality. Action meaning: keep live packet scoring
  as a launch blocker. Quoted evidence: "specific, measurable, attainable, relevant, time-bound" [2].

## Evidence Map
- Strong: specific, measurable readiness requirements and formal decision criteria support strict local scoring.
  Quoted evidence: "specific, measurable requirements" [1].
  Confidence: high. Follow-up verification: confirm the copied packet still passes strict scoring and keeps
  source URLs plus evidence source snippets.
- Weak: fixture-only verification still needs risk treatment owner and time-bound review.
  Quoted evidence: "Risk Owner, Time Plan, Expected Effect" [2]. Confidence: medium.
  Follow-up verification: ask the platform owner to compare against a live provider packet.
- Missing: live provider response until credentials are restored. Confidence: low.
  Follow-up verification: assign provider credential recovery before final launch review.

## Deep Dive
Technical: keep source URLs, copied Markdown payloads, and "specific, measurable requirements" [1] with every fixture run.
Clinical: generated research briefs should distinguish patient population, endpoint maturity, and
trial-readiness. Regulatory: flag compliance constraints, source freshness, and evidence limits before launch review.
Operations: the output should assign risk owner, time plan, status [2], required inputs, compliance blocker owner, and proposal review artifact for the next step. Commercial:
the result should connect evidence quality to pursuit priority, proposal go/no-go, commercialization timing, and budget timing. Alternative comparison:
a manual review workflow is lighter for one-off checks,
but a scorer-ready packet is stronger when reviewers need repeatable source evidence and decision gates.
Competitive reuse value: compared with manual review or generic research services, this scorer-ready packet
gives platform operators and launch reviewers reusable source-backed decision gates, owner handoff, and a
review-packet checklist that can be reused for each launch review.

## Action Plan
Next 7 days:
- Day 1 / Priority P0. Owner: AI Lab maintainer. Inputs: rendered browser result, copied review packet,
  and evidence source snippets. Artifact: scorer-ready review packet. Decision gate: accept only if strict
  quality scoring passes against "specific, measurable requirements" [1]. Success metric: copied packet scores
  pass with zero failed checks.
  Dependencies/blocked by: copied Markdown and evidence snippets must be available before strict scoring;
  block launch review if packet parsing fails.
- Day 2-5 / Priority P1. Owner: platform operator. Inputs: recovered provider credentials and live AI Lab
  packet. Artifact: live output quality report. Decision gate: decide whether the live provider output is
  ready for reuse. Success metric: live packet has a source-backed recommendation and no strict failures.
  Dependencies/blocked by: starts after provider credentials recover and the time-bound local packet passes [2]; blocked
  by stale source freshness or unsupported live-provider claims.

## Reusable Handoff
Copy-ready decision log: proceed with the scorer-ready packet workflow, with medium confidence, while
specific, measurable requirements [1] remain the change condition. Stakeholder ask: platform operator should attach the
strict quality report and risk treatment status [2] to the launch review. Owner next step: AI Lab maintainer can paste this into the
release meeting note, assign the live-packet artifact, and reuse the scoring command for follow-up checks.
Artifact-ready format:
- Decision log: proceed with scorer-ready packet workflow with calibrated medium confidence.
- Stakeholder ask: platform operator attaches the strict quality report to launch review.
- Owner next step: AI Lab maintainer adds the live-packet artifact to the release meeting note.
- Evidence attachment: copied review packet, source URLs, specific measurable requirements [1], risk owner and status [2], and strict quality report.
- Quoted evidence: "Risk Owner, Time Plan, Expected Effect" [2].

## Assumptions & Boundaries
Assumption: "specific, measurable requirements" [1] can validate local rendering, copy handling, and strict
scorer behavior, not live provider quality. Boundary: external provider credentials and live retrieval are
out-of-scope for this smoke check. Constraint: launch reuse is blocked until live-provider recovery is
complete. Validation: attach the source snapshot, review the memo before launch review, and confirm risk owner,
time plan, expected effect, and status [2] before production reuse.

## Reviewer Red Flags
Red flag: do not use the browser fixture as launch approval for live provider quality. Stop condition:
hold or reject production reuse if "specific, measurable requirements" [1] are missing or if
risk treatment owner, time plan, expected effect, or status cannot be verified [2]. Evidence blocker: unsupported claims, uncited
source lines, or unverifiable quotes are no-go until corrected. Escalation: assign the AI Lab maintainer,
platform operator, or launch reviewer to verify and resolve the blocker before production reuse.

## Risks & Open Questions
- Risk: provider output drift could pass rendering while weakening decision usefulness. Owner: AI Lab
  maintainer. Verification: score a fresh live packet and strict scorer output against "specific, measurable requirements" [1]. Status/review:
  open; review by the next launch review. Follow-up: refresh the fixture or hold production reuse if the
  live packet fails.
- Risk: stale source material could make a copied packet look stronger than the evidence allows. Owner:
  platform operator. Verification: attach a source snapshot and confirm risk owner, time plan, expected effect, and status [2]. Status/review:
  open; review before production reuse. Follow-up: lower confidence or hold production reuse until sources
  are refreshed.
- Open question: what minimum live-output score should trigger reuse approval? Owner: launch reviewer.
  Verification: compare the live packet, strict scorer output, and reviewer notes. Status/review:
  unresolved; revisit before the release meeting. Follow-up: document the accepted threshold in the
  review packet.

## References & Search Queries
- [1] NASA SWE-034 acceptance criteria: https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695413/SWE-034%2B-%2BAcceptance%2BCriteria (source type: acceptance-criteria standard; checked: 2026-06-07; source freshness: verify before launch review)
- [2] UNDP risk recording and reporting: https://healthimplementation.undp.org/functional-areas/risk-management/undp-risk-management-process/risk-recording-and-reporting/ (source type: risk-management guidance; checked: 2026-06-07; source freshness: verify before launch review)
- Search query: site:.gov NASA SWE acceptance criteria measurable testable launch review source freshness.
- Search query: site:.org UNDP risk recording risk owner time plan expected effect status.
- Search query: AI Lab live provider packet source freshness strict scorer reviewer threshold.

## Quality Criteria
- Ready to use: accepted when the reviewer can identify the recommendation, source-backed evidence,
  uncertainty, owner, next action, and "specific, measurable requirements" [1].
- Do not use: reject or hold when source freshness, provider credentials, citations, or launch blockers
  are missing or risk owner/status cannot be verified [2].
- Evidence required: copied review packet, source URLs, evidence snippets, cited evidence, and strict
  quality report.
- Verifier/owner: AI Lab maintainer or platform operator confirms the criteria before reuse.
- Reuse destination: release meeting note, launch review, follow-up live-packet artifact, and review packet.
""".strip()
AI_LAB_EVIDENCE_SOURCES = (
    {
        "id": "1",
        "title": "NASA SWE-034 acceptance criteria",
        "url": "https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695413/SWE-034%2B-%2BAcceptance%2BCriteria",
        "freshness": "checked: 2026-06-07; source freshness: verify before launch review",
        "source_type": "acceptance-criteria standard",
        "snippet": (
            "NASA SWE-034 defines acceptance criteria as specific, measurable requirements that a system "
            "or component needs to fulfill before approval. Acceptance testing must lead to formal decisions "
            "about software readiness, including Acceptance with Conditions or Rejection/Remediation."
        ),
    },
    {
        "id": "2",
        "title": "UNDP risk recording and reporting",
        "url": "https://healthimplementation.undp.org/functional-areas/risk-management/undp-risk-management-process/risk-recording-and-reporting/",
        "freshness": "checked: 2026-06-07; source freshness: verify before launch review",
        "source_type": "risk-management guidance",
        "snippet": (
            "UNDP risk recording lists Risk Owner, Time Plan, Expected Effect, Responsible for treatments, "
            "and Status. Treatment actions should let an observer objectively evaluate if the actions have "
            "been done, and risk treatment should be specific, measurable, attainable, relevant, time-bound."
        ),
    },
)


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _print_progress(message: str = "") -> None:
    print(message, flush=True)


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}" if path != "/" else base_url.rstrip("/")


def _path_from_url(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    path = without_scheme.split("/", 1)[-1] if "/" in without_scheme else ""
    path = f"/{path.split('?', 1)[0].split('#', 1)[0]}"
    return path.rstrip("/") or "/"


def _collect_body_failures(check: RouteCheck, body_text: str) -> list[str]:
    failures: list[str] = []
    if len(body_text.strip()) < 20:
        failures.append(f"{check.name}: body is unexpectedly short")
    for expected in check.expected_text:
        if not any(variant in body_text for variant in _text_variants(expected)):
            failures.append(f"{check.name}: missing expected text {expected!r}")
    if "Support ID" in body_text or "지원 ID" in body_text:
        failures.append(f"{check.name}: rendered the error boundary")
    for raw_error in RAW_TRANSPORT_ERROR_TEXT:
        if raw_error in body_text:
            failures.append(f"{check.name}: rendered raw transport error text {raw_error!r}")
    return failures


def _text_variants(expected: str) -> tuple[str, ...]:
    variants = tuple(part for part in expected.split("|") if part)
    return variants or (expected,)


def _expand_expected_texts(expected_text: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(variant for expected in expected_text for variant in _text_variants(expected))


def _redirect_failures(check: RouteCheck, page_url: str) -> list[str]:
    if not check.expected_url_path:
        return []
    actual_path = _path_from_url(page_url)
    if actual_path == check.expected_url_path:
        return []
    return [f"{check.name}: expected final path {check.expected_url_path}, got {actual_path}"]


def _browser_error_failures(route_name: str, console_errors: list[str], page_errors: list[str]) -> list[str]:
    failures = [f"{route_name}: console error: {message[:300]}" for message in console_errors[:5]]
    failures.extend(f"{route_name}: page error: {message[:300]}" for message in page_errors[:5])
    return failures


def _request_resource_type(request: Any) -> str:
    value = getattr(request, "resource_type", "")
    if callable(value):
        try:
            value = value()
        except Exception:  # pragma: no cover - defensive for Playwright internals
            value = ""
    return str(value or "")


def _is_network_diagnostic_request(request: Any) -> bool:
    return _request_resource_type(request) in DIAGNOSTIC_RESOURCE_TYPES


def _request_failure_text(request: Any) -> str:
    method = str(getattr(request, "method", "") or "?")
    url = str(getattr(request, "url", "") or "unknown-url")
    failure = getattr(request, "failure", None)
    if callable(failure):
        try:
            failure = failure()
        except Exception:  # pragma: no cover - defensive for Playwright internals
            failure = None
    error_text = getattr(failure, "error_text", None) or str(failure or "unknown failure")
    return f"{method} {url} failed: {error_text}"


def _response_error_text(response: Any) -> str:
    request = getattr(response, "request", None)
    method = str(getattr(request, "method", "") or "?")
    url = str(getattr(response, "url", "") or "unknown-url")
    status = str(getattr(response, "status", "") or "unknown-status")
    return f"{method} {url} returned HTTP {status}"


def _network_diagnostic_failures(failed_requests: list[str], http_error_responses: list[str]) -> list[str]:
    failures = [f"network request failed: {message[:300]}" for message in failed_requests[:5]]
    failures.extend(f"network HTTP error: {message[:300]}" for message in http_error_responses[:5])
    return failures


def _first_visible_locator(locators: list[Any], *, timeout_ms: int):
    last_error: Exception | None = None
    per_locator_timeout = min(timeout_ms, 1500)
    for locator in locators:
        try:
            locator.wait_for(state="visible", timeout=per_locator_timeout)
            return locator
        except PlaywrightTimeoutError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise PlaywrightTimeoutError("no locator candidates provided")


def _any_text_visible(page, texts: tuple[str, ...], *, timeout_ms: int) -> bool:
    per_text_timeout = min(timeout_ms, 1500)
    for text in texts:
        try:
            page.get_by_text(text).first.wait_for(state="visible", timeout=per_text_timeout)
            return True
        except PlaywrightTimeoutError:
            continue
    if "Research Submission" in texts:
        try:
            page.locator('main form input[type="file"]').first.wait_for(state="attached", timeout=timeout_ms)
            page.locator("main form textarea").first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            pass
    return False


def _goto_app_route(page, base_url: str, path: str, timeout_ms: int):
    return page.goto(_url(base_url, path), wait_until="domcontentloaded", timeout=timeout_ms)


def _wait_for_route_render(page, check: RouteCheck, timeout_ms: int) -> None:
    if check.expected_text and hasattr(page, "get_by_text"):
        expected_texts = _expand_expected_texts(check.expected_text)
        if _any_text_visible(page, expected_texts, timeout_ms=timeout_ms):
            return
        page.wait_for_function(
            """
            (expectedTexts) => {
              const body = document.body?.innerText || '';
              return expectedTexts.some((text) => body.includes(text));
            }
            """,
            arg=list(expected_texts),
            timeout=timeout_ms,
        )


def _run_login_validation_check(page, base_url: str, timeout_ms: int) -> list[str]:
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = _goto_app_route(page, base_url, "/login", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"login-validation: HTTP status {status}")

        page.get_by_placeholder("you@example.com").fill("researcher@example.com", timeout=timeout_ms)
        password_field = _first_visible_locator(
            [
                page.get_by_placeholder("비밀번호를 입력해 주세요"),
                page.get_by_placeholder("Enter your password"),
            ],
            timeout_ms=timeout_ms,
        )
        password_field.fill("123", timeout=timeout_ms)
        page.get_by_role("button", name=re.compile(r"^(로그인|Sign in)$")).click(timeout=timeout_ms)

        if not _any_text_visible(page, LOGIN_SHORT_PASSWORD_MESSAGES, timeout_ms=timeout_ms):
            failures.append("login-validation: short password did not render an in-app error")
    except PlaywrightTimeoutError as exc:
        failures.append(f"login-validation: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"login-validation: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures("login-validation", console_errors, page_errors))
    return failures


def _run_dashboard_quick_upload_click_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "dashboard-quick-upload-click"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = _goto_app_route(page, base_url, "/dashboard", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        upload_link = _first_visible_locator(
            [
                page.get_by_test_id("dashboard-quick-action-upload"),
                page.get_by_role("link", name=re.compile(r"(새 연구 제출|Submit new research)")),
            ],
            timeout_ms=timeout_ms,
        )
        upload_link.click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/upload$"), timeout=timeout_ms)
        if not _any_text_visible(page, ("Research Submission", "IPFS에 저장하고 제출 등록"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: upload page did not render after click")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _dashboard_readiness_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "summary": {
            "ready_count": 7,
            "total": 13,
            "required_ready_count": 4,
            "required_total": 7,
        },
        "checks": [
            {"id": "api", "status": "pass", "required": True},
            {
                "id": "auth",
                "status": "fail",
                "required": True,
                "remediation": (
                    "Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON. "
                    "Use ALLOW_TEST_BYPASS only for local smoke."
                ),
                "required_env": ["GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON"],
            },
            {"id": "vector_store", "status": "pass", "required": True, "metric": 7},
            {"id": "llm", "status": "pass", "required": True},
            {
                "id": "stripe",
                "status": "fail",
                "required": True,
                "remediation": (
                    "Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO_MONTHLY, "
                    "and STRIPE_PRICE_PRO_YEARLY before enabling paid checkout."
                ),
                "required_env": [
                    "STRIPE_SECRET_KEY",
                    "STRIPE_WEBHOOK_SECRET",
                    "STRIPE_PRICE_PRO_MONTHLY",
                    "STRIPE_PRICE_PRO_YEARLY",
                ],
            },
            {
                "id": "stripe_return_url",
                "status": "pass",
                "required": True,
            },
            {"id": "stripe_portal", "status": "pass", "required": False},
            {
                "id": "cors",
                "status": "fail",
                "required": True,
                "remediation": (
                    "Set ALLOWED_ORIGINS to the deployed frontend origin list; do not use wildcard or localhost origins."
                ),
                "required_env": ["ALLOWED_ORIGINS"],
            },
            {"id": "redis", "status": "pass", "required": False},
            {
                "id": "rabbitmq",
                "status": "warn",
                "required": False,
                "remediation": "Set RABBITMQ_URL and confirm RabbitMQ is reachable from the worker runtime.",
                "required_env": ["RABBITMQ_URL"],
            },
            {
                "id": "ipfs",
                "status": "warn",
                "required": False,
                "remediation": "Set PINATA_JWT, or PINATA_API_KEY plus PINATA_API_SECRET, before public asset minting.",
                "required_env": ["PINATA_JWT", "PINATA_API_KEY", "PINATA_API_SECRET"],
            },
            {
                "id": "web3",
                "status": "pass",
                "required": False,
                "configured": True,
                "available": True,
                "remediation": (
                    "Use MOCK_MODE=true only for local demos. For production, configure WEB3_RPC_URL as a public "
                    "HTTPS Polygon Amoy RPC endpoint plus deployed DSCI/NFT/DAO contract addresses."
                ),
                "required_env": [
                    "MOCK_MODE",
                    "WEB3_RPC_URL",
                    "DSCI_CONTRACT_ADDRESS",
                    "NFT_CONTRACT_ADDRESS",
                    "DESCI_DAO_CONTRACT_ADDRESS",
                ],
                "details": {
                    "rpc_configured": True,
                    "rpc_public_https": False,
                    "contract_count": 2,
                    "contracts": {
                        "DSCI_CONTRACT_ADDRESS": True,
                        "NFT_CONTRACT_ADDRESS": True,
                        "DESCI_DAO_CONTRACT_ADDRESS": False,
                    },
                    "mock_mode_enabled": True,
                    "mock_mode_allowed": True,
                    "rpc_url": "https://secret-rpc.example",
                    "contract_address": "0x1111111111111111111111111111111111111111",
                },
            },
            {
                "id": "grobid",
                "status": "warn",
                "required": False,
                "remediation": "Set GROBID_ENABLED=true and GROBID_URL to a reachable GROBID service.",
                "required_env": ["GROBID_ENABLED", "GROBID_URL"],
            },
        ],
        "checked_at": "2026-07-03T00:00:00Z",
        "launch_blockers": ["auth", "stripe", "cors"],
    }


def _dashboard_percent(ready_count: int, total: int) -> int:
    return round((ready_count / total) * 100) if total else 0


def _dashboard_launch_action_from_check(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": check.get("id"),
        "required": bool(check.get("required")),
        "status": check.get("status"),
        "remediation": check.get("remediation", ""),
        "required_env": check.get("required_env") if isinstance(check.get("required_env"), list) else [],
    }


def _dashboard_launch_payload() -> dict[str, Any]:
    readiness_payload = _dashboard_readiness_payload()
    summary = readiness_payload["summary"]
    checks = [check for check in readiness_payload["checks"] if isinstance(check, dict)]
    blockers = [check for check in checks if check.get("required") and check.get("status") == "fail"]
    warnings = [check for check in checks if check.get("status") == "warn"]

    return {
        "product": "DSCI-DecentBio",
        "release_decision": "no-go",
        "operator_phase": "blocked",
        "readiness_status": readiness_payload["status"],
        "checked_at": readiness_payload["checked_at"],
        "score": {
            "overall_percent": _dashboard_percent(summary["ready_count"], summary["total"]),
            "required_percent": _dashboard_percent(summary["required_ready_count"], summary["required_total"]),
        },
        "summary": {
            "ready_count": summary["ready_count"],
            "total": summary["total"],
            "required_ready_count": summary["required_ready_count"],
            "required_total": summary["required_total"],
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "launch_blockers": [check.get("id") for check in blockers],
        "next_actions": [_dashboard_launch_action_from_check(check) for check in [*blockers, *warnings]],
    }


def _fulfill_json_api_route(route, *, request_urls: list[str], payload: Any) -> None:
    request = route.request
    if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
        route.continue_()
        return
    request_urls.append(request.url)
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


def _dashboard_shell_api_payloads() -> dict[str, Any]:
    return {
        "/me": {
            "uid": "dev-auth-bypass-user",
            "email": "dev-auth@desci.local",
            "display_name": "Dev Researcher",
            "role": "researcher",
        },
        "/papers/me": [
            {
                "id": "browser-smoke-paper",
                "title": "Browser Smoke Launch Readiness Paper",
                "authors": "Dev Researcher",
            }
        ],
        "/health": {
            "status": "healthy",
            "chromadb_count": 2,
            "count": 2,
        },
        "/vcs": [
            {
                "id": "browser-smoke-vc",
                "name": "Browser Smoke Ventures",
                "country": "Global",
                "portfolio_keywords": ["AI therapeutics", "platform biology"],
                "investment_thesis": "Fixture investor profile for dashboard rendering.",
                "match_reason": "Focus areas: AI therapeutics, platform biology",
                "score": 91,
            }
        ],
        "/notices": [
            {
                "id": "browser-smoke-notice",
                "title": "Browser Smoke Translational Grant",
                "source": "Fixture funding notice",
                "body_text": "Funding notice fixture for dashboard recommendation rendering.",
                "deadline": "2026-07-15",
                "url": "https://example.org/browser-smoke-translational-grant",
            }
        ],
    }


def _exact_api_route_pattern(path: str) -> re.Pattern[str]:
    escaped_path = re.escape(path)
    return re.compile(rf"^[a-z][a-z0-9+.-]*://[^/?#]+{escaped_path}(?:[?#].*)?$", re.IGNORECASE)


def _dashboard_shell_api_routes(
    request_urls: list[str],
) -> list[tuple[re.Pattern[str], Callable]]:
    routes: list[tuple[re.Pattern[str], Callable]] = []
    for path, payload in _dashboard_shell_api_payloads().items():

        def make_handler(route_payload: Any) -> Callable:
            def fulfill_dashboard_shell(route) -> None:
                _fulfill_json_api_route(route, request_urls=request_urls, payload=route_payload)

            return fulfill_dashboard_shell

        routes.append((_exact_api_route_pattern(path), make_handler(payload)))
    return routes


def _run_dashboard_readiness_refresh_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "dashboard-readiness-refresh"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    ready_requests: list[str] = []
    launch_requests: list[str] = []
    dashboard_shell_requests: list[str] = []
    ready_route_pattern = "**/ready"
    launch_route_pattern = "**/launch"
    dashboard_shell_routes = _dashboard_shell_api_routes(dashboard_shell_requests)
    ready_payload = _dashboard_readiness_payload()
    launch_payload = _dashboard_launch_payload()

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_ready(route) -> None:
        _fulfill_json_api_route(route, request_urls=ready_requests, payload=ready_payload)

    def fulfill_launch(route) -> None:
        _fulfill_json_api_route(route, request_urls=launch_requests, payload=launch_payload)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(ready_route_pattern, fulfill_ready)
    page.route(launch_route_pattern, fulfill_launch)
    for pattern, handler in dashboard_shell_routes:
        page.route(pattern, handler)

    try:
        try:
            page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url.rstrip("/"))
        except PlaywrightError as exc:
            failures.append(f"{route_name}: could not grant clipboard permissions ({exc})")

        response = _goto_app_route(page, base_url, "/dashboard", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("product-readiness-panel").wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_function(
            """
            () => {
              const progress = document.querySelector('[data-testid="product-readiness-progress"]')?.textContent || '';
              const ready = document.querySelector('[data-testid="product-readiness-ready-summary"]')?.textContent || '';
              const required = document.querySelector('[data-testid="product-readiness-required-summary"]')?.textContent || '';
              return progress.includes('54%') && ready.includes('7') && ready.includes('13')
                && required.includes('4') && required.includes('7');
            }
            """,
            timeout=timeout_ms,
        )
        progress_text = page.get_by_test_id("product-readiness-progress").inner_text(timeout=timeout_ms)
        if "54%" not in progress_text:
            failures.append(f"{route_name}: expected 54% progress, got {progress_text!r}")

        launch_control = page.get_by_test_id("product-readiness-launch-control")
        if launch_control.count() != 1:
            failures.append(f"{route_name}: missing launch control panel")
        else:
            launch_text = launch_control.inner_text(timeout=timeout_ms)
            expected_fragments = ("57%", "54%")
            missing_fragments = [fragment for fragment in expected_fragments if fragment not in launch_text]
            if missing_fragments:
                failures.append(f"{route_name}: launch control score missing {missing_fragments}: {launch_text!r}")

        release_decision_text = page.get_by_test_id("product-readiness-release-decision").inner_text(timeout=timeout_ms)
        if not any(fragment in release_decision_text for fragment in ("No-go", "no-go", "중단")):
            failures.append(f"{route_name}: release decision did not show no-go: {release_decision_text!r}")

        operator_phase_text = page.get_by_test_id("product-readiness-operator-phase").inner_text(timeout=timeout_ms)
        if not any(fragment in operator_phase_text for fragment in ("Blocked", "blocked", "차단")):
            failures.append(f"{route_name}: operator phase did not show blocked: {operator_phase_text!r}")

        if page.get_by_test_id("product-readiness-launch-drift").count() != 0:
            drift_text = page.get_by_test_id("product-readiness-launch-drift").inner_text(timeout=timeout_ms)
            failures.append(f"{route_name}: rendered launch drift warning for consistent fixture: {drift_text!r}")

        ready_summary = page.get_by_test_id("product-readiness-ready-summary").inner_text(timeout=timeout_ms)
        required_summary = page.get_by_test_id("product-readiness-required-summary").inner_text(timeout=timeout_ms)
        if "7" not in ready_summary or "13" not in ready_summary:
            failures.append(f"{route_name}: ready summary missing 7/13 evidence: {ready_summary!r}")
        if "4" not in required_summary or "7" not in required_summary:
            failures.append(f"{route_name}: required summary missing 4/7 evidence: {required_summary!r}")

        for check_id in (
            "api",
            "auth",
            "vector_store",
            "llm",
            "stripe",
            "stripe_return_url",
            "stripe_portal",
            "cors",
            "redis",
            "rabbitmq",
            "ipfs",
            "web3",
            "grobid",
        ):
            if page.get_by_test_id(f"product-readiness-check-{check_id}").count() != 1:
                failures.append(f"{route_name}: missing readiness check row {check_id}")

        if page.get_by_test_id("product-readiness-web3-triage").count() != 1:
            failures.append(f"{route_name}: missing Web3 readiness triage")
        else:
            web3_text = page.get_by_test_id("product-readiness-web3-triage").inner_text(timeout=timeout_ms)
            expected_fragments = (
                "RPC configured, not public HTTPS",
                "2 valid contract env values",
                "DSCI_CONTRACT_ADDRESS: valid",
                "NFT_CONTRACT_ADDRESS: valid",
                "DESCI_DAO_CONTRACT_ADDRESS: missing",
                "MOCK_MODE allowed for local runtime",
            )
            missing_fragments = [fragment for fragment in expected_fragments if fragment not in web3_text]
            if missing_fragments:
                failures.append(f"{route_name}: Web3 triage missing {missing_fragments}: {web3_text!r}")
            forbidden_fragments = ("https://secret-rpc.example", "0x1111111111111111111111111111111111111111")
            leaked_fragments = [fragment for fragment in forbidden_fragments if fragment in web3_text]
            if leaked_fragments:
                failures.append(f"{route_name}: Web3 triage exposed secret-shaped details {leaked_fragments}")

        if page.get_by_test_id("product-readiness-next-actions").count() != 1:
            failures.append(f"{route_name}: missing launch action queue")
        else:
            accessible_buttons = (
                "Copy all 6 launch actions",
                "Copy Authentication launch action",
                "Copy Stripe billing launch action",
                "Copy CORS origins launch action",
                "Copy RabbitMQ launch action",
                "Copy IPFS launch action",
                "Copy GROBID launch action",
            )
            for button_name in accessible_buttons:
                try:
                    page.get_by_role("button", name=button_name).wait_for(state="visible", timeout=timeout_ms)
                except PlaywrightTimeoutError:
                    failures.append(f"{route_name}: missing accessible button name {button_name!r}")

            auth_action = page.get_by_test_id("product-readiness-next-action-auth")
            if auth_action.count() != 1:
                failures.append(f"{route_name}: missing Authentication launch action")
            else:
                action_text = auth_action.inner_text(timeout=timeout_ms)
                if "FIREBASE_SERVICE_ACCOUNT_JSON" not in action_text or "local smoke" not in action_text:
                    failures.append(f"{route_name}: Authentication launch action lacks env/remediation: {action_text!r}")

            stripe_action = page.get_by_test_id("product-readiness-next-action-stripe")
            if stripe_action.count() != 1:
                failures.append(f"{route_name}: missing Stripe launch action")
            else:
                action_text = stripe_action.inner_text(timeout=timeout_ms)
                if "STRIPE_WEBHOOK_SECRET" not in action_text or "paid checkout" not in action_text:
                    failures.append(f"{route_name}: Stripe launch action lacks env/remediation: {action_text!r}")
                copy_button = page.get_by_test_id("product-readiness-next-action-copy-stripe")
                if copy_button.count() != 1:
                    failures.append(f"{route_name}: missing Stripe launch action copy button")
                else:
                    copy_button.click(timeout=timeout_ms)
                    try:
                        page.wait_for_timeout(200)
                        clipboard_payload = page.evaluate("() => navigator.clipboard.readText()")
                    except PlaywrightError as exc:
                        failures.append(f"{route_name}: could not read Stripe launch action clipboard ({exc})")
                    else:
                        expected_fragments = (
                            "Launch action: Stripe billing",
                            "Priority: required",
                            "Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO_MONTHLY",
                            "Required env: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET",
                        )
                        missing_fragments = [fragment for fragment in expected_fragments if fragment not in clipboard_payload]
                        if missing_fragments:
                            failures.append(
                                f"{route_name}: Stripe clipboard payload missing {missing_fragments}: {clipboard_payload!r}"
                            )
                        if "sk_live_" in clipboard_payload:
                            failures.append(f"{route_name}: Stripe clipboard payload exposed a secret-shaped value")
                    try:
                        feedback_text = page.get_by_test_id("product-readiness-copy-feedback").inner_text(timeout=timeout_ms)
                    except PlaywrightError as exc:
                        failures.append(f"{route_name}: missing Stripe copy feedback ({exc})")
                    else:
                        if "Copied " not in feedback_text or "Stripe" not in feedback_text or "launch action." not in feedback_text:
                            failures.append(f"{route_name}: Stripe copy feedback mismatch: {feedback_text!r}")
            cors_action = page.get_by_test_id("product-readiness-next-action-cors")
            if cors_action.count() != 1:
                failures.append(f"{route_name}: missing CORS launch action")
            else:
                action_text = cors_action.inner_text(timeout=timeout_ms)
                if "ALLOWED_ORIGINS" not in action_text or "deployed frontend origin list" not in action_text:
                    failures.append(f"{route_name}: CORS launch action lacks env/remediation: {action_text!r}")
            copy_all_button = page.get_by_test_id("product-readiness-next-actions-copy-all")
            if copy_all_button.count() != 1:
                failures.append(f"{route_name}: missing launch action copy-all button")
            else:
                copy_all_button.click(timeout=timeout_ms)
                try:
                    page.wait_for_timeout(200)
                    clipboard_payload = page.evaluate("() => navigator.clipboard.readText()")
                except PlaywrightError as exc:
                    failures.append(f"{route_name}: could not read launch action copy-all clipboard ({exc})")
                else:
                    expected_fragments = (
                        "Launch action: Authentication",
                        "Launch action: Stripe billing",
                        "Launch action: CORS origins",
                        "Launch action: RabbitMQ",
                        "Launch action: IPFS",
                        "Launch action: GROBID",
                        "Required env: GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_SERVICE_ACCOUNT_JSON",
                        "Required env: ALLOWED_ORIGINS",
                        "Required env: RABBITMQ_URL",
                        "Required env: PINATA_JWT, PINATA_API_KEY, PINATA_API_SECRET",
                        "Set GROBID_ENABLED=true and GROBID_URL",
                    )
                    missing_fragments = [fragment for fragment in expected_fragments if fragment not in clipboard_payload]
                    if missing_fragments:
                        failures.append(
                            f"{route_name}: launch action copy-all payload missing {missing_fragments}: {clipboard_payload!r}"
                        )
                    if "sk_live_" in clipboard_payload:
                        failures.append(f"{route_name}: launch action copy-all payload exposed a secret-shaped value")
                try:
                    feedback_text = page.get_by_test_id("product-readiness-copy-feedback").inner_text(timeout=timeout_ms)
                except PlaywrightError as exc:
                    failures.append(f"{route_name}: missing copy-all feedback ({exc})")
                else:
                    if "Copied 6 launch actions." not in feedback_text:
                        failures.append(f"{route_name}: copy-all feedback mismatch: {feedback_text!r}")

        request_count_before_refresh = len(ready_requests)
        launch_count_before_refresh = len(launch_requests)
        with page.expect_response(
            lambda response: response.request.method.upper() == "GET" and urlparse(response.url).path == "/ready",
            timeout=timeout_ms,
        ), page.expect_response(
            lambda response: response.request.method.upper() == "GET" and urlparse(response.url).path == "/launch",
            timeout=timeout_ms,
        ):
            page.get_by_test_id("product-readiness-refresh").click(timeout=timeout_ms)
        if len(ready_requests) <= request_count_before_refresh:
            failures.append(f"{route_name}: refresh did not issue another /ready request")
        if len(launch_requests) <= launch_count_before_refresh:
            failures.append(f"{route_name}: refresh did not issue another /launch request")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(ready_route_pattern, fulfill_ready)
        page.unroute(launch_route_pattern, fulfill_launch)
        for pattern, handler in dashboard_shell_routes:
            page.unroute(pattern, handler)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_dashboard_readiness_clipboard_failure_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "dashboard-readiness-copy-failure"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    ready_route_pattern = "**/ready"
    launch_route_pattern = "**/launch"
    ready_payload = _dashboard_readiness_payload()
    launch_payload = _dashboard_launch_payload()

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_ready(route) -> None:
        _fulfill_json_api_route(route, request_urls=[], payload=ready_payload)

    def fulfill_launch(route) -> None:
        _fulfill_json_api_route(route, request_urls=[], payload=launch_payload)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(ready_route_pattern, fulfill_ready)
    page.route(launch_route_pattern, fulfill_launch)

    try:
        response = _goto_app_route(page, base_url, "/dashboard", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("product-readiness-next-actions").wait_for(state="visible", timeout=timeout_ms)
        page.evaluate(
            """() => {
                Object.defineProperty(navigator, 'clipboard', {
                    configurable: true,
                    value: {
                        writeText: async () => {
                            throw new Error('Clipboard denied by browser smoke');
                        },
                        readText: async () => ''
                    }
                });
            }"""
        )

        page.get_by_test_id("product-readiness-next-action-copy-stripe").click(timeout=timeout_ms)
        feedback = page.get_by_role("alert")
        feedback.wait_for(state="visible", timeout=timeout_ms)
        feedback_text = feedback.inner_text(timeout=timeout_ms)
        if "Could not copy" not in feedback_text or "Stripe" not in feedback_text or "visible remediation" not in feedback_text:
            failures.append(f"{route_name}: Stripe copy failure feedback mismatch: {feedback_text!r}")
        button_text = page.get_by_test_id("product-readiness-next-action-copy-stripe").inner_text(timeout=timeout_ms)
        if "Copied" in button_text:
            failures.append(f"{route_name}: Stripe copy button showed success after clipboard denial")

        page.get_by_test_id("product-readiness-next-actions-copy-all").click(timeout=timeout_ms)
        feedback_text = page.get_by_role("alert").inner_text(timeout=timeout_ms)
        if "Could not copy launch actions." not in feedback_text:
            failures.append(f"{route_name}: copy-all failure feedback mismatch: {feedback_text!r}")
        button_text = page.get_by_test_id("product-readiness-next-actions-copy-all").inner_text(timeout=timeout_ms)
        if "Copied" in button_text:
            failures.append(f"{route_name}: copy-all button showed success after clipboard denial")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(ready_route_pattern, fulfill_ready)
        page.unroute(launch_route_pattern, fulfill_launch)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_dashboard_recommendation_source_link_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "dashboard-recommendation-source-link-fallback"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    notices_requests: list[str] = []
    notices_route_pattern = "**/notices?*"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_notices(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        notices_requests.append(request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-safe-source",
                        "title": "Safe Source Grant",
                        "source": "KDDF",
                        "body_text": "Funding notice with a canonical HTTPS source URL.",
                        "deadline": "2026-08-15",
                        "url": "https://safe.example/notice",
                    },
                    {
                        "id": "browser-missing-source",
                        "title": "Missing Source Grant",
                        "source": "NTIS",
                        "body_text": "Funding notice missing its canonical source URL.",
                    },
                    {
                        "id": "browser-unsafe-source",
                        "title": "Unsafe Source Grant",
                        "source": "NTIS",
                        "body_text": "Funding notice with a javascript URL that must not become a link.",
                        "url": "javascript:alert(1)",
                    },
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(notices_route_pattern, fulfill_notices)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__aiLabCopiedText = '';
              const clipboardStub = {
                writeText: async (text) => {
                  window.__aiLabCopiedText = String(text);
                  window.localStorage.setItem('__aiLabCopiedText', String(text));
                }
              };
              Object.defineProperty(Navigator.prototype, 'clipboard', {
                configurable: true,
                get: () => clipboardStub
              });
              Object.defineProperty(navigator, 'clipboard', {
                configurable: true,
                value: clipboardStub
              });
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/dashboard", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        valid_link = page.get_by_test_id("recommendation-source-link-0")
        valid_link.wait_for(state="visible", timeout=timeout_ms)
        href = valid_link.get_attribute("href", timeout=timeout_ms) or ""
        target = valid_link.get_attribute("target", timeout=timeout_ms) or ""
        rel = valid_link.get_attribute("rel", timeout=timeout_ms) or ""
        if href != "https://safe.example/notice":
            failures.append(f"{route_name}: safe notice href mismatch: {href!r}")
        if target != "_blank":
            failures.append(f"{route_name}: safe notice target mismatch: {target!r}")
        if "noopener" not in rel or "noreferrer" not in rel:
            failures.append(f"{route_name}: safe notice rel missing safe flags: {rel!r}")

        for index, title in ((1, "Missing Source Grant"), (2, "Unsafe Source Grant")):
            page.get_by_text(title).first.wait_for(state="visible", timeout=timeout_ms)
            unavailable = page.get_by_test_id(f"recommendation-source-unavailable-{index}")
            unavailable.wait_for(state="visible", timeout=timeout_ms)
            unavailable_text = unavailable.inner_text(timeout=timeout_ms)
            if "Source link unavailable" not in unavailable_text:
                failures.append(f"{route_name}: unavailable fallback mismatch for {title}: {unavailable_text!r}")
            if page.get_by_test_id(f"recommendation-source-link-{index}").count() != 0:
                failures.append(f"{route_name}: rendered source link for invalid notice {title}")

        broken_links = page.locator('[data-testid^="recommendation-card-"] a[href="#"], [data-testid^="recommendation-card-"] a[href^="javascript:"]')
        broken_count = broken_links.count()
        if broken_count:
            failures.append(f"{route_name}: recommendation cards still rendered {broken_count} broken/unsafe source links")

        valid_link.evaluate(
            """element => {
                window.__recommendationSourceClicks = [];
                element.addEventListener('click', (event) => {
                    event.preventDefault();
                    window.__recommendationSourceClicks.push({
                        href: element.href,
                        target: element.target,
                        rel: element.rel,
                    });
                }, { once: true });
            }"""
        )
        valid_link.click(timeout=timeout_ms)
        clicks = page.evaluate("() => window.__recommendationSourceClicks || []")
        if len(clicks) != 1:
            failures.append(f"{route_name}: expected one safe source click, got {clicks!r}")

        if not notices_requests:
            failures.append(f"{route_name}: did not request /notices for recommendation data")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(notices_route_pattern, fulfill_notices)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_checkout_mocked_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-checkout-mocked"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    checkout_route_pattern = "**/subscription/checkout"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "free", "rate_limit": "30/minute"}),
        )

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        post_body = request.post_data or ""
        checkout_posts.append({"url": request.url, "body": post_body})
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "checkout_url": _url(base_url, "/subscription/success?session_id=browser-smoke-checkout"),
                    "session_id": "browser-smoke-checkout",
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        if not _any_text_visible(page, ("Stripe 보안 결제", "Secured by Stripe"), timeout_ms=timeout_ms):
            try:
                page.get_by_test_id("pricing-trust-marker").wait_for(state="visible", timeout=min(timeout_ms, 1500))
            except PlaywrightTimeoutError:
                failures.append(f"{route_name}: pricing trust marker is not visible")

        page.get_by_test_id("pricing-pro-cta").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/subscription/success.*session_id=browser-smoke-checkout"), timeout=timeout_ms)

        if len(checkout_posts) != 1:
            failures.append(f"{route_name}: expected one checkout POST, got {len(checkout_posts)}")
        elif '"tier":"pro"' not in checkout_posts[0]["body"] or '"billing":"monthly"' not in checkout_posts[0]["body"]:
            failures.append(f"{route_name}: checkout POST body did not include pro monthly plan")
        page.get_by_test_id("pricing-success-panel").wait_for(state="visible", timeout=timeout_ms)
        session_text = page.get_by_test_id("pricing-success-session").inner_text(timeout=timeout_ms)
        if "browser-smoke-checkout" not in session_text:
            failures.append(f"{route_name}: success page did not show checkout session id")
        if page.get_by_test_id("pricing-success-dashboard").get_attribute("href", timeout=timeout_ms) != "/dashboard":
            failures.append(f"{route_name}: success dashboard link is not /dashboard")
        if page.get_by_test_id("pricing-success-upload").get_attribute("href", timeout=timeout_ms) != "/upload":
            failures.append(f"{route_name}: success upload link is not /upload")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_checkout_yearly_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-checkout-yearly"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    checkout_route_pattern = "**/subscription/checkout"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "free", "rate_limit": "30/minute"}),
        )

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        post_body = request.post_data or ""
        checkout_posts.append({"url": request.url, "body": post_body})
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "checkout_url": _url(base_url, "/subscription/success?session_id=browser-smoke-yearly"),
                    "session_id": "browser-smoke-yearly",
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("pricing-billing-yearly").click(timeout=timeout_ms)
        page.get_by_test_id("pricing-pro-cta").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/subscription/success.*session_id=browser-smoke-yearly"), timeout=timeout_ms)

        if len(checkout_posts) != 1:
            failures.append(f"{route_name}: expected one checkout POST, got {len(checkout_posts)}")
        elif '"tier":"pro"' not in checkout_posts[0]["body"] or '"billing":"yearly"' not in checkout_posts[0]["body"]:
            failures.append(f"{route_name}: checkout POST body did not include pro yearly plan")
        page.get_by_test_id("pricing-success-panel").wait_for(state="visible", timeout=timeout_ms)
        session_text = page.get_by_test_id("pricing-success-session").inner_text(timeout=timeout_ms)
        if "browser-smoke-yearly" not in session_text:
            failures.append(f"{route_name}: success page did not show yearly checkout session id")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_checkout_cancelled_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-checkout-cancelled"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    checkout_route_pattern = "**/subscription/checkout"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "free", "rate_limit": "30/minute"}),
        )

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        post_body = request.post_data or ""
        checkout_posts.append({"url": request.url, "body": post_body})
        checkout_url = (
            _url(base_url, "/pricing?checkout=cancelled&plan=pro&billing=monthly")
            if len(checkout_posts) == 1
            else _url(base_url, "/subscription/success?session_id=browser-smoke-retry")
        )
        session_id = "browser-smoke-cancelled" if len(checkout_posts) == 1 else "browser-smoke-retry"
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "checkout_url": checkout_url,
                    "session_id": session_id,
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("pricing-pro-cta").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/pricing.*checkout=cancelled.*plan=pro"), timeout=timeout_ms)

        if len(checkout_posts) != 1:
            failures.append(f"{route_name}: expected one checkout POST, got {len(checkout_posts)}")
        elif '"tier":"pro"' not in checkout_posts[0]["body"] or '"billing":"monthly"' not in checkout_posts[0]["body"]:
            failures.append(f"{route_name}: checkout POST body did not include pro monthly plan")

        cancelled_notice = page.get_by_test_id("pricing-checkout-cancelled")
        cancelled_notice.wait_for(state="visible", timeout=timeout_ms)
        notice_text = cancelled_notice.inner_text(timeout=timeout_ms)
        for expected in ("Checkout canceled.", "Pro", "monthly"):
            if expected not in notice_text:
                failures.append(f"{route_name}: cancel notice missing {expected!r}: {notice_text!r}")
        if page.get_by_test_id("pricing-success-panel").count() > 0:
            failures.append(f"{route_name}: cancel return rendered the success panel")

        page.get_by_test_id("pricing-checkout-cancelled-retry").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/subscription/success.*session_id=browser-smoke-retry"), timeout=timeout_ms)
        if len(checkout_posts) != 2:
            failures.append(f"{route_name}: expected retry checkout POST, got {len(checkout_posts)} posts")
        elif '"tier":"pro"' not in checkout_posts[1]["body"] or '"billing":"monthly"' not in checkout_posts[1]["body"]:
            failures.append(f"{route_name}: retry checkout POST body did not preserve pro monthly plan")
        page.get_by_test_id("pricing-success-panel").wait_for(state="visible", timeout=timeout_ms)
        retry_session_text = page.get_by_test_id("pricing-success-session").inner_text(timeout=timeout_ms)
        if "browser-smoke-retry" not in retry_session_text:
            failures.append(f"{route_name}: retry success page did not show retry checkout session id")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_checkout_error_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-checkout-error-visible"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    checkout_route_pattern = "**/subscription/checkout"
    error_detail = "Stripe payment is not configured for browser smoke."
    expected_resource_error = "the server responded with a status of 503"

    def collect_console(message) -> None:
        if message.type == "error":
            if expected_resource_error in message.text:
                return
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        post_body = request.post_data or ""
        checkout_posts.append({"url": request.url, "body": post_body})
        route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": error_detail}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("pricing-pro-cta").click(timeout=timeout_ms)
        error_notice = page.get_by_test_id("pricing-checkout-error")
        error_notice.wait_for(state="visible", timeout=timeout_ms)
        error_text = error_notice.inner_text(timeout=timeout_ms)
        if error_detail not in error_text:
            failures.append(f"{route_name}: checkout error notice missing API detail: {error_text!r}")

        if len(checkout_posts) != 1:
            failures.append(f"{route_name}: expected one checkout POST, got {len(checkout_posts)}")
        elif '"tier":"pro"' not in checkout_posts[0]["body"] or '"billing":"monthly"' not in checkout_posts[0]["body"]:
            failures.append(f"{route_name}: checkout POST body did not include pro monthly plan")

        actual_path = _path_from_url(page.url)
        if actual_path != "/pricing":
            failures.append(f"{route_name}: expected to stay on /pricing, got {actual_path}")
        if page.get_by_test_id("pricing-success-panel").count() > 0:
            failures.append(f"{route_name}: error return rendered the success panel")
        if page.get_by_test_id("pricing-checkout-cancelled").count() > 0:
            failures.append(f"{route_name}: error return rendered the cancellation notice")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_enterprise_contact_intent_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-enterprise-contact-intent"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    checkout_route_pattern = "**/subscription/checkout"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "free", "rate_limit": "30/minute"}),
        )

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        checkout_posts.append({"url": request.url, "body": request.post_data or ""})
        route.fulfill(
            status=409,
            content_type="application/json",
            body=json.dumps({"detail": "enterprise contact should not create checkout"}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        enterprise_cta = page.get_by_test_id("pricing-enterprise-cta")
        enterprise_cta.wait_for(state="visible", timeout=timeout_ms)
        tag_name = enterprise_cta.evaluate("element => element.tagName")
        if tag_name != "A":
            failures.append(f"{route_name}: enterprise CTA should be a semantic link, got {tag_name!r}")

        contact_url = enterprise_cta.get_attribute("href", timeout=timeout_ms) or ""
        target = enterprise_cta.get_attribute("target", timeout=timeout_ms) or ""
        rel = enterprise_cta.get_attribute("rel", timeout=timeout_ms) or ""
        if not contact_url.startswith("mailto:hello@decentbio.xyz"):
            failures.append(f"{route_name}: enterprise CTA href mismatch {contact_url!r}")
        if "subject=Enterprise Plan Inquiry" not in contact_url:
            failures.append(f"{route_name}: enterprise CTA missing subject in {contact_url!r}")
        if target != "_blank":
            failures.append(f"{route_name}: enterprise CTA target is not _blank: {target!r}")
        if "noopener" not in rel or "noreferrer" not in rel:
            failures.append(f"{route_name}: enterprise CTA missing safe rel flags: {rel!r}")

        enterprise_cta.evaluate(
            """element => {
                window.__pricingEnterpriseClicks = [];
                element.addEventListener('click', (event) => {
                    event.preventDefault();
                    window.__pricingEnterpriseClicks.push({
                        href: element.href,
                        target: element.target,
                        rel: element.rel,
                    });
                }, { once: true });
            }"""
        )
        enterprise_cta.click(timeout=timeout_ms)
        clicks = page.evaluate("() => window.__pricingEnterpriseClicks || []")
        if len(clicks) != 1:
            failures.append(f"{route_name}: expected one sales contact click, got {clicks!r}")

        if checkout_posts:
            failures.append(f"{route_name}: enterprise CTA posted checkout instead of contacting sales: {checkout_posts!r}")
        actual_path = _path_from_url(page.url)
        if actual_path != "/pricing":
            failures.append(f"{route_name}: expected to stay on /pricing, got {actual_path}")
        if page.get_by_test_id("pricing-success-panel").count() > 0:
            failures.append(f"{route_name}: enterprise contact rendered the checkout success panel")
        if page.get_by_test_id("pricing-checkout-error").count() > 0:
            failures.append(f"{route_name}: enterprise contact rendered a checkout error")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_layout_inset_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-layout-inset"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    viewports = (
        ("mobile", {"width": 390, "height": 844}, 12),
        ("desktop", {"width": 1440, "height": 900}, 12),
    )

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        for viewport_name, viewport, min_inset in viewports:
            page.set_viewport_size(viewport)
            response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
            status = response.status if response is not None else 0
            if status >= 400:
                failures.append(f"{route_name}: {viewport_name} HTTP status {status}")

            page.locator(".pricing-page-container h1").first.wait_for(state="visible", timeout=timeout_ms)
            metrics = page.evaluate(
                """
                () => {
                  const rectFor = (element) => {
                    const rect = element?.getBoundingClientRect();
                    return rect
                      ? { left: rect.left, right: rect.right, width: rect.width, height: rect.height }
                      : null;
                  };
                  const cards = Array.from(document.querySelectorAll('.pricing-tier-grid .glass-card'));
                  return {
                    viewportWidth: window.innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    navPrimary: rectFor(document.querySelector('.pricing-page-nav .clay-button')),
                    h1: rectFor(document.querySelector('.pricing-page-container h1')),
                    grid: rectFor(document.querySelector('.pricing-tier-grid')),
                    firstCard: rectFor(cards[0]),
                    lastCard: rectFor(cards[cards.length - 1]),
                    cta: rectFor(document.querySelector('.pricing-tier-grid .clay-button, .pricing-tier-grid .clay-panel-pressed')),
                  };
                }
                """
            )
            viewport_width = metrics.get("viewportWidth", viewport["width"])
            max_right = viewport_width - min_inset
            if metrics.get("scrollWidth", 0) > viewport_width + 2:
                failures.append(f"{route_name}: {viewport_name} has horizontal document overflow ({metrics!r})")
            for key in ("h1", "grid", "firstCard"):
                box = metrics.get(key) or {}
                if box.get("left", -1) < min_inset:
                    failures.append(f"{route_name}: {viewport_name} {key} starts too close to edge ({metrics!r})")
            for key in ("grid", "lastCard", "navPrimary"):
                box = metrics.get(key) or {}
                if box.get("right", viewport_width + 1) > max_right + 0.5:
                    failures.append(f"{route_name}: {viewport_name} {key} ends too close to edge ({metrics!r})")
            cta_box = metrics.get("cta") or {}
            if cta_box.get("height", 0) < 44:
                failures.append(f"{route_name}: {viewport_name} pricing CTA is below touch target height ({metrics!r})")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_public_touch_targets_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "public-touch-targets"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    routes = ("/", "/explore", "/investors", "/pricing")

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        page.set_viewport_size({"width": 390, "height": 844})
        for path in routes:
            response = _goto_app_route(page, base_url, path, timeout_ms)
            status = response.status if response is not None else 0
            if status >= 400:
                failures.append(f"{route_name}: {path} HTTP status {status}")
            page.locator("body").wait_for(state="visible", timeout=timeout_ms)
            metrics = page.evaluate(
                """
                () => {
                  const isVisible = (element) => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none'
                      && style.visibility !== 'hidden'
                      && rect.width > 0
                      && rect.height > 0
                      && rect.bottom > 0
                      && rect.top < window.innerHeight;
                  };
                  const labelFor = (element) => (
                    element.innerText
                    || element.getAttribute('aria-label')
                    || element.getAttribute('title')
                    || ''
                  ).trim().replace(/\\s+/g, ' ').slice(0, 80);
                  const selector = [
                    'nav a',
                    'nav button',
                    '.locale-toggle-button',
                    '.clay-button',
                    '.clay-input',
                    'button[class*="rounded-[1.2rem]"]',
                    'a.inline-flex',
                    'button.inline-flex',
                  ].join(',');
                  const controls = Array.from(document.querySelectorAll(selector))
                    .filter((element) => isVisible(element) && labelFor(element))
                    .map((element) => {
                      const rect = element.getBoundingClientRect();
                      return {
                        tag: element.tagName.toLowerCase(),
                        text: labelFor(element),
                        width: rect.width,
                        height: rect.height,
                        left: rect.left,
                        top: rect.top,
                      };
                    });
                  return {
                    scrollWidth: document.documentElement.scrollWidth,
                    viewportWidth: window.innerWidth,
                    tooSmall: controls.filter((item) => item.width < 44 || item.height < 44),
                  };
                }
                """
            )
            if metrics.get("scrollWidth", 0) > metrics.get("viewportWidth", 390) + 2:
                failures.append(f"{route_name}: {path} has horizontal document overflow ({metrics!r})")
            too_small = metrics.get("tooSmall") or []
            if too_small:
                failures.append(f"{route_name}: {path} has controls below 44px touch target ({too_small[:5]!r})")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_billing_portal_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-billing-portal"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    portal_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    portal_route_pattern = "**/subscription/portal"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "pro", "rate_limit": "30/minute"}),
        )

    def fulfill_portal(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        portal_posts.append({"url": request.url, "body": request.post_data or ""})
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"portal_url": _url(base_url, "/pricing?portal=browser-smoke")}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(portal_route_pattern, fulfill_portal)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("pricing-manage-billing-panel").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("pricing-manage-billing").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/pricing.*portal=browser-smoke"), timeout=timeout_ms)

        if len(portal_posts) != 1:
            failures.append(f"{route_name}: expected one billing portal POST, got {len(portal_posts)}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(portal_route_pattern, fulfill_portal)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_pricing_billing_portal_error_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-billing-portal-error-visible"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    portal_posts: list[dict[str, Any]] = []
    tier_route_pattern = "**/subscription/tier"
    portal_route_pattern = "**/subscription/portal"
    error_detail = "Stripe billing portal is not configured for browser smoke."
    expected_resource_error = "the server responded with a status of 503"

    def collect_console(message) -> None:
        if message.type == "error":
            if expected_resource_error in message.text:
                return
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "pro", "rate_limit": "30/minute"}),
        )

    def fulfill_portal(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        portal_posts.append({"url": request.url, "body": request.post_data or ""})
        route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": error_detail}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(tier_route_pattern, fulfill_tier)
    page.route(portal_route_pattern, fulfill_portal)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("pricing-manage-billing-panel").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("pricing-manage-billing").click(timeout=timeout_ms)
        error_notice = page.get_by_test_id("pricing-checkout-error")
        error_notice.wait_for(state="visible", timeout=timeout_ms)
        error_text = error_notice.inner_text(timeout=timeout_ms)
        if error_detail not in error_text:
            failures.append(f"{route_name}: billing portal error notice missing API detail: {error_text!r}")

        if len(portal_posts) != 1:
            failures.append(f"{route_name}: expected one billing portal POST, got {len(portal_posts)}")
        actual_path = _path_from_url(page.url)
        if actual_path != "/pricing":
            failures.append(f"{route_name}: expected to stay on /pricing, got {actual_path}")
        if page.get_by_test_id("pricing-success-panel").count() > 0:
            failures.append(f"{route_name}: error return rendered the success panel")
        if page.get_by_test_id("pricing-checkout-cancelled").count() > 0:
            failures.append(f"{route_name}: error return rendered the cancellation notice")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(tier_route_pattern, fulfill_tier)
        page.unroute(portal_route_pattern, fulfill_portal)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _pricing_authenticated_session_present(page, timeout_ms: int | None = None) -> bool:
    try:
        if timeout_ms:
            page.wait_for_function(
                """() => {
                    const nav = document.querySelector('nav.pricing-page-nav');
                    return Boolean(nav?.querySelector('a[href="/dashboard"], a[href="/login"]'));
                }""",
                timeout=min(timeout_ms, 2000),
            )
        return page.locator('nav.pricing-page-nav a[href="/dashboard"]').count() > 0
    except (PlaywrightTimeoutError, PlaywrightError):
        return False


def _run_pricing_anonymous_paid_redirect_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "pricing-anonymous-paid-redirect"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    checkout_posts: list[dict[str, Any]] = []
    checkout_route_pattern = "**/subscription/checkout"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_checkout(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        checkout_posts.append({"url": request.url, "body": request.post_data or ""})
        route.fulfill(
            status=409,
            content_type="application/json",
            body=json.dumps({"detail": "anonymous users must sign in before checkout"}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(checkout_route_pattern, fulfill_checkout)

    try:
        response = _goto_app_route(page, base_url, "/pricing", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: pricing HTTP status {status}")

        if _pricing_authenticated_session_present(page, timeout_ms):
            failures.append(
                f"{route_name}: frontend is already authenticated; rerun with --expect-dev-auth "
                "or restart the frontend without VITE_ENABLE_DEV_AUTH_BYPASS for anonymous redirect checks"
            )
        else:
            page.get_by_test_id("pricing-pro-cta").click(timeout=timeout_ms)
            page.wait_for_url(re.compile(r".*/login\?.*"), timeout=timeout_ms)

            parsed_url = urlparse(page.url)
            query = parse_qs(parsed_url.query)
            if parsed_url.path.rstrip("/") != "/login":
                failures.append(f"{route_name}: expected /login after anonymous Pro click, got {parsed_url.path}")
            if query.get("next") != ["/pricing"]:
                failures.append(f"{route_name}: expected next=/pricing, got {query.get('next')}")
            if query.get("plan") != ["pro"]:
                failures.append(f"{route_name}: expected plan=pro, got {query.get('plan')}")
            if checkout_posts:
                failures.append(f"{route_name}: anonymous click posted checkout before login: {checkout_posts!r}")
            if page.get_by_test_id("pricing-success-panel").count() > 0:
                failures.append(f"{route_name}: anonymous redirect rendered the checkout success panel")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(checkout_route_pattern, fulfill_checkout)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_upload_form_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "upload-form-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = _goto_app_route(page, base_url, "/upload", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        submit_button = page.get_by_role("button", name=re.compile(r"(IPFS|Store on)")).last
        submit_button.wait_for(state="visible", timeout=timeout_ms)
        if not submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button should be disabled before required fields are ready")

        if not _any_text_visible(
            page,
            ("Submission checklist", "제출 준비 체크리스트"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: submission checklist is not visible")

        upload_fixture = SCRIPT_DIR.parents[2] / "var" / "tmp" / "desci-browser-smoke-upload.pdf"
        upload_fixture.parent.mkdir(parents=True, exist_ok=True)
        upload_fixture.write_bytes(b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF")
        page.locator('main form input[type="file"]').first.set_input_files(str(upload_fixture), timeout=timeout_ms)
        page.locator('main form input[type="checkbox"]').first.check(timeout=timeout_ms)

        if not submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button enabled before title and authors were entered")
        if not _any_text_visible(
            page,
            ("Missing required items", "필수 항목 누락"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing-required status is not visible")

        text_inputs = page.locator('main form input[type="text"]')
        text_inputs.nth(0).fill("Browser smoke submission readiness", timeout=timeout_ms)
        text_inputs.nth(1).fill("QA Researcher", timeout=timeout_ms)

        if submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button stayed disabled after all required fields were ready")
        if not _any_text_visible(
            page,
            ("Ready to submit", "제출 준비 완료"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: ready-to-submit status is not visible")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_protected_mobile_layout_inset_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "protected-mobile-layout-inset"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        page.set_viewport_size({"width": 390, "height": 844})
        response = _goto_app_route(page, base_url, "/upload", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.locator("main h1").first.wait_for(state="visible", timeout=timeout_ms)
        metrics = page.evaluate(
            """
            () => {
              const main = document.querySelector('main');
              const content = main?.querySelector('.mx-auto.flex.w-full.max-w-7xl.flex-1.flex-col');
              const h1 = main?.querySelector('h1');
              const menuButton = Array.from(main?.querySelectorAll('button') || []).find((button) => {
                const rect = button.getBoundingClientRect();
                return rect.y < 130 && rect.x < 120;
              });
              const rectFor = (element) => {
                const rect = element?.getBoundingClientRect();
                return rect ? { left: rect.left, width: rect.width } : null;
              };
              const mainStyle = main ? getComputedStyle(main) : null;
              return {
                mainPaddingLeft: Number.parseFloat(mainStyle?.paddingLeft || '0'),
                mainPaddingRight: Number.parseFloat(mainStyle?.paddingRight || '0'),
                contentLeft: rectFor(content)?.left ?? -1,
                h1Left: rectFor(h1)?.left ?? -1,
                menuLeft: rectFor(menuButton)?.left ?? -1,
                menuWidth: rectFor(menuButton)?.width ?? -1,
              };
            }
            """
        )
        if metrics.get("mainPaddingLeft", 0) < 12 or metrics.get("mainPaddingRight", 0) < 12:
            failures.append(f"{route_name}: mobile main padding collapsed ({metrics!r})")
        if metrics.get("contentLeft", -1) < 12 or metrics.get("h1Left", -1) < 12:
            failures.append(f"{route_name}: mobile content starts too close to viewport edge ({metrics!r})")
        if metrics.get("menuLeft", -1) < 12 or metrics.get("menuWidth", -1) < 40:
            failures.append(f"{route_name}: mobile navigation button collapsed ({metrics!r})")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_upload_submit_receipt_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "upload-submit-receipt"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    upload_posts: list[str] = []
    index_posts: list[str] = []
    job_polls: list[str] = []
    event_streams: list[str] = []
    paper_id = "browser-smoke-receipt-paper"
    cid = f"Qm{'r' * 44}"
    job_id = "upload-smoke-job"
    upload_route_pattern = "**/upload"
    jobs_route_pattern = "**/jobs/**"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_upload(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        upload_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": paper_id,
                    "cid": cid,
                    "ipfs_url": f"https://ipfs.io/ipfs/{cid}",
                }
            ),
        )

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/papers/index" in url:
            index_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": job_id,
                            "type": "paper_index",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper indexing",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(job_id)}(?:[?#].*)?$", url):
            job_polls.append(url)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": job_id,
                        "type": "paper_index",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper index refreshed",
                        "result": {
                            "cid": cid,
                            "ipfs_url": f"https://ipfs.io/ipfs/{cid}",
                        },
                    }
                ),
            )
            return

        route.continue_()

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(upload_route_pattern, fulfill_upload)
    page.route(jobs_route_pattern, fulfill_jobs)

    try:
        response = _goto_app_route(page, base_url, "/upload", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        upload_fixture = SCRIPT_DIR.parents[2] / "var" / "tmp" / "desci-browser-smoke-submit-receipt.pdf"
        upload_fixture.parent.mkdir(parents=True, exist_ok=True)
        upload_fixture.write_bytes(b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF")
        page.locator('main form input[type="file"]').first.set_input_files(str(upload_fixture), timeout=timeout_ms)
        text_inputs = page.locator('main form input[type="text"]')
        text_inputs.nth(0).fill("Browser smoke durable receipt", timeout=timeout_ms)
        text_inputs.nth(1).fill("QA Researcher", timeout=timeout_ms)
        page.locator("main form textarea").first.fill(
            "Smoke check for durable upload receipt after successful indexing.",
            timeout=timeout_ms,
        )
        page.locator('main form input[type="checkbox"]').first.check(timeout=timeout_ms)

        submit_button = page.locator("main form").get_by_role("button").last
        with page.expect_response(lambda response: "/jobs/papers/index" in response.url, timeout=timeout_ms):
            submit_button.click(timeout=timeout_ms)

        receipt = page.get_by_test_id("upload-submission-receipt")
        receipt.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("upload-receipt-ipfs").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("upload-receipt-vault").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("upload-receipt-match").wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_timeout(6000)

        if page.get_by_test_id("upload-submission-receipt").count() != 1:
            failures.append(f"{route_name}: durable receipt disappeared after the previous reset window")

        receipt_role = receipt.get_attribute("role", timeout=timeout_ms)
        if receipt_role != "status":
            failures.append(f"{route_name}: receipt should announce as role=status, got {receipt_role!r}")

        receipt_text = receipt.inner_text(timeout=timeout_ms)
        for expected in (cid, "Open IPFS record", "Research Vault", "Match Studio"):
            if expected not in receipt_text:
                failures.append(f"{route_name}: receipt missing {expected!r}")

        ipfs_href = page.get_by_test_id("upload-receipt-ipfs").get_attribute("href", timeout=timeout_ms)
        if ipfs_href != f"https://ipfs.io/ipfs/{cid}":
            failures.append(f"{route_name}: IPFS receipt href mismatch: {ipfs_href!r}")
        ipfs_rel = set((page.get_by_test_id("upload-receipt-ipfs").get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(ipfs_rel):
            failures.append(f"{route_name}: IPFS receipt link missing safe rel tokens")
        match_href = page.get_by_test_id("upload-receipt-match").get_attribute("href", timeout=timeout_ms) or ""
        if f"paper_id={paper_id}" not in match_href:
            failures.append(f"{route_name}: Match Studio link lost paper_id: {match_href!r}")

        if len(upload_posts) != 1:
            failures.append(f"{route_name}: expected one upload POST, got {len(upload_posts)}")
        if len(index_posts) != 1:
            failures.append(f"{route_name}: expected one paper index job POST, got {len(index_posts)}")
        if len(job_polls) < 1:
            failures.append(f"{route_name}: expected at least one authenticated job poll")
        if event_streams:
            failures.append(f"{route_name}: private upload job opened EventSource unexpectedly")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(upload_route_pattern, fulfill_upload)
        page.unroute(jobs_route_pattern, fulfill_jobs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_upload_submit_wallet_receipt_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "upload-submit-wallet-receipt"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    upload_posts: list[str] = []
    index_posts: list[str] = []
    job_polls: list[str] = []
    mint_posts: list[str] = []
    reward_urls: list[str] = []
    event_streams: list[str] = []
    paper_id = "paper-wallet-receipt"
    cid = f"Qm{'a' * 44}"
    job_id = "upload-wallet-smoke-job"
    mint_tx_hash = f"0x{'c' * 64}"
    reward_tx_hash = f"0x{'d' * 64}"
    upload_route_pattern = "**/upload"
    jobs_route_pattern = "**/jobs/**"
    mint_route_pattern = "**/nft/mint"
    reward_route_pattern = "**/reward/paper**"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_upload(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        upload_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": paper_id,
                    "cid": cid,
                    "ipfs_url": f"https://ipfs.io/ipfs/{cid}",
                }
            ),
        )

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/papers/index" in url:
            index_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": job_id,
                            "type": "paper_index",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper indexing",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(job_id)}(?:[?#].*)?$", url):
            job_polls.append(url)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": job_id,
                        "type": "paper_index",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper index refreshed",
                        "result": {
                            "cid": cid,
                            "ipfs_url": f"https://ipfs.io/ipfs/{cid}",
                        },
                    }
                ),
            )
            return

        route.continue_()

    def fulfill_mint(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        mint_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "tx_hash": mint_tx_hash}),
        )

    def fulfill_reward(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        reward_urls.append(request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "tx_hash": reward_tx_hash}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(upload_route_pattern, fulfill_upload)
    page.route(jobs_route_pattern, fulfill_jobs)
    page.route(mint_route_pattern, fulfill_mint)
    page.route(reward_route_pattern, fulfill_reward)

    try:
        page.add_init_script(
            f"""
            (() => {{
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__desciWalletRequests = [];
              window.ethereum = {{
                request: async (payload) => {{
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_accounts') {{
                    return ['{MOCK_WALLET_ADDRESS}'];
                  }}
                  return null;
                }},
                on: () => undefined,
                removeListener: () => undefined,
              }};
            }})();
            """
        )

        response = _goto_app_route(page, base_url, "/upload", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.wait_for_function(
            "() => (window.__desciWalletRequests || []).some((item) => item.method === 'eth_accounts')",
            timeout=timeout_ms,
        )

        upload_fixture = SCRIPT_DIR.parents[2] / "var" / "tmp" / "desci-browser-smoke-wallet-receipt.pdf"
        upload_fixture.parent.mkdir(parents=True, exist_ok=True)
        upload_fixture.write_bytes(b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF")
        page.locator('main form input[type="file"]').first.set_input_files(str(upload_fixture), timeout=timeout_ms)
        text_inputs = page.locator('main form input[type="text"]')
        text_inputs.nth(0).fill("Browser smoke wallet receipt", timeout=timeout_ms)
        text_inputs.nth(1).fill("QA Wallet Researcher", timeout=timeout_ms)
        page.locator("main form textarea").first.fill(
            "Smoke check for connected-wallet mint and DSCI reward receipt links.",
            timeout=timeout_ms,
        )
        page.locator('main form input[type="checkbox"]').first.check(timeout=timeout_ms)

        submit_button = page.locator("main form").get_by_role("button").last
        with page.expect_response(lambda response: "/jobs/papers/index" in response.url, timeout=timeout_ms):
            submit_button.click(timeout=timeout_ms)

        receipt = page.get_by_test_id("upload-submission-receipt")
        receipt.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("upload-receipt-mint-tx").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("upload-receipt-reward-tx").wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_timeout(6000)

        if page.get_by_test_id("upload-submission-receipt").count() != 1:
            failures.append(f"{route_name}: wallet receipt disappeared after the previous reset window")

        receipt_text = receipt.inner_text(timeout=timeout_ms)
        for expected in (cid, "IP-NFT", "DSCI", "Minting and rewards are complete.", "Match Studio"):
            if expected not in receipt_text:
                failures.append(f"{route_name}: wallet receipt missing {expected!r}")

        mint_href = page.get_by_test_id("upload-receipt-mint-tx").get_attribute("href", timeout=timeout_ms)
        if mint_href != f"https://amoy.polygonscan.com/tx/{mint_tx_hash}":
            failures.append(f"{route_name}: IP-NFT tx href mismatch: {mint_href!r}")
        mint_rel = set((page.get_by_test_id("upload-receipt-mint-tx").get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(mint_rel):
            failures.append(f"{route_name}: IP-NFT tx link missing safe rel tokens")
        reward_href = page.get_by_test_id("upload-receipt-reward-tx").get_attribute("href", timeout=timeout_ms)
        if reward_href != f"https://amoy.polygonscan.com/tx/{reward_tx_hash}":
            failures.append(f"{route_name}: reward tx href mismatch: {reward_href!r}")
        reward_rel = set((page.get_by_test_id("upload-receipt-reward-tx").get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(reward_rel):
            failures.append(f"{route_name}: reward tx link missing safe rel tokens")
        ipfs_href = page.get_by_test_id("upload-receipt-ipfs").get_attribute("href", timeout=timeout_ms)
        if ipfs_href != f"https://ipfs.io/ipfs/{cid}":
            failures.append(f"{route_name}: IPFS receipt href mismatch: {ipfs_href!r}")
        ipfs_rel = set((page.get_by_test_id("upload-receipt-ipfs").get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(ipfs_rel):
            failures.append(f"{route_name}: IPFS receipt link missing safe rel tokens")
        match_href = page.get_by_test_id("upload-receipt-match").get_attribute("href", timeout=timeout_ms) or ""
        if f"paper_id={paper_id}" not in match_href:
            failures.append(f"{route_name}: Match Studio link lost paper_id: {match_href!r}")

        if len(upload_posts) != 1:
            failures.append(f"{route_name}: expected one upload POST, got {len(upload_posts)}")
        if len(index_posts) != 1:
            failures.append(f"{route_name}: expected one paper index job POST, got {len(index_posts)}")
        if len(job_polls) < 1:
            failures.append(f"{route_name}: expected at least one authenticated job poll")
        if len(mint_posts) != 1:
            failures.append(f"{route_name}: expected one mint POST, got {len(mint_posts)}")
        else:
            try:
                payload = json.loads(mint_posts[0])
            except json.JSONDecodeError:
                payload = {}
                failures.append(f"{route_name}: mint POST body was not JSON")
            if payload.get("user_address") != MOCK_WALLET_ADDRESS:
                failures.append(f"{route_name}: mint used wrong user_address: {payload.get('user_address')!r}")
            if payload.get("token_uri") != f"ipfs://{cid}":
                failures.append(f"{route_name}: mint used wrong token_uri: {payload.get('token_uri')!r}")
            consent_hash = payload.get("consent_hash", "")
            if not re.fullmatch(r"0x[a-f0-9]{64}", consent_hash):
                failures.append(f"{route_name}: mint consent_hash is malformed: {consent_hash!r}")
            if not payload.get("consent_timestamp"):
                failures.append(f"{route_name}: mint consent_timestamp is missing")
        if len(reward_urls) != 1:
            failures.append(f"{route_name}: expected one reward POST, got {len(reward_urls)}")
        else:
            reward_query = parse_qs(urlparse(reward_urls[0]).query)
            if reward_query.get("user_address") != [MOCK_WALLET_ADDRESS]:
                failures.append(f"{route_name}: reward used wrong user_address: {reward_query!r}")
        if event_streams:
            failures.append(f"{route_name}: private upload job opened EventSource unexpectedly")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(upload_route_pattern, fulfill_upload)
        page.unroute(jobs_route_pattern, fulfill_jobs)
        page.unroute(mint_route_pattern, fulfill_mint)
        page.unroute(reward_route_pattern, fulfill_reward)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_asset_upload_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "asset-upload-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    upload_posts: list[str] = []
    assets_route_pattern = "**/assets"
    upload_route_pattern = "**/assets/upload"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_assets(route) -> None:
        if route.request.method.upper() != "GET" or route.request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        assets = []
        if upload_posts:
            assets = [
                {
                    "id": "asset-smoke",
                    "filename": "asset-readiness.txt",
                    "original_filename": "asset-readiness.txt",
                    "saved_filename": "asset-smoke.txt",
                    "path": "data/assets/asset-smoke.txt",
                    "type": "patent",
                    "size": 39,
                    "indexed": True,
                    "analysis": {"status": "indexed"},
                }
            ]
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(assets),
        )

    def fulfill_upload(route) -> None:
        if route.request.method.upper() != "POST" or route.request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        upload_posts.append(route.request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": "asset-smoke",
                    "filename": "asset-readiness.txt",
                    "original_filename": "asset-readiness.txt",
                    "saved_filename": "asset-smoke.txt",
                    "path": "data/assets/asset-smoke.txt",
                    "type": "patent",
                    "size": 39,
                    "indexed": True,
                    "analysis": {"status": "indexed"},
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(assets_route_pattern, fulfill_assets)
    page.route(upload_route_pattern, fulfill_upload)

    try:
        response = _goto_app_route(page, base_url, "/assets", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        upload_button = page.get_by_test_id("asset-manager-upload-button")
        upload_button.wait_for(state="visible", timeout=timeout_ms)
        if not upload_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: upload button should be disabled before a file is selected")

        if not _any_text_visible(page, ("Asset upload checklist",), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: upload checklist is not visible")
        if not _any_text_visible(page, ("Missing required items",), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: missing-required status is not visible")

        upload_fixture = SCRIPT_DIR.parents[2] / "var" / "tmp" / "desci-browser-smoke-asset-readiness.txt"
        upload_fixture.parent.mkdir(parents=True, exist_ok=True)
        upload_fixture.write_text("Browser smoke asset readiness fixture", encoding="utf-8")
        page.get_by_test_id("asset-manager-type-select").select_option("patent", timeout=timeout_ms)
        page.get_by_test_id("asset-manager-file-input").set_input_files(str(upload_fixture), timeout=timeout_ms)

        if upload_posts:
            failures.append(f"{route_name}: asset upload POST ran during file selection")
        if upload_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: upload button stayed disabled after a valid file was selected")
        if not _any_text_visible(page, ("Ready to upload",), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: ready-to-upload status is not visible")

        with page.expect_response(lambda response: "/assets/upload" in response.url, timeout=timeout_ms):
            upload_button.click(timeout=timeout_ms)

        if len(upload_posts) != 1:
            failures.append(f"{route_name}: expected one asset upload POST, got {len(upload_posts)}")
        elif "asset_type" not in upload_posts[0] or "patent" not in upload_posts[0]:
            failures.append(f"{route_name}: upload POST body did not include selected patent asset type")
        receipt = page.get_by_test_id("asset-manager-upload-receipt")
        receipt.wait_for(state="visible", timeout=timeout_ms)
        receipt_role = receipt.get_attribute("role", timeout=timeout_ms)
        if receipt_role != "status":
            failures.append(f"{route_name}: upload receipt should announce as role=status, got {receipt_role!r}")
        receipt_atomic = receipt.get_attribute("aria-atomic", timeout=timeout_ms)
        if receipt_atomic != "true":
            failures.append(f"{route_name}: upload receipt should be aria-atomic=true, got {receipt_atomic!r}")
        receipt_text = receipt.inner_text(timeout=timeout_ms)
        if "asset uploaded" not in receipt_text.lower():
            failures.append(f"{route_name}: upload receipt missing asset uploaded heading")
        for expected in ("asset-readiness.txt", "Indexed", "Open VC Portal", "Analyze an RFP"):
            if expected not in receipt_text:
                failures.append(f"{route_name}: upload receipt missing {expected!r}")
        vc_href = receipt.get_by_role("link", name=re.compile(r"(Open VC Portal|VC Portal)")).get_attribute(
            "href", timeout=timeout_ms
        )
        if vc_href != "/vc-portal":
            failures.append(f"{route_name}: VC Portal receipt link mismatch: {vc_href!r}")
        rfp_href = receipt.get_by_role("link", name=re.compile(r"(Analyze an RFP|RFP)")).get_attribute(
            "href", timeout=timeout_ms
        )
        if rfp_href != "/biolinker":
            failures.append(f"{route_name}: RFP receipt link mismatch: {rfp_href!r}")
        page.get_by_text("Saved as asset-smoke.txt").first.wait_for(state="visible", timeout=timeout_ms)

        followup_fixture = SCRIPT_DIR.parents[2] / "var" / "tmp" / "desci-browser-smoke-asset-followup.txt"
        followup_fixture.write_text("Browser smoke asset follow-up fixture", encoding="utf-8")
        page.get_by_test_id("asset-manager-file-input").set_input_files(str(followup_fixture), timeout=timeout_ms)
        page.get_by_text("desci-browser-smoke-asset-followup.txt").wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"asset-manager-upload-receipt\"]') === null",
            timeout=timeout_ms,
        )
        if len(upload_posts) != 1:
            failures.append(f"{route_name}: selecting a follow-up file unexpectedly posted again ({len(upload_posts)} POSTs)")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(assets_route_pattern, fulfill_assets)
        page.unroute(upload_route_pattern, fulfill_upload)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_biolinker_rfp_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "biolinker-rfp-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    analyze_posts: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/analyze" in request.url:
            analyze_posts.append(request.url)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)

    try:
        response = _goto_app_route(page, base_url, "/biolinker", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        analyze_button = page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(적합도 분석|Analyze fit)"),
        ).last
        analyze_button.wait_for(state="visible", timeout=timeout_ms)
        if not analyze_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: analyze button should be disabled before required fields are ready")

        if not _any_text_visible(
            page,
            ("Analysis checklist", "분석 준비 체크리스트"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: analysis checklist is not visible")
        if not _any_text_visible(
            page,
            ("Missing required items", "필수 항목 누락"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing-required status is not visible")

        page.locator("main input.clay-input").first.fill("Joolife Bio", timeout=timeout_ms)
        page.locator("main textarea").first.fill(
            "Funding notice for translational AI drug discovery with clinical validation milestones.",
            timeout=timeout_ms,
        )

        if analyze_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: analyze button stayed disabled after required fields were ready")
        if not _any_text_visible(
            page,
            ("Ready to analyze", "분석 준비 완료"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: ready-to-analyze status is not visible")
        if analyze_posts:
            failures.append(f"{route_name}: analyze POST should not run during readiness check: {analyze_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_biolinker_paper_context_handoff_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "biolinker-paper-context-handoff"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    match_posts: list[str] = []
    event_streams: list[str] = []
    paper_id = "browser-handoff-paper"
    paper_title = "Receipt Handoff Study"
    job_id = "browser-handoff-match-job"
    jobs_route_pattern = "**/jobs/**"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/match/paper" in url:
            match_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": job_id,
                            "type": "paper_match",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper matching",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": job_id,
                        "type": "paper_match",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper matching complete",
                        "result": {
                            "matches": [
                                {
                                    "id": "rfp-browser-handoff",
                                    "metadata": {
                                        "title": "Translational AI Grant",
                                        "source": "KDDF",
                                        "keywords": "AI,clinical",
                                    },
                                    "document": "Funding opportunity for translational AI validation.",
                                    "similarity": 0.91,
                                }
                            ]
                        },
                    }
                ),
            )
            return

        route.continue_()

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(jobs_route_pattern, fulfill_jobs)

    try:
        response = _goto_app_route(
            page,
            base_url,
            f"/biolinker?paper_id={paper_id}&paper_title=Receipt%20Handoff%20Study",
            timeout_ms,
        )
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("biolinker-paper-context").wait_for(state="visible", timeout=timeout_ms)
        context_title = page.get_by_test_id("biolinker-paper-context-title").inner_text(timeout=timeout_ms)
        if context_title != paper_title:
            failures.append(f"{route_name}: paper context title mismatch: {context_title!r}")
        context_id = page.get_by_test_id("biolinker-paper-context-id").inner_text(timeout=timeout_ms)
        if context_id != paper_id:
            failures.append(f"{route_name}: paper context id mismatch: {context_id!r}")

        page.get_by_text("Translational AI Grant").first.wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_timeout(1000)

        if len(match_posts) != 1:
            failures.append(f"{route_name}: expected one paper match job POST, got {len(match_posts)}")
        elif f'"paper_id":"{paper_id}"' not in match_posts[0]:
            failures.append(f"{route_name}: paper match POST lost paper_id: {match_posts[0]!r}")
        if event_streams:
            failures.append(f"{route_name}: private paper match opened EventSource unexpectedly")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(jobs_route_pattern, fulfill_jobs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_biolinker_proposal_clipboard_failure_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "biolinker-proposal-clipboard-failure"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    match_posts: list[str] = []
    proposal_posts: list[str] = []
    paper_upload_posts: list[str] = []
    paper_index_posts: list[str] = []
    event_streams: list[str] = []
    paper_id = "browser-proposal-paper"
    paper_title = "Proposal Smoke Study"
    rfp_id = "rfp-browser-proposal"
    match_job_id = "browser-proposal-match-job"
    proposal_job_id = "browser-proposal-generate-job"
    paper_upload_id = "browser-proposal-source-package"
    paper_upload_cid = f"Qm{'p' * 44}"
    paper_index_job_id = "browser-proposal-source-package-index-job"
    draft = "# Proposal Draft\n\nFund translational AI validation with milestone-based reporting."
    critique = "## Review\n\nStrong fit with measurable validation milestones."
    missing_evidence = "Budget narrative"
    jobs_route_pattern = "**/jobs/**"
    paper_upload_route_pattern = re.compile(r"^https?://[^/]+/upload(?:[?#].*)?$")
    assets_route_pattern = "**/assets"
    asset_upload_route_pattern = "**/assets/upload"
    asset_upload_posts: list[str] = []
    smoke_paper_path = SCRIPT_DIR.parent / ".tmp" / "proposal-evidence-browser-smoke.pdf"
    smoke_asset_path = SCRIPT_DIR.parent / ".tmp" / "proposal-evidence-browser-smoke.txt"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/match/paper" in url:
            match_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": match_job_id,
                            "type": "paper_match",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper matching",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(match_job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": match_job_id,
                        "type": "paper_match",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper matching complete",
                        "result": {
                            "matches": [
                                {
                                    "id": rfp_id,
                                    "metadata": {
                                        "title": "Proposal Export Grant",
                                        "source": "KDDF",
                                        "keywords": "AI,clinical",
                                    },
                                    "document": "Funding opportunity for translational AI validation.",
                                    "similarity": 0.94,
                                }
                            ]
                        },
                    }
                ),
            )
            return

        if method == "POST" and "/jobs/proposal/generate" in url:
            proposal_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": proposal_job_id,
                            "type": "proposal_generate",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued proposal generation",
                        }
                    }
                ),
            )
            return

        if method == "POST" and "/jobs/papers/index" in url:
            paper_index_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": paper_index_job_id,
                            "type": "paper_index",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper indexing",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(proposal_job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": proposal_job_id,
                        "type": "proposal_generate",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Proposal generated",
                            "result": {
                                "draft": draft,
                                "critique": critique,
                                "missing_evidence": [missing_evidence],
                                "supporting_evidence_assets": [
                                    {
                                        "id": "asset-budget",
                                        "filename": "budget-narrative.txt",
                                        "type": "paper",
                                        "indexed": True,
                                        "missing_evidence": [missing_evidence],
                                        "evidence_origin": "asset_library",
                                        "source_label": "Asset Library",
                                        "source_route": "/assets",
                                    }
                                ],
                            },
                        }
                    ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(paper_index_job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": paper_index_job_id,
                        "type": "paper_index",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper index refreshed",
                        "result": {
                            "cid": paper_upload_cid,
                            "ipfs_url": f"https://ipfs.io/ipfs/{paper_upload_cid}",
                        },
                    }
                ),
            )
            return

        route.continue_()

    def fulfill_paper_upload(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        post_data = request.post_data or ""
        paper_upload_posts.append(post_data)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": paper_upload_id,
                    "cid": paper_upload_cid,
                    "ipfs_url": f"https://ipfs.io/ipfs/{paper_upload_cid}",
                    "proposal_evidence_context": {
                        "from_proposal": True,
                        "rfp_title": "Proposal Export Grant",
                        "missing_evidence": [missing_evidence],
                    },
                }
            ),
        )

    def fulfill_assets(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        if request.method.upper() == "GET":
            route.fulfill(status=200, content_type="application/json", body=json.dumps([]))
            return
        route.continue_()

    def fulfill_asset_upload(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        if request.method.upper() == "POST":
            post_data = request.post_data or ""
            asset_upload_posts.append(post_data)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": "asset-browser-proposal-evidence",
                        "filename": "proposal-evidence-browser-smoke.txt",
                        "original_filename": "proposal-evidence-browser-smoke.txt",
                        "saved_filename": "asset-browser-proposal-evidence.txt",
                        "type": "paper",
                        "indexed": True,
                        "analysis": {"status": "indexed"},
                        "proposal_evidence_context": {
                            "from_proposal": True,
                            "rfp_title": "Proposal Export Grant",
                            "missing_evidence": [missing_evidence],
                        },
                    }
                ),
            )
            return
        route.continue_()

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(jobs_route_pattern, fulfill_jobs)
    page.route(paper_upload_route_pattern, fulfill_paper_upload)
    page.route(assets_route_pattern, fulfill_assets)
    page.route(asset_upload_route_pattern, fulfill_asset_upload)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.sessionStorage.setItem('desci:biolinker-notice-import', JSON.stringify({
                from_notice: true,
                rfp_title: 'Proposal Evidence Grant',
                rfp_source: 'KDDF',
                rfp_text: 'Funding opportunity for translational AI validation.',
                deadline_status: 'urgent',
                deadline_label: 'Urgent',
                readiness_score: 82,
                evidence_to_prepare: ['Research plan', 'Budget narrative'],
                risk_flags: ['Confirm eligibility.'],
                submission_timeline: ['Day 0: confirm eligibility.'],
              }));
              window.__proposalClipboardAttempts = 0;
              window.__proposalUnhandledRejections = [];
              window.addEventListener('unhandledrejection', (event) => {
                window.__proposalUnhandledRejections.push(String(event.reason || 'unknown rejection'));
              });
              Object.defineProperty(navigator, 'clipboard', {
                configurable: true,
                value: {
                  writeText: async () => {
                    window.__proposalClipboardAttempts += 1;
                    throw new DOMException('clipboard denied by browser smoke', 'NotAllowedError');
                  },
                },
              });
            })();
            """
        )

        response = _goto_app_route(
            page,
            base_url,
            f"/biolinker?paper_id={paper_id}&paper_title=Proposal%20Smoke%20Study",
            timeout_ms,
        )
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("biolinker-paper-context").wait_for(state="visible", timeout=timeout_ms)
        context_title = page.get_by_test_id("biolinker-paper-context-title").inner_text(timeout=timeout_ms)
        if context_title != paper_title:
            failures.append(f"{route_name}: paper context title mismatch: {context_title!r}")
        context_id = page.get_by_test_id("biolinker-paper-context-id").inner_text(timeout=timeout_ms)
        if context_id != paper_id:
            failures.append(f"{route_name}: paper context id mismatch: {context_id!r}")
        page.get_by_text("Proposal Export Grant").first.wait_for(state="visible", timeout=timeout_ms)
        page.locator("main").get_by_role("button", name=re.compile(r"Proposal Export Grant")).first.click(
            timeout=timeout_ms
        )
        page.get_by_test_id("proposal-view-modal").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Fund translational AI validation").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("proposal-supporting-evidence").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("budget-narrative.txt").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Asset Library").first.wait_for(state="visible", timeout=timeout_ms)
        supporting_asset_link = page.get_by_test_id("proposal-supporting-evidence-link-asset-budget")
        if supporting_asset_link.get_attribute("href", timeout=timeout_ms) != "/assets":
            failures.append(f"{route_name}: supporting evidence source link href mismatch")
        page.get_by_test_id("proposal-missing-evidence").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text(missing_evidence).first.wait_for(state="visible", timeout=timeout_ms)
        upload_href = page.get_by_test_id("proposal-evidence-upload-link").get_attribute(
            "href",
            timeout=timeout_ms,
        )
        assets_href = page.get_by_test_id("proposal-evidence-assets-link").get_attribute(
            "href",
            timeout=timeout_ms,
        )
        if upload_href != "/upload":
            failures.append(f"{route_name}: evidence upload link href mismatch: {upload_href!r}")
        if assets_href != "/assets":
            failures.append(f"{route_name}: evidence assets link href mismatch: {assets_href!r}")

        page.get_by_test_id("proposal-copy-all").click(timeout=timeout_ms)
        page.get_by_text("Could not copy the proposal. Check browser clipboard permissions.").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )

        clipboard_attempts = page.evaluate("() => window.__proposalClipboardAttempts || 0")
        if clipboard_attempts != 1:
            failures.append(f"{route_name}: expected one clipboard attempt, got {clipboard_attempts!r}")
        unhandled_rejections = page.evaluate("() => window.__proposalUnhandledRejections || []")
        if unhandled_rejections:
            failures.append(f"{route_name}: clipboard failure created unhandled rejections: {unhandled_rejections!r}")

        if len(match_posts) != 1:
            failures.append(f"{route_name}: expected one paper match job POST, got {len(match_posts)}")
        elif f'"paper_id":"{paper_id}"' not in match_posts[0]:
            failures.append(f"{route_name}: paper match POST lost paper_id: {match_posts[0]!r}")
        if len(proposal_posts) != 1:
            failures.append(f"{route_name}: expected one proposal job POST, got {len(proposal_posts)}")
        else:
            try:
                payload = json.loads(proposal_posts[0])
            except json.JSONDecodeError:
                payload = {}
                failures.append(f"{route_name}: proposal POST body was not JSON")
            if payload.get("paper_id") != paper_id:
                failures.append(f"{route_name}: proposal POST used wrong paper_id: {payload.get('paper_id')!r}")
            if payload.get("rfp_id") != rfp_id:
                failures.append(f"{route_name}: proposal POST used wrong rfp_id: {payload.get('rfp_id')!r}")
            notice_context = payload.get("notice_context")
            if not isinstance(notice_context, dict):
                failures.append(f"{route_name}: proposal POST missing notice_context: {payload!r}")
            else:
                expected_context = {
                    "title": "Proposal Evidence Grant",
                    "source": "KDDF",
                    "deadline_status": "urgent",
                    "deadline_label": "Urgent",
                    "readiness_score": 82,
                    "evidence_to_prepare": ["Research plan", "Budget narrative"],
                    "risk_flags": ["Confirm eligibility."],
                    "submission_timeline": ["Day 0: confirm eligibility."],
                }
                for key, expected_value in expected_context.items():
                    if notice_context.get(key) != expected_value:
                        failures.append(
                            f"{route_name}: proposal notice_context {key} mismatch: {notice_context.get(key)!r}"
                        )
        if event_streams:
            failures.append(f"{route_name}: private proposal flow opened EventSource unexpectedly")

        page.get_by_test_id("proposal-evidence-upload-link").click(timeout=timeout_ms)
        page.get_by_test_id("upload-proposal-evidence-handoff").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Proposal Export Grant").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text(missing_evidence).first.wait_for(state="visible", timeout=timeout_ms)
        upload_assets_href = page.get_by_test_id("upload-proposal-evidence-assets-link").get_attribute(
            "href",
            timeout=timeout_ms,
        )
        if upload_assets_href != "/assets":
            failures.append(f"{route_name}: upload handoff assets link href mismatch: {upload_assets_href!r}")

        smoke_paper_path.parent.mkdir(parents=True, exist_ok=True)
        smoke_paper_path.write_bytes(b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF")
        page.locator('main form input[type="file"]').first.set_input_files(str(smoke_paper_path), timeout=timeout_ms)
        text_inputs = page.locator('main form input[type="text"]')
        text_inputs.nth(0).fill("Browser smoke sponsor package", timeout=timeout_ms)
        text_inputs.nth(1).fill("QA Researcher", timeout=timeout_ms)
        page.locator("main form textarea").first.fill(
            "Original sponsor notice and budget narrative package for browser smoke.",
            timeout=timeout_ms,
        )
        page.locator('main form input[type="checkbox"]').first.check(timeout=timeout_ms)
        with page.expect_response(lambda response: "/jobs/papers/index" in response.url, timeout=timeout_ms):
            page.locator("main form").get_by_role("button").last.click(timeout=timeout_ms)
        page.get_by_test_id("upload-submission-receipt").wait_for(state="visible", timeout=timeout_ms)

        if len(paper_upload_posts) != 1:
            failures.append(f"{route_name}: expected one paper evidence upload POST, got {len(paper_upload_posts)}")
        else:
            paper_upload_post = paper_upload_posts[0]
            if "proposal_evidence_context" not in paper_upload_post:
                failures.append(f"{route_name}: paper upload POST missing proposal_evidence_context")
            if missing_evidence not in paper_upload_post:
                failures.append(f"{route_name}: paper upload POST missing evidence item")
        if len(paper_index_posts) != 1:
            failures.append(f"{route_name}: expected one paper evidence index job POST, got {len(paper_index_posts)}")
        elif paper_upload_id not in paper_index_posts[0]:
            failures.append(f"{route_name}: paper evidence index POST lost uploaded paper id: {paper_index_posts[0]!r}")

        page.get_by_test_id("upload-proposal-evidence-assets-link").click(timeout=timeout_ms)
        asset_handoff = page.get_by_test_id("asset-manager-proposal-evidence-handoff")
        asset_handoff.wait_for(state="visible", timeout=timeout_ms)
        asset_handoff.get_by_text("Proposal Export Grant").first.wait_for(state="visible", timeout=timeout_ms)
        asset_handoff.get_by_text(missing_evidence).first.wait_for(state="visible", timeout=timeout_ms)
        asset_upload_href = page.get_by_test_id("asset-manager-proposal-evidence-upload-link").get_attribute(
            "href",
            timeout=timeout_ms,
        )
        if asset_upload_href != "/upload":
            failures.append(f"{route_name}: asset handoff upload link href mismatch: {asset_upload_href!r}")
        selected_asset_type = page.get_by_test_id("asset-manager-type-select").input_value(timeout=timeout_ms)
        if selected_asset_type != "paper":
            failures.append(f"{route_name}: asset handoff selected type mismatch: {selected_asset_type!r}")

        smoke_asset_path.parent.mkdir(parents=True, exist_ok=True)
        smoke_asset_path.write_text("Budget narrative evidence for browser smoke.", encoding="utf-8")
        page.get_by_test_id("asset-manager-file-input").set_input_files(str(smoke_asset_path), timeout=timeout_ms)
        page.get_by_test_id("asset-manager-upload-button").click(timeout=timeout_ms)
        page.get_by_test_id("asset-manager-upload-receipt-evidence").wait_for(state="visible", timeout=timeout_ms)
        if len(asset_upload_posts) != 1:
            failures.append(f"{route_name}: expected one asset evidence upload POST, got {len(asset_upload_posts)}")
        else:
            asset_post = asset_upload_posts[0]
            if "proposal_evidence_context" not in asset_post:
                failures.append(f"{route_name}: asset upload POST missing proposal_evidence_context")
            if "Budget narrative" not in asset_post:
                failures.append(f"{route_name}: asset upload POST missing evidence item")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(jobs_route_pattern, fulfill_jobs)
        page.unroute(paper_upload_route_pattern, fulfill_paper_upload)
        page.unroute(assets_route_pattern, fulfill_assets)
        page.unroute(asset_upload_route_pattern, fulfill_asset_upload)
        try:
            smoke_paper_path.unlink()
        except OSError:
            pass
        try:
            smoke_asset_path.unlink()
        except OSError:
            pass

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_biolinker_proposal_export_popup_blocked_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "biolinker-proposal-export-popup-blocked"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    match_posts: list[str] = []
    proposal_posts: list[str] = []
    event_streams: list[str] = []
    paper_id = "browser-proposal-export-paper"
    rfp_id = "rfp-browser-proposal-export"
    match_job_id = "browser-proposal-export-match-job"
    proposal_job_id = "browser-proposal-export-generate-job"
    draft = "# Export Proposal Draft\n\nPrepare a printable proposal for translational AI validation.\n\n<img src=x onerror=alert(1)>"
    critique = "## Review\n\nExport-ready after operator review.\n\n<script>alert(2)</script>"
    jobs_route_pattern = "**/jobs/**"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/match/paper" in url:
            match_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": match_job_id,
                            "type": "paper_match",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper matching",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(match_job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": match_job_id,
                        "type": "paper_match",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper matching complete",
                        "result": {
                            "matches": [
                                {
                                    "id": rfp_id,
                                    "metadata": {
                                        "title": "Printable <script>Proposal</script> Grant",
                                        "source": "KDDF",
                                        "keywords": "AI,export",
                                    },
                                    "document": "Funding opportunity requiring a shareable proposal draft.",
                                    "similarity": 0.93,
                                }
                            ]
                        },
                    }
                ),
            )
            return

        if method == "POST" and "/jobs/proposal/generate" in url:
            proposal_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": proposal_job_id,
                            "type": "proposal_generate",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued proposal generation",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(proposal_job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": proposal_job_id,
                        "type": "proposal_generate",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Proposal generated",
                        "result": {
                            "draft": draft,
                            "critique": critique,
                        },
                    }
                ),
            )
            return

        route.continue_()

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(jobs_route_pattern, fulfill_jobs)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__proposalExportMode = 'capture';
              window.__proposalExportOpens = [];
              window.__proposalExportWrittenHtml = '';
              window.__proposalExportPrints = 0;
              window.__proposalExportUnhandledRejections = [];
              window.addEventListener('unhandledrejection', (event) => {
                window.__proposalExportUnhandledRejections.push(String(event.reason || 'unknown rejection'));
              });
              window.open = (url, target, features) => {
                window.__proposalExportOpens.push({ url: url || '', target: target || '', features: features || '' });
                if (window.__proposalExportMode === 'blocked') {
                  return null;
                }
                return {
                  document: {
                    open: () => {},
                    write: (html) => {
                      window.__proposalExportWrittenHtml += String(html || '');
                    },
                    close: () => {},
                  },
                  focus: () => {},
                  print: () => {
                    window.__proposalExportPrints += 1;
                  },
                };
              };
            })();
            """
        )

        response = _goto_app_route(
            page,
            base_url,
            f"/biolinker?paper_id={paper_id}&paper_title=Proposal%20Export%20Study",
            timeout_ms,
        )
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("biolinker-paper-context").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Printable", exact=False).first.wait_for(state="visible", timeout=timeout_ms)
        page.locator("main").get_by_role("button", name=re.compile(r"Printable")).first.click(
            timeout=timeout_ms
        )
        page.get_by_test_id("proposal-view-modal").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Prepare a printable proposal").first.wait_for(state="visible", timeout=timeout_ms)

        page.get_by_test_id("proposal-export-pdf").click(timeout=timeout_ms)
        page.get_by_text("Opened the print window. Save it as PDF.").first.wait_for(state="visible", timeout=timeout_ms)
        written_html = page.evaluate("() => window.__proposalExportWrittenHtml || ''")
        if "&lt;script&gt;Proposal&lt;/script&gt;" not in written_html:
            failures.append(f"{route_name}: exported title was not HTML-escaped")
        if "&lt;img src=x onerror=alert(1)&gt;" not in written_html:
            failures.append(f"{route_name}: exported draft body was not HTML-escaped")
        if "<script>" in written_html or "<img src=x onerror=alert(1)>" in written_html:
            failures.append(f"{route_name}: exported popup HTML retained executable markup")
        page.wait_for_timeout(650)
        print_attempts = page.evaluate("() => window.__proposalExportPrints || 0")
        if print_attempts != 1:
            failures.append(f"{route_name}: expected one successful popup print attempt, got {print_attempts!r}")

        page.evaluate("() => { window.__proposalExportMode = 'blocked'; }")
        page.get_by_test_id("proposal-export-pdf").click(timeout=timeout_ms)
        page.get_by_text("Please allow pop-ups and try again.").first.wait_for(state="visible", timeout=timeout_ms)

        opens = page.evaluate("() => window.__proposalExportOpens || []")
        if len(opens) != 2:
            failures.append(f"{route_name}: expected one captured and one blocked window.open call, got {opens!r}")
        else:
            for index, opened in enumerate(opens):
                open_target = str(opened.get("target", ""))
                open_features = str(opened.get("features", ""))
                if open_target != "_blank":
                    failures.append(f"{route_name}: export popup target mismatch at open {index}: {open_target!r}")
                if "noopener" not in open_features or "noreferrer" not in open_features:
                    failures.append(
                        f"{route_name}: export popup features missing safe flags at open {index}: {open_features!r}"
                    )
        unhandled_rejections = page.evaluate("() => window.__proposalExportUnhandledRejections || []")
        if unhandled_rejections:
            failures.append(f"{route_name}: popup block created unhandled rejections: {unhandled_rejections!r}")

        if len(match_posts) != 1:
            failures.append(f"{route_name}: expected one paper match job POST, got {len(match_posts)}")
        elif f'"paper_id":"{paper_id}"' not in match_posts[0]:
            failures.append(f"{route_name}: paper match POST lost paper_id: {match_posts[0]!r}")
        if len(proposal_posts) != 1:
            failures.append(f"{route_name}: expected one proposal job POST, got {len(proposal_posts)}")
        else:
            try:
                payload = json.loads(proposal_posts[0])
            except json.JSONDecodeError:
                payload = {}
                failures.append(f"{route_name}: proposal POST body was not JSON")
            if payload.get("paper_id") != paper_id:
                failures.append(f"{route_name}: proposal POST used wrong paper_id: {payload.get('paper_id')!r}")
            if payload.get("rfp_id") != rfp_id:
                failures.append(f"{route_name}: proposal POST used wrong rfp_id: {payload.get('rfp_id')!r}")
        if event_streams:
            failures.append(f"{route_name}: private proposal export flow opened EventSource unexpectedly")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(jobs_route_pattern, fulfill_jobs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_biolinker_empty_match_next_actions_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "biolinker-empty-match-next-actions"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    match_posts: list[str] = []
    event_streams: list[str] = []
    paper_id = "browser-empty-match-paper"
    paper_title = "Empty Match Study"
    job_id = "browser-empty-match-job"
    jobs_route_pattern = "**/jobs/**"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_jobs(route) -> None:
        request = route.request
        if request.resource_type not in {"fetch", "xhr", "eventsource"}:
            route.continue_()
            return

        url = request.url
        method = request.method.upper()
        if "/events" in url:
            event_streams.append(url)
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "unexpected SSE"}))
            return

        if method == "POST" and "/jobs/match/paper" in url:
            match_posts.append(request.post_data or "")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "job": {
                            "id": job_id,
                            "type": "paper_match",
                            "status": "queued",
                            "progress": 0,
                            "message": "Queued paper matching",
                        }
                    }
                ),
            )
            return

        if method == "GET" and re.search(rf"/jobs/{re.escape(job_id)}(?:[?#].*)?$", url):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "id": job_id,
                        "type": "paper_match",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Paper matching complete",
                        "result": {"matches": []},
                    }
                ),
            )
            return

        route.continue_()

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(jobs_route_pattern, fulfill_jobs)

    try:
        response = _goto_app_route(
            page,
            base_url,
            f"/biolinker?paper_id={paper_id}&paper_title=Empty%20Match%20Study",
            timeout_ms,
        )
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("biolinker-paper-context").wait_for(state="visible", timeout=timeout_ms)
        context_title = page.get_by_test_id("biolinker-paper-context-title").inner_text(timeout=timeout_ms)
        if context_title != paper_title:
            failures.append(f"{route_name}: paper context title mismatch: {context_title!r}")

        page.get_by_test_id("biolinker-empty-title").wait_for(state="visible", timeout=timeout_ms)
        empty_title = page.get_by_test_id("biolinker-empty-title").inner_text(timeout=timeout_ms)
        if "No funding matches yet" not in empty_title:
            failures.append(f"{route_name}: empty title mismatch: {empty_title!r}")

        notices_link = page.get_by_test_id("biolinker-empty-open-notices")
        notices_href = notices_link.get_attribute("href", timeout=timeout_ms)
        if notices_href != "/notices":
            failures.append(f"{route_name}: Funding Radar link href mismatch: {notices_href!r}")

        page.get_by_test_id("biolinker-empty-use-rfp-analysis").click(timeout=timeout_ms)
        page.locator("main textarea").first.wait_for(state="visible", timeout=timeout_ms)
        if page.locator("main input.clay-input").count() < 2 or page.locator("main textarea").count() < 1:
            failures.append(f"{route_name}: RFP Analysis panel was not visible after empty-state CTA")

        if len(match_posts) != 1:
            failures.append(f"{route_name}: expected one paper match job POST, got {len(match_posts)}")
        elif f'"paper_id":"{paper_id}"' not in match_posts[0]:
            failures.append(f"{route_name}: paper match POST lost paper_id: {match_posts[0]!r}")
        if event_streams:
            failures.append(f"{route_name}: private paper match opened EventSource unexpectedly")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(jobs_route_pattern, fulfill_jobs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_notices_biolinker_bridge_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "notices-biolinker-bridge"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    analyze_posts: list[str] = []
    notices_route_pattern = "**/notices?*"
    fixture_body = "Bridge notice body for translational AI drug discovery milestones."

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/analyze" in request.url:
            analyze_posts.append(request.url)

    def fulfill_notices(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-notice-bridge",
                        "title": "Bridge AI Drug Discovery Grant",
                        "source": "KDDF",
                        "body_text": fixture_body,
                        "budget_range": "$250K-$500K",
                        "deadline": "2026-09-30",
                        "keywords": ["AI drug discovery", "translational research"],
                        "url": "https://example.org/bridge-ai-drug-discovery",
                    }
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)
    page.route(notices_route_pattern, fulfill_notices)

    try:
        response = _goto_app_route(page, base_url, "/notices", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_text("Bridge AI Drug Discovery Grant").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("notices-analyze-browser-smoke-notice-bridge").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/biolinker$"), timeout=timeout_ms)
        page.get_by_test_id("biolinker-imported-notice").wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_function(
            "(expected) => Array.from(document.querySelectorAll('main textarea')).some((node) => node.value === expected)",
            arg=fixture_body,
            timeout=timeout_ms,
        )

        if not _any_text_visible(
            page,
            ("Funding Radar notice loaded", "펀딩 공고를 불러왔습니다"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: imported notice context is not visible")
        if not _any_text_visible(
            page,
            ("Bridge AI Drug Discovery Grant",),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: imported notice title is not visible")
        textarea_values = page.locator("main textarea").evaluate_all("(nodes) => nodes.map((node) => node.value)")
        if fixture_body not in textarea_values:
            failures.append(f"{route_name}: imported notice body was not loaded into an RFP textarea")

        analyze_button = page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(Analyze fit|적합도 분석)"),
        ).last
        analyze_button.wait_for(state="visible", timeout=timeout_ms)
        if not analyze_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: analyze button should stay disabled until organization is entered")
        if analyze_posts:
            failures.append(f"{route_name}: analyze POST should not run during bridge check: {analyze_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)
        page.unroute(notices_route_pattern, fulfill_notices)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_notices_discovery_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "notices-discovery-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    discover_posts: list[str] = []
    notices_route_pattern = "**/notices?*"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/discover/grants" in request.url:
            discover_posts.append(request.url)

    def fulfill_notices(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-discovery-readiness",
                        "title": "Discovery Readiness Grant",
                        "source": "KDDF",
                        "body_text": "Browser smoke notice for discovery readiness validation.",
                        "budget_range": "$100K-$250K",
                        "deadline": "2026-10-31",
                        "keywords": ["grant discovery", "readiness"],
                        "url": "https://example.org/discovery-readiness",
                    }
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)
    page.route(notices_route_pattern, fulfill_notices)

    try:
        response = _goto_app_route(page, base_url, "/notices", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        discover_button = page.get_by_test_id("notices-discover-button")
        discover_button.wait_for(state="visible", timeout=timeout_ms)
        if not discover_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: discover button should be disabled before research context is entered")
        if not _any_text_visible(
            page,
            ("Discovery checklist",),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: discovery checklist is not visible")
        if not _any_text_visible(
            page,
            ("Missing research context",),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing-context status is not visible")

        page.locator("main textarea").first.fill(
            "Browser smoke grant discovery context for translational AI research.",
            timeout=timeout_ms,
        )
        if discover_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: discover button stayed disabled after research context was entered")
        if not _any_text_visible(
            page,
            ("Ready to discover",),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: ready-to-discover status is not visible")
        if discover_posts:
            failures.append(f"{route_name}: discover POST should not run during readiness check: {discover_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)
        page.unroute(notices_route_pattern, fulfill_notices)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_notices_discovery_biolinker_handoff_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "notices-discovery-biolinker-handoff"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    discover_posts: list[str] = []
    analyze_posts: list[dict[str, object]] = []
    notices_route_pattern = "**/notices?*"
    discover_route_pattern = "**/discover/grants"
    analyze_route_pattern = "**/analyze"
    fixture_context = "Browser smoke grant discovery context for closed translational AI research."
    fixture_title = "Closed Discovery Handoff Grant"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/analyze" in request.url:
            try:
                analyze_posts.append(json.loads(request.post_data or "{}"))
            except json.JSONDecodeError:
                analyze_posts.append({"raw": request.post_data or ""})

    def fulfill_notices(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-discovery-handoff-source",
                        "title": "Discovery Handoff Source Notice",
                        "source": "NIH",
                        "body_text": "Browser smoke source notice for discovery handoff validation.",
                        "deadline": "2026-08-01",
                        "keywords": ["handoff", "closed"],
                        "url": "https://example.org/discovery-handoff-source",
                    }
                ]
            ),
        )

    def fulfill_discover(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        discover_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "opportunities": [
                        {
                            "id": "browser-discovery-handoff",
                            "title": fixture_title,
                            "source": "NIH",
                            "score": 0.79,
                            "rationale": ["Strong scientific fit, but the current notice is closed."],
                            "url": "https://example.org/discovery-handoff",
                            "application_brief": {
                                "readiness_score": 25,
                                "deadline_status": "closed",
                                "fit_summary": "Useful historical sponsor context only.",
                                "evidence_to_prepare": ["Renewed notice confirmation"],
                                "risk_flags": ["Deadline has already passed."],
                                "submission_timeline": ["Find renewed FOA before submission."],
                            },
                        }
                    ],
                    "research_signals": {"concepts": ["Closed grant context"]},
                }
            ),
        )

    def fulfill_analyze(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "rfp": {
                        "id": "browser-discovery-handoff",
                        "title": fixture_title,
                        "source": "NIH",
                        "body_text": "Closed handoff grant body.",
                        "keywords": ["closed", "handoff"],
                    },
                    "result": {
                        "fit_score": 86,
                        "fit_grade": "A",
                        "match_summary": ["Structured Funding Radar context reached analysis."],
                        "required_docs": ["Renewed notice confirmation"],
                        "risk_flags": ["Deadline has already passed."],
                        "recommended_actions": ["Find renewed FOA before submission."],
                    },
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)
    page.route(notices_route_pattern, fulfill_notices)
    page.route(discover_route_pattern, fulfill_discover)
    page.route(analyze_route_pattern, fulfill_analyze)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.sessionStorage.removeItem('desci:biolinker-notice-import');
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/notices", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.locator("main textarea").first.fill(fixture_context, timeout=timeout_ms)
        page.get_by_test_id("notices-discover-button").click(timeout=timeout_ms)
        page.get_by_text(fixture_title).first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("notices-deadline-status-browser-discovery-handoff").wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        page.get_by_test_id("notices-deadline-warning-browser-discovery-handoff").wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        page.get_by_test_id("notices-discovery-analyze-browser-discovery-handoff").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/biolinker$"), timeout=timeout_ms)

        imported_context = page.get_by_test_id("biolinker-imported-notice-context")
        imported_context.wait_for(state="visible", timeout=timeout_ms)
        context_text = imported_context.inner_text(timeout=timeout_ms)
        normalized_context_text = context_text.lower()
        for expected in (
            "Imported analysis context",
            "Deadline status: Closed",
            "Submission readiness: 25%",
            "Risk flags",
            "Deadline has already passed.",
            "Evidence to prepare",
            "Renewed notice confirmation",
            "Submission timeline",
            "Find renewed FOA before submission.",
        ):
            if expected.lower() not in normalized_context_text:
                failures.append(f"{route_name}: imported context missing {expected!r}: {context_text!r}")

        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('main textarea')).some((node) =>
              node.value.includes('Deadline status: Closed') &&
              node.value.includes('Risk flags:\\n- Deadline has already passed.')
            )
            """,
            timeout=timeout_ms,
        )
        stored_import = page.evaluate("() => window.sessionStorage.getItem('desci:biolinker-notice-import')")
        if stored_import is not None:
            failures.append(f"{route_name}: notice import session storage was not cleared after BioLinker load")
        if len(discover_posts) != 1:
            failures.append(f"{route_name}: expected one /discover/grants POST, got {len(discover_posts)}")
        elif fixture_context not in discover_posts[0]:
            failures.append(f"{route_name}: discovery POST lost research context: {discover_posts[0]!r}")
        if analyze_posts:
            failures.append(f"{route_name}: analyze POST ran before operator clicked Analyze fit: {analyze_posts[0]!r}")

        page.locator("main input.clay-input").first.fill("Joolife Bio", timeout=timeout_ms)
        page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(Analyze fit|적합도 분석)"),
        ).last.click(timeout=timeout_ms)
        page.wait_for_function(
            "() => document.body.innerText.includes('86') && document.body.innerText.includes('A')",
            timeout=timeout_ms,
        )
        if len(analyze_posts) != 1:
            failures.append(f"{route_name}: expected one /analyze POST after Analyze fit, got {len(analyze_posts)}")
        else:
            payload = analyze_posts[0]
            notice_context = payload.get("notice_context") if isinstance(payload, dict) else None
            if not isinstance(notice_context, dict):
                failures.append(f"{route_name}: analyze payload missing notice_context: {payload!r}")
            else:
                expected_context = {
                    "title": fixture_title,
                    "source": "NIH",
                    "deadline_status": "closed",
                    "deadline_label": "Closed",
                    "readiness_score": 25,
                    "evidence_to_prepare": ["Renewed notice confirmation"],
                    "risk_flags": ["Deadline has already passed."],
                    "submission_timeline": ["Find renewed FOA before submission."],
                }
                for key, expected_value in expected_context.items():
                    if notice_context.get(key) != expected_value:
                        failures.append(
                            f"{route_name}: analyze notice_context {key} mismatch: {notice_context.get(key)!r}"
                        )
            profile = payload.get("user_profile") if isinstance(payload, dict) else None
            if not isinstance(profile, dict) or profile.get("company_name") != "Joolife Bio":
                failures.append(f"{route_name}: analyze payload lost company profile: {payload!r}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)
        page.unroute(analyze_route_pattern, fulfill_analyze)
        page.unroute(discover_route_pattern, fulfill_discover)
        page.unroute(notices_route_pattern, fulfill_notices)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_notices_source_link_fallback_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "notices-source-link-fallback"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    notices_requests: list[str] = []
    discovery_posts: list[str] = []
    notices_route_pattern = "**/notices?*"
    discover_route_pattern = "**/discover/grants"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_notices(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        notices_requests.append(request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-safe-notice",
                        "title": "Safe Notice Source",
                        "source": "KDDF",
                        "body_text": "Funding notice with a canonical HTTPS source URL.",
                        "deadline": "2026-08-15",
                        "keywords": ["source link", "safe"],
                        "url": "https://safe.example/notice",
                    },
                    {
                        "id": "browser-missing-notice",
                        "title": "Missing Notice Source",
                        "source": "NTIS",
                        "body_text": "Funding notice missing its canonical source URL.",
                        "keywords": ["source link", "missing"],
                    },
                    {
                        "id": "browser-unsafe-notice",
                        "title": "Unsafe Notice Source",
                        "source": "NTIS",
                        "body_text": "Funding notice with a javascript URL that must not become a link.",
                        "keywords": ["source link", "unsafe"],
                        "url": "javascript:alert(1)",
                    },
                ]
            ),
        )

    def fulfill_discover(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        discovery_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "opportunities": [
                        {
                            "id": "browser-discovery-safe",
                            "title": "Safe Discovery Source",
                            "source": "KDDF",
                            "score": 0.91,
                            "rationale": ["Safe source URL should stay clickable."],
                            "url": "https://safe.example/discovery",
                        },
                        {
                            "id": "browser-discovery-missing",
                            "title": "Missing Discovery Source",
                            "source": "NTIS",
                            "score": 0.74,
                            "rationale": ["Missing source URL should render a fallback."],
                        },
                        {
                            "id": "browser-discovery-unsafe",
                            "title": "Unsafe Discovery Source",
                            "source": "NTIS",
                            "score": 0.68,
                            "rationale": ["Unsafe source URL should render a fallback."],
                            "url": "javascript:alert(1)",
                        },
                    ],
                    "research_signals": {"concepts": ["Funding safety"]},
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(notices_route_pattern, fulfill_notices)
    page.route(discover_route_pattern, fulfill_discover)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/notices", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        original_link = page.get_by_test_id("notices-original-source-link-browser-safe-notice")
        original_link.wait_for(state="visible", timeout=timeout_ms)
        original_href = original_link.get_attribute("href", timeout=timeout_ms) or ""
        original_target = original_link.get_attribute("target", timeout=timeout_ms) or ""
        original_rel = original_link.get_attribute("rel", timeout=timeout_ms) or ""
        if original_href != "https://safe.example/notice":
            failures.append(f"{route_name}: safe notice href mismatch: {original_href!r}")
        if original_target != "_blank":
            failures.append(f"{route_name}: safe notice target mismatch: {original_target!r}")
        if "noopener" not in original_rel or "noreferrer" not in original_rel:
            failures.append(f"{route_name}: safe notice rel missing safe flags: {original_rel!r}")

        for suffix, title in (("browser-missing-notice", "Missing Notice Source"), ("browser-unsafe-notice", "Unsafe Notice Source")):
            page.get_by_text(title).first.wait_for(state="visible", timeout=timeout_ms)
            unavailable = page.get_by_test_id(f"notices-original-source-unavailable-{suffix}")
            unavailable.wait_for(state="visible", timeout=timeout_ms)
            unavailable_text = unavailable.inner_text(timeout=timeout_ms)
            if "Source link unavailable" not in unavailable_text:
                failures.append(f"{route_name}: notice fallback mismatch for {title}: {unavailable_text!r}")
            if page.get_by_test_id(f"notices-original-source-link-{suffix}").count() != 0:
                failures.append(f"{route_name}: rendered original source link for invalid notice {title}")

        page.locator("main textarea").first.fill(
            "Browser smoke grant discovery context for translational AI source links.",
            timeout=timeout_ms,
        )
        page.get_by_test_id("notices-discover-button").click(timeout=timeout_ms)
        discovery_link = page.get_by_test_id("notices-discovery-source-link-browser-discovery-safe")
        discovery_link.wait_for(state="visible", timeout=timeout_ms)
        discovery_href = discovery_link.get_attribute("href", timeout=timeout_ms) or ""
        discovery_target = discovery_link.get_attribute("target", timeout=timeout_ms) or ""
        discovery_rel = discovery_link.get_attribute("rel", timeout=timeout_ms) or ""
        if discovery_href != "https://safe.example/discovery":
            failures.append(f"{route_name}: safe discovery href mismatch: {discovery_href!r}")
        if discovery_target != "_blank":
            failures.append(f"{route_name}: safe discovery target mismatch: {discovery_target!r}")
        if "noopener" not in discovery_rel or "noreferrer" not in discovery_rel:
            failures.append(f"{route_name}: safe discovery rel missing safe flags: {discovery_rel!r}")

        for suffix, title in (("browser-discovery-missing", "Missing Discovery Source"), ("browser-discovery-unsafe", "Unsafe Discovery Source")):
            page.get_by_text(title).first.wait_for(state="visible", timeout=timeout_ms)
            unavailable = page.get_by_test_id(f"notices-discovery-source-unavailable-{suffix}")
            unavailable.wait_for(state="visible", timeout=timeout_ms)
            unavailable_text = unavailable.inner_text(timeout=timeout_ms)
            if "Source link unavailable" not in unavailable_text:
                failures.append(f"{route_name}: discovery fallback mismatch for {title}: {unavailable_text!r}")
            if page.get_by_test_id(f"notices-discovery-source-link-{suffix}").count() != 0:
                failures.append(f"{route_name}: rendered discovery source link for invalid notice {title}")

        broken_links = page.locator('main a[href="#"], main a[href^="javascript:"]')
        broken_count = broken_links.count()
        if broken_count:
            failures.append(f"{route_name}: Notices rendered {broken_count} broken/unsafe source links")

        original_link.evaluate(
            """element => {
                window.__noticesSourceClicks = [];
                element.addEventListener('click', (event) => {
                    event.preventDefault();
                    window.__noticesSourceClicks.push({
                        href: element.href,
                        target: element.target,
                        rel: element.rel,
                    });
                }, { once: true });
            }"""
        )
        original_link.click(timeout=timeout_ms)
        clicks = page.evaluate("() => window.__noticesSourceClicks || []")
        if len(clicks) != 1:
            failures.append(f"{route_name}: expected one safe original-source click, got {clicks!r}")

        if not notices_requests:
            failures.append(f"{route_name}: did not request /notices for source-link data")
        if len(discovery_posts) != 1:
            failures.append(f"{route_name}: expected one /discover/grants POST, got {len(discovery_posts)}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(discover_route_pattern, fulfill_discover)
        page.unroute(notices_route_pattern, fulfill_notices)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_ai_lab_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "ai-lab-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    agent_posts: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/api/agent/" in request.url:
            agent_posts.append(request.url)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)

    try:
        response = _goto_app_route(page, base_url, "/ai-lab", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        run_button = page.get_by_test_id("ai-lab-run-button")
        run_button.wait_for(state="visible", timeout=timeout_ms)
        if not run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: research run button should be disabled before topic is entered")
        if not _any_text_visible(page, ("Run checklist", "실행 준비 체크리스트"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: run checklist is not visible")
        if not _any_text_visible(page, ("Missing required inputs", "필수 입력 누락"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: missing-input status is not visible")

        page.get_by_test_id("ai-lab-research-topic").fill(
            "Browser smoke research topic for launch readiness.",
            timeout=timeout_ms,
        )
        if run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: research run button stayed disabled after topic was entered")
        if not _any_text_visible(page, ("Ready to run", "실행 준비 완료"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: research ready status is not visible")

        page.get_by_role("button", name="Content Writer").click(timeout=timeout_ms)
        if not run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: writer run button should be disabled before writer inputs are entered")
        page.get_by_test_id("ai-lab-write-topic").fill("Browser smoke content memo", timeout=timeout_ms)
        if not run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: writer run button should stay disabled until source text is entered")
        page.get_by_test_id("ai-lab-write-source").fill(
            "Raw source text for the AI Workbench readiness browser smoke.",
            timeout=timeout_ms,
        )
        if run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: writer run button stayed disabled after all writer inputs were entered")

        page.get_by_role("button", name="YouTube Intelligence").click(timeout=timeout_ms)
        if not run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: YouTube run button should be disabled before URL is entered")
        page.get_by_test_id("ai-lab-youtube-url").fill(
            "not-a-video-url",
            timeout=timeout_ms,
        )
        if not run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: YouTube run button should stay disabled for malformed URLs")
        page.get_by_test_id("ai-lab-youtube-url-invalid").wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("ai-lab-youtube-url").fill(
            "https://youtube.com/watch?v=browser-smoke",
            timeout=timeout_ms,
        )
        if run_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: YouTube run button stayed disabled after URL was entered")
        if not _any_text_visible(page, ("Extra question is optional", "추가 질문은 선택 사항"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: optional YouTube query checklist item is not visible")
        if agent_posts:
            failures.append(f"{route_name}: agent POST should not run during readiness check: {agent_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_ai_lab_agent_error_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "ai-lab-agent-error-visible"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    write_posts: list[str] = []
    agent_write_route_pattern = "**/api/agent/write"
    unavailable_detail = (
        "AI agent service is unavailable. Check provider credentials and retry after the service is restored."
    )

    def collect_console(message) -> None:
        if message.type == "error":
            text = message.text
            if (
                "Failed to load resource" in text
                and "503" in text
            ):
                return
            console_errors.append(text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_agent_write(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        write_posts.append(request.post_data or "")
        route.fulfill(
            status=503,
            headers={
                "access-control-allow-origin": base_url.rstrip("/"),
                "access-control-expose-headers": "x-request-id",
                "x-request-id": "agent-smoke-unavailable",
            },
            content_type="application/json",
            body=json.dumps({"detail": unavailable_detail}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(agent_write_route_pattern, fulfill_agent_write)

    try:
        try:
            page.context.grant_permissions(
                ["clipboard-read", "clipboard-write"],
                origin=base_url.rstrip("/"),
            )
        except PlaywrightError:
            pass
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
            })();
            """
        )

        response = _goto_app_route(page, base_url, "/ai-lab", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_role("button", name="Content Writer").click(timeout=timeout_ms)
        page.get_by_test_id("ai-lab-write-topic").fill(
            "Browser smoke provider failure memo",
            timeout=timeout_ms,
        )
        page.get_by_test_id("ai-lab-write-source").fill(
            "Source text for the AI Workbench provider-unavailable browser smoke.",
            timeout=timeout_ms,
        )

        with page.expect_response(
            lambda response: response.request.method.upper() == "POST"
            and urlparse(response.url).path.endswith("/api/agent/write"),
            timeout=timeout_ms,
        ) as write_info:
            page.get_by_test_id("ai-lab-run-button").click(timeout=timeout_ms)
        write_response = write_info.value
        if write_response.status != 503:
            failures.append(f"{route_name}: expected agent write HTTP 503, got {write_response.status}")

        page.get_by_text("Agent run failed").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("AI provider credentials are currently unavailable").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        page.get_by_text("agent-smoke-unavailable").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_role("button", name="Try again").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Reusable execution packet").first.wait_for(state="visible", timeout=timeout_ms)
        packet_text = page.get_by_test_id("ai-lab-recovery-packet").inner_text(timeout=timeout_ms)
        required_packet_fragments = (
            "AI Workbench 실행 패킷",
            "Browser smoke provider failure memo",
            "Content Writer",
            "## 출력 형식",
            "## 품질 기준",
            "Source text for the AI Workbench provider-unavailable browser smoke.",
        )
        missing_packet_fragments = [
            fragment for fragment in required_packet_fragments if fragment not in packet_text
        ]
        if missing_packet_fragments:
            failures.append(
                f"{route_name}: recovery packet missing fragments: {', '.join(missing_packet_fragments)}"
            )
        page.get_by_test_id("ai-lab-copy-recovery-packet").click(timeout=timeout_ms)
        page.get_by_text("Copied the execution packet to your clipboard.").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        copied_packet = page.evaluate(
            """async () => {
              const stubValue = window.__aiLabCopiedText || localStorage.getItem('__aiLabCopiedText') || '';
              if (stubValue) return stubValue;
              if (navigator.clipboard?.readText) return await navigator.clipboard.readText();
              return '';
            }"""
        )
        if "Browser smoke provider failure memo" not in copied_packet or "## 품질 기준" not in copied_packet:
            failures.append(f"{route_name}: copied recovery packet lost required content")

        if len(write_posts) != 1:
            failures.append(f"{route_name}: expected one agent write POST, got {len(write_posts)}")
        elif "Browser smoke provider failure memo" not in write_posts[0]:
            failures.append(f"{route_name}: write POST body lost the memo topic")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(agent_write_route_pattern, fulfill_agent_write)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_ai_lab_result_copy_failure_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "ai-lab-result-copy-failure"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    research_posts: list[str] = []
    agent_research_route_pattern = "**/api/agent/research"
    result_text = AI_LAB_DECISION_READY_FIXTURE
    quality_report = score_ai_lab_output(
        result_text,
        evidence_sources=AI_LAB_EVIDENCE_SOURCES,
        require_evidence=True,
        require_quoted_evidence=True,
    )
    if quality_report["status"] != "pass":
        failures.append(
            f"{route_name}: fixture fails AI Lab output quality contract: "
            f"{', '.join(quality_report['failed_check_ids'])}"
        )

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_agent_research(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        research_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            headers={"access-control-allow-origin": base_url.rstrip("/")},
            content_type="application/json",
            body=json.dumps(
                {
                    "result": {
                        "report": result_text,
                        "evidence_sources": list(AI_LAB_EVIDENCE_SOURCES),
                        "meta": {"bridge_applied": True},
                    },
                    "meta": {"bridge_applied": True},
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(agent_research_route_pattern, fulfill_agent_research)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__aiLabClipboardAttempts = 0;
              window.__aiLabClipboardPayloads = [];
              window.__aiLabUnhandledRejections = [];
              window.addEventListener('unhandledrejection', (event) => {
                window.__aiLabUnhandledRejections.push(String(event.reason || 'unknown rejection'));
              });
              Object.defineProperty(navigator, 'clipboard', {
                configurable: true,
                value: {
                  writeText: async (payload) => {
                    window.__aiLabClipboardAttempts += 1;
                    window.__aiLabClipboardPayloads.push(String(payload || ''));
                    if (String(payload || '').includes('# AI Lab Review Packet')) {
                      return;
                    }
                    throw new DOMException('clipboard denied by browser smoke', 'NotAllowedError');
                  },
                },
              });
            })();
            """
        )

        response = _goto_app_route(page, base_url, "/ai-lab", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("ai-lab-research-topic").fill(
            "Browser smoke AI Lab copy failure topic.",
            timeout=timeout_ms,
        )
        with page.expect_response(
            lambda response: response.request.method.upper() == "POST"
            and urlparse(response.url).path.endswith("/api/agent/research"),
            timeout=timeout_ms,
        ) as research_info:
            page.get_by_test_id("ai-lab-run-button").click(timeout=timeout_ms)
        research_response = research_info.value
        if research_response.status != 200:
            failures.append(f"{route_name}: expected agent research HTTP 200, got {research_response.status}")

        page.get_by_text("Browser Smoke AI Lab deep analysis").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        rendered_result = page.locator("main").inner_text(timeout=timeout_ms)
        required_result_fragments = (
            "1-minute Executive Summary",
            "Evidence basis",
            "Confidence is medium",
            "Next action",
            "source IDs",
            "source URLs",
            "source snippets",
            "Competitive reuse value",
            "reusable source-backed decision gates",
            "review-packet checklist",
            "Confidence calibration",
            "would raise confidence",
            "would lower confidence",
            "Audience & Use Case",
            "platform operator",
            "scorer-ready review packet",
            "live-packet artifact",
            "Key Findings",
            "specific, measurable requirements",
            "objectively evaluate if the actions have been done",
            "Reviewers need fixture limits",
            "Evidence Map",
            "Strong: specific, measurable readiness requirements",
            "Weak: fixture-only verification still needs risk treatment owner",
            "Change condition",
            "before launch review",
            "source evidence quality scoring or copied source packet parsing",
            "Deep Dive",
            "Technical: keep source URLs",
            "Regulatory: flag compliance",
            "Action Plan",
            "Dependencies/blocked by",
            "block launch review",
            "stale source freshness",
            "Reusable Handoff",
            "Copy-ready decision log",
            "Artifact-ready format",
            "Stakeholder ask",
            "Evidence attachment",
            "Assumptions & Boundaries",
            "out-of-scope",
            "Reviewer Red Flags",
            "do not use",
            "Stop condition",
            "Evidence blocker",
            "launch reviewer",
            "before production reuse",
            "Risks & Open Questions",
            "Owner:",
            "Verification:",
            "Status/review:",
            "Follow-up:",
            "References & Search Queries",
            "Quality Criteria",
            "Ready to use",
            "Evidence required",
            "Reuse destination",
            "Evidence sources",
            "NASA SWE-034 acceptance criteria",
            "https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695413/SWE-034%2B-%2BAcceptance%2BCriteria",
            "UNDP risk recording and reporting",
            "source freshness",
            "live provider packet source freshness",
            "NASA SWE acceptance criteria measurable testable launch review source freshness",
            "Copy review packet",
        )
        missing_result_fragments = [
            fragment for fragment in required_result_fragments if fragment not in rendered_result
        ]
        if missing_result_fragments:
            failures.append(
                f"{route_name}: successful result missing quality sections: {', '.join(missing_result_fragments)}"
            )
        page.get_by_text("Bridge correction applied").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_test_id("ai-lab-copy-review-packet").click(timeout=timeout_ms)
        page.get_by_text("Copied the review packet to your clipboard.").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        clipboard_payloads = page.evaluate("() => window.__aiLabClipboardPayloads || []")
        review_packets = [
            payload for payload in clipboard_payloads if isinstance(payload, str) and "# AI Lab Review Packet" in payload
        ]
        if len(review_packets) != 1:
            failures.append(f"{route_name}: expected one review packet clipboard payload, got {len(review_packets)}")
        else:
            for fragment in ("User Request Context", "Browser smoke AI Lab copy failure topic.", "--review-packet"):
                if fragment not in review_packets[0]:
                    failures.append(f"{route_name}: review packet missing {fragment!r}")
            try:
                review_result_text, review_evidence_sources = parse_review_packet(review_packets[0])
                review_topic = parse_review_packet_topic(review_packets[0])
                review_quality_report = score_ai_lab_output(
                    review_result_text,
                    evidence_sources=review_evidence_sources,
                    require_evidence=True,
                    require_quoted_evidence=True,
                    expected_topic=review_topic,
                )
                if review_quality_report["status"] != "pass":
                    failures.append(
                        f"{route_name}: copied review packet fails strict scorer: "
                        f"{', '.join(review_quality_report['failed_check_ids'])}"
                    )
            except (ValueError, json.JSONDecodeError) as exc:
                failures.append(f"{route_name}: copied review packet could not be parsed ({exc})")
        page.get_by_test_id("ai-lab-copy-result").click(timeout=timeout_ms)
        page.get_by_text("Could not copy the result.").first.wait_for(state="visible", timeout=timeout_ms)

        clipboard_attempts = page.evaluate("() => window.__aiLabClipboardAttempts || 0")
        if clipboard_attempts != 2:
            failures.append(f"{route_name}: expected two clipboard attempts, got {clipboard_attempts!r}")
        unhandled_rejections = page.evaluate("() => window.__aiLabUnhandledRejections || []")
        if unhandled_rejections:
            failures.append(f"{route_name}: clipboard failure created unhandled rejections: {unhandled_rejections!r}")

        if len(research_posts) != 1:
            failures.append(f"{route_name}: expected one agent research POST, got {len(research_posts)}")
        elif "Browser smoke AI Lab copy failure topic." not in research_posts[0]:
            failures.append(f"{route_name}: research POST body lost the topic")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(agent_research_route_pattern, fulfill_agent_research)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_peer_review_readiness_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "peer-review-readiness"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    review_posts: list[str] = []
    papers_route_pattern = "**/papers/me"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/reward/review" in request.url:
            review_posts.append(request.url)

    def fulfill_review_papers(route) -> None:
        if route.request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-peer-review-paper",
                        "title": "Browser smoke review-ready paper",
                        "abstract": "Seeded review fixture for readiness validation.",
                        "reward_claimed": False,
                    }
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)
    page.route(papers_route_pattern, fulfill_review_papers)

    try:
        response = _goto_app_route(page, base_url, "/peer-review", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        paper_button = page.locator("main button.glass-card").first
        paper_button.wait_for(state="visible", timeout=timeout_ms)
        paper_button.click(timeout=timeout_ms)

        submit_button = page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(Submit review|리뷰 제출)"),
        ).last
        submit_button.wait_for(state="visible", timeout=timeout_ms)
        if not submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button should be disabled before critique is entered")

        if not _any_text_visible(
            page,
            ("Review checklist", "리뷰 준비 체크리스트"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: review checklist is not visible")
        if not _any_text_visible(
            page,
            ("Missing required items", "필수 항목 누락"),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing-required status is not visible")

        page.locator("main textarea").first.fill(
            "Browser smoke review readiness confirms the critique field before submission.",
            timeout=timeout_ms,
        )

        if not submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button should stay disabled until a wallet is connected")
        if not _any_text_visible(page, ("Review critique entered", "리뷰 내용 입력됨"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: review-text-ready status is not visible")
        wallet_required = page.get_by_test_id("peer-review-wallet-required")
        if wallet_required.count() != 1:
            failures.append(f"{route_name}: wallet-required guidance is not visible")
        else:
            wallet_href = wallet_required.get_by_role("link").get_attribute("href", timeout=timeout_ms)
            if wallet_href != "/wallet":
                failures.append(f"{route_name}: wallet guidance link mismatch: {wallet_href!r}")
        if review_posts:
            failures.append(f"{route_name}: review POST should not run during readiness check: {review_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)
        page.unroute(papers_route_pattern, fulfill_review_papers)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_peer_review_submit_receipt_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "peer-review-submit-receipt"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    review_posts: list[dict[str, str]] = []
    papers_route_pattern = "**/papers/me"
    reward_route_pattern = "**/reward/review*"
    reward_tx_hash = f"0x{'7' * 64}"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_review_papers(route) -> None:
        if route.request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-peer-review-submit-paper",
                        "title": "Browser smoke rewarded review paper",
                        "abstract": "Seeded review fixture for rewarded submission validation.",
                        "reward_claimed": False,
                    }
                ]
            ),
        )

    def fulfill_review_reward(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        review_posts.append({"url": request.url, "body": request.post_data or ""})
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "success": True,
                    "tx_hash": reward_tx_hash,
                    "user": MOCK_WALLET_ADDRESS,
                    "amount": 50,
                    "reason": "rewardPeerReview",
                    "_mock": True,
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(papers_route_pattern, fulfill_review_papers)
    page.route(reward_route_pattern, fulfill_review_reward)

    try:
        page.add_init_script(
            f"""
            (() => {{
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__desciWalletRequests = [];
              window.ethereum = {{
                request: async (payload) => {{
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_accounts') {{
                    return ['{MOCK_WALLET_ADDRESS}'];
                  }}
                  return null;
                }},
                on: () => undefined,
                removeListener: () => undefined,
              }};
            }})();
            """
        )

        response = _goto_app_route(page, base_url, "/peer-review", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.wait_for_function(
            "() => (window.__desciWalletRequests || []).some((item) => item.method === 'eth_accounts')",
            timeout=timeout_ms,
        )
        page.get_by_text("Browser smoke rewarded review paper").first.click(timeout=timeout_ms)
        page.locator("main textarea").first.fill(
            "Browser smoke submits a rewarded peer review and expects a durable receipt.",
            timeout=timeout_ms,
        )

        submit_button = page.locator("main").get_by_role("button", name="Submit review").last
        if submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit button stayed disabled with critique and wallet")
        with page.expect_response(
            lambda response: response.request.method.upper() == "POST"
            and urlparse(response.url).path.endswith("/reward/review"),
            timeout=timeout_ms,
        ) as reward_info:
            submit_button.click(timeout=timeout_ms)
        reward_response = reward_info.value
        if reward_response.status != 200:
            failures.append(f"{route_name}: reward HTTP status {reward_response.status}")

        receipt = page.get_by_test_id("peer-review-submission-receipt")
        receipt.wait_for(state="visible", timeout=timeout_ms)
        receipt_text = receipt.inner_text(timeout=timeout_ms)
        for expected in (
            "Review reward receipt",
            "50 DSCI",
            'Reward scheduled for "Browser smoke rewarded review paper" with review score 3/10.',
            reward_tx_hash,
        ):
            if expected not in receipt_text:
                failures.append(f"{route_name}: receipt missing {expected!r}")

        page.get_by_text("Rewarded").first.wait_for(state="visible", timeout=timeout_ms)
        if len(review_posts) != 1:
            failures.append(f"{route_name}: expected one review reward POST, got {len(review_posts)}")
        else:
            review_query = parse_qs(urlparse(review_posts[0]["url"]).query)
            if review_query.get("user_address") != [MOCK_WALLET_ADDRESS]:
                failures.append(f"{route_name}: reward used wrong user_address: {review_query!r}")
            if review_query.get("paper_id") != ["browser-smoke-peer-review-submit-paper"]:
                failures.append(f"{route_name}: reward used wrong paper_id: {review_query!r}")
            if review_query.get("rating") != ["3"]:
                failures.append(f"{route_name}: reward used wrong rating: {review_query!r}")
            try:
                body = json.loads(review_posts[0]["body"])
            except json.JSONDecodeError:
                body = {}
                failures.append(f"{route_name}: reward POST body was not JSON")
            if body.get("review_text") != "Browser smoke submits a rewarded peer review and expects a durable receipt.":
                failures.append(f"{route_name}: reward POST body lost review text")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(papers_route_pattern, fulfill_review_papers)
        page.unroute(reward_route_pattern, fulfill_review_reward)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_mylab_mint_wallet_required_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "mylab-mint-wallet-required"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    mint_posts: list[str] = []
    papers_route_pattern = "**/papers/me"
    mint_route_pattern = "**/nft/mint"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_mylab_papers(route) -> None:
        if route.request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-mylab-paper",
                        "title": "MyLab Mint Guard Paper",
                        "abstract": "A browser baseline paper for MyLab mint guard validation.",
                        "type": "paper",
                        "nft_minted": False,
                        "ipfs_url": "ipfs://browser-smoke-mylab-paper",
                        "created_at": "2026-06-06T00:00:00Z",
                    }
                ]
            ),
        )

    def trap_mint(route) -> None:
        if route.request.method.upper() != "POST":
            route.continue_()
            return
        mint_posts.append(route.request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "tx_hash": "browser-smoke-mint-should-not-run"}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(papers_route_pattern, fulfill_mylab_papers)
    page.route(mint_route_pattern, trap_mint)

    try:
        response = _goto_app_route(page, base_url, "/mylab", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_text("MyLab Mint Guard Paper").first.wait_for(state="visible", timeout=timeout_ms)
        mint_button = page.locator("main").get_by_role("button", name=re.compile(r"IP-NFT")).last
        mint_button.wait_for(state="visible", timeout=timeout_ms)
        mint_button.click(timeout=timeout_ms)

        page.get_by_role("alert").filter(has_text=re.compile(r"Wallet")).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        if mint_posts:
            failures.append(f"{route_name}: mint POST escaped without wallet: {mint_posts[0][:200]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(papers_route_pattern, fulfill_mylab_papers)
        page.unroute(mint_route_pattern, trap_mint)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_mylab_mint_success_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "mylab-mint-success"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    mint_posts: list[str] = []
    ipfs_cid = f"Qm{'m' * 44}"
    tx_hash = f"0x{'e' * 64}"
    papers_route_pattern = "**/papers/me"
    mint_route_pattern = "**/nft/mint"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_papers(route) -> None:
        if route.request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            headers={"access-control-allow-origin": base_url.rstrip("/")},
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "browser-smoke-mint-paper",
                        "title": "Browser smoke mintable paper",
                        "abstract": "Seeded paper for IP-NFT mint success validation.",
                        "type": "paper",
                        "created_at": "2026-06-06T00:00:00Z",
                        "ipfs_url": f"ipfs://{ipfs_cid}",
                        "nft_minted": False,
                    },
                    {
                        "id": "browser-smoke-unsafe-paper",
                        "title": "Browser smoke unsafe IPFS paper",
                        "abstract": "Seeded paper with malformed IPFS data.",
                        "type": "paper",
                        "created_at": "2026-06-06T00:00:00Z",
                        "ipfs_url": "javascript:alert(1)",
                        "nft_minted": False,
                    }
                ]
            ),
        )

    def fulfill_mint(route) -> None:
        request = route.request
        if request.method.upper() != "POST":
            route.continue_()
            return
        mint_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            headers={"access-control-allow-origin": base_url.rstrip("/")},
            content_type="application/json",
            body=json.dumps({"success": True, "tx_hash": tx_hash}),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(papers_route_pattern, fulfill_papers)
    page.route(mint_route_pattern, fulfill_mint)

    try:
        page.add_init_script(
            f"""
            (() => {{
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__desciWalletRequests = [];
              window.ethereum = {{
                request: async (payload) => {{
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_accounts') {{
                    return ['{MOCK_WALLET_ADDRESS}'];
                  }}
                  return null;
                }},
                on: () => undefined,
                removeListener: () => undefined,
              }};
            }})();
            """
        )

        response = _goto_app_route(page, base_url, "/mylab", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_text("Browser smoke mintable paper").first.wait_for(state="visible", timeout=timeout_ms)
        ipfs_link = page.get_by_test_id("mylab-ipfs-browser-smoke-mint-paper")
        ipfs_link.wait_for(state="visible", timeout=timeout_ms)
        if ipfs_link.get_attribute("href", timeout=timeout_ms) != f"https://ipfs.io/ipfs/{ipfs_cid}":
            failures.append(f"{route_name}: MyLab IPFS href mismatch")
        ipfs_rel = set((ipfs_link.get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(ipfs_rel):
            failures.append(f"{route_name}: MyLab IPFS link missing safe rel tokens")
        page.get_by_test_id("mylab-ipfs-unavailable-browser-smoke-unsafe-paper").wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        unsafe_link_count = page.locator('main a[href="#"], main a[href^="javascript:"]').count()
        if unsafe_link_count:
            failures.append(f"{route_name}: rendered unsafe MyLab anchor count {unsafe_link_count}")
        page.wait_for_function(
            "() => (window.__desciWalletRequests || []).some((item) => item.method === 'eth_accounts')",
            timeout=timeout_ms,
        )

        with page.expect_response(
            lambda response: response.request.method.upper() == "POST"
            and urlparse(response.url).path.endswith("/nft/mint"),
            timeout=timeout_ms,
        ) as mint_info:
            page.locator("main").get_by_role("button", name="Mint IP-NFT").first.click(timeout=timeout_ms)
        mint_response = mint_info.value
        if mint_response.status != 200:
            failures.append(f"{route_name}: mint HTTP status {mint_response.status}")

        if len(mint_posts) != 1:
            failures.append(f"{route_name}: expected one mint POST, got {len(mint_posts)}")
        else:
            try:
                payload = json.loads(mint_posts[0])
            except json.JSONDecodeError:
                payload = {}
                failures.append(f"{route_name}: mint POST body was not JSON")
            if payload.get("user_address") != MOCK_WALLET_ADDRESS:
                failures.append(f"{route_name}: mint used wrong user_address: {payload.get('user_address')!r}")
            if payload.get("token_uri") != f"ipfs://{ipfs_cid}":
                failures.append(f"{route_name}: mint used wrong token_uri: {payload.get('token_uri')!r}")

        page.get_by_text("IP-NFT minted").first.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Browser smoke mintable paper").first.wait_for(state="visible", timeout=timeout_ms)
        tx_link = page.get_by_test_id("success-modal-tx-link")
        tx_link.wait_for(state="visible", timeout=timeout_ms)
        expected_href = f"https://amoy.polygonscan.com/tx/{tx_hash}"
        if tx_link.get_attribute("href", timeout=timeout_ms) != expected_href:
            failures.append(f"{route_name}: tx explorer link mismatch")
        if tx_link.get_attribute("target", timeout=timeout_ms) != "_blank":
            failures.append(f"{route_name}: tx explorer link should open in a new tab")
        rel_tokens = set((tx_link.get_attribute("rel", timeout=timeout_ms) or "").split())
        if not {"noopener", "noreferrer"}.issubset(rel_tokens):
            failures.append(f"{route_name}: tx explorer link missing safe rel tokens")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(papers_route_pattern, fulfill_papers)
        page.unroute(mint_route_pattern, fulfill_mint)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_vc_portal_select_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "vc-portal-select"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    match_requests: list[str] = []
    match_route_pattern = "**/vcs/*/matches*"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_vc_matches(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return

        match_requests.append(request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "asset_id": "browser-smoke-vc-asset",
                        "title": "Browser Smoke AI Therapeutics Platform",
                        "summary": "AI-guided therapeutic discovery asset with translational validation evidence.",
                        "match_reason": "Matches the selected VC thesis across AI therapeutics and platform biology.",
                        "score": 91,
                        "keywords": ["AI therapeutics", "Drug discovery", "Series A"],
                    }
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(match_route_pattern, fulfill_vc_matches)

    try:
        response = _goto_app_route(page, base_url, "/vc-portal", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        selector = page.locator("select").first
        selector.wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('select option')).some((option) => option.value)",
            timeout=timeout_ms,
        )
        options = selector.locator("option").evaluate_all(
            """options => options
                .map(option => ({ value: option.value, label: option.textContent || '' }))
                .filter(option => option.value)"""
        )
        if not options:
            failures.append(f"{route_name}: no venture firm options rendered")
        else:
            selected = options[0]
            selector.select_option(selected["value"], timeout=timeout_ms)
            page.get_by_test_id("vc-portal-deal-flow-results").wait_for(state="visible", timeout=timeout_ms)
            body_text = page.locator("body").inner_text(timeout=timeout_ms)
            body_text_folded = body_text.casefold()
            selected_name = selected["label"].split(" (", 1)[0].strip()
            if selected_name and selected_name.casefold() not in body_text_folded:
                failures.append(f"{route_name}: selected VC profile did not render {selected_name!r}")
            for expected in ("Investment thesis", "Focus areas", "Preferred stages"):
                if expected.casefold() not in body_text_folded:
                    failures.append(f"{route_name}: missing selected profile text {expected!r}")
            for expected in (
                "Browser Smoke AI Therapeutics Platform",
                "91%",
                "Matches the selected VC thesis across AI therapeutics and platform biology.",
            ):
                if expected.casefold() not in body_text_folded:
                    failures.append(f"{route_name}: missing deal-flow match text {expected!r}")
            match_card = page.get_by_test_id("vc-portal-match-card-browser-smoke-vc-asset")
            if match_card.get_attribute("aria-haspopup", timeout=timeout_ms) != "dialog":
                failures.append(f"{route_name}: match card does not advertise dialog behavior")
            match_card.click(timeout=timeout_ms)

            dialog = page.get_by_test_id("vc-match-detail-dialog")
            dialog.wait_for(state="visible", timeout=timeout_ms)
            if dialog.get_attribute("role", timeout=timeout_ms) != "dialog":
                failures.append(f"{route_name}: match detail is not exposed as a dialog")
            if dialog.get_attribute("aria-modal", timeout=timeout_ms) != "true":
                failures.append(f"{route_name}: match detail dialog is missing aria-modal=true")
            dialog_title_id = dialog.get_attribute("aria-labelledby", timeout=timeout_ms)
            dialog_title = page.locator(f"#{dialog_title_id}").inner_text(timeout=timeout_ms) if dialog_title_id else ""
            if "Browser Smoke AI Therapeutics Platform" not in dialog_title:
                failures.append(f"{route_name}: match detail dialog is not labelled by the match title")
            close_button = page.get_by_test_id("vc-match-detail-close")
            close_label = close_button.get_attribute("aria-label", timeout=timeout_ms)
            if not close_label:
                failures.append(f"{route_name}: match detail close button is missing an accessible label")
            close_button.click(timeout=timeout_ms)
            if dialog.count() > 0:
                failures.append(f"{route_name}: match detail dialog did not close")
            match_card.click(timeout=timeout_ms)
            dialog.wait_for(state="visible", timeout=timeout_ms)
            page.keyboard.press("Escape")
            if dialog.count() > 0:
                failures.append(f"{route_name}: match detail dialog did not close on Escape")
            if not match_requests:
                failures.append(f"{route_name}: selecting a VC did not request ranked deal flow")
            elif selected["value"] not in match_requests[-1]:
                failures.append(
                    f"{route_name}: deal-flow request {match_requests[-1]!r} did not include selected VC {selected['value']!r}"
                )
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(match_route_pattern, fulfill_vc_matches)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_wallet_extension_missing_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "wallet-extension-missing"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = _goto_app_route(page, base_url, "/wallet", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        connect_button = page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(지갑 연결|Connect wallet)"),
        ).last
        connect_button.click(timeout=timeout_ms)
        if not _any_text_visible(
            page,
            (
                "브라우저 지갑 확장 프로그램을 설치하거나 활성화한 뒤 다시 시도하세요.",
                "Install or enable a browser wallet extension, then try again.",
            ),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing wallet-extension guidance after click")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_governance_wallet_required_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "governance-wallet-required"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    governance_posts: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def collect_request(request) -> None:
        if request.method.upper() == "POST" and "/governance/" in request.url:
            governance_posts.append(request.url)

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.on("request", collect_request)

    try:
        response = _goto_app_route(page, base_url, "/governance", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        if not _any_text_visible(
            page,
            (
                "Governance actions require a connected wallet before creating proposals or voting.",
                "거버넌스 제안 생성과 투표에는 연결된 지갑이 필요합니다.",
            ),
            timeout_ms=timeout_ms,
        ):
            failures.append(f"{route_name}: missing wallet-required governance guidance")

        page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(New proposal|새 제안)"),
        ).last.click(timeout=timeout_ms)
        buttons = page.locator("main").get_by_role("button")
        button_states = buttons.evaluate_all(
            """buttons => buttons.map((button) => ({
                text: (button.textContent || '').replace(/\\s+/g, ' ').trim(),
                disabled: button.disabled,
            }))"""
        )

        def find_button_state(candidates: tuple[str, ...]) -> dict[str, Any] | None:
            for state in button_states:
                label = str(state.get("text", ""))
                if any(candidate in label for candidate in candidates):
                    return state
            return None

        expected_disabled_buttons = (
            (("Submit proposal", "제안 제출"), "submit proposal"),
            (("For", "찬성"), "vote for"),
            (("Against", "반대"), "vote against"),
        )
        for candidates, label in expected_disabled_buttons:
            state = find_button_state(candidates)
            if state is None:
                if label != "submit proposal":
                    continue
                failures.append(f"{route_name}: missing {label} button")
            elif not state.get("disabled"):
                failures.append(f"{route_name}: {label} button should be disabled before wallet connection")

        if governance_posts:
            failures.append(f"{route_name}: governance POST escaped without wallet: {governance_posts[0]}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.remove_listener("request", collect_request)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_governance_connected_create_vote_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "governance-connected-create-vote"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    proposal_title = "Browser Smoke Governance Runtime Proposal"
    proposal_description = "Verify runtime fallback proposal creation and voting."

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        page.add_init_script(
            f"""
            (() => {{
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__desciWalletRequests = [];
              window.__desciCurrentChainId = '0x1';
              window.ethereum = {{
                request: async (payload) => {{
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_requestAccounts') {{
                    return ['{MOCK_WALLET_ADDRESS}'];
                  }}
                  if (payload.method === 'eth_chainId') {{
                    return window.__desciCurrentChainId;
                  }}
                  if (payload.method === 'wallet_switchEthereumChain') {{
                    window.__desciCurrentChainId = payload.params?.[0]?.chainId;
                    return null;
                  }}
                  if (payload.method === 'wallet_addEthereumChain') {{
                    window.__desciCurrentChainId = payload.params?.[0]?.chainId;
                    return null;
                  }}
                  return null;
                }},
              }};
            }})();
            """
        )

        response = _goto_app_route(page, base_url, "/wallet", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: wallet HTTP status {status}")

        page.locator("main").get_by_role("button", name=re.compile(r"Connect wallet")).last.click(timeout=timeout_ms)
        page.get_by_text(MOCK_WALLET_ADDRESS, exact=True).first.wait_for(state="visible", timeout=timeout_ms)

        methods = page.evaluate("() => (window.__desciWalletRequests || []).map((item) => item.method)")
        for method in ("eth_requestAccounts", "eth_chainId", "wallet_switchEthereumChain"):
            if method not in methods:
                failures.append(f"{route_name}: missing wallet request method {method}")

        page.locator('a[href="/governance"]').first.click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/governance$"), timeout=timeout_ms)
        page.locator("main").get_by_text("Governance Hub").first.wait_for(state="visible", timeout=timeout_ms)
        page.locator("main").get_by_role("button", name="New proposal").last.click(timeout=timeout_ms)
        page.get_by_placeholder("Proposal title").fill(proposal_title, timeout=timeout_ms)
        page.get_by_placeholder("Proposal description").fill(proposal_description, timeout=timeout_ms)

        with page.expect_response(
            lambda response: response.request.method == "POST" and response.url.endswith("/governance/proposals"),
            timeout=timeout_ms,
        ) as create_info:
            page.locator("main").get_by_role("button", name="Submit proposal").last.click(timeout=timeout_ms)
        create_response = create_info.value
        if create_response.status >= 400:
            failures.append(f"{route_name}: create proposal HTTP status {create_response.status}")
        receipt = page.get_by_test_id("governance-action-receipt")
        receipt.wait_for(state="visible", timeout=timeout_ms)
        if receipt.get_attribute("role", timeout=timeout_ms) != "status":
            failures.append(f"{route_name}: governance receipt should announce as role=status")
        if receipt.get_attribute("aria-atomic", timeout=timeout_ms) != "true":
            failures.append(f"{route_name}: governance receipt should be aria-atomic=true")
        create_receipt_text = receipt.inner_text(timeout=timeout_ms)
        for expected in ("Governance action confirmed", "Proposal", f"Proposal created: {proposal_title}", MOCK_WALLET_ADDRESS):
            if expected not in create_receipt_text:
                failures.append(f"{route_name}: create receipt missing {expected!r}")
        page.get_by_text(proposal_title, exact=True).first.wait_for(state="visible", timeout=timeout_ms)

        with page.expect_response(
            lambda response: response.request.method == "POST"
            and re.search(r"/governance/proposals/.+/vote$", response.url) is not None,
            timeout=timeout_ms,
        ) as vote_info:
            page.locator("main").get_by_role("button", name="For").first.click(timeout=timeout_ms)
        vote_response = vote_info.value
        if vote_response.status >= 400:
            failures.append(f"{route_name}: vote HTTP status {vote_response.status}")
        vote_receipt_text = receipt.inner_text(timeout=timeout_ms)
        for expected in ("Governance action confirmed", "Vote", f"Vote recorded: For on {proposal_title}", MOCK_WALLET_ADDRESS):
            if expected not in vote_receipt_text:
                failures.append(f"{route_name}: vote receipt missing {expected!r}")
        page.get_by_text("For: 100").first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_wallet_restore_direct_governance_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "wallet-restore-direct-governance"
    restored_wallet_address = "0x5555555555555555555555555555555555555555"
    proposal_title = f"Wallet Restore Browser Smoke {datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    proposal_description = "Verify direct governance routes restore an already-authorized wallet account."
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        page.add_init_script(
            f"""
            (() => {{
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
              window.__desciWalletRequests = [];
              window.__desciWalletListeners = {{}};
              window.ethereum = {{
                request: async (payload) => {{
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_accounts') {{
                    return ['{restored_wallet_address}'];
                  }}
                  if (payload.method === 'eth_requestAccounts') {{
                    throw new Error('Passive restore must not prompt for wallet accounts.');
                  }}
                  return null;
                }},
                on: (eventName, handler) => {{
                  window.__desciWalletListeners[eventName] = handler;
                }},
                removeListener: (eventName, handler) => {{
                  if (window.__desciWalletListeners[eventName] === handler) {{
                    delete window.__desciWalletListeners[eventName];
                  }}
                }},
              }};
            }})();
            """
        )

        response = _goto_app_route(page, base_url, "/governance", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.locator("main").get_by_text("Governance Hub").first.wait_for(state="visible", timeout=timeout_ms)
        page.wait_for_function(
            "() => (window.__desciWalletRequests || []).some((item) => item.method === 'eth_accounts')",
            timeout=timeout_ms,
        )

        wallet_required = page.locator(
            "main",
        ).get_by_text("Governance actions require a connected wallet before creating proposals or voting.")
        if wallet_required.count() > 0:
            failures.append(f"{route_name}: wallet-required guidance remained visible after eth_accounts restore")

        methods = page.evaluate("() => (window.__desciWalletRequests || []).map((item) => item.method)")
        if "eth_accounts" not in methods:
            failures.append(f"{route_name}: did not request authorized wallet accounts")
        if "eth_requestAccounts" in methods:
            failures.append(f"{route_name}: passive restore prompted for wallet accounts")

        page.locator("main").get_by_role("button", name="New proposal").last.click(timeout=timeout_ms)
        page.get_by_placeholder("Proposal title").fill(proposal_title, timeout=timeout_ms)
        page.get_by_placeholder("Proposal description").fill(proposal_description, timeout=timeout_ms)

        submit_button = page.locator("main").get_by_role("button", name="Submit proposal").last
        if submit_button.is_disabled(timeout=timeout_ms):
            failures.append(f"{route_name}: submit proposal stayed disabled after wallet restore")

        with page.expect_response(
            lambda response: response.request.method.upper() == "POST"
            and urlparse(response.url).path.endswith("/governance/proposals"),
            timeout=timeout_ms,
        ) as create_info:
            submit_button.click(timeout=timeout_ms)
        create_response = create_info.value
        if create_response.status >= 400:
            failures.append(f"{route_name}: create proposal HTTP status {create_response.status}")

        post_body = create_response.request.post_data or "{}"
        try:
            post_payload = json.loads(post_body)
        except json.JSONDecodeError:
            post_payload = {}
            failures.append(f"{route_name}: create proposal POST body was not JSON")
        if post_payload.get("proposer") != restored_wallet_address:
            failures.append(
                f"{route_name}: create proposal used proposer {post_payload.get('proposer')!r}, "
                f"expected {restored_wallet_address!r}"
            )

        page.get_by_text(proposal_title, exact=True).first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_wallet_provider_amoy_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "wallet-provider-amoy"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        page.add_init_script(
            """
            (() => {
              window.__desciWalletRequests = [];
              window.__desciCurrentChainId = '0x1';
              window.ethereum = {
                request: async (payload) => {
                  window.__desciWalletRequests.push(payload);
                  if (payload.method === 'eth_requestAccounts') {
                    return ['0x1234567890123456789012345678901234567890'];
                  }
                  if (payload.method === 'eth_chainId') {
                    return window.__desciCurrentChainId;
                  }
                  if (payload.method === 'wallet_switchEthereumChain') {
                    const error = new Error('Unrecognized chain ID');
                    error.code = 4902;
                    throw error;
                  }
                  if (payload.method === 'wallet_addEthereumChain') {
                    window.__desciCurrentChainId = payload.params?.[0]?.chainId;
                    return null;
                  }
                  return null;
                },
              };
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/wallet", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        connect_button = page.locator("main").get_by_role(
            "button",
            name=re.compile(r"(지갑 연결|Connect wallet)"),
        ).last
        connect_button.click(timeout=timeout_ms)
        page.get_by_text(MOCK_WALLET_ADDRESS, exact=True).first.wait_for(state="visible", timeout=timeout_ms)

        requests = page.evaluate("() => window.__desciWalletRequests || []")
        methods = [request.get("method") for request in requests if isinstance(request, dict)]
        if "eth_requestAccounts" not in methods:
            failures.append(f"{route_name}: did not request wallet accounts")
        if "wallet_switchEthereumChain" not in methods:
            failures.append(f"{route_name}: did not request Polygon Amoy chain switch")
        if "wallet_addEthereumChain" not in methods:
            failures.append(f"{route_name}: did not request Polygon Amoy chain add after unknown-chain switch failure")

        add_chain_request = next(
            (
                request
                for request in requests
                if isinstance(request, dict) and request.get("method") == "wallet_addEthereumChain"
            ),
            None,
        )
        add_chain_payload = {}
        if isinstance(add_chain_request, dict):
            params = add_chain_request.get("params")
            if isinstance(params, list) and params and isinstance(params[0], dict):
                add_chain_payload = params[0]
        if add_chain_payload.get("chainId") != POLYGON_AMOY_CHAIN_ID:
            failures.append(
                f"{route_name}: add-chain chainId mismatch: {add_chain_payload.get('chainId')!r}"
            )
        if POLYGON_AMOY_RPC_URL not in (add_chain_payload.get("rpcUrls") or []):
            failures.append(
                f"{route_name}: add-chain RPC URLs missing {POLYGON_AMOY_RPC_URL!r}"
            )
        if POLYGON_AMOY_EXPLORER_URL not in (add_chain_payload.get("blockExplorerUrls") or []):
            failures.append(
                f"{route_name}: add-chain explorer URLs missing {POLYGON_AMOY_EXPLORER_URL!r}"
            )
        native_currency = add_chain_payload.get("nativeCurrency")
        if not isinstance(native_currency, dict) or native_currency.get("symbol") != "POL":
            failures.append(f"{route_name}: add-chain native currency should use POL")

        current_chain = page.evaluate("() => window.__desciCurrentChainId")
        if current_chain != POLYGON_AMOY_CHAIN_ID:
            failures.append(f"{route_name}: expected wallet chain {POLYGON_AMOY_CHAIN_ID}, got {current_chain}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_landing_cta_intent_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "landing-cta-intent"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    papers_route_pattern = "**/papers/public"
    tier_route_pattern = "**/subscription/tier"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_papers(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "landing-paper-1",
                        "title": "Landing CTA Research Feed Fixture",
                        "authors": "QA Researcher",
                        "abstract": "Fixture paper for landing CTA browser smoke.",
                        "tags": ["Landing", "Smoke"],
                        "ipfs_cid": "QmLandingCtaSmoke",
                        "date": "2026-06-06",
                        "field": "Genomics",
                        "cited": 1,
                    }
                ]
            ),
        )

    def fulfill_tier(route) -> None:
        request = route.request
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"uid": "browser-smoke-user", "tier": "free", "rate_limit": "30/minute"}),
        )

    def href_path_and_params(test_id: str) -> tuple[str, dict[str, list[str]]]:
        href = page.get_by_test_id(test_id).get_attribute("href", timeout=timeout_ms) or ""
        parsed = urlparse(href)
        return parsed.path, parse_qs(parsed.query)

    def expect_href(test_id: str, *, path: str, next_path: str | None = None) -> None:
        actual_path, params = href_path_and_params(test_id)
        if actual_path != path:
            failures.append(f"{route_name}: {test_id} expected path {path}, got {actual_path}")
        if next_path is not None and params.get("next", [None])[0] != next_path:
            failures.append(f"{route_name}: {test_id} expected next={next_path}")

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(papers_route_pattern, fulfill_papers)
    page.route(tier_route_pattern, fulfill_tier)

    try:
        response = _goto_app_route(page, base_url, "/", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        expect_href("landing-sign-in", path="/login")
        expect_href("landing-header-get-started", path="/login", next_path="/dashboard")
        expect_href("landing-start-researcher", path="/login", next_path="/upload")
        expect_href("landing-create-account", path="/login", next_path="/dashboard")
        expect_href("landing-explore-research", path="/explore")
        expect_href("landing-compare-plans", path="/pricing")

        page.get_by_test_id("landing-explore-research").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/explore(?:[?#].*)?$"), timeout=timeout_ms)
        page.get_by_text("Landing CTA Research Feed Fixture").first.wait_for(state="visible", timeout=timeout_ms)

        _goto_app_route(page, base_url, "/", timeout_ms)
        page.get_by_test_id("landing-compare-plans").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/pricing(?:[?#].*)?$"), timeout=timeout_ms)
        if not _any_text_visible(page, ("Starter", "Pro", "Enterprise"), timeout_ms=timeout_ms):
            failures.append(f"{route_name}: pricing CTA did not render plan choices")

        _goto_app_route(page, base_url, "/", timeout_ms)
        page.get_by_test_id("landing-start-researcher").click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/(login|upload)(?:[?#].*)?$"), timeout=timeout_ms)
        final = urlparse(page.url)
        final_params = parse_qs(final.query)
        if final.path == "/login":
            if final_params.get("next", [None])[0] != "/upload":
                failures.append(f"{route_name}: researcher CTA login URL lost next=/upload")
        elif final.path == "/upload":
            if not _any_text_visible(page, ("Research Submission", "IPFS"), timeout_ms=timeout_ms):
                failures.append(f"{route_name}: researcher CTA did not render upload after dev-auth redirect")
        else:
            failures.append(f"{route_name}: researcher CTA landed on unexpected path {final.path}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(papers_route_pattern, fulfill_papers)
        page.unroute(tier_route_pattern, fulfill_tier)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_explore_analyze_intent_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "explore-analyze-intent"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    paper_match_posts: list[str] = []
    papers_route_pattern = "**/papers/public"
    paper_match_route_pattern = "**/jobs/match/paper"
    fixture_id = "browser-paper-1"
    fixture_title = "Federated Learning for Rare Disease Genomics"
    fixture_cid = "QmXoYGnpFjy5F2zRRMRK9q8XqFhT5gE1sJaJ2Q5Nc9X1bK"
    fixture_tx_hash = f"0x{'b' * 64}"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_papers(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": fixture_id,
                        "title": fixture_title,
                        "authors": "Jung H.",
                        "abstract": "Federated GWAS across hospitals without sharing raw genotype data.",
                        "tags": ["Federated Learning", "Genomics"],
                        "ipfs_cid": fixture_cid,
                        "tx_hash": fixture_tx_hash,
                        "date": "2026-03-28",
                        "field": "Genomics",
                        "cited": 35,
                    },
                    {
                        "id": "browser-paper-2",
                        "title": "Microbiome Immune Axis in Pancreatic Cancer",
                        "authors": "Lee Y.",
                        "abstract": "A cohort analysis for chemotherapy resistance.",
                        "tags": ["Microbiome", "Oncology"],
                        "ipfs_cid": "QmBrowserSmokeExploreOther",
                        "date": "2026-04-02",
                        "field": "Oncology",
                        "cited": 18,
                    },
                    {
                        "id": "browser-paper-unsafe-links",
                        "title": "Unsafe Link Payload Paper",
                        "authors": "Security QA",
                        "abstract": "A paper record with malformed outbound link fields.",
                        "tags": ["Security"],
                        "ipfs_cid": "../javascript:alert(1)",
                        "tx_hash": "javascript:alert(1)",
                        "date": "2026-05-01",
                        "field": "AI Drug Discovery",
                        "cited": 1,
                    },
                ]
            ),
        )

    def fulfill_paper_match(route) -> None:
        request = route.request
        if request.method.upper() != "POST" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        paper_match_posts.append(request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "job": {
                        "id": "browser-smoke-paper-match",
                        "type": "paper_match",
                        "status": "succeeded",
                        "progress": 100,
                        "message": "Browser smoke match complete",
                        "result": {"matches": []},
                    }
                }
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(papers_route_pattern, fulfill_papers)
    page.route(paper_match_route_pattern, fulfill_paper_match)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/explore", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_text("Unsafe Link Payload Paper").first.wait_for(state="visible", timeout=timeout_ms)
        ipfs_unavailable = page.get_by_test_id("research-feed-ipfs-unavailable-browser-paper-unsafe-links")
        ipfs_unavailable.wait_for(state="visible", timeout=timeout_ms)
        if "IPFS unavailable" not in ipfs_unavailable.inner_text(timeout=timeout_ms):
            failures.append(f"{route_name}: malformed CID fallback text mismatch")
        tx_unavailable = page.get_by_test_id("research-feed-tx-unavailable-browser-paper-unsafe-links")
        tx_unavailable.wait_for(state="visible", timeout=timeout_ms)
        if "Tx unavailable" not in tx_unavailable.inner_text(timeout=timeout_ms):
            failures.append(f"{route_name}: malformed tx fallback text mismatch")
        if page.get_by_test_id("research-feed-ipfs-browser-paper-unsafe-links").count() != 0:
            failures.append(f"{route_name}: rendered IPFS link for malformed CID")
        if page.get_by_test_id("research-feed-tx-browser-paper-unsafe-links").count() != 0:
            failures.append(f"{route_name}: rendered explorer link for malformed tx hash")
        broken_links = page.locator('main a[href="#"], main a[href^="javascript:"]')
        broken_count = broken_links.count()
        if broken_count:
            failures.append(f"{route_name}: explore rendered {broken_count} broken/unsafe outbound links")

        page.get_by_test_id("research-feed-search").fill("federated", timeout=timeout_ms)
        page.get_by_test_id("research-feed-field-genomics").click(timeout=timeout_ms)
        page.get_by_text(fixture_title).first.wait_for(state="visible", timeout=timeout_ms)
        if page.get_by_text("Microbiome Immune Axis in Pancreatic Cancer").count() > 0:
            failures.append(f"{route_name}: non-matching paper stayed visible after search and field filter")

        ipfs_href = page.get_by_test_id(f"research-feed-ipfs-{fixture_id}").get_attribute("href", timeout=timeout_ms)
        if ipfs_href != f"https://ipfs.io/ipfs/{fixture_cid}":
            failures.append(f"{route_name}: IPFS href mismatch: {ipfs_href}")
        tx_href = page.get_by_test_id(f"research-feed-tx-{fixture_id}").get_attribute("href", timeout=timeout_ms)
        if tx_href != f"https://amoy.polygonscan.com/tx/{fixture_tx_hash}":
            failures.append(f"{route_name}: transaction href mismatch: {tx_href}")

        analyze_link = page.get_by_test_id(f"research-feed-analyze-{fixture_id}")
        analyze_href = analyze_link.get_attribute("href", timeout=timeout_ms) or ""
        analyze_url = urlparse(analyze_href)
        analyze_params = parse_qs(analyze_url.query)
        if analyze_url.path != "/login":
            failures.append(f"{route_name}: analyze href should route through login, got {analyze_url.path}")
        if analyze_params.get("next", [None])[0] != "/biolinker":
            failures.append(f"{route_name}: analyze href did not preserve next=/biolinker")
        if analyze_params.get("paper_id", [None])[0] != fixture_id:
            failures.append(f"{route_name}: analyze href did not preserve paper_id")
        if analyze_params.get("intent", [None])[0] != "analyze":
            failures.append(f"{route_name}: analyze href did not preserve intent=analyze")

        analyze_link.click(timeout=timeout_ms)
        page.wait_for_url(re.compile(r".*/(login|biolinker)(?:[?#].*)?$"), timeout=timeout_ms)
        final = urlparse(page.url)
        final_params = parse_qs(final.query)
        if final.path == "/login":
            if final_params.get("next", [None])[0] != "/biolinker":
                failures.append(f"{route_name}: login URL lost next=/biolinker")
        elif final.path != "/biolinker":
            failures.append(f"{route_name}: expected final path /login or /biolinker, got {final.path}")

        for key, expected in {"paper_id": fixture_id, "intent": "analyze"}.items():
            if final_params.get(key, [None])[0] != expected:
                failures.append(f"{route_name}: final URL lost {key}={expected}")

        if final.path == "/biolinker" and not paper_match_posts:
            failures.append(f"{route_name}: dev-auth redirect reached BioLinker without starting paper match")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(papers_route_pattern, fulfill_papers)
        page.unroute(paper_match_route_pattern, fulfill_paper_match)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_investors_filter_directory_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "investors-filter-directory"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    vcs_route_pattern = "**/vcs?*"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_vcs(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "vc-korea-oncology",
                        "name": "Korea Oncology Seed Fund",
                        "country": "KR",
                        "website": "https://korea-oncology.example",
                        "investment_thesis": "Seed oncology therapeutics in Korea.",
                        "preferred_stages": ["Seed"],
                        "portfolio_keywords": ["Oncology", "Therapeutics"],
                        "contact_email": "team@korea-oncology.example",
                    },
                    {
                        "id": "vc-ra-capital",
                        "name": "RA Capital Management",
                        "country": "US",
                        "website": "https://www.racap.com",
                        "investment_thesis": "Evidence-backed oncology, mRNA, and protein degradation platforms.",
                        "preferred_stages": ["Series A", "Series B", "Crossover"],
                        "portfolio_keywords": ["Oncology", "mRNA", "Protein Degradation"],
                        "contact_email": "deals@racap.com",
                    },
                    {
                        "id": "vc-us-digital-health",
                        "name": "US Digital Health Ventures",
                        "country": "US",
                        "website": "https://digital-health.example",
                        "investment_thesis": "Seed digital health and care delivery platforms.",
                        "preferred_stages": ["Seed"],
                        "portfolio_keywords": ["Digital Health"],
                        "contact_email": "hello@digital-health.example",
                    },
                    {
                        "id": "vc-missing-website",
                        "name": "Missing Website Capital",
                        "country": "FR",
                        "investment_thesis": "European life science growth rounds.",
                        "preferred_stages": ["Growth"],
                        "portfolio_keywords": ["Life Science"],
                        "contact_email": "missing@example.test",
                    },
                    {
                        "id": "vc-unsafe-website",
                        "name": "Unsafe Website Ventures",
                        "country": "US",
                        "website": "javascript:alert(1)",
                        "investment_thesis": "Early healthcare marketplaces.",
                        "preferred_stages": ["Pre-Series A"],
                        "portfolio_keywords": ["Marketplace"],
                        "contact_email": "javascript:alert(1)",
                    },
                ]
            ),
        )

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(vcs_route_pattern, fulfill_vcs)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/investors", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        page.get_by_test_id("investors-result-count").wait_for(state="visible", timeout=timeout_ms)
        safe_website = page.get_by_test_id("investor-website-vc-ra-capital")
        safe_website.wait_for(state="visible", timeout=timeout_ms)
        website_href = safe_website.get_attribute("href", timeout=timeout_ms)
        website_target = safe_website.get_attribute("target", timeout=timeout_ms) or ""
        website_rel = safe_website.get_attribute("rel", timeout=timeout_ms) or ""
        if website_href != "https://www.racap.com/":
            failures.append(f"{route_name}: RA Capital website href mismatch before filtering: {website_href}")
        if website_target != "_blank":
            failures.append(f"{route_name}: RA Capital website target mismatch: {website_target!r}")
        if "noopener" not in website_rel or "noreferrer" not in website_rel:
            failures.append(f"{route_name}: RA Capital website rel missing safe flags: {website_rel!r}")
        for suffix, title in (("vc-missing-website", "Missing Website Capital"), ("vc-unsafe-website", "Unsafe Website Ventures")):
            page.get_by_text(title).first.wait_for(state="visible", timeout=timeout_ms)
            unavailable = page.get_by_test_id(f"investor-website-unavailable-{suffix}")
            unavailable.wait_for(state="visible", timeout=timeout_ms)
            unavailable_text = unavailable.inner_text(timeout=timeout_ms)
            if "Website unavailable" not in unavailable_text:
                failures.append(f"{route_name}: website fallback mismatch for {title}: {unavailable_text!r}")
            if page.get_by_test_id(f"investor-website-{suffix}").count() != 0:
                failures.append(f"{route_name}: rendered website link for invalid VC {title}")
        unsafe_email = page.get_by_test_id("investor-email-unavailable-vc-unsafe-website")
        unsafe_email.wait_for(state="visible", timeout=timeout_ms)
        unsafe_email_text = unsafe_email.inner_text(timeout=timeout_ms)
        if "Email unavailable" not in unsafe_email_text:
            failures.append(f"{route_name}: unsafe email fallback mismatch: {unsafe_email_text!r}")
        if page.get_by_test_id("investor-email-vc-unsafe-website").count() != 0:
            failures.append(f"{route_name}: rendered mailto link for unsafe investor email")
        broken_links = page.locator('main a[href="#"], main a[href^="javascript:"]')
        broken_count = broken_links.count()
        if broken_count:
            failures.append(f"{route_name}: investor directory rendered {broken_count} broken/unsafe links")
        unsafe_mailto_count = page.locator('main a[href^="mailto:javascript:"], main a[href^="mailto:?"]').count()
        if unsafe_mailto_count:
            failures.append(f"{route_name}: investor directory rendered {unsafe_mailto_count} unsafe mailto links")

        page.get_by_test_id("investors-search").fill("oncology", timeout=timeout_ms)
        page.get_by_test_id("investors-country-filter").select_option("US", timeout=timeout_ms)
        page.get_by_test_id("investors-stage-filter").select_option("Series A", timeout=timeout_ms)
        page.get_by_text("RA Capital Management").first.wait_for(state="visible", timeout=timeout_ms)

        visible_cards = page.locator('[data-testid^="investor-card-"]').count()
        if visible_cards != 1:
            failures.append(f"{route_name}: expected one filtered investor card, got {visible_cards}")
        if page.get_by_test_id("investor-card-vc-korea-oncology").count() > 0:
            failures.append(f"{route_name}: KR oncology card stayed visible after country filter")
        if page.get_by_test_id("investor-card-vc-us-digital-health").count() > 0:
            failures.append(f"{route_name}: US Seed card stayed visible after Series A filter")

        result_count = page.get_by_test_id("investors-result-count").inner_text(timeout=timeout_ms)
        if "1" not in result_count or "5" not in result_count:
            failures.append(f"{route_name}: result count did not show one of five investors: {result_count!r}")

        website_href = page.get_by_test_id("investor-website-vc-ra-capital").get_attribute("href", timeout=timeout_ms)
        if website_href != "https://www.racap.com/":
            failures.append(f"{route_name}: RA Capital website href mismatch: {website_href}")
        email_href = page.get_by_test_id("investor-email-vc-ra-capital").get_attribute("href", timeout=timeout_ms)
        if email_href != "mailto:deals@racap.com":
            failures.append(f"{route_name}: RA Capital email href mismatch: {email_href}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(vcs_route_pattern, fulfill_vcs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


def _run_investors_seed_directory_fallback_check(page, base_url: str, timeout_ms: int) -> list[str]:
    route_name = "investors-seed-directory-fallback"
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    vcs_route_pattern = "**/vcs?*"

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    def fulfill_empty_vcs(route) -> None:
        request = route.request
        if request.method.upper() != "GET" or request.resource_type not in {"fetch", "xhr"}:
            route.continue_()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps([]))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)
    page.route(vcs_route_pattern, fulfill_empty_vcs)

    try:
        page.add_init_script(
            """
            (() => {
              window.localStorage.setItem('dsci.locale', 'en-US');
              window.localStorage.setItem('dsci.outputLanguage', 'en');
            })();
            """
        )
        response = _goto_app_route(page, base_url, "/investors", timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{route_name}: HTTP status {status}")

        fallback_banner = page.get_by_test_id("investors-fallback-banner")
        fallback_banner.wait_for(state="visible", timeout=timeout_ms)
        fallback_text = fallback_banner.inner_text(timeout=timeout_ms)
        if "curated launch directory" not in fallback_text:
            failures.append(f"{route_name}: fallback banner copy mismatch: {fallback_text!r}")

        seed_card = page.get_by_test_id("investor-card-vc-kip-001")
        seed_card.wait_for(state="visible", timeout=timeout_ms)
        page.get_by_text("Korea Investment Partners").first.wait_for(state="visible", timeout=timeout_ms)

        empty_state_count = page.get_by_text("No investors match your filters").count()
        if empty_state_count:
            failures.append(f"{route_name}: rendered empty state while seed directory fallback was active")

        result_count = page.get_by_test_id("investors-result-count").inner_text(timeout=timeout_ms)
        if "5" not in result_count:
            failures.append(f"{route_name}: result count did not include fallback seed count: {result_count!r}")
    except PlaywrightTimeoutError as exc:
        failures.append(f"{route_name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{route_name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)
        page.unroute(vcs_route_pattern, fulfill_empty_vcs)

    failures.extend(_browser_error_failures(route_name, console_errors, page_errors))
    return failures


PUBLIC_ACTION_CHECKS = (
    ("landing-cta-intent", "/ -> /explore, /pricing, /login or /upload", _run_landing_cta_intent_check),
    ("explore-analyze-intent", "/explore -> /login or /biolinker", _run_explore_analyze_intent_check),
    ("investors-filter-directory", "/investors", _run_investors_filter_directory_check),
    ("investors-seed-directory-fallback", "/investors empty /vcs -> launch seed directory", _run_investors_seed_directory_fallback_check),
    ("pricing-enterprise-contact-intent", "/pricing enterprise -> sales contact", _run_pricing_enterprise_contact_intent_check),
    ("pricing-layout-inset", "/pricing responsive layout", _run_pricing_layout_inset_check),
    ("public-touch-targets", "/, /explore, /investors, /pricing mobile touch targets", _run_public_touch_targets_check),
)


ANONYMOUS_ACTION_CHECKS = (
    ("pricing-anonymous-paid-redirect", "/pricing anonymous -> /login?next=/pricing&plan=pro", _run_pricing_anonymous_paid_redirect_check),
)


AUTHENTICATED_ACTION_CHECKS = (
    ("dashboard-quick-upload-click", "/dashboard -> /upload", _run_dashboard_quick_upload_click_check),
    ("dashboard-readiness-refresh", "/dashboard", _run_dashboard_readiness_refresh_check),
    ("dashboard-readiness-copy-failure", "/dashboard clipboard denial", _run_dashboard_readiness_clipboard_failure_check),
    ("dashboard-recommendation-source-link-fallback", "/dashboard recommendation source link fallback", _run_dashboard_recommendation_source_link_check),
    ("pricing-checkout-mocked", "/pricing -> /subscription/success", _run_pricing_checkout_mocked_check),
    ("pricing-checkout-yearly", "/pricing yearly -> /subscription/success", _run_pricing_checkout_yearly_check),
    ("pricing-checkout-cancelled", "/pricing -> /pricing?checkout=cancelled", _run_pricing_checkout_cancelled_check),
    ("pricing-checkout-error-visible", "/pricing checkout failure", _run_pricing_checkout_error_check),
    ("pricing-billing-portal", "/pricing paid account -> billing portal", _run_pricing_billing_portal_check),
    ("pricing-billing-portal-error-visible", "/pricing billing portal failure", _run_pricing_billing_portal_error_check),
    ("upload-form-readiness", "/upload", _run_upload_form_readiness_check),
    ("protected-mobile-layout-inset", "/upload mobile layout", _run_protected_mobile_layout_inset_check),
    ("upload-submit-receipt", "/upload submit -> durable receipt", _run_upload_submit_receipt_check),
    ("upload-submit-wallet-receipt", "/upload connected wallet -> mint/reward receipt", _run_upload_submit_wallet_receipt_check),
    ("asset-upload-readiness", "/assets", _run_asset_upload_readiness_check),
    ("biolinker-rfp-readiness", "/biolinker", _run_biolinker_rfp_readiness_check),
    ("biolinker-paper-context-handoff", "/biolinker?paper_id=...", _run_biolinker_paper_context_handoff_check),
    ("biolinker-proposal-clipboard-failure", "/biolinker proposal copy denied", _run_biolinker_proposal_clipboard_failure_check),
    ("biolinker-proposal-export-popup-blocked", "/biolinker proposal export popup blocked", _run_biolinker_proposal_export_popup_blocked_check),
    ("biolinker-empty-match-next-actions", "/biolinker?paper_id=... empty", _run_biolinker_empty_match_next_actions_check),
    ("notices-discovery-readiness", "/notices", _run_notices_discovery_readiness_check),
    ("notices-discovery-biolinker-handoff", "/notices discovery -> /biolinker", _run_notices_discovery_biolinker_handoff_check),
    ("notices-source-link-fallback", "/notices source link fallback", _run_notices_source_link_fallback_check),
    ("notices-biolinker-bridge", "/notices -> /biolinker", _run_notices_biolinker_bridge_check),
    ("ai-lab-readiness", "/ai-lab", _run_ai_lab_readiness_check),
    ("ai-lab-agent-error-visible", "/ai-lab provider failure", _run_ai_lab_agent_error_check),
    ("ai-lab-result-copy-failure", "/ai-lab result copy denied", _run_ai_lab_result_copy_failure_check),
    ("peer-review-readiness", "/peer-review", _run_peer_review_readiness_check),
    ("peer-review-submit-receipt", "/peer-review connected wallet -> review reward receipt", _run_peer_review_submit_receipt_check),
    ("mylab-mint-wallet-required", "/mylab", _run_mylab_mint_wallet_required_check),
    ("mylab-mint-success", "/mylab connected mint", _run_mylab_mint_success_check),
    ("vc-portal-select", "/vc-portal", _run_vc_portal_select_check),
    ("governance-wallet-required", "/governance", _run_governance_wallet_required_check),
    ("governance-connected-create-vote", "/governance connected wallet", _run_governance_connected_create_vote_check),
    ("wallet-restore-direct-governance", "/governance restored wallet", _run_wallet_restore_direct_governance_check),
    ("wallet-extension-missing", "/wallet", _run_wallet_extension_missing_check),
    ("wallet-provider-amoy", "/wallet", _run_wallet_provider_amoy_check),
)


LAUNCH_CLICK_SUITE_CHECKS = (
    "landing-cta-intent",
    "explore-analyze-intent",
    "pricing-enterprise-contact-intent",
    "dashboard-quick-upload-click",
    "dashboard-readiness-refresh",
    "pricing-checkout-mocked",
    "upload-form-readiness",
    "upload-submit-receipt",
    "asset-upload-readiness",
)


def _run_check(page, base_url: str, check: RouteCheck, timeout_ms: int) -> list[str]:
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    def collect_console(message) -> None:
        if message.type == "error":
            console_errors.append(message.text)

    def collect_page_error(error) -> None:
        page_errors.append(str(error))

    page.on("console", collect_console)
    page.on("pageerror", collect_page_error)

    try:
        response = _goto_app_route(page, base_url, check.path, timeout_ms)
        status = response.status if response is not None else 0
        if status >= 400:
            failures.append(f"{check.name}: HTTP status {status}")
        if check.expected_url_path and hasattr(page, "wait_for_url"):
            page.wait_for_url(re.compile(rf".*{re.escape(check.expected_url_path)}(?:[?#].*)?$"), timeout=timeout_ms)
        _wait_for_route_render(page, check, timeout_ms)

        body_text = page.locator("body").inner_text(timeout=timeout_ms)
        failures.extend(_collect_body_failures(check, body_text))
        failures.extend(_redirect_failures(check, page.url))
    except PlaywrightTimeoutError as exc:
        failures.append(f"{check.name}: timed out ({exc})")
    except PlaywrightError as exc:
        failures.append(f"{check.name}: browser error ({exc})")
    finally:
        page.remove_listener("console", collect_console)
        page.remove_listener("pageerror", collect_page_error)

    failures.extend(_browser_error_failures(check.name, console_errors, page_errors))
    return failures


def _safe_trace_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return safe[:80] or "browser-smoke"


def _trace_artifact_path(trace_dir: str | Path, trace_name: str) -> Path:
    return Path(trace_dir) / f"{_safe_trace_name(trace_name)}.trace.zip"


def _run_with_fresh_page(
    browser,
    runner,
    *args,
    trace_dir: str | Path | None = None,
    trace_name: str | None = None,
) -> FreshPageResult:
    page = browser.new_page()
    failed_requests: list[str] = []
    http_error_responses: list[str] = []
    trace_started = False
    trace_path: Path | None = None
    failures: list[str] = []

    def collect_request_failed(request) -> None:
        if _is_network_diagnostic_request(request):
            failed_requests.append(_request_failure_text(request))

    def collect_response(response) -> None:
        request = getattr(response, "request", None)
        if not request or not _is_network_diagnostic_request(request):
            return
        status = getattr(response, "status", 0)
        if isinstance(status, int) and status >= 400:
            http_error_responses.append(_response_error_text(response))

    try:
        if trace_dir is not None and trace_name:
            Path(trace_dir).mkdir(parents=True, exist_ok=True)
            page.context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
                title=trace_name,
            )
            trace_started = True
        page.on("requestfailed", collect_request_failed)
        page.on("response", collect_response)
        failures = runner(page, *args)
        if failures:
            failures = list(failures)
            failures.extend(_network_diagnostic_failures(failed_requests, http_error_responses))
    finally:
        if trace_started:
            try:
                if failures:
                    trace_path = _trace_artifact_path(trace_dir, trace_name or "browser-smoke")
                    page.context.tracing.stop(path=str(trace_path))
                else:
                    page.context.tracing.stop()
            except PlaywrightError as exc:
                if failures:
                    failures.append(f"{trace_name or 'browser-smoke'}: trace capture failed ({exc})")
                    trace_path = None
        page.remove_listener("requestfailed", collect_request_failed)
        page.remove_listener("response", collect_response)
        page.close()
    return FreshPageResult(failures=failures, trace_path=str(trace_path) if trace_path else None)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run browser smoke checks against the DSCI frontend.")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173", help="Frontend base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout per route in seconds")
    parser.add_argument("--skip-protected", action="store_true", help="Skip protected route redirect checks")
    parser.add_argument("--skip-login-validation", action="store_true", help="Skip login form validation interaction")
    parser.add_argument(
        "--only-check",
        action="append",
        default=[],
        help="Run only the named check. Can be provided multiple times.",
    )
    parser.add_argument(
        "--expect-dev-auth",
        action="store_true",
        help=(
            "Expect the frontend to be running with VITE_ENABLE_DEV_AUTH_BYPASS=true "
            "and validate protected screens instead of anonymous redirects."
        ),
    )
    parser.add_argument(
        "--launch-click-suite",
        action="store_true",
        help=(
            "Run the launch-critical browser click preset. Requires --expect-dev-auth "
            "because it covers dashboard, checkout, upload, and asset paths."
        ),
    )
    parser.add_argument("--json-out", help="Optional JSON evidence output file")
    parser.add_argument(
        "--trace-on-failure-dir",
        help="Optional directory for Playwright trace zip artifacts. Traces are kept only for failed checks.",
    )
    return parser.parse_args(argv)


def _requested_check_names(args: argparse.Namespace) -> set[str]:
    requested = set(args.only_check or [])
    if args.launch_click_suite:
        requested.update(LAUNCH_CLICK_SUITE_CHECKS)
    return requested


def _selected_by_name(args: argparse.Namespace, name: str) -> bool:
    requested = _requested_check_names(args)
    return not requested or name in requested


def _base_checks_for_args(args: argparse.Namespace) -> list[RouteCheck]:
    checks = list(PUBLIC_CHECKS)
    if args.expect_dev_auth:
        checks = [check for check in checks if check.name != "login"]
        checks.append(
            RouteCheck(
                "login-dev-auth-redirect",
                "/login",
                ("dev-auth@desci.local",),
                expected_url_path="/dashboard",
            )
        )
        checks.extend(AUTHENTICATED_CHECKS)
    elif not args.skip_protected:
        checks.extend(PROTECTED_REDIRECT_CHECKS)
    return checks


def _checks_for_args(args: argparse.Namespace) -> list[RouteCheck]:
    return [check for check in _base_checks_for_args(args) if _selected_by_name(args, check.name)]


def _base_action_checks_for_args(args: argparse.Namespace) -> list[tuple[str, str, Callable]]:
    checks = list(PUBLIC_ACTION_CHECKS)
    if not args.expect_dev_auth:
        checks.extend(ANONYMOUS_ACTION_CHECKS)
    if args.expect_dev_auth:
        checks.extend(AUTHENTICATED_ACTION_CHECKS)
    return checks


def _action_checks_for_args(args: argparse.Namespace) -> list[tuple[str, str, Callable]]:
    return [check for check in _base_action_checks_for_args(args) if _selected_by_name(args, check[0])]


def _should_run_login_validation(args: argparse.Namespace) -> bool:
    return not args.skip_login_validation and _selected_by_name(args, "login-validation")


def _validate_only_checks(args: argparse.Namespace) -> None:
    if args.launch_click_suite and not args.expect_dev_auth:
        raise ValueError("--launch-click-suite requires --expect-dev-auth")
    requested = _requested_check_names(args)
    if not requested:
        return
    available = {check.name for check in _base_checks_for_args(args)}
    available.update(check[0] for check in _base_action_checks_for_args(args))
    if not args.skip_login_validation:
        available.add("login-validation")
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"Unknown or unavailable browser smoke check(s): {', '.join(missing)}")


def write_json_report(
    path: str | Path,
    *,
    frontend: str,
    reports: list[BrowserCheckReport],
    failures: list[str],
    playwright_available: bool,
    timeout_seconds: float | None = None,
    skip_protected: bool | None = None,
    skip_login_validation: bool | None = None,
    expect_dev_auth: bool | None = None,
    launch_click_suite: bool | None = None,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failed_count = sum(1 for report in reports if not report.ok)
    if failures and not failed_count:
        failed_count = len(failures)
    launch_control = browser_launch_control_report(reports)
    launch_click_suite_report = browser_launch_click_suite_report(reports) if launch_click_suite else None
    trace_artifacts = [
        {"check_name": report.name, "path": report.trace_path}
        for report in reports
        if isinstance(report.trace_path, str) and report.trace_path
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failures,
        "frontend": frontend,
        "timeout_seconds": timeout_seconds,
        "skip_protected": skip_protected,
        "skip_login_validation": skip_login_validation,
        "expect_dev_auth": expect_dev_auth,
        "launch_click_suite": launch_click_suite,
        "playwright_available": playwright_available,
        "summary": {
            "total": len(reports),
            "passed": sum(1 for report in reports if report.ok),
            "failed": failed_count,
        },
        "launch_control": launch_control,
        "launch_click_suite_report": launch_click_suite_report,
        "trace_artifacts": trace_artifacts,
        "failures": failures,
        "checks": [],
    }
    for report in reports:
        check_payload: dict[str, Any] = {
            "name": report.name,
            "path": report.path,
            "ok": report.ok,
            "failures": report.failures,
        }
        if report.trace_path:
            check_payload["trace_path"] = report.trace_path
        payload["checks"].append(check_payload)
    if launch_control is None:
        payload.pop("launch_control")
    if launch_click_suite is None:
        payload.pop("launch_click_suite")
    if launch_click_suite_report is None:
        payload.pop("launch_click_suite_report")
    if not trace_artifacts:
        payload.pop("trace_artifacts")
    write_json_atomic(output_path, payload, trailing_newline=True)
    _print_progress(f"[browser-smoke] json written: {output_path}")


def browser_launch_control_report(reports: list[BrowserCheckReport]) -> dict[str, Any] | None:
    check_report = next((report for report in reports if report.name == "dashboard-readiness-refresh"), None)
    if check_report is None:
        return None

    launch_payload = _dashboard_launch_payload()
    next_actions = launch_payload.get("next_actions")
    if not isinstance(next_actions, list):
        next_actions = []
    next_action_ids, next_action_required_env = _launch_action_coverage(next_actions)
    report: dict[str, Any] = {
        "check_name": check_report.name,
        "ok": check_report.ok,
        "evidence_source": "browser-smoke-dashboard-fixture",
        "api_mocked": True,
        "mocked_endpoints": list(DASHBOARD_READINESS_MOCKED_ENDPOINTS),
        "release_decision": launch_payload.get("release_decision"),
        "operator_phase": launch_payload.get("operator_phase"),
        "readiness_status": launch_payload.get("readiness_status"),
        "summary": launch_payload.get("summary") if isinstance(launch_payload.get("summary"), dict) else {},
        "score": launch_payload.get("score") if isinstance(launch_payload.get("score"), dict) else {},
        "launch_blockers": launch_payload.get("launch_blockers")
        if isinstance(launch_payload.get("launch_blockers"), list)
        else [],
        "next_action_count": len(next_actions),
        "failures": check_report.failures,
    }
    if next_action_ids:
        report["next_action_ids"] = next_action_ids
    if next_action_required_env:
        report["next_action_required_env"] = next_action_required_env
    return report


def browser_launch_click_suite_report(reports: list[BrowserCheckReport]) -> dict[str, Any]:
    report_by_name = {report.name: report for report in reports}
    selected_reports = [report_by_name[name] for name in LAUNCH_CLICK_SUITE_CHECKS if name in report_by_name]
    missing = [name for name in LAUNCH_CLICK_SUITE_CHECKS if name not in report_by_name]
    failed = [report.name for report in selected_reports if not report.ok]
    return {
        "suite": "launch-click",
        "expected_check_count": len(LAUNCH_CLICK_SUITE_CHECKS),
        "executed_check_count": len(selected_reports),
        "passed_check_count": sum(1 for report in selected_reports if report.ok),
        "failed_check_count": len(failed),
        "missing_checks": missing,
        "failed_checks": failed,
        "check_names": list(LAUNCH_CLICK_SUITE_CHECKS),
    }


def _launch_action_coverage(next_actions: list[Any]) -> tuple[list[str], list[str]]:
    action_ids: list[str] = []
    required_env: list[str] = []
    for action in next_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id:
            action_ids.append(action_id)
        env_values = action.get("required_env")
        if isinstance(env_values, list):
            required_env.extend(item for item in env_values if isinstance(item, str) and item)
    return _unique_strings(action_ids), _unique_strings(required_env)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_output()

    args = parse_args(argv)
    if args.expect_dev_auth:
        args.skip_login_validation = True

    if sync_playwright is None:
        _print_progress("[browser-smoke] Playwright is not installed. Install with: python -m pip install playwright")
        if args.json_out:
            write_json_report(
                args.json_out,
                frontend=args.frontend,
                reports=[],
                failures=["playwright is not installed"],
                playwright_available=False,
                timeout_seconds=args.timeout,
                skip_protected=args.skip_protected,
                skip_login_validation=args.skip_login_validation,
                expect_dev_auth=args.expect_dev_auth,
                launch_click_suite=args.launch_click_suite,
            )
        return 2

    _validate_only_checks(args)
    checks = _checks_for_args(args)
    action_checks = _action_checks_for_args(args)

    failures: list[str] = []
    reports: list[BrowserCheckReport] = []
    timeout_ms = int(args.timeout * 1000)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for check in checks:
                result = _run_with_fresh_page(
                    browser,
                    _run_check,
                    args.frontend,
                    check,
                    timeout_ms,
                    trace_dir=args.trace_on_failure_dir,
                    trace_name=check.name,
                )
                status = "FAIL" if result.failures else "OK"
                _print_progress(f"[browser-smoke] {check.name:<18} {status} {check.path}")
                failures.extend(result.failures)
                reports.append(
                    BrowserCheckReport(
                        name=check.name,
                        path=check.path,
                        ok=not result.failures,
                        failures=result.failures,
                        trace_path=result.trace_path,
                    )
                )
            for check_name, check_path, check_runner in action_checks:
                result = _run_with_fresh_page(
                    browser,
                    check_runner,
                    args.frontend,
                    timeout_ms,
                    trace_dir=args.trace_on_failure_dir,
                    trace_name=check_name,
                )
                status = "FAIL" if result.failures else "OK"
                _print_progress(f"[browser-smoke] {check_name:<18} {status} {check_path}")
                failures.extend(result.failures)
                reports.append(
                    BrowserCheckReport(
                        name=check_name,
                        path=check_path,
                        ok=not result.failures,
                        failures=result.failures,
                        trace_path=result.trace_path,
                    )
                )
            if _should_run_login_validation(args):
                result = _run_with_fresh_page(
                    browser,
                    _run_login_validation_check,
                    args.frontend,
                    timeout_ms,
                    trace_dir=args.trace_on_failure_dir,
                    trace_name="login-validation",
                )
                status = "FAIL" if result.failures else "OK"
                _print_progress(f"[browser-smoke] {'login-validation':<18} {status} /login")
                failures.extend(result.failures)
                reports.append(
                    BrowserCheckReport(
                        name="login-validation",
                        path="/login",
                        ok=not result.failures,
                        failures=result.failures,
                        trace_path=result.trace_path,
                    )
                )
        finally:
            browser.close()

    if args.json_out:
        write_json_report(
            args.json_out,
            frontend=args.frontend,
            reports=reports,
            failures=failures,
            playwright_available=True,
            timeout_seconds=args.timeout,
            skip_protected=args.skip_protected,
            skip_login_validation=args.skip_login_validation,
            expect_dev_auth=args.expect_dev_auth,
            launch_click_suite=args.launch_click_suite,
        )

    if failures:
        _print_progress("\n[browser-smoke] FAILED")
        for failure in failures:
            _print_progress(f"- {failure}")
        return 1

    _print_progress("\n[browser-smoke] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
