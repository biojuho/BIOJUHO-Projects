from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "apps" / "desci-platform" / "scripts" / "browser_smoke.py"


def load_browser_smoke_module():
    spec = importlib.util.spec_from_file_location("desci_browser_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_url_helpers_normalize_frontend_paths() -> None:
    smoke = load_browser_smoke_module()

    assert smoke._url("http://127.0.0.1:5173/", "/pricing") == "http://127.0.0.1:5173/pricing"
    assert smoke._url("http://127.0.0.1:5173/", "/") == "http://127.0.0.1:5173"
    assert smoke._path_from_url("http://127.0.0.1:5173/login?next=%2Fdashboard#top") == "/login"


def test_build_report_marks_failed_checks() -> None:
    smoke = load_browser_smoke_module()
    checks = [smoke.RouteCheck("home", "/", ("DSCI",))]
    results = [
        smoke.RouteCheckResult(
            name="home",
            path="/",
            ok=False,
            failures=("home: console error: boom",),
            status_code=200,
            final_path="/",
        )
    ]

    report = smoke.build_report(
        "http://127.0.0.1:5173",
        checks,
        results,
        20.0,
        playwright_available=True,
    )

    assert report["status"] == "fail"
    assert report["summary"] == {"total": 1, "passed": 0, "failed": 1, "blocked": 0, "planned": 1}
    assert report["checks"][0]["status_code"] == 200
    assert report["checks"][0]["final_path"] == "/"
    assert report["failures"] == ["home: console error: boom"]


def test_main_writes_blocked_report_when_playwright_is_missing(tmp_path: Path, monkeypatch) -> None:
    smoke = load_browser_smoke_module()
    json_out = tmp_path / "desci-browser-smoke.json"
    monkeypatch.setattr(smoke, "sync_playwright", None)

    result = smoke.main(["--json-out", str(json_out), "--skip-protected"])

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert result == 2
    assert payload["schema_version"] == 1
    assert payload["tool"] == "desci_browser_smoke"
    assert payload["status"] == "blocked"
    assert payload["playwright_available"] is False
    assert payload["summary"]["planned"] == len(smoke.PUBLIC_CHECKS)
    assert payload["summary"]["blocked"] == 1
    assert "Playwright is not installed" in payload["failures"][0]
