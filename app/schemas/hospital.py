"""Pydantic schemas for Hospital, Ward, and Bed."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ---------- Bed ----------

class BedBase(BaseModel):
    bed_number: str
    bed_type: str = "general"
    status: str = "available"
    has_monitor: bool = False
    has_oxygen: bool = False


class BedCreate(BedBase):
    ward_id: int


class BedResponse(BedBase):
    id: int
    ward_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Ward ----------

class WardBase(BaseModel):
    name: str
    ward_type: str = "general"
    floor: int | None = None
    total_beds: int = 20
    available_beds: int = 20


class WardCreate(WardBase):
    hospital_id: int


class WardResponse(WardBase):
    id: int
    hospital_id: int
    is_active: bool
    beds: list[BedResponse] = []
    model_config = ConfigDict(from_attributes=True)


class WardSummary(BaseModel):
    id: int
    name: str
    ward_type: str
    total_beds: int
    available_beds: int
    occupancy_rate: float = 0.0
    model_config = ConfigDict(from_attributes=True)


# ---------- Hospital ----------

class HospitalBase(BaseModel):
    name: str
    address: str
    city: str = "Bangalore"
    state: str = "Karnataka"
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    total_beds: int = 100
    icu_beds: int = 20
    emergency_beds: int = 15
    ventilator_beds: int = 10
    tier: str = "secondary"


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    total_beds: int | None = None
    icu_beds: int | None = None
    emergency_beds: int | None = None
    ventilator_beds: int | None = None
    tier: str | None = None


class HospitalResponse(HospitalBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HospitalDetail(HospitalResponse):
    wards: list[WardSummary] = []


class HospitalCapacity(BaseModel):
    hospital_id: int
    hospital_name: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    occupancy_rate: float
    icu_total: int
    icu_available: int
    emergency_total: int
    emergency_available: int
    ventilator_total: int
    ventilator_available: int
