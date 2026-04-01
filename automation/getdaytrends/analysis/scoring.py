"""analysis/scoring.py — 시그널 기반 스코어링 헬퍼 함수.

analyzer.py에서 추출. 교차 검증, 신선도, 시그널 점수 계산.
"""

import math
import re

try:
    from ..models import MultiSourceContext
except ImportError:
    from models import MultiSourceContext


def _compute_cross_source_confidence(
    volume_numeric: int,
    context: "MultiSourceContext",
) -> int:
    """
    Phase 1: 멀티소스 교차 검증 점수 (0~4).
    +1 볼륨 있음 / +1 X에서 실제 트윗 확인 / +1 뉴스 확인 / +1 Reddit 확인
    """
    score = 0
    if volume_numeric > 0:
        score += 1
    if (
        context
        and context.twitter_insight
        and "없음" not in context.twitter_insight
        and "오류" not in context.twitter_insight
        and len(context.twitter_insight) > 20
    ):
        score += 1
    if context and context.news_insight and "없음" not in context.news_insight and len(context.news_insight) > 20:
        score += 1
    if (
        context
        and context.reddit_insight
        and "없음" not in context.reddit_insight
        and "제한" not in context.reddit_insight
        and len(context.reddit_insight) > 20
    ):
        score += 1
    return score


def _compute_freshness_score(content_age_hours: float, is_new: bool = True) -> float:
    """
    [v6.1] 시간 기반 신선도 점수 (0~20).
    content_age_hours가 0이면 (날짜 미확인) is_new 폴백.
    - 0~1h: 20점 (최신)
    - 1~3h: 20→15점
    - 3~6h: 15→10점
    - 6~12h: 10→5점
    - 12h+: 5→0점
    """
    if content_age_hours <= 0:
        return 20.0 if is_new else 10.0  # 날짜 미확인 → 기존 바이너리 폴백
    if content_age_hours <= 1:
        return 20.0
    if content_age_hours <= 3:
        return 20.0 - (content_age_hours - 1) * 2.5  # 20 → 15
    if content_age_hours <= 6:
        return 15.0 - (content_age_hours - 3) * 1.67  # 15 → 10
    if content_age_hours <= 12:
        return 10.0 - (content_age_hours - 6) * 0.83  # 10 → 5
    return max(5.0 - (content_age_hours - 12) * 0.42, 0)  # 5 → 0 (24h)


def _compute_signal_score(
    volume_numeric: int,
    trend_acceleration: str,
    cross_source_confidence: int,
    is_new: bool = True,
    content_age_hours: float = 0.0,
    velocity: float = 0.0,
) -> float:
    """
    Phase 2: 시그널 기반 보조 점수 (0~100).
    볼륨(30) + 가속도(25) + 소스수(20) + 신선도(15) + 벨로시티(10) [v9.0]
    [v6.1] 신선도: 바이너리 → 시간 감쇠 함수
    [v9.0] velocity: 런 간 볼륨 증가율 기반 최대 10점 추가
    """
    # 볼륨 점수 (로그 정규화, 최대 30점)
    if volume_numeric > 0:
        vol_score = min(math.log10(volume_numeric + 1) / math.log10(10_000_001) * 30, 30)
    else:
        vol_score = 0

    # 가속도 점수 (최대 25점)
    acc_score = 0.0
    m = re.search(r"\+([\d.]+)\s*%?", trend_acceleration or "")
    if m:
        pct = float(m.group(1))
        if pct >= 30:
            acc_score = 25
        elif pct >= 10:
            acc_score = 15
        elif pct >= 3:
            acc_score = 8
        else:
            acc_score = 3
    elif trend_acceleration and trend_acceleration.startswith("-"):
        acc_score = 0
    elif "급상승" in (trend_acceleration or ""):
        acc_score = 25

    # 소스 교차 점수 (최대 20점, 기존 25 → 조정)
    source_score = min(cross_source_confidence * 5.0, 20)

    # [v6.1] 신선도 점수 — 시간 감쇠 (최대 15점, 기존 20 → 조정)
    freshness_score = _compute_freshness_score(content_age_hours, is_new) * 0.75

    # [v9.0] 벨로시티 점수 — 런 간 볼륨 증가율 (최대 10점)
    velocity_score = min(max(velocity, 0.0) * 5.0, 10.0)

    return min(vol_score + acc_score + source_score + freshness_score + velocity_score, 100)
