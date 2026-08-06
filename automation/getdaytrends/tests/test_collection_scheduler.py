"""서버측 수집 스케줄러 계약.

수집이 브라우저 탭에 묶여 있어 2026-08-06 관측이 두 시간분에 그쳤다. 서버가 이어받되
가동 시간대·주기·일일 상한·중복 회피 네 겹으로 묶는 것이 이 모듈의 존재 이유다.
그 네 겹의 경계를 시계를 기다리지 않고 여기서 고정한다.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collection_scheduler import (  # noqa: E402
    CollectionScheduler,
    Lane,
    SchedulerConfig,
    decide,
)

KST = timezone(timedelta(hours=9))
CONFIG = SchedulerConfig(
    enabled=True,
    interval_seconds=300,
    active_start_hour=9,
    active_end_hour=24,
    daily_call_cap=200,
    tz_offset_hours=9,
)


def at_kst(hour: int, minute: int = 0, day: int = 6) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=KST).astimezone(timezone.utc)


def ago(now: datetime, **delta) -> str:
    return (now - timedelta(**delta)).isoformat()


class TestActiveHours:
    def test_collects_during_active_hours(self):
        now = at_kst(14)
        assert decide(now_utc=now, last_refreshed_at=ago(now, minutes=10), calls_today=0, config=CONFIG).collect

    def test_skips_before_start_hour(self):
        now = at_kst(8, 59)
        result = decide(now_utc=now, last_refreshed_at=ago(now, hours=6), calls_today=0, config=CONFIG)
        assert not result.collect
        assert result.reason == "outside_active_hours"

    def test_starts_exactly_at_start_hour(self):
        now = at_kst(9, 0)
        assert decide(now_utc=now, last_refreshed_at=ago(now, hours=6), calls_today=0, config=CONFIG).collect

    def test_stops_after_midnight(self):
        # 00~09시는 쉰다. 새벽 내내 외부 요청을 보내지 않기 위한 규칙이다.
        now = at_kst(2)
        assert not decide(now_utc=now, last_refreshed_at=ago(now, hours=3), calls_today=0, config=CONFIG).collect

    def test_last_active_hour_is_23(self):
        assert decide(now_utc=at_kst(23, 59), last_refreshed_at=None, calls_today=0, config=CONFIG).collect

    def test_wrap_around_window_covers_midnight(self):
        # 08~02시처럼 자정을 넘기는 설정도 지원한다.
        wrap = SchedulerConfig(active_start_hour=8, active_end_hour=2, tz_offset_hours=9)
        assert wrap.is_active_hour(at_kst(23))
        assert wrap.is_active_hour(at_kst(1))
        assert not wrap.is_active_hour(at_kst(3))
        assert not wrap.is_active_hour(at_kst(7))

    def test_equal_hours_means_always_on(self):
        always = SchedulerConfig(active_start_hour=0, active_end_hour=0, tz_offset_hours=9)
        assert always.is_active_hour(at_kst(4))

    def test_uses_local_timezone_not_utc(self):
        # UTC 03시는 KST 12시다. UTC로 판단하면 한낮에 쉬어 버린다.
        noon_kst = datetime(2026, 8, 6, 3, 0, tzinfo=timezone.utc)
        assert CONFIG.is_active_hour(noon_kst)


class TestIntervalAndDuplication:
    def test_skips_when_recently_refreshed_by_browser(self):
        # 탭이 열려 있어 2분 전에 갱신됐다면 서버가 요청을 보태지 않는다.
        now = at_kst(14)
        result = decide(now_utc=now, last_refreshed_at=ago(now, minutes=2), calls_today=0, config=CONFIG)
        assert not result.collect
        assert result.reason == "recently_refreshed"

    def test_collects_once_interval_elapsed(self):
        now = at_kst(14)
        result = decide(now_utc=now, last_refreshed_at=ago(now, seconds=300), calls_today=0, config=CONFIG)
        assert result.collect
        assert result.reason == "due"

    def test_interval_boundary_is_inclusive(self):
        now = at_kst(14)
        assert decide(now_utc=now, last_refreshed_at=ago(now, seconds=299), calls_today=0, config=CONFIG).reason == "recently_refreshed"

    def test_never_collected_runs_immediately(self):
        now = at_kst(14)
        result = decide(now_utc=now, last_refreshed_at=None, calls_today=0, config=CONFIG)
        assert result.collect
        assert result.reason == "never_collected"

    def test_future_timestamp_does_not_freeze_collection(self):
        # 시계가 어긋나 미래 시각이 찍히면 영영 쉬어 버릴 수 있다.
        now = at_kst(14)
        result = decide(now_utc=now, last_refreshed_at=(now + timedelta(hours=1)).isoformat(), calls_today=0, config=CONFIG)
        assert result.collect
        assert result.reason == "clock_skew"


class TestDailyCap:
    def test_stops_at_cap(self):
        now = at_kst(14)
        result = decide(now_utc=now, last_refreshed_at=ago(now, hours=1), calls_today=200, config=CONFIG)
        assert not result.collect
        assert result.reason == "cap_reached"

    def test_one_below_cap_still_collects(self):
        now = at_kst(14)
        assert decide(now_utc=now, last_refreshed_at=ago(now, hours=1), calls_today=199, config=CONFIG).collect

    def test_cap_covers_a_full_active_day(self):
        # 09~24시를 5분 주기로 채워도 상한에 닿지 않아야 한다(15시간 × 12회 = 180).
        active_hours = CONFIG.active_end_hour - CONFIG.active_start_hour
        max_calls = active_hours * (3600 // CONFIG.interval_seconds)
        assert max_calls < CONFIG.daily_call_cap


class TestDisabled:
    def test_disabled_config_never_collects(self):
        off = SchedulerConfig(enabled=False)
        assert not decide(now_utc=at_kst(14), last_refreshed_at=None, calls_today=0, config=off).collect

    def test_disabled_scheduler_does_not_start(self):
        lane = Lane("x_radar", lambda: {}, _never_called)
        scheduler = CollectionScheduler([lane], SchedulerConfig(enabled=False))
        scheduler.start()
        assert scheduler.status()["running"] is False

    def test_env_switch_turns_it_off(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_ENABLED", "false")
        assert SchedulerConfig.from_env().enabled is False
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_ENABLED", "1")
        assert SchedulerConfig.from_env().enabled is True

    def test_env_interval_has_a_floor(self, monkeypatch):
        # 실수로 1초를 넣어도 외부 사이트를 두드리지 않게 바닥을 둔다.
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_INTERVAL_SECONDS", "1")
        assert SchedulerConfig.from_env().interval_seconds == 60

    def test_env_garbage_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_DAILY_CAP", "많이")
        assert SchedulerConfig.from_env().daily_call_cap == 200


async def _never_called():  # pragma: no cover - 호출되면 테스트가 실패해야 한다
    raise AssertionError("수집이 일어나서는 안 되는 상황에서 refresh가 불렸다")


class TestTick:
    @pytest.mark.asyncio
    async def test_tick_refreshes_stale_lane_only(self):
        now = at_kst(14)
        calls: list[str] = []

        async def refresh_stale():
            calls.append("stale")

        stale = Lane("stale", lambda: {"refreshed_at": ago(now, hours=2)}, refresh_stale)
        fresh = Lane("fresh", lambda: {"refreshed_at": ago(now, seconds=30)}, _never_called)
        scheduler = CollectionScheduler([stale, fresh], CONFIG, clock=lambda: now)

        reasons = await scheduler.tick()

        assert calls == ["stale"]
        assert reasons == {"stale": "due", "fresh": "recently_refreshed"}
        assert scheduler.status()["lanes"]["stale"]["calls_today"] == 1
        assert scheduler.status()["lanes"]["fresh"]["calls_today"] == 0

    @pytest.mark.asyncio
    async def test_collection_failure_does_not_stop_other_lanes(self):
        now = at_kst(14)
        collected: list[str] = []

        async def boom():
            raise RuntimeError("공개 X 응답 없음")

        async def ok():
            collected.append("second")

        failing = Lane("first", lambda: {"refreshed_at": None}, boom)
        working = Lane("second", lambda: {"refreshed_at": None}, ok)
        scheduler = CollectionScheduler([failing, working], CONFIG, clock=lambda: now)

        reasons = await scheduler.tick()

        assert collected == ["second"]
        assert reasons["first"] == "error"
        status = scheduler.status()["lanes"]["first"]
        assert "공개 X 응답 없음" in status["last_error"]
        assert status["consecutive_errors"] == 1

    @pytest.mark.asyncio
    async def test_snapshot_failure_is_treated_as_never_collected(self):
        now = at_kst(14)
        calls: list[str] = []

        def broken_snapshot():
            raise OSError("스냅샷 파일 손상")

        async def refresh():
            calls.append("x")

        scheduler = CollectionScheduler([Lane("x", broken_snapshot, refresh)], CONFIG, clock=lambda: now)
        await scheduler.tick()
        assert calls == ["x"]

    @pytest.mark.asyncio
    async def test_daily_counter_resets_after_midnight(self):
        moment = {"now": at_kst(23, 50)}

        async def refresh():
            pass

        lane = Lane("x", lambda: {"refreshed_at": None}, refresh)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: moment["now"])

        await scheduler.tick()
        assert scheduler.status()["lanes"]["x"]["calls_today"] == 1

        # 다음 날 가동 시간대로 넘어가면 카운터가 0에서 다시 센다.
        moment["now"] = at_kst(9, 5, day=7)
        await scheduler.tick()
        assert scheduler.status()["lanes"]["x"]["calls_today"] == 1

    @pytest.mark.asyncio
    async def test_cap_blocks_further_collection_within_the_day(self):
        now = at_kst(14)
        calls: list[int] = []

        async def refresh():
            calls.append(1)

        capped = SchedulerConfig(interval_seconds=300, daily_call_cap=2, active_start_hour=9, active_end_hour=24)
        lane = Lane("x", lambda: {"refreshed_at": None}, refresh)
        scheduler = CollectionScheduler([lane], capped, clock=lambda: now)

        for _ in range(4):
            await scheduler.tick()

        assert len(calls) == 2
        assert scheduler.status()["lanes"]["x"]["last_reason"] == "cap_reached"


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_then_stop_is_clean(self):
        collected: list[int] = []

        async def refresh():
            collected.append(1)

        lane = Lane("x", lambda: {"refreshed_at": None}, refresh)
        # 주기를 짧게 두고 곧바로 세운다 — 첫 틱만 돌면 충분하다.
        scheduler = CollectionScheduler([lane], SchedulerConfig(interval_seconds=60, active_start_hour=0, active_end_hour=0))
        scheduler.start()
        assert scheduler.status()["running"] is True
        await asyncio.sleep(0.05)
        await scheduler.stop()

        assert scheduler.status()["running"] is False
        assert collected == [1]

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        scheduler = CollectionScheduler([], CONFIG)
        await scheduler.stop()
        assert scheduler.status()["running"] is False

    @pytest.mark.asyncio
    async def test_start_twice_keeps_one_task(self):
        scheduler = CollectionScheduler([], SchedulerConfig(active_start_hour=0, active_end_hour=0))
        scheduler.start()
        first = scheduler._task
        scheduler.start()
        assert scheduler._task is first
        await scheduler.stop()


class TestStatusRoute:
    def test_route_reports_disabled_state(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi not installed")

        import dashboard

        with TestClient(dashboard.app) as client:
            body = client.get("/api/collection-scheduler").json()

        # conftest가 테스트 중에는 스케줄러를 꺼 둔다 — 그 상태가 그대로 보여야 한다.
        assert body["enabled"] is False
        assert body["running"] is False
