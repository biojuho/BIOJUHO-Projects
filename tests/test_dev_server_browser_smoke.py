from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_browser_smoke.py"
BROWSER_MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "dev_server_browser_checks.json"
TARGETS_MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "dev_server_targets.json"


def load_browser_smoke_module():
    spec = importlib.util.spec_from_file_location("dev_server_browser_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_browser_manifest_validates_against_dev_server_targets() -> None:
    smoke = load_browser_smoke_module()
    browser_manifest = smoke.load_browser_manifest(BROWSER_MANIFEST_PATH)
    targets_manifest = smoke.load_targets_manifest(TARGETS_MANIFEST_PATH)

    errors = smoke.validate_manifest(browser_manifest, targets_manifest)

    assert errors == []
    assert {check["target_id"] for check in browser_manifest["checks"]} == {
        "dashboard-frontend",
        "agriguard-frontend",
        "desci-frontend",
        "canva-widget-preview",
    }
    assert sum(len(check["routes"]) for check in browser_manifest["checks"]) == 10


def test_dashboard_operator_checklist_text_is_manifest_guarded() -> None:
    browser_manifest = json.loads(BROWSER_MANIFEST_PATH.read_text(encoding="utf-8"))
    dashboard_check = next(
        check for check in browser_manifest["checks"] if check["target_id"] == "dashboard-frontend"
    )
    home_route = next(route for route in dashboard_check["routes"] if route["name"] == "home")
    expected_text = home_route["expected_text"]

    assert "CREDENTIAL OPERATOR CHECKLIST" in expected_text
    assert "0 ready / 5 blocked" in expected_text
    assert "Checklist next" in expected_text
    assert "Required env: missing" in expected_text
    assert "Canva OAuth and OpenAPI tool execution" in expected_text


def test_url_helpers_use_target_origin_for_route_paths() -> None:
    smoke = load_browser_smoke_module()

    assert smoke.route_url("http://127.0.0.1:5175/", "/pricing") == "http://127.0.0.1:5175/pricing"
    assert (
        smoke.route_url("http://127.0.0.1:5176/src/dev/preview.html", "")
        == "http://127.0.0.1:5176/src/dev/preview.html"
    )
    assert smoke.path_from_url("http://127.0.0.1:5175/login?next=%2Fdashboard") == "/login"


def test_manifest_validation_rejects_bad_target_and_route() -> None:
    smoke = load_browser_smoke_module()
    browser_manifest = smoke.load_browser_manifest(BROWSER_MANIFEST_PATH)
    targets_manifest = smoke.load_targets_manifest(TARGETS_MANIFEST_PATH)
    browser_manifest["checks"][0]["target_id"] = "dashboard-api"
    browser_manifest["checks"][1]["routes"][0]["path"] = "relative"
    browser_manifest["checks"][2]["routes"][0]["expected_text"] = []

    errors = smoke.validate_manifest(browser_manifest, targets_manifest)

    assert "checks[0].target_id must reference a frontend target" in errors
    assert "checks[1].routes[0].path must be empty or start with /" in errors
    assert "checks[2].routes[0].expected_text must be a non-empty array" in errors


def test_validate_only_writes_machine_and_markdown_reports(tmp_path: Path) -> None:
    smoke = load_browser_smoke_module()
    json_out = tmp_path / "browser-smoke.json"
    markdown_out = tmp_path / "browser-smoke.md"

    result = smoke.main(
        [
            "--validate-only",
            "--target",
            "desci-frontend",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["status"] == "valid"
    assert payload["summary"]["targets"] == 1
    assert payload["summary"]["routes"] == 5
    assert "Dev-Server Browser Smoke" in markdown


def test_route_result_records_expected_text_matches() -> None:
    smoke = load_browser_smoke_module()

    class Response:
        status = 200

    class Locator:
        def inner_text(self, timeout: int) -> str:
            return "AI Projects Dashboard\nQueue #2\nGitHub source-refresh token boundary"

    class Page:
        url = "http://127.0.0.1:5173/"

        def on(self, event: str, callback) -> None:
            return None

        def remove_listener(self, event: str, callback) -> None:
            return None

        def goto(self, url: str, wait_until: str, timeout: int):
            self.url = url
            return Response()

        def locator(self, selector: str) -> Locator:
            return Locator()

    result = smoke.run_route(
        Page(),
        {"id": "dashboard-frontend", "url": "http://127.0.0.1:5173/"},
        {
            "name": "home",
            "path": "/",
            "expected_text": [
                "AI Projects Dashboard",
                "Queue #2",
                "GitHub source-refresh token boundary",
            ],
        },
        1000,
    )

    assert result.ok is True
    assert result.expected_text_count == 3
    assert result.matched_expected_text == [
        "AI Projects Dashboard",
        "Queue #2",
        "GitHub source-refresh token boundary",
    ]
    assert result.missing_expected_text == []


def test_route_result_records_missing_expected_text() -> None:
    smoke = load_browser_smoke_module()

    class Response:
        status = 200

    class Locator:
        def inner_text(self, timeout: int) -> str:
            return "AI Projects Dashboard"

    class Page:
        url = "http://127.0.0.1:5173/"

        def on(self, event: str, callback) -> None:
            return None

        def remove_listener(self, event: str, callback) -> None:
            return None

        def goto(self, url: str, wait_until: str, timeout: int):
            self.url = url
            return Response()

        def locator(self, selector: str) -> Locator:
            return Locator()

    result = smoke.run_route(
        Page(),
        {"id": "dashboard-frontend", "url": "http://127.0.0.1:5173/"},
        {"name": "home", "path": "/", "expected_text": ["AI Projects Dashboard", "Queue #2"]},
        1000,
    )

    assert result.ok is False
    assert result.expected_text_count == 2
    assert result.matched_expected_text == ["AI Projects Dashboard"]
    assert result.missing_expected_text == ["Queue #2"]
    assert any("missing expected text 'Queue #2'" in failure for failure in result.failures)


def test_markdown_lists_expected_text_evidence() -> None:
    smoke = load_browser_smoke_module()
    route_result = smoke.RouteResult(
        target_id="dashboard-frontend",
        name="home",
        path="/",
        ok=False,
        failures=["dashboard-frontend/home: missing expected text 'Queue #2'"],
        expected_text_count=2,
        matched_expected_text=["AI Projects Dashboard"],
        missing_expected_text=["Queue #2"],
        status_code=200,
        final_path="/",
    )
    report = smoke.build_report(
        [{"target_id": "dashboard-frontend", "routes": [{"name": "home"}]}],
        [route_result],
        status="fail",
    )

    markdown = smoke.format_markdown(report)

    assert "## Expected Text Evidence" in markdown
    assert "- `dashboard-frontend` `home` matched=`1/2`" in markdown
    assert "  - matched: `AI Projects Dashboard`" in markdown
    assert "  - missing: `Queue #2`" in markdown
