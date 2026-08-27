"""서버측 수집 스케줄러 계약.

수집이 브라우저 탭에 묶여 있어 2026-08-06 관측이 두 시간분에 그쳤다. 서버가 이어받되
가동 시간대·주기·일일 상한·중복 회피 네 겹으로 묶는 것이 이 모듈의 존재 이유다.
그 네 겹의 경계를 시계를 기다리지 않고 여기서 고정한다.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta, timezone
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
    return datetime(2026, 8, day, hour, minute, tzinfo=KST).astimezone(UTC)


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
        noon_kst = datetime(2026, 8, 6, 3, 0, tzinfo=UTC)
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

    def test_lane_interval_override_controls_duplication_window(self):
        now = at_kst(14)
        recent = decide(
            now_utc=now,
            last_refreshed_at=ago(now, seconds=119),
            calls_today=0,
            config=CONFIG,
            interval_seconds=120,
        )
        due = decide(
            now_utc=now,
            last_refreshed_at=ago(now, seconds=120),
            calls_today=0,
            config=CONFIG,
            interval_seconds=120,
        )
        assert recent.reason == "recently_refreshed"
        assert due.reason == "due"

    def test_lane_interval_override_keeps_minimum_floor(self):
        now = at_kst(14)
        result = decide(
            now_utc=now,
            last_refreshed_at=ago(now, seconds=59),
            calls_today=0,
            config=CONFIG,
            interval_seconds=1,
        )
        assert result.reason == "recently_refreshed"


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

    def test_direct_config_interval_has_the_same_floor(self):
        assert SchedulerConfig(interval_seconds=1).interval_seconds == 60

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


async def _noop():
    pass


class TestPerLaneActiveHours:
    """핸드오프 0065 — lane별 활동 시간.

    커뮤니티 lane(기본 09-24)과 L0/L1(24시간)의 경계 시각 다섯 개 판정을 고정한다.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "label, hour, minute, community_collects",
        [
            ("08:59", 8, 59, False),
            ("09:00", 9, 0, True),
            ("23:59", 23, 59, True),
            ("00:00", 0, 0, False),
            ("03:00", 3, 0, False),
        ],
    )
    async def test_boundary_times_per_lane(self, label, hour, minute, community_collects):
        now = at_kst(hour, minute)
        collected: list[str] = []

        async def refresh(name: str):
            collected.append(name)

        community = Lane(
            "x_radar",
            lambda: {"refreshed_at": ago(now, hours=6)},
            lambda: refresh("x_radar"),
        )
        breaking = Lane(
            "kma-weather",
            lambda: {"refreshed_at": ago(now, hours=6)},
            lambda: refresh("kma-weather"),
        )
        scheduler = CollectionScheduler([community, breaking], CONFIG, clock=lambda: now)

        reasons = await scheduler.tick()

        assert ("x_radar" in collected) is community_collects, label
        assert "kma-weather" in collected, label
        if community_collects:
            assert reasons["x_radar"] == "due", label
        else:
            assert reasons["x_radar"] == "outside_active_hours", label
        assert reasons["kma-weather"] == "due", label

        lanes = scheduler.status()["lanes"]
        assert lanes["x_radar"]["active_hours"] == "09-24"
        assert lanes["kma-weather"]["active_hours"] == "00-24"

    @pytest.mark.asyncio
    async def test_community_lane_keeps_current_window(self):
        # 회귀 방향: 커뮤니티 lane의 활동 시간은 현행 09-24 그대로다.
        lane = Lane("fast_viral", lambda: {}, _noop)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(3, 0))

        assert scheduler.status()["lanes"]["fast_viral"]["active_hours"] == "09-24"
        reasons = await scheduler.tick()
        assert reasons["fast_viral"] == "outside_active_hours"
        assert scheduler.status()["lanes"]["fast_viral"]["calls_today"] == 0

    @pytest.mark.asyncio
    async def test_lane_field_override_wins(self):
        lane = Lane("x_radar", lambda: {}, _noop, active_start_hour=0, active_end_hour=0)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(3, 0))

        assert scheduler.status()["lanes"]["x_radar"]["active_hours"] == "00-24"
        assert (await scheduler.tick())["x_radar"] == "never_collected"

    @pytest.mark.asyncio
    async def test_env_override_per_lane(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_START_HOUR", "0")
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_END_HOUR", "0")
        lane = Lane("x_radar", lambda: {}, _noop)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(3, 0))

        assert scheduler.status()["lanes"]["x_radar"]["active_hours"] == "00-24"
        assert (await scheduler.tick())["x_radar"] == "never_collected"

    @pytest.mark.asyncio
    async def test_env_garbage_falls_back_to_lane_default(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_START_HOUR", "새벽")
        lane = Lane("x_radar", lambda: {}, _noop)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(3, 0))

        assert scheduler.status()["lanes"]["x_radar"]["active_hours"] == "09-24"

    @pytest.mark.parametrize("name", ["kma-weather", "yonhap-rss", "kma_weather", "yonhap_rss"])
    def test_l0_l1_names_default_to_always_on(self, name):
        scheduler = CollectionScheduler([Lane(name, lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(3, 0))
        assert scheduler.status()["lanes"][name]["active_hours"] == "00-24"

    @pytest.mark.parametrize("name", ["x_radar", "fast_viral", "weather"])
    def test_other_names_keep_default_window(self, name):
        scheduler = CollectionScheduler([Lane(name, lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(3, 0))
        assert scheduler.status()["lanes"][name]["active_hours"] == "09-24"


class TestPerLaneIntervals:
    def test_lane_field_and_global_interval_are_reported_separately(self):
        lanes = [
            Lane("x_radar", lambda: {}, _noop, interval_seconds=120),
            Lane("creator_reference", lambda: {}, _noop, interval_seconds=900),
        ]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: at_kst(14))

        status = scheduler.status()
        assert status["interval_seconds"] == 300
        assert status["loop_interval_seconds"] == 120
        assert status["lanes"]["x_radar"]["interval_seconds"] == 120
        assert status["lanes"]["creator_reference"]["interval_seconds"] == 900

    def test_lane_interval_environment_override(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_INTERVAL_SECONDS", "180")
        scheduler = CollectionScheduler([Lane("x_radar", lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["interval_seconds"] == 180

    def test_lane_field_interval_wins_over_environment(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_INTERVAL_SECONDS", "180")
        lane = Lane("x_radar", lambda: {}, _noop, interval_seconds=120)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["interval_seconds"] == 120

    def test_lane_interval_environment_uses_floor_and_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_INTERVAL_SECONDS", "1")
        scheduler = CollectionScheduler([Lane("x_radar", lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["interval_seconds"] == 60

        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_INTERVAL_SECONDS", "빠르게")
        scheduler = CollectionScheduler([Lane("x_radar", lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["interval_seconds"] == CONFIG.interval_seconds

    @pytest.mark.asyncio
    async def test_tick_uses_each_lane_interval_for_recent_snapshot(self):
        now = at_kst(14)
        collected: list[str] = []

        async def refresh(name: str):
            collected.append(name)

        lanes = [
            Lane(
                "x_radar",
                lambda: {"refreshed_at": ago(now, seconds=90)},
                lambda: refresh("x_radar"),
                interval_seconds=120,
            ),
            Lane(
                "creator_reference",
                lambda: {"refreshed_at": ago(now, seconds=90)},
                lambda: refresh("creator_reference"),
                interval_seconds=60,
            ),
        ]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: now)

        reasons = await scheduler.tick()

        assert reasons == {"x_radar": "recently_refreshed", "creator_reference": "due"}
        assert collected == ["creator_reference"]

    @pytest.mark.asyncio
    async def test_run_sleeps_at_fastest_lane_interval(self, monkeypatch):
        scheduler = CollectionScheduler(
            [
                Lane("x_radar", lambda: {}, _noop, interval_seconds=120),
                Lane("creator_reference", lambda: {}, _noop, interval_seconds=900),
            ],
            CONFIG,
            clock=lambda: at_kst(14),
        )
        observed_timeouts: list[float] = []

        async def fake_wait_for(awaitable, timeout):
            observed_timeouts.append(timeout)
            awaitable.close()
            scheduler._stopping.set()
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        await scheduler._run()

        assert observed_timeouts == [120]

    @pytest.mark.asyncio
    async def test_run_subtracts_tick_duration_from_next_wake(self, monkeypatch):
        start = at_kst(14)
        clock_values = iter([start, start + timedelta(seconds=45)])
        scheduler = CollectionScheduler(
            [Lane("x_radar", lambda: {}, _noop, interval_seconds=120)],
            CONFIG,
            clock=lambda: next(clock_values),
        )
        observed_timeouts: list[float] = []
        # 수집에 45초를 썼으면 남은 75초만 쉰다.

        async def fake_wait_for(awaitable, timeout):
            observed_timeouts.append(timeout)
            awaitable.close()
            scheduler._stopping.set()
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        await scheduler._run()

        assert observed_timeouts == [75]

    def test_next_wake_uses_collector_completion_not_tick_start(self):
        now = at_kst(14)
        refreshed_at = now - timedelta(seconds=119.4)
        lane = Lane(
            "x_radar",
            lambda: {"refreshed_at": refreshed_at.isoformat()},
            _noop,
            interval_seconds=120,
        )
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: now)

        assert scheduler._seconds_until_next_check() == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_failed_attempt_sets_next_wake_even_when_snapshot_is_old(self):
        now = at_kst(14)

        async def fail():
            raise RuntimeError("synthetic failure")

        lane = Lane("x_radar", lambda: {"refreshed_at": ago(now, minutes=10)}, fail, interval_seconds=120)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: now)

        assert (await scheduler.tick())["x_radar"] == "error"
        # The run loop uses last_attempt_at for its wake deadline, so it will
        # not call tick again until the interval has elapsed.
        assert scheduler._seconds_until_next_check() == 120
        assert scheduler.status()["lanes"]["x_radar"]["calls_today"] == 1


class TestPerLaneDailyCap:
    """핸드오프 0065 — 전역 200을 lane별 상한으로 배분해 독식을 막는다."""

    @pytest.mark.asyncio
    async def test_default_cap_is_equal_share_of_global(self):
        lanes = [Lane("a", lambda: {}, _noop), Lane("b", lambda: {}, _noop)]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: at_kst(14))

        status = scheduler.status()["lanes"]
        assert status["a"]["daily_call_cap"] == 100
        assert status["b"]["daily_call_cap"] == 100
        assert status["a"]["daily_call_cap"] + status["b"]["daily_call_cap"] == CONFIG.daily_call_cap

    @pytest.mark.asyncio
    async def test_single_lane_keeps_global_cap(self):
        scheduler = CollectionScheduler([Lane("x", lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x"]["daily_call_cap"] == CONFIG.daily_call_cap

    @pytest.mark.asyncio
    async def test_four_lanes_split_global_cap(self):
        lanes = [Lane(f"lane{i}", lambda: {}, _noop) for i in range(4)]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: at_kst(14))

        caps = [state["daily_call_cap"] for state in scheduler.status()["lanes"].values()]
        assert caps == [50, 50, 50, 50]
        assert sum(caps) == CONFIG.daily_call_cap

    @pytest.mark.asyncio
    async def test_one_lane_cannot_monopolize_global_cap(self):
        now = at_kst(14)
        collected: dict[str, int] = {}

        async def refresh(name: str):
            collected[name] = collected.get(name, 0) + 1

        lanes = [
            Lane("a", lambda: {"refreshed_at": ago(now, hours=1)}, lambda: refresh("a")),
            Lane("b", lambda: {"refreshed_at": ago(now, hours=1)}, lambda: refresh("b")),
        ]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: now)

        for _ in range(120):
            await scheduler.tick()

        status = scheduler.status()["lanes"]
        assert collected["a"] == 100 < CONFIG.daily_call_cap
        assert collected["b"] == 100 < CONFIG.daily_call_cap
        assert status["a"]["last_reason"] == "cap_reached"
        assert status["b"]["last_reason"] == "cap_reached"
        assert collected["a"] + collected["b"] == CONFIG.daily_call_cap

    def test_decide_respects_lane_cap_not_global(self):
        now = at_kst(14)
        result = decide(
            now_utc=now,
            last_refreshed_at=ago(now, hours=1),
            calls_today=100,
            config=CONFIG,
            daily_call_cap=100,
        )
        assert not result.collect
        assert result.reason == "cap_reached"

        # lane 상한이 전역 200 미만이면 199회로도 막힌다 — 200을 독식할 수 없다.
        result = decide(
            now_utc=now,
            last_refreshed_at=ago(now, hours=1),
            calls_today=199,
            config=CONFIG,
            daily_call_cap=100,
        )
        assert not result.collect
        assert result.reason == "cap_reached"

    def test_lane_cap_of_zero_blocks_immediately(self):
        now = at_kst(14)
        result = decide(
            now_utc=now,
            last_refreshed_at=ago(now, hours=1),
            calls_today=0,
            config=CONFIG,
            daily_call_cap=0,
        )
        assert not result.collect
        assert result.reason == "cap_reached"

    @pytest.mark.asyncio
    async def test_env_override_cap(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_DAILY_CAP", "30")
        scheduler = CollectionScheduler([Lane("x_radar", lambda: {}, _noop)], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["daily_call_cap"] == 30

    @pytest.mark.asyncio
    async def test_lane_field_cap_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_X_RADAR_DAILY_CAP", "30")
        lane = Lane("x_radar", lambda: {}, _noop, daily_call_cap=5)
        scheduler = CollectionScheduler([lane], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["x_radar"]["daily_call_cap"] == 5


class TestScrapeApiBudgetSplit:
    """헤더 판정(2026-08-16) — 전역 200은 scrape lane끼리, api lane은 전역 밖 자기 상한 300."""

    @pytest.mark.asyncio
    async def test_scrape_split_and_api_default_300(self):
        lanes = [
            Lane("s1", lambda: {}, _noop),
            Lane("s2", lambda: {}, _noop),
            Lane("a1", lambda: {}, _noop, kind="api"),
            Lane("a2", lambda: {}, _noop, kind="api"),
        ]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: at_kst(14))

        status = scheduler.status()["lanes"]
        assert status["s1"]["kind"] == "scrape"
        assert status["s2"]["kind"] == "scrape"
        assert status["s1"]["daily_call_cap"] == 100
        assert status["s2"]["daily_call_cap"] == 100
        assert status["a1"]["kind"] == "api"
        assert status["a2"]["kind"] == "api"
        assert status["a1"]["daily_call_cap"] == 300
        assert status["a2"]["daily_call_cap"] == 300
        assert status["s1"]["daily_call_cap"] + status["s2"]["daily_call_cap"] == CONFIG.daily_call_cap

    @pytest.mark.asyncio
    async def test_api_consumption_does_not_shrink_scrape_budget(self):
        now = at_kst(14)
        collected: dict[str, int] = {}

        async def refresh(name: str):
            collected[name] = collected.get(name, 0) + 1

        def make(name: str, kind: str) -> Lane:
            return Lane(name, lambda: {"refreshed_at": ago(now, hours=1)}, lambda: refresh(name), kind=kind)

        scheduler = CollectionScheduler(
            [make("s1", "scrape"), make("s2", "scrape"), make("a1", "api"), make("a2", "api")],
            CONFIG,
            clock=lambda: now,
        )

        for _ in range(288):
            await scheduler.tick()

        # 24시간(288틱)을 채워도 api lane은 자기 상한 300 안이고,
        # scrape lane 예산(각 100)은 한 푼도 줄지 않았다.
        assert collected["a1"] == 288
        assert collected["a2"] == 288
        assert collected["s1"] == 100
        assert collected["s2"] == 100
        status = scheduler.status()["lanes"]
        assert status["s1"]["daily_call_cap"] == 100
        assert status["s2"]["daily_call_cap"] == 100

        # 300은 실상한이다 — 도달하면 멈춘다(무한이 아니다).
        for _ in range(12):
            await scheduler.tick()
        assert collected["a1"] == 300
        assert collected["a2"] == 300
        reasons = await scheduler.tick()
        assert reasons["a1"] == "cap_reached"
        assert reasons["a2"] == "cap_reached"

    @pytest.mark.asyncio
    async def test_unspecified_kind_defaults_to_scrape(self):
        lanes = [Lane("u1", lambda: {}, _noop), Lane("u2", lambda: {}, _noop)]
        scheduler = CollectionScheduler(lanes, CONFIG, clock=lambda: at_kst(14))

        status = scheduler.status()["lanes"]
        assert status["u1"]["kind"] == "scrape"
        assert status["u2"]["kind"] == "scrape"
        # api 기본값 300이 아니라 전역 200을 나눈 100/100이다.
        assert status["u1"]["daily_call_cap"] == 100
        assert status["u2"]["daily_call_cap"] == 100

    @pytest.mark.asyncio
    async def test_kind_normalization_and_unknown_kind_is_scrape(self):
        scheduler = CollectionScheduler(
            [
                Lane("upper", lambda: {}, _noop, kind="API"),
                Lane("weird", lambda: {}, _noop, kind="모름"),
            ],
            CONFIG,
            clock=lambda: at_kst(14),
        )

        status = scheduler.status()["lanes"]
        assert status["upper"]["kind"] == "api"
        assert status["upper"]["daily_call_cap"] == 300
        assert status["weird"]["kind"] == "scrape"

    @pytest.mark.asyncio
    async def test_api_cap_env_override(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_SCHEDULER_A1_DAILY_CAP", "500")
        scheduler = CollectionScheduler([Lane("a1", lambda: {}, _noop, kind="api")], CONFIG, clock=lambda: at_kst(14))
        assert scheduler.status()["lanes"]["a1"]["daily_call_cap"] == 500
