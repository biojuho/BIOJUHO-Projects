# ruff: noqa: N806  # TestingSessionLocal follows SQLAlchemy naming convention
from __future__ import annotations

from urllib.parse import urlparse

import models
import pytest
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import products
from services import qr_tokens as qr_token_service
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


def _client_for_user(db_session, user: dict) -> TestClient:
    app = FastAPI()

    def override_get_db():
        yield db_session

    app.dependency_overrides[products.get_db] = override_get_db
    app.dependency_overrides[products.get_current_user] = lambda: user
    app.include_router(products.router)
    return TestClient(app)


def _create_product_record(
    db_session,
    *,
    product_id: str,
    owner_id: str = "farmer-1",
    name: str = "Shine Muscat",
    origin: str = "Naju",
) -> models.Product:
    product = models.Product(
        id=product_id,
        owner_id=owner_id,
        qr_code=f"agri://verify/{product_id}",
        name=name,
        description="Cold-chain produce",
        category="Fruit",
        origin=origin,
        requires_cold_chain=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


def test_create_product_issues_hashed_qr_token_and_public_label_url(db_session, monkeypatch):
    monkeypatch.setattr(products, "get_chain", lambda: type("Chain", (), {"log_event": lambda *_args, **_kwargs: None})())
    monkeypatch.setenv("PUBLIC_VERIFY_BASE_URL", "https://verify.agriguard.test/")
    operator = {"uid": "operator-1", "email": "ops@example.com", "role": "operator"}

    with _client_for_user(db_session, operator) as client:
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
    parsed = urlparse(payload["qr_code"])
    assert f"{parsed.scheme}://{parsed.netloc}" == "https://verify.agriguard.test"
    raw_token = parsed.path.removeprefix("/verify/")
    assert raw_token and raw_token != payload["id"]

    saved_token = db_session.query(models.QRToken).filter(models.QRToken.product_id == payload["id"]).one()
    assert saved_token.batch_code.startswith("AG-")
    assert saved_token.token_hash == qr_token_service.hash_qr_token(raw_token)
    assert raw_token not in saved_token.token_hash


def test_product_page_returns_metadata_and_searches_id_name_origin(db_session):
    _create_product_record(db_session, product_id="apple-1", name="Organic Apple", origin="Korea")
    _create_product_record(db_session, product_id="tomato-1", name="Tomatoes", origin="Busan")
    _create_product_record(db_session, product_id="wheat-1", name="Wheat", origin="Farmville")
    operator = {"uid": "operator-1", "email": "ops@example.com", "role": "operator"}

    with _client_for_user(db_session, operator) as client:
        page_response = client.get("/products/page", params={"page": 2, "page_size": 2})
        by_name = client.get("/products/page", params={"search": "apple", "page_size": 20})
        by_origin = client.get("/products/page", params={"search": "busan", "page_size": 20})
        by_id = client.get("/products/page", params={"search": "wheat-1", "page_size": 20})

    assert page_response.status_code == 200
    page_payload = page_response.json()
    assert page_payload["total"] == 3
    assert page_payload["page"] == 2
    assert page_payload["page_size"] == 2
    assert page_payload["total_pages"] == 2
    assert [item["id"] for item in page_payload["items"]] == ["wheat-1"]

    assert [item["id"] for item in by_name.json()["items"]] == ["apple-1"]
    assert [item["id"] for item in by_origin.json()["items"]] == ["tomato-1"]
    assert [item["id"] for item in by_id.json()["items"]] == ["wheat-1"]


def test_product_routes_scope_regular_user_to_owned_products(db_session):
    _create_product_record(db_session, product_id="owned-product", owner_id="farmer-1", name="Owned Grapes")
    _create_product_record(db_session, product_id="other-product", owner_id="farmer-2", name="Other Apples")
    regular_user = {"uid": "farmer-1", "email": "farmer-1@example.com", "role": "Farmer"}

    with _client_for_user(db_session, regular_user) as client:
        list_response = client.get("/products/")
        page_response = client.get("/products/page", params={"page_size": 20})
        owned_response = client.get("/products/owned-product")
        other_response = client.get("/products/other-product")

    assert list_response.status_code == 200
    assert {item["id"] for item in list_response.json()} == {"owned-product"}
    assert page_response.status_code == 200
    assert page_response.json()["total"] == 1
    assert [item["id"] for item in page_response.json()["items"]] == ["owned-product"]
    assert owned_response.status_code == 200
    assert owned_response.json()["id"] == "owned-product"
    assert other_response.status_code == 404


def test_regular_user_cannot_create_product_for_another_owner(db_session, monkeypatch):
    chain_calls: list[object] = []
    monkeypatch.setattr(products, "get_chain", lambda: type("Chain", (), {"log_event": chain_calls.append})())
    regular_user = {"uid": "farmer-1", "email": "farmer-1@example.com", "role": "Farmer"}

    with _client_for_user(db_session, regular_user) as client:
        response = client.post(
            "/products/",
            params={"owner_id": "farmer-2"},
            json={
                "name": "Cross Tenant Product",
                "description": "Should not be allowed",
                "category": "Fruit",
                "origin": "Naju",
                "requires_cold_chain": True,
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cannot create a product for another owner."}
    assert db_session.query(models.Product).count() == 0
    assert chain_calls == []
