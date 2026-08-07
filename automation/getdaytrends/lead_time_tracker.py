"""Persist directly observed community-to-aggregator lead times."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_lead_time_store(path: Path) -> dict[str, Any]:
    """Read a lead-time store without mutating it."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"version": 1, "items": {}, "updated_at": None}
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
        return {"version": 1, "items": {}, "updated_at": None}
    return payload


def summarize_lead_time_store(payload: dict[str, Any]) -> dict[str, Any]:
    """Aggregate evidence from a stored observation file.

    Definition used here (and by metrics_for when both timestamps exist):
    lead_minutes = (aggregator_first_seen_at − direct_first_seen_at) in minutes.
    Positive means we saw the post on a direct community listing before IssueLink;
    negative means the aggregator had it first (we were late).

    metrics_for only exposes positive leads as lead_minutes. This summary keeps the
    signed distribution so late detections are not hidden.
    """
    items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    status_counts: Counter[str] = Counter()
    signed_minutes: list[float] = []
    by_source: dict[str, list[float]] = {}
    timestamps: list[datetime] = []

    for key, record in items.items():
        if not isinstance(record, dict):
            continue
        direct_at = _parse_iso(record.get("direct_first_seen_at"))
        aggregator_at = _parse_iso(record.get("aggregator_first_seen_at"))
        source = str(record.get("community_source") or str(key).split(":", 1)[0] or "unknown")
        for stamp in (direct_at, aggregator_at):
            if stamp is not None:
                timestamps.append(stamp)

        if direct_at and aggregator_at:
            delta_seconds = (aggregator_at - direct_at).total_seconds()
            delta_minutes = delta_seconds / 60.0
            signed_minutes.append(delta_minutes)
            by_source.setdefault(source, []).append(delta_minutes)
            if delta_seconds > 0:
                status_counts["measured"] += 1
            elif delta_seconds == 0:
                status_counts["same_poll"] += 1
            else:
                status_counts["aggregator_first"] += 1
        elif direct_at:
            status_counts["awaiting_aggregator"] += 1
        elif aggregator_at:
            status_counts["aggregator_only"] += 1
        else:
            status_counts["empty"] += 1

    n_both = len(signed_minutes)
    positive = [value for value in signed_minutes if value > 0]
    negative = [value for value in signed_minutes if value < 0]
    zero = [value for value in signed_minutes if value == 0]

    def _pct(part: int, whole: int) -> float | None:
        return round(100.0 * part / whole, 1) if whole else None

    source_rows = []
    for source, values in sorted(by_source.items(), key=lambda item: (-len(item[1]), item[0])):
        source_rows.append(
            {
                "community_source": source,
                "paired_count": len(values),
                "median_lead_minutes": round(median(values), 2),
                "positive_share_pct": _pct(sum(1 for value in values if value > 0), len(values)),
                "negative_share_pct": _pct(sum(1 for value in values if value < 0), len(values)),
                "zero_share_pct": _pct(sum(1 for value in values if value == 0), len(values)),
            }
        )

    buckets = Counter()
    for value in signed_minutes:
        if value < -60:
            buckets["lt_-60m"] += 1
        elif value < -15:
            buckets["-60_to_-15m"] += 1
        elif value < 0:
            buckets["-15_to_0m"] += 1
        elif value == 0:
            buckets["0m"] += 1
        elif value <= 15:
            buckets["0_to_15m"] += 1
        elif value <= 60:
            buckets["15_to_60m"] += 1
        elif value <= 180:
            buckets["60_to_180m"] += 1
        else:
            buckets["gt_180m"] += 1

    return {
        "definition": (
            "lead_minutes = aggregator_first_seen_at − direct_first_seen_at. "
            "Positive: direct listing first; negative: IssueLink/aggregator first."
        ),
        "store_updated_at": payload.get("updated_at"),
        "record_count": len(items),
        "paired_count": n_both,
        "pair_rate_pct": _pct(n_both, len(items)),
        "status_counts": dict(status_counts),
        "time_span_utc": {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None,
        },
        "signed_lead": {
            "n": n_both,
            "median_minutes": round(median(signed_minutes), 2) if signed_minutes else None,
            "mean_minutes": round(sum(signed_minutes) / n_both, 2) if n_both else None,
            "positive_count": len(positive),
            "positive_share_pct": _pct(len(positive), n_both),
            "positive_median_minutes": round(median(positive), 2) if positive else None,
            "negative_count": len(negative),
            "negative_share_pct": _pct(len(negative), n_both),
            "negative_median_minutes": round(median(negative), 2) if negative else None,
            "zero_count": len(zero),
            "zero_share_pct": _pct(len(zero), n_both),
            "buckets": dict(buckets),
        },
        "by_source": source_rows,
        "evidence_grade": (
            "insufficient"
            if n_both < 10
            else "directional_to_preliminary"
            if n_both < 50
            else "preliminary"
        ),
    }


class LeadTimeTracker:
    """Record observation timestamps without inferring unseen publication times."""

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        return load_lead_time_store(self.state_path)

    @staticmethod
    def _key(item: dict[str, Any]) -> str:
        source = str(item.get("community_source") or "fmkorea").casefold()
        return f"{source}:{item.get('id')}"

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.state_path)

    def summarize(self) -> dict[str, Any]:
        """Read-only aggregate of the current in-memory store."""
        return summarize_lead_time_store(self._state)

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
