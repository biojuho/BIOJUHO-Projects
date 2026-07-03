from __future__ import annotations

from unittest.mock import MagicMock

import models
import pytest
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import products
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
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = testing_session()

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
        "uid": "test-operator",
        "email": "operator@example.com",
        "role": "operator",
    }
    app.include_router(products.router)

    with TestClient(app) as test_client:
        yield test_client


def _create_product(db_session, *, product_id: str = "timeline-product") -> None:
    db_session.add(
        models.Product(
            id=product_id,
            owner_id="dev-user-id",
            qr_code=f"agri://verify/{product_id}",
            name="Timeline Product",
            description="Timeline action contract product",
            category="Vegetables",
            origin="Naju",
            requires_cold_chain=True,
        )
    )
    db_session.commit()


def test_tracking_chain_event_includes_action_for_timeline(client, db_session, monkeypatch):
    product_id = "timeline-product"
    _create_product(db_session, product_id=product_id)
    mock_chain = MagicMock()
    monkeypatch.setattr(products, "get_chain", lambda: mock_chain)

    response = client.post(
        f"/products/{product_id}/track",
        params={
            "status": "in_transit",
            "location": "Seoul Hub",
            "handler_id": "handler-7",
        },
    )

    assert response.status_code == 200
    logged_product_id, logged_event = mock_chain.log_event.call_args.args
    assert logged_product_id == product_id
    assert logged_event["action"] == "IN_TRANSIT"
    assert logged_event["status"] == "in_transit"
