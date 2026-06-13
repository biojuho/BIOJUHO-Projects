"""
Service helpers for TAP product surfaces.

This keeps dashboard/API consumers thin and gives us one place to add:
1. caching,
2. persistence/snapshotting,
3. paywall policy,
4. alert fan-out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _load_db_funcs() -> object:
    """Lazy import to break db <-> tap circular dependency."""
    try:
        from ..db import enqueue_tap_alerts, get_latest_tap_board_snapshot, save_tap_board_snapshot
    except ImportError:
        from db import enqueue_tap_alerts, get_latest_tap_board_snapshot, save_tap_board_snapshot
    return get_latest_tap_board_snapshot, save_tap_board_snapshot, enqueue_tap_alerts


def _load_alert_queue_funcs() -> object:
    """Lazy import for TAP alert queue delivery helpers."""

    try:
        from ..db import get_tap_alert_delivery_batch, update_tap_alert_delivery_status
    except ImportError:
        from db import get_tap_alert_delivery_batch, update_tap_alert_delivery_status
    return get_tap_alert_delivery_batch, update_tap_alert_delivery_status


def _load_alert_sender() -> object:
    """Lazy import for channel fan-out to keep import surfaces small."""

    try:
        from ..alerts import send_alert
    except ImportError:
        from alerts import send_alert
    return send_alert


try:
    from .detector import TrendArbitrageDetector
    from .product_feed import TapBoard, TapBoardBuilder, empty_tap_board
except ImportError:
    from tap.detector import TrendArbitrageDetector
    from tap.product_feed import TapBoard, TapBoardBuilder, empty_tap_board


@dataclass(slots=True)
class TapBoardRequest:
    """Query contract for TAP product surfaces."""

    target_country: str = ""
    limit: int = 10
    teaser_count: int = 3
    prefer_saved_snapshot: bool = True
    persist_snapshot: bool = True
    force_refresh: bool = False
    snapshot_max_age_minutes: int = 30
    snapshot_source: str = "tap_service"

    @property
    def normalized_target_country(self) -> str:
        return (self.target_country or "").strip().lower()


@dataclass(slots=True)
class TapRefreshSummary:
    """Operational summary for TAP snapshot refresh + alert queueing."""

    markets: list[dict] = field(default_factory=list)
    snapshots_built: int = 0
    alerts_queued: int = 0
    total_detected: int = 0

    def to_dict(self) -> dict:
        return {
            "markets": list(self.markets),
            "snapshots_built": self.snapshots_built,
            "alerts_queued": self.alerts_queued,
            "total_detected": self.total_detected,
        }


@dataclass(slots=True)
class TapAlertDispatchSummary:
    """Operational summary for draining the TAP premium alert queue."""

    target_country: str = ""
    dry_run: bool = False
    channels: list[str] = field(default_factory=list)
    attempted: int = 0
    dispatched: int = 0
    failed: int = 0
    skipped: int = 0
    items: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_country": self.target_country,
            "dry_run": self.dry_run,
            "channels": list(self.channels),
            "attempted": self.attempted,
            "dispatched": self.dispatched,
            "failed": self.failed,
            "skipped": self.skipped,
            "items": list(self.items),
        }


async def get_latest_tap_board_snapshot(
    conn,
    config,
    request: TapBoardRequest | None = None,
) -> TapBoard | None:
    """Return the freshest saved TAP board without recomputing detection."""

    resolved = request or TapBoardRequest()
    target_country = _resolve_target_country(resolved, config)
    load_snapshot, _, _ = _load_db_funcs()
    board = await load_snapshot(
        conn,
        target_country=target_country,
        max_age_minutes=resolved.snapshot_max_age_minutes,
    )
    if board is None:
        return None
    return board.clone_for_delivery(
        limit=resolved.limit,
        teaser_count=resolved.teaser_count,
        delivery_mode="cached",
    )


async def build_tap_board_snapshot(
    conn,
    config,
    request: TapBoardRequest | None = None,
) -> TapBoard:
    """Build a TAP board snapshot for one target market.

    This is the product-serving orchestration path:
    1. serve a fresh saved snapshot when available,
    2. rebuild when stale or missing,
    3. persist the rebuilt board for subsequent reads.
    """

    resolved = request or TapBoardRequest()
    target_country = _resolve_target_country(resolved, config)

    if resolved.prefer_saved_snapshot and not resolved.force_refresh:
        latest = await get_latest_tap_board_snapshot(conn, config, resolved)
        if latest is not None:
            return latest

    detector = TrendArbitrageDetector(conn)
    opportunities = await detector.detect(config=config)
    if not opportunities:
        board = empty_tap_board(target_country=target_country, teaser_count=resolved.teaser_count)
        if resolved.persist_snapshot:
            _, save_snapshot, _ = _load_db_funcs()
            await save_snapshot(conn, board, source=resolved.snapshot_source)
        return board

    builder = TapBoardBuilder()
    storage_board = builder.build(
        opportunities,
        target_country=target_country,
        limit=max(resolved.limit, builder.DEFAULT_LIMIT),
        teaser_count=max(resolved.teaser_count, builder.DEFAULT_TEASER_COUNT),
    )
    if resolved.persist_snapshot:
        _, save_snapshot, _ = _load_db_funcs()
        await save_snapshot(conn, storage_board, source=resolved.snapshot_source)
    return storage_board.clone_for_delivery(
        limit=resolved.limit,
        teaser_count=resolved.teaser_count,
        delivery_mode="live",
    )


def _tap_refresh_request(config, target_country: str, snapshot_source: str) -> TapBoardRequest:
    return TapBoardRequest(
        target_country=target_country,
        limit=max(1, int(getattr(config, "tap_board_limit", 10) or 10)),
        teaser_count=max(0, int(getattr(config, "tap_teaser_count", 3) or 3)),
        prefer_saved_snapshot=False,
        persist_snapshot=True,
        force_refresh=True,
        snapshot_max_age_minutes=max(0, int(getattr(config, "tap_snapshot_max_age_minutes", 30) or 30)),
        snapshot_source=snapshot_source,
    )


async def _enqueue_tap_alerts_if_enabled(conn, config, board, target_country: str, enqueue_alerts) -> int:
    if not getattr(config, "enable_tap_alert_queue", True):
        return 0
    return await enqueue_alerts(
        conn,
        board,
        target_country=target_country,
        top_k=max(0, int(getattr(config, "tap_alert_top_k", 3) or 3)),
        min_priority=float(getattr(config, "tap_alert_min_priority", 80.0) or 80.0),
        min_viral_score=max(0, int(getattr(config, "tap_alert_min_viral_score", 75) or 75)),
        cooldown_minutes=max(0, int(getattr(config, "tap_alert_cooldown_minutes", 180) or 180)),
    )


def _record_tap_refresh_market(summary: TapRefreshSummary, board, target_country: str, queued: int) -> None:
    summary.snapshots_built += 1
    summary.alerts_queued += queued
    summary.total_detected += board.total_detected
    summary.markets.append(
        {
            "target_country": target_country,
            "snapshot_id": board.snapshot_id,
            "detected": board.total_detected,
            "queued": queued,
        }
    )


async def refresh_tap_market_surfaces(
    conn,
    config,
    *,
    snapshot_source: str = "tap_refresh",
) -> TapRefreshSummary:
    """Refresh per-market TAP snapshots and enqueue premium alerts."""

    markets = _resolve_market_targets(config)
    summary = TapRefreshSummary()
    if len(markets) < 2:
        return summary

    _, _, enqueue_alerts = _load_db_funcs()

    for target_country in markets:
        board = await build_tap_board_snapshot(
            conn,
            config,
            _tap_refresh_request(config, target_country, snapshot_source),
        )

        queued = await _enqueue_tap_alerts_if_enabled(conn, config, board, target_country, enqueue_alerts)
        _record_tap_refresh_market(summary, board, target_country, queued)

    return summary


def _tap_dispatch_batch_limit(config, limit: int | None) -> int:
    return int(limit or getattr(config, "tap_alert_dispatch_batch_size", 5) or 5)


def _tap_dispatch_summary(config, target_country: str, dry_run: bool) -> TapAlertDispatchSummary:
    return TapAlertDispatchSummary(
        target_country=target_country,
        dry_run=dry_run,
        channels=_configured_alert_channels(config),
    )


async def _dispatch_tap_alert_items(conn, config, queued_items: list[dict], update_status, send_alert) -> tuple[int, int, list[dict]]:
    dispatched = 0
    failed = 0
    results = []
    for item in queued_items:
        item_result = await _dispatch_tap_alert_item(conn, item, config, update_status, send_alert)
        if item_result["status"] == "dispatched":
            dispatched += 1
        else:
            failed += 1
        results.append(item_result)
    return dispatched, failed, results


async def dispatch_tap_alert_queue(
    conn,
    config,
    *,
    limit: int | None = None,
    target_country: str = "",
    dry_run: bool = False,
) -> TapAlertDispatchSummary:
    """Deliver queued TAP alerts to configured notification channels."""

    resolved_country = (target_country or "").strip().lower()
    batch_limit = _tap_dispatch_batch_limit(config, limit)
    summary = _tap_dispatch_summary(config, resolved_country, dry_run)
    if batch_limit <= 0:
        return summary

    load_batch, update_status = _load_alert_queue_funcs()
    queued_items = await load_batch(
        conn,
        limit=batch_limit,
        target_country=resolved_country,
        lifecycle_status="queued",
    )
    if not queued_items:
        return summary

    if dry_run or getattr(config, "no_alerts", False) or not summary.channels:
        _mark_tap_dispatch_skipped(summary, queued_items, _tap_dispatch_skip_reason(config, dry_run), dry_run)
        return summary

    send_alert = _load_alert_sender()
    summary.attempted = len(queued_items)
    summary.dispatched, summary.failed, summary.items = await _dispatch_tap_alert_items(
        conn, config, queued_items, update_status, send_alert
    )

    return summary

def _tap_dispatch_skip_reason(config, dry_run: bool) -> str:
    if dry_run:
        return "dry_run"
    if getattr(config, "no_alerts", False):
        return "alerts_disabled"
    return "no_channels"


def _mark_tap_dispatch_skipped(summary: TapAlertDispatchSummary, queued_items: list[dict], reason: str, dry_run: bool) -> None:
    summary.skipped = len(queued_items)
    summary.attempted = len(queued_items) if dry_run else 0
    summary.items = [
        {
            "alert_id": item["alert_id"],
            "keyword": item["keyword"],
            "status": reason,
        }
        for item in queued_items
    ]


def _tap_channel_results(channel_results: dict) -> tuple[list[str], list[str], str]:
    successful_channels = [
        channel for channel, result in channel_results.items() if isinstance(result, dict) and result.get("ok")
    ]
    failed_channels = [
        channel for channel, result in channel_results.items() if not (isinstance(result, dict) and result.get("ok"))
    ]
    failure_reason = "; ".join(
        f"{channel}: {result.get('error', 'unknown error')}"
        for channel, result in channel_results.items()
        if isinstance(result, dict) and not result.get("ok")
    )
    return successful_channels, failed_channels, failure_reason


def _tap_delivery_metadata(
    status: str,
    attempted_at: str,
    successful_channels: list[str],
    failed_channels: list[str],
    failure_reason: str,
    channel_results: dict,
) -> dict:
    return {
        "last_delivery": {
            "status": status,
            "attempted_at": attempted_at,
            "successful_channels": successful_channels,
            "failed_channels": failed_channels,
            "channels": successful_channels or list(channel_results.keys()),
            "failure_reason": failure_reason,
            "channel_results": channel_results,
        }
    }


async def _dispatch_tap_alert_item(conn, item: dict, config, update_status, send_alert) -> dict:
    channel_results = send_alert(item["alert_message"], config)
    successful_channels, failed_channels, failure_reason = _tap_channel_results(channel_results)
    attempted_at = datetime.utcnow().isoformat()

    if successful_channels:
        await update_status(
            conn,
            alert_id=item["alert_id"],
            lifecycle_status="dispatched",
            dispatched_at=attempted_at,
            last_attempt_at=attempted_at,
            metadata_patch=_tap_delivery_metadata(
                "dispatched",
                attempted_at,
                successful_channels,
                failed_channels,
                failure_reason,
                channel_results,
            ),
        )
        status = "dispatched"
    else:
        await update_status(
            conn,
            alert_id=item["alert_id"],
            lifecycle_status="failed",
            last_attempt_at=attempted_at,
            metadata_patch=_tap_delivery_metadata(
                "failed",
                attempted_at,
                successful_channels,
                failed_channels,
                failure_reason,
                channel_results,
            ),
        )
        status = "failed"

    return {
        "alert_id": item["alert_id"],
        "keyword": item["keyword"],
        "status": status,
        "channels": successful_channels or list(channel_results.keys()),
        "channel_results": channel_results,
        "failure_reason": failure_reason,
    }


def _resolve_target_country(resolved: TapBoardRequest, config) -> str:
    return resolved.normalized_target_country or (getattr(config, "country", "") or "").strip().lower()


def _resolve_market_targets(config) -> list[str]:
    raw_markets = list(getattr(config, "countries", []) or [getattr(config, "country", "")])
    normalized: list[str] = []
    seen: set[str] = set()
    for country in raw_markets:
        normalized_country = (country or "").strip().lower()
        if not normalized_country or normalized_country in seen:
            continue
        seen.add(normalized_country)
        normalized.append(normalized_country)
    return normalized


def _configured_alert_channels(config) -> list[str]:
    channels: list[str] = []
    if getattr(config, "telegram_bot_token", "") and getattr(config, "telegram_chat_id", ""):
        channels.append("telegram")
    if getattr(config, "discord_webhook_url", ""):
        channels.append("discord")
    if getattr(config, "slack_webhook_url", ""):
        channels.append("slack")
    if getattr(config, "smtp_host", "") and getattr(config, "alert_email", ""):
        channels.append("email")
    return channels
