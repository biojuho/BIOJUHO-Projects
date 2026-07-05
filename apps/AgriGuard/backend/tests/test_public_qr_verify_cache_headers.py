from __future__ import annotations

import models
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import qr_verify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def test_public_qr_verify_disables_response_caching() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    app = FastAPI()

    def override_get_db():
        yield session

    app.dependency_overrides[qr_verify.get_db] = override_get_db
    app.include_router(qr_verify.router)

    try:
        with TestClient(app) as client:
            response = client.get("/api/qr/not-a-real-token/verify", params={"session_id": "cache-header-probe"})

        assert response.status_code == 200
        for header, expected in qr_verify.PUBLIC_VERIFY_CACHE_HEADERS.items():
            assert response.headers[header] == expected

        saved = session.query(models.QRScanEvent).filter_by(session_id="cache-header-probe").one()
        assert saved.error_code == "invalid_or_expired_qr"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_public_qr_verify_normalizes_analytics_labels() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    app = FastAPI()

    def override_get_db():
        yield session

    app.dependency_overrides[qr_verify.get_db] = override_get_db
    app.include_router(qr_verify.router)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/qr/not-a-real-token/verify",
                params={
                    "session_id": "bad session\nid",
                    "variant_id": "qr consumer<script>",
                    "source": "public verify page",
                },
            )

        assert response.status_code == 200
        saved = session.query(models.QRScanEvent).one()
        assert saved.session_id.startswith("public-")
        assert saved.variant_id == "qr_consumer_v1"
        assert saved.source == "consumer_verify_page"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
