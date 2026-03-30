from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrackingEvent(BaseModel):
    timestamp: datetime
    status: str
    location: str
    handler_id: str

    model_config = ConfigDict(from_attributes=True)


class Certificate(BaseModel):
    cert_id: str
    issued_by: str
    issue_date: datetime
    cert_type: str  # e.g., "Organic", "GAP"

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    description: str
    category: str
    origin: str | None = "Unknown"
    harvest_date: datetime | None = None
    requires_cold_chain: bool = False


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    id: str
    owner_id: str
    tracking_history: list[TrackingEvent] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    is_verified: bool = False
    qr_code: str  # Simulation string

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    role: str  # Farmer, Distributor, Retailer, Consumer
    name: str
    organization: str


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GrowthCycles(BaseModel):
    active: int
    completed: int


class RecentActivity(BaseModel):
    timestamp: str
    event: str


class DashboardData(BaseModel):
    total_farms: int
    active_sensors: int
    critical_alerts: int
    growth_cycles: GrowthCycles
    recent_activity: list[RecentActivity]


class DashboardResponse(BaseModel):
    status: str
    data: DashboardData


class QRScanEventCreate(BaseModel):
    session_id: str
    event_type: str
    occurred_at: datetime | None = None
    product_id: str | None = None
    qr_value: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    recovery_method: str | None = None
    source: str = "qr_reader"
    variant_id: str = "qr_page_v1"
    event_payload: dict[str, Any] = Field(default_factory=dict)


class QRScanEventResponse(BaseModel):
    status: str
    event_id: str
