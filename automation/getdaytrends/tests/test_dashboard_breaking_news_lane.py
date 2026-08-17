"""Dashboard registration contract for the independent breaking-news lane."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.asyncio
async def test_dashboard_keeps_scrape_lanes_and_adds_always_on_api_lane(monkeypatch):
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

    status = real_scheduler(captured_lanes).status()["lanes"]
    assert list(status) == ["x_radar", "fast_viral", "breaking_news"]
    assert {
        name: {
            "kind": status[name]["kind"],
            "active_hours": status[name]["active_hours"],
            "daily_call_cap": status[name]["daily_call_cap"],
        }
        for name in ("x_radar", "fast_viral")
    } == {
        "x_radar": {"kind": "scrape", "active_hours": "09-24", "daily_call_cap": 100},
        "fast_viral": {"kind": "scrape", "active_hours": "09-24", "daily_call_cap": 100},
    }
    assert status["breaking_news"]["kind"] == "api"
    assert status["breaking_news"]["active_hours"] == "00-24"
    assert status["breaking_news"]["daily_call_cap"] == 300


@pytest.mark.asyncio
async def test_breaking_news_lane_calls_observer_and_persists_observed_at(monkeypatch):
    import dashboard

    observed_at = "2026-08-16T00:05:00+00:00"
    observer = SimpleNamespace(
        observe=AsyncMock(
            return_value={
                "enabled": True,
                "available": True,
                "observed_at": observed_at,
                "product_candidates": [],
            }
        )
    )
    monkeypatch.setattr(dashboard._x_opportunity_radar, "breaking_news_observer", observer)
    monkeypatch.setattr(
        dashboard._x_opportunity_radar,
        "snapshot",
        lambda: {
            "items": [
                {"keyword": "반도체 수출", "lane": "동시 폭발"},
                {"keyword": "기상특보", "lane": "속보·공적발표"},
            ],
            "breaking_news_observation": {},
        },
    )
    monkeypatch.setattr(dashboard, "_breaking_news_lane_state", {"refreshed_at": None})

    result = await dashboard._refresh_breaking_news_lane()

    observer.observe.assert_awaited_once_with(("반도체 수출",))
    assert result["refreshed_at"] == observed_at
    assert dashboard._breaking_news_lane_snapshot()["refreshed_at"] == observed_at
