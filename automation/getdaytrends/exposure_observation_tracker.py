"""Persist observable signal changes used by X exposure ranking."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class ExposureObservationTracker:
    """Keep short time series and return deltas without inventing missing history."""

    def __init__(
        self,
        state_path: Path | None,
        *,
        max_points: int = 24,
        post_meta_path: Path | None = None,
        max_meta_posts: int = 200_000,
    ):
        self.state_path = state_path
        self.max_points = max_points
        self._state = self._load()
        self._dirty = False
        self.post_meta_path = post_meta_path
        self.max_meta_posts = max_meta_posts
        self._post_meta = self._load_post_meta()
        self._post_meta_dirty = False

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

    def _load_post_meta(self) -> dict[str, Any]:
        if self.post_meta_path is None:
            return {"version": 1, "posts": {}}
        try:
            payload = json.loads(self.post_meta_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "posts": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("posts"), dict):
            return {"version": 1, "posts": {}}
        return payload

    def _record_post_meta(
        self,
        key: str,
        post_meta: dict[str, Any] | None,
        *,
        first_seen_at: str,
    ) -> None:
        if self.post_meta_path is None or not isinstance(post_meta, dict):
            return
        posts = self._post_meta.setdefault("posts", {})
        if key in posts:
            return
        kernel_person = post_meta.get("kernel_person")
        posts[key] = {
            "title": str(post_meta.get("title") or ""),
            "community_source": str(post_meta.get("community_source") or ""),
            "community_label": str(post_meta.get("community_label") or ""),
            "source_url": str(post_meta.get("source_url") or ""),
            "category": str(post_meta.get("category") or ""),
            "first_seen_at": first_seen_at,
            "kernel_axis": str(post_meta.get("kernel_axis") or "") or None,
            "kernel_person": kernel_person if isinstance(kernel_person, bool) else None,
        }
        self._post_meta_dirty = True

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
        post_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = observed_at.astimezone(UTC).isoformat()
        series = self._state.setdefault("series", {}).setdefault(key, [])
        first_seen_at = str(series[0].get("observed_at") or timestamp) if series else timestamp
        self._record_post_meta(key, post_meta, first_seen_at=first_seen_at)
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
        if not self._dirty and not self._post_meta_dirty:
            return
        timestamp = now.astimezone(UTC).isoformat()
        if self._dirty and self.state_path is not None:
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
            self._state["updated_at"] = timestamp
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.state_path)
            self._dirty = False

        if self._post_meta_dirty and self.post_meta_path is not None:
            posts = self._post_meta.setdefault("posts", {})
            trim_count = max(0, len(posts) - self.max_meta_posts)
            if trim_count:
                oldest_keys = sorted(
                    posts,
                    key=lambda key: str(posts[key].get("first_seen_at") or ""),
                )[:trim_count]
                for key in oldest_keys:
                    del posts[key]
                print(
                    f"community_post_meta: pruned {trim_count} oldest posts",
                    file=sys.stderr,
                )
            self._post_meta["version"] = 1
            self._post_meta["updated_at"] = timestamp
            self.post_meta_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.post_meta_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(self._post_meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.post_meta_path)
            self._post_meta_dirty = False
