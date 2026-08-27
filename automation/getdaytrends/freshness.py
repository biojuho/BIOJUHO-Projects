"""수집 신선도 판정.

각 수집 레인이 마지막으로 갱신된 시각을 나이(age)와 등급으로 환산한다.
판정을 서버에 두는 이유는 두 가지다 — 프론트에 흩어진 임계를 한곳에 모으고,
파이썬 테스트로 경계값을 고정할 수 있게 하기 위해서다.

수집은 서버 스케줄러가 맡고 화면은 GET 폴링으로 마지막 스냅샷만 읽는다(0099).
스케줄러가 멈추면 스냅샷도 멈추므로, 화면의 라이브 표시가 계속 켜져 있으면
멈춘 걸 알 수 없다. 이 모듈의 등급을 그 표시에 연동한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# 레인별 임계(초). 서버 스케줄러 주기(dashboard.py Lane 배선)를 기준으로 잡았다 —
# 한두 번 걸러도 경고가 뜨지 않고, 연속으로 놓치면 확실히 눈에 띄게 한다.
# 300초 주기에서 360초 경고는 정상 회차 사이에도 경고가 깜빡거릴 만큼 촘촘해서
# 0099에서 느슨하게 다시 잡았다.
LANE_THRESHOLDS: dict[str, tuple[int, int]] = {
    # 이름: (warn_after_seconds, stale_after_seconds)
    "x_radar": (360, 900),  # 서버 120초 주기
    "fast_viral": (900, 1800),  # 서버 300초 주기
    "live_reference": (2700, 5400),  # 서버 1800초 주기
}

DEFAULT_WARN_AFTER = 360
DEFAULT_STALE_AFTER = 900


@dataclass(frozen=True)
class Freshness:
    age_seconds: int | None
    level: str  # "fresh" | "warn" | "stale" | "unknown"
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {"age_seconds": self.age_seconds, "level": self.level, "label": self.label}


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    # 타임존이 없는 값은 UTC로 본다. 이 저장소의 수집기는 tz-aware UTC로 기록하지만,
    # 예전 파일이나 손으로 만든 값이 섞여도 로컬 시간으로 오해하지 않게 한다.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def humanize_age(age_seconds: int | None) -> str:
    if age_seconds is None:
        return "기록 없음"
    if age_seconds < 0:
        # 서버와 수집기의 시계가 어긋난 경우. 미래 시각을 "방금"으로 뭉개면
        # 시계 문제를 영영 모르게 되므로 그대로 드러낸다.
        return "시각 오류"
    if age_seconds < 60:
        return "방금"
    minutes = age_seconds // 60
    if minutes < 60:
        return f"{minutes}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    return f"{hours // 24}일 전"


def describe_freshness(
    refreshed_at: Any,
    *,
    warn_after: int = DEFAULT_WARN_AFTER,
    stale_after: int = DEFAULT_STALE_AFTER,
    now: datetime | None = None,
) -> dict[str, Any]:
    """마지막 갱신 시각을 나이·등급·표시 문구로 환산한다."""
    parsed = _parse(refreshed_at)
    if parsed is None:
        return Freshness(None, "unknown", humanize_age(None)).as_dict()

    current = (now or datetime.now(UTC)).astimezone(UTC)
    age = int((current - parsed).total_seconds())
    if age < 0:
        level = "unknown"
    elif age >= stale_after:
        level = "stale"
    elif age >= warn_after:
        level = "warn"
    else:
        level = "fresh"
    return Freshness(age, level, humanize_age(age)).as_dict()


def describe_lane(lane: str, refreshed_at: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """레인 이름으로 임계를 골라 신선도를 판정한다."""
    warn_after, stale_after = LANE_THRESHOLDS.get(lane, (DEFAULT_WARN_AFTER, DEFAULT_STALE_AFTER))
    return describe_freshness(refreshed_at, warn_after=warn_after, stale_after=stale_after, now=now)


def attach_freshness(
    payload: dict[str, Any],
    lane: str,
    *,
    field: str = "refreshed_at",
    now: datetime | None = None,
) -> dict[str, Any]:
    """스냅샷 응답에 freshness 필드를 얹어 돌려준다(원본은 건드리지 않는다)."""
    enriched = dict(payload or {})
    enriched["freshness"] = describe_lane(lane, enriched.get(field), now=now)
    return enriched
