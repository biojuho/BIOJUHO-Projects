import logging
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from dependencies import get_db
import models
import schemas
from datetime import UTC, datetime, timedelta
from auth import get_current_user
from services.chain_simulator import get_chain


logger = logging.getLogger(__name__)
router = APIRouter()


def _log_chain_event_after_commit(product_id: str, event_payload: dict) -> None:
    """Write chain events only after the DB commit succeeds."""
    try:
        get_chain().log_event(product_id, event_payload)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Chain log failed after DB commit for product %s", product_id, exc_info=exc)

@router.post("/products/", response_model=schemas.Product)
def create_product(
    product: schemas.ProductCreate,
    owner_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product_id = str(uuid.uuid4())

    db_product = models.Product(
        id=product_id,
        owner_id=owner_id,
        qr_code=f"agri://verify/{product_id}",
        name=product.name,
        description=product.description,
        category=product.category,
        origin=product.origin,
        harvest_date=product.harvest_date,
        requires_cold_chain=product.requires_cold_chain,
    )
    try:
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Product creation failed: {str(e)}") from e

    _log_chain_event_after_commit(product_id, {"action": "REGISTER", "owner": owner_id})
    return db_product


@router.get("/products/", response_model=list[schemas.Product])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()


@router.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}/history")
def get_product_history(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    history = get_chain().get_product_history(product_id)
    return {"product_id": product_id, "history": history}


@router.post("/products/{product_id}/certifications", response_model=schemas.Product)
def add_certification(
    product_id: str,
    cert_type: str,
    issued_by: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        new_cert = models.Certificate(
            cert_id=cert_id,
            product_id=product_id,
            issued_by=issued_by,
            issue_date=datetime.now(UTC),
            cert_type=cert_type,
        )
        db.add(new_cert)
        db.commit()
        db.refresh(product)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Certification failed: {str(e)}") from e

    _log_chain_event_after_commit(
        product_id,
        {
            "action": "CERTIFICATION_ISSUED",
            "cert_id": cert_id,
            "cert_type": cert_type,
            "issued_by": issued_by,
        },
    )
    return product


@router.post("/products/{product_id}/track")
def add_tracking_event(
    product_id: str,
    status: str,
    location: str,
    handler_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        event_timestamp = datetime.now(UTC)
        event = models.TrackingEvent(
            product_id=product_id,
            timestamp=event_timestamp,
            status=status,
            location=location,
            handler_id=handler_id,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Tracking event failed: {str(e)}") from e

    _log_chain_event_after_commit(
        product_id,
        {
            "timestamp": event_timestamp.isoformat(),
            "status": status,
            "location": location,
            "handler_id": handler_id,
        },
    )
    return {"status": "success", "event": {"id": event.id, "status": event.status, "location": event.location}}
