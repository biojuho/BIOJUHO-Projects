import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import models
from sqlalchemy.orm import Session

DEFAULT_TOKEN_BYTES = 32
DEFAULT_TOKEN_TTL_DAYS = 365


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def qr_token_pepper() -> str:
    return (
        os.environ.get("QR_TOKEN_PEPPER", "").strip()
        or os.environ.get("SECRET_KEY", "").strip()
        or "INSECURE-DEV-QR-PEPPER"
    )


def generate_qr_token() -> str:
    token_bytes = max(16, _int_env("QR_TOKEN_BYTES", DEFAULT_TOKEN_BYTES))
    return secrets.token_urlsafe(token_bytes)


def hash_qr_token(token: str) -> str:
    payload = f"{qr_token_pepper()}:{token}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def token_prefix(token: str) -> str:
    return token[:10]


def public_batch_code(product_id: str) -> str:
    digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"AG-{digest}"


def default_expires_at(now: datetime | None = None) -> datetime | None:
    ttl_days = _int_env("QR_TOKEN_TTL_DAYS", DEFAULT_TOKEN_TTL_DAYS)
    if ttl_days <= 0:
        return None
    baseline = now or datetime.now(UTC)
    return baseline + timedelta(days=ttl_days)


def build_public_qr_code(token: str) -> str:
    base_url = os.environ.get("PUBLIC_VERIFY_BASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}/verify/{token}"
    return f"agri://verify/{token}"


def issue_qr_token(
    db: Session,
    *,
    product_id: str,
    batch_code: str | None = None,
    expires_at: datetime | None = None,
    raw_token: str | None = None,
) -> tuple[str, models.QRToken]:
    token = raw_token or generate_qr_token()
    qr_token = models.QRToken(
        id=str(uuid.uuid4()),
        product_id=product_id,
        token_hash=hash_qr_token(token),
        token_prefix=token_prefix(token),
        batch_code=batch_code or public_batch_code(product_id),
        issued_at=datetime.now(UTC),
        expires_at=expires_at if expires_at is not None else default_expires_at(),
    )
    db.add(qr_token)
    return token, qr_token


def lookup_qr_token(db: Session, token: str) -> models.QRToken | None:
    return db.query(models.QRToken).filter(models.QRToken.token_hash == hash_qr_token(token)).first()


def is_token_expired(qr_token: models.QRToken, *, now: datetime) -> bool:
    if qr_token.expires_at is None:
        return False
    expires_at = qr_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def active_qr_tokens_for_product(
    db: Session,
    *,
    product_id: str,
    now: datetime | None = None,
) -> list[models.QRToken]:
    baseline = now or datetime.now(UTC)
    tokens = (
        db.query(models.QRToken)
        .filter(models.QRToken.product_id == product_id, models.QRToken.revoked_at.is_(None))
        .all()
    )
    return [token for token in tokens if not is_token_expired(token, now=baseline)]


def revoke_qr_token(qr_token: models.QRToken, *, now: datetime | None = None) -> models.QRToken:
    if qr_token.revoked_at is None:
        qr_token.revoked_at = now or datetime.now(UTC)
    return qr_token


def reissue_qr_token(
    db: Session,
    *,
    product_id: str,
    batch_code: str | None = None,
    expires_at: datetime | None = None,
    revoke_existing: bool = True,
    now: datetime | None = None,
) -> tuple[str, models.QRToken, list[models.QRToken]]:
    baseline = now or datetime.now(UTC)
    revoked_tokens: list[models.QRToken] = []
    if revoke_existing:
        revoked_tokens = active_qr_tokens_for_product(db, product_id=product_id, now=baseline)
        for existing_token in revoked_tokens:
            revoke_qr_token(existing_token, now=baseline)

    raw_token, qr_token = issue_qr_token(
        db,
        product_id=product_id,
        batch_code=batch_code,
        expires_at=expires_at,
    )
    return raw_token, qr_token, revoked_tokens
