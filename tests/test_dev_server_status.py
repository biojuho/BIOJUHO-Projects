from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_status.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "dev_server_targets.json"


def load_status_module():
    spec = importlib.util.spec_from_file_location("dev_server_status", STATUS_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_manifest_validates_against_workspace_paths() -> None:
    status = load_status_module()
    payload = status.load_manifest(MANIFEST_PATH)

    errors = status.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert errors == []
    assert {target["id"] for target in payload["targets"]} == {
        "dashboard-api",
        "dashboard-frontend",
        "agriguard-api",
        "agriguard-frontend",
        "desci-api",
        "desci-frontend",
        "canva-widget-preview",
    }
    dependencies = {target["id"]: target.get("depends_on", []) for target in payload["targets"]}
    assert dependencies["dashboard-frontend"] == ["dashboard-api"]
    assert dependencies["agriguard-frontend"] == ["agriguard-api"]
    assert dependencies["desci-frontend"] == ["desci-api"]
    timeouts = {target["id"]: target.get("timeout_seconds") for target in payload["targets"]}
    assert timeouts["desci-api"] == 5.0


def test_manifest_rejects_unsafe_target_data() -> None:
    status = load_status_module()
    payload = status.load_manifest(MANIFEST_PATH)
    payload["targets"][0]["id"] = "bad id"
    payload["targets"][0]["cwd"] = "../outside"
    payload["targets"][0]["command"] = ["python", "api.py && whoami"]
    payload["targets"][0]["url"] = "https://example.com:443/api"
    payload["targets"][0]["expected_status"] = [True]
    payload["targets"][0]["timeout_seconds"] = 0
    payload["targets"][1]["id"] = payload["targets"][2]["id"]
    payload["targets"][3]["depends_on"] = ["missing-api"]

    errors = status.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "targets[0].id must use lowercase letters, numbers, hyphens, or underscores" in errors
    assert "targets[0].cwd must be a repo-relative path" in errors
    assert "targets[0].command[1] must not include shell command separators" in errors
    assert "targets[0].url must target localhost or 127.0.0.1" in errors
    assert "targets[0].expected_status[0] must be an HTTP status code" in errors
    assert "targets[0].timeout_seconds must be a positive number" in errors
    assert "targets[2].id must be unique" in errors
    assert "targets[3].depends_on references unknown target id: missing-api" in errors


def test_probe_target_reports_ready_and_unready() -> None:
    status = load_status_module()
    target = status.load_manifest(MANIFEST_PATH)["targets"][0]

    ready = status.probe_target(target, fetcher=lambda _url, _timeout: (200, 12, '{"workspace_smoke":{}}', None))
    wrong_service = status.probe_target(target, fetcher=lambda _url, _timeout: (200, 4, '{"other":"service"}', None))
    unready = status.probe_target(target, fetcher=lambda _url, _timeout: (None, 3, None, "connection refused"))

    assert ready["ok"] is True
    assert ready["status_code"] == 200
    assert ready["latency_ms"] == 12
    assert ready["timeout_seconds"] == 2.0
    assert wrong_service["ok"] is False
    assert wrong_service["error"] == "response body missing marker(s): workspace_smoke"
    assert unready["ok"] is False
    assert unready["error"] == "connection refused"


def test_probe_target_uses_target_timeout_override() -> None:
    status = load_status_module()
    target = dict(status.load_manifest(MANIFEST_PATH)["targets"][0])
    target["timeout_seconds"] = 7.5
    seen = {}

    def fetcher(_url: str, timeout: float):
        seen["timeout"] = timeout
        return 200, 1, '{"workspace_smoke":{}}', None

    ready = status.probe_target(target, timeout=2.0, fetcher=fetcher)

    assert seen["timeout"] == 7.5
    assert ready["timeout_seconds"] == 7.5
    assert ready["ok"] is True


def test_run_writes_machine_report_with_target_filter(tmp_path: Path) -> None:
    status = load_status_module()
    json_out = tmp_path / "dev-server-status.json"

    report = status.run(
        MANIFEST_PATH,
        json_out=json_out,
        target_ids=["dashboard-api", "agriguard-api"],
        fetcher=lambda url, _timeout: (
            200 if "8080" in url else None,
            5,
            '{"workspace_smoke":{}}' if "8080" in url else None,
            None if "8080" in url else "offline",
        ),
    )

    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["status"] == "degraded"
    assert report["summary"] == {"total": 2, "ready": 1, "unready": 1}
    assert [target["id"] for target in written["targets"]] == ["dashboard-api", "agriguard-api"]
    assert written["targets"][0]["ok"] is True
    assert written["targets"][1]["error"] == "offline"


def test_frontend_dependency_failure_marks_target_unready() -> None:
    status = load_status_module()

    def fetcher(url: str, _timeout: float):
        if "5173" in url:
            return 200, 5, "AI Projects Dashboard", None
        if "8080" in url:
            return None, 2, None, "offline"
        raise AssertionError(f"unexpected URL: {url}")

    report = status.run(MANIFEST_PATH, target_ids=["dashboard-frontend"], fetcher=fetcher)

    assert report["status"] == "degraded"
    assert report["summary"] == {"total": 1, "ready": 0, "unready": 1}
    target = report["targets"][0]
    assert target["status_code"] == 200
    assert target["ok"] is False
    assert target["error"] == "dependency target(s) unready: dashboard-api"
    assert target["dependencies"] == [
        {
            "id": "dashboard-api",
            "ok": False,
            "status_code": None,
            "error": "offline",
            "url": "http://127.0.0.1:8080/api/quality_overview",
        }
    ]


def test_validate_only_cli_does_not_probe_network(tmp_path: Path) -> None:
    status = load_status_module()
    json_out = tmp_path / "manifest.json"

    result = status.main(["--manifest", str(MANIFEST_PATH), "--validate-only", "--json-out", str(json_out)])

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert result == 0
    assert report["status"] == "validated"
    assert report["summary"]["total"] == 7


def test_wait_for_ready_retries_until_target_is_ready() -> None:
    status = load_status_module()
    calls = {"count": 0}

    def fetcher(_url: str, _timeout: float):
        calls["count"] += 1
        if calls["count"] == 1:
            return None, 2, None, "offline"
        return 200, 3, '{"workspace_smoke":{}}', None

    report = status.run(
        MANIFEST_PATH,
        target_ids=["dashboard-api"],
        wait_ready=True,
        wait_timeout=5,
        poll_interval=0.01,
        fetcher=fetcher,
        sleeper=lambda _seconds: None,
    )

    assert report["status"] == "ready"
    assert report["summary"] == {"total": 1, "ready": 1, "unready": 0}
    assert report["wait"] == {
        "enabled": True,
        "attempts": 2,
        "timeout_seconds": 5,
        "poll_interval_seconds": 0.01,
        "ready": True,
    }


def test_wait_for_ready_respects_zero_timeout() -> None:
    status = load_status_module()
    report = status.run(
        MANIFEST_PATH,
        target_ids=["dashboard-api"],
        wait_ready=True,
        wait_timeout=0,
        poll_interval=0.01,
        fetcher=lambda _url, _timeout: (None, 1, None, "offline"),
        sleeper=lambda _seconds: None,
    )

    assert report["status"] == "degraded"
    assert report["summary"] == {"total": 1, "ready": 0, "unready": 1}
    assert report["wait"]["attempts"] == 1
    assert report["wait"]["ready"] is False


def test_wait_for_ready_normalizes_negative_timing_values() -> None:
    status = load_status_module()
    report = status.run(
        MANIFEST_PATH,
        target_ids=["dashboard-api"],
        wait_ready=True,
        wait_timeout=-1,
        poll_interval=-1,
        fetcher=lambda _url, _timeout: (None, 1, None, "offline"),
        sleeper=lambda _seconds: None,
    )

    assert report["wait"]["timeout_seconds"] == 0.0
    assert report["wait"]["poll_interval_seconds"] == 0.0
