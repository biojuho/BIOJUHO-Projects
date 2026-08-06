"""서버측 수집 스케줄러.

지금까지 자동 갱신은 대시보드 페이지의 `setInterval`에서만 돌았다. 탭을 닫으면
수집이 멈췄고, 2026-08-06에는 관측이 09:07~11:20 두 시간분에 그쳤다. 조기 탐지
리드타임은 연속 관측이 없으면 측정 자체가 성립하지 않는다.

그렇다고 24시간 쉬지 않고 외부에 요청을 보내면 곤란하므로 네 겹으로 묶는다.

1. **가동 시간대** — 기본 09~24시(KST). 새벽에는 아예 돌지 않는다.
2. **주기** — 기본 5분. 브라우저가 하던 2분보다 느슨하다.
3. **일일 상한** — 레인당 기본 200회. 넘으면 자정까지 멈춘다.
4. **중복 회피** — 마지막 갱신이 주기보다 최근이면 건너뛴다. 브라우저가 열려 있어
   이미 수집 중이면 서버는 요청을 보태지 않는다.

`decide()`는 부작용이 없는 순수 함수다. 판정과 루프를 나눠 둔 덕분에 시간대·상한·
자정 넘김 같은 경계를 시계를 기다리지 않고 테스트할 수 있다.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

try:
    from .freshness import _parse as _parse_timestamp
except ImportError:  # 스크립트로 직접 실행할 때
    from freshness import _parse as _parse_timestamp

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_ACTIVE_START_HOUR = 9
DEFAULT_ACTIVE_END_HOUR = 24
DEFAULT_DAILY_CALL_CAP = 200
DEFAULT_TZ_OFFSET_HOURS = 9  # KST


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


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    active_start_hour: int = DEFAULT_ACTIVE_START_HOUR
    active_end_hour: int = DEFAULT_ACTIVE_END_HOUR
    daily_call_cap: int = DEFAULT_DAILY_CALL_CAP
    tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS

    @classmethod
    def from_env(cls) -> SchedulerConfig:
        return cls(
            enabled=_env_bool("GETDAYTRENDS_SCHEDULER_ENABLED", True),
            interval_seconds=max(60, _env_int("GETDAYTRENDS_SCHEDULER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
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

    def is_active_hour(self, now_utc: datetime) -> bool:
        hour = self.local_now(now_utc).hour
        start, end = self.active_start_hour, self.active_end_hour
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
) -> Decision:
    """이번 틱에 이 레인을 수집할지 판정한다(부작용 없음)."""
    if not config.enabled:
        return Decision(False, "disabled")
    if calls_today >= config.daily_call_cap:
        return Decision(False, "cap_reached")
    if not config.is_active_hour(now_utc):
        return Decision(False, "outside_active_hours")

    parsed = _parse_timestamp(last_refreshed_at)
    if parsed is None:
        return Decision(True, "never_collected")

    age = (now_utc.astimezone(timezone.utc) - parsed).total_seconds()
    if age < 0:
        # 시계가 어긋난 상태에서 무한정 쉬지 않도록 한 번 수집하고 시각을 다시 쓴다.
        return Decision(True, "clock_skew")
    if age < config.interval_seconds:
        # 브라우저가 방금 갱신했다 — 요청을 보태지 않는다.
        return Decision(False, "recently_refreshed")
    return Decision(True, "due")


@dataclass
class Lane:
    """수집 대상 한 갈래. 스냅샷에서 마지막 시각을 읽고, refresh로 한 번 수집한다."""

    name: str
    snapshot: Callable[[], dict[str, Any]]
    refresh: Callable[[], Awaitable[Any]]


@dataclass
class LaneState:
    calls_today: int = 0
    day: date | None = None
    last_attempt_at: datetime | None = None
    last_reason: str = "not_started"
    last_error: str | None = None
    consecutive_errors: int = 0


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
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._states: dict[str, LaneState] = {lane.name: LaneState() for lane in lanes}
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    # ── 상태 ──────────────────────────────────────────────────────────────
    def status(self) -> dict[str, Any]:
        now = self._clock()
        return {
            "enabled": self.config.enabled,
            "running": self._task is not None and not self._task.done(),
            "interval_seconds": self.config.interval_seconds,
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
        logger.info(
            "[scheduler] 수집 스케줄러 시작 — %s초 주기, %02d~%02d시(UTC%+d), 레인당 하루 %d회",
            self.config.interval_seconds,
            self.config.active_start_hour,
            self.config.active_end_hour,
            self.config.tz_offset_hours,
            self.config.daily_call_cap,
        )
        try:
            while not self._stopping.is_set():
                try:
                    await self.tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # 어떤 이유로도 루프가 죽지 않게
                    logger.exception("[scheduler] 틱 처리 중 예기치 못한 오류: %s", exc)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.config.interval_seconds)
                except asyncio.TimeoutError:
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
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: B014 - 종료 경로에서 예외를 삼킨다
            pass
