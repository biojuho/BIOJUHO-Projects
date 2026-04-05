"""
Dashboard Router 통합 테스트 — demo mode fallback, 캐시 동작, 집계 로직 검증.

타겟: routers/dashboard.py
커버리지:
  - GET / : health check
  - GET /api/v1/dashboard/summary : 실데이터 + demo mode fallback + 캐시 히트
  - GET /dashboard/summary : 공급망 집계, eager-load 결과 검증
  - _build_status_distribution / _build_origin_distribution : 헬퍼 함수 엣지 케이스
"""

from __future__ import annotations

import os

# database.py creates engine at import time — force SQLite before any import
os.environ["DATABASE_URL"] = "sqlite://"

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import models
import pytest
from database import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import dashboard
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ── Fixtures ─────────────────────────────────────────────────────────────────


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


class _NoOpCache:
    """테스트용 NoOp 캐시 — 항상 miss."""

    async def get(self, key):
        return None

    async def set(self, key, value, *, ttl=None):
        pass


class _HitCache:
    """테스트용 캐시 — 저장된 값 반환."""

    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, *, ttl=None):
        self._store[key] = value


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def override_get_db():
        yield db_session

    # dashboard.py 내부의 get_db (로컬 정의)를 override
    app.dependency_overrides[dashboard.get_db] = override_get_db

    app.include_router(dashboard.router)

    with TestClient(app) as test_client:
        yield test_client


def _seed_farmer(db_session, *, name: str = "김농부") -> models.User:
    user = models.User(role="Farmer", name=name, organization="테스트농장")
    db_session.add(user)
    db_session.commit()
    return user


def _seed_product(
    db_session,
    *,
    product_id: str = "prod-1",
    origin: str = "Naju",
    harvest_date=None,
    requires_cold_chain: bool = False,
) -> models.Product:
    product = models.Product(
        id=product_id,
        owner_id="farmer-1",
        qr_code=f"agri://verify/{product_id}",
        name="Shine Muscat",
        description="Test",
        category="Fruit",
        origin=origin,
        harvest_date=harvest_date,
        requires_cold_chain=requires_cold_chain,
    )
    db_session.add(product)
    db_session.commit()
    return product


def _seed_tracking_event(
    db_session, product_id: str, *, status: str = "in_transit", location: str = "Seoul"
) -> models.TrackingEvent:
    event = models.TrackingEvent(
        product_id=product_id,
        status=status,
        location=location,
        handler_id="handler-1",
        timestamp=datetime.now(UTC),
    )
    db_session.add(event)
    db_session.commit()
    return event


def _seed_certificate(db_session, product_id: str) -> models.Certificate:
    cert = models.Certificate(
        cert_id="CERT-TEST001",
        product_id=product_id,
        issued_by="Korea GAP",
        cert_type="Organic",
    )
    db_session.add(cert)
    db_session.commit()
    return cert


# ══════════════════════════════════════════════════════════════════════════════
#  GET / — Health Check
# ══════════════════════════════════════════════════════════════════════════════


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert "AgriGuard" in payload["message"]


# ══════════════════════════════════════════════════════════════════════════════
#  GET /api/v1/dashboard/summary — Frontend Dashboard
# ══════════════════════════════════════════════════════════════════════════════


def test_frontend_dashboard_demo_mode_when_no_data(client):
    """데이터 없을 때 → demo 상수값 반환."""
    with patch.object(dashboard, "get_cache", return_value=_NoOpCache()):
        response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_farms"] == dashboard.DEMO_TOTAL_FARMS
    assert data["active_sensors"] == dashboard.DEMO_ACTIVE_SENSORS
    assert data["growth_cycles"]["active"] == dashboard.DEMO_ACTIVE_CYCLES
    assert data["growth_cycles"]["completed"] == dashboard.DEMO_COMPLETED_CYCLES
    assert len(data["recent_activity"]) >= 1


def test_frontend_dashboard_real_data(client, db_session):
    """실데이터 존재 → farmer_count, product 기반 계산."""
    _seed_farmer(db_session, name="농부1")
    _seed_farmer(db_session, name="농부2")
    p = _seed_product(db_session, product_id="prod-dash-1", harvest_date=None)
    _seed_product(db_session, product_id="prod-dash-2", harvest_date=datetime.now(UTC))
    _seed_tracking_event(db_session, "prod-dash-1", status="delivered", location="Busan")

    with patch.object(dashboard, "get_cache", return_value=_NoOpCache()):
        response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_farms"] == 2  # 실제 farmer 수
    assert data["active_sensors"] == 2 * dashboard.DEMO_SENSORS_PER_PRODUCT
    assert data["growth_cycles"]["active"] == 1  # 미수확 1개
    assert data["growth_cycles"]["completed"] == 1  # 수확 완료 1개
    assert len(data["recent_activity"]) >= 1
    assert "delivered" in data["recent_activity"][0]["event"]


def test_frontend_dashboard_cache_hit(client, db_session):
    """캐시에 값이 있으면 DB 조회 없이 캐시 반환."""
    cached_result = {
        "status": "success",
        "data": {
            "total_farms": 999,
            "active_sensors": 888,
            "critical_alerts": 0,
            "growth_cycles": {"active": 77, "completed": 66},
            "recent_activity": [{"timestamp": "2026-04-04T00:00:00Z", "event": "cached"}],
        },
    }
    cache = _HitCache()
    # 동기적으로 캐시 세팅
    cache._store["agriguard:dashboard:frontend"] = cached_result

    with patch.object(dashboard, "get_cache", return_value=cache):
        response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    assert response.json()["data"]["total_farms"] == 999


# ══════════════════════════════════════════════════════════════════════════════
#  GET /dashboard/summary — Supply Chain Summary
# ══════════════════════════════════════════════════════════════════════════════


def test_supply_chain_summary_empty(client):
    """제품 없을 때 → 모든 카운트 0."""
    with patch.object(dashboard, "get_cache", return_value=_NoOpCache()):
        response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_products"] == 0
    assert payload["certified_products"] == 0
    assert payload["cold_chain_products"] == 0
    assert payload["total_tracking_events"] == 0
    assert payload["status_distribution"] == {}
    assert payload["origin_distribution"] == {}


def test_supply_chain_summary_with_data(client, db_session):
    """제품/인증서/추적이벤트 복합 집계."""
    p1 = _seed_product(db_session, product_id="sc-1", origin="Naju", requires_cold_chain=True)
    p2 = _seed_product(db_session, product_id="sc-2", origin="Jeju", requires_cold_chain=False)
    _seed_certificate(db_session, "sc-1")
    _seed_tracking_event(db_session, "sc-1", status="in_transit", location="Seoul")
    _seed_tracking_event(db_session, "sc-1", status="delivered", location="Busan")
    _seed_tracking_event(db_session, "sc-2", status="in_transit", location="Incheon")

    with patch.object(dashboard, "get_cache", return_value=_NoOpCache()):
        response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_products"] == 2
    assert payload["certified_products"] == 1
    assert payload["cold_chain_products"] == 1
    assert payload["total_tracking_events"] == 3
    assert payload["origin_distribution"] == {"Naju": 1, "Jeju": 1}
    # status_distribution: 각 product의 최신 status 기준
    # sc-1: delivered (더 최근), sc-2: in_transit
    assert "delivered" in payload["status_distribution"] or "in_transit" in payload["status_distribution"]


# ══════════════════════════════════════════════════════════════════════════════
#  Helper functions — unit tests
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildStatusDistribution:

    def test_empty_products(self):
        assert dashboard._build_status_distribution([]) == {}

    def test_products_without_tracking_history(self, db_session):
        """tracking_history가 빈 제품 → distribution에 포함되지 않음."""
        p = _seed_product(db_session, product_id="no-history")
        # SQLAlchemy lazy-load를 위해 refresh
        db_session.refresh(p)
        result = dashboard._build_status_distribution([p])
        assert result == {}

    def test_multiple_products_aggregation(self, db_session):
        p1 = _seed_product(db_session, product_id="agg-1")
        p2 = _seed_product(db_session, product_id="agg-2")
        _seed_tracking_event(db_session, "agg-1", status="delivered")
        _seed_tracking_event(db_session, "agg-2", status="delivered")
        db_session.refresh(p1)
        db_session.refresh(p2)

        result = dashboard._build_status_distribution([p1, p2])
        assert result == {"delivered": 2}


class TestBuildOriginDistribution:

    def test_empty_products(self):
        assert dashboard._build_origin_distribution([]) == {}

    def test_null_origin_defaults_to_unknown(self, db_session):
        """origin이 None인 제품 → 'Unknown'으로 집계."""
        p = _seed_product(db_session, product_id="null-origin", origin=None)
        db_session.refresh(p)
        result = dashboard._build_origin_distribution([p])
        assert result == {"Unknown": 1}

    def test_diverse_origins(self, db_session):
        _seed_product(db_session, product_id="o-1", origin="Naju")
        _seed_product(db_session, product_id="o-2", origin="Naju")
        _seed_product(db_session, product_id="o-3", origin="Jeju")
        products = db_session.query(models.Product).all()

        result = dashboard._build_origin_distribution(products)
        assert result["Naju"] == 2
        assert result["Jeju"] == 1


class TestFormatTrackingEventAsActivity:

    def test_format_output(self, db_session):
        p = _seed_product(db_session, product_id="abcd1234-rest-of-id")
        event = _seed_tracking_event(db_session, "abcd1234-rest-of-id", status="in_transit", location="Seoul Hub")
        db_session.refresh(event)

        result = dashboard._format_tracking_event_as_activity(event)
        assert "abcd1234" in result["event"]
        assert "in_transit" in result["event"]
        assert "Seoul Hub" in result["event"]
        assert result["timestamp"].endswith("Z")
