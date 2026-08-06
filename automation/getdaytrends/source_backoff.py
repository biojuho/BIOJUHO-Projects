"""소스별 실패 백오프.

2026-08-06에 직접 수집 소스를 넷에서 일곱으로 늘리면서 5분 주기를 그대로 뒀다.
사이트당 하루 180회다. 82cook이 그걸 견디지 못하고 IP 단위로 443을 끊었고
(연결 자체가 거부됨), 수집기는 그 뒤로도 5분마다 계속 두드렸다.

차단당한 곳을 같은 빈도로 계속 찌르는 건 상대에게도 우리에게도 손해다.
실패가 이어지면 간격을 벌리고, 성공하면 즉시 원래대로 돌아온다.

이 모듈은 순수 상태 기계다 — 시각을 인자로 받으므로 시계를 기다리지 않고 테스트한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# 연속 실패 횟수별 대기 시간(분). 마지막 값에서 더 늘리지 않는다.
BACKOFF_MINUTES = (15, 30, 60, 180, 360)


class SourceBackoff:
    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._until: dict[str, datetime] = {}

    def should_skip(self, key: str, now: datetime) -> bool:
        until = self._until.get(key)
        return bool(until and now < until)

    def record_success(self, key: str) -> None:
        # 한 번 성공하면 그동안의 실패는 잊는다. 일시적 장애를 영구 감점으로 만들지 않는다.
        self._failures.pop(key, None)
        self._until.pop(key, None)

    def record_failure(self, key: str, now: datetime) -> None:
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        minutes = BACKOFF_MINUTES[min(count, len(BACKOFF_MINUTES)) - 1]
        self._until[key] = now + timedelta(minutes=minutes)

    def status(self, now: datetime) -> dict[str, Any]:
        return {
            key: {
                "failures": self._failures.get(key, 0),
                "resume_in_minutes": max(0, round((until - now).total_seconds() / 60)),
            }
            for key, until in self._until.items()
            if now < until
        }
