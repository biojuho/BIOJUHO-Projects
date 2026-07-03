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


class ProductPage(BaseModel):
    items: list[Product]
    total: int
    page: int
    page_size: int
    total_pages: int


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


class QRKPISummaryResponse(BaseModel):
    status: str
    hours: int
    variant_id: str
    since: datetime
    scan_start_sessions: int
    scan_success_sessions: int
    scan_failure_sessions: int
    verification_complete_sessions: int
    consumer_scan_sessions: int
    scan_success_rate: float
    target_scan_success_rate: float
    scan_success_status: str
    target_daily_scans: int
    daily_scan_progress: float
    daily_scan_status: str


class QRKPITrendPoint(BaseModel):
    date: str
    scan_start_sessions: int
    scan_success_sessions: int
    verification_complete_sessions: int
    scan_success_rate: float
    daily_scan_progress: float
    scan_success_status: str
    daily_scan_status: str


class QRKPITrendResponse(BaseModel):
    status: str
    days: int
    variant_id: str
    timezone: str
    target_scan_success_rate: float
    target_daily_scans: int
    items: list[QRKPITrendPoint] = Field(default_factory=list)


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


class QRTokenAdminSummary(BaseModel):
    id: str
    product_id: str
    token_prefix: str
    batch_code: str
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_verified_at: datetime | None = None
    scan_count: int = 0
    is_active: bool
    status: str

    model_config = ConfigDict(from_attributes=True)


class QRTokenListResponse(BaseModel):
    status: str
    product_id: str
    items: list[QRTokenAdminSummary] = Field(default_factory=list)
    total: int
    active_count: int
    revoked_count: int
    expired_count: int
    page: int
    page_size: int
    total_pages: int


class QRTokenReissueRequest(BaseModel):
    revoke_existing: bool = True
    expires_at: datetime | None = None


class QRTokenReissueResponse(BaseModel):
    status: str
    product_id: str
    qr_code: str
    token: str
    token_summary: QRTokenAdminSummary
    revoked_token_ids: list[str] = Field(default_factory=list)


class QRTokenRevokeResponse(BaseModel):
    status: str
    token_summary: QRTokenAdminSummary


class SensorDeviceUpsertRequest(BaseModel):
    owner_id: str | None = Field(default=None, max_length=120)
    clear_owner: bool = False
    label: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=120)
    expected_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    is_active: bool = True


class SensorDeviceSummary(BaseModel):
    sensor_id: str
    owner_id: str | None = None
    label: str | None = None
    zone: str | None = None
    expected_interval_minutes: int | None = None
    is_active: bool
    registered_at: datetime
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_battery: float | None = None
    last_status: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SensorDeviceListResponse(BaseModel):
    status: str
    items: list[SensorDeviceSummary] = Field(default_factory=list)
    total: int
    active_count: int
    disabled_count: int
    page: int
    page_size: int
    total_pages: int


class SensorDeviceActionResponse(BaseModel):
    status: str
    sensor: SensorDeviceSummary


class UnsupportedSensorIdentityListResponse(BaseModel):
    status: str
    items: list[SensorDeviceSummary] = Field(default_factory=list)
    total: int
    active_count: int
    disabled_count: int
    safe_pattern: str
    notes: list[str] = Field(default_factory=list)


class UnsupportedSensorIdentityCleanupRequest(BaseModel):
    sensor_ids: list[str] | None = Field(default=None, max_length=100)


class UnsupportedSensorIdentityCleanupResponse(BaseModel):
    status: str
    disabled_count: int
    disabled_sensor_ids: list[str] = Field(default_factory=list)
    skipped_sensor_ids: list[str] = Field(default_factory=list)
    items: list[SensorDeviceSummary] = Field(default_factory=list)


class UnsupportedSensorIdentityReissueRequest(BaseModel):
    old_sensor_id: str = Field(min_length=1, max_length=120)
    new_sensor_id: str = Field(min_length=1, max_length=120)


class UnsupportedSensorIdentityReissueResponse(BaseModel):
    status: str
    source_sensor: SensorDeviceSummary
    replacement_sensor: SensorDeviceSummary
    broker_rotation_required: bool = True
    notes: list[str] = Field(default_factory=list)


class MQTTRejectionEventSummary(BaseModel):
    id: str
    sensor_id: str | None = None
    reason: str | None = None
    occurred_at: datetime
    error_message: str | None = None
    registry_required: bool | None = None


class MQTTRejectionListResponse(BaseModel):
    status: str
    items: list[MQTTRejectionEventSummary] = Field(default_factory=list)
    total: int
    reason_counts: dict[str, int] = Field(default_factory=dict)
    window_hours: int
    page: int
    page_size: int
    total_pages: int


class MQTTBrokerProvisioningResponse(BaseModel):
    status: str
    generated_at: datetime
    active_sensor_count: int
    disabled_sensor_count: int
    unsupported_sensor_ids: list[str] = Field(default_factory=list)
    acl_file: str
    password_file_commands: list[str] = Field(default_factory=list)
    password_file_delete_commands: list[str] = Field(default_factory=list)
    dynamic_security_commands: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MQTTBrokerProvisioningEvidenceRequest(BaseModel):
    mode: str = Field(default="combined", max_length=40)
    artifact_hash: str = Field(min_length=64, max_length=64)
    artifact_generated_at: datetime | None = None
    applied_at: datetime | None = None
    broker_host: str | None = Field(default=None, max_length=160)
    runbook_reference: str | None = Field(default=None, max_length=240)
    active_sensor_count: int = Field(ge=0)
    disabled_sensor_count: int = Field(ge=0)
    unsupported_sensor_count: int = Field(ge=0)
    credential_rotation_required: bool = True
    rotation_note: str | None = Field(default=None, max_length=500)


class MQTTBrokerProvisioningEvidenceSummary(BaseModel):
    id: str
    recorded_at: datetime
    applied_at: datetime
    mode: str
    artifact_hash: str
    artifact_generated_at: datetime | None = None
    broker_host: str | None = None
    runbook_reference: str | None = None
    active_sensor_count: int
    disabled_sensor_count: int
    unsupported_sensor_count: int
    credential_rotation_required: bool
    actor_uid: str | None = None
    actor_email: str | None = None
    rotation_note: str | None = None


class MQTTBrokerProvisioningEvidenceResponse(BaseModel):
    status: str
    latest: MQTTBrokerProvisioningEvidenceSummary | None = None


class MQTTBrokerProvisioningEvidenceHistoryResponse(BaseModel):
    status: str
    items: list[MQTTBrokerProvisioningEvidenceSummary] = Field(default_factory=list)
    total: int
    broker_host: str | None = None
    page: int
    page_size: int
    total_pages: int
