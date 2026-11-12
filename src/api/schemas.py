
"""
Pydantic schemas for the Reverse Logistics API.
Uses the actual SQLAlchemy project schema.
"""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    total_assets: int
    total_shipments: int
    total_custody_events: int
    total_rmas: int


class AssetSummary(BaseModel):
    asset_id: int
    asset_code: str
    serial_number: Optional[str] = None
    asset_type_name: str
    lifecycle_status: str
    deposit_amount: float
    created_at: datetime


class AssetDetail(AssetSummary):
    owner_name: Optional[str] = None
    current_location_name: Optional[str] = None
    last_event_time: Optional[datetime] = None


class TrajectoryEvent(BaseModel):
    event_id: int
    event_type: str
    event_timestamp: str
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    actor_name: str
    shipment_code: Optional[str] = None
    notes: Optional[str] = None


class TrajectoryResponse(BaseModel):
    asset_id: int
    asset_code: str
    serial_number: Optional[str] = None
    lifecycle_status: str
    current_location: str
    current_location_description: str
    is_in_transit: bool
    current_custodian: str
    last_event_time: Optional[str] = None
    total_events: int
    trajectory: List[TrajectoryEvent]


class CustodyEventCreate(BaseModel):
    asset_id: int = Field(..., description="Existing reusable asset ID")
    event_type: Literal["dispatch", "transfer", "receipt", "return"]
    to_location_id: int = Field(..., description="Destination location ID")
    from_location_id: Optional[int] = None
    shipment_id: Optional[int] = None
    actor_name: str = Field(..., min_length=1, max_length=150)
    notes: Optional[str] = None


class CustodyEventResponse(BaseModel):
    event_id: int
    asset_id: int
    event_type: str
    event_timestamp: datetime
    actor_name: str
    status: str = "INGESTED"


class RMAResponse(BaseModel):
    return_id: int
    return_code: str
    asset_id: int
    shipment_id: Optional[int] = None
    requested_by: str
    request_date: datetime
    approved_date: Optional[datetime] = None
    return_status: str
    inspection_condition: Optional[str] = None
    inspection_remarks: Optional[str] = None
    repair_status: Optional[str] = None


class AnomalyItem(BaseModel):
    rule_code: str
    rule_name: str
    asset_id: int
    severity: str
    details: str
