"""Pydantic schemas for bed reservation system."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BedReserveRequest(BaseModel):
    """Request to reserve a specific bed."""
    bed_id: int | str
    hospital_id: int = 1
    patient_name: str | None = "Emergency Patient"
    coordinator_id: str | None = None
    triage_score: int = 3  # 1=Resuscitation, 2=Emergency, 3=Urgent


class BedReserveResponse(BaseModel):
    """Response after a successful bed reservation."""
    success: bool
    token: str
    reservation_token: str
    bed_id: int | str
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


# ---- Voice-Enabled Bed Reservation & Hospital Contact Schemas ----
from typing import Any, Dict, List
from pydantic import Field


class VerifiedStaffProfile(BaseModel):
    """Pre-verified user profile passed from authenticated clinical session."""
    employee_id: str | None = Field(default="EMP-1005", description="Verified Employee/Badge ID")
    name: str | None = Field(default="Dr. Rajiv Mehta", description="Physician / Clinician Full Name")
    role: str | None = Field(default="doctor", description="Role cadre: doctor, nurse, paramedic, admin")
    title: str | None = Field(default="Chief Trauma Surgeon & Medical Director", description="Clinical Title")
    department: str | None = Field(default="Emergency Trauma & Surgical ICU", description="Hospital Department")
    hospital: str | None = Field(default="SIDS Hospital Surat", description="Hospital Station Base")
    specialization: str | None = Field(default="Trauma & Critical Care", description="Specialization")


class VoiceBedContactRequest(BaseModel):
    """Voice command payload to contact hospital and reserve bed."""
    audio_transcript: str = Field(..., description="Spoken voice directive transcription")
    hospital_id: int = Field(default=1, description="Target Hospital ID")
    staff_profile: VerifiedStaffProfile | None = Field(default=None, description="Pre-verified staff profile")
    target_bed_id: str | None = Field(default=None, description="Optional explicit bed identifier")


class ClinicalVoiceAnalysis(BaseModel):
    """Entities and clinical triage extracted by the voice processing model."""
    intent: str
    acuity_level: str
    triage_score: int
    urgency: str
    target_ward_type: str
    patient_condition: str
    equipment_needed: List[str]
    requires_ventilator: bool
    requires_oxygen: bool
    eta_minutes: int | None = 5
    extracted_bed_number: str | None = None


class VoiceBedContactResponse(BaseModel):
    """Structured response from voice processing model and atomic bed lock."""
    success: bool
    transcription_processed: str
    model_analysis: ClinicalVoiceAnalysis
    verified_staff: Dict[str, Any]
    reservation: Dict[str, Any] | None = None
    speech_feedback: str
    message: str
