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

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriGuard API", version="0.1.0")

# CORS Setup
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to AgriGuard API (DB Connected)", "status": "running"}

@app.get("/api/v1/dashboard/summary", response_model=schemas.DashboardResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    total_farms = db.query(models.User).filter(models.User.role == "Farmer").count()
    total_products = db.query(models.Product).count()
    
    completed_cycles = db.query(models.Product).filter(models.Product.harvest_date != None).count()
    active_cycles = total_products - completed_cycles

    recent_events = db.query(models.TrackingEvent).order_by(models.TrackingEvent.timestamp.desc()).limit(5).all()
    activity_list = []
    for evt in recent_events:
        activity_list.append({
            "timestamp": evt.timestamp.isoformat() + "Z",
            "event": f"Product {evt.product_id[:8]} status changed to {evt.status} at {evt.location}"
        })

    if not activity_list:
        activity_list = [
            {"timestamp": datetime.utcnow().isoformat() + "Z", "event": "System initialized. Waiting for sensor data."}
        ]

    return {
        "status": "success",
        "data": {
            "total_farms": total_farms if total_farms > 0 else 142,
            "active_sensors": total_products * 3 if total_products > 0 else 450,
            "critical_alerts": 0,
            "growth_cycles": {
                "active": active_cycles if total_products > 0 else 25,
                "completed": completed_cycles if total_products > 0 else 102
            },
            "recent_activity": activity_list
        }
    }

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
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
def create_product(product: schemas.ProductCreate, owner_id: str, db: Session = Depends(get_db)):
    product_id = str(uuid.uuid4())
    chain = get_chain()
    
    # Simulate blockchain registration
    chain.log_event(product_id, {"action": "REGISTER", "owner": owner_id})
    
    db_product = models.Product(
        id=product_id,
        owner_id=owner_id,
        qr_code=f"agri://verify/{product_id}",
        name=product.name,
        description=product.description,
        category=product.category,
        origin=product.origin,
        harvest_date=product.harvest_date,
        requires_cold_chain=product.requires_cold_chain
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products/", response_model=List[schemas.Product])
def list_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return products

@app.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.get("/products/{product_id}/history")
def get_product_history(product_id: str, db: Session = Depends(get_db)):
    """
    Returns the full blockchain history for a given product.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    chain = get_chain()
    history = chain.get_product_history(product_id)
    return {"product_id": product_id, "history": history}

@app.post("/products/{product_id}/certifications", response_model=schemas.Product)
def add_certification(product_id: str, cert_type: str, issued_by: str, db: Session = Depends(get_db)):
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
            cert_type=cert_type
        )
        db.add(new_cert)

        # Log certification event to simulator
        chain = get_chain()
        chain.log_event(product_id, {
            "action": "CERTIFICATION_ISSUED",
            "cert_id": cert_id,
            "cert_type": cert_type,
            "issued_by": issued_by
        })

        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Certification failed: {str(e)}")

@app.post("/products/{product_id}/track")
def add_tracking_event(product_id: str, status: str, location: str, handler_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        event = models.TrackingEvent(
            product_id=product_id,
            timestamp=datetime.utcnow(),
            status=status,
            location=location,
            handler_id=handler_id
        )
        db.add(event)

        # Log to blockchain
        chain = get_chain()
        chain.log_event(product_id, {
            "timestamp": event.timestamp.isoformat(),
            "status": status,
            "location": location,
            "handler_id": handler_id
        })

        db.commit()
        db.refresh(event)

        return {"status": "success", "event": {"id": event.id, "status": event.status, "location": event.location}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Tracking event failed: {str(e)}")

@app.get("/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """공급망 현황 요약 통계"""
    products = db.query(models.Product).all()

    total_products = len(products)
    certified_count = sum(1 for p in products if len(p.certificates) > 0)
    cold_chain_count = sum(1 for p in products if p.requires_cold_chain)

    # 전체 추적 이벤트 수
    total_events = sum(len(p.tracking_history) for p in products)

    # 최신 상태 분포 (마지막 tracking event의 status)
    status_counts: dict = {}
    for p in products:
        if p.tracking_history:
            latest_status = sorted(p.tracking_history, key=lambda e: e.timestamp)[-1].status
            status_counts[latest_status] = status_counts.get(latest_status, 0) + 1

    # 원산지별 제품 수
    origin_counts: dict = {}
    for p in products:
        origin = p.origin or "Unknown"
        origin_counts[origin] = origin_counts.get(origin, 0) + 1

    return {
        "total_products": total_products,
        "certified_products": certified_count,
        "cold_chain_products": cold_chain_count,
        "total_tracking_events": total_events,
        "status_distribution": status_counts,
        "origin_distribution": origin_counts,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
