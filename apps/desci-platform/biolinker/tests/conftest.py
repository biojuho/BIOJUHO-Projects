"""
pytest configuration & shared fixtures for BioLinker tests.

Centralises monkeypatch stubs for external services (ChromaDB, Firebase,
Web3, IPFS) so individual test modules don't have to repeat setup boilerplate.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ── Ensure biolinker package root is on sys.path ─────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import main as app_main  # noqa: E402
import routers.crawl as crawl_router  # noqa: E402
import routers.rfp as rfp_router  # noqa: E402
import routers.web3 as web3_router  # noqa: E402
import services.usage_middleware as usage_mw  # noqa: E402


# ── Warnings suppression ────────────────────────────────────────────────────


def pytest_configure(config):  # noqa: ARG001
    # python-multipart internal import path changed
    warnings.filterwarnings(
        "ignore",
        message="Please use `import python_multipart` instead",
        category=PendingDeprecationWarning,
    )
    # google-genai internal async client inheritance
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )
    # FastAPI uses deprecated asyncio.iscoroutinefunction (Python 3.12+)
    warnings.filterwarnings(
        "ignore",
        message="'asyncio.iscoroutinefunction' is deprecated",
        category=DeprecationWarning,
    )
    # FastAPI HTTP status constant renamed
    warnings.filterwarnings(
        "ignore",
        message="'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated",
        category=DeprecationWarning,
    )
    # websockets legacy module deprecated in v14
    warnings.filterwarnings(
        "ignore",
        message="websockets.legacy is deprecated",
        category=DeprecationWarning,
    )
    # google-genai uses Python 3.14-deprecated typing internals
    warnings.filterwarnings(
        "ignore",
        message="'_UnionGenericAlias' is deprecated",
        category=DeprecationWarning,
    )
    # LangChain Pydantic V1 compat layer not supported on Python 3.14+
    warnings.filterwarnings(
        "ignore",
        message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
        category=UserWarning,
    )


# ── Stub factories ──────────────────────────────────────────────────────────


@pytest.fixture
def stub_vector_store():
    """MagicMock vector store with sensible defaults."""
    store = MagicMock()
    store.count.return_value = 5
    store.search_similar.return_value = []
    return store


@pytest.fixture
def stub_web3():
    """MagicMock Web3 service (disconnected)."""
    svc = MagicMock()
    svc.is_connected = False
    return svc


@pytest.fixture
def stub_ipfs():
    """MagicMock IPFS service (configured but no-op close)."""
    svc = MagicMock()
    svc.is_configured = True
    svc.close = AsyncMock()
    return svc


# ── Composite monkeypatch fixtures ──────────────────────────────────────────


@pytest.fixture
def mock_external_services(monkeypatch, stub_vector_store, stub_web3, stub_ipfs):
    """Patch all external service singletons in main + routers at once.

    Returns a dict of the stubs so tests can further customise them.
    """
    monkeypatch.setattr(app_main, "get_vector_store", lambda: stub_vector_store)
    monkeypatch.setattr(rfp_router, "get_vector_store", lambda: stub_vector_store)
    monkeypatch.setattr(app_main, "get_web3_service", lambda: stub_web3)
    monkeypatch.setattr(app_main, "get_ipfs_service", lambda: stub_ipfs)
    monkeypatch.setattr(app_main, "db", None)
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")

    # UsageGuard / TierRequired mock — ENTERPRISE 티어로 모든 가드 통과
    from services.user_tier import UserTier as _UserTier

    stub_tier_mgr = MagicMock()
    stub_tier_mgr.get_tier = AsyncMock(return_value=_UserTier.ENTERPRISE)
    stub_tier_mgr.get_usage = AsyncMock(return_value=MagicMock(
        usage_summary=lambda: {"tier": "enterprise", "usage": {}}
    ))
    stub_tier_mgr.check_and_increment = AsyncMock(return_value=(
        True,
        {"tier": "enterprise", "usage": {"rfp_analysis": {"used": 1, "limit": 999999, "remaining": 999998}}},
    ))
    monkeypatch.setattr(usage_mw, "get_tier_manager", lambda: stub_tier_mgr)

    return {
        "vector_store": stub_vector_store,
        "web3": stub_web3,
        "ipfs": stub_ipfs,
        "tier_manager": stub_tier_mgr,
    }


@pytest.fixture
def sync_client(mock_external_services):
    """Synchronous TestClient with all external services stubbed."""
    with TestClient(app_main.app) as client:
        # 인증 바이패스 헤더 기본 설정
        client.headers["Authorization"] = "Bearer test-token-bypass"
        yield client


@pytest_asyncio.fixture
async def async_client(mock_external_services):
    """Async httpx client with all external services stubbed."""
    transport = ASGITransport(app=app_main.app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token-bypass"},
    ) as client:
        yield client
