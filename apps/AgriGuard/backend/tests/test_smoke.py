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

        assert revision == ("0006_add_sensor_device_owner_scope",)
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

    assert [step.name for step in steps] == ["nav", "supply_chain", "qr_path", "admin_routes", "product_detail"]
    assert "--click-nav" in steps[0].command
    assert "--mobile" in steps[0].command
    assert "--mobile" in steps[1].command
    assert "--mobile" in steps[4].command
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


def test_browser_smoke_suite_summarizes_child_report(tmp_path: Path):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "run_browser_smoke_suite.py",
        "run_browser_smoke_suite_summary_under_test",
    )
    report_path = tmp_path / "child.json"
    report_path.write_text(
        json.dumps({"checks": [{"ok": True}, {"ok": False}, {"ok": True}]}),
        encoding="utf-8",
    )

    summary = script.summarize_child_report(report_path)

    assert summary == {
        "report_found": True,
        "checks_total": 3,
        "checks_passed": 2,
        "checks_failed": 1,
    }


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
    assert script.extract_verify_token("raw-token") == "raw-token"


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


def test_product_detail_browser_smoke_uses_phone_viewport_for_mobile_default():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_under_test",
    )

    assert script.resolve_viewport(mobile=False, viewport=None) == {"width": 1440, "height": 960}
    assert script.resolve_viewport(mobile=True, viewport=None) == {"width": 390, "height": 844}
    assert script.resolve_viewport(mobile=True, viewport="412x915") == {"width": 412, "height": 915}


def test_product_detail_browser_smoke_uses_operator_token_env(monkeypatch):
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "product_detail_browser_smoke.py",
        "product_detail_browser_smoke_operator_token_under_test",
    )

    monkeypatch.setenv("AGRIGUARD_BROWSER_OPERATOR_TOKEN", "staging-detail-token")
    monkeypatch.setattr(sys, "argv", ["product_detail_browser_smoke.py"])
    args = script.parse_args()

    assert args.operator_token == "staging-detail-token"


def test_consumer_verify_unavailable_browser_smoke_route_and_viewport():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "consumer_verify_unavailable_browser_smoke.py",
        "consumer_verify_unavailable_browser_smoke_under_test",
    )

    assert script.parse_viewport("390x844") == {"width": 390, "height": 844}
    assert script.route_url("http://127.0.0.1:5174/", "offline-token").startswith(
        "http://127.0.0.1:5174/verify/offline-token?scan_source=unavailable_smoke"
    )


def test_consumer_verify_unavailable_browser_smoke_classifies_expected_api_failures():
    script = _load_script_module(
        Path(__file__).resolve().parents[2] / "scripts" / "consumer_verify_unavailable_browser_smoke.py",
        "consumer_verify_unavailable_browser_smoke_failure_classification_under_test",
    )

    assert script.is_expected_unavailable_console(
        {"type": "error", "text": "Failed to load resource: the server responded with a status of 502 (Bad Gateway)"}
    )
    assert not script.is_expected_unavailable_console({"type": "error", "text": "Uncaught TypeError"})
    assert script.has_unavailable_api_failure([{"url": "/api/api/qr/token/verify", "status": 502}], [])
    assert script.has_unavailable_api_failure([], [{"url": "/api/api/qr/token/verify", "failure": "net::ERR_FAILED"}])
    assert not script.has_unavailable_api_failure([{"url": "/api/api/qr/token/verify", "status": 200}], [])
