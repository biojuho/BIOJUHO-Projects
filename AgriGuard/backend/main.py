import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

import models
import schemas
from database import SessionLocal, engine
from services.chain_simulator import get_chain
from auth import get_current_user

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriGuard API", version="0.1.0")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fallback values used when the DB has no real data yet (demo mode)
DEMO_TOTAL_FARMS = 142
DEMO_SENSORS_PER_PRODUCT = 3
DEMO_ACTIVE_SENSORS = 450
DEMO_ACTIVE_CYCLES = 25
DEMO_COMPLETED_CYCLES = 102


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_latest_status_per_product(product: models.Product) -> str | None:
    if not product.tracking_history:
        return None
    return max(product.tracking_history, key=lambda event: event.timestamp).status


def _build_status_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        latest_status = _get_latest_status_per_product(product)
        if latest_status:
            distribution[latest_status] = distribution.get(latest_status, 0) + 1
    return distribution


def _build_origin_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        origin = product.origin or "Unknown"
        distribution[origin] = distribution.get(origin, 0) + 1
    return distribution


def _format_tracking_event_as_activity(event: models.TrackingEvent) -> dict:
    return {
        "timestamp": event.timestamp.isoformat() + "Z",
        "event": f"Product {event.product_id[:8]} status changed to {event.status} at {event.location}",
    }


@app.get("/")
def read_root():
    return {"message": "Welcome to AgriGuard API (DB Connected)", "status": "running"}


@app.get("/api/v1/dashboard/summary", response_model=schemas.DashboardResponse)
def get_frontend_dashboard_summary(db: Session = Depends(get_db)):
    farmer_count = db.query(models.User).filter(models.User.role == "Farmer").count()
    total_products = db.query(models.Product).count()
    harvested_products = db.query(models.Product).filter(models.Product.harvest_date != None).count()
    active_cycles = total_products - harvested_products

    recent_events = (
        db.query(models.TrackingEvent)
        .order_by(models.TrackingEvent.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_activity = [_format_tracking_event_as_activity(e) for e in recent_events]

    if not recent_activity:
        recent_activity = [
            {"timestamp": datetime.utcnow().isoformat() + "Z", "event": "System initialized. Waiting for sensor data."}
        ]

    has_real_data = total_products > 0
    return {
        "status": "success",
        "data": {
            "total_farms": farmer_count if has_real_data else DEMO_TOTAL_FARMS,
            "active_sensors": total_products * DEMO_SENSORS_PER_PRODUCT if has_real_data else DEMO_ACTIVE_SENSORS,
            "critical_alerts": 0,
            "growth_cycles": {
                "active": active_cycles if has_real_data else DEMO_ACTIVE_CYCLES,
                "completed": harvested_products if has_real_data else DEMO_COMPLETED_CYCLES,
            },
            "recent_activity": recent_activity,
        },
    }


@app.get("/dashboard/summary")
def get_supply_chain_summary(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()

    certified_count = sum(1 for p in products if p.certificates)
    cold_chain_count = sum(1 for p in products if p.requires_cold_chain)
    total_tracking_events = sum(len(p.tracking_history) for p in products)

    return {
        "total_products": len(products),
        "certified_products": certified_count,
        "cold_chain_products": cold_chain_count,
        "total_tracking_events": total_tracking_events,
        "status_distribution": _build_status_distribution(products),
        "origin_distribution": _build_origin_distribution(products),
    }


@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_user = models.User(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        role=user.role,
        name=user.name,
        organization=user.organization
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/products/", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate, owner_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    product_id = str(uuid.uuid4())
    get_chain().log_event(product_id, {"action": "REGISTER", "owner": owner_id})

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
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.get("/products/", response_model=List[schemas.Product])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()


@app.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/products/{product_id}/history")
def get_product_history(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    history = get_chain().get_product_history(product_id)
    return {"product_id": product_id, "history": history}


@app.post("/products/{product_id}/certifications", response_model=schemas.Product)
def add_certification(product_id: str, cert_type: str, issued_by: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        new_cert = models.Certificate(
            cert_id=cert_id,
            product_id=product_id,
            issued_by=issued_by,
            issue_date=datetime.utcnow(),
            cert_type=cert_type,
        )
        db.add(new_cert)
        get_chain().log_event(product_id, {
            "action": "CERTIFICATION_ISSUED",
            "cert_id": cert_id,
            "cert_type": cert_type,
            "issued_by": issued_by,
        })
        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Certification failed: {str(e)}")


@app.post("/products/{product_id}/track")
def add_tracking_event(product_id: str, status: str, location: str, handler_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        event = models.TrackingEvent(
            product_id=product_id,
            timestamp=datetime.utcnow(),
            status=status,
            location=location,
            handler_id=handler_id,
        )
        db.add(event)
        get_chain().log_event(product_id, {
            "timestamp": event.timestamp.isoformat(),
            "status": status,
            "location": location,
            "handler_id": handler_id,
        })
        db.commit()
        db.refresh(event)
        return {"status": "success", "event": {"id": event.id, "status": event.status, "location": event.location}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Tracking event failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
