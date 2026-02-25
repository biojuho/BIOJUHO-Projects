from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TrackingEvent(BaseModel):
    timestamp: datetime
    status: str
    location: str
    handler_id: str

    class Config:
        orm_mode = True
        from_attributes = True

class Certificate(BaseModel):
    cert_id: str
    issued_by: str
    issue_date: datetime
    cert_type: str  # e.g., "Organic", "GAP"

    class Config:
        orm_mode = True
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    description: str
    category: str
    origin: Optional[str] = "Unknown"
    harvest_date: Optional[datetime] = None
    requires_cold_chain: bool = False

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: str
    owner_id: str
    tracking_history: List[TrackingEvent] = Field(default_factory=list)
    certificates: List[Certificate] = Field(default_factory=list)
    is_verified: bool = False
    qr_code: str  # Simulation string

    class Config:
        orm_mode = True
        from_attributes = True

class UserBase(BaseModel):
    role: str # Farmer, Distributor, Retailer, Consumer
    name: str
    organization: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

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
    recent_activity: List[RecentActivity]

class DashboardResponse(BaseModel):
    status: str
    data: DashboardData
