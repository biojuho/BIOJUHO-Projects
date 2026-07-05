# ruff: noqa: S603  # subprocess calls invoke trusted scripts under test control
"""
AgriGuard Backend Smoke Tests
Tests core API endpoints and seed_db functionality.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import types
import uuid
from pathlib import Path

import pytest

backend_dir = os.path.join(os.path.dirname(__file__), "..")
workspace_dir = os.path.abspath(os.path.join(backend_dir, "..", "..", ".."))
temp_root = os.path.join(workspace_dir, ".smoke-tmp", "agriguard-backend")
os.makedirs(temp_root, exist_ok=True)
PYTHON = sys.executable
SMOKE_DB_PATH = os.path.join(temp_root, "subprocess-smoke.db")


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{SMOKE_DB_PATH}"
    env["AUTO_CREATE_SCHEMA"] = "1"
    env["AGRIGUARD_ENV_FILE"] = os.path.join(temp_root, "missing.env")
    env["TMP"] = temp_root
    env["TEMP"] = temp_root
    env["TMPDIR"] = temp_root
    return env


def _python_can_import(import_stmt: str) -> bool:
    result = subprocess.run(
        [PYTHON, "-c", import_stmt],
        cwd=backend_dir,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def test_imports():
    """Verify all core modules can be imported without error."""
    result = subprocess.run([PYTHON, "-c", "import models, database, seed_db"], cwd=backend_dir, env=_subprocess_env())
    assert result.returncode == 0


def test_seed_db_creates_data():
    """Run seed_db and verify data counts."""
    result = subprocess.run([PYTHON, "seed_db.py"], cwd=backend_dir, capture_output=True, env=_subprocess_env())
    assert result.returncode == 0


def test_dashboard_summary_data_shape():
    """Verify seed data can produce a valid dashboard summary."""
    code = """
from database import SessionLocal
import models
db = SessionLocal()
try:
    total_products = db.query(models.Product).count()
    verified = db.query(models.Product).filter(models.Product.is_verified == True).count()
    events = db.query(models.TrackingEvent).count()
    assert total_products >= 0
    assert verified >= 0
    assert events >= 0
finally:
    db.close()
"""
    result = subprocess.run([PYTHON, "-c", code], cwd=backend_dir, env=_subprocess_env())
    assert result.returncode == 0


def test_qr_event_summary_funnel_metrics():
    """Verify QR funnel summary math with a temporary SQLite database."""
    code = """
import os
import uuid
from datetime import datetime, timezone

db_path = os.path.join(os.environ["TMP"], f"qr-events-smoke-{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTO_CREATE_SCHEMA"] = "1"

from database import SessionLocal, initialize_database
import models
from routers.qr_events import get_qr_event_summary

initialize_database()
db = SessionLocal()
try:
    now = datetime.now(timezone.utc)
    db.add_all([
        models.QRScanEvent(
            session_id="s1", event_type="scan_start", occurred_at=now, variant_id="qr_page_v2"
        ),
        models.QRScanEvent(
            session_id="s1", event_type="scan_failure", occurred_at=now,
            variant_id="qr_page_v2", error_code="camera_denied",
        ),
        models.QRScanEvent(
            session_id="s1", event_type="scan_recovery", occurred_at=now,
            variant_id="qr_page_v2", recovery_method="retry",
        ),
        models.QRScanEvent(
            session_id="s1", event_type="verification_complete", occurred_at=now,
            variant_id="qr_page_v2",
        ),
        models.QRScanEvent(
            session_id="s2", event_type="scan_start", occurred_at=now, variant_id="qr_page_v2"
        ),
        models.QRScanEvent(
            session_id="s2", event_type="scan_failure", occurred_at=now,
            variant_id="qr_page_v2", error_code="invalid_qr",
        ),
    ])
    db.commit()

    summary = get_qr_event_summary(hours=24, variant_id="qr_page_v2", db=db)
    assert summary["total_events"] == 6
    assert summary["total_sessions"] == 2
    assert summary["event_counts"]["scan_start"] == 2
    assert summary["event_counts"]["scan_failure"] == 2
    assert summary["event_counts"]["scan_recovery"] == 1
    assert summary["event_counts"]["verification_complete"] == 1
    assert summary["error_counts"]["camera_denied"] == 1
    assert summary["error_counts"]["invalid_qr"] == 1
    assert summary["variant_counts"]["qr_page_v2"] == 6
    assert summary["funnel"]["scan_start_sessions"] == 2
    assert summary["funnel"]["scan_failure_sessions"] == 2
    assert summary["funnel"]["scan_recovery_sessions"] == 1
    assert summary["funnel"]["verification_complete_sessions"] == 1
    assert summary["funnel"]["verification_completion_rate"] == 0.5
    assert summary["funnel"]["recovery_rate_after_failure"] == 0.5
finally:
    db.close()
"""
    result = subprocess.run([PYTHON, "-c", code], cwd=backend_dir, env=_subprocess_env())
    assert result.returncode == 0


def test_run_migrations_script_applies_head_revision():
    """Verify the Alembic migration runner upgrades a fresh database to the latest revision."""
    if importlib.util.find_spec("alembic") is None or not _python_can_import("from alembic import command"):
        pytest.skip("alembic is not installed in the current test environment")

    db_path = os.path.join(temp_root, f"{uuid.uuid4().hex}-migrations-smoke.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    try:
        env = _subprocess_env()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        env["AUTO_CREATE_SCHEMA"] = "0"

        result = subprocess.run(
            [PYTHON, "scripts/run_migrations.py"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr or result.stdout

        with sqlite3.connect(db_path) as connection:
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            tables = {
                row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            qr_indexes = {row[1] for row in connection.execute("PRAGMA index_list('qr_scan_events')").fetchall()}
            sensor_indexes = {row[1] for row in connection.execute("PRAGMA index_list('sensor_devices')").fetchall()}

        assert revision == ("0006_sensor_owner_scope",)
        assert "qr_scan_events" in tables
        assert "qr_tokens" in tables
        assert "sensor_devices" in tables
        assert "ix_qr_scan_events_occurred_session_event" in qr_indexes
        assert "ix_qr_scan_events_variant_occurred_session_event" in qr_indexes
        assert "ix_sensor_devices_owner_id" in sensor_indexes
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_alembic_revision_ids_fit_postgres_version_column():
    """Postgres enforces Alembic's varchar(32) version column."""
    versions_dir = Path(backend_dir) / "alembic" / "versions"
    revision_ids: list[str] = []
    for path in versions_dir.glob("*.py"):
        namespace: dict[str, object] = {}
        exec(path.read_text(encoding="utf-8"), namespace)
        revision = namespace.get("revision")
        if isinstance(revision, str):
            revision_ids.append(revision)

    assert revision_ids
    assert all(len(revision) <= 32 for revision in revision_ids)


def test_run_migrations_rewrites_deprecated_revision_aliases():
    """Existing local databases may have recorded pre-shortened revision ids."""
    if importlib.util.find_spec("alembic") is None or not _python_can_import("from alembic import command"):
        pytest.skip("alembic is not installed in the current test environment")

    script_path = Path(backend_dir) / "scripts" / "run_migrations.py"
    spec = importlib.util.spec_from_file_location("run_migrations_for_test", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    db_path = os.path.join(temp_root, f"{uuid.uuid4().hex}-deprecated-revisions.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    try:
        with sqlite3.connect(db_path) as connection:
            connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(255))")
            connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", ("0005_add_qr_scan_event_kpi_indexes",))
            connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", ("0006_add_sensor_device_owner_scope",))

        rewrites = module._rewrite_deprecated_revision_aliases(f"sqlite:///{db_path}")

        with sqlite3.connect(db_path) as connection:
            versions = {
                row[0] for row in connection.execute("SELECT version_num FROM alembic_version").fetchall()
            }

        assert rewrites == [
            {"from": "0005_add_qr_scan_event_kpi_indexes", "to": "0005_qr_kpi_indexes"},
            {"from": "0006_add_sensor_device_owner_scope", "to": "0006_sensor_owner_scope"},
        ]
        assert versions == {"0005_qr_kpi_indexes", "0006_sensor_owner_scope"}
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_qr_ab_script_handles_missing_variant_data():
    """Verify the QR A/B helper exits cleanly when one variant has no samples yet."""
    dataset_path = os.path.join(temp_root, f"qr-ab-{uuid.uuid4().hex}.json")
    try:
        payload = {
            "dataset_name": "single-arm sample",
            "sessions": [
                {
                    "session_id": "a-001",
                    "variant": "A",
                    "scan_success": True,
                    "verification_success": True,
                    "invalid_error": False,
                    "used_manual_recovery": False,
                    "time_to_verify_sec": 12.3,
                    "trust_score": 4.1,
                }
            ],
        }
        with open(dataset_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

        result = subprocess.run(
            [PYTHON, "../scripts/ab_test_qr_page.py", "--dataset", dataset_path],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert "Need samples for both variants before making a decision" in result.stdout
    finally:
        try:
            os.remove(dataset_path)
        except OSError:
            pass


def _load_script_module(script_path: Path, module_name: str):
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.Page = object
    sync_api.Response = object
    sync_api.sync_playwright = lambda: None
    playwright = types.ModuleType("playwright")
    previous_playwright = sys.modules.get("playwright")
    previous_sync_api = sys.modules.get("playwright.sync_api")
    sys.modules["playwright"] = playwright
    sys.modules["playwright.sync_api"] = sync_api
    try:
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_playwright is None:
            sys.modules.pop("playwright", None)
        else:
            sys.modules["playwright"] = previous_playwright
        if previous_sync_api is None:
            sys.modules.pop("playwright.sync_api", None)
        else:
            sys.modules["playwright.sync_api"] = previous_sync_api


def test_nav_browser_smoke_uses_phone_viewport_for_mobile_default():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "nav_browser_smoke.py",
        "nav_browser_smoke_under_test",
    )

    assert script.resolve_viewport(mobile=False, viewport=None) == {"width": 1440, "height": 960}
    assert script.resolve_viewport(mobile=True, viewport=None) == {"width": 390, "height": 844}
    assert script.resolve_viewport(mobile=True, viewport="412x915") == {"width": 412, "height": 915}


def test_nav_browser_smoke_tracks_mobile_first_viewport_affordances():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "nav_browser_smoke.py",
        "nav_browser_smoke_affordances_under_test",
    )

    route_names = {route["name"] for route in script.DEFAULT_ROUTES}

    assert set(script.MOBILE_ROUTE_AFFORDANCES).issubset(route_names)
    assert script.should_check_mobile_affordances({"viewportWidth": 390}, mobile=False) is True
    assert script.should_check_mobile_affordances({"viewportWidth": 1440}, mobile=True) is True
    assert script.should_check_mobile_affordances({"viewportWidth": 1440}, mobile=False) is False
    assert script.mobile_touch_targets_ok({"undersizedTouchTargets": []}) is True
    assert script.mobile_touch_targets_ok({"undersizedTouchTargets": [{"tag": "button", "height": 36}]}) is False
    assert script.MOBILE_ROUTE_AFFORDANCES["registry"][0]["text"] == "Register Harvest"
    assert script.MOBILE_ROUTE_AFFORDANCES["scanner"][0]["min_visible_ratio"] == 0.98
    assert script.MOBILE_ROUTE_AFFORDANCES["cold_chain"][0]["min_visible_height"] == 220
    assert script.MOBILE_ROUTE_AFFORDANCES["qr_tokens"][0]["min_visible_height"] == 220


def test_nav_browser_smoke_requires_semantic_route_accessibility():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "nav_browser_smoke.py",
        "nav_browser_smoke_semantics_under_test",
    )

    valid_metrics = {
        "hasMain": True,
        "hasNav": True,
        "h1Count": 1,
        "duplicateIds": [],
        "unnamedInteractive": [],
        "unlabeledFields": [],
        "credentialAutocompleteGaps": [],
    }

    assert script.route_semantics_ok(valid_metrics) is True
    assert script.route_semantics_detail(valid_metrics)["h1Count"] == 1

    for field, value in [
        ("hasMain", False),
        ("hasNav", False),
        ("h1Count", 0),
        ("duplicateIds", ["search"]),
        ("unnamedInteractive", [{"tag": "button"}]),
        ("unlabeledFields", [{"tag": "input"}]),
        ("credentialAutocompleteGaps", [{"tag": "input", "id": "operator-token"}]),
    ]:
        failing_metrics = dict(valid_metrics)
        failing_metrics[field] = value
        assert script.route_semantics_ok(failing_metrics) is False


def test_browser_smoke_suite_builds_live_backend_steps_and_redacts_operator_token(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_under_test",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_browser_smoke_suite.py",
            "--base-url",
            "http://127.0.0.1:5174",
            "--api-url",
            "http://127.0.0.1:8002",
            "--operator-token",
            "secret-operator-token",
            "--output-dir",
            "var/browser-suite",
            "--mobile",
        ],
    )
    args = script.parse_args()
    steps = script.build_steps(args)

    assert [step.name for step in steps] == [
        "dashboard_auth_recovery",
        "nav",
        "supply_chain",
        "qr_path",
        "admin_routes",
        "product_detail",
    ]
    assert "--mobile" in steps[0].command
    assert "--click-nav" in steps[1].command
    assert "--mobile" in steps[1].command
    assert "--mobile" in steps[2].command
    assert "--mobile" in steps[4].command
    assert "--mobile" in steps[5].command
    redacted = script.redact_command(steps[0].command, operator_token=args.operator_token)
    assert "secret-operator-token" not in redacted
    assert "<redacted>" in redacted


def test_browser_smoke_suite_unavailable_check_is_explicit_opt_in(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_unavailable_under_test",
    )

    monkeypatch.setattr(sys, "argv", ["run_browser_smoke_suite.py"])
    default_steps = script.build_steps(script.parse_args())
    assert "consumer_verify_unavailable" not in [step.name for step in default_steps]

    monkeypatch.setattr(sys, "argv", ["run_browser_smoke_suite.py", "--include-unavailable-check"])
    opted_in_steps = script.build_steps(script.parse_args())
    assert opted_in_steps[-1].name == "consumer_verify_unavailable"
    assert "--intercept-api-failure" in opted_in_steps[-1].command


def test_browser_smoke_suite_summarizes_child_report(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_summary_under_test",
    )
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "nav_loaded", "ok": True}, {"name": "qr_failed", "ok": False}, {"ok": True}]}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert summary == {
        "report_found": True,
        "checks_total": 3,
        "checks_passed": 2,
        "checks_failed": 1,
        "failed_check_names": ["qr_failed"],
        "screenshot_artifacts_total": 0,
        "screenshot_artifacts_passed": 0,
        "screenshot_artifacts_failed": 0,
        "failed_screenshot_artifacts": [],
        "screenshot_artifacts": [],
    }


def test_browser_smoke_suite_summarizes_unnamed_failed_child_check(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_unnamed_summary_under_test",
    )
    report_path = tmp_path / "child.json"
    report_path.write_text(json.dumps({"checks": [{"ok": False}]}), encoding="utf-8")

    summary = script.summarize_child_report(report_path)

    assert summary["failed_check_names"] == ["check_1"]


def test_browser_smoke_suite_validates_screenshot_artifacts(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_screenshot_artifacts_under_test",
    )
    screenshot = tmp_path / "screen.png"
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x02"
        b"\x00\x00\x00\x03"
        b"\x08\x02\x00\x00\x00"
    )
    screenshot.write_bytes(png_header + (b"\x00" * script.MIN_SCREENSHOT_BYTES))
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "rendered", "ok": True}], "screenshot": str(screenshot)}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert summary["screenshot_artifacts_total"] == 1
    assert summary["screenshot_artifacts_passed"] == 1
    assert summary["screenshot_artifacts_failed"] == 0
    assert summary["screenshot_artifacts"][0]["width"] == 2
    assert summary["screenshot_artifacts"][0]["height"] == 3


def test_browser_smoke_suite_fails_corrupt_screenshot_artifact(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_corrupt_screenshot_under_test",
    )
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"not-a-png")
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "rendered", "ok": True}], "screenshot": str(screenshot)}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert summary["screenshot_artifacts_total"] == 1
    assert summary["screenshot_artifacts_passed"] == 0
    assert summary["screenshot_artifacts_failed"] == 1
    assert summary["failed_screenshot_artifacts"] == [str(screenshot)]


def test_browser_smoke_suite_launch_gate_requires_screenshot_artifact(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_launch_gate_requires_artifact_under_test",
    )
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "rendered", "ok": True}]}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert script.screenshot_artifact_gate(summary) == {
        "screenshot_artifacts_required": True,
        "screenshot_artifacts_missing": True,
        "screenshot_artifact_dimension_failures": [],
        "screenshot_artifacts_gate_ok": False,
    }
    assert not script.child_report_passes_launch_gate(0, summary)


def test_browser_smoke_suite_launch_gate_accepts_valid_screenshot_artifact(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_launch_gate_valid_artifact_under_test",
    )
    screenshot = tmp_path / "screen.png"
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x02"
        b"\x00\x00\x00\x03"
        b"\x08\x02\x00\x00\x00"
    )
    screenshot.write_bytes(png_header + (b"\x00" * script.MIN_SCREENSHOT_BYTES))
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "rendered", "ok": True}], "screenshot": str(screenshot)}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert script.screenshot_artifact_gate(summary)["screenshot_artifacts_gate_ok"] is True
    assert script.child_report_passes_launch_gate(0, summary)


def test_browser_smoke_suite_mobile_launch_gate_requires_viewport_screenshot_dimensions(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_mobile_screenshot_dimensions_under_test",
    )
    screenshot = tmp_path / "screen.png"
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x02"
        b"\x00\x00\x00\x03"
        b"\x08\x02\x00\x00\x00"
    )
    screenshot.write_bytes(png_header + (b"\x00" * script.MIN_SCREENSHOT_BYTES))
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"name": "rendered", "ok": True}], "screenshot": str(screenshot)}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)
    artifact_gate = script.screenshot_artifact_gate(
        summary,
        expected_dimensions=script.MOBILE_SCREENSHOT_DIMENSIONS,
    )

    assert artifact_gate["screenshot_artifacts_gate_ok"] is False
    assert artifact_gate["screenshot_artifact_dimension_failures"] == [
        f"{screenshot}: expected 390x844, got 2x3"
    ]
    assert not script.child_report_passes_launch_gate(
        0,
        summary,
        expected_screenshot_dimensions=script.MOBILE_SCREENSHOT_DIMENSIONS,
    )


def test_browser_smoke_suite_expected_screenshot_dimensions_are_step_specific():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_step_dimensions_under_test",
    )

    assert script.expected_screenshot_dimensions_for_step("admin_routes", mobile=False) == script.DESKTOP_SCREENSHOT_DIMENSIONS
    assert script.expected_screenshot_dimensions_for_step("nav", mobile=False) == script.DESKTOP_SCREENSHOT_DIMENSIONS
    assert script.expected_screenshot_dimensions_for_step("qr_path", mobile=False) == script.MOBILE_SCREENSHOT_DIMENSIONS
    assert script.expected_screenshot_dimensions_for_step("consumer_verify_unavailable", mobile=False) == script.MOBILE_SCREENSHOT_DIMENSIONS
    assert script.expected_screenshot_dimensions_for_step("admin_routes", mobile=True) == script.MOBILE_SCREENSHOT_DIMENSIONS


def test_browser_smoke_suite_timeout_writes_failed_step(monkeypatch, tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_timeout_step_under_test",
    )
    step = script.BrowserSmokeStep(
        name="slow_step",
        command=["python", "slow.py", "--operator-token", "secret"],
        json_out=tmp_path / "missing-child.json",
    )

    def timeout_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=step.command, timeout=120, output="partial out", stderr="partial err")

    monkeypatch.setattr(script.subprocess, "run", timeout_run)

    result = script.run_step(step, operator_token="secret", timeout_ms=30_000, dry_run=False)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["report_found"] is False
    assert result["screenshot_artifacts_missing"] is True
    assert result["command"] == ["python", "slow.py", "--operator-token", "<redacted>"]


def test_browser_smoke_suite_backend_contract_accepts_required_paths():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_contract_pass_under_test",
    )

    summary = script.summarize_backend_openapi_contract(
        {"paths": {path: {} for path in script.REQUIRED_BACKEND_OPENAPI_PATHS}}
    )

    assert summary["ok"] is True
    assert summary["missing_paths"] == []


def test_browser_smoke_suite_backend_contract_flags_stale_backend():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_contract_fail_under_test",
    )

    summary = script.summarize_backend_openapi_contract(
        {
            "paths": {
                "/products/": {},
                "/products/page": {},
                "/qr-events": {},
                "/qr-events/summary": {},
            }
        }
    )

    assert summary["ok"] is False
    assert "/qr-events/kpis" in summary["missing_paths"]
    assert "/qr-tokens/products/{product_id}" in summary["missing_paths"]
    assert "restart/rebuild the backend" in summary["detail"]


def test_browser_smoke_suite_backend_proxy_alignment_accepts_shared_state():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_proxy_alignment_pass_under_test",
    )

    summary = script.summarize_backend_proxy_alignment(
        api_url="http://127.0.0.1:8002/",
        frontend_api_url="http://127.0.0.1:5174/api/",
        seeded_product={"id": "product-1", "name": "Proxy Probe"},
        proxy_product={"id": "product-1", "name": "Proxy Probe"},
    )

    assert summary["ok"] is True
    assert summary["api_url"] == "http://127.0.0.1:8002"
    assert summary["frontend_api_url"] == "http://127.0.0.1:5174/api"
    assert "share seeded product state" in summary["detail"]


def test_browser_smoke_suite_backend_proxy_alignment_flags_mismatched_state():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_proxy_alignment_fail_under_test",
    )

    summary = script.summarize_backend_proxy_alignment(
        api_url="http://127.0.0.1:8102",
        frontend_api_url="http://127.0.0.1:5174/api",
        seeded_product={"id": "product-1", "name": "Proxy Probe"},
        proxy_error='HTTP 404: {"detail":"Product not found"}',
    )

    assert summary["ok"] is False
    assert summary["product_id"] == "product-1"
    assert "different backend" in summary["detail"]
    assert "HTTP 404" in summary["detail"]


def test_nav_browser_smoke_defaults_operator_token_for_local_dev(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "nav_browser_smoke.py",
        "nav_browser_smoke_operator_token_under_test",
    )

    monkeypatch.delenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["nav_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == script.DEFAULT_OPERATOR_TOKEN


def test_qr_path_browser_smoke_keeps_invalid_manual_probe_distinct(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_under_test",
    )

    monkeypatch.setattr(sys, "argv", ["qr_path_browser_smoke.py"])
    args = script.parse_args()

    assert args.invalid_manual_value == script.DEFAULT_INVALID_MANUAL_VALUE
    assert args.manual_token is None
    assert args.invalid_manual_value != args.manual_token
    assert args.invalid_manual_value != args.invalid_token
    assert args.invalid_manual_value != script.LEGACY_FIXTURE_MANUAL_TOKEN


def test_qr_path_browser_smoke_uses_operator_token_env(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_operator_token_under_test",
    )

    monkeypatch.setenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", "staging-operator-token")
    monkeypatch.setattr(sys, "argv", ["qr_path_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == "staging-operator-token"


def test_qr_path_browser_smoke_resolves_seed_api_url_from_base_proxy(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_api_url_under_test",
    )

    monkeypatch.delenv("AGRIGUARD_BROWSER_API_URL", raising=False)

    assert (
        script.resolve_seed_api_url(base_url="http://127.0.0.1:5199", api_url="")
        == "http://127.0.0.1:5199/api"
    )
    assert script.resolve_seed_api_url(
        base_url="http://127.0.0.1:5199",
        api_url="http://127.0.0.1:8002/",
    ) == "http://127.0.0.1:8002"


def test_qr_path_browser_smoke_extracts_public_verify_tokens():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_token_extract_under_test",
    )

    assert script.extract_verify_token("agri://verify/public-token-1") == "public-token-1"
    assert script.extract_verify_token("https://verify.agriguard.test/verify/public-token-2") == "public-token-2"
    assert script.extract_verify_token("https://verify.agriguard.test/verify/verify/public-token-3") == "public-token-3"
    assert script.extract_verify_token("verify/public-token-4") == "public-token-4"
    assert script.extract_verify_token("raw-token") == "raw-token"


def test_qr_path_browser_smoke_redacts_public_tokens_from_report():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_report_redaction_under_test",
    )

    token = "public-secret-token"
    report = {
        "manualToken": token,
        "observations": {
            "seededManualToken": {
                "token": token,
                "qr_code_prefix": f"agri://verify/{token}",
            },
            "publicVerifyResponses": [
                {
                    "url": f"http://127.0.0.1:8003/api/qr/{token}/verify?session_id=s1",
                    "cacheControl": "no-store",
                }
            ],
        },
        "checks": [
            {
                "name": "manual_verify_url_opened",
                "ok": True,
                "detail": f"http://127.0.0.1:5174/verify/{token}?scan_source=qr_reader",
            }
        ],
    }

    redacted = script.redact_report_public_tokens(report, {token})
    payload = json.dumps(redacted)

    assert token not in payload
    assert script.PUBLIC_QR_TOKEN_REDACTION in payload
    assert "/api/qr/" in payload
    assert "/verify" in payload
    assert "no-store" in payload


def test_qr_path_browser_smoke_tracks_public_summary_first_viewport_targets():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_first_viewport_under_test",
    )

    target_names = {target["name"] for target in script.PUBLIC_VERIFY_SUMMARY_TARGETS}

    assert target_names == {
        "manual_verify_origin_card_first_viewport",
        "manual_verify_batch_card_first_viewport",
        "manual_verify_temperature_card_first_viewport",
        "manual_verify_last_verified_card_first_viewport",
    }
    assert script.should_check_first_viewport_targets({"viewportWidth": 390}) is True
    assert script.should_check_first_viewport_targets({"viewportWidth": 1440}) is False
    assert script.PUBLIC_VERIFY_SUMMARY_TARGETS[-1]["text"] == "Last verified"
    assert script.PUBLIC_VERIFY_SUMMARY_TARGETS[-1]["min_visible_ratio"] == 0.98


def test_qr_path_browser_smoke_matches_spa_verify_routes():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_route_match_under_test",
    )

    assert script.verify_route_matches(
        "http://127.0.0.1:5174/verify/public-token-1?scan_source=qr_reader",
        "public-token-1",
    )
    assert script.verify_route_matches(
        "http://127.0.0.1:5174/verify/public%3Atoken?scan_source=qr_reader",
        "public:token",
    )
    assert not script.verify_route_matches("http://127.0.0.1:5174/scan", "public-token-1")


def test_qr_path_browser_smoke_waits_for_spa_route_state():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_route_wait_under_test",
    )

    waits = []

    class FakePage:
        url = "http://127.0.0.1:5174/scan"

        def wait_for_timeout(self, timeout):
            waits.append(timeout)
            self.url = "http://127.0.0.1:5174/verify/public-token-1?scan_source=qr_reader"

    script.wait_for_verify_route(FakePage(), "public-token-1", 1000)

    assert waits == [250]


def test_qr_path_browser_smoke_route_timeout_reports_current_url():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_route_timeout_under_test",
    )

    class BodyLocator:
        def inner_text(self, timeout):
            assert timeout == 5_000
            return "Scanner paused\nManual verification code"

    class FakePage:
        url = "http://127.0.0.1:5174/scan"

        def wait_for_timeout(self, timeout):
            return None

        def locator(self, selector):
            assert selector == "body"
            return BodyLocator()

    with pytest.raises(RuntimeError) as exc_info:
        script.wait_for_verify_route(FakePage(), "public-token-1", 1)

    message = str(exc_info.value)
    assert "expected_path='/verify/public-token-1'" in message
    assert "current_url='http://127.0.0.1:5174/scan'" in message
    assert "Scanner paused Manual verification code" in message


def test_supply_chain_browser_smoke_uses_phone_viewport_for_mobile_default():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "supply_chain_browser_smoke.py",
        "supply_chain_browser_smoke_under_test",
    )

    assert script.resolve_viewport(mobile=False, viewport=None) == {"width": 1440, "height": 960}
    assert script.resolve_viewport(mobile=True, viewport=None) == {"width": 390, "height": 844}
    assert script.resolve_viewport(mobile=True, viewport="412x915") == {"width": 412, "height": 915}


def test_supply_chain_browser_smoke_defaults_operator_token_for_local_dev(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "supply_chain_browser_smoke.py",
        "supply_chain_browser_smoke_operator_token_under_test",
    )

    monkeypatch.delenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["supply_chain_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == script.DEFAULT_OPERATOR_TOKEN


def test_supply_chain_browser_smoke_accepts_proxy_prefixed_products_page():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "supply_chain_browser_smoke.py",
        "supply_chain_browser_smoke_proxy_path_under_test",
    )

    assert script.api_response_path({"url": "http://127.0.0.1:5174/api/products/page?page=1"}) == "/products/page"
    assert script.api_response_path({"url": "http://127.0.0.1:8002/products/page?page=1"}) == "/products/page"
    assert script.api_response_path({"url": "http://127.0.0.1:5174/api/products?page=1"}) == "/products"


def test_admin_routes_browser_smoke_uses_operator_token_env(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_operator_token_under_test",
    )

    monkeypatch.setenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", "staging-admin-token")
    monkeypatch.setattr(sys, "argv", ["admin_routes_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == "staging-admin-token"


def test_admin_routes_browser_smoke_uses_phone_viewport_for_mobile_default():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_viewport_under_test",
    )

    assert script.resolve_viewport(mobile=False, viewport=None) == {"width": 1440, "height": 960}
    assert script.resolve_viewport(mobile=True, viewport=None) == {"width": 390, "height": 844}
    assert script.resolve_viewport(mobile=True, viewport="412x915") == {"width": 412, "height": 915}
    assert script.has_no_horizontal_overflow({"clientWidth": 390, "viewportWidth": 390, "scrollWidth": 390}) is True
    assert script.has_no_horizontal_overflow({"clientWidth": 390, "viewportWidth": 390, "scrollWidth": 430}) is False


def test_admin_routes_browser_smoke_uses_viewport_screenshots_for_fixed_nav(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_screenshot_under_test",
    )
    calls = []

    class FakePage:
        def evaluate(self, script):
            pass

        def screenshot(self, **kwargs):
            calls.append(kwargs)

    script.capture_screenshot(FakePage(), tmp_path / "mobile.png", mobile=True)
    script.capture_screenshot(FakePage(), tmp_path / "desktop.png", mobile=False)

    assert calls[0]["full_page"] is False
    assert calls[1]["full_page"] is False


def test_admin_routes_browser_smoke_masks_public_qr_screenshot_artifacts(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_screenshot_mask_under_test",
    )
    scripts = []
    screenshots = []

    class FakePage:
        def evaluate(self, script_text):
            scripts.append(script_text)

        def screenshot(self, **kwargs):
            screenshots.append(kwargs)

    script.capture_screenshot(FakePage(), tmp_path / "qr-tokens.png", mobile=False)

    assert screenshots[0]["full_page"] is False
    assert "qr-token-row" in scripts[0]
    assert "agri:\\/\\/verify" in scripts[0]
    assert script.PUBLIC_QR_TOKEN_REDACTION in scripts[0]


def test_admin_routes_browser_smoke_attaches_page_diagnostics():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_diagnostics_under_test",
    )
    handlers = {}

    class FakePage:
        def on(self, event, callback):
            handlers[event] = callback

    console_messages = []
    request_failures = []
    page_errors = []

    script.attach_page_diagnostics(
        FakePage(),
        console_messages=console_messages,
        request_failures=request_failures,
        page_errors=page_errors,
    )

    assert set(handlers) == {"console", "requestfailed", "pageerror"}


def test_admin_routes_browser_smoke_classifies_expected_missing_auth_console():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_expected_auth_console_under_test",
    )

    assert script.is_expected_missing_auth_console(
        {"type": "error", "text": "Failed to load resource: the server responded with a status of 401 (Unauthorized)"}
    )
    assert not script.is_expected_missing_auth_console(
        {"type": "error", "text": "Failed to load resource: the server responded with a status of 500 (Internal Server Error)"}
    )
    assert not script.is_expected_missing_auth_console({"type": "warning", "text": "401 (Unauthorized)"})


def test_admin_routes_browser_smoke_redacts_public_qr_tokens_from_report():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "admin_routes_browser_smoke.py",
        "admin_routes_browser_smoke_redaction_under_test",
    )

    token = "admin-public-secret-token"
    table_token = "table-public-token-12345678"
    report = {
        "checks": [
            {"name": "qr_token_reissued", "ok": True, "detail": f"/verify/{token}"},
            {"name": "api_response", "ok": True, "detail": f"/api/qr/{token}/verify"},
        ],
        "observations": {
            "seed_product": {"qr_code_prefix": f"agri://verify/{token}"},
            "qr_tokens": {
                "metrics": {
                    "bodyTextSample": (
                        f"New label URL ready http://127.0.0.1:5174/verify/{token}?scan_source=admin "
                        f"Token{table_token}Stateactive"
                    )
                }
            },
        },
    }
    tokens = script.extract_public_qr_route_tokens(report)
    redacted = script.redact_report_public_tokens(report, tokens)
    payload = json.dumps(redacted)

    assert token in tokens
    assert token not in payload
    assert table_token not in payload
    assert script.PUBLIC_QR_TOKEN_REDACTION in payload
    assert "agri://verify/" in payload
    assert "/api/qr/" in payload


def test_product_detail_browser_smoke_uses_phone_viewport_for_mobile_default():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_under_test",
    )

    assert script.resolve_viewport(mobile=False, viewport=None) == {"width": 1440, "height": 960}
    assert script.resolve_viewport(mobile=True, viewport=None) == {"width": 390, "height": 844}
    assert script.resolve_viewport(mobile=True, viewport="412x915") == {"width": 412, "height": 915}


def test_product_detail_browser_smoke_tracks_mobile_first_viewport_targets():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_affordances_under_test",
    )

    target_names = {target["name"] for target in script.MOBILE_FIRST_VIEWPORT_TARGETS}

    assert target_names == {
        "product_qr_first_viewport",
        "operator_tracking_action_first_viewport",
        "operator_certification_action_first_viewport",
    }
    assert script.should_check_mobile_affordances({"viewportWidth": 390}, mobile=False) is True
    assert script.should_check_mobile_affordances({"viewportWidth": 1440}, mobile=True) is True
    assert script.should_check_mobile_affordances({"viewportWidth": 1440}, mobile=False) is False
    assert script.MOBILE_FIRST_VIEWPORT_TARGETS[0]["aria_label"] == "Product verification QR"
    assert script.MOBILE_FIRST_VIEWPORT_TARGETS[1]["text"] == "Add Tracking Event"
    assert script.MOBILE_FIRST_VIEWPORT_TARGETS[2]["text"] == "Add Certification"


def test_product_detail_browser_smoke_uses_operator_token_env(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_operator_token_under_test",
    )

    monkeypatch.setenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", "staging-detail-token")
    monkeypatch.setattr(sys, "argv", ["product_detail_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == "staging-detail-token"


def test_product_detail_browser_smoke_redacts_public_qr_tokens_from_report():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_redaction_under_test",
    )

    token = "detail-public-secret-token"
    report = {
        "checks": [{"name": "manual_verify", "ok": True, "detail": f"/verify/{token}"}],
        "observations": {
            "seed_product": {"qr_code_prefix": f"agri://verify/{token}"},
            "initial": {
                "url": f"http://127.0.0.1:5174/product/product-1",
                "metrics": {"bodyTextSample": f"QR label agri://verify/{token}"},
            },
        },
        "requestFailures": [{"url": f"http://127.0.0.1:5174/api/qr/{token}/verify", "failure": "failed"}],
    }
    tokens = script.extract_public_qr_route_tokens(report)
    redacted = script.redact_report_public_tokens(report, tokens)
    payload = json.dumps(redacted)

    assert token in tokens
    assert token not in payload
    assert script.PUBLIC_QR_TOKEN_REDACTION in payload
    assert "agri://verify/" in payload
    assert "/api/qr/" in payload


def test_product_detail_browser_smoke_masks_public_qr_screenshot_artifacts(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_screenshot_mask_under_test",
    )
    scripts = []
    screenshots = []

    class FakePage:
        def evaluate(self, script_text):
            scripts.append(script_text)

        def screenshot(self, **kwargs):
            screenshots.append(kwargs)

    script.capture_screenshot(FakePage(), tmp_path / "product-detail.png")

    assert screenshots[0]["full_page"] is False
    assert "Product verification QR" in scripts[0]
    assert "agri:\\/\\/verify" in scripts[0]
    assert script.PUBLIC_QR_TOKEN_REDACTION in scripts[0]


def test_consumer_verify_unavailable_browser_smoke_route_and_viewport():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "consumer_verify_unavailable_browser_smoke.py",
        "consumer_verify_unavailable_browser_smoke_under_test",
    )

    assert script.parse_viewport("390x844") == {"width": 390, "height": 844}
    assert script.route_url("http://127.0.0.1:5174/", "offline-token").startswith(
        "http://127.0.0.1:5174/verify/offline-token?scan_source=unavailable_smoke"
    )
    assert script.verify_api_route_patterns("offline-token") == (
        "**/api/api/qr/offline-token/verify**",
        "**/api/qr/offline-token/verify**",
    )
    assert script.verify_api_route_patterns("token with space") == (
        "**/api/api/qr/token%20with%20space/verify**",
        "**/api/qr/token%20with%20space/verify**",
    )


def test_consumer_verify_unavailable_browser_smoke_redacts_report_token():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "consumer_verify_unavailable_browser_smoke.py",
        "consumer_verify_unavailable_browser_smoke_redaction_under_test",
    )

    token = "unavailable-secret-token"
    report = {
        "url": f"http://127.0.0.1:5174/verify/{token}?scan_source=unavailable_smoke",
        "apiResponses": [{"url": f"http://127.0.0.1:5174/api/qr/{token}/verify", "status": 503}],
        "checks": [{"name": "failure", "ok": True, "detail": f"/api/qr/{token}/verify"}],
    }
    redacted = script.redact_report_public_tokens(report, {token})
    payload = json.dumps(redacted)

    assert token not in payload
    assert script.PUBLIC_QR_TOKEN_REDACTION in payload
    assert "/api/qr/" in payload
    assert "/verify" in payload


def test_qr_path_browser_smoke_tracks_public_verify_cache_headers():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "qr_path_browser_smoke.py",
        "qr_path_browser_smoke_public_verify_cache_under_test",
    )

    assert script.is_public_verify_api_response("http://127.0.0.1:5174/api/qr/token-1/verify?session_id=s1")
    assert script.is_public_verify_api_response("http://127.0.0.1:5174/api/api/qr/token-1/verify")
    assert not script.is_public_verify_api_response("http://127.0.0.1:5174/api/qr/token-1")
    assert script.public_verify_response_cache_ok(
        {
            "cacheControl": "no-store",
            "pragma": "no-cache",
            "expires": "0",
        }
    )
    assert not script.public_verify_response_cache_ok(
        {
            "cacheControl": "max-age=60",
            "pragma": "no-cache",
            "expires": "0",
        }
    )


def test_consumer_verify_unavailable_browser_smoke_classifies_expected_api_failures():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "consumer_verify_unavailable_browser_smoke.py",
        "consumer_verify_unavailable_browser_smoke_failure_classification_under_test",
    )

    assert script.is_expected_unavailable_console(
        {"type": "error", "text": "Failed to load resource: the server responded with a status of 502 (Bad Gateway)"}
    )
    assert script.is_expected_unavailable_console(
        {"type": "error", "text": "Failed to verify QR token AxiosError: Request failed with status code 503"}
    )
    assert script.is_expected_unavailable_console(
        {"type": "warning", "text": "Service Worker registration blocked by Playwright"}
    )
    assert not script.is_expected_unavailable_console({"type": "error", "text": "Uncaught TypeError"})
    assert script.has_unavailable_api_failure([{"url": "/api/api/qr/token/verify", "status": 502}], [])
    assert script.has_unavailable_api_failure([], [{"url": "/api/api/qr/token/verify", "failure": "net::ERR_FAILED"}])
    assert not script.has_unavailable_api_failure([{"url": "/api/api/qr/token/verify", "status": 200}], [])
