"""
BioLinker - API Endpoint Tests
Async tests for core endpoints using httpx AsyncClient and pytest-asyncio.

External service stubs are provided by conftest.py fixtures:
  - async_client: httpx AsyncClient with all services mocked
  - mock_external_services: dict of stub objects for further customisation
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

# Module references for monkeypatching (imported via conftest sys.path setup)
import main as app_main  # noqa: E402
import routers.crawl as crawl_router  # noqa: E402
import routers.rfp as rfp_router  # noqa: E402


# ─── GET /health ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_200(async_client: AsyncClient):
    """GET /health should return 200 with subsystem status fields."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "llm_available" in data
    assert "chromadb_ok" in data
    assert "chromadb_count" in data
    assert "web3_connected" in data
    assert "ipfs_configured" in data


@pytest.mark.asyncio
async def test_health_healthy_when_vector_store_ok(async_client: AsyncClient):
    """When vector store is operational, status should be 'healthy'."""
    response = await async_client.get("/health")

    data = response.json()
    assert data["status"] == "healthy"
    assert data["chromadb_ok"] is True
    assert data["chromadb_count"] == 5


@pytest.mark.asyncio
async def test_health_degraded_when_vector_store_fails(monkeypatch):
    """When vector store raises, status should be 'degraded'."""
    from httpx import ASGITransport, AsyncClient as _AsyncClient

    broken_store = MagicMock()
    broken_store.count.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(app_main, "get_vector_store", lambda: broken_store)

    stub_web3 = MagicMock()
    stub_web3.is_connected = False
    monkeypatch.setattr(app_main, "get_web3_service", lambda: stub_web3)

    stub_ipfs = MagicMock()
    stub_ipfs.is_configured = False
    stub_ipfs.close = AsyncMock()
    monkeypatch.setattr(app_main, "get_ipfs_service", lambda: stub_ipfs)
    monkeypatch.setattr(app_main, "db", None)

    transport = ASGITransport(app=app_main.app)
    async with _AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    data = response.json()
    assert data["status"] == "degraded"
    assert data["chromadb_ok"] is False


# ─── GET /notices ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notices_returns_200(async_client: AsyncClient, monkeypatch):
    """GET /notices should delegate to scheduler and return a list."""
    mock_notices = [
        {"id": "n1", "title": "Test Notice", "source": "KDDF"},
        {"id": "n2", "title": "Another Notice", "source": "NTIS"},
    ]

    stub_scheduler = MagicMock()
    stub_scheduler.get_notices.return_value = mock_notices
    monkeypatch.setattr(crawl_router, "get_scheduler", lambda: stub_scheduler)

    response = await async_client.get("/notices")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == "n1"


@pytest.mark.asyncio
async def test_notices_filters_by_source(async_client: AsyncClient, monkeypatch):
    """GET /notices?source=KDDF should pass the source filter to the scheduler."""
    stub_scheduler = MagicMock()
    stub_scheduler.get_notices.return_value = [
        {"id": "k1", "title": "KDDF Notice", "source": "KDDF"},
    ]
    monkeypatch.setattr(crawl_router, "get_scheduler", lambda: stub_scheduler)

    response = await async_client.get("/notices", params={"source": "KDDF", "limit": 10})

    assert response.status_code == 200
    stub_scheduler.get_notices.assert_called_once_with(source="KDDF", limit=10)


@pytest.mark.asyncio
async def test_notices_empty_list(async_client: AsyncClient, monkeypatch):
    """GET /notices should return empty list when no notices exist."""
    stub_scheduler = MagicMock()
    stub_scheduler.get_notices.return_value = []
    monkeypatch.setattr(crawl_router, "get_scheduler", lambda: stub_scheduler)

    response = await async_client.get("/notices")

    assert response.status_code == 200
    assert response.json() == []


# ─── POST /analyze ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_returns_200_with_mocked_llm(async_client: AsyncClient, monkeypatch):
    """POST /analyze should return a structured AnalyzeResponse when LLM is mocked."""
    from models import RFPDocument, AnalysisResult, FitGrade

    # Mock crawler.parse_text
    mock_rfp = RFPDocument(
        id="test-rfp-001",
        title="AI Bio Grant 2024",
        source="KDDF",
        body_text="Government funding for AI-driven drug discovery.",
        keywords=["AI", "drug discovery", "bio"],
    )

    mock_crawler = MagicMock()
    mock_crawler.parse_text = AsyncMock(return_value=mock_rfp)
    monkeypatch.setattr(rfp_router, "get_crawler", lambda: mock_crawler)

    # Mock analyzer.analyze
    mock_result = AnalysisResult(
        fit_score=85,
        fit_grade=FitGrade.A,
        match_summary=[
            "Strong AI capabilities match",
            "TRL level is appropriate",
            "Company size eligible",
        ],
        required_docs=["Business plan"],
        risk_flags=["Budget constraints"],
        recommended_actions=["Prepare partnership letter"],
    )

    mock_analyzer = MagicMock()
    mock_analyzer.analyze = AsyncMock(return_value=mock_result)
    monkeypatch.setattr(rfp_router, "get_analyzer", lambda: mock_analyzer)

    payload = {
        "rfp_text": "2024 BioHealth Innovation R&D funding announcement...",
        "rfp_url": "https://example.com/rfp/001",
        "user_profile": {
            "company_name": "Test Biotech",
            "tech_keywords": ["AI", "antibody", "drug discovery"],
            "tech_description": "AI-powered antibody drug development company",
            "company_size": "SME",
            "current_trl": "TRL 4",
        },
    }

    response = await async_client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "rfp" in data
    assert "result" in data
    assert data["rfp"]["title"] == "AI Bio Grant 2024"
    assert data["result"]["fit_score"] == 85
    assert data["result"]["fit_grade"] == "A"
    assert len(data["result"]["match_summary"]) == 3


@pytest.mark.asyncio
async def test_analyze_returns_500_on_llm_failure(async_client: AsyncClient, monkeypatch):
    """POST /analyze should return 500 if the LLM analysis raises."""
    mock_crawler = MagicMock()
    mock_crawler.parse_text = AsyncMock(side_effect=RuntimeError("LLM quota exceeded"))
    monkeypatch.setattr(rfp_router, "get_crawler", lambda: mock_crawler)

    payload = {
        "rfp_text": "Some RFP text",
        "user_profile": {
            "company_name": "Test",
            "tech_keywords": ["AI"],
            "tech_description": "Test company",
        },
    }

    response = await async_client.post("/analyze", json=payload)

    assert response.status_code == 500
    assert "LLM quota exceeded" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_returns_422_on_missing_fields(async_client: AsyncClient):
    """POST /analyze should return 422 when required fields are missing."""
    response = await async_client.post("/analyze", json={"rfp_text": "hello"})

    assert response.status_code == 422


# ─── GET / (root) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_root_returns_service_info(async_client: AsyncClient):
    """GET / should return basic service metadata."""
    response = await async_client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "BioLinker"
    assert "version" in data
    assert "features" in data


# ─── GET /match/rfp ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_match_rfp_returns_results(async_client: AsyncClient, monkeypatch):
    """GET /match/rfp should return vector search results."""
    mock_results = [
        {"document": {"id": "rfp-1", "title": "Grant A"}, "score": 0.92},
    ]

    stub_vector_store = MagicMock()
    stub_vector_store.search_similar.return_value = mock_results
    stub_vector_store.count.return_value = 10
    monkeypatch.setattr(app_main, "get_vector_store", lambda: stub_vector_store)
    monkeypatch.setattr(rfp_router, "get_vector_store", lambda: stub_vector_store)

    response = await async_client.get("/match/rfp", params={"query": "AI drug discovery"})

    assert response.status_code == 200
    stub_vector_store.search_similar.assert_called_once_with(
        "AI drug discovery", n_results=5
    )


@pytest.mark.asyncio
async def test_match_rfp_requires_query(async_client: AsyncClient):
    """GET /match/rfp without query param should return 422."""
    response = await async_client.get("/match/rfp")

    assert response.status_code == 422
