"""Tests for C-3 dashboard enhancement endpoints."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_DASHBOARD_IMPORT_DEPS_OK = (
    importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
)


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


@pytest.fixture
def local_tmp_path():
    base_dir = Path.cwd() / "getdaytrends" / ".smoke-tmp" / "pytest-dashboard"
    base_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = base_dir / f"dashboard-{uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    yield tmp_dir


class TestExistingEndpoints:
    """기존 endpoint 회귀 테스트."""

    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "getdaytrends" in resp.text and "Dashboard" in resp.text
        assert "tap-dispatch-btn" in resp.text
        assert "tap-alert-list" in resp.text
        assert "tap-target-country" in resp.text
        assert "tap-alert-lifecycle" in resp.text
        assert "tap-save-preset-btn" in resp.text
        assert "tap-preset-strip" in resp.text
        assert "tap-outcome-list" in resp.text
        assert "tap-deal-room" in resp.text

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


class TestDashboardEnhancements:
    """Tests for newly added log/A-B dashboard helpers."""

    def test_logs_endpoint_falls_back_to_local_file(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        base_dir.mkdir(parents=True)
        (base_dir / "tweet_bot.log").write_text("line-1\nline-2\nline-3\n", encoding="utf-8")

        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = RuntimeError("loki unavailable")

        with patch("dashboard._config") as mock_config, patch("dashboard.httpx.AsyncClient") as mock_client_cls:
            mock_config.base_dir = base_dir
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client

            resp = client.get("/api/logs?limit=2")

        assert resp.status_code == 200
        assert resp.json() == {"logs": ["line-2", "line-3"], "source": "local"}

    def test_ab_test_endpoint_reads_dailynews_results(self, client, local_tmp_path):
        workspace_dir = local_tmp_path / "workspace"
        base_dir = workspace_dir / "getdaytrends"
        ab_dir = workspace_dir / "DailyNews" / "output"
        base_dir.mkdir(parents=True)
        ab_dir.mkdir(parents=True)
        (ab_dir / "ab_test_economy_kr_v2.json").write_text(
            """
            {
              "evaluation": {
                "version_a": {"primary_kpi": 45},
                "version_b": {"primary_kpi": 90}
              }
            }
            """,
            encoding="utf-8",
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir

            resp = client.get("/api/ab_test")

        assert resp.status_code == 200
        assert resp.json() == {
            "metrics": {
                "group_a": {"ctr": 4.5, "conversion": 1.5},
                "group_b": {"ctr": 9.0, "conversion": 3.0},
            }
        }

    def test_review_queue_endpoint_returns_snapshot(self, client):
        payload = {
            "counts": {"Ready": 1, "Approved": 1},
            "items": [{"draft_id": "draft-1", "review_status": "Ready"}],
        }
        with patch("dashboard.get_review_queue_snapshot", new_callable=AsyncMock, return_value=payload) as mock_snapshot:
            resp = client.get("/api/review_queue?limit=25")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_snapshot.assert_awaited_once()
        assert mock_snapshot.await_args.kwargs["limit"] == 25


class TestDashboardGracefulDegradation:
    """Failure-path tests for dashboard read endpoints."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/api/trends", []),
            ("/api/tweets", []),
            ("/api/runs", []),
            ("/api/trends/today", []),
            ("/api/trends/sample/tweets", []),
            ("/api/stats/categories", []),
            ("/api/watchlist", []),
        ],
    )
    def test_list_endpoints_return_empty_payload_when_db_connection_fails(self, client, path, expected):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(path)

        assert resp.status_code == 200
        assert resp.json() == expected
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-reason"] == "dependency_unavailable"

    def test_stats_endpoint_returns_zeroed_payload_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get("/api/stats")

        assert resp.status_code == 200
        assert resp.json() == {
            "total_runs": 0,
            "total_trends": 0,
            "avg_viral_score": 0,
            "total_tweets": 0,
            "llm_cost_7d": 0.0,
            "llm_daily": [],
            "_meta": {
                "degraded": True,
                "source": "api_stats",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-source"] == "api_stats"

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            (
                "/api/source/quality",
                {
                    "_meta": {
                        "degraded": True,
                        "source": "api_source_quality",
                        "unavailable_reason": "dependency_unavailable",
                    }
                },
            ),
            (
                "/api/review_queue",
                {
                    "counts": {},
                    "items": [],
                    "_meta": {
                        "degraded": True,
                        "source": "api_review_queue",
                        "unavailable_reason": "dependency_unavailable",
                    },
                },
            ),
            (
                "/api/tap/alerts",
                {
                    "counts": {},
                    "items": [],
                    "_meta": {
                        "degraded": True,
                        "source": "api_tap_alert_queue",
                        "unavailable_reason": "dependency_unavailable",
                    },
                },
            ),
        ],
    )
    def test_structured_endpoints_return_safe_fallback_when_db_connection_fails(self, client, path, expected):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(path)

        assert resp.status_code == 200
        assert resp.json() == expected
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-reason"] == "dependency_unavailable"

    def test_source_quality_endpoint_returns_empty_map_when_repository_raises(self, client):
        with patch(
            "dashboard.get_source_quality_summary",
            new_callable=AsyncMock,
            side_effect=RuntimeError("metrics query failed"),
        ):
            resp = client.get("/api/source/quality")

        assert resp.status_code == 200
        assert resp.json() == {
            "_meta": {
                "degraded": True,
                "source": "api_source_quality",
                "unavailable_reason": "dependency_unavailable",
            }
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_endpoint_returns_empty_offer_payload_when_builder_raises(self, client):
        with patch(
            "dashboard_routes_tap.build_tap_deal_room_snapshot",
            new_callable=AsyncMock,
            side_effect=RuntimeError("deal room unavailable"),
        ):
            resp = client.get(
                "/api/tap/deal-room?target_country=united-states"
                "&teaser_count=2&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "generated_at": resp.json()["generated_at"],
            "snapshot_id": "",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "teaser_count": 2,
            "total_detected": 0,
            "offers": [],
            "future_dependencies": ["stripe>=10.12.0", "jinja2>=3.1.4", "rapidfuzz>=3.9.0"],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_funnel_endpoint_returns_zero_summary_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(
                "/api/tap/deal-room/funnel"
                "?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "views": 0,
                "clicks": 0,
                "checkout_opens": 0,
                "purchases": 0,
                "revenue": 0.0,
                "ctr": 0.0,
                "checkout_rate": 0.0,
                "purchase_rate": 0.0,
                "view_to_purchase_rate": 0.0,
            },
            "items": [],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room_funnel",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_checkout_summary_endpoint_returns_zero_summary_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(
                "/api/tap/deal-room/checkouts"
                "?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "created": 0,
                "completed": 0,
                "paid": 0,
                "quoted_revenue": 0.0,
                "captured_revenue": 0.0,
                "completion_rate": 0.0,
            },
            "items": [],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room_checkouts",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"


# ── DATABASE_URL Routing Tests ──────────────────────────────────────


@pytest.mark.skipif(not _DASHBOARD_IMPORT_DEPS_OK, reason="dashboard import deps not installed")
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


class TestTapOpportunities:
    """Tests for the productized TAP feed endpoint."""

    def test_tap_endpoint_returns_board_payload(self, client):
        payload = {
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "united-states",
            "total_detected": 1,
            "teaser_count": 1,
            "items": [
                {
                    "keyword": "AI regulation",
                    "source_country": "korea",
                    "target_countries": ["united-states"],
                    "viral_score": 88,
                    "priority": 82.5,
                    "time_gap_hours": 3.0,
                    "paywall_tier": "free_teaser",
                    "public_teaser": "teaser",
                    "recommended_platforms": ["x", "threads"],
                    "recommended_angle": "angle",
                    "execution_notes": ["note"],
                    "publish_window": None,
                    "revenue_play": None,
                }
            ],
            "future_dependencies": ["rapidfuzz>=3.9.0"],
        }
        board_stub = MagicMock()
        board_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.build_tap_board_snapshot",
            new_callable=AsyncMock,
            return_value=board_stub,
        ) as mock_build:
            resp = client.get("/api/tap/opportunities?target_country=united-states&teaser_count=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["target_country"] == "united-states"
        assert data["total_detected"] == 1
        assert data["items"][0]["keyword"] == "AI regulation"
        assert data["items"][0]["paywall_tier"] == "free_teaser"
        mock_build.assert_awaited_once()

    def test_tap_latest_endpoint_returns_cached_snapshot(self, client):
        payload = {
            "snapshot_id": "tap_cached",
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "united-states",
            "total_detected": 1,
            "teaser_count": 1,
            "items": [],
            "snapshot_source": "dashboard_api",
            "delivery_mode": "cached",
            "future_dependencies": [],
        }
        board_stub = MagicMock()
        board_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.get_latest_tap_board_snapshot",
            new_callable=AsyncMock,
            return_value=board_stub,
        ) as mock_latest:
            resp = client.get("/api/tap/opportunities/latest?target_country=united-states&teaser_count=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot_id"] == "tap_cached"
        assert data["delivery_mode"] == "cached"
        mock_latest.assert_awaited_once()

    def test_tap_alert_queue_endpoint_returns_snapshot(self, client):
        payload = {
            "counts": {"queued": 2},
            "items": [
                {
                    "alert_id": "tapa_1",
                    "keyword": "AI regulation",
                    "target_country": "united-states",
                }
            ],
        }

        with patch(
            "dashboard_routes_tap.get_tap_alert_queue_snapshot",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_queue:
            resp = client.get("/api/tap/alerts?limit=10&lifecycle_status=queued&target_country=united-states")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_queue.assert_awaited_once()
        assert mock_queue.await_args.kwargs["target_country"] == "united-states"

    def test_tap_alert_dispatch_endpoint_returns_summary(self, client):
        payload = {
            "target_country": "united-states",
            "dry_run": False,
            "channels": ["telegram"],
            "attempted": 1,
            "dispatched": 1,
            "failed": 0,
            "skipped": 0,
            "items": [{"alert_id": "tapa_1", "status": "dispatched"}],
        }
        summary_stub = MagicMock()
        summary_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.dispatch_tap_alert_queue",
            new_callable=AsyncMock,
            return_value=summary_stub,
        ) as mock_dispatch:
            resp = client.post("/api/tap/alerts/dispatch?limit=5&target_country=united-states")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_dispatch.assert_awaited_once()
        assert mock_dispatch.await_args.kwargs["target_country"] == "united-states"

    def test_tap_deal_room_endpoint_returns_offer_payload(self, client):
        payload = {
            "generated_at": "2026-04-06T00:00:00",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "teaser_count": 2,
            "total_detected": 3,
            "offers": [
                {
                    "keyword": "AI regulation",
                    "tier": "teaser",
                    "teaser_headline": "headline",
                    "teaser_body": "body",
                    "premium_title": "AI regulation premium alert bundle",
                    "price_anchor": "$99",
                    "cta_label": "Unlock premium playbook",
                    "checkout_handle": "",
                    "bundle_outline": ["outline"],
                    "sponsor_fit": ["creator"],
                    "locked_sections": ["publish_window"],
                    "execution_deadline_minutes": 90,
                }
            ],
            "future_dependencies": ["stripe>=10.12.0"],
        }
        room_stub = MagicMock()
        room_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.build_tap_deal_room_snapshot",
            new_callable=AsyncMock,
            return_value=room_stub,
        ) as mock_room:
            resp = client.get(
                "/api/tap/deal-room?target_country=united-states"
                "&audience_segment=creator&include_checkout=true"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_room.assert_awaited_once()
        request = mock_room.await_args.args[2]
        assert request.target_country == "united-states"
        assert request.include_checkout is True

    def test_tap_deal_room_event_endpoint_tracks_event(self, client):
        with patch(
            "dashboard_routes_tap.record_tap_deal_room_event",
            new_callable=AsyncMock,
            return_value="tapde_1",
        ) as mock_record:
            resp = client.post(
                "/api/tap/deal-room/events"
                "?keyword=AI%20regulation"
                "&event_type=view"
                "&target_country=united-states"
                "&session_id=session-1"
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "event_id": "tapde_1"}
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["keyword"] == "AI regulation"
        assert mock_record.await_args.kwargs["event_type"] == "view"
        assert mock_record.await_args.kwargs["target_country"] == "united-states"

    def test_tap_deal_room_event_endpoint_rejects_blank_keyword(self, client):
        with patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=%20%20%20&event_type=view")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "keyword is required"}
        mock_record.assert_not_awaited()

    def test_tap_deal_room_event_endpoint_rejects_unsupported_event_type(self, client):
        with patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=AI%20regulation&event_type=share")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "unsupported deal-room event_type: share"}
        mock_record.assert_not_awaited()

    def test_tap_deal_room_event_endpoint_translates_repository_value_error(self, client):
        with patch(
            "dashboard_routes_tap.record_tap_deal_room_event",
            new_callable=AsyncMock,
            side_effect=ValueError("keyword is required"),
        ) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=AI%20regulation&event_type=view")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "keyword is required"}
        mock_record.assert_awaited_once()

    def test_tap_deal_room_funnel_endpoint_returns_summary(self, client):
        payload = {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "views": 12,
                "clicks": 4,
                "checkout_opens": 3,
                "purchases": 1,
                "revenue": 99.0,
                "ctr": 0.3333,
                "checkout_rate": 0.75,
                "purchase_rate": 0.25,
                "view_to_purchase_rate": 0.0833,
            },
            "items": [],
        }
        with patch(
            "dashboard_routes_tap.get_tap_deal_room_funnel",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_funnel:
            resp = client.get(
                "/api/tap/deal-room/funnel"
                "?days=30&target_country=united-states"
                "&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_funnel.assert_awaited_once()
        assert mock_funnel.await_args.kwargs["target_country"] == "united-states"
        assert mock_funnel.await_args.kwargs["audience_segment"] == "creator"

    def test_tap_deal_room_checkout_summary_endpoint_returns_payload(self, client):
        payload = {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "created": 4,
                "completed": 2,
                "paid": 2,
                "quoted_revenue": 198.0,
                "captured_revenue": 198.0,
                "completion_rate": 0.5,
            },
            "items": [],
        }
        with patch(
            "dashboard_routes_tap.get_tap_checkout_session_summary",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_summary:
            resp = client.get(
                "/api/tap/deal-room/checkouts"
                "?days=30&target_country=united-states&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_summary.assert_awaited_once()
        assert mock_summary.await_args.kwargs["target_country"] == "united-states"

    def test_tap_deal_room_checkout_endpoint_creates_session(self, client):
        payload = {
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "premium_title": "AI regulation premium alert bundle",
            "teaser_body": "body",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "currency": "usd",
            "actor_id": "dashboard-session-1",
        }
        session_payload = {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"}

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._create_stripe_checkout_session", return_value=session_payload) as mock_checkout, \
             patch("dashboard_routes_tap.upsert_tap_checkout_session", new_callable=AsyncMock) as mock_upsert, \
             patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "provider": "stripe",
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "tracking_status": "tracked",
        }
        mock_checkout.assert_called_once()
        assert mock_checkout.call_args.kwargs["unit_amount"] == 9900
        mock_upsert.assert_awaited_once()
        assert mock_upsert.await_args.kwargs["checkout_session_id"] == "cs_test_123"
        assert mock_upsert.await_args.kwargs["session_status"] == "created"
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["event_type"] == "checkout_open"
        assert mock_record.await_args.kwargs["session_id"] == "cs_test_123"

    def test_tap_deal_room_checkout_endpoint_rejects_invalid_handle(self, client):
        resp = client.post(
            "/api/tap/deal-room/checkout",
            json={
                "keyword": "AI regulation",
                "price_anchor": "$99",
                "checkout_handle": "email:premium_alert_bundle:united-states:AI regulation",
            },
        )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "Unsupported checkout handle"}

    def test_tap_deal_room_checkout_endpoint_rejects_keyword_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:Different topic",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle keyword mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_target_country_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "target_country": "canada",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle target_country mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_package_tier_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "package_tier": "single_alert",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle package_tier mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_malformed_stripe_response(self, client):
        payload = {
            "keyword": "AI regulation",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
        }

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._create_stripe_checkout_session", return_value={"url": "https://checkout.stripe.com/pay/cs_test_123"}):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 502
        assert resp.json() == {"ok": False, "error": "Stripe checkout session response is missing id"}

    def test_tap_deal_room_checkout_endpoint_degrades_when_tracking_persistence_fails(self, client):
        payload = {
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "premium_title": "AI regulation premium alert bundle",
            "teaser_body": "body",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "currency": "usd",
            "actor_id": "dashboard-session-1",
        }
        session_payload = {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"}

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._create_stripe_checkout_session", return_value=session_payload), \
             patch("dashboard_routes_tap.upsert_tap_checkout_session", new_callable=AsyncMock, side_effect=RuntimeError("db unavailable")), \
             patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "provider": "stripe",
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "tracking_status": "degraded",
            "tracking_warning": "Checkout was created, but tracking persistence is temporarily unavailable.",
        }
        mock_record.assert_not_awaited()

    def test_tap_deal_room_stripe_webhook_records_purchase(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "session_id": "cs_test_123",
            "actor_id": "buyer@example.com",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe"},
        }

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._construct_stripe_event", return_value={"id": "evt_123", "type": "checkout.session.completed"}), \
             patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload), \
             patch("dashboard_routes_tap.mark_tap_checkout_session_completed", new_callable=AsyncMock, return_value=True) as mock_mark, \
             patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock, return_value="evt_123") as mock_record:
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "processed": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "event_type": "purchase",
            "revenue_value": 99.0,
        }
        mock_mark.assert_awaited_once()
        assert mock_mark.await_args.kwargs["checkout_session_id"] == "cs_test_123"
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["event_id"] == "evt_123"
        assert mock_record.await_args.kwargs["event_type"] == "purchase"
        assert mock_record.await_args.kwargs["revenue_value"] == 99.0

    def test_tap_deal_room_stripe_webhook_rejects_invalid_signature(self, client):
        with patch("dashboard_routes_tap._config") as mock_config, patch(
            "dashboard_routes_tap._construct_stripe_event",
            side_effect=ValueError("Invalid Stripe webhook signature"),
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b"{}",
                headers={"Stripe-Signature": "bad_sig"},
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "Invalid Stripe webhook signature"}

    def test_tap_deal_room_stripe_webhook_ignores_missing_session_id(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "session_id": "",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe"},
        }

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._construct_stripe_event", return_value={"id": "evt_123", "type": "checkout.session.completed"}), \
             patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "ignored": True,
            "reason": "missing_session_id",
            "event_type": "purchase",
            "keyword": "AI regulation",
        }

    def test_tap_deal_room_stripe_webhook_ignores_invalid_revenue_value(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "session_id": "cs_test_123",
            "revenue_value": "not-a-number",
            "metadata": {"provider": "stripe"},
        }

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._construct_stripe_event", return_value={"id": "evt_123", "type": "checkout.session.completed"}), \
             patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "ignored": True,
            "reason": "invalid_revenue_value",
            "event_type": "purchase",
            "keyword": "AI regulation",
            "session_id": "cs_test_123",
        }

    def test_tap_deal_room_stripe_webhook_returns_retryable_error_when_persistence_fails(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "session_id": "cs_test_123",
            "actor_id": "buyer@example.com",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe", "payment_status": "paid", "currency": "usd"},
        }

        with patch("dashboard_routes_tap._config") as mock_config, \
             patch("dashboard_routes_tap._construct_stripe_event", return_value={"id": "evt_123", "type": "checkout.session.completed"}), \
             patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload), \
             patch("dashboard_routes_tap.mark_tap_checkout_session_completed", new_callable=AsyncMock, side_effect=RuntimeError("db unavailable")), \
             patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 503
        assert resp.json() == {
            "ok": False,
            "error": "Webhook persistence unavailable",
            "retryable": True,
            "event_id": "evt_123",
            "session_id": "cs_test_123",
        }
        mock_record.assert_not_awaited()

