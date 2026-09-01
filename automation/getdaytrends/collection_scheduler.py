"""서버측 수집 스케줄러.

지금까지 자동 갱신은 대시보드 페이지의 `setInterval`에서만 돌았다. 탭을 닫으면
수집이 멈췄고, 2026-08-06에는 관측이 09:07~11:20 두 시간분에 그쳤다. 조기 탐지
리드타임은 연속 관측이 없으면 측정 자체가 성립하지 않는다.

그렇다고 24시간 쉬지 않고 외부에 요청을 보내면 곤란하므로 네 겹으로 묶는다.

1. **가동 시간대** — 기본 09~24시(KST). lane별로 덮어쓸 수 있고, L0(기상청)·L1(연합뉴스)
   lane만 24시간 가동을 기본으로 연다(핸드오프 0065).
2. **주기** — 기본 5분. 브라우저가 하던 2분보다 느슨하다. lane별 `interval_seconds` 또는
   `GETDAYTRENDS_SCHEDULER_<LANE>_INTERVAL_SECONDS`로 덮어쓸 수 있고, 최소 60초다.
3. **일일 상한** — `scrape` lane(기본값)들만 전역 `daily_call_cap=200`을 lane 수로 균등
   배분해 쓴다. `api` lane은 전역 예산 밖에서 자기 상한(기본 300)을 갖는다.
   lane별로 환경변수·Lane 필드로 덮어쓸 수 있다.
4. **중복 회피** — 마지막 갱신이 주기보다 최근이면 건너뛴다. 브라우저가 열려 있어
   이미 수집 중이면 서버는 요청을 보태지 않는다.

lane별 설정은 셋 중 앞선 것이 이긴다:

1. `Lane(kind=…, active_start_hour=…, active_end_hour=…, daily_call_cap=…, interval_seconds=…)` — 코드에서 직접
   지정. `kind`는 `"scrape"`/`"api"` 둘 중 하나고 **기본은 `"scrape"`**다 — 모르는 lane을
   싸게 취급하면 위험하므로 안전한 쪽이 기본이다. `api` lane은 전역 예산에 들어가지 않는다.
2. 환경변수 `GETDAYTRENDS_SCHEDULER_<LANE>_START_HOUR` · `_END_HOUR` · `_DAILY_CAP` ·
   `_INTERVAL_SECONDS`
   (lane 이름의 `-`는 `_`로 바꾸고 대문자로 읽는다. 예: `kma-weather` → `KMA_WEATHER`)
3. 이름 기본값 — `kma-weather`·`yonhap-rss`(0063 shadow 소스 키, `_` 표기도 동일 취급)는
   24시간, 그 밖은 전역 `active_start_hour`~`active_end_hour`. 상한 기본값은 `scrape`가
   전역 상한의 균등 배분, `api`가 300이다.

`start == end`는 24시간 가동을 뜻한다(0-0이면 하루 종일).

`decide()`는 부작용이 없는 순수 함수다. 판정과 루프를 나눠 둔 덕분에 시간대·상한·
자정 넘김 같은 경계를 시계를 기다리지 않고 테스트할 수 있다.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from freshness import _parse as _parse_timestamp

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 60
DEFAULT_ACTIVE_START_HOUR = 9
DEFAULT_ACTIVE_END_HOUR = 24
DEFAULT_DAILY_CALL_CAP = 200
DEFAULT_API_DAILY_CALL_CAP = 300  # api lane은 전역 예산 밖 자기 상한 (헤더 판정 2026-08-16)
DEFAULT_TZ_OFFSET_HOURS = 9  # KST
MIN_WAKE_SECONDS = 0.25


def _env_int(name: str, fallback: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning("%s=%r 을 정수로 읽을 수 없어 기본값 %s 를 씁니다", name, raw, fallback)
        return fallback


def _env_bool(name: str, fallback: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _lane_env_var(lane_name: str, key: str) -> str:
    lane_key = lane_name.strip().upper().replace("-", "_")
    return f"GETDAYTRENDS_SCHEDULER_{lane_key}_{key}"


def _lane_env_int(lane_name: str, key: str) -> int | None:
    raw = os.getenv(_lane_env_var(lane_name, key))
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning(
            "%s=%r 을 정수로 읽을 수 없어 무시합니다",
            _lane_env_var(lane_name, key),
            raw,
        )
        return None


def _minimum_interval_seconds(value: int, fallback: int = DEFAULT_INTERVAL_SECONDS) -> int:
    """Return a safe scheduler interval, never shorter than one minute."""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = int(fallback)
    return max(MIN_INTERVAL_SECONDS, interval)


# 핸드오프 0065 — L0(기상청)·L1(연합뉴스) lane은 API·RSS라 호출이 싸고 「2시간 이내
# 속보 탐지」 계약의 1차 소스다. 이 둘만 24시간 가동을 기본으로 연다. 이름은 0063
# shadow 관측의 소스 키를 쓰고, '-'와 '_' 표기는 같게 정규화해 맞춘다.
_ALWAYS_ON_LANE_NAMES = frozenset({"kma-weather", "yonhap-rss"})


def _lane_name_key(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _lane_defaults_to_always_on(name: str) -> bool:
    return _lane_name_key(name) in _ALWAYS_ON_LANE_NAMES


def _lane_kind(lane: Lane) -> str:
    """lane 종류. 명시하지 않거나 api가 아니면 안전한 쪽인 scrape로 취급한다."""
    return "api" if (lane.kind or "scrape").strip().lower() == "api" else "scrape"


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    active_start_hour: int = DEFAULT_ACTIVE_START_HOUR
    active_end_hour: int = DEFAULT_ACTIVE_END_HOUR
    daily_call_cap: int = DEFAULT_DAILY_CALL_CAP
    tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS

    def __post_init__(self) -> None:
        # Direct construction must obey the same external-request floor as from_env().
        object.__setattr__(self, "interval_seconds", _minimum_interval_seconds(self.interval_seconds))

    @classmethod
    def from_env(cls) -> SchedulerConfig:
        return cls(
            enabled=_env_bool("GETDAYTRENDS_SCHEDULER_ENABLED", True),
            interval_seconds=_minimum_interval_seconds(
                _env_int("GETDAYTRENDS_SCHEDULER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
            ),
            active_start_hour=_env_int("GETDAYTRENDS_SCHEDULER_START_HOUR", DEFAULT_ACTIVE_START_HOUR),
            active_end_hour=_env_int("GETDAYTRENDS_SCHEDULER_END_HOUR", DEFAULT_ACTIVE_END_HOUR),
            daily_call_cap=_env_int("GETDAYTRENDS_SCHEDULER_DAILY_CAP", DEFAULT_DAILY_CALL_CAP),
            tz_offset_hours=_env_int("GETDAYTRENDS_SCHEDULER_TZ_OFFSET_HOURS", DEFAULT_TZ_OFFSET_HOURS),
        )

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.tz_offset_hours))

    def local_now(self, now_utc: datetime) -> datetime:
        return now_utc.astimezone(self.tz)

    def is_active_hour(
        self,
        now_utc: datetime,
        start_hour: int | None = None,
        end_hour: int | None = None,
    ) -> bool:
        """가동 시간대 판정. start/end를 주면 전역 대신 그 값으로 판정한다."""
        hour = self.local_now(now_utc).hour
        start = self.active_start_hour if start_hour is None else start_hour
        end = self.active_end_hour if end_hour is None else end_hour
        if start == end:
            return True  # 24시간 가동
        if start < end:
            return start <= hour < end
        # 자정을 넘기는 구간(예: 08~02시)
        return hour >= start or hour < end


@dataclass(frozen=True)
class Decision:
    collect: bool
    reason: str


def decide(
    *,
    now_utc: datetime,
    last_refreshed_at: Any,
    calls_today: int,
    config: SchedulerConfig,
    active_start_hour: int | None = None,
    active_end_hour: int | None = None,
    daily_call_cap: int | None = None,
    interval_seconds: int | None = None,
) -> Decision:
    """이번 틱에 이 레인을 수집할지 판정한다(부작용 없음).

    활동 시간·일일 상한·주기 인자를 주면 lane별 값으로, 주지 않으면 전역 설정으로 판정한다.
    """
    cap = config.daily_call_cap if daily_call_cap is None else daily_call_cap
    interval = (
        config.interval_seconds
        if interval_seconds is None
        else _minimum_interval_seconds(interval_seconds, config.interval_seconds)
    )
    if not config.enabled:
        return Decision(False, "disabled")
    if calls_today >= cap:
        return Decision(False, "cap_reached")
    if not config.is_active_hour(now_utc, active_start_hour, active_end_hour):
        return Decision(False, "outside_active_hours")

    parsed = _parse_timestamp(last_refreshed_at)
    if parsed is None:
        return Decision(True, "never_collected")

    age = (now_utc.astimezone(UTC) - parsed).total_seconds()
    if age < 0:
        # 시계가 어긋난 상태에서 무한정 쉬지 않도록 한 번 수집하고 시각을 다시 쓴다.
        return Decision(True, "clock_skew")
    if age < interval:
        # 브라우저가 방금 갱신했다 — 요청을 보태지 않는다.
        return Decision(False, "recently_refreshed")
    return Decision(True, "due")


@dataclass
class Lane:
    """수집 대상 한 갈래. 스냅샷에서 마지막 시각을 읽고, refresh로 한 번 수집한다.

    활동 시간·일일 상한·주기는 lane별로 덮어쓸 수 있다. None이면 환경변수
    (`GETDAYTRENDS_SCHEDULER_<LANE>_START_HOUR` 등) → 이름 기본값·전역 설정 순으로
    읽는다(모듈 docstring의 우선순위 참고).
    """

    name: str
    snapshot: Callable[[], dict[str, Any]]
    refresh: Callable[[], Awaitable[Any]]
    kind: str = "scrape"
    active_start_hour: int | None = None
    active_end_hour: int | None = None
    daily_call_cap: int | None = None
    interval_seconds: int | None = None


@dataclass
class LaneState:
    calls_today: int = 0
    day: date | None = None
    last_attempt_at: datetime | None = None
    last_reason: str = "not_started"
    last_error: str | None = None
    consecutive_errors: int = 0


@dataclass(frozen=True)
class LaneSchedule:
    """lane 하나에 실제로 적용되는 활동 시간과 일일 상한."""

    active_start_hour: int
    active_end_hour: int
    daily_call_cap: int
    kind: str = "scrape"
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS

    @property
    def active_hours_label(self) -> str:
        if self.active_start_hour == self.active_end_hour:
            return "00-24"  # 24시간 가동
        return f"{self.active_start_hour:02d}-{self.active_end_hour:02d}"


class CollectionScheduler:
    def __init__(
        self,
        lanes: list[Lane],
        config: SchedulerConfig | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.config = config or SchedulerConfig.from_env()
        self.lanes = lanes
        self._clock = clock or (lambda: datetime.now(UTC))
        self._states: dict[str, LaneState] = {lane.name: LaneState() for lane in lanes}
        scrape_count = sum(1 for lane in lanes if _lane_kind(lane) == "scrape")
        scrape_share = self.config.daily_call_cap // max(1, scrape_count)
        self._lane_schedules: dict[str, LaneSchedule] = {
            lane.name: self._resolve_lane_schedule(lane, scrape_share) for lane in lanes
        }
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def _resolve_lane_schedule(self, lane: Lane, scrape_share: int) -> LaneSchedule:
        kind = _lane_kind(lane)
        if _lane_defaults_to_always_on(lane.name):
            default_start, default_end = 0, 0
        else:
            default_start = self.config.active_start_hour
            default_end = self.config.active_end_hour
        env_start = _lane_env_int(lane.name, "START_HOUR")
        env_end = _lane_env_int(lane.name, "END_HOUR")
        env_cap = _lane_env_int(lane.name, "DAILY_CAP")
        env_interval = _lane_env_int(lane.name, "INTERVAL_SECONDS")
        default_cap = scrape_share if kind == "scrape" else DEFAULT_API_DAILY_CALL_CAP
        return LaneSchedule(
            active_start_hour=(
                lane.active_start_hour
                if lane.active_start_hour is not None
                else env_start
                if env_start is not None
                else default_start
            ),
            active_end_hour=(
                lane.active_end_hour
                if lane.active_end_hour is not None
                else env_end
                if env_end is not None
                else default_end
            ),
            daily_call_cap=(
                lane.daily_call_cap
                if lane.daily_call_cap is not None
                else env_cap
                if env_cap is not None
                else default_cap
            ),
            kind=kind,
            interval_seconds=_minimum_interval_seconds(
                lane.interval_seconds
                if lane.interval_seconds is not None
                else env_interval
                if env_interval is not None
                else self.config.interval_seconds,
                self.config.interval_seconds,
            ),
        )

    def _loop_interval_seconds(self) -> int:
        """Wake often enough for the fastest lane; each lane still gates itself in decide()."""
        return min(
            (schedule.interval_seconds for schedule in self._lane_schedules.values()),
            default=self.config.interval_seconds,
        )

    def _last_activity_at(
        self,
        lane: Lane,
        state: LaneState,
        snapshot: dict[str, Any] | None = None,
    ) -> datetime | None:
        """Newest collector refresh or scheduler attempt used for rate limiting."""
        if snapshot is None:
            try:
                snapshot = lane.snapshot() or {}
            except Exception:
                snapshot = {}
        refreshed_at = _parse_timestamp(snapshot.get("refreshed_at"))
        candidates = [value.astimezone(UTC) for value in (refreshed_at, state.last_attempt_at) if value is not None]
        return max(candidates, default=None)

    def _seconds_until_next_check(self) -> float:
        """Return the nearest lane due time from actual refresh/attempt timestamps.

        A fixed sleep from tick start can wake a fraction before the collector's
        own ``refreshed_at`` anniversary.  That early tick is skipped and used
        to delay the next check by a full interval.  Calculating each remaining
        duration directly catches the due time without busy polling.
        """
        now = self._clock().astimezone(UTC)
        remaining: list[float] = []
        for lane in self.lanes:
            activity = self._last_activity_at(lane, self._states[lane.name])
            if activity is None:
                return MIN_WAKE_SECONDS
            age_seconds = (now - activity).total_seconds()
            interval = self._lane_schedules[lane.name].interval_seconds
            remaining.append(max(MIN_WAKE_SECONDS, interval - age_seconds))
        return min(remaining, default=float(self._loop_interval_seconds()))

    # ── 상태 ──────────────────────────────────────────────────────────────
    def status(self) -> dict[str, Any]:
        now = self._clock()
        return {
            "enabled": self.config.enabled,
            "running": self._task is not None and not self._task.done(),
            "interval_seconds": self.config.interval_seconds,
            "loop_interval_seconds": self._loop_interval_seconds(),
            "active_hours": f"{self.config.active_start_hour:02d}-{self.config.active_end_hour:02d}",
            "timezone_offset_hours": self.config.tz_offset_hours,
            "daily_call_cap": self.config.daily_call_cap,
            "within_active_hours": self.config.is_active_hour(now),
            "lanes": {
                name: {
                    "calls_today": state.calls_today,
                    "last_attempt_at": state.last_attempt_at.isoformat() if state.last_attempt_at else None,
                    "last_reason": state.last_reason,
                    "last_error": state.last_error,
                    "consecutive_errors": state.consecutive_errors,
                    "kind": self._lane_schedules[name].kind,
                    "interval_seconds": self._lane_schedules[name].interval_seconds,
                    "active_hours": self._lane_schedules[name].active_hours_label,
                    "within_active_hours": self.config.is_active_hour(
                        now,
                        self._lane_schedules[name].active_start_hour,
                        self._lane_schedules[name].active_end_hour,
                    ),
                    "daily_call_cap": self._lane_schedules[name].daily_call_cap,
                }
                for name, state in self._states.items()
            },
        }

    # ── 한 틱 ─────────────────────────────────────────────────────────────
    def _roll_day(self, state: LaneState, now_utc: datetime) -> None:
        today = self.config.local_now(now_utc).date()
        if state.day != today:
            state.day = today
            state.calls_today = 0

    async def tick(self) -> dict[str, str]:
        """모든 레인을 한 번씩 검토한다. 반환값은 레인별 판정 이유(테스트·상태 확인용)."""
        now = self._clock()
        reasons: dict[str, str] = {}
        for lane in self.lanes:
            state = self._states[lane.name]
            self._roll_day(state, now)
            try:
                snapshot = lane.snapshot() or {}
            except Exception as exc:  # 스냅샷 읽기 실패로 루프가 죽지 않게
                logger.warning("[scheduler] %s 스냅샷 조회 실패: %s", lane.name, exc)
                snapshot = {}
            decision = decide(
                now_utc=now,
                last_refreshed_at=snapshot.get("refreshed_at"),
                calls_today=state.calls_today,
                config=self.config,
                active_start_hour=self._lane_schedules[lane.name].active_start_hour,
                active_end_hour=self._lane_schedules[lane.name].active_end_hour,
                daily_call_cap=self._lane_schedules[lane.name].daily_call_cap,
                interval_seconds=self._lane_schedules[lane.name].interval_seconds,
            )
            state.last_reason = decision.reason
            reasons[lane.name] = decision.reason
            if not decision.collect:
                continue

            state.calls_today += 1
            state.last_attempt_at = now
            try:
                await lane.refresh()
                state.last_error = None
                state.consecutive_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # 수집 실패는 흔하다(외부 사이트 장애). 루프는 계속 돌되 상태에 남긴다.
                state.last_error = f"{type(exc).__name__}: {exc}"[:200]
                state.consecutive_errors += 1
                reasons[lane.name] = "error"
                logger.warning("[scheduler] %s 수집 실패: %s", lane.name, exc)
        return reasons

    # ── 루프 ──────────────────────────────────────────────────────────────
    async def _run(self) -> None:
        lanes_desc = ", ".join(
            f"{name}[{schedule.kind}]={schedule.active_hours_label}(하루 {schedule.daily_call_cap}회)"
            for name, schedule in self._lane_schedules.items()
        )
        logger.info(
            "[scheduler] 수집 스케줄러 시작 — 전역 %s초, 최소 %s초 주기(UTC%+d), lane: %s",
            self.config.interval_seconds,
            self._loop_interval_seconds(),
            self.config.tz_offset_hours,
            lanes_desc or "(없음)",
        )
        try:
            while not self._stopping.is_set():
                try:
                    await self.tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # 어떤 이유로도 루프가 죽지 않게
                    logger.exception("[scheduler] 틱 처리 중 예기치 못한 오류: %s", exc)
                # 각 lane의 실제 완료/시도시각에서 다음 만기까지 남은 만큼만 쉰다.
                remaining = self._seconds_until_next_check()
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=remaining)
                except TimeoutError:
                    continue
        finally:
            logger.info("[scheduler] 수집 스케줄러 정지")

    def start(self) -> None:
        if not self.config.enabled:
            logger.info("[scheduler] 비활성 상태로 기동 — GETDAYTRENDS_SCHEDULER_ENABLED 로 켤 수 있습니다")
            return
        if self._task is not None and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="getdaytrends-collection-scheduler")

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is None or task.done():
            return
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
