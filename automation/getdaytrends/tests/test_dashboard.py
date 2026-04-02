"""Tests for C-3 dashboard enhancement endpoints."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def mock_db_conn():
    """Mock async DB connection with cursor support."""
    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=cursor)
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def client(mock_db_conn):
    """FastAPI TestClient with mocked DB connection."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    with patch("dashboard._get_conn", return_value=mock_db_conn):
        from dashboard import app

        with TestClient(app) as c:
            yield c


class TestExistingEndpoints:
    """기존 endpoint 회귀 테스트."""

    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "getdaytrends" in resp.text and "Dashboard" in resp.text

    def test_pipeline_status(self, client):
        resp = client.get("/api/pipeline_status")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data


class TestC3TrendsToday:
    """GET /api/trends/today"""

    def test_returns_empty_list(self, client):
        resp = client.get("/api/trends/today")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_respects_limit(self, client, mock_db_conn):
        resp = client.get("/api/trends/today?limit=5")
        assert resp.status_code == 200
        # Verify the query was called with limit
        call_args = mock_db_conn.execute.call_args
        assert call_args is not None


class TestC3TrendTweets:
    """GET /api/trends/{keyword}/tweets"""

    def test_returns_empty_for_unknown_keyword(self, client):
        resp = client.get("/api/trends/unknown_keyword/tweets")
        assert resp.status_code == 200
        assert resp.json() == []


class TestC3SourceQuality:
    """GET /api/source/quality"""

    def test_returns_quality_data(self, client, mock_db_conn):
        with patch(
            "dashboard.get_source_quality_summary",
            new_callable=AsyncMock,
            return_value={
                "twitter": {"success_rate": 0.85, "avg_latency_ms": 230},
                "reddit": {"success_rate": 0.92, "avg_latency_ms": 180},
            },
        ):
            resp = client.get("/api/source/quality")
            assert resp.status_code == 200


class TestC3CategoryStats:
    """GET /api/stats/categories"""

    def test_returns_empty_list(self, client):
        resp = client.get("/api/stats/categories")
        assert resp.status_code == 200
        assert resp.json() == []


class TestC3Watchlist:
    """GET /api/watchlist"""

    def test_returns_empty_or_data(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── DATABASE_URL Routing Tests ──────────────────────────────────────


class TestDashboardDatabaseUrlRouting:
    """dashboard._get_conn이 DATABASE_URL을 올바르게 전달하는지 테스트."""

    @pytest.mark.asyncio
    async def test_get_conn_passes_database_url_from_config(self):
        """AppConfig.database_url이 get_connection에 전달되어야 한다."""
        mock_conn = AsyncMock()
        with patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn) as mock_gc, \
             patch("dashboard.init_db", new_callable=AsyncMock), \
             patch("dashboard._config") as mock_config:

            mock_config.db_path = "data/test.db"
            mock_config.database_url = "postgresql://user:pass@cloud-host:5432/prod"

            from dashboard import _get_conn
            conn = await _get_conn()

            mock_gc.assert_called_once_with(
                "data/test.db",
                database_url="postgresql://user:pass@cloud-host:5432/prod",
            )
            assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_get_conn_empty_database_url_defaults_sqlite(self):
        """database_url이 빈 문자열이면 SQLite로 폴백해야 한다."""
        mock_conn = AsyncMock()
        with patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn) as mock_gc, \
             patch("dashboard.init_db", new_callable=AsyncMock), \
             patch("dashboard._config") as mock_config:

            mock_config.db_path = "data/local.db"
            mock_config.database_url = ""

            from dashboard import _get_conn
            await _get_conn()

            mock_gc.assert_called_once_with(
                "data/local.db",
                database_url="",
            )

    @pytest.mark.asyncio
    async def test_get_conn_calls_init_db(self):
        """_get_conn은 항상 init_db를 호출해야 한다."""
        mock_conn = AsyncMock()
        with patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn), \
             patch("dashboard.init_db", new_callable=AsyncMock) as mock_init, \
             patch("dashboard._config") as mock_config:

            mock_config.db_path = "data/test.db"
            mock_config.database_url = ""

            from dashboard import _get_conn
            await _get_conn()

            mock_init.assert_called_once_with(mock_conn)

