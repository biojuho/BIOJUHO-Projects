# ruff: noqa: N806  # TestingSessionLocal follows SQLAlchemy naming convention
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import models
import pytest
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import qr_events
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def override_get_db():
        yield db_session

    app.dependency_overrides[qr_events.get_db] = override_get_db
    app.include_router(qr_events.router)

    with TestClient(app) as test_client:
        yield test_client


def _qr_event(
    session_id: str,
    event_type: str,
    *,
    variant_id: str = "qr_consumer_v1",
    occurred_at: datetime,
    error_code: str | None = None,
) -> models.QRScanEvent:
    return models.QRScanEvent(
        session_id=session_id,
        event_type=event_type,
        occurred_at=occurred_at,
        variant_id=variant_id,
        error_code=error_code,
    )


def test_qr_kpis_report_scan_success_and_daily_statuses(client, db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            _qr_event("session-success", "scan_start", occurred_at=now),
            _qr_event("session-success", "verification_complete", occurred_at=now),
            _qr_event("session-recovered", "scan_start", occurred_at=now),
            _qr_event("session-recovered", "scan_failure", occurred_at=now, error_code="blurred"),
            _qr_event("session-recovered", "scan_recovery", occurred_at=now),
            _qr_event("session-recovered", "verification_complete", occurred_at=now),
            _qr_event("session-failed", "scan_start", occurred_at=now),
            _qr_event("session-failed", "scan_failure", occurred_at=now, error_code="invalid_qr"),
            _qr_event("session-direct", "verification_complete", occurred_at=now),
        ]
    )
    db_session.commit()

    response = client.get(
        "/qr-events/kpis",
        params={
            "hours": 24,
            "variant_id": "qr_consumer_v1",
            "target_scan_success_rate": 0.99,
            "target_daily_scans": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["scan_start_sessions"] == 3
    assert payload["scan_success_sessions"] == 2
    assert payload["scan_failure_sessions"] == 2
    assert payload["verification_complete_sessions"] == 3
    assert payload["consumer_scan_sessions"] == 3
    assert payload["scan_success_rate"] == 0.6667
    assert payload["scan_success_status"] == "below_target"
    assert payload["daily_scan_progress"] == 1.0
    assert payload["daily_scan_status"] == "on_track"


def test_qr_kpis_return_no_data_success_status_without_scan_starts(client, db_session):
    db_session.add(
        _qr_event("session-direct", "verification_complete", occurred_at=datetime.now(UTC))
    )
    db_session.commit()

    response = client.get("/qr-events/kpis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scan_start_sessions"] == 0
    assert payload["scan_success_sessions"] == 0
    assert payload["verification_complete_sessions"] == 1
    assert payload["scan_success_rate"] == 0.0
    assert payload["scan_success_status"] == "no_data"
    assert payload["daily_scan_status"] == "below_target"


def test_qr_kpi_trend_zero_fills_days_and_uses_timezone_boundaries(client, db_session):
    reporting_timezone = ZoneInfo("Asia/Seoul")
    today = datetime.now(UTC).astimezone(reporting_timezone).date()
    yesterday = today - timedelta(days=1)

    def at_local(day, event_time):
        return datetime.combine(day, event_time, tzinfo=reporting_timezone).astimezone(UTC)

    db_session.add_all(
        [
            _qr_event("session-yesterday", "scan_start", occurred_at=at_local(yesterday, time(23, 30))),
            _qr_event("session-yesterday", "verification_complete", occurred_at=at_local(yesterday, time(23, 45))),
            _qr_event("session-today", "scan_start", occurred_at=at_local(today, time(0, 15))),
            _qr_event("session-today", "scan_failure", occurred_at=at_local(today, time(0, 30))),
            _qr_event("session-direct", "verification_complete", occurred_at=at_local(today, time(0, 45))),
        ]
    )
    db_session.commit()

    response = client.get(
        "/qr-events/kpis/trend",
        params={
            "days": 2,
            "timezone": "Asia/Seoul",
            "target_scan_success_rate": 0.99,
            "target_daily_scans": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["timezone"] == "Asia/Seoul"
    assert [item["date"] for item in payload["items"]] == [yesterday.isoformat(), today.isoformat()]
    assert payload["items"][0]["scan_success_sessions"] == 1
    assert payload["items"][0]["scan_success_status"] == "on_track"
    assert payload["items"][1]["scan_success_sessions"] == 0
    assert payload["items"][1]["verification_complete_sessions"] == 1
    assert payload["items"][1]["scan_success_status"] == "below_target"
    assert payload["items"][1]["daily_scan_status"] == "on_track"


def test_qr_kpi_trend_rejects_unknown_timezone(client):
    response = client.get("/qr-events/kpis/trend", params={"timezone": "Mars/Base"})

    assert response.status_code == 400
    assert "Unsupported timezone" in response.json()["detail"]
