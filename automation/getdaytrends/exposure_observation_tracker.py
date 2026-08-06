"""Persist observable signal changes used by X exposure ranking."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class ExposureObservationTracker:
    """Keep short time series and return deltas without inventing missing history."""

    def __init__(self, state_path: Path | None, *, max_points: int = 24):
        self.state_path = state_path
        self.max_points = max_points
        self._state = self._load()
        self._dirty = False

    def _load(self) -> dict[str, Any]:
        if self.state_path is None:
            return {"version": 1, "series": {}}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "series": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("series"), dict):
            return {"version": 1, "series": {}}
        return payload

    @staticmethod
    def _delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
        if not previous:
            return {
                "previous_observed_at": None,
                "x_rank_change": None,
                "new_originals": None,
                "new_sources": None,
                "comment_growth": None,
                "new_mentions": None,
            }

        def positive_change(field: str) -> int | None:
            before = previous.get(field)
            after = current.get(field)
            if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
                return None
            return max(0, round(after - before))

        previous_rank = previous.get("x_rank")
        current_rank = current.get("x_rank")
        rank_change = None
        if isinstance(previous_rank, int) and isinstance(current_rank, int):
            rank_change = previous_rank - current_rank
        return {
            "previous_observed_at": previous.get("observed_at"),
            "x_rank_change": rank_change,
            "new_originals": positive_change("original_count"),
            "new_sources": positive_change("source_count"),
            "comment_growth": positive_change("comments"),
            "new_mentions": positive_change("mentions"),
        }

    def record(
        self,
        key: str,
        metrics: dict[str, Any],
        *,
        observed_at: datetime,
        score_version: str,
    ) -> dict[str, Any]:
        timestamp = observed_at.astimezone(UTC).isoformat()
        series = self._state.setdefault("series", {}).setdefault(key, [])
        previous = series[-1] if series else None
        current = {"observed_at": timestamp, "score_version": score_version, **metrics}
        deltas = self._delta(current, previous)
        sample_id = current.get("sample_id")
        same_upstream_sample = bool(
            previous
            and sample_id
            and previous.get("sample_id") == sample_id
        )
        if not same_upstream_sample and previous != current:
            series.append(current)
            del series[: max(0, len(series) - self.max_points)]
            self._dirty = True
        positive_rank_streak = 0
        for before, after in zip(reversed(series[:-1]), reversed(series[1:]), strict=True):
            before_rank = before.get("x_rank")
            after_rank = after.get("x_rank")
            try:
                before_at = datetime.fromisoformat(str(before.get("observed_at"))).astimezone(UTC)
                after_at = datetime.fromisoformat(str(after.get("observed_at"))).astimezone(UTC)
            except (TypeError, ValueError):
                break
            if (
                not isinstance(before_rank, int)
                or not isinstance(after_rank, int)
                or before_rank <= after_rank
                or after_at - before_at > timedelta(minutes=10)
            ):
                break
            positive_rank_streak += 1
        return {
            "observed_at": timestamp,
            "score_version": score_version,
            "observation_count": len(series),
            "positive_rank_streak": positive_rank_streak,
            "sample_advanced": not same_upstream_sample,
            **deltas,
        }

    def save(self, *, now: datetime) -> None:
        if not self._dirty or self.state_path is None:
            return
        cutoff = now.astimezone(UTC) - timedelta(days=7)
        kept: dict[str, list[dict[str, Any]]] = {}
        for key, points in self._state.get("series", {}).items():
            recent = []
            for point in points:
                try:
                    observed = datetime.fromisoformat(str(point.get("observed_at"))).astimezone(UTC)
                except (TypeError, ValueError):
                    continue
                if observed >= cutoff:
                    recent.append(point)
            if recent:
                kept[key] = recent[-self.max_points :]
        self._state["series"] = kept
        self._state["updated_at"] = now.astimezone(UTC).isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.state_path)
        self._dirty = False
