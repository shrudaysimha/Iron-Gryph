"""Pydantic schemas for Patient and Admission."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ---------- Patient ----------

class PatientBase(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)
    gender: str
    blood_group: str | None = None
    phone: str | None = None
    emergency_contact: str | None = None
    address: str | None = None
    condition: str | None = None
    triage_score: int = Field(default=3, ge=1, le=5)
    arrival_mode: str = "walk_in"


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    arrival_time: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Admission ----------

class AdmissionBase(BaseModel):
    department: str = "emergency"
    diagnosis: str | None = None
    severity: str = "moderate"
    notes: str | None = None


class AdmissionCreate(AdmissionBase):
    patient_id: int
    hospital_id: int
    bed_id: int | None = None
    attending_doctor_id: int | None = None


class AdmitPatientRequest(BaseModel):
    """Combined request to create a patient and admit them in one call."""
    # Patient info
    name: str
    age: int = Field(ge=0, le=150)
    gender: str
    blood_group: str | None = None
    phone: str | None = None
    emergency_contact: str | None = None
    condition: str | None = None
    triage_score: int = Field(default=3, ge=1, le=5)
    arrival_mode: str = "walk_in"

    # Admission info
    hospital_id: int
    department: str = "emergency"
    diagnosis: str | None = None
    severity: str = "moderate"
    bed_id: int | None = None
    attending_doctor_id: int | None = None


class DischargeRequest(BaseModel):
    notes: str | None = None


class AdmissionResponse(AdmissionBase):
    id: int
    patient_id: int
    hospital_id: int
    bed_id: int | None
    attending_doctor_id: int | None
    status: str
    admitted_at: datetime
    discharged_at: datetime | None
    expected_discharge: datetime | None
    length_of_stay_hours: float | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdmissionDetail(AdmissionResponse):
    patient: PatientResponse | None = None
