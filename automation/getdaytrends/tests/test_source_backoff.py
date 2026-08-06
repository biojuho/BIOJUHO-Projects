"""소스별 실패 백오프 계약.

2026-08-06에 직접 수집을 넷에서 일곱으로 늘리며 5분 주기를 그대로 뒀다.
82cook이 IP 단위로 443을 끊었는데 수집기는 그 뒤로도 5분마다 계속 두드렸다.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source_backoff import BACKOFF_MINUTES, SourceBackoff  # noqa: E402

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def test_healthy_source_is_never_skipped():
    assert SourceBackoff().should_skip("dogdrip", NOW) is False


def test_first_failure_pauses_the_source():
    b = SourceBackoff()
    b.record_failure("82cook", NOW)
    assert b.should_skip("82cook", NOW + timedelta(minutes=14)) is True
    assert b.should_skip("82cook", NOW + timedelta(minutes=16)) is False


def test_repeated_failures_widen_the_gap():
    b = SourceBackoff()
    seen = []
    for _ in range(len(BACKOFF_MINUTES) + 2):
        b.record_failure("82cook", NOW)
        seen.append(b.status(NOW)["82cook"]["resume_in_minutes"])
    # 간격이 단조 증가하다 마지막 값에서 멈춘다 — 무한히 늘려 영영 포기하지는 않는다.
    assert seen[:len(BACKOFF_MINUTES)] == list(BACKOFF_MINUTES)
    assert seen[-1] == BACKOFF_MINUTES[-1]


def test_one_success_clears_the_penalty():
    # 일시적 장애를 영구 감점으로 만들면 소스가 영영 돌아오지 못한다.
    b = SourceBackoff()
    for _ in range(3):
        b.record_failure("82cook", NOW)
    b.record_success("82cook")
    assert b.should_skip("82cook", NOW) is False
    assert b.status(NOW) == {}


def test_sources_are_independent():
    b = SourceBackoff()
    b.record_failure("82cook", NOW)
    assert b.should_skip("82cook", NOW) is True
    assert b.should_skip("ruliweb", NOW) is False


def test_status_only_lists_sources_still_waiting():
    b = SourceBackoff()
    b.record_failure("82cook", NOW)
    assert "82cook" in b.status(NOW)
    assert b.status(NOW + timedelta(minutes=20)) == {}
