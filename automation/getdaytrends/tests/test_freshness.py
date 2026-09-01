"""수집 신선도 판정 계약.

2026-08-06에 수집이 세 시간 넘게 멈춰 있었는데도 화면은 라이브로 보였다.
등급 경계와 파싱 관용도를 여기서 고정한다.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from freshness import (
    LANE_THRESHOLDS,
    attach_freshness,
    describe_freshness,
    describe_lane,
    humanize_age,
)

NOW = datetime(2026, 8, 6, 14, 0, 0, tzinfo=UTC)


def _at(**delta) -> str:
    return (NOW - timedelta(**delta)).isoformat()


class TestLevels:
    def test_just_collected_is_fresh(self):
        result = describe_freshness(_at(seconds=30), warn_after=360, stale_after=900, now=NOW)
        assert result["level"] == "fresh"
        assert result["age_seconds"] == 30
        assert result["label"] == "방금"

    def test_warn_boundary_is_inclusive(self):
        # 임계 정각은 이미 경고다. 한 틱 차이로 조용히 넘어가지 않게 고정한다.
        assert describe_freshness(_at(seconds=360), warn_after=360, stale_after=900, now=NOW)["level"] == "warn"
        assert describe_freshness(_at(seconds=359), warn_after=360, stale_after=900, now=NOW)["level"] == "fresh"

    def test_stale_boundary_is_inclusive(self):
        assert describe_freshness(_at(seconds=900), warn_after=360, stale_after=900, now=NOW)["level"] == "stale"
        assert describe_freshness(_at(seconds=899), warn_after=360, stale_after=900, now=NOW)["level"] == "warn"

    def test_hours_long_gap_is_stale(self):
        # 실제로 겪은 상황: 11:20에 멈춘 채 14:00에 조회.
        result = describe_freshness(_at(hours=2, minutes=40), warn_after=360, stale_after=900, now=NOW)
        assert result["level"] == "stale"
        assert result["label"] == "2시간 전"


class TestParsing:
    def test_missing_timestamp_is_unknown(self):
        for value in (None, "", "   ", 0, [], {}):
            result = describe_freshness(value, now=NOW)
            assert result["level"] == "unknown"
            assert result["age_seconds"] is None
            assert result["label"] == "기록 없음"

    def test_unparseable_string_is_unknown(self):
        assert describe_freshness("어제쯤", now=NOW)["level"] == "unknown"

    def test_naive_timestamp_is_read_as_utc(self):
        # 수집기는 tz-aware UTC로 쓰지만 예전 파일이 섞여도 로컬로 오해하면 안 된다.
        naive = (NOW - timedelta(minutes=5)).replace(tzinfo=None).isoformat()
        assert describe_freshness(naive, now=NOW)["age_seconds"] == 300

    def test_zulu_suffix_is_accepted(self):
        zulu = (NOW - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        assert describe_freshness(zulu, now=NOW)["age_seconds"] == 300

    def test_datetime_object_is_accepted(self):
        assert describe_freshness(NOW - timedelta(minutes=5), now=NOW)["age_seconds"] == 300

    def test_other_timezone_is_normalized(self):
        kst = (NOW - timedelta(minutes=5)).astimezone(timezone(timedelta(hours=9))).isoformat()
        assert describe_freshness(kst, now=NOW)["age_seconds"] == 300

    def test_future_timestamp_is_not_reported_as_fresh(self):
        # 시계가 어긋난 것을 "방금"으로 뭉개면 원인을 영영 못 찾는다.
        result = describe_freshness((NOW + timedelta(minutes=10)).isoformat(), now=NOW)
        assert result["level"] == "unknown"
        assert result["label"] == "시각 오류"


class TestHumanize:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(0, "방금"), (59, "방금"), (60, "1분 전"), (3599, "59분 전"), (3600, "1시간 전"), (86400, "1일 전")],
    )
    def test_labels(self, seconds, expected):
        assert humanize_age(seconds) == expected


class TestLaneWiring:
    def test_lane_thresholds_cover_server_collected_lanes(self):
        assert set(LANE_THRESHOLDS) >= {"x_radar", "fast_viral", "live_reference"}
        for warn_after, stale_after in LANE_THRESHOLDS.values():
            assert 0 < warn_after < stale_after

    def test_thresholds_match_server_scheduler_cycles(self):
        # 0099 배선: x_radar 120초 · fast_viral 300초 · live_reference 1800초.
        # 임계는 회차 몇 번 놓쳐도 경고가 깜빡이지 않을 만큼 느슨해야 한다.
        assert LANE_THRESHOLDS["x_radar"] == (360, 900)
        assert LANE_THRESHOLDS["fast_viral"] == (900, 1800)
        assert LANE_THRESHOLDS["live_reference"] == (2700, 5400)

    def test_two_minute_lane_tolerates_one_missed_cycle(self):
        # 120초 주기 레인이 한 번 걸렀다고 경고가 뜨면 경고가 무뎌진다.
        assert describe_lane("x_radar", _at(seconds=150), now=NOW)["level"] == "fresh"
        assert describe_lane("x_radar", _at(minutes=20), now=NOW)["level"] == "stale"

    def test_five_minute_lane_boundaries(self):
        # 300초 주기: 한 회차(300초) 지나는 것은 fresh, 세 회차(900초)부터 경고.
        assert describe_lane("fast_viral", _at(seconds=300), now=NOW)["level"] == "fresh"
        assert describe_lane("fast_viral", _at(seconds=899), now=NOW)["level"] == "fresh"
        assert describe_lane("fast_viral", _at(seconds=900), now=NOW)["level"] == "warn"
        assert describe_lane("fast_viral", _at(seconds=1799), now=NOW)["level"] == "warn"
        assert describe_lane("fast_viral", _at(seconds=1800), now=NOW)["level"] == "stale"

    def test_live_reference_lane_boundaries(self):
        # 1800초(30분) 주기: 한 회차 놓침(3600초)은 경고, 세 회차(5400초)부터 stale.
        assert describe_lane("live_reference", _at(seconds=1800), now=NOW)["level"] == "fresh"
        assert describe_lane("live_reference", _at(seconds=2699), now=NOW)["level"] == "fresh"
        assert describe_lane("live_reference", _at(seconds=2700), now=NOW)["level"] == "warn"
        assert describe_lane("live_reference", _at(seconds=5399), now=NOW)["level"] == "warn"
        assert describe_lane("live_reference", _at(seconds=5400), now=NOW)["level"] == "stale"

    def test_unknown_lane_falls_back_to_defaults(self):
        assert describe_lane("nope", _at(seconds=30), now=NOW)["level"] == "fresh"

    def test_attach_does_not_mutate_snapshot(self):
        snapshot = {"items": [], "refreshed_at": _at(minutes=1)}
        enriched = attach_freshness(snapshot, "x_radar", now=NOW)
        assert "freshness" not in snapshot
        assert enriched["freshness"]["level"] == "fresh"
        assert enriched["items"] == []

    def test_attach_handles_empty_snapshot(self):
        assert attach_freshness({}, "x_radar", now=NOW)["freshness"]["level"] == "unknown"


def _async_returning(value):
    async def _call(*_args, **_kwargs):
        return value

    return _call


@pytest.fixture
def client():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    import dashboard

    with TestClient(dashboard.app) as test_client:
        yield test_client


class TestRouteWiring:
    """GET 스냅샷 응답에 freshness가 실제로 실리는지. 여기가 끊기면 화면은 다시 눈을 감는다."""

    @staticmethod
    def _stale_iso() -> str:
        return (datetime.now(UTC) - timedelta(hours=3)).isoformat()

    def test_x_radar_snapshot_carries_freshness(self, client):
        import dashboard_routes_x_radar

        previous = dashboard_routes_x_radar._radar
        dashboard_routes_x_radar.init_x_radar_router(
            SimpleNamespace(snapshot=lambda: {"available": True, "items": [], "refreshed_at": self._stale_iso()})
        )
        try:
            response = client.get("/api/x-radar")
        finally:
            dashboard_routes_x_radar._radar = previous

        assert response.status_code == 200
        body = response.json()
        assert body["freshness"]["level"] == "stale"
        assert body["freshness"]["label"] == "3시간 전"
        assert body["items"] == []  # 원래 필드는 그대로 남는다

    def test_fast_viral_snapshot_carries_freshness(self, client):
        import dashboard_routes_fast_viral

        previous = dashboard_routes_fast_viral._collector
        dashboard_routes_fast_viral.init_fast_viral_router(
            SimpleNamespace(snapshot=lambda: {"available": True, "items": [], "refreshed_at": self._stale_iso()})
        )
        try:
            response = client.get("/api/fast-viral")
        finally:
            dashboard_routes_fast_viral._collector = previous

        assert response.status_code == 200
        assert response.json()["freshness"]["level"] == "stale"

    def test_x_radar_refresh_response_carries_freshness(self, client):
        # 화면은 GET 스냅샷이 아니라 이 POST 응답을 렌더링한다. 여기가 비면
        # 방금 수집한 직후에도 배지가 "-"로 나온다(2026-08-06에 실제로 그랬다).
        import dashboard_routes_x_radar

        previous = dashboard_routes_x_radar._radar
        payload = {"available": True, "items": [], "refreshed_at": datetime.now(UTC).isoformat()}
        dashboard_routes_x_radar.init_x_radar_router(
            SimpleNamespace(snapshot=lambda: payload, refresh=_async_returning(payload))
        )
        try:
            response = client.post("/api/x-radar/refresh", json={"country": "korea", "limit": 10})
        finally:
            dashboard_routes_x_radar._radar = previous

        assert response.status_code == 200
        assert response.json()["freshness"]["level"] == "fresh"

    def test_fast_viral_refresh_response_carries_freshness(self, client):
        import dashboard_routes_fast_viral

        previous = dashboard_routes_fast_viral._collector
        payload = {"available": True, "items": [], "refreshed_at": datetime.now(UTC).isoformat()}
        dashboard_routes_fast_viral.init_fast_viral_router(
            SimpleNamespace(snapshot=lambda: payload, refresh=_async_returning(payload))
        )
        try:
            response = client.post("/api/fast-viral/refresh?limit=12")
        finally:
            dashboard_routes_fast_viral._collector = previous

        assert response.status_code == 200
        assert response.json()["freshness"]["level"] == "fresh"

    def test_dashboard_page_renders_freshness_ui(self, client):
        # 서버가 등급을 실어 보내도 화면이 쓰지 않으면 소용없다.
        page = client.get("/").text
        assert "function freshnessParts" in page
        assert "live-dot.is-stale" in page
        assert "수집 멈춤" in page
        # 라이브 점이 등급에 연동됐는지 — 커뮤니티·영상 큐·X 레이더·YouTube 현재 큐
        # 네 레인 모두.
        assert page.count('class="live-dot${fresh.dotClass}"') == 4

    def test_snapshot_without_timestamp_reports_unknown(self, client):
        import dashboard_routes_x_radar

        previous = dashboard_routes_x_radar._radar
        dashboard_routes_x_radar.init_x_radar_router(
            SimpleNamespace(snapshot=lambda: {"available": False, "items": [], "refreshed_at": None})
        )
        try:
            response = client.get("/api/x-radar")
        finally:
            dashboard_routes_x_radar._radar = previous

        assert response.json()["freshness"]["level"] == "unknown"

    def test_live_reference_status_carries_freshness(self, client, tmp_path):
        # 자동 폴링이 읽는 GET /live/status 에 서버 판정 신선도가 실려야
        # 화면이 자체 임의로 라이브 여부를 짐작하지 않는다.
        import dashboard_routes_reference
        from reference_library import ReferenceLibraryStore

        previous_store = dashboard_routes_reference._store
        previous_collector = dashboard_routes_reference._collector
        store = ReferenceLibraryStore(tmp_path / "freshness-live.json")
        store.set_live_status(
            {
                "items": [],
                "last_success_at": self._stale_iso(),
                # A failed attempt happened just now. Freshness must still be
                # measured from last_success_at, not this attempt timestamp.
                "refreshed_at": datetime.now(UTC).isoformat(),
                "is_stale": True,
            }
        )
        dashboard_routes_reference.init_reference_router(store, None)
        try:
            response = client.get("/api/reference-library/live/status")
        finally:
            dashboard_routes_reference._store = previous_store
            dashboard_routes_reference._collector = previous_collector

        assert response.status_code == 200
        body = response.json()
        # 30분 주기 레인의 임계(2700/5400초)에서 3시간은 확실히 stale.
        assert body["freshness"]["level"] == "stale"
        assert body["items"] == []
