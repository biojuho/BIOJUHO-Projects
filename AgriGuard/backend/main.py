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
def create_product(product: schemas.ProductCreate, owner_id: str = "demo-user", db: Session = Depends(get_db)):
    product_id = str(uuid.uuid4())
    chain = get_chain()
    
    # Simulate blockchain registration
    tx_hash = chain.log_event(product_id, {"action": "REGISTER", "owner": owner_id})
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
