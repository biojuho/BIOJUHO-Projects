"""Dashboard API smoke + regression tests.

All endpoints should return 200 and valid JSON even when
underlying DBs are empty or missing. Tests use FastAPI TestClient
with no live DB dependency — SQLite helpers gracefully return [].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure workspace root and packages are importable
WORKSPACE = Path(__file__).resolve().parents[1]
for p in (WORKSPACE, WORKSPACE / "packages", WORKSPACE / "apps"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi.testclient import TestClient

from apps.dashboard.api import app

client = TestClient(app)


# ── Endpoint existence + 200 OK ────────────────────────────────────

ENDPOINTS = [
    "/api/overview",
    "/api/getdaytrends",
    "/api/cie",
    "/api/agriguard",
    "/api/dailynews",
    "/api/ab_performance",
    "/api/costs",
    "/api/qa_reports",
    "/api/quality_overview",
    "/api/sla_status",
    "/api/mcp_health",
]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_returns_200(path: str):
    """Every registered API endpoint should return 200."""
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_returns_json(path: str):
    """Every endpoint should return valid JSON."""
    resp = client.get(path)
    data = resp.json()
    assert isinstance(data, dict), f"{path} should return a JSON object"


# ── /api/qa_reports structure ──────────────────────────────────────

class TestQaReports:

    def test_has_summary_block(self):
        data = client.get("/api/qa_reports").json()
        assert "summary" in data
        summary = data["summary"]
        for key in ("total_reports", "passed", "failed", "pass_rate", "avg_score"):
            assert key in summary, f"Missing summary key: {key}"

    def test_has_platform_stats(self):
        data = client.get("/api/qa_reports").json()
        assert "platform_stats" in data
        assert isinstance(data["platform_stats"], list)

    def test_has_daily_trend(self):
        data = client.get("/api/qa_reports").json()
        assert "daily_trend" in data
        assert isinstance(data["daily_trend"], list)

    def test_has_reports_list(self):
        data = client.get("/api/qa_reports").json()
        assert "reports" in data
        assert isinstance(data["reports"], list)

    def test_limit_param(self):
        resp = client.get("/api/qa_reports?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reports"]) <= 5

    def test_limit_capped_at_200(self):
        resp = client.get("/api/qa_reports?limit=999")
        assert resp.status_code == 200


# ── /api/quality_overview structure ────────────────────────────────

class TestQualityOverview:

    def test_has_qa_grades(self):
        data = client.get("/api/quality_overview").json()
        assert "qa_grades" in data
        assert isinstance(data["qa_grades"], list)

    def test_has_top_blocking_reasons(self):
        data = client.get("/api/quality_overview").json()
        assert "top_blocking_reasons" in data
        assert isinstance(data["top_blocking_reasons"], list)

    def test_has_lifecycle_distribution(self):
        data = client.get("/api/quality_overview").json()
        assert "lifecycle_distribution" in data

    def test_has_daily_production(self):
        data = client.get("/api/quality_overview").json()
        assert "daily_production" in data

    def test_has_confidence_distribution(self):
        data = client.get("/api/quality_overview").json()
        assert "confidence_distribution" in data


# ── /api/overview structure ────────────────────────────────────────

class TestOverview:

    def test_has_projects(self):
        data = client.get("/api/overview").json()
        assert "projects" in data
        assert "timestamp" in data

    def test_projects_contain_expected_keys(self):
        data = client.get("/api/overview").json()
        projects = data["projects"]
        for key in ("getdaytrends", "cie", "agriguard", "dailynews"):
            assert key in projects, f"Missing project key: {key}"


# ── /api/getdaytrends structure ────────────────────────────────────

class TestGetDayTrends:

    def test_has_totals(self):
        data = client.get("/api/getdaytrends").json()
        for key in ("total_runs", "total_trends", "total_tweets"):
            assert key in data

    def test_has_recent_runs(self):
        data = client.get("/api/getdaytrends").json()
        assert "recent_runs" in data
        assert isinstance(data["recent_runs"], list)


# ── /api/costs structure ───────────────────────────────────────────

class TestCosts:

    def test_returns_dict(self):
        data = client.get("/api/costs").json()
        assert isinstance(data, dict)


# ── /api/sla_status structure ──────────────────────────────────────

class TestSlaStatus:

    def test_has_sla_target(self):
        data = client.get("/api/sla_status").json()
        assert "sla_target" in data
        assert isinstance(data["sla_target"], (int, float))

    def test_has_overall_metrics(self):
        data = client.get("/api/sla_status").json()
        assert "overall_success_rate" in data
        assert "overall_sla_met" in data
        assert isinstance(data["overall_sla_met"], bool)

    def test_has_pipelines_list(self):
        data = client.get("/api/sla_status").json()
        assert "pipelines" in data
        assert isinstance(data["pipelines"], list)

    def test_pipeline_structure(self):
        """Each pipeline object should have required fields."""
        data = client.get("/api/sla_status").json()
        for p in data["pipelines"]:
            for key in ("name", "total_runs", "success_rate", "sla_met"):
                assert key in p, f"Pipeline missing key: {key}"

    def test_lookback_days(self):
        data = client.get("/api/sla_status").json()
        assert "lookback_days" in data
        assert data["lookback_days"] > 0


# ── /api/mcp_health structure ──────────────────────────────────────

class TestMcpHealth:

    def test_has_total_servers(self):
        data = client.get("/api/mcp_health").json()
        assert "total_servers" in data
        assert isinstance(data["total_servers"], int)

    def test_has_servers_list(self):
        data = client.get("/api/mcp_health").json()
        assert "servers" in data
        assert isinstance(data["servers"], list)

    def test_server_structure(self):
        data = client.get("/api/mcp_health").json()
        for s in data["servers"]:
            for key in ("name", "status", "exists"):
                assert key in s, f"Server missing key: {key}"

    def test_has_ready_count(self):
        data = client.get("/api/mcp_health").json()
        assert "ready" in data
        assert "needs_attention" in data

