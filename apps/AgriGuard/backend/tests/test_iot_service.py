from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import iot_service
import models
import pytest
from database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def testing_session_local():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    original_session_local = iot_service.SessionLocal
    original_history = list(iot_service._sensor_history)
    iot_service.SessionLocal = testing_session_local
    iot_service._sensor_history.clear()
    iot_service._reading_buffer.clear()

    try:
        yield testing_session_local
    finally:
        iot_service.SessionLocal = original_session_local
        iot_service._sensor_history[:] = original_history
        iot_service._reading_buffer.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_sensor_reading(
    session,
    *,
    sensor_id: str,
    zone: str,
    temperature: float,
    humidity: float,
    timestamp: datetime,
    status: str,
    battery: float = 95.0,
):
    session.add(
        models.SensorReading(
            sensor_id=sensor_id,
            zone=zone,
            temperature=temperature,
            humidity=humidity,
            timestamp=timestamp.replace(tzinfo=None),
            status=status,
            battery=battery,
        )
    )
    session.commit()


def test_get_latest_readings_prefers_database_state(testing_session_local):
    session = testing_session_local()
    now = datetime.now(UTC)
    _seed_sensor_reading(
        session,
        sensor_id="sensor-recent",
        zone="Cold Storage A",
        temperature=12.5,
        humidity=61.0,
        timestamp=now - timedelta(minutes=10),
        status="alert",
    )
    _seed_sensor_reading(
        session,
        sensor_id="sensor-old",
        zone="Cold Storage B",
        temperature=-18.0,
        humidity=55.0,
        timestamp=now - timedelta(hours=3),
        status="normal",
    )

    readings = iot_service.get_latest_readings(hours=1)

    assert len(readings) == 1
    assert readings[0]["sensor_id"] == "sensor-recent"
    assert readings[0]["status"] == "alert"
    assert readings[0]["timestamp"].endswith("Z")
    assert "Temperature too high: 12.5C" in readings[0]["alerts"]


def test_get_current_status_aggregates_database_rows(testing_session_local):
    session = testing_session_local()
    now = datetime.now(UTC)
    _seed_sensor_reading(
        session,
        sensor_id="zone-a-1",
        zone="Cold Storage A",
        temperature=-20.0,
        humidity=50.0,
        timestamp=now - timedelta(minutes=15),
        status="normal",
    )
    _seed_sensor_reading(
        session,
        sensor_id="zone-a-2",
        zone="Cold Storage A",
        temperature=11.0,
        humidity=52.0,
        timestamp=now - timedelta(minutes=5),
        status="alert",
    )
    _seed_sensor_reading(
        session,
        sensor_id="zone-b-1",
        zone="Transport Unit 1",
        temperature=-16.0,
        humidity=48.0,
        timestamp=now - timedelta(minutes=8),
        status="normal",
    )

    status = iot_service.get_current_status()

    assert status["overall_status"] == "alert"
    assert status["total_readings"] == 3
    zones = {zone["zone"]: zone for zone in status["zones"]}
    assert zones["Cold Storage A"]["readings_count"] == 2
    assert zones["Cold Storage A"]["alert_count"] == 1
    assert zones["Transport Unit 1"]["readings_count"] == 1
    assert zones["Transport Unit 1"]["alert_count"] == 0


def test_broadcast_messages_include_origin_and_skip_self_relay():
    reading = {
        "sensor_id": "sensor-1",
        "timestamp": "2026-04-08T00:00:00Z",
        "temperature": -18.0,
        "humidity": 55.0,
        "battery": 90.0,
        "zone": "Cold Storage A",
        "status": "normal",
        "alerts": [],
    }

    wrapped = iot_service._build_broadcast_message(reading)
    decoded = iot_service._decode_broadcast_message(json.dumps(wrapped))

    assert decoded["origin"] == iot_service._WORKER_INSTANCE_ID
    assert decoded["reading"] == reading
    assert iot_service._should_relay_broadcast(decoded) is False
    assert iot_service._should_relay_broadcast({"origin": "another-worker", "reading": reading}) is True


def test_buffer_reading_keeps_backlog_beyond_previous_maxlen(testing_session_local):
    reading = {
        "sensor_id": "sensor-backlog",
        "timestamp": "2026-04-08T00:00:00Z",
        "temperature": -18.0,
        "humidity": 55.0,
        "battery": 95.0,
        "zone": "Cold Storage A",
        "status": "normal",
        "alerts": [],
    }

    for _ in range(5100):
        iot_service._buffer_reading(dict(reading))

    assert len(iot_service._reading_buffer) == 5100


def test_flush_reading_buffer_requeues_failed_batch(monkeypatch, testing_session_local):
    class FailingSession:
        def bulk_save_objects(self, objects):
            self.objects = objects

        def commit(self):
            raise RuntimeError("db unavailable")

        def rollback(self):
            return None

        def close(self):
            return None

    reading = {
        "sensor_id": "sensor-fail",
        "timestamp": "2026-04-08T00:00:00Z",
        "temperature": -18.0,
        "humidity": 55.0,
        "battery": 95.0,
        "zone": "Cold Storage A",
        "status": "normal",
        "alerts": [],
    }

    iot_service._buffer_reading(dict(reading))
    monkeypatch.setattr(iot_service, "SessionLocal", lambda: FailingSession())

    assert iot_service._flush_reading_buffer() == 0
    assert len(iot_service._reading_buffer) == 1
    assert iot_service._reading_buffer[0]["sensor_id"] == "sensor-fail"


@pytest.mark.asyncio
async def test_close_iot_resources_flushes_pending_buffer(testing_session_local):
    reading = {
        "sensor_id": "sensor-close",
        "timestamp": "2026-04-08T00:00:00Z",
        "temperature": -18.0,
        "humidity": 55.0,
        "battery": 95.0,
        "zone": "Cold Storage A",
        "status": "normal",
        "alerts": [],
    }

    iot_service._buffer_reading(dict(reading))

    await iot_service.close_iot_resources()

    session = testing_session_local()
    rows = session.query(models.SensorReading).all()
    assert len(rows) == 1
    assert rows[0].sensor_id == "sensor-close"
    assert len(iot_service._reading_buffer) == 0
