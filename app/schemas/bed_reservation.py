"""Pydantic schemas for bed reservation system."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BedReserveRequest(BaseModel):
    """Request to reserve a specific bed."""
    bed_id: int
    hospital_id: int
    patient_name: str
    triage_score: int = 3  # 1=Resuscitation, 2=Emergency, 3=Urgent


class BedReserveResponse(BaseModel):
    """Response after a successful bed reservation."""
    success: bool
    reservation_token: str
    bed_id: int
    bed_number: str
    ward_name: str
    ward_type: str
    bed_type: str
    status: str
    expires_at: datetime
    ttl_seconds: int
    message: str


class BedStatusResponse(BaseModel):
    """Status of an individual bed in the grid."""
    id: int
    bed_number: str
    bed_type: str
    status: str  # available, occupied, reserved, maintenance
    has_monitor: bool
    has_oxygen: bool
    ward_id: int
    ward_name: str
    ward_type: str
    reservation_expires_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WardBedGrid(BaseModel):
    """All beds in a single ward."""
    ward_id: int
    ward_name: str
    ward_type: str
    floor: int | None
    total_beds: int
    available_beds: int
    beds: list[BedStatusResponse]


class BedGridResponse(BaseModel):
    """Full bed grid for a hospital."""
    hospital_id: int
    wards: list[WardBedGrid]
    total_beds: int
    total_available: int
    total_occupied: int
    total_reserved: int
    total_maintenance: int
    generated_at: datetime
