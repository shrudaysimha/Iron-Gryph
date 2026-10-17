"""Pydantic schemas for Staff."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StaffBase(BaseModel):
    name: str
    employee_id: str
    role: str
    specialization: str | None = None
    phone: str | None = None
    current_shift: str = "off"
    max_patients: int = 10


class StaffCreate(StaffBase):
    hospital_id: int


class StaffUpdate(BaseModel):
    current_shift: str | None = None
    on_duty: bool | None = None
    is_available: bool | None = None
    shift_start: datetime | None = None
    shift_end: datetime | None = None
    current_patients: int | None = None


class StaffResponse(StaffBase):
    id: int
    hospital_id: int
    on_duty: bool
    is_available: bool
    current_patients: int
    shift_start: datetime | None
    shift_end: datetime | None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StaffAvailability(BaseModel):
    hospital_id: int
    total_staff: int
    on_duty: int
    off_duty: int
    doctors_on_duty: int
    nurses_on_duty: int
    paramedics_on_duty: int
    staff_to_patient_ratio: float
