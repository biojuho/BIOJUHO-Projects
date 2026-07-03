from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import browser_smoke  # noqa: E402


class _FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int) -> str:  # noqa: ARG002
        return self.text


class _FakeTracing:
    def __init__(self) -> None:
        self.started = []
        self.stopped = []

    def start(self, **kwargs):
        self.started.append(kwargs)

    def stop(self, path=None):
        self.stopped.append(path)
        if path:
            Path(path).write_text("fake trace", encoding="utf-8")


class _FakeContext:
    def __init__(self) -> None:
        self.tracing = _FakeTracing()


class _FakePage:
    def __init__(self, body: str, status: int = 200, url: str = "http://test/") -> None:
        self.body = body
        self.status = status
        self.url = url
        self.handlers = {}
        self.removed = []
        self.goto_wait_until = []
        self.closed = False
        self.context = _FakeContext()

    def on(self, event: str, handler):
        self.handlers[event] = handler

    def remove_listener(self, event: str, handler):
        self.removed.append((event, handler))

    def goto(self, url: str, wait_until: str, timeout: int):  # noqa: ARG002
        self.url = url if self.url == "http://test/" else self.url
        self.goto_wait_until.append(wait_until)
        return SimpleNamespace(status=self.status)

    def locator(self, selector: str):  # noqa: ARG002
        return _FakeLocator(self.body)

    def close(self):
        self.closed = True


class _CountLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class _PricingSessionProbePage:
    def __init__(self, dashboard_link_count: int) -> None:
        self.dashboard_link_count = dashboard_link_count
        self.selectors: list[str] = []

    def locator(self, selector: str):
        self.selectors.append(selector)
        return _CountLocator(self.dashboard_link_count)


class _NeverVisibleTextLocator:
    @property
    def first(self):
        return self

    def wait_for(self, *, state: str, timeout: int):  # noqa: ARG002
        raise browser_smoke.PlaywrightTimeoutError("text not visible yet")


class _LateRenderPage(_FakePage):
    def __init__(self, body: str, status: int = 200, url: str = "http://test/") -> None:
        super().__init__(body, status=status, url=url)
        self.text_queries: list[str] = []
        self.wait_for_function_args = None

    def get_by_text(self, text: str):
        self.text_queries.append(text)
        return _NeverVisibleTextLocator()

    def wait_for_function(self, expression: str, *, arg, timeout: int):  # noqa: ARG002
        self.wait_for_function_args = (expression, arg, timeout)
        assert any(text in self.body for text in arg)
        return True


class _FakeBrowser:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages
        self.created = []

    def new_page(self):
        page = self.pages.pop(0)
        self.created.append(page)
        return page


class _FakeRequest:
    def __init__(
        self,
        *,
        url: str,
        method: str = "GET",
        resource_type: str = "fetch",
        failure: str = "net::ERR_CONNECTION_FAILED",
    ) -> None:
        self.url = url
        self.method = method
        self.resource_type = resource_type
        self.failure = failure


class _FakeResponse:
    def __init__(self, *, url: str, status: int, request: _FakeRequest) -> None:
        self.url = url
        self.status = status
        self.request = request


def test_run_check_passes_and_removes_listeners() -> None:
    page = _FakePage("DSCI dashboard content is long enough to be valid.")
    check = browser_smoke.RouteCheck("home", "/", ("DSCI",))

    failures = browser_smoke._run_check(page, "http://test", check, 1000)  # pylint: disable=protected-access

    assert failures == []
    assert {event for event, _ in page.removed} == {"console", "pageerror"}
    assert page.goto_wait_until == ["domcontentloaded"]


def test_run_check_waits_for_late_route_text_before_reading_body() -> None:
    page = _LateRenderPage("Match Studio route content is now long enough to be valid.")
    check = browser_smoke.RouteCheck("biolinker-authenticated", "/biolinker", ("Match Studio",))

    failures = browser_smoke._run_check(page, "http://test", check, 5000)  # pylint: disable=protected-access

    assert failures == []
    assert page.text_queries == ["Match Studio"]
    assert page.wait_for_function_args is not None
    assert page.wait_for_function_args[1] == ["Match Studio"]
    assert page.wait_for_function_args[2] == 5000


def test_browser_smoke_does_not_wait_for_network_idle() -> None:
    source = inspect.getsource(browser_smoke)

    assert "networkidle" not in source
    assert "wait_for_load_state" not in source


def test_browser_smoke_progress_prints_flush() -> None:
    source = inspect.getsource(browser_smoke._print_progress)  # pylint: disable=protected-access

    assert "flush=True" in source


def test_run_with_fresh_page_closes_page() -> None:
    page = _FakePage("DSCI isolated page content is long enough.")
    browser = _FakeBrowser([page])

    def runner(active_page, value: str) -> list[str]:
        assert active_page is page
        assert value == "ok"
        return []

    result = browser_smoke._run_with_fresh_page(browser, runner, "ok")  # pylint: disable=protected-access

    assert result.failures == []
    assert result.trace_path is None
    assert browser.created == [page]
    assert page.closed is True


def test_run_with_fresh_page_appends_network_diagnostics_only_when_check_fails() -> None:
    page = _FakePage("DSCI isolated page content is long enough.")
    browser = _FakeBrowser([page])

    def runner(active_page) -> list[str]:
        failed_request = _FakeRequest(url="http://api.test/papers/me")
        error_response = _FakeResponse(
            url="http://api.test/ready",
            status=503,
            request=_FakeRequest(url="http://api.test/ready"),
        )
        active_page.handlers["requestfailed"](failed_request)
        active_page.handlers["response"](error_response)
        return ["upload-form-readiness: timed out"]

    result = browser_smoke._run_with_fresh_page(browser, runner)  # pylint: disable=protected-access

    failures = result.failures
    assert failures[0] == "upload-form-readiness: timed out"
    assert "network request failed: GET http://api.test/papers/me failed: net::ERR_CONNECTION_FAILED" in failures
    assert "network HTTP error: GET http://api.test/ready returned HTTP 503" in failures
    assert result.trace_path is None
    assert {event for event, _ in page.removed} == {"requestfailed", "response"}


def test_run_with_fresh_page_suppresses_network_diagnostics_when_check_passes() -> None:
    page = _FakePage("DSCI isolated page content is long enough.")
    browser = _FakeBrowser([page])

    def runner(active_page) -> list[str]:
        active_page.handlers["requestfailed"](_FakeRequest(url="http://api.test/expected-failure"))
        return []

    result = browser_smoke._run_with_fresh_page(browser, runner)  # pylint: disable=protected-access

    assert result.failures == []
    assert result.trace_path is None


def test_run_with_fresh_page_discards_trace_when_check_passes(tmp_path: Path) -> None:
    page = _FakePage("DSCI isolated page content is long enough.")
    browser = _FakeBrowser([page])

    def runner(active_page) -> list[str]:
        assert active_page is page
        return []

    result = browser_smoke._run_with_fresh_page(  # pylint: disable=protected-access
        browser,
        runner,
        trace_dir=tmp_path,
        trace_name="home",
    )

    assert result.failures == []
    assert result.trace_path is None
    assert page.context.tracing.started == [{"screenshots": True, "snapshots": True, "sources": True, "title": "home"}]
    assert page.context.tracing.stopped == [None]
    assert list(tmp_path.glob("*.zip")) == []


def test_run_with_fresh_page_keeps_trace_when_check_fails(tmp_path: Path) -> None:
    page = _FakePage("DSCI isolated page content is long enough.")
    browser = _FakeBrowser([page])

    def runner(active_page) -> list[str]:
        assert active_page is page
        return ["dashboard-readiness-refresh: timed out"]

    result = browser_smoke._run_with_fresh_page(  # pylint: disable=protected-access
        browser,
        runner,
        trace_dir=tmp_path,
        trace_name="dashboard readiness refresh",
    )

    expected_trace = tmp_path / "dashboard-readiness-refresh.trace.zip"
    assert result.failures == ["dashboard-readiness-refresh: timed out"]
    assert result.trace_path == str(expected_trace)
    assert page.context.tracing.stopped == [str(expected_trace)]
    assert expected_trace.read_text(encoding="utf-8") == "fake trace"


def test_run_check_reports_status_missing_text_redirect_and_console_errors() -> None:
    page = _FakePage("Short body", status=500, url="http://test/dashboard")
    check = browser_smoke.RouteCheck("dashboard", "/dashboard", ("Expected",), expected_url_path="/login")
    failures = browser_smoke._run_check(page, "http://test", check, 1000)  # pylint: disable=protected-access

    assert "dashboard: HTTP status 500" in failures
    assert "dashboard: body is unexpectedly short" in failures
    assert "dashboard: missing expected text 'Expected'" in failures
    assert "dashboard: expected final path /login, got /dashboard" in failures


def test_run_check_reports_visible_raw_transport_errors() -> None:
    page = _FakePage("DSCI dashboard rendered Failed to fetch in the visible panel.")
    check = browser_smoke.RouteCheck("dashboard", "/dashboard", ("DSCI",))

    failures = browser_smoke._run_check(page, "http://test", check, 1000)  # pylint: disable=protected-access

    assert "dashboard: rendered raw transport error text 'Failed to fetch'" in failures


def test_collect_browser_errors_limits_messages() -> None:
    failures = browser_smoke._browser_error_failures(  # pylint: disable=protected-access
        "route",
        [f"console-{index}" for index in range(7)],
        [f"page-{index}" for index in range(7)],
    )

    assert len(failures) == 10
    assert failures[0] == "route: console error: console-0"
    assert failures[-1] == "route: page error: page-4"


def test_browser_smoke_writes_json_evidence(tmp_path) -> None:
    output = tmp_path / "browser-smoke.json"
    reports = [
        browser_smoke.BrowserCheckReport(name="home", path="/", ok=True, failures=[]),
        browser_smoke.BrowserCheckReport(name="pricing", path="/pricing", ok=False, failures=["pricing: missing text"]),
    ]

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=reports,
        failures=["pricing: missing text"],
        playwright_available=True,
        timeout_seconds=15.0,
        skip_protected=False,
        skip_login_validation=False,
        expect_dev_auth=False,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    assert payload["frontend"] == "http://frontend"
    assert payload["timeout_seconds"] == 15.0
    assert payload["skip_protected"] is False
    assert payload["skip_login_validation"] is False
    assert payload["expect_dev_auth"] is False
    assert payload["playwright_available"] is True
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 1}
    assert "launch_control" not in payload
    assert payload["checks"][1]["failures"] == ["pricing: missing text"]
    assert not (output.parent / "browser-smoke.json.tmp").exists()


def test_browser_smoke_json_evidence_exposes_launch_control(tmp_path) -> None:
    output = tmp_path / "browser-smoke-launch-control.json"
    reports = [
        browser_smoke.BrowserCheckReport(name="dashboard-readiness-refresh", path="/dashboard", ok=True, failures=[]),
    ]
    expected_action_ids = ["auth", "stripe", "cors", "rabbitmq", "ipfs", "grobid"]
    expected_required_env = [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY",
        "STRIPE_PRICE_PRO_YEARLY",
        "ALLOWED_ORIGINS",
        "RABBITMQ_URL",
        "PINATA_JWT",
        "PINATA_API_KEY",
        "PINATA_API_SECRET",
        "GROBID_ENABLED",
        "GROBID_URL",
    ]

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=reports,
        failures=[],
        playwright_available=True,
        timeout_seconds=15.0,
        skip_protected=False,
        skip_login_validation=False,
        expect_dev_auth=True,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["launch_control"] == {
        "check_name": "dashboard-readiness-refresh",
        "ok": True,
        "evidence_source": "browser-smoke-dashboard-fixture",
        "api_mocked": True,
        "mocked_endpoints": list(browser_smoke.DASHBOARD_READINESS_MOCKED_ENDPOINTS),
        "release_decision": "no-go",
        "operator_phase": "blocked",
        "readiness_status": "blocked",
        "summary": {
            "ready_count": 7,
            "total": 13,
            "required_ready_count": 4,
            "required_total": 7,
            "blocker_count": 3,
            "warning_count": 3,
        },
        "score": {"overall_percent": 54, "required_percent": 57},
        "launch_blockers": ["auth", "stripe", "cors"],
        "next_action_count": 6,
        "next_action_ids": expected_action_ids,
        "next_action_required_env": expected_required_env,
        "failures": [],
    }


def test_browser_smoke_json_evidence_exposes_launch_click_suite(tmp_path) -> None:
    output = tmp_path / "browser-smoke-launch-click-suite.json"
    reports = [
        browser_smoke.BrowserCheckReport(name=name, path=f"/{name}", ok=True, failures=[])
        for name in browser_smoke.LAUNCH_CLICK_SUITE_CHECKS[:-1]
    ]
    reports.append(
        browser_smoke.BrowserCheckReport(
            name=browser_smoke.LAUNCH_CLICK_SUITE_CHECKS[-1],
            path="/assets",
            ok=False,
            failures=["asset-upload-readiness: missing uploader"],
        )
    )

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=reports,
        failures=["asset-upload-readiness: missing uploader"],
        playwright_available=True,
        timeout_seconds=15.0,
        skip_protected=False,
        skip_login_validation=True,
        expect_dev_auth=True,
        launch_click_suite=True,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["launch_click_suite"] is True
    assert payload["launch_click_suite_report"] == {
        "suite": "launch-click",
        "expected_check_count": len(browser_smoke.LAUNCH_CLICK_SUITE_CHECKS),
        "executed_check_count": len(browser_smoke.LAUNCH_CLICK_SUITE_CHECKS),
        "passed_check_count": len(browser_smoke.LAUNCH_CLICK_SUITE_CHECKS) - 1,
        "failed_check_count": 1,
        "missing_checks": [],
        "failed_checks": ["asset-upload-readiness"],
        "check_names": list(browser_smoke.LAUNCH_CLICK_SUITE_CHECKS),
    }


def test_browser_smoke_json_evidence_records_failure_traces(tmp_path) -> None:
    output = tmp_path / "browser-smoke-trace.json"
    trace_path = tmp_path / "traces" / "pricing.trace.zip"
    reports = [
        browser_smoke.BrowserCheckReport(
            name="pricing",
            path="/pricing",
            ok=False,
            failures=["pricing: missing text"],
            trace_path=str(trace_path),
        ),
    ]

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=reports,
        failures=["pricing: missing text"],
        playwright_available=True,
        timeout_seconds=15.0,
        skip_protected=False,
        skip_login_validation=False,
        expect_dev_auth=False,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["trace_artifacts"] == [{"check_name": "pricing", "path": str(trace_path)}]
    assert payload["checks"] == [
        {
            "name": "pricing",
            "path": "/pricing",
            "ok": False,
            "failures": ["pricing: missing text"],
            "trace_path": str(trace_path),
        }
    ]


def test_browser_smoke_json_evidence_counts_infrastructure_failure(tmp_path) -> None:
    output = tmp_path / "browser-smoke-missing-playwright.json"

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=[],
        failures=["playwright is not installed"],
        playwright_available=False,
        timeout_seconds=20.0,
        skip_protected=True,
        skip_login_validation=True,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    assert payload["playwright_available"] is False
    assert payload["timeout_seconds"] == 20.0
    assert payload["skip_protected"] is True
    assert payload["skip_login_validation"] is True
    assert payload["summary"] == {"total": 0, "passed": 0, "failed": 1}
    assert payload["failures"] == ["playwright is not installed"]


def test_browser_smoke_replaces_existing_json_report_atomically(tmp_path) -> None:
    output = tmp_path / "browser-smoke.json"
    output.write_text('{"old": true}', encoding="utf-8")

    browser_smoke.write_json_report(
        output,
        frontend="http://frontend",
        reports=[browser_smoke.BrowserCheckReport(name="home", path="/", ok=True, failures=[])],
        failures=[],
        playwright_available=True,
        timeout_seconds=15.0,
        skip_protected=True,
        skip_login_validation=True,
    )

    payload = browser_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "old" not in payload
    assert not (output.parent / "browser-smoke.json.tmp").exists()


def test_browser_smoke_parse_args_accepts_json_out_and_login_validation_skip() -> None:
    args = browser_smoke.parse_args([
        "--frontend",
        "http://frontend",
        "--skip-login-validation",
        "--json-out",
        "browser.json",
    ])

    assert args.frontend == "http://frontend"
    assert args.skip_login_validation is True
    assert args.expect_dev_auth is False
    assert args.launch_click_suite is False
    assert args.only_check == []
    assert args.json_out == "browser.json"
    assert args.trace_on_failure_dir is None


def test_browser_smoke_launch_click_suite_selects_release_click_paths() -> None:
    args = browser_smoke.parse_args([
        "--frontend",
        "http://frontend",
        "--expect-dev-auth",
        "--launch-click-suite",
    ])

    browser_smoke._validate_only_checks(args)  # pylint: disable=protected-access
    assert browser_smoke._checks_for_args(args) == []  # pylint: disable=protected-access
    assert [check[0] for check in browser_smoke._action_checks_for_args(args)] == list(  # pylint: disable=protected-access
        browser_smoke.LAUNCH_CLICK_SUITE_CHECKS
    )
    assert browser_smoke._should_run_login_validation(args) is False  # pylint: disable=protected-access


def test_browser_smoke_launch_click_suite_requires_dev_auth() -> None:
    args = browser_smoke.parse_args([
        "--frontend",
        "http://frontend",
        "--launch-click-suite",
    ])

    try:
        browser_smoke._validate_only_checks(args)  # pylint: disable=protected-access
    except ValueError as exc:
        assert "--launch-click-suite requires --expect-dev-auth" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected launch click suite without dev auth to raise ValueError")


def test_browser_smoke_only_check_filters_available_dev_auth_check() -> None:
    args = browser_smoke.parse_args([
        "--frontend",
        "http://frontend",
        "--expect-dev-auth",
        "--only-check",
        "notices-source-link-fallback",
    ])
    checks = browser_smoke._action_checks_for_args(args)  # pylint: disable=protected-access

    assert [check[0] for check in checks] == ["notices-source-link-fallback"]


def test_browser_smoke_only_check_rejects_unknown_or_unavailable_check() -> None:
    args = browser_smoke.parse_args([
        "--frontend",
        "http://frontend",
        "--only-check",
        "notices-source-link-fallback",
    ])

    try:
        browser_smoke._validate_only_checks(args)  # pylint: disable=protected-access
    except ValueError as exc:
        assert "notices-source-link-fallback" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected unavailable only-check to raise ValueError")


def test_browser_smoke_public_checks_cover_investor_directory() -> None:
    args = browser_smoke.parse_args(["--frontend", "http://frontend", "--skip-protected"])
    checks = browser_smoke._checks_for_args(args)  # pylint: disable=protected-access

    investors = next((check for check in checks if check.name == "investors"), None)
    assert investors is not None
    assert investors.path == "/investors"
    assert "투자자 디렉터리" in investors.expected_text


def test_browser_smoke_dev_auth_checks_replace_protected_redirects() -> None:
    args = browser_smoke.parse_args(["--frontend", "http://frontend", "--expect-dev-auth"])
    checks = browser_smoke._checks_for_args(args)  # pylint: disable=protected-access
    names = {check.name for check in checks}

    assert "login" not in names
    assert "login-dev-auth-redirect" in names
    assert "dashboard-authenticated" in names
    assert "biolinker-authenticated" in names
    assert "upload-authenticated" in names
    assert "mylab-authenticated" in names
    assert "vc-portal-authenticated" in names
    assert "notices-authenticated" in names
    assert "ai-lab-authenticated" in names
    assert "peer-review-authenticated" in names
    assert "wallet-authenticated" in names
    assert "assets-authenticated" in names
    assert "governance-authenticated" in names
    assert "dashboard-redirect" not in names
    assert "upload-redirect" not in names


def test_dashboard_smoke_fixtures_keep_ready_and_launch_consistent() -> None:
    ready = browser_smoke._dashboard_readiness_payload()  # pylint: disable=protected-access
    launch = browser_smoke._dashboard_launch_payload()  # pylint: disable=protected-access

    assert ready["status"] == launch["readiness_status"] == "blocked"
    for field in ("ready_count", "total", "required_ready_count", "required_total"):
        assert ready["summary"][field] == launch["summary"][field]
    assert ready["launch_blockers"] == launch["launch_blockers"] == ["auth", "stripe", "cors"]
    assert launch["release_decision"] == "no-go"
    assert launch["operator_phase"] == "blocked"
    assert launch["score"] == {"overall_percent": 54, "required_percent": 57}
    assert launch["summary"]["blocker_count"] == 3
    assert launch["summary"]["warning_count"] == 3
    assert [action["id"] for action in launch["next_actions"]] == [
        "auth",
        "stripe",
        "cors",
        "rabbitmq",
        "ipfs",
        "grobid",
    ]
    assert "stripe_return_url" not in ready["launch_blockers"]
    assert inspect.getsource(browser_smoke._dashboard_launch_payload).count("_dashboard_readiness_payload()") == 1


def test_dashboard_shell_route_handlers_accept_route_only() -> None:
    routes = browser_smoke._dashboard_shell_api_routes([])  # pylint: disable=protected-access

    assert len(routes) == 5
    for _, handler in routes:
        positional = [
            parameter
            for parameter in inspect.signature(handler).parameters.values()
            if parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ]
        assert len(positional) == 1
        assert positional[0].default is inspect.Parameter.empty


def test_dashboard_readiness_smoke_routes_launch_control_contract() -> None:
    source = inspect.getsource(browser_smoke._run_dashboard_readiness_refresh_check)  # pylint: disable=protected-access

    assert 'launch_route_pattern = "**/launch"' in source
    assert "fulfill_launch" in source
    assert "_dashboard_shell_api_routes" in source
    assert "product-readiness-launch-control" in source
    assert "product-readiness-release-decision" in source
    assert "product-readiness-operator-phase" in source
    assert "product-readiness-launch-drift" in source
    assert "refresh did not issue another /launch request" in source
    assert set(browser_smoke.DASHBOARD_READINESS_MOCKED_ENDPOINTS) == {
        "/ready",
        "/launch",
        "/me",
        "/papers/me",
        "/health",
        "/vcs",
        "/notices",
    }


def test_dashboard_quick_upload_smoke_mocks_dashboard_shell_routes() -> None:
    source = inspect.getsource(browser_smoke._run_dashboard_quick_upload_click_check)  # pylint: disable=protected-access

    assert "_dashboard_shell_api_routes" in source
    assert 'ready_route_pattern = "**/ready"' in source
    assert 'launch_route_pattern = "**/launch"' in source
    assert "page.route(pattern, handler)" in source
    assert "page.unroute(pattern, handler)" in source


def test_dashboard_clipboard_failure_smoke_routes_launch_control_contract() -> None:
    source = inspect.getsource(browser_smoke._run_dashboard_readiness_clipboard_failure_check)  # pylint: disable=protected-access

    assert 'launch_route_pattern = "**/launch"' in source
    assert "fulfill_launch" in source
    assert "page.unroute(launch_route_pattern, fulfill_launch)" in source


def test_browser_smoke_public_action_checks_include_public_click_paths() -> None:
    names = [name for name, _, _ in browser_smoke.PUBLIC_ACTION_CHECKS]

    assert names == [
        "landing-cta-intent",
        "explore-analyze-intent",
        "investors-filter-directory",
        "investors-seed-directory-fallback",
        "pricing-enterprise-contact-intent",
        "pricing-layout-inset",
        "public-touch-targets",
    ]


def test_investors_seed_directory_fallback_smoke_mocks_empty_vc_list() -> None:
    source = inspect.getsource(browser_smoke._run_investors_seed_directory_fallback_check)  # pylint: disable=protected-access

    assert 'vcs_route_pattern = "**/vcs?*"' in source
    assert "fulfill_empty_vcs" in source
    assert "json.dumps([])" in source
    assert "investors-fallback-banner" in source
    assert "investor-card-vc-kip-001" in source


def test_browser_smoke_anonymous_action_checks_include_paid_plan_login_redirect() -> None:
    names = [name for name, _, _ in browser_smoke.ANONYMOUS_ACTION_CHECKS]

    assert names == [
        "pricing-anonymous-paid-redirect",
    ]


def test_browser_smoke_detects_authenticated_pricing_session() -> None:
    page = _PricingSessionProbePage(dashboard_link_count=1)

    assert browser_smoke._pricing_authenticated_session_present(page) is True  # pylint: disable=protected-access
    assert page.selectors == ['nav.pricing-page-nav a[href="/dashboard"]']


def test_browser_smoke_anonymous_pricing_refuses_authenticated_frontend() -> None:
    source = inspect.getsource(browser_smoke._run_pricing_anonymous_paid_redirect_check)  # pylint: disable=protected-access

    assert "_pricing_authenticated_session_present(page, timeout_ms)" in source
    assert "rerun with --expect-dev-auth" in source
    assert "VITE_ENABLE_DEV_AUTH_BYPASS" in source


def test_browser_smoke_dev_auth_action_checks_include_vc_selector() -> None:
    names = [name for name, _, _ in browser_smoke.AUTHENTICATED_ACTION_CHECKS]

    assert names == [
        "dashboard-quick-upload-click",
        "dashboard-readiness-refresh",
        "dashboard-readiness-copy-failure",
        "dashboard-recommendation-source-link-fallback",
        "pricing-checkout-mocked",
        "pricing-checkout-yearly",
        "pricing-checkout-cancelled",
        "pricing-checkout-error-visible",
        "pricing-billing-portal",
        "pricing-billing-portal-error-visible",
        "upload-form-readiness",
        "protected-mobile-layout-inset",
        "upload-submit-receipt",
        "upload-submit-wallet-receipt",
        "asset-upload-readiness",
        "biolinker-rfp-readiness",
        "biolinker-paper-context-handoff",
        "biolinker-proposal-clipboard-failure",
        "biolinker-proposal-export-popup-blocked",
        "biolinker-empty-match-next-actions",
        "notices-discovery-readiness",
        "notices-discovery-biolinker-handoff",
        "notices-source-link-fallback",
        "notices-biolinker-bridge",
        "ai-lab-readiness",
        "ai-lab-agent-error-visible",
        "ai-lab-result-copy-failure",
        "peer-review-readiness",
        "peer-review-submit-receipt",
        "mylab-mint-wallet-required",
        "mylab-mint-success",
        "vc-portal-select",
        "governance-wallet-required",
        "governance-connected-create-vote",
        "wallet-restore-direct-governance",
        "wallet-extension-missing",
        "wallet-provider-amoy",
    ]


def test_vc_portal_selector_waits_for_loaded_options() -> None:
    source = inspect.getsource(browser_smoke._run_vc_portal_select_check)  # pylint: disable=protected-access

    assert "document.querySelectorAll('select option')" in source
    assert "some((option) => option.value)" in source


def test_pricing_subscription_browser_smoke_mocks_tier_fetch_after_redirects() -> None:
    yearly_source = inspect.getsource(browser_smoke._run_pricing_checkout_yearly_check)  # pylint: disable=protected-access
    cancelled_source = inspect.getsource(browser_smoke._run_pricing_checkout_cancelled_check)  # pylint: disable=protected-access

    for source in (yearly_source, cancelled_source):
        assert 'tier_route_pattern = "**/subscription/tier"' in source
        assert "page.route(tier_route_pattern, fulfill_tier)" in source
        assert "page.unroute(tier_route_pattern, fulfill_tier)" in source
        assert '"tier": "free"' in source


def test_pricing_layout_smoke_checks_responsive_inset_and_touch_target() -> None:
    source = inspect.getsource(browser_smoke._run_pricing_layout_inset_check)  # pylint: disable=protected-access

    assert '"mobile", {"width": 390, "height": 844}' in source
    assert '"desktop", {"width": 1440, "height": 900}' in source
    assert ".pricing-page-container h1" in source
    assert "pricing CTA is below touch target height" in source
    assert "horizontal document overflow" in source


def test_public_touch_target_smoke_checks_public_mobile_controls() -> None:
    source = inspect.getsource(browser_smoke._run_public_touch_targets_check)  # pylint: disable=protected-access

    assert 'set_viewport_size({"width": 390, "height": 844})' in source
    assert 'routes = ("/", "/explore", "/investors", "/pricing")' in source
    assert ".locale-toggle-button" in source
    assert "controls below 44px touch target" in source
    assert "horizontal document overflow" in source


def test_protected_mobile_layout_smoke_checks_mobile_inset() -> None:
    source = inspect.getsource(browser_smoke._run_protected_mobile_layout_inset_check)  # pylint: disable=protected-access

    assert 'set_viewport_size({"width": 390, "height": 844})' in source
    assert "mainPaddingLeft" in source
    assert "contentLeft" in source
    assert "menuWidth" in source
    assert "mobile navigation button collapsed" in source


def test_ai_lab_browser_fixture_passes_strict_quality_scorer() -> None:
    report = browser_smoke.score_ai_lab_output(
        browser_smoke.AI_LAB_DECISION_READY_FIXTURE,
        evidence_sources=browser_smoke.AI_LAB_EVIDENCE_SOURCES,
        require_evidence=True,
        require_quoted_evidence=True,
    )

    assert report["status"] == "pass"
    assert "quoted_evidence_matches_sources" not in report["failed_check_ids"]


def test_notices_discovery_biolinker_handoff_smoke_covers_structured_context() -> None:
    source = inspect.getsource(browser_smoke._run_notices_discovery_biolinker_handoff_check)  # pylint: disable=protected-access

    assert 'discover_route_pattern = "**/discover/grants"' in source
    assert "notices-discovery-analyze-browser-discovery-handoff" in source
    assert "biolinker-imported-notice-context" in source
    assert '"deadline_status": "closed"' in source
    assert '"readiness_score": 25' in source
    assert "Deadline status: Closed" in source
    assert "node.value.includes('Risk flags:" in source
    assert "Deadline has already passed." in source
    assert "notice import session storage was not cleared" in source
    assert 'analyze_route_pattern = "**/analyze"' in source
    assert "analyze POST ran before operator clicked Analyze fit" in source
    assert '"notice_context"' in source
    assert '"submission_timeline": ["Find renewed FOA before submission."]' in source
