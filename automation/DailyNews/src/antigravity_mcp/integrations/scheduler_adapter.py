"""Smart posting scheduler adapter.

Provides optimal posting time calculation based on historical data
and default engagement windows. Extracted from .agent/engine/scheduler.py.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# KST-based posting windows (from historical X engagement research)
_DEFAULT_WINDOWS = {
    "weekday": [
        {"hour": 7, "weight": 0.7},
        {"hour": 8, "weight": 0.8},
        {"hour": 12, "weight": 0.9},
        {"hour": 18, "weight": 0.85},
        {"hour": 21, "weight": 1.0},
        {"hour": 22, "weight": 0.75},
    ],
    "weekend": [
        {"hour": 10, "weight": 0.8},
        {"hour": 13, "weight": 0.85},
        {"hour": 16, "weight": 0.7},
        {"hour": 20, "weight": 0.95},
        {"hour": 22, "weight": 0.8},
    ],
}

_KST_OFFSET = 9  # UTC+9


class SchedulerAdapter:
    """Determines optimal posting times for X content."""

    def __init__(self, *, state_store: PipelineStateStore | None = None) -> None:
        self._state_store = state_store

    def get_optimal_hours(self, count: int = 5, target_date: datetime | None = None) -> list[dict]:
        """Return top *count* posting hours for *target_date* (default: today KST)."""
        now = target_date or datetime.now(UTC)
        kst_hour = (now.hour + _KST_OFFSET) % 24
        kst_weekday = (now.weekday() + (1 if kst_hour < now.hour else 0)) % 7
        day_type = "weekend" if kst_weekday >= 5 else "weekday"

        windows = _DEFAULT_WINDOWS[day_type]

        # Boost windows that leverage historical tweet performance
        if self._state_store:
            try:
                top_tweets = self._state_store.get_top_tweets(days=30, limit=20)
                if len(top_tweets) >= 5:
                    hour_scores: dict[int, float] = {}
                    for tw in top_tweets:
                        published = tw.get("published_at", "")
                        if published and "T" in published:
                            try:
                                h = int(published.split("T")[1][:2])
                                kst_h = (h + _KST_OFFSET) % 24
                                imp = tw.get("impressions", 0)
                                hour_scores[kst_h] = hour_scores.get(kst_h, 0) + imp
                            except (ValueError, IndexError):
                                pass
                    if hour_scores:
                        max_score = max(hour_scores.values())
                        for w in windows:
                            hist_score = hour_scores.get(w["hour"], 0)
                            if max_score > 0:
                                w["weight"] = w["weight"] * 0.5 + (hist_score / max_score) * 0.5
            except Exception as exc:
                logger.debug("Historical posting data unavailable: %s", exc)

        ranked = sorted(windows, key=lambda w: w["weight"], reverse=True)
        return ranked[:count]

    def should_post_now(self, tolerance_minutes: int = 30) -> bool:
        """Check if the current time is within an optimal posting window."""
        now = datetime.now(UTC)
        kst_hour = (now.hour + _KST_OFFSET) % 24
        kst_minute = now.minute
        optimal = self.get_optimal_hours(count=3)
        for w in optimal:
            diff = abs(kst_hour * 60 + kst_minute - w["hour"] * 60)
            if diff <= tolerance_minutes or (1440 - diff) <= tolerance_minutes:
                return True
        return False

    def get_next_posting_slot(self) -> dict:
        """Return the next optimal posting time slot."""
        now = datetime.now(UTC)
        kst_hour = (now.hour + _KST_OFFSET) % 24
        optimal = self.get_optimal_hours(count=6)
        for w in optimal:
            if w["hour"] > kst_hour:
                return {"hour_kst": w["hour"], "weight": w["weight"]}
        # All today's slots passed; return first tomorrow slot
        return {"hour_kst": optimal[0]["hour"], "weight": optimal[0]["weight"], "tomorrow": True}
