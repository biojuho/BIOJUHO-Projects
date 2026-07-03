# ruff: noqa: B008  # FastAPI's Depends() in defaults is the canonical injection pattern
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import models
import schemas
from dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter()

DEFAULT_SCAN_SUCCESS_TARGET = 0.99
DEFAULT_DAILY_SCAN_TARGET = 1000


def _empty_qr_summary(*, hours: int, variant_id: str | None, since: datetime) -> dict:
    return {
        "hours": hours,
        "variant_id": variant_id or "all",
        "since": since.isoformat() + "Z",
        "total_events": 0,
        "total_sessions": 0,
        "event_counts": {},
        "error_counts": {},
        "variant_counts": {},
        "funnel": {
            "scan_start_sessions": 0,
            "scan_failure_sessions": 0,
            "scan_recovery_sessions": 0,
            "verification_complete_sessions": 0,
            "verification_completion_rate": 0.0,
            "recovery_rate_after_failure": 0.0,
        },
    }


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _qr_event_counts(events: list[models.QRScanEvent]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    event_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}

    for event in events:
        _increment(event_counts, event.event_type)
        _increment(variant_counts, event.variant_id)
        if event.error_code:
            _increment(error_counts, event.error_code)

    return event_counts, error_counts, variant_counts


def _qr_sessions(events: list[models.QRScanEvent]) -> dict[str, set[str]]:
    sessions: dict[str, set[str]] = {}
    for event in events:
        sessions.setdefault(event.session_id, set()).add(event.event_type)
    return sessions


def _session_count_with_event(sessions: dict[str, set[str]], event_type: str) -> int:
    return sum(1 for event_types in sessions.values() if event_type in event_types)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _qr_funnel(sessions: dict[str, set[str]]) -> dict[str, int | float]:
    scan_start_sessions = _session_count_with_event(sessions, "scan_start")
    scan_failure_sessions = _session_count_with_event(sessions, "scan_failure")
    scan_recovery_sessions = _session_count_with_event(sessions, "scan_recovery")
    verification_complete_sessions = _session_count_with_event(sessions, "verification_complete")

    return {
        "scan_start_sessions": scan_start_sessions,
        "scan_failure_sessions": scan_failure_sessions,
        "scan_recovery_sessions": scan_recovery_sessions,
        "verification_complete_sessions": verification_complete_sessions,
        "verification_completion_rate": _rate(verification_complete_sessions, scan_start_sessions),
        "recovery_rate_after_failure": _rate(scan_recovery_sessions, scan_failure_sessions),
    }


def _qr_kpi_values(
    sessions: dict[str, set[str]],
    *,
    target_scan_success_rate: float,
    target_daily_scans: int,
) -> dict[str, int | float | str]:
    scan_start_sessions = _session_count_with_event(sessions, "scan_start")
    scan_failure_sessions = _session_count_with_event(sessions, "scan_failure")
    verification_complete_sessions = _session_count_with_event(sessions, "verification_complete")
    scan_success_sessions = sum(
        1 for event_types in sessions.values()
        if "scan_start" in event_types and "verification_complete" in event_types
    )
    scan_success_rate = _rate(scan_success_sessions, scan_start_sessions)
    daily_scan_progress = round(min(1.0, verification_complete_sessions / target_daily_scans), 4)

    return {
        "scan_start_sessions": scan_start_sessions,
        "scan_success_sessions": scan_success_sessions,
        "scan_failure_sessions": scan_failure_sessions,
        "verification_complete_sessions": verification_complete_sessions,
        "scan_success_rate": scan_success_rate,
        "daily_scan_progress": daily_scan_progress,
        "scan_success_status": _status_for_rate(scan_success_rate, target_scan_success_rate, scan_start_sessions),
        "daily_scan_status": _status_for_count(verification_complete_sessions, target_daily_scans),
    }


def _reporting_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name.strip())
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Unsupported timezone. Use an IANA time zone name such as UTC, Asia/Seoul, or America/Los_Angeles.",
        ) from exc


def _event_date(event: models.QRScanEvent, reporting_timezone: ZoneInfo) -> str:
    occurred_at = event.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    else:
        occurred_at = occurred_at.astimezone(UTC)
    return occurred_at.astimezone(reporting_timezone).date().isoformat()


def _status_for_rate(value: float, target: float, denominator: int) -> str:
    if denominator <= 0:
        return "no_data"
    return "on_track" if value >= target else "below_target"


def _status_for_count(value: int, target: int) -> str:
    return "on_track" if value >= target else "below_target"


@router.post("/qr-events", response_model=schemas.QRScanEventResponse)
def capture_qr_scan_event(payload: schemas.QRScanEventCreate, db: Session = Depends(get_db)) -> dict:
    try:
        event = models.QRScanEvent(
            session_id=payload.session_id,
            event_type=payload.event_type,
            occurred_at=payload.occurred_at or datetime.now(UTC),
            product_id=payload.product_id,
            qr_value=payload.qr_value,
            error_code=payload.error_code,
            error_message=payload.error_message,
            recovery_method=payload.recovery_method,
            source=payload.source,
            variant_id=payload.variant_id,
            metadata_json=json.dumps(payload.event_payload, ensure_ascii=False),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        # Business metrics
        try:
            from shared.business_metrics import biz

            biz.qr_scan(payload.event_type)
            if payload.event_type == "verification_complete":
                biz.verification_complete()
        except ImportError:
            pass
        return {"status": "success", "event_id": event.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"QR event capture failed: {str(e)}") from e


@router.get("/qr-events/summary")
def get_qr_event_summary(hours: int = 24, variant_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    since = datetime.now(UTC) - timedelta(hours=hours)
    query = db.query(models.QRScanEvent).filter(models.QRScanEvent.occurred_at >= since)
    if variant_id:
        query = query.filter(models.QRScanEvent.variant_id == variant_id)

    events = query.order_by(models.QRScanEvent.occurred_at.asc()).all()
    if not events:
        return _empty_qr_summary(hours=hours, variant_id=variant_id, since=since)

    event_counts, error_counts, variant_counts = _qr_event_counts(events)
    sessions = _qr_sessions(events)

    return {
        "hours": hours,
        "variant_id": variant_id or "all",
        "since": since.isoformat() + "Z",
        "total_events": len(events),
        "total_sessions": len(sessions),
        "event_counts": event_counts,
        "error_counts": error_counts,
        "variant_counts": variant_counts,
        "funnel": _qr_funnel(sessions),
    }


@router.get("/qr-events/kpis", response_model=schemas.QRKPISummaryResponse)
def get_qr_kpis(
    hours: int = Query(default=24, ge=1, le=720),
    variant_id: str | None = Query(default=None, max_length=80),
    target_scan_success_rate: float = Query(default=DEFAULT_SCAN_SUCCESS_TARGET, ge=0.0, le=1.0),
    target_daily_scans: int = Query(default=DEFAULT_DAILY_SCAN_TARGET, ge=1, le=1_000_000),
    db: Session = Depends(get_db),
) -> schemas.QRKPISummaryResponse:
    since = datetime.now(UTC) - timedelta(hours=hours)
    query = db.query(models.QRScanEvent).filter(models.QRScanEvent.occurred_at >= since)
    if variant_id:
        query = query.filter(models.QRScanEvent.variant_id == variant_id)

    events = query.order_by(models.QRScanEvent.occurred_at.asc()).all()
    sessions = _qr_sessions(events)
    values = _qr_kpi_values(
        sessions,
        target_scan_success_rate=target_scan_success_rate,
        target_daily_scans=target_daily_scans,
    )

    return schemas.QRKPISummaryResponse(
        status="success",
        hours=hours,
        variant_id=variant_id or "all",
        since=since,
        scan_start_sessions=values["scan_start_sessions"],
        scan_success_sessions=values["scan_success_sessions"],
        scan_failure_sessions=values["scan_failure_sessions"],
        verification_complete_sessions=values["verification_complete_sessions"],
        consumer_scan_sessions=values["verification_complete_sessions"],
        scan_success_rate=values["scan_success_rate"],
        target_scan_success_rate=target_scan_success_rate,
        scan_success_status=values["scan_success_status"],
        target_daily_scans=target_daily_scans,
        daily_scan_progress=values["daily_scan_progress"],
        daily_scan_status=values["daily_scan_status"],
    )


@router.get("/qr-events/kpis/trend", response_model=schemas.QRKPITrendResponse)
def get_qr_kpi_trend(
    days: int = Query(default=7, ge=1, le=90),
    variant_id: str | None = Query(default=None, max_length=80),
    timezone_name: str = Query(default="UTC", alias="timezone", min_length=1, max_length=64),
    target_scan_success_rate: float = Query(default=DEFAULT_SCAN_SUCCESS_TARGET, ge=0.0, le=1.0),
    target_daily_scans: int = Query(default=DEFAULT_DAILY_SCAN_TARGET, ge=1, le=1_000_000),
    db: Session = Depends(get_db),
) -> schemas.QRKPITrendResponse:
    reporting_timezone = _reporting_timezone(timezone_name)
    today = datetime.now(UTC).astimezone(reporting_timezone).date()
    start_date = today - timedelta(days=days - 1)
    since = datetime.combine(start_date, datetime.min.time(), tzinfo=reporting_timezone).astimezone(UTC)
    day_sessions: dict[str, dict[str, set[str]]] = {
        (start_date + timedelta(days=offset)).isoformat(): {}
        for offset in range(days)
    }

    query = db.query(models.QRScanEvent).filter(models.QRScanEvent.occurred_at >= since)
    if variant_id:
        query = query.filter(models.QRScanEvent.variant_id == variant_id)

    for event in query.order_by(models.QRScanEvent.occurred_at.asc()).all():
        day_key = _event_date(event, reporting_timezone)
        if day_key not in day_sessions:
            continue
        day_sessions[day_key].setdefault(event.session_id, set()).add(event.event_type)

    items = []
    for day_key in sorted(day_sessions):
        values = _qr_kpi_values(
            day_sessions[day_key],
            target_scan_success_rate=target_scan_success_rate,
            target_daily_scans=target_daily_scans,
        )
        items.append(
            schemas.QRKPITrendPoint(
                date=day_key,
                scan_start_sessions=values["scan_start_sessions"],
                scan_success_sessions=values["scan_success_sessions"],
                verification_complete_sessions=values["verification_complete_sessions"],
                scan_success_rate=values["scan_success_rate"],
                daily_scan_progress=values["daily_scan_progress"],
                scan_success_status=values["scan_success_status"],
                daily_scan_status=values["daily_scan_status"],
            )
        )

    return schemas.QRKPITrendResponse(
        status="success",
        days=days,
        variant_id=variant_id or "all",
        timezone=reporting_timezone.key,
        target_scan_success_rate=target_scan_success_rate,
        target_daily_scans=target_daily_scans,
        items=items,
    )
