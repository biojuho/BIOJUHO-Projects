"""Persist directly observed community-to-aggregator lead times."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class LeadTimeTracker:
    """Record observation timestamps without inferring unseen publication times."""

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "items": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
            return {"version": 1, "items": {}}
        return payload

    @staticmethod
    def _key(item: dict[str, Any]) -> str:
        source = str(item.get("community_source") or "fmkorea").casefold()
        return f"{source}:{item.get('id')}"

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.state_path)

    def record_observations(
        self,
        direct_items: list[dict[str, Any]],
        aggregator_items: list[dict[str, Any]],
        *,
        observed_at: datetime,
    ) -> None:
        """Record one poll atomically; simultaneous first sightings claim no lead."""
        timestamp = observed_at.astimezone(UTC).isoformat()
        direct_keys = {self._key(item) for item in direct_items}
        aggregator_keys = {self._key(item) for item in aggregator_items}
        item_by_key = {self._key(item): item for item in [*direct_items, *aggregator_items]}
        records = self._state.setdefault("items", {})
        changed = False

        for key in direct_keys | aggregator_keys:
            record = records.setdefault(
                key,
                {
                    "community_source": str(item_by_key[key].get("community_source") or "fmkorea"),
                    "post_id": str(item_by_key[key].get("id") or ""),
                    "direct_first_seen_at": None,
                    "aggregator_first_seen_at": None,
                },
            )
            if key in direct_keys and not record.get("direct_first_seen_at"):
                record["direct_first_seen_at"] = timestamp
                changed = True
            if key in aggregator_keys and not record.get("aggregator_first_seen_at"):
                record["aggregator_first_seen_at"] = timestamp
                changed = True

        if changed:
            self._prune(observed_at)
            self._state["updated_at"] = timestamp
            self._save()

    def _prune(self, now: datetime) -> None:
        cutoff = now.astimezone(UTC) - timedelta(days=30)
        records = self._state.get("items", {})
        kept: list[tuple[str, dict[str, Any], datetime]] = []
        for key, record in records.items():
            latest_raw = record.get("aggregator_first_seen_at") or record.get("direct_first_seen_at")
            try:
                latest = datetime.fromisoformat(str(latest_raw)).astimezone(UTC)
            except (TypeError, ValueError):
                continue
            if latest >= cutoff:
                kept.append((key, record, latest))
        kept.sort(key=lambda value: value[2], reverse=True)
        self._state["items"] = {key: record for key, record, _ in kept[:5000]}

    def metrics_for(self, item: dict[str, Any]) -> dict[str, Any]:
        record = self._state.get("items", {}).get(self._key(item), {})
        direct_raw = record.get("direct_first_seen_at")
        aggregator_raw = record.get("aggregator_first_seen_at")
        lead_seconds: int | None = None
        status = "unmeasured"
        if direct_raw and aggregator_raw:
            direct_at = datetime.fromisoformat(direct_raw)
            aggregator_at = datetime.fromisoformat(aggregator_raw)
            delta = round((aggregator_at - direct_at).total_seconds())
            if delta > 0:
                lead_seconds = delta
                status = "measured"
            elif delta == 0:
                status = "same_poll"
            else:
                status = "aggregator_first"
        elif direct_raw:
            status = "awaiting_aggregator"
        elif aggregator_raw:
            status = "aggregator_only"
        first_seen_values = [value for value in (direct_raw, aggregator_raw) if value]
        return {
            "first_seen_at": min(first_seen_values) if first_seen_values else None,
            "direct_first_seen_at": direct_raw,
            "aggregator_first_seen_at": aggregator_raw,
            "lead_seconds": lead_seconds,
            "lead_minutes": round(lead_seconds / 60, 1) if lead_seconds is not None else None,
            "lead_status": status,
        }
