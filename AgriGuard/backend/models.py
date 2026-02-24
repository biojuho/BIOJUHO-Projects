from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    role = Column(String, index=True)
    name = Column(String)
    organization = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    description = Column(String)
    category = Column(String)
    origin = Column(String, default="Unknown")
    harvest_date = Column(DateTime, nullable=True)
    requires_cold_chain = Column(Boolean, default=False)
    owner_id = Column(String, index=True)
    is_verified = Column(Boolean, default=False)
    qr_code = Column(String)

    # Relationships
    tracking_history = relationship("TrackingEvent", back_populates="product", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="product", cascade="all, delete-orphan")

class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String, ForeignKey("products.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    location = Column(String)
    handler_id = Column(String)

    product = relationship("Product", back_populates="tracking_history")

class Certificate(Base):
    __tablename__ = "certificates"

    cert_id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"))
    issued_by = Column(String)
    issue_date = Column(DateTime, default=datetime.utcnow)
    cert_type = Column(String)

    product = relationship("Product", back_populates="certificates")
