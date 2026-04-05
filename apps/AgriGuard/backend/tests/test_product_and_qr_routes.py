from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import models
import pytest
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import products, qr_events
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

    app.dependency_overrides[products.get_db] = override_get_db
    app.dependency_overrides[products.get_current_user] = lambda: {
        "uid": "test-user-id",
        "email": "tester@example.com",
        "name": "QA Tester",
    }
    app.dependency_overrides[qr_events.get_db] = override_get_db

    app.include_router(products.router)
    app.include_router(qr_events.router)

    with TestClient(app) as test_client:
        yield test_client


def _create_product_record(db_session, *, product_id: str = "product-1") -> models.Product:
    product = models.Product(
        id=product_id,
        owner_id="farmer-1",
        qr_code=f"agri://verify/{product_id}",
        name="Shine Muscat",
        description="Cold-chain grapes",
        category="Fruit",
        origin="Naju",
        requires_cold_chain=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


def test_create_product_persists_record_and_logs_register_event(client, db_session, monkeypatch):
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        "/products/",
        params={"owner_id": "farmer-1"},
        json={
            "name": "Shine Muscat",
            "description": "Cold-chain grapes",
            "category": "Fruit",
            "origin": "Naju",
            "requires_cold_chain": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["owner_id"] == "farmer-1"
    assert payload["qr_code"] == f"agri://verify/{payload['id']}"
    assert payload["tracking_history"] == []
    assert payload["certificates"] == []

    saved = db_session.query(models.Product).filter(models.Product.id == payload["id"]).one()
    assert saved.name == "Shine Muscat"
    assert saved.origin == "Naju"
    assert saved.requires_cold_chain is True

    mock_chain.log_event.assert_called_once_with(
        payload["id"],
        {"action": "REGISTER", "owner": "farmer-1"},
    )


def test_create_product_returns_500_without_chain_log_when_commit_fails(client, db_session, monkeypatch):
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    def failing_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    response = client.post(
        "/products/",
        params={"owner_id": "farmer-1"},
        json={
            "name": "Shine Muscat",
            "description": "Cold-chain grapes",
            "category": "Fruit",
            "origin": "Naju",
            "requires_cold_chain": True,
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Product creation failed: database unavailable"}
    assert db_session.query(models.Product).count() == 0
    mock_chain.log_event.assert_not_called()


def test_create_product_succeeds_when_chain_log_fails_after_commit(client, db_session, monkeypatch):
    mock_chain = MagicMock()
    mock_chain.log_event.side_effect = RuntimeError("chain offline")
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        "/products/",
        params={"owner_id": "farmer-1"},
        json={
            "name": "Shine Muscat",
            "description": "Cold-chain grapes",
            "category": "Fruit",
            "origin": "Naju",
            "requires_cold_chain": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    saved = db_session.query(models.Product).filter(models.Product.id == payload["id"]).one()
    assert saved.owner_id == "farmer-1"
    mock_chain.log_event.assert_called_once()


def test_add_tracking_event_persists_event_and_logs_timestamp(client, db_session, monkeypatch):
    _create_product_record(db_session, product_id="product-track-1")
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        "/products/product-track-1/track",
        params={
            "status": "in_transit",
            "location": "Seoul Hub",
            "handler_id": "handler-7",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["event"]["status"] == "in_transit"
    assert payload["event"]["location"] == "Seoul Hub"

    saved_event = db_session.query(models.TrackingEvent).filter(models.TrackingEvent.id == payload["event"]["id"]).one()
    assert saved_event.product_id == "product-track-1"
    assert saved_event.handler_id == "handler-7"

    logged_product_id, logged_event = mock_chain.log_event.call_args.args
    assert logged_product_id == "product-track-1"
    assert logged_event["status"] == "in_transit"
    assert logged_event["location"] == "Seoul Hub"
    assert logged_event["handler_id"] == "handler-7"
    assert datetime.fromisoformat(logged_event["timestamp"]).tzinfo == UTC


def test_add_tracking_event_returns_500_without_chain_log_when_commit_fails(client, db_session, monkeypatch):
    _create_product_record(db_session, product_id="product-track-fail")
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    def failing_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    response = client.post(
        "/products/product-track-fail/track",
        params={
            "status": "in_transit",
            "location": "Seoul Hub",
            "handler_id": "handler-7",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Tracking event failed: database unavailable"}
    assert db_session.query(models.TrackingEvent).filter(models.TrackingEvent.product_id == "product-track-fail").count() == 0
    mock_chain.log_event.assert_not_called()


def test_add_tracking_event_returns_404_for_unknown_product(client, monkeypatch):
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        "/products/missing-product/track",
        params={
            "status": "in_transit",
            "location": "Seoul Hub",
            "handler_id": "handler-7",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
    mock_chain.log_event.assert_not_called()


def test_get_product_history_returns_chain_events_for_existing_product(client, db_session, monkeypatch):
    _create_product_record(db_session, product_id="product-history-1")
    mock_chain = MagicMock()
    mock_chain.get_product_history.return_value = [
        {"tx_hash": "0xabc", "product_id": "product-history-1", "data": {"action": "REGISTER"}}
    ]
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.get("/products/product-history-1/history")

    assert response.status_code == 200
    assert response.json() == {
        "product_id": "product-history-1",
        "history": [{"tx_hash": "0xabc", "product_id": "product-history-1", "data": {"action": "REGISTER"}}],
    }
    mock_chain.get_product_history.assert_called_once_with("product-history-1")


def test_add_certification_persists_certificate_and_logs_chain_event(client, db_session, monkeypatch):
    _create_product_record(db_session, product_id="product-cert-1")
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        "/products/product-cert-1/certifications",
        params={"cert_type": "Organic", "issued_by": "Korea GAP"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "product-cert-1"
    assert len(payload["certificates"]) == 1
    assert payload["certificates"][0]["cert_type"] == "Organic"
    assert payload["certificates"][0]["issued_by"] == "Korea GAP"

    saved_cert = db_session.query(models.Certificate).filter(models.Certificate.product_id == "product-cert-1").one()
    assert saved_cert.cert_type == "Organic"
    assert saved_cert.issued_by == "Korea GAP"
    assert saved_cert.cert_id.startswith("CERT-")

    logged_product_id, logged_event = mock_chain.log_event.call_args.args
    assert logged_product_id == "product-cert-1"
    assert logged_event["action"] == "CERTIFICATION_ISSUED"
    assert logged_event["cert_type"] == "Organic"
    assert logged_event["issued_by"] == "Korea GAP"
    assert logged_event["cert_id"] == saved_cert.cert_id


def test_add_certification_returns_500_and_rolls_back_when_commit_fails(client, db_session, monkeypatch):
    _create_product_record(db_session, product_id="product-cert-fail")
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    original_commit = db_session.commit
    commit_calls = {"count": 0}

    def failing_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 1:
            raise RuntimeError("database unavailable")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", failing_commit)

    response = client.post(
        "/products/product-cert-fail/certifications",
        params={"cert_type": "Organic", "issued_by": "Korea GAP"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Certification failed: database unavailable"}
    assert db_session.query(models.Certificate).filter(models.Certificate.product_id == "product-cert-fail").count() == 0
    mock_chain.log_event.assert_not_called()


def test_capture_qr_scan_event_persists_unicode_metadata_and_defaults(client, db_session):
    korean_reason = "\uce74\uba54\ub77c \uad8c\ud55c \uac70\ubd80"

    response = client.post(
        "/qr-events",
        json={
            "session_id": "session-1",
            "event_type": "scan_failure",
            "error_code": "camera_denied",
            "error_message": "Camera permission denied",
            "event_payload": {"reason": korean_reason, "retryable": True},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"

    saved = db_session.query(models.QRScanEvent).filter(models.QRScanEvent.id == payload["event_id"]).one()
    assert saved.session_id == "session-1"
    assert saved.source == "qr_reader"
    assert saved.variant_id == "qr_page_v1"
    assert saved.occurred_at is not None
    assert json.loads(saved.metadata_json) == {"reason": korean_reason, "retryable": True}
    assert korean_reason in saved.metadata_json


def test_qr_event_summary_returns_empty_shape_when_no_events(client):
    response = client.get("/qr-events/summary", params={"hours": 12})

    assert response.status_code == 200
    payload = response.json()

    assert payload["hours"] == 12
    assert payload["variant_id"] == "all"
    assert payload["total_events"] == 0
    assert payload["total_sessions"] == 0
    assert payload["event_counts"] == {}
    assert payload["error_counts"] == {}
    assert payload["variant_counts"] == {}
    assert payload["funnel"] == {
        "scan_start_sessions": 0,
        "scan_failure_sessions": 0,
        "scan_recovery_sessions": 0,
        "verification_complete_sessions": 0,
        "verification_completion_rate": 0.0,
        "recovery_rate_after_failure": 0.0,
    }


def test_qr_event_summary_filters_variant_and_handles_zero_start_sessions(client, db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            models.QRScanEvent(
                session_id="session-a",
                event_type="scan_start",
                occurred_at=now,
                variant_id="variant-a",
            ),
            models.QRScanEvent(
                session_id="session-a",
                event_type="verification_complete",
                occurred_at=now,
                variant_id="variant-a",
            ),
            models.QRScanEvent(
                session_id="session-b",
                event_type="scan_failure",
                occurred_at=now,
                variant_id="variant-b",
                error_code="camera_denied",
            ),
            models.QRScanEvent(
                session_id="session-b",
                event_type="scan_recovery",
                occurred_at=now,
                variant_id="variant-b",
            ),
            models.QRScanEvent(
                session_id="session-c",
                event_type="scan_failure",
                occurred_at=now,
                variant_id="variant-b",
                error_code="invalid_qr",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/qr-events/summary", params={"hours": 24, "variant_id": "variant-b"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["variant_id"] == "variant-b"
    assert payload["total_events"] == 3
    assert payload["total_sessions"] == 2
    assert payload["event_counts"] == {"scan_failure": 2, "scan_recovery": 1}
    assert payload["error_counts"] == {"camera_denied": 1, "invalid_qr": 1}
    assert payload["variant_counts"] == {"variant-b": 3}
    assert payload["funnel"]["scan_start_sessions"] == 0
    assert payload["funnel"]["scan_failure_sessions"] == 2
    assert payload["funnel"]["scan_recovery_sessions"] == 1
    assert payload["funnel"]["verification_complete_sessions"] == 0
    assert payload["funnel"]["verification_completion_rate"] == 0.0
    assert payload["funnel"]["recovery_rate_after_failure"] == 0.5
