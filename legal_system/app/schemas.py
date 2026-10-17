"""Pydantic request and response schemas for Legal System."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---- Auth Schemas ----

class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    badge_number: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---- Case Schemas ----

class CaseCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Operation Nightshade: Financial Embezzlement"})
    description: Optional[str] = Field(None, json_schema_extra={"example": "Cross-border illicit wire transfers and falsified ledger accounts"})
    category: str = Field(default="Financial Fraud", json_schema_extra={"example": "Financial Fraud"})
    priority: str = Field(default="High", json_schema_extra={"example": "High"})  # Critical, High, Medium, Low
    lead_investigator_id: Optional[int] = None


class CaseStatusUpdate(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "In Court"})  # Open, Under Investigation, In Court, Closed


class CaseResponse(BaseModel):
    id: int
    case_number: str
    title: str
    description: Optional[str]
    category: str
    status: str
    priority: str
    lead_investigator_id: int
    lead_investigator_name: Optional[str] = None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---- Evidence Schemas ----

class EvidenceResponse(BaseModel):
    id: int
    case_id: int
    title: str
    description: Optional[str]
    category: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    uploaded_by_id: int
    uploader_name: Optional[str] = None
    is_tampered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseDetailResponse(CaseResponse):
    evidence_documents: List[EvidenceResponse] = []


class EvidenceVerifyResponse(BaseModel):
    evidence_id: int
    title: str
    filename: str
    is_valid: bool
    expected_hash: str
    current_hash: Optional[str]
    status_badge: str  # "VERIFIED_GREEN" | "TAMPERED_RED"
    message: str
    verified_at: datetime
    verified_by: str


# ---- Audit Log Schemas ----

class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int]
    username: str
    user_role: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: str
    sha256_snapshot: Optional[str]
    ip_address: str

    model_config = {"from_attributes": True}
