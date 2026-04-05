from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from dependencies import get_db
import models
import schemas
import uuid
import json
from datetime import UTC, datetime, timedelta
from auth import get_current_user
from services.chain_simulator import get_chain



router = APIRouter()


@router.post("/qr-events", response_model=schemas.QRScanEventResponse)
def capture_qr_scan_event(payload: schemas.QRScanEventCreate, db: Session = Depends(get_db)):
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
def get_qr_event_summary(hours: int = 24, variant_id: str | None = None, db: Session = Depends(get_db)):
    since = datetime.now(UTC) - timedelta(hours=hours)
    query = db.query(models.QRScanEvent).filter(models.QRScanEvent.occurred_at >= since)
    if variant_id:
        query = query.filter(models.QRScanEvent.variant_id == variant_id)

    events = query.order_by(models.QRScanEvent.occurred_at.asc()).all()
    if not events:
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

    event_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    sessions: dict[str, set[str]] = {}

    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        variant_counts[event.variant_id] = variant_counts.get(event.variant_id, 0) + 1
        sessions.setdefault(event.session_id, set()).add(event.event_type)
        if event.error_code:
            error_counts[event.error_code] = error_counts.get(event.error_code, 0) + 1

    total_sessions = len(sessions)
    scan_start_sessions = sum(1 for value in sessions.values() if "scan_start" in value)
    scan_failure_sessions = sum(1 for value in sessions.values() if "scan_failure" in value)
    scan_recovery_sessions = sum(1 for value in sessions.values() if "scan_recovery" in value)
    verification_complete_sessions = sum(1 for value in sessions.values() if "verification_complete" in value)

    completion_rate = round(verification_complete_sessions / scan_start_sessions, 4) if scan_start_sessions else 0.0
    recovery_rate = round(scan_recovery_sessions / scan_failure_sessions, 4) if scan_failure_sessions else 0.0

    return {
        "hours": hours,
        "variant_id": variant_id or "all",
        "since": since.isoformat() + "Z",
        "total_events": len(events),
        "total_sessions": total_sessions,
        "event_counts": event_counts,
        "error_counts": error_counts,
        "variant_counts": variant_counts,
        "funnel": {
            "scan_start_sessions": scan_start_sessions,
            "scan_failure_sessions": scan_failure_sessions,
            "scan_recovery_sessions": scan_recovery_sessions,
            "verification_complete_sessions": verification_complete_sessions,
            "verification_completion_rate": completion_rate,
            "recovery_rate_after_failure": recovery_rate,
        },
    }
