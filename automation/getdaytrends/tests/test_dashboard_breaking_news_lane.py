"""Dashboard scheduler lane registration contract (0099).

독립 `breaking_news` lane은 제거됐다 — `x_radar` refresh 내부가 breaking
observer를 이미 호출하므로(내부 호출 회귀는 test_breaking_news_observation.py가
지킨다) 별도 lane은 같은 수집을 겹치게 할 뿐이다. 이 파일은 지금 배선 자체를
고정한다: 서버 소유 24시간 수집, 수동 버튼만 POST.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.asyncio
async def test_lanes_are_server_owned_and_breaking_lane_is_gone(monkeypatch):
    import dashboard

    captured_lanes = []
    real_scheduler = dashboard.CollectionScheduler

    class SchedulerProbe:
        def __init__(self, lanes):
            captured_lanes.extend(lanes)

        def start(self):
            pass

        async def stop(self):
            pass

    monkeypatch.delenv("GETDAYTRENDS_SCHEDULER_API_DAILY_CAP", raising=False)
    monkeypatch.setattr(dashboard, "CollectionScheduler", SchedulerProbe)
    monkeypatch.setattr(dashboard, "_runtime_paths", SimpleNamespace(configured=False))

    async with dashboard._lifespan(dashboard.app):
        pass

    assert [lane.name for lane in captured_lanes] == ["x_radar", "fast_viral", "creator_reference"]
    # 독립 속보 lane은 없다 — x_radar refresh가 observer를 내부에서 호출한다.
    assert "breaking_news" not in {lane.name for lane in captured_lanes}
    assert not hasattr(dashboard, "_refresh_breaking_news_lane")
    assert not hasattr(dashboard, "_breaking_news_lane_state")

    status = real_scheduler(captured_lanes).status()["lanes"]
    assert list(status) == ["x_radar", "fast_viral", "creator_reference"]
    assert {
        name: {
            "kind": status[name]["kind"],
            "active_hours": status[name]["active_hours"],
            "daily_call_cap": status[name]["daily_call_cap"],
            "interval_seconds": status[name]["interval_seconds"],
        }
        for name in ("x_radar", "fast_viral", "creator_reference")
    } == {
        # X 레이더: 24시간 120초 서버 소유 수집.
        "x_radar": {"kind": "scrape", "active_hours": "00-24", "daily_call_cap": 720, "interval_seconds": 120},
        # 커뮤니티 조기감지: 24시간 300초(전역 기본), 상한만 명시.
        "fast_viral": {"kind": "scrape", "active_hours": "00-24", "daily_call_cap": 288, "interval_seconds": 300},
        # YouTube 레퍼런스: 공개 검색 메타 scrape, 24시간 30분 보수 주기.
        "creator_reference": {
            "kind": "scrape",
            "active_hours": "00-24",
            "daily_call_cap": 48,
            "interval_seconds": 1800,
        },
    }


@pytest.mark.asyncio
async def test_creator_reference_lane_reads_live_status_and_refreshes_store(monkeypatch):
    """creator_reference lane의 스냅샷·리프레시가 실제 저장소·수집기로 배선돼야 한다."""
    import dashboard

    captured_lanes = []

    class SchedulerProbe:
        def __init__(self, lanes):
            captured_lanes.extend(lanes)

        def start(self):
            pass

        async def stop(self):
            pass

    live_status = {"refreshed_at": "2026-08-27T03:00:00+00:00", "items": []}
    refresh = AsyncMock(return_value={"collected": 2})
    monkeypatch.setattr(dashboard, "CollectionScheduler", SchedulerProbe)
    monkeypatch.setattr(dashboard, "_runtime_paths", SimpleNamespace(configured=False))
    # lane은 lifespan 안에서 스냅샷·리프레시를 바인딩하므로 그 전에 패치한다.
    monkeypatch.setattr(dashboard._reference_store, "get_live_status", lambda: live_status)
    monkeypatch.setattr(dashboard._reference_collector, "refresh", refresh)

    async with dashboard._lifespan(dashboard.app):
        pass

    lane = next(item for item in captured_lanes if item.name == "creator_reference")

    assert lane.snapshot() == live_status
    await lane.refresh()
    # 서버 자동 수집은 보수적으로 — 키워드당 3개만.
    refresh.assert_awaited_once_with(per_keyword=3)


@pytest.mark.asyncio
async def test_fast_viral_refresh_runs_video_producer_but_isolates_its_failure(monkeypatch):
    import dashboard

    fast_snapshot = {"available": True, "refreshed_at": "2026-08-27T04:20:00+09:00"}
    fast_refresh = AsyncMock(return_value=fast_snapshot)
    video_refresh = AsyncMock(side_effect=RuntimeError("synthetic producer failure"))
    monkeypatch.setattr(dashboard._fast_viral_collector, "refresh", fast_refresh)
    monkeypatch.setattr(dashboard._video_queue_producer, "refresh", video_refresh)

    result = await dashboard._refresh_fast_viral_lane()

    assert result == fast_snapshot
    fast_refresh.assert_awaited_once_with(limit=12)
    video_refresh.assert_awaited_once_with()


def test_scheduler_status_includes_video_queue_producer_state(monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "_collection_scheduler", None)
    monkeypatch.setattr(
        dashboard._video_queue_producer,
        "snapshot",
        lambda: {"last_success_at": "2026-08-27T04:20:00+09:00", "last_error": None},
    )

    status = dashboard.api_collection_scheduler()

    assert status["video_queue_producer"]["last_success_at"] == "2026-08-27T04:20:00+09:00"
    assert status["video_queue_producer"]["last_error"] is None


def test_scheduler_status_exposes_each_collectors_last_success_and_errors(monkeypatch):
    import dashboard

    class SchedulerProbe:
        def status(self):
            return {
                "enabled": True,
                "running": True,
                "lanes": {
                    "x_radar": {},
                    "fast_viral": {},
                    "creator_reference": {},
                },
            }

    monkeypatch.setattr(dashboard, "_collection_scheduler", SchedulerProbe())
    monkeypatch.setattr(
        dashboard._x_opportunity_radar,
        "snapshot",
        lambda: {
            "last_success_at": "2026-08-27T04:00:00+00:00",
            "last_attempt_at": "2026-08-27T04:02:00+00:00",
            "is_stale": True,
            "errors": ["synthetic x failure"],
            "source_health": {"google_trends": False},
        },
    )
    monkeypatch.setattr(
        dashboard._fast_viral_collector,
        "snapshot",
        lambda: {"refreshed_at": "2026-08-27T04:01:00+00:00", "errors": []},
    )
    monkeypatch.setattr(
        dashboard._reference_store,
        "get_live_status",
        lambda: {
            "last_success_at": "2026-08-27T03:30:00+00:00",
            "last_attempt_at": "2026-08-27T04:00:00+00:00",
            "is_stale": True,
            "errors": ["synthetic youtube failure"],
        },
    )

    lanes = dashboard.api_collection_scheduler()["lanes"]

    assert lanes["x_radar"]["last_success_at"] == "2026-08-27T04:00:00+00:00"
    assert lanes["x_radar"]["collector_last_attempt_at"] == "2026-08-27T04:02:00+00:00"
    assert lanes["x_radar"]["serving_last_good"] is True
    assert lanes["x_radar"]["collector_errors"] == ["synthetic x failure"]
    assert lanes["fast_viral"]["last_success_at"] == "2026-08-27T04:01:00+00:00"
    assert lanes["creator_reference"]["collector_errors"] == ["synthetic youtube failure"]
