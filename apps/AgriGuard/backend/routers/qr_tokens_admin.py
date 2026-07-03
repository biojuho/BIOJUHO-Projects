# ruff: noqa: B008  # FastAPI's Depends() in defaults is the canonical injection pattern
import json
import os
from datetime import UTC, datetime

import models
import schemas
from auth import get_current_user, user_owner_keys, user_roles
from dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from services.qr_tokens import build_public_qr_code, is_token_expired, reissue_qr_token, revoke_qr_token
from sqlalchemy.orm import Session

router = APIRouter(prefix="/qr-tokens")

_GLOBAL_QR_TOKEN_OPERATOR_ROLES = {"admin", "operator", "quality_manager"}
_QR_TOKEN_OPERATOR_ROLES = _GLOBAL_QR_TOKEN_OPERATOR_ROLES | {"qr_operator"}
_TOKEN_STATUSES = {"all", "active", "revoked", "expired"}


def _split_env_list(name: str) -> set[str]:
    return {value.strip().lower() for value in os.environ.get(name, "").split(",") if value.strip()}


def require_qr_token_operator(current_user: dict = Depends(get_current_user)) -> dict:
    uid = str(current_user.get("uid") or "").strip().lower()
    email = str(current_user.get("email") or "").strip().lower()
    allowed_uids = _split_env_list("QR_TOKEN_OPERATOR_UIDS")
    allowed_emails = _split_env_list("QR_TOKEN_OPERATOR_EMAILS")

    if user_roles(current_user) & _QR_TOKEN_OPERATOR_ROLES:
        return current_user
    if uid and uid in allowed_uids:
        return current_user
    if email and email in allowed_emails:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="QR token administration requires an operator role or explicit allow-list grant.",
    )


def _token_status(qr_token: models.QRToken, *, now: datetime | None = None) -> str:
    baseline = now or datetime.now(UTC)
    if qr_token.revoked_at is not None:
        return "revoked"
    if is_token_expired(qr_token, now=baseline):
        return "expired"
    return "active"


def _can_manage_product_qr_tokens(current_user: dict, product: models.Product) -> bool:
    if user_roles(current_user) & _GLOBAL_QR_TOKEN_OPERATOR_ROLES:
        return True
    owner_id = str(product.owner_id or "").strip()
    return bool(owner_id and owner_id in user_owner_keys(current_user))


def _get_manageable_product(db: Session, product_id: str, current_user: dict) -> models.Product:
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product is None or not _can_manage_product_qr_tokens(current_user, product):
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _get_manageable_qr_token(db: Session, token_id: str, current_user: dict) -> models.QRToken:
    qr_token = db.query(models.QRToken).filter(models.QRToken.id == token_id).first()
    if qr_token is None:
        raise HTTPException(status_code=404, detail="QR token not found")

    product = db.query(models.Product).filter(models.Product.id == qr_token.product_id).first()
    if product is None or not _can_manage_product_qr_tokens(current_user, product):
        raise HTTPException(status_code=404, detail="QR token not found")
    return qr_token


def _token_summary(qr_token: models.QRToken, *, now: datetime | None = None) -> schemas.QRTokenAdminSummary:
    baseline = now or datetime.now(UTC)
    token_status = _token_status(qr_token, now=baseline)
    return schemas.QRTokenAdminSummary(
        id=qr_token.id,
        product_id=qr_token.product_id,
        token_prefix=qr_token.token_prefix,
        batch_code=qr_token.batch_code,
        issued_at=qr_token.issued_at,
        expires_at=qr_token.expires_at,
        revoked_at=qr_token.revoked_at,
        last_verified_at=qr_token.last_verified_at,
        scan_count=int(qr_token.scan_count or 0),
        is_active=token_status == "active",
        status=token_status,
    )


def _operator_session_id(current_user: dict) -> str:
    actor = str(current_user.get("uid") or current_user.get("email") or "unknown-operator").strip()
    return f"operator:{actor or 'unknown-operator'}"


def _operator_metadata(current_user: dict) -> dict:
    return {
        "actor_uid": current_user.get("uid"),
        "actor_email": current_user.get("email"),
        "actor_roles": sorted(user_roles(current_user)),
    }


def _record_qr_token_admin_event(
    db: Session,
    *,
    current_user: dict,
    event_type: str,
    product_id: str,
    qr_token: models.QRToken,
    event_payload: dict,
) -> None:
    db.add(
        models.QRScanEvent(
            session_id=_operator_session_id(current_user),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            product_id=product_id,
            qr_value=qr_token.token_prefix,
            source="qr_token_admin",
            variant_id="qr_token_admin_v1",
            metadata_json=json.dumps(
                {
                    **_operator_metadata(current_user),
                    **event_payload,
                    "token_id": qr_token.id,
                    "token_prefix": qr_token.token_prefix,
                },
                ensure_ascii=False,
            ),
        )
    )


@router.get(
    "/products/{product_id}",
    response_model=schemas.QRTokenListResponse,
)
def list_product_qr_tokens(
    product_id: str,
    token_status: str = Query(default="all", max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_qr_token_operator),
) -> schemas.QRTokenListResponse:
    normalized_status = token_status.strip().lower()
    if normalized_status not in _TOKEN_STATUSES:
        raise HTTPException(status_code=400, detail="token_status must be one of all, active, revoked, expired")

    product = _get_manageable_product(db, product_id, current_user)

    now = datetime.now(UTC)
    tokens = (
        db.query(models.QRToken)
        .filter(models.QRToken.product_id == product.id)
        .order_by(models.QRToken.issued_at.desc(), models.QRToken.id.asc())
        .all()
    )
    summaries = [_token_summary(qr_token, now=now) for qr_token in tokens]
    counts = {
        "active": sum(1 for item in summaries if item.status == "active"),
        "revoked": sum(1 for item in summaries if item.status == "revoked"),
        "expired": sum(1 for item in summaries if item.status == "expired"),
    }
    filtered = summaries if normalized_status == "all" else [item for item in summaries if item.status == normalized_status]
    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    offset = (current_page - 1) * page_size

    return schemas.QRTokenListResponse(
        status="success",
        product_id=product.id,
        items=filtered[offset : offset + page_size],
        total=total,
        active_count=counts["active"],
        revoked_count=counts["revoked"],
        expired_count=counts["expired"],
        page=current_page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/products/{product_id}/reissue",
    response_model=schemas.QRTokenReissueResponse,
)
def reissue_product_qr_token(
    product_id: str,
    request: schemas.QRTokenReissueRequest | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_qr_token_operator),
) -> schemas.QRTokenReissueResponse:
    product = _get_manageable_product(db, product_id, current_user)

    payload = request or schemas.QRTokenReissueRequest()
    try:
        raw_token, qr_token, revoked_tokens = reissue_qr_token(
            db,
            product_id=product.id,
            revoke_existing=payload.revoke_existing,
            expires_at=payload.expires_at,
        )
        product.qr_code = build_public_qr_code(raw_token)
        _record_qr_token_admin_event(
            db,
            current_user=current_user,
            event_type="qr_token_reissued",
            product_id=product.id,
            qr_token=qr_token,
            event_payload={
                "revoke_existing": payload.revoke_existing,
                "revoked_token_ids": [token.id for token in revoked_tokens],
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
            },
        )
        db.commit()
        db.refresh(qr_token)
        db.refresh(product)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"QR token reissue failed: {str(exc)}") from exc

    return schemas.QRTokenReissueResponse(
        status="success",
        product_id=product.id,
        qr_code=product.qr_code,
        token=raw_token,
        token_summary=_token_summary(qr_token),
        revoked_token_ids=[token.id for token in revoked_tokens],
    )


@router.post("/{token_id}/revoke", response_model=schemas.QRTokenRevokeResponse)
def revoke_product_qr_token(
    token_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_qr_token_operator),
) -> schemas.QRTokenRevokeResponse:
    qr_token = _get_manageable_qr_token(db, token_id, current_user)

    was_already_revoked = qr_token.revoked_at is not None
    try:
        revoke_qr_token(qr_token)
        _record_qr_token_admin_event(
            db,
            current_user=current_user,
            event_type="qr_token_revoked",
            product_id=qr_token.product_id,
            qr_token=qr_token,
            event_payload={"already_revoked": was_already_revoked},
        )
        db.commit()
        db.refresh(qr_token)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"QR token revocation failed: {str(exc)}") from exc

    return schemas.QRTokenRevokeResponse(status="success", token_summary=_token_summary(qr_token))
