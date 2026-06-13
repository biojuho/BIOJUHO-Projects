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


def _count_usable_context_sources(context: MultiSourceContext | None) -> int:
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
    context: MultiSourceContext,
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
    """Signal score (0-100)."""
    return min(
        _volume_signal_score(volume_numeric)
        + _acceleration_signal_score(trend_acceleration)
        + _source_signal_score(cross_source_confidence)
        + _freshness_signal_score(content_age_hours, is_new)
        + _velocity_signal_score(velocity),
        100,
    )


def _volume_signal_score(volume_numeric: int) -> float:
    if volume_numeric <= 0:
        return 0.0
    return min(math.log10(volume_numeric + 1) / math.log10(10_000_001) * 30, 30)


def _acceleration_signal_score(trend_acceleration: str) -> float:
    acceleration = trend_acceleration or ""
    match = re.search(r"\+([\d.]+)\s*%?", acceleration)
    if match:
        return _positive_acceleration_score(float(match.group(1)))
    if acceleration.startswith("-"):
        return 0.0
    if "급상승" in acceleration:
        return 25.0
    return 0.0


def _positive_acceleration_score(pct: float) -> float:
    if pct >= 30:
        return 25.0
    if pct >= 10:
        return 15.0
    if pct >= 3:
        return 8.0
    return 3.0


def _source_signal_score(cross_source_confidence: int) -> float:
    return min(cross_source_confidence * 5.0, 20)


def _freshness_signal_score(content_age_hours: float, is_new: bool) -> float:
    return _compute_freshness_score(content_age_hours, is_new) * 0.75


def _velocity_signal_score(velocity: float) -> float:
    return min(max(velocity, 0.0) * 5.0, 10.0)
