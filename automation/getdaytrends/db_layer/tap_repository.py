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


def _normalize_event_type(event_type: str) -> str:
    normalized = (event_type or "").strip().lower()
    aliases = {
        "open": "view",
        "impression": "view",
        "cta_click": "click",
        "buy": "purchase",
        "checkout": "checkout_open",
    }
    return aliases.get(normalized, normalized)


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


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


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


async def record_tap_deal_room_event(
    conn,
    *,
    keyword: str,
    event_type: str,
    snapshot_id: str = "",
    target_country: str = "",
    audience_segment: str = "",
    package_tier: str = "premium_alert_bundle",
    offer_tier: str = "premium",
    price_anchor: str = "",
    checkout_handle: str = "",
    session_id: str = "",
    actor_id: str = "",
    revenue_value: float = 0.0,
    metadata: dict | None = None,
    event_id: str = "",
) -> str:
    """Persist one TAP deal-room funnel event."""

    normalized_keyword = (keyword or "").strip()
    normalized_event_type = _normalize_event_type(event_type)
    if not normalized_keyword:
        raise ValueError("keyword is required")
    if normalized_event_type not in {"view", "click", "checkout_open", "purchase"}:
        raise ValueError(f"unsupported deal-room event_type: {event_type}")

    resolved_event_id = event_id or f"tapde_{uuid4().hex}"
    if event_id:
        existing_cursor = await conn.execute(
            "SELECT event_id FROM tap_deal_room_events WHERE event_id = ? LIMIT 1",
            (resolved_event_id,),
        )
        existing_row = await existing_cursor.fetchone()
        if existing_row:
            return resolved_event_id
    payload = _merge_json_dict(
        metadata or {},
        {
            "event_type": normalized_event_type,
            "package_tier": package_tier,
            "offer_tier": offer_tier,
        },
    )

    async with sqlite_write_lock(conn):
        try:
            await conn.execute(
                """INSERT INTO tap_deal_room_events (
                       event_id, snapshot_id, keyword, target_country, audience_segment,
                       package_tier, offer_tier, event_type, price_anchor, checkout_handle,
                       session_id, actor_id, revenue_value, metadata_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolved_event_id,
                    snapshot_id,
                    normalized_keyword,
                    _normalize_country(target_country),
                    (audience_segment or "").strip().lower(),
                    (package_tier or "").strip().lower(),
                    (offer_tier or "").strip().lower(),
                    normalized_event_type,
                    price_anchor,
                    checkout_handle,
                    session_id,
                    actor_id,
                    float(revenue_value or 0.0),
                    _json_text(payload),
                    datetime.utcnow().isoformat(),
                ),
            )
            await conn.commit()
        except Exception as exc:
            message = str(exc).lower()
            if event_id and "event_id" in message and ("unique" in message or "duplicate" in message):
                return resolved_event_id
            raise

    return resolved_event_id


async def upsert_tap_checkout_session(
    conn,
    *,
    checkout_session_id: str,
    checkout_handle: str = "",
    snapshot_id: str = "",
    keyword: str,
    target_country: str = "",
    audience_segment: str = "",
    package_tier: str = "premium_alert_bundle",
    offer_tier: str = "premium",
    session_status: str = "created",
    payment_status: str = "",
    currency: str = "usd",
    quoted_price_value: float = 0.0,
    revenue_value: float = 0.0,
    checkout_url: str = "",
    actor_id: str = "",
    stripe_customer_id: str = "",
    stripe_event_id: str = "",
    metadata: dict | None = None,
    completed_at: str | None = None,
) -> str:
    """Insert or refresh one TAP checkout session row."""

    normalized_session_id = (checkout_session_id or "").strip()
    normalized_keyword = (keyword or "").strip()
    if not normalized_session_id:
        raise ValueError("checkout_session_id is required")
    if not normalized_keyword:
        raise ValueError("keyword is required")

    now = datetime.utcnow().isoformat()
    normalized_status = (session_status or "created").strip().lower() or "created"
    normalized_payment = (payment_status or "").strip().lower()
    payload = _merge_json_dict(
        metadata or {},
        {
            "checkout_handle": checkout_handle,
            "session_status": normalized_status,
            "payment_status": normalized_payment,
        },
    )

    async with sqlite_write_lock(conn):
        existing_cursor = await conn.execute(
            "SELECT metadata_json FROM tap_checkout_sessions WHERE checkout_session_id = ? LIMIT 1",
            (normalized_session_id,),
        )
        existing_row = await existing_cursor.fetchone()
        if existing_row:
            merged_metadata = _merge_json_dict(_json_dict(existing_row["metadata_json"]), payload)
            await conn.execute(
                """UPDATE tap_checkout_sessions
                   SET checkout_handle = ?,
                       snapshot_id = ?,
                       keyword = ?,
                       target_country = ?,
                       audience_segment = ?,
                       package_tier = ?,
                       offer_tier = ?,
                       session_status = ?,
                       payment_status = ?,
                       currency = ?,
                       quoted_price_value = ?,
                       revenue_value = ?,
                       checkout_url = ?,
                       actor_id = ?,
                       stripe_customer_id = ?,
                       stripe_event_id = ?,
                       metadata_json = ?,
                       updated_at = ?,
                       completed_at = COALESCE(?, completed_at)
                 WHERE checkout_session_id = ?""",
                (
                    checkout_handle,
                    snapshot_id,
                    normalized_keyword,
                    _normalize_country(target_country),
                    (audience_segment or "").strip().lower(),
                    (package_tier or "").strip().lower(),
                    (offer_tier or "").strip().lower(),
                    normalized_status,
                    normalized_payment,
                    (currency or "usd").strip().lower(),
                    float(quoted_price_value or 0.0),
                    float(revenue_value or 0.0),
                    checkout_url,
                    actor_id,
                    stripe_customer_id,
                    stripe_event_id,
                    _json_text(merged_metadata),
                    now,
                    completed_at,
                    normalized_session_id,
                ),
            )
        else:
            await conn.execute(
                """INSERT INTO tap_checkout_sessions (
                       checkout_session_id, checkout_handle, snapshot_id, keyword,
                       target_country, audience_segment, package_tier, offer_tier,
                       session_status, payment_status, currency, quoted_price_value,
                       revenue_value, checkout_url, actor_id, stripe_customer_id,
                       stripe_event_id, metadata_json, created_at, updated_at, completed_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    normalized_session_id,
                    checkout_handle,
                    snapshot_id,
                    normalized_keyword,
                    _normalize_country(target_country),
                    (audience_segment or "").strip().lower(),
                    (package_tier or "").strip().lower(),
                    (offer_tier or "").strip().lower(),
                    normalized_status,
                    normalized_payment,
                    (currency or "usd").strip().lower(),
                    float(quoted_price_value or 0.0),
                    float(revenue_value or 0.0),
                    checkout_url,
                    actor_id,
                    stripe_customer_id,
                    stripe_event_id,
                    _json_text(payload),
                    now,
                    now,
                    completed_at,
                ),
            )
        await conn.commit()

    return normalized_session_id


async def mark_tap_checkout_session_completed(
    conn,
    *,
    checkout_session_id: str,
    payment_status: str = "paid",
    revenue_value: float = 0.0,
    stripe_customer_id: str = "",
    stripe_event_id: str = "",
    metadata: dict | None = None,
) -> bool:
    """Mark one TAP checkout session as completed/paid."""

    normalized_session_id = (checkout_session_id or "").strip()
    if not normalized_session_id:
        return False

    completed_at = datetime.utcnow().isoformat()
    async with sqlite_write_lock(conn):
        existing_cursor = await conn.execute(
            "SELECT metadata_json FROM tap_checkout_sessions WHERE checkout_session_id = ? LIMIT 1",
            (normalized_session_id,),
        )
        existing_row = await existing_cursor.fetchone()
        if existing_row is None:
            return False
        merged_metadata = _merge_json_dict(_json_dict(existing_row["metadata_json"]), metadata or {})
        cursor = await conn.execute(
            """UPDATE tap_checkout_sessions
               SET session_status = 'completed',
                   payment_status = ?,
                   revenue_value = ?,
                   stripe_customer_id = COALESCE(NULLIF(?, ''), stripe_customer_id),
                   stripe_event_id = COALESCE(NULLIF(?, ''), stripe_event_id),
                   metadata_json = ?,
                   updated_at = ?,
                   completed_at = ?
             WHERE checkout_session_id = ?""",
            (
                (payment_status or "paid").strip().lower(),
                float(revenue_value or 0.0),
                stripe_customer_id,
                stripe_event_id,
                _json_text(merged_metadata),
                completed_at,
                completed_at,
                normalized_session_id,
            ),
        )
        await conn.commit()

    return bool(cursor.rowcount)


async def get_tap_checkout_session_summary(
    conn,
    *,
    days: int = 30,
    target_country: str = "",
    audience_segment: str = "",
    package_tier: str = "",
    limit: int = 10,
) -> dict:
    """Return checkout-session ops summary for TAP deal-room commerce."""

    cutoff = datetime.utcnow().timestamp() - (max(1, days) * 86400)
    cutoff_iso = datetime.utcfromtimestamp(cutoff).isoformat()
    clauses = ["created_at >= ?"]
    params: list = [cutoff_iso]

    normalized_country = _normalize_country(target_country)
    normalized_segment = (audience_segment or "").strip().lower()
    normalized_package = (package_tier or "").strip().lower()
    if normalized_country:
        clauses.append("target_country = ?")
        params.append(normalized_country)
    if normalized_segment:
        clauses.append("audience_segment = ?")
        params.append(normalized_segment)
    if normalized_package:
        clauses.append("package_tier = ?")
        params.append(normalized_package)

    where_clause = f"WHERE {' AND '.join(clauses)}"
    totals_cursor = await conn.execute(
        f"""SELECT
                  COUNT(*) AS created,
                  COALESCE(SUM(CASE WHEN session_status = 'completed' THEN 1 ELSE 0 END), 0) AS completed,
                  COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END), 0) AS paid,
                  COALESCE(ROUND(SUM(quoted_price_value), 2), 0.0) AS quoted_revenue,
                  COALESCE(ROUND(SUM(CASE WHEN session_status = 'completed' THEN revenue_value ELSE 0 END), 2), 0.0) AS captured_revenue
           FROM tap_checkout_sessions
           {where_clause}""",
        tuple(params),
    )
    totals_row = await totals_cursor.fetchone()
    totals = dict(totals_row) if totals_row else {}
    totals.setdefault("created", 0)
    totals.setdefault("completed", 0)
    totals.setdefault("paid", 0)
    totals.setdefault("quoted_revenue", 0.0)
    totals.setdefault("captured_revenue", 0.0)
    totals["completion_rate"] = _safe_rate(float(totals["completed"]), float(totals["created"]))

    items_cursor = await conn.execute(
        f"""SELECT checkout_session_id, checkout_handle, snapshot_id, keyword,
                  target_country, audience_segment, package_tier, offer_tier,
                  session_status, payment_status, currency, quoted_price_value,
                  revenue_value, checkout_url, actor_id, stripe_customer_id,
                  stripe_event_id, metadata_json, created_at, updated_at, completed_at
           FROM tap_checkout_sessions
           {where_clause}
           ORDER BY updated_at DESC, id DESC
           LIMIT ?""",
        tuple(params + [max(1, limit)]),
    )
    item_rows = await items_cursor.fetchall()

    return {
        "window_days": max(1, days),
        "filters": {
            "target_country": normalized_country,
            "audience_segment": normalized_segment,
            "package_tier": normalized_package,
        },
        "totals": totals,
        "items": [
            {
                "checkout_session_id": row["checkout_session_id"],
                "checkout_handle": row["checkout_handle"],
                "snapshot_id": row["snapshot_id"],
                "keyword": row["keyword"],
                "target_country": row["target_country"],
                "audience_segment": row["audience_segment"],
                "package_tier": row["package_tier"],
                "offer_tier": row["offer_tier"],
                "session_status": row["session_status"],
                "payment_status": row["payment_status"],
                "currency": row["currency"],
                "quoted_price_value": row["quoted_price_value"],
                "revenue_value": row["revenue_value"],
                "checkout_url": row["checkout_url"],
                "actor_id": row["actor_id"],
                "stripe_customer_id": row["stripe_customer_id"],
                "stripe_event_id": row["stripe_event_id"],
                "metadata": _json_dict(row["metadata_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "completed_at": row["completed_at"],
            }
            for row in item_rows
        ],
    }


async def get_tap_deal_room_funnel(
    conn,
    *,
    days: int = 30,
    target_country: str = "",
    audience_segment: str = "",
    package_tier: str = "",
    limit: int = 20,
) -> dict:
    """Summarize TAP deal-room funnel performance for learning loops."""

    cutoff = datetime.utcnow().timestamp() - (max(1, days) * 86400)
    cutoff_iso = datetime.utcfromtimestamp(cutoff).isoformat()
    clauses = ["created_at >= ?"]
    params: list = [cutoff_iso]

    normalized_country = _normalize_country(target_country)
    normalized_segment = (audience_segment or "").strip().lower()
    normalized_package = (package_tier or "").strip().lower()

    if normalized_country:
        clauses.append("target_country = ?")
        params.append(normalized_country)
    if normalized_segment:
        clauses.append("audience_segment = ?")
        params.append(normalized_segment)
    if normalized_package:
        clauses.append("package_tier = ?")
        params.append(normalized_package)

    where_clause = f"WHERE {' AND '.join(clauses)}"
    totals_cursor = await conn.execute(
        f"""SELECT
                  COALESCE(SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END), 0) AS views,
                  COALESCE(SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicks,
                  COALESCE(SUM(CASE WHEN event_type = 'checkout_open' THEN 1 ELSE 0 END), 0) AS checkout_opens,
                  COALESCE(SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END), 0) AS purchases,
                  COALESCE(ROUND(SUM(revenue_value), 2), 0.0) AS revenue
           FROM tap_deal_room_events
           {where_clause}""",
        tuple(params),
    )
    totals_row = await totals_cursor.fetchone()
    totals = dict(totals_row) if totals_row else {}
    totals.setdefault("views", 0)
    totals.setdefault("clicks", 0)
    totals.setdefault("checkout_opens", 0)
    totals.setdefault("purchases", 0)
    totals.setdefault("revenue", 0.0)
    totals["ctr"] = _safe_rate(float(totals["clicks"]), float(totals["views"]))
    totals["checkout_rate"] = _safe_rate(float(totals["checkout_opens"]), float(totals["clicks"]))
    totals["purchase_rate"] = _safe_rate(float(totals["purchases"]), float(totals["clicks"]))
    totals["view_to_purchase_rate"] = _safe_rate(float(totals["purchases"]), float(totals["views"]))

    items_cursor = await conn.execute(
        f"""SELECT keyword, package_tier, offer_tier,
                  COALESCE(SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END), 0) AS views,
                  COALESCE(SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicks,
                  COALESCE(SUM(CASE WHEN event_type = 'checkout_open' THEN 1 ELSE 0 END), 0) AS checkout_opens,
                  COALESCE(SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END), 0) AS purchases,
                  COALESCE(ROUND(SUM(revenue_value), 2), 0.0) AS revenue,
                  MAX(created_at) AS last_event_at
           FROM tap_deal_room_events
           {where_clause}
           GROUP BY keyword, package_tier, offer_tier
           ORDER BY purchases DESC, clicks DESC, views DESC, revenue DESC
           LIMIT ?""",
        tuple(params + [max(1, limit)]),
    )
    item_rows = await items_cursor.fetchall()

    items = []
    for row in item_rows:
        item = dict(row)
        item["ctr"] = _safe_rate(float(item["clicks"]), float(item["views"]))
        item["checkout_rate"] = _safe_rate(float(item["checkout_opens"]), float(item["clicks"]))
        item["purchase_rate"] = _safe_rate(float(item["purchases"]), float(item["clicks"]))
        item["view_to_purchase_rate"] = _safe_rate(float(item["purchases"]), float(item["views"]))
        items.append(item)

    return {
        "window_days": max(1, days),
        "filters": {
            "target_country": normalized_country,
            "audience_segment": normalized_segment,
            "package_tier": normalized_package,
        },
        "totals": totals,
        "items": items,
    }


async def get_tap_deal_room_offer_stats(
    conn,
    *,
    days: int = 30,
    target_country: str = "",
    audience_segment: str = "",
    package_tier: str = "",
) -> dict[str, dict]:
    """Return a compact keyword+tier stats map for deal-room personalization."""

    summary = await get_tap_deal_room_funnel(
        conn,
        days=days,
        target_country=target_country,
        audience_segment=audience_segment,
        package_tier=package_tier,
        limit=200,
    )
    stats_map: dict[str, dict] = {}
    for item in summary.get("items", []):
        key = f"{_normalize_keyword(item['keyword'])}::{(item.get('offer_tier') or '').strip().lower()}"
        stats_map[key] = item
    return stats_map
