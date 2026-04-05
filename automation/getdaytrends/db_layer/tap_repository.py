"""Persistence helpers for TAP product snapshots and premium alert queues."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from . import _json_text, sqlite_write_lock

try:
    from ..tap.product_feed import TapBoard, TapBoardItem
except ImportError:
    from tap.product_feed import TapBoard, TapBoardItem


def _json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_country(country: str) -> str:
    return (country or "").strip().lower()


def _normalize_keyword(keyword: str) -> str:
    return "".join(ch for ch in (keyword or "").strip().lower() if ch.isalnum())


def _merge_json_dict(base: dict | None, patch: dict | None) -> dict:
    merged = dict(base or {})
    if patch:
        for key, value in patch.items():
            merged[key] = value
    return merged


def _is_snapshot_fresh(generated_at: str, max_age_minutes: int) -> bool:
    if max_age_minutes <= 0:
        return True
    if not generated_at:
        return False
    try:
        parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return False

    now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.utcnow()
    age_minutes = (now - parsed).total_seconds() / 60
    return age_minutes <= max_age_minutes


async def save_tap_board_snapshot(
    conn,
    board: TapBoard,
    *,
    source: str = "tap_service",
) -> str:
    """Persist one TAP board snapshot and its flattened items."""

    snapshot_id = board.snapshot_id or f"tap_{uuid4().hex}"
    generated_at = board.generated_at or datetime.utcnow().isoformat()
    created_at = datetime.utcnow().isoformat()

    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO tap_snapshots (
                   snapshot_id, target_country, total_detected, teaser_count,
                   generated_at, future_dependencies, source, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                _normalize_country(board.target_country),
                board.total_detected,
                board.teaser_count,
                generated_at,
                _json_text(board.future_dependencies),
                source,
                created_at,
            ),
        )

        for item_order, item in enumerate(board.items):
            await conn.execute(
                """INSERT INTO tap_snapshot_items (
                       snapshot_id, item_order, keyword, source_country,
                       target_countries, viral_score, priority, time_gap_hours,
                       paywall_tier, public_teaser, recommended_platforms,
                       recommended_angle, execution_notes, publish_window_json,
                       revenue_play_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    item_order,
                    item.keyword,
                    _normalize_country(item.source_country),
                    _json_text(item.target_countries),
                    item.viral_score,
                    item.priority,
                    item.time_gap_hours,
                    item.paywall_tier.value,
                    item.public_teaser,
                    _json_text(item.recommended_platforms),
                    item.recommended_angle,
                    _json_text(item.execution_notes),
                    _json_text(item.publish_window.to_dict() if item.publish_window else {}),
                    _json_text(item.revenue_play.to_dict() if item.revenue_play else {}),
                    created_at,
                ),
            )

        await conn.commit()

    board.snapshot_id = snapshot_id
    board.snapshot_source = source
    return snapshot_id


async def get_latest_tap_board_snapshot(
    conn,
    *,
    target_country: str = "",
    max_age_minutes: int = 0,
) -> TapBoard | None:
    """Load the newest TAP board snapshot for a target market."""

    normalized_country = _normalize_country(target_country)

    if normalized_country:
        cursor = await conn.execute(
            """SELECT snapshot_id, target_country, total_detected, teaser_count,
                      generated_at, future_dependencies, source
               FROM tap_snapshots
               WHERE target_country = ?
               ORDER BY created_at DESC, id DESC
               LIMIT 1""",
            (normalized_country,),
        )
    else:
        cursor = await conn.execute(
            """SELECT snapshot_id, target_country, total_detected, teaser_count,
                      generated_at, future_dependencies, source
               FROM tap_snapshots
               ORDER BY created_at DESC, id DESC
               LIMIT 1"""
        )

    snapshot_row = await cursor.fetchone()
    if not snapshot_row:
        return None

    snapshot = dict(snapshot_row)
    if not _is_snapshot_fresh(snapshot.get("generated_at", ""), max_age_minutes):
        return None

    items_cursor = await conn.execute(
        """SELECT keyword, source_country, target_countries, viral_score, priority,
                  time_gap_hours, paywall_tier, public_teaser, recommended_platforms,
                  recommended_angle, execution_notes, publish_window_json,
                  revenue_play_json
           FROM tap_snapshot_items
           WHERE snapshot_id = ?
           ORDER BY item_order ASC, id ASC""",
        (snapshot["snapshot_id"],),
    )
    item_rows = await items_cursor.fetchall()

    items = [
        TapBoardItem.from_dict(
            {
                "keyword": row["keyword"],
                "source_country": row["source_country"],
                "target_countries": _json_list(row["target_countries"]),
                "viral_score": row["viral_score"],
                "priority": row["priority"],
                "time_gap_hours": row["time_gap_hours"],
                "paywall_tier": row["paywall_tier"],
                "public_teaser": row["public_teaser"],
                "recommended_platforms": _json_list(row["recommended_platforms"]),
                "recommended_angle": row["recommended_angle"],
                "execution_notes": _json_list(row["execution_notes"]),
                "publish_window": _json_dict(row["publish_window_json"]),
                "revenue_play": _json_dict(row["revenue_play_json"]),
            }
        )
        for row in item_rows
    ]

    return TapBoard(
        snapshot_id=snapshot["snapshot_id"],
        generated_at=snapshot["generated_at"],
        target_country=_normalize_country(snapshot["target_country"]),
        total_detected=int(snapshot["total_detected"] or 0),
        teaser_count=int(snapshot["teaser_count"] or 0),
        items=items,
        snapshot_source=snapshot.get("source", "tap_service"),
        delivery_mode="cached",
        future_dependencies=[str(item) for item in _json_list(snapshot.get("future_dependencies"))],
    )


def _build_alert_message(item: TapBoardItem, target_country: str) -> str:
    target = (_normalize_country(target_country) or "target").upper()
    source = (_normalize_country(item.source_country) or "source").upper()
    platforms = ", ".join(item.recommended_platforms[:3]) or "x"
    return (
        f"[TAP PRO] {target} gap open: '{item.keyword}' is already moving in {source}. "
        f"Priority {item.priority:.1f}, viral {item.viral_score}. "
        f"Ship on {platforms} before the gap closes."
    )


async def _has_recent_alert(
    conn,
    *,
    dedupe_key: str,
    cooldown_minutes: int,
) -> bool:
    if cooldown_minutes <= 0:
        return False

    cursor = await conn.execute(
        """SELECT queued_at
           FROM tap_alert_queue
           WHERE dedupe_key = ?
           ORDER BY queued_at DESC, id DESC
           LIMIT 1""",
        (dedupe_key,),
    )
    row = await cursor.fetchone()
    if not row or not row["queued_at"]:
        return False

    try:
        queued_at = datetime.fromisoformat(str(row["queued_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False

    now = datetime.now(queued_at.tzinfo) if queued_at.tzinfo is not None else datetime.utcnow()
    age_minutes = (now - queued_at).total_seconds() / 60
    return age_minutes < cooldown_minutes


async def enqueue_tap_alerts(
    conn,
    board: TapBoard,
    *,
    target_country: str = "",
    top_k: int = 3,
    min_priority: float = 80.0,
    min_viral_score: int = 75,
    cooldown_minutes: int = 180,
) -> int:
    """Queue premium TAP alerts from a board while respecting cooldown windows."""

    normalized_target = _normalize_country(target_country or board.target_country)
    queued_count = 0
    candidates = [
        item
        for item in board.items
        if item.priority >= min_priority and item.viral_score >= min_viral_score
    ][: max(0, top_k)]

    async with sqlite_write_lock(conn):
        for item in candidates:
            dedupe_key = f"{normalized_target}:{_normalize_keyword(item.keyword)}"
            if await _has_recent_alert(conn, dedupe_key=dedupe_key, cooldown_minutes=cooldown_minutes):
                continue

            queued_at = datetime.utcnow().isoformat()
            await conn.execute(
                """INSERT INTO tap_alert_queue (
                       alert_id, snapshot_id, dedupe_key, target_country, keyword,
                       source_country, paywall_tier, priority, viral_score,
                       alert_message, metadata_json, lifecycle_status, queued_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"tapa_{uuid4().hex}",
                    board.snapshot_id,
                    dedupe_key,
                    normalized_target,
                    item.keyword,
                    _normalize_country(item.source_country),
                    item.paywall_tier.value,
                    item.priority,
                    item.viral_score,
                    _build_alert_message(item, normalized_target),
                    _json_text(
                        {
                            "recommended_platforms": item.recommended_platforms,
                            "recommended_angle": item.recommended_angle,
                            "time_gap_hours": item.time_gap_hours,
                            "public_teaser": item.public_teaser,
                        }
                    ),
                    "queued",
                    queued_at,
                ),
            )
            queued_count += 1

        await conn.commit()

    return queued_count


async def get_tap_alert_queue_snapshot(
    conn,
    *,
    limit: int = 50,
    lifecycle_status: str = "queued",
    target_country: str = "",
) -> dict:
    """Return a compact view of the TAP premium alert queue."""

    normalized_status = (lifecycle_status or "").strip().lower()
    normalized_country = _normalize_country(target_country)
    clauses: list[str] = []
    params: list[str] = []
    if normalized_status:
        clauses.append("LOWER(lifecycle_status) = ?")
        params.append(normalized_status)
    if normalized_country:
        clauses.append("target_country = ?")
        params.append(normalized_country)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    counts_cursor = await conn.execute(
        f"""SELECT lifecycle_status, COUNT(*) AS count
            FROM tap_alert_queue
            {where_clause}
            GROUP BY lifecycle_status""",
        tuple(params),
    )
    count_rows = await counts_cursor.fetchall()

    items_cursor = await conn.execute(
        f"""SELECT alert_id, snapshot_id, target_country, keyword, source_country,
                  paywall_tier, priority, viral_score, alert_message,
                  metadata_json, lifecycle_status, queued_at, dispatched_at, last_attempt_at
           FROM tap_alert_queue
           {where_clause}
            ORDER BY queued_at DESC, id DESC
            LIMIT ?""",
        tuple(params) + (limit,),
    )
    item_rows = await items_cursor.fetchall()

    return {
        "counts": {row["lifecycle_status"]: row["count"] for row in count_rows},
        "items": [
            {
                "alert_id": row["alert_id"],
                "snapshot_id": row["snapshot_id"],
                "target_country": row["target_country"],
                "keyword": row["keyword"],
                "source_country": row["source_country"],
                "paywall_tier": row["paywall_tier"],
                "priority": row["priority"],
                "viral_score": row["viral_score"],
                "alert_message": row["alert_message"],
                "metadata": _json_dict(row["metadata_json"]),
                "lifecycle_status": row["lifecycle_status"],
                "queued_at": row["queued_at"],
                "dispatched_at": row["dispatched_at"],
                "last_attempt_at": row["last_attempt_at"],
            }
            for row in item_rows
        ],
    }


async def get_tap_alert_delivery_batch(
    conn,
    *,
    limit: int = 10,
    target_country: str = "",
    lifecycle_status: str = "queued",
) -> list[dict]:
    """Fetch the next TAP alerts that are eligible for channel delivery."""

    normalized_status = (lifecycle_status or "queued").strip().lower() or "queued"
    normalized_country = _normalize_country(target_country)

    clauses = ["LOWER(lifecycle_status) = ?"]
    params: list = [normalized_status]
    if normalized_country:
        clauses.append("target_country = ?")
        params.append(normalized_country)

    cursor = await conn.execute(
        f"""SELECT alert_id, snapshot_id, target_country, keyword, source_country,
                  paywall_tier, priority, viral_score, alert_message,
                  metadata_json, lifecycle_status, queued_at, dispatched_at, last_attempt_at
           FROM tap_alert_queue
           WHERE {' AND '.join(clauses)}
           ORDER BY queued_at ASC, id ASC
           LIMIT ?""",
        tuple(params + [max(1, limit)]),
    )
    rows = await cursor.fetchall()
    return [
        {
            "alert_id": row["alert_id"],
            "snapshot_id": row["snapshot_id"],
            "target_country": row["target_country"],
            "keyword": row["keyword"],
            "source_country": row["source_country"],
            "paywall_tier": row["paywall_tier"],
            "priority": row["priority"],
            "viral_score": row["viral_score"],
            "alert_message": row["alert_message"],
            "metadata": _json_dict(row["metadata_json"]),
            "lifecycle_status": row["lifecycle_status"],
            "queued_at": row["queued_at"],
            "dispatched_at": row["dispatched_at"],
            "last_attempt_at": row["last_attempt_at"],
        }
        for row in rows
    ]


async def update_tap_alert_delivery_status(
    conn,
    *,
    alert_id: str,
    lifecycle_status: str,
    dispatched_at: str | None = None,
    last_attempt_at: str | None = None,
    metadata_patch: dict | None = None,
) -> bool:
    """Update delivery lifecycle timestamps for one TAP alert."""

    normalized_status = (lifecycle_status or "").strip().lower()
    if not alert_id or not normalized_status:
        return False

    attempted_at = last_attempt_at or datetime.utcnow().isoformat()

    async with sqlite_write_lock(conn):
        existing_cursor = await conn.execute(
            "SELECT metadata_json FROM tap_alert_queue WHERE alert_id = ?",
            (alert_id,),
        )
        existing_row = await existing_cursor.fetchone()
        if existing_row is None:
            return False
        merged_metadata = _merge_json_dict(_json_dict(existing_row["metadata_json"]), metadata_patch)
        cursor = await conn.execute(
            """UPDATE tap_alert_queue
               SET lifecycle_status = ?,
                   dispatched_at = COALESCE(?, dispatched_at),
                   last_attempt_at = ?,
                   metadata_json = ?
                WHERE alert_id = ?""",
            (
                normalized_status,
                dispatched_at,
                attempted_at,
                _json_text(merged_metadata),
                alert_id,
            ),
        )
        await conn.commit()

    return bool(cursor.rowcount)
