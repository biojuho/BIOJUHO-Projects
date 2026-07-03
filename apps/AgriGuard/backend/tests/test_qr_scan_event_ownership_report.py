from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import models
import pytest
from database import Base
from scripts import report_qr_scan_event_ownership
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _event(
    *,
    event_id: str,
    source: str,
    event_type: str,
    product_id: str | None = None,
    qr_value: str | None = None,
    error_code: str | None = None,
    metadata: dict | str | None = None,
) -> models.QRScanEvent:
    metadata_json = metadata if isinstance(metadata, str) else json.dumps(metadata or {})
    return models.QRScanEvent(
        id=event_id,
        session_id=f"session-{event_id}",
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        product_id=product_id,
        qr_value=qr_value,
        error_code=error_code,
        source=source,
        variant_id="test",
        metadata_json=metadata_json,
    )


def _seed_ownership_fixture(db_session):
    db_session.add_all(
        [
            models.Product(id="product-owned", name="Owned Greens", owner_id="farmer-1"),
            models.Product(id="product-conflict", name="Conflict Greens", owner_id="farmer-2"),
            models.SensorDevice(sensor_id="sensor-owned", owner_id="farmer-3", registered_at=datetime.now(UTC), updated_at=datetime.now(UTC)),
        ]
    )
    db_session.add_all(
        [
            _event(event_id="via-product", source="consumer_verify_page", event_type="verification_complete", product_id="product-owned"),
            _event(
                event_id="via-sensor",
                source="mqtt_ingest",
                event_type="mqtt_sensor_rejected",
                qr_value="sensor-owned",
                metadata={"sensor_id": "sensor-owned"},
            ),
            _event(
                event_id="via-metadata",
                source="sensor_device_admin",
                event_type="mqtt_broker_provisioning_applied",
                metadata={"owner_id": "farmer-4"},
            ),
            _event(
                event_id="public-diagnostic",
                source="consumer_verify_page",
                event_type="scan_failure",
                metadata={"token_status": "missing"},
            ),
            _event(event_id="unresolved-admin", source="sensor_device_admin", event_type="sensor_owner_cleared"),
            _event(
                event_id="conflict",
                source="qr_token_admin",
                event_type="qr_token_reissued",
                product_id="product-conflict",
                metadata={"owner_id": "farmer-other"},
            ),
            _event(event_id="bad-metadata", source="consumer_verify_page", event_type="scan_failure", metadata="{not json"),
        ]
    )
    db_session.commit()


def test_qr_scan_event_ownership_report_counts_paths_and_review_items(db_session):
    _seed_ownership_fixture(db_session)

    report = report_qr_scan_event_ownership.build_qr_scan_event_ownership_report(db_session, sample_limit=10)

    assert report["status"] == "warn"
    assert report["total_events"] == 7
    assert report["owned_event_count"] == 3
    assert report["unresolved_event_count"] == 3
    assert report["conflict_event_count"] == 1
    assert report["invalid_metadata_count"] == 1
    assert report["global_diagnostic_event_count"] == 1
    assert report["blocked_event_count"] == 3
    assert report["blocked_for_qr_scan_events_rls"] is True
    assert report["rls_visibility_counts"] == {
        "blocked": 3,
        "global_diagnostic": 1,
        "tenant_owned": 3,
    }
    assert report["owner_path_counts"] == {
        "metadata_json.owner_id": 1,
        "product_id -> products.owner_id": 2,
        "sensor_id -> sensor_devices.owner_id": 1,
        "unresolved": 3,
    }
    review_ids = {item["event_id"] for item in report["review_items"]}
    assert {"unresolved-admin", "conflict", "bad-metadata"} <= review_ids
    assert "public-diagnostic" not in review_ids


def test_classify_qr_scan_event_prefers_product_owner_and_flags_conflict(db_session):
    _seed_ownership_fixture(db_session)
    product_owners, sensor_owners = report_qr_scan_event_ownership._owner_maps(db_session)
    event = db_session.get(models.QRScanEvent, "conflict")

    item = report_qr_scan_event_ownership.classify_qr_scan_event(
        event,
        product_owners=product_owners,
        sensor_owners=sensor_owners,
    )

    assert item["status"] == "conflict"
    assert item["owner_id"] == "farmer-2"
    assert item["owner_path"] == "product_id -> products.owner_id"
    assert item["candidate_owner_ids"] == ["farmer-2", "farmer-other"]


def test_classify_public_diagnostic_scan_failure_is_global_only_not_blocked(db_session):
    event = _event(
        event_id="public-diagnostic-only",
        source="consumer_verify_page",
        event_type="scan_failure",
        error_code="invalid_or_expired_qr",
        metadata={"token_status": "missing"},
    )
    db_session.add(event)
    db_session.commit()

    item = report_qr_scan_event_ownership.classify_qr_scan_event(
        event,
        product_owners={},
        sensor_owners={},
    )

    assert item["status"] == "unresolved"
    assert item["rls_visibility"] == "global_diagnostic"
    assert item["requires_review"] is False


def test_qr_scan_event_ownership_report_cli_outputs_json_and_markdown(tmp_path):
    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    json_out = tmp_path / "ownership.json"
    markdown_out = tmp_path / "ownership.md"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["AUTO_CREATE_SCHEMA"] = "1"
    env["AGRIGUARD_ENV_FILE"] = str(tmp_path / "missing.env")

    setup_code = """
from datetime import datetime, timezone
from database import initialize_database, SessionLocal
import models
initialize_database()
db = SessionLocal()
try:
    db.add(models.Product(id="product-cli", name="CLI Product", owner_id="farmer-cli"))
    db.add(models.QRScanEvent(
        id="cli-event",
        session_id="cli-session",
        event_type="verification_complete",
        occurred_at=datetime.now(timezone.utc),
        product_id="product-cli",
        source="consumer_verify_page",
        variant_id="test",
        metadata_json="{}",
    ))
    db.commit()
finally:
    db.close()
"""
    setup_result = subprocess.run([PYTHON, "-c", setup_code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert setup_result.returncode == 0, setup_result.stderr or setup_result.stdout

    result = subprocess.run(
        [
            PYTHON,
            "scripts/report_qr_scan_event_ownership.py",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--fail-on-blocked",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["database_target"].startswith("sqlite:///")
    assert payload["owned_event_count"] == 1
    assert payload["blocked_for_qr_scan_events_rls"] is False
    assert "product_id -> products.owner_id" in markdown_out.read_text(encoding="utf-8")


def test_qr_scan_event_ownership_report_cli_fail_on_blocked_rejects_unscoped_rows(tmp_path):
    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["AUTO_CREATE_SCHEMA"] = "1"
    env["AGRIGUARD_ENV_FILE"] = str(tmp_path / "missing.env")

    setup_code = """
from datetime import datetime, timezone
from database import initialize_database, SessionLocal
import models
initialize_database()
db = SessionLocal()
try:
    db.add(models.QRScanEvent(
        id="blocked-event",
        session_id="blocked-session",
        event_type="sensor_owner_cleared",
        occurred_at=datetime.now(timezone.utc),
        source="sensor_device_admin",
        variant_id="test",
        metadata_json="{}",
    ))
    db.commit()
finally:
    db.close()
"""
    setup_result = subprocess.run([PYTHON, "-c", setup_code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert setup_result.returncode == 0, setup_result.stderr or setup_result.stdout

    result = subprocess.run(
        [PYTHON, "scripts/report_qr_scan_event_ownership.py", "--fail-on-blocked"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Blocked events: `1`" in result.stdout
    assert "Traceback" not in result.stderr


def test_qr_scan_event_ownership_report_cli_fails_closed_when_schema_is_missing(tmp_path):
    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["AUTO_CREATE_SCHEMA"] = "0"
    env["AGRIGUARD_ENV_FILE"] = str(tmp_path / "missing.env")

    result = subprocess.run(
        [PYTHON, "scripts/report_qr_scan_event_ownership.py"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "database schema is not ready" in result.stderr
    assert "Traceback" not in result.stderr
