from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Index
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
    __table_args__ = (
        Index("ix_products_qr_code", "qr_code", unique=True),
    )

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
    __table_args__ = (
        Index("ix_tracking_events_product_id", "product_id"),
    )

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String, ForeignKey("products.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    location = Column(String)
    handler_id = Column(String)

    product = relationship("Product", back_populates="tracking_history")

class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_product_id", "product_id"),
    )

    cert_id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"))
    issued_by = Column(String)
    issue_date = Column(DateTime, default=datetime.utcnow)
    cert_type = Column(String)

    product = relationship("Product", back_populates="certificates")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index("ix_sensor_readings_sensor_id", "sensor_id"),
        Index("ix_sensor_readings_timestamp", "timestamp"),
        Index("ix_sensor_readings_zone", "zone"),
        Index("ix_sensor_reading_sensor_ts", "sensor_id", "timestamp"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sensor_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    battery = Column(Float)
    zone = Column(String)
    status = Column(String, default="normal")
