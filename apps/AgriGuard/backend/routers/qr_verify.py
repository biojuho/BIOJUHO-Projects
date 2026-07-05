# ruff: noqa: B008  # FastAPI's Depends() in defaults is the canonical injection pattern
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlparse

import models
import schemas
from dependencies import get_db
from fastapi import APIRouter, Depends, Query, Response
from services.chain_simulator import get_chain
from services.qr_tokens import is_token_expired, lookup_qr_token, public_batch_code
from sqlalchemy import or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{4,160}$")
_TEMP_MIN_C = -25.0
_TEMP_MAX_C = 8.0
_TEMP_WINDOW_HOURS = 24
_STALE_AFTER_MINUTES = 10
_ANALYTICS_LABEL_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
PUBLIC_VERIFY_CACHE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Expires": "0",
}


def set_public_verify_cache_headers(response: Response) -> None:
    for header, value in PUBLIC_VERIFY_CACHE_HEADERS.items():
        response.headers[header] = value


def _safe_analytics_label(value: str | None, *, default: str, max_length: int) -> str:
    normalized = (value or "").strip()
    if not normalized or len(normalized) > max_length or not _ANALYTICS_LABEL_RE.fullmatch(normalized):
        return default
    return normalized


def _safe_session_id(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) > 120 or not _ANALYTICS_LABEL_RE.fullmatch(normalized):
        return None
    return normalized


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_qr_token(raw_token: str) -> str:
    value = unquote(raw_token).strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme == "agri" and parsed.netloc == "verify":
        return parsed.path.strip("/")
    if parsed.scheme in {"http", "https"}:
        parts = [part for part in parsed.path.split("/") if part]
        for marker in ("verify", "product"):
            if marker in parts and parts.index(marker) + 1 < len(parts):
                return parts[parts.index(marker) + 1]
    return value


def _is_public_token_shape(token: str) -> bool:
    return bool(_TOKEN_RE.fullmatch(token))


def _legacy_qr_lookup_enabled() -> bool:
    return os.environ.get("ALLOW_LEGACY_QR_LOOKUP", "true").strip().lower() in {"1", "true", "yes", "on"}


def _redact_value(value: str | None, *, prefix: int = 8, suffix: int = 6) -> str:
    if not value:
        return "unavailable"
    if len(value) <= prefix + suffix + 3:
        return value
    return f"{value[:prefix]}...{value[-suffix:]}"


def _safe_event_type(record: dict) -> str:
    data = record.get("data") if isinstance(record.get("data"), dict) else {}
    event_type = data.get("action") or data.get("status") or "AUDIT_EVENT"
    return str(event_type)


def _record_timestamp(record: dict) -> datetime | None:
    raw_timestamp = record.get("timestamp")
    if not isinstance(raw_timestamp, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")))
    except ValueError:
        return None


def _build_route(product: models.Product) -> list[schemas.QRRouteCheckpoint]:
    events = sorted(
        product.tracking_history,
        key=lambda event: _as_utc(event.timestamp) or datetime.min.replace(tzinfo=UTC),
    )
    return [
        schemas.QRRouteCheckpoint(
            timestamp=_as_utc(event.timestamp) or datetime.now(UTC),
            status=event.status,
            location=event.location,
        )
        for event in events
    ]


def _temperature_status(rows: list[models.SensorReading], *, now: datetime) -> schemas.QRTemperatureSummary:
    if not rows:
        return schemas.QRTemperatureSummary(
            status="unknown",
            message="No recent sensor readings are available for the public verification window.",
        )

    temps = [float(row.temperature) for row in rows]
    latest = max((_as_utc(row.timestamp) for row in rows), default=None)
    is_stale = latest is None or now - latest > timedelta(minutes=_STALE_AFTER_MINUTES)
    min_temp = min(temps)
    max_temp = max(temps)
    avg_temp = round(sum(temps) / len(temps), 1)

    if min_temp < _TEMP_MIN_C or max_temp > _TEMP_MAX_C:
        status = "warning"
        message = "Recent cold-chain readings include a temperature excursion."
    elif is_stale:
        status = "unknown"
        message = "Temperature data is delayed, so cold-chain status cannot be confirmed."
    else:
        status = "safe"
        message = "Recent cold-chain readings are within the expected range."

    return schemas.QRTemperatureSummary(
        status=status,
        message=message,
        min_celsius=round(min_temp, 1),
        max_celsius=round(max_temp, 1),
        average_celsius=avg_temp,
        readings_count=len(rows),
        last_reading_at=latest,
        is_stale=is_stale,
    )


def _build_temperature_summary(db: Session, *, now: datetime) -> schemas.QRTemperatureSummary:
    cutoff = now.replace(tzinfo=None) - timedelta(hours=_TEMP_WINDOW_HOURS)
    rows = (
        db.query(models.SensorReading)
        .filter(models.SensorReading.timestamp >= cutoff)
        .order_by(models.SensorReading.timestamp.desc())
        .limit(500)
        .all()
    )
    return _temperature_status(rows, now=now)


def _build_blockchain_proof(product_id: str, route: list[schemas.QRRouteCheckpoint]) -> schemas.QRBlockchainProof:
    try:
        raw_records = get_chain().get_product_history(product_id)
    except Exception:  # pragma: no cover - defensive fallback path
        logger.warning("Chain proof lookup failed for public QR verification", exc_info=True)
        raw_records = []

    public_records = [
        schemas.QRBlockchainRecord(
            tx_hash=_redact_value(str(record.get("tx_hash") or "")),
            block=str(record.get("block") or "pending"),
            timestamp=_record_timestamp(record),
            event_type=_safe_event_type(record),
        )
        for record in raw_records[:5]
    ]
    evidence_payload = {
        "product_id": product_id,
        "route": [checkpoint.model_dump(mode="json") for checkpoint in route],
        "records": [record.model_dump(mode="json") for record in public_records],
    }
    evidence_hash = hashlib.sha256(json.dumps(evidence_payload, sort_keys=True).encode("utf-8")).hexdigest()
    latest_tx_hash = public_records[0].tx_hash if public_records else None

    if public_records:
        return schemas.QRBlockchainProof(
            status="anchored",
            message="Audit evidence is anchored in the AgriGuard chain.",
            record_count=len(raw_records),
            latest_tx_hash=latest_tx_hash,
            evidence_hash=evidence_hash,
            records=public_records,
        )

    return schemas.QRBlockchainProof(
        status="pending",
        message="No public chain anchor was found for this verification request.",
        record_count=0,
        evidence_hash=evidence_hash,
        records=[],
    )


def _has_recall_signal(route: list[schemas.QRRouteCheckpoint]) -> bool:
    return any("recall" in checkpoint.status.lower() for checkpoint in route)


def _trust_badge(
    *,
    product: models.Product,
    temperature_summary: schemas.QRTemperatureSummary,
    blockchain_proof: schemas.QRBlockchainProof,
    route: list[schemas.QRRouteCheckpoint],
) -> schemas.QRTrustBadge:
    if _has_recall_signal(route):
        return schemas.QRTrustBadge(
            status="Warning",
            label="Check before purchase",
            reason="A recall-related route status was reported for this batch.",
        )
    if temperature_summary.status == "warning":
        return schemas.QRTrustBadge(
            status="Warning",
            label="Temperature warning",
            reason="Cold-chain readings include a temperature excursion.",
        )
    if product.is_verified and temperature_summary.status != "unknown":
        return schemas.QRTrustBadge(
            status="Safe",
            label="Verified batch",
            reason="The batch is operator-verified and recent temperature data is acceptable.",
        )
    if blockchain_proof.status == "anchored" and temperature_summary.status == "safe":
        return schemas.QRTrustBadge(
            status="Safe",
            label="Chain-backed evidence",
            reason="Traceability evidence is anchored and recent temperature data is acceptable.",
        )
    return schemas.QRTrustBadge(
        status="Unknown",
        label="Needs more evidence",
        reason="The QR is registered, but public evidence is incomplete or delayed.",
    )


def _unknown_response(*, now: datetime) -> schemas.QRVerifyResponse:
    evidence_hash = hashlib.sha256(f"unknown:{now.isoformat()}".encode("utf-8")).hexdigest()
    return schemas.QRVerifyResponse(
        status="unknown",
        is_valid=False,
        verified_at=now,
        last_verified_at=now,
        trust_badge=schemas.QRTrustBadge(
            status="Unknown",
            label="QR not verified",
            reason="This code is invalid, expired, fake, or not issued by AgriGuard.",
        ),
        product=None,
        batch=None,
        route=[],
        temperature_summary=schemas.QRTemperatureSummary(
            status="unknown",
            message="No product data is shown for unverified QR codes.",
        ),
        blockchain_proof=schemas.QRBlockchainProof(
            status="unavailable",
            message="No public audit proof is available for this QR code.",
            evidence_hash=evidence_hash,
        ),
        consumer_notice="Do not rely on this QR code. Ask the seller for a valid AgriGuard verification label.",
    )


def _store_public_verify_event(
    db: Session,
    *,
    session_id: str | None,
    variant_id: str,
    source: str,
    token: str,
    product_id: str | None,
    event_type: str,
    error_code: str | None = None,
    token_status: str = "unknown",
) -> None:
    try:
        event = models.QRScanEvent(
            session_id=session_id or f"public-{uuid.uuid4().hex}",
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            product_id=product_id,
            qr_value=_redact_value(token),
            error_code=error_code,
            source=source,
            variant_id=variant_id,
            metadata_json=json.dumps(
                {
                    "token_shape": "accepted" if _is_public_token_shape(token) else "rejected",
                    "token_status": token_status,
                }
            ),
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to store public QR verification analytics event", exc_info=True)


def _lookup_legacy_product_by_token(db: Session, token: str) -> models.Product | None:
    if not _legacy_qr_lookup_enabled():
        return None
    return (
        db.query(models.Product)
        .filter(or_(models.Product.id == token, models.Product.qr_code == token, models.Product.qr_code == f"agri://verify/{token}"))
        .first()
    )


@router.get("/api/qr/{qr_token}/verify", response_model=schemas.QRVerifyResponse)
def verify_qr_token(
    qr_token: str,
    response: Response,
    session_id: str | None = Query(default=None, max_length=120),
    variant_id: str = Query(default="qr_consumer_v1", max_length=80),
    source: str = Query(default="consumer_verify_page", max_length=80),
    db: Session = Depends(get_db),
) -> schemas.QRVerifyResponse:
    now = datetime.now(UTC)
    set_public_verify_cache_headers(response)
    token = _normalize_qr_token(qr_token)
    safe_session_id = _safe_session_id(session_id)
    safe_variant_id = _safe_analytics_label(variant_id, default="qr_consumer_v1", max_length=80)
    safe_source = _safe_analytics_label(source, default="consumer_verify_page", max_length=80)

    if not _is_public_token_shape(token):
        _store_public_verify_event(
            db,
            session_id=safe_session_id,
            variant_id=safe_variant_id,
            source=safe_source,
            token=token,
            product_id=None,
            event_type="scan_failure",
            error_code="invalid_or_expired_qr",
        )
        return _unknown_response(now=now)

    qr_token = lookup_qr_token(db, token)
    token_status = "valid"
    if qr_token is not None and qr_token.revoked_at is not None:
        _store_public_verify_event(
            db,
            session_id=safe_session_id,
            variant_id=safe_variant_id,
            source=safe_source,
            token=token,
            product_id=qr_token.product_id,
            event_type="scan_failure",
            error_code="revoked_qr",
            token_status="revoked",
        )
        return _unknown_response(now=now)

    if qr_token is not None and is_token_expired(qr_token, now=now):
        _store_public_verify_event(
            db,
            session_id=safe_session_id,
            variant_id=safe_variant_id,
            source=safe_source,
            token=token,
            product_id=qr_token.product_id,
            event_type="scan_failure",
            error_code="expired_qr",
            token_status="expired",
        )
        return _unknown_response(now=now)

    product = qr_token.product if qr_token is not None else _lookup_legacy_product_by_token(db, token)
    if product is None:
        _store_public_verify_event(
            db,
            session_id=safe_session_id,
            variant_id=safe_variant_id,
            source=safe_source,
            token=token,
            product_id=None,
            event_type="scan_failure",
            error_code="invalid_or_expired_qr",
            token_status="missing",
        )
        return _unknown_response(now=now)

    if qr_token is None:
        token_status = "legacy"
    else:
        qr_token.scan_count = int(qr_token.scan_count or 0) + 1
        qr_token.last_verified_at = now

    route = _build_route(product)
    temperature_summary = _build_temperature_summary(db, now=now)
    blockchain_proof = _build_blockchain_proof(product.id, route)
    trust_badge = _trust_badge(
        product=product,
        temperature_summary=temperature_summary,
        blockchain_proof=blockchain_proof,
        route=route,
    )

    _store_public_verify_event(
        db,
        session_id=safe_session_id,
        variant_id=safe_variant_id,
        source=safe_source,
        token=token,
        product_id=product.id,
        event_type="verification_complete",
        token_status=token_status,
    )

    return schemas.QRVerifyResponse(
        status="success",
        is_valid=True,
        verified_at=now,
        last_verified_at=_as_utc(qr_token.last_verified_at) if qr_token is not None else now,
        trust_badge=trust_badge,
        product=schemas.QRPublicProduct(
            name=product.name,
            category=product.category,
            origin=product.origin or "Unknown",
        ),
        batch=schemas.QRBatchSummary(
            batch_code=qr_token.batch_code if qr_token is not None else public_batch_code(product.id),
            harvest_date=_as_utc(product.harvest_date),
            cold_chain_required=bool(product.requires_cold_chain),
            recall_status="reported" if _has_recall_signal(route) else "not_reported",
        ),
        route=route,
        temperature_summary=temperature_summary,
        blockchain_proof=blockchain_proof,
        consumer_notice="Only public traceability fields are shown. Operator, tenant, and handler details are redacted.",
    )
