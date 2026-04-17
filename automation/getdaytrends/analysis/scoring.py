"""Signal scoring helpers for trend analysis."""

from __future__ import annotations

import math
import re

try:
    from ..models import MultiSourceContext
except ImportError:
    from models import MultiSourceContext


_INVALID_SIGNAL_MARKERS = (
    "없음",
    "오류",
    "실패",
    "제한",
    "log in to x",
    "sign in to x",
    "login to x",
    "log in",
    "sign in",
    "<html",
    "<!doctype",
    "[x 데이터 없음]",
)


def _has_usable_source_text(text: str | None) -> bool:
    """Return True when a source snippet looks like real evidence, not a shell/login page."""
    if not text:
        return False
    cleaned = text.strip()
    if len(cleaned) <= 20:
        return False
    lowered = cleaned.lower()
    return not any(marker in lowered for marker in _INVALID_SIGNAL_MARKERS)


def _count_usable_context_sources(context: "MultiSourceContext | None") -> int:
    """Count usable external sources among X, Reddit, and News."""
    if not context:
        return 0
    return sum(
        1
        for text in (
            getattr(context, "twitter_insight", ""),
            getattr(context, "reddit_insight", ""),
            getattr(context, "news_insight", ""),
        )
        if _has_usable_source_text(text)
    )


def _compute_cross_source_confidence(
    volume_numeric: int,
    context: "MultiSourceContext",
) -> int:
    """
    Phase 1 cross-source confidence (0-4).
    +1 volume exists, +1 usable X, +1 usable news, +1 usable Reddit.
    """
    score = 0
    if volume_numeric > 0:
        score += 1
    if context and _has_usable_source_text(context.twitter_insight):
        score += 1
    if context and _has_usable_source_text(context.news_insight):
        score += 1
    if context and _has_usable_source_text(context.reddit_insight):
        score += 1
    return score


def _compute_freshness_score(content_age_hours: float, is_new: bool = True) -> float:
    """
    Freshness score (0-20).
    When age is unknown, keep the old new/non-new fallback behavior.
    """
    if content_age_hours <= 0:
        return 20.0 if is_new else 10.0
    if content_age_hours <= 1:
        return 20.0
    if content_age_hours <= 3:
        return 20.0 - (content_age_hours - 1) * 2.5
    if content_age_hours <= 6:
        return 15.0 - (content_age_hours - 3) * 1.67
    if content_age_hours <= 12:
        return 10.0 - (content_age_hours - 6) * 0.83
    return max(5.0 - (content_age_hours - 12) * 0.42, 0)


def _compute_signal_score(
    volume_numeric: int,
    trend_acceleration: str,
    cross_source_confidence: int,
    is_new: bool = True,
    content_age_hours: float = 0.0,
    velocity: float = 0.0,
) -> float:
    """
    Signal score (0-100).
    Volume(30) + acceleration(25) + sources(20) + freshness(15) + velocity(10).
    """
    if volume_numeric > 0:
        vol_score = min(math.log10(volume_numeric + 1) / math.log10(10_000_001) * 30, 30)
    else:
        vol_score = 0

    acc_score = 0.0
    match = re.search(r"\+([\d.]+)\s*%?", trend_acceleration or "")
    if match:
        pct = float(match.group(1))
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

    source_score = min(cross_source_confidence * 5.0, 20)
    freshness_score = _compute_freshness_score(content_age_hours, is_new) * 0.75
    velocity_score = min(max(velocity, 0.0) * 5.0, 10.0)

    return min(vol_score + acc_score + source_score + freshness_score + velocity_score, 100)
