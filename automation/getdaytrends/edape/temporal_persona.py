"""
EDAPE — Temporal Persona Tuner

시간대·요일에 따라 콘텐츠 톤을 자동 조절하는 모듈.
X(Twitter) 알고리즘의 시간대별 engagement 편향을 반영한다.

근거:
  - 주중 오전(8~12시): 정보 소비 모드 → 팩트/데이터 중심 콘텐츠가 engagement 높음
  - 주중 오후(13~18시): 가벼운 공유 모드 → 의견/관찰형 콘텐츠
  - 야간(19~01시): 감성 모드 → 감정적 관찰/공감형 콘텐츠
  - 주말 전일: 엔터테인먼트 모드 → 위트/풍자형
"""

from __future__ import annotations

from datetime import datetime


# ══════════════════════════════════════════════════════
#  Time Slot Definitions
# ══════════════════════════════════════════════════════

# (시작시간, 종료시간, 주중hint, 주말hint)
_TIME_SLOTS: list[tuple[int, int, str, str]] = [
    (
        7, 12,
        "팩트 중심 — 데이터/통계를 앞세우고, '왜 중요한가'를 1문장으로 각인. 짧은 문장, 강한 수치.",
        "가벼운 정보 — 주말 아침 감성. '알고 보면 재밌는' 프레임, 호기심 유발 훅.",
    ),
    (
        12, 18,
        "의견 중심 — '솔직히 말하면'으로 시작하는 관찰형. 논쟁 유도, 인용 RT 유도.",
        "엔터 중심 — 풍자·위트·밈 감성. 과장법 허용, 짧은 펀치라인.",
    ),
    (
        18, 24,
        "감성 중심 — 하루 마감 감성. 공감 서사, 질문형 킥, 1인칭 사용 권장.",
        "감성 중심 — 주말 야간. 깊은 생각, 에세이 톤, 장문 허용.",
    ),
    (
        0, 7,
        "야간 — 매니아 타겟. 니치 주제, 깊은 분석, 언더그라운드 감성.",
        "야간 — 올빼미 팬덤. 서브컬처 레퍼런스, 밀도 높은 정보.",
    ),
]


class TemporalPersonaTuner:
    """시간대·요일 기반 페르소나 힌트 생성기."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now()

    def get_current_hint(self) -> str:
        """현재 시간대에 맞는 페르소나 튜닝 힌트 반환."""
        hour = self._now.hour
        is_weekend = self._now.weekday() >= 5  # 0=월 ... 6=일

        for start, end, weekday_hint, weekend_hint in _TIME_SLOTS:
            if start <= hour < end:
                base = weekend_hint if is_weekend else weekday_hint
                day_label = "주말" if is_weekend else "주중"
                return f"[{day_label} {hour:02d}시] {base}"

        # fallback (should not reach here)
        return ""

    def get_slot_name(self) -> str:
        """디버깅용 현재 슬롯 이름 반환."""
        hour = self._now.hour
        is_weekend = self._now.weekday() >= 5

        if 7 <= hour < 12:
            slot = "morning"
        elif 12 <= hour < 18:
            slot = "afternoon"
        elif 18 <= hour < 24:
            slot = "evening"
        else:
            slot = "night"

        prefix = "weekend" if is_weekend else "weekday"
        return f"{prefix}_{slot}"
