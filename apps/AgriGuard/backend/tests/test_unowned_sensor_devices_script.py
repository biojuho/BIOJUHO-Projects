from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import models
import pytest
from database import Base
from scripts import report_unowned_sensor_devices
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_sensor_device(
    db_session,
    *,
    sensor_id: str,
    owner_id: str | None,
    is_active: bool = True,
    zone: str = "Dock A",
) -> models.SensorDevice:
    now = datetime.now(UTC)
    device = models.SensorDevice(
        sensor_id=sensor_id,
        owner_id=owner_id,
        label=f"Probe {sensor_id}",
        zone=zone,
        expected_interval_minutes=5,
        is_active=is_active,
        registered_at=now,
        first_seen_at=now - timedelta(minutes=5) if is_active else None,
        last_seen_at=now if is_active else None,
        last_battery=91.0 if is_active else None,
        last_status="normal" if is_active else None,
        updated_at=now,
    )
    db_session.add(device)
    db_session.commit()
    return device


def test_unowned_sensor_report_counts_and_samples(db_session):
    _seed_sensor_device(db_session, sensor_id="owned-sensor", owner_id="farmer-1")
    _seed_sensor_device(db_session, sensor_id="unowned-active", owner_id=None, zone="Dock A")
    _seed_sensor_device(db_session, sensor_id="unowned-disabled", owner_id=None, is_active=False, zone="Dock B")

    report = report_unowned_sensor_devices.build_unowned_sensor_report(db_session, limit=10)

    assert report["status"] == "warn"
    assert report["unowned_sensor_count"] == 2
    assert report["active_unowned_sensor_count"] == 1
    assert report["disabled_unowned_sensor_count"] == 1
    assert {item["sensor_id"] for item in report["items"]} == {"unowned-active", "unowned-disabled"}
    assert {row["zone"] for row in report["zone_counts"]} == {"Dock A", "Dock B"}


def test_unowned_sensor_backfill_requires_explicit_target(db_session):
    _seed_sensor_device(db_session, sensor_id="unowned-active", owner_id=None)

    with pytest.raises(ValueError, match="Backfill requires"):
        report_unowned_sensor_devices.build_backfill_plan(db_session, owner_id="farmer-1")


def test_unowned_sensor_backfill_rejects_owned_or_missing_targets(db_session):
    _seed_sensor_device(db_session, sensor_id="owned-sensor", owner_id="farmer-1")
    _seed_sensor_device(db_session, sensor_id="unowned-active", owner_id=None)

    with pytest.raises(ValueError, match="owned-sensor"):
        report_unowned_sensor_devices.build_backfill_plan(
            db_session,
            owner_id="farmer-2",
            sensor_ids=["owned-sensor", "unowned-active"],
        )

    with pytest.raises(ValueError, match="missing-sensor"):
        report_unowned_sensor_devices.build_backfill_plan(
            db_session,
            owner_id="farmer-2",
            sensor_ids=["missing-sensor"],
        )


def test_unowned_sensor_backfill_assigns_selected_unowned_sensor(db_session):
    _seed_sensor_device(db_session, sensor_id="owned-sensor", owner_id="farmer-1")
    _seed_sensor_device(db_session, sensor_id="unowned-active", owner_id=None)
    _seed_sensor_device(db_session, sensor_id="unowned-disabled", owner_id=None, is_active=False)

    result = report_unowned_sensor_devices.apply_owner_backfill(
        db_session,
        owner_id="farmer-2",
        sensor_ids=["unowned-active"],
    )

    assert result["applied"] is True
    assert result["updated_count"] == 1
    assert result["target_sensor_ids"] == ["unowned-active"]
    assert db_session.get(models.SensorDevice, "unowned-active").owner_id == "farmer-2"
    assert db_session.get(models.SensorDevice, "unowned-disabled").owner_id is None
    assert db_session.get(models.SensorDevice, "owned-sensor").owner_id == "farmer-1"


def test_unowned_sensor_report_cli_dry_run_outputs_json_and_markdown(tmp_path):
    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    json_out = tmp_path / "unowned-sensors.json"
    markdown_out = tmp_path / "unowned-sensors.md"
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
    db.add(models.SensorDevice(
        sensor_id="cli-unowned-1",
        owner_id=None,
        label="CLI probe",
        zone="CLI Dock",
        expected_interval_minutes=5,
        is_active=True,
        registered_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
            "scripts/report_unowned_sensor_devices.py",
            "--owner-id",
            "farmer-cli",
            "--sensor-id",
            "cli-unowned-1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["unowned_sensor_count"] == 1
    assert payload["backfill"]["applied"] is False
    assert payload["backfill"]["target_sensor_ids"] == ["cli-unowned-1"]
    assert "cli-unowned-1" in markdown_out.read_text(encoding="utf-8")


def test_unowned_sensor_report_cli_fails_closed_when_schema_is_missing(tmp_path):
    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["AUTO_CREATE_SCHEMA"] = "0"
    env["AGRIGUARD_ENV_FILE"] = str(tmp_path / "missing.env")

    result = subprocess.run(
        [PYTHON, "scripts/report_unowned_sensor_devices.py"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "database schema is not ready" in result.stderr
    assert "Traceback" not in result.stderr
