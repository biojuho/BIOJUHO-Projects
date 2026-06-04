"""Dashboard API smoke + regression tests.

All endpoints should return 200 and valid JSON even when
underlying DBs are empty or missing. Tests use FastAPI TestClient
with no live DB dependency — SQLite helpers gracefully return [].
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure workspace root and packages are importable
WORKSPACE = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = WORKSPACE / "apps" / "dashboard"
for p in reversed((DASHBOARD_DIR, WORKSPACE, WORKSPACE / "packages", WORKSPACE / "apps")):
    path = str(p)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

loaded_api = sys.modules.get("api")
dashboard_api = (DASHBOARD_DIR / "api.py").resolve()
loaded_api_file = getattr(loaded_api, "__file__", None) if loaded_api else None
if loaded_api_file and Path(loaded_api_file).resolve() != dashboard_api:
    sys.modules.pop("api", None)

from api import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from routers import gdt as gdt_router  # noqa: E402

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

    def test_includes_workspace_smoke_slowest_checks(self, tmp_path, monkeypatch):
        smoke_dir = tmp_path / "var"
        smoke_dir.mkdir()
        smoke_report = smoke_dir / "workspace-smoke-cie.json"
        smoke_report.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "duration_seconds": 12.345,
                    "summary": {"total": 2, "completed": 2, "passed": 2, "failed": 0, "remaining": 0},
                    "scope_summary": {
                        "cie": {"completed": 2, "passed": 2, "failed": 0, "elapsed_seconds": 12.3}
                    },
                    "mcp_trace": {
                        "enabled": True,
                        "completed": 1,
                        "passed": 1,
                        "failed": 0,
                        "elapsed_seconds": 3.2,
                        "checked_units": ["automation/DailyNews"],
                        "command_kinds": {"pytest": 1},
                        "checks": [
                            {
                                "name": "DailyNews unit tests",
                                "cwd": "automation/DailyNews",
                                "ok": True,
                                "returncode": 0,
                                "elapsed_seconds": 3.2,
                                "command_kind": "pytest",
                            }
                        ],
                    },
                    "results": [
                        {"scope": "cie", "name": "cie compile", "ok": True, "returncode": 0, "elapsed_seconds": 0.5},
                        {"scope": "cie", "name": "cie tests", "ok": True, "returncode": 0, "elapsed_seconds": 11.8},
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(gdt_router, "WORKSPACE", tmp_path)

        data = client.get("/api/quality_overview").json()
        smoke = data["workspace_smoke"]

        assert smoke["available"] is True
        assert smoke["status"] == "complete"
        assert smoke["summary"]["passed"] == 2
        assert smoke["scope_summary"]["cie"]["completed"] == 2
        assert smoke["mcp_trace"]["enabled"] is True
        assert smoke["mcp_trace"]["command_kinds"] == {"pytest": 1}
        assert smoke["duration_seconds"] == 12.345
        assert smoke["slowest_checks"][0]["name"] == "cie tests"

    def test_uses_latest_enabled_mcp_trace_when_latest_smoke_is_workspace_only(self, tmp_path, monkeypatch):
        smoke_dir = tmp_path / "var"
        smoke_dir.mkdir()
        mcp_report = smoke_dir / "workspace-smoke-mcp.json"
        workspace_report = smoke_dir / "workspace-smoke-workspace.json"
        mcp_report.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "duration_seconds": 8.4,
                    "summary": {"total": 1, "completed": 1, "passed": 1, "failed": 0, "remaining": 0},
                    "mcp_trace": {
                        "enabled": True,
                        "completed": 1,
                        "passed": 1,
                        "failed": 0,
                        "elapsed_seconds": 8.4,
                        "checked_units": ["automation/DailyNews"],
                        "command_kinds": {"pytest": 1},
                        "checks": [],
                    },
                    "results": [],
                }
            ),
            encoding="utf-8",
        )
        workspace_report.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "duration_seconds": 2.0,
                    "summary": {"total": 1, "completed": 1, "passed": 1, "failed": 0, "remaining": 0},
                    "mcp_trace": {"enabled": False},
                    "results": [],
                }
            ),
            encoding="utf-8",
        )
        os.utime(mcp_report, (100, 100))
        os.utime(workspace_report, (200, 200))
        monkeypatch.setattr(gdt_router, "WORKSPACE", tmp_path)

        smoke = client.get("/api/quality_overview").json()["workspace_smoke"]

        assert smoke["path"] == "var/workspace-smoke-workspace.json"
        assert smoke["mcp_trace_path"] == "var/workspace-smoke-mcp.json"
        assert smoke["mcp_trace"]["enabled"] is True
        assert smoke["mcp_trace"]["command_kinds"] == {"pytest": 1}

    def test_includes_dev_server_readiness_summary(self, tmp_path, monkeypatch):
        status_dir = tmp_path / "var"
        status_dir.mkdir()
        status_report = status_dir / "dev-server-status-dashboard.json"
        status_report.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "degraded",
                    "summary": {"total": 2, "ready": 1, "unready": 1},
                    "targets": [
                        {
                            "id": "dashboard-api",
                            "label": "Dashboard API",
                            "project": "dashboard",
                            "kind": "api",
                            "ok": True,
                            "status_code": 200,
                            "url": "http://127.0.0.1:8080/api/quality_overview",
                        },
                        {
                            "id": "dashboard-frontend",
                            "label": "Dashboard Frontend",
                            "project": "dashboard",
                            "kind": "frontend",
                            "ok": False,
                            "status_code": None,
                            "url": "http://127.0.0.1:5173/",
                            "error": "offline",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(gdt_router, "WORKSPACE", tmp_path)

        data = client.get("/api/quality_overview").json()
        dev_status = data["dev_server_status"]

        assert dev_status["available"] is True
        assert dev_status["status"] == "degraded"
        assert dev_status["summary"] == {"total": 2, "ready": 1, "unready": 1}
        assert dev_status["unready_targets"][0]["id"] == "dashboard-frontend"

    def test_includes_external_credential_boundary_summary(self, tmp_path, monkeypatch):
        report_dir = tmp_path / "docs" / "reports" / "2026-06"
        report_dir.mkdir(parents=True)
        report = report_dir / "EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json"
        report.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "generated_at": "2026-06-05T00:00:00+00:00",
                    "registry_generated_at": "2026-06-05T03:04:31+09:00",
                    "boundary_count": 2,
                    "missing_required_env_count": 3,
                    "missing_required_env": ["CANVA_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN"],
                    "status_counts": {"external_auth_blocked": 1, "credential_gated": 1},
                    "boundaries": [
                        {
                            "id": "hosted_agent_runtime_credentials",
                            "title": "Hosted agent runtime and tracing credentials",
                            "status": "future_scoped",
                            "owner": "operator",
                            "missing_required_env": [],
                            "optional_env_available": False,
                            "evidence_count": 1,
                        },
                        {
                            "id": "canva_oauth_and_openapi_tool_execution",
                            "title": "Canva OAuth and OpenAPI tool execution",
                            "status": "external_auth_blocked",
                            "owner": "operator",
                            "missing_required_env": ["CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET"],
                            "optional_env_available": False,
                            "evidence_count": 2,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        live_report = report_dir / "EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json"
        live_report.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "summary": {
                        "next_unblock": {
                            "boundary_id": "canva_oauth_and_openapi_tool_execution",
                            "env_names": ["CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET"],
                            "live_status": "blocked_missing_required_env",
                            "plan_rank": 1,
                            "verification_commands": [
                                "cd mcp/canva-mcp && npm run doctor:canva",
                                "cd mcp/canva-mcp && npm run auth:canva",
                            ],
                        }
                    },
                    "boundaries": [
                        {
                            "id": "canva_oauth_and_openapi_tool_execution",
                            "title": "Canva OAuth and OpenAPI tool execution",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(gdt_router, "WORKSPACE", tmp_path)

        data = client.get("/api/quality_overview").json()
        boundaries = data["credential_boundaries"]

        assert boundaries["available"] is True
        assert boundaries["status"] == "pass"
        assert boundaries["boundary_count"] == 2
        assert boundaries["missing_required_env_count"] == 3
        assert boundaries["boundaries"][0]["id"] == "canva_oauth_and_openapi_tool_execution"
        assert boundaries["boundaries"][0]["missing_required_env_count"] == 2
        next_unblock = boundaries["next_unblock"]
        assert next_unblock["boundary_id"] == "canva_oauth_and_openapi_tool_execution"
        assert next_unblock["title"] == "Canva OAuth and OpenAPI tool execution"
        assert next_unblock["plan_rank"] == 1
        assert next_unblock["live_status"] == "blocked_missing_required_env"
        assert next_unblock["env_names"] == ["CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET"]
        assert next_unblock["verification_command_count"] == 2
        assert next_unblock["first_verification_command"] == "cd mcp/canva-mcp && npm run doctor:canva"


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
