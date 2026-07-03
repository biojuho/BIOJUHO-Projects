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

class QRTrustBadge(BaseModel):
    status: str
    label: str
    reason: str


class QRPublicProduct(BaseModel):
    name: str
    category: str
    origin: str


class QRBatchSummary(BaseModel):
    batch_code: str
    harvest_date: datetime | None = None
    cold_chain_required: bool
    recall_status: str = "not_reported"


class QRRouteCheckpoint(BaseModel):
    timestamp: datetime
    status: str
    location: str


class QRTemperatureSummary(BaseModel):
    status: str
    message: str
    min_celsius: float | None = None
    max_celsius: float | None = None
    average_celsius: float | None = None
    readings_count: int = 0
    last_reading_at: datetime | None = None
    is_stale: bool = False


class QRBlockchainRecord(BaseModel):
    tx_hash: str
    block: str
    timestamp: datetime | None = None
    event_type: str


class QRBlockchainProof(BaseModel):
    status: str
    message: str
    record_count: int = 0
    latest_tx_hash: str | None = None
    evidence_hash: str
    records: list[QRBlockchainRecord] = Field(default_factory=list)


class QRVerifyResponse(BaseModel):
    status: str
    is_valid: bool
    verified_at: datetime
    last_verified_at: datetime
    trust_badge: QRTrustBadge
    product: QRPublicProduct | None = None
    batch: QRBatchSummary | None = None
    route: list[QRRouteCheckpoint] = Field(default_factory=list)
    temperature_summary: QRTemperatureSummary
    blockchain_proof: QRBlockchainProof
    consumer_notice: str
