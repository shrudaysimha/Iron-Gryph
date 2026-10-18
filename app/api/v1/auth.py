"""Authentication and User Session API endpoints for MediBook."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.staff import Staff

router = APIRouter()


class LoginRequest(BaseModel):
    identifier: str
    password: str = "medibook2026"
    role: str | None = None


# Curated high-impact clinical profiles
DEFAULT_PROFILES = [
    {
        "employee_id": "EMP-1005",
        "name": "Dr. Rajiv Mehta",
        "role": "doctor",
        "title": "Chief Trauma Surgeon & Medical Director",
        "department": "Emergency Trauma & Surgical ICU",
        "specialization": "Trauma & Critical Care (DM, MD)",
        "shift": "morning",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=150&auto=format&fit=crop&q=80",
    },
    {
        "employee_id": "EMP-1000",
        "name": "Dr. Ananya Sen",
        "role": "doctor",
        "title": "Consultant Surgeon & OPD Bay 3 Lead",
        "department": "Gastrointestinal Surgery & General OPD",
        "specialization": "MS, MCh Gastrointestinal Surgery",
        "shift": "morning",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1594824813627-84d436893699?w=150&auto=format&fit=crop&q=80",
    },
    {
        "employee_id": "EMP-1001",
        "name": "Priya Patel, RN",
        "role": "nurse",
        "title": "Head Triage Officer & Resus Bay Lead",
        "department": "Emergency Rapid Intake (ESI 1-5)",
        "specialization": "Acute Trauma Triage & Resuscitation",
        "shift": "morning",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=150&auto=format&fit=crop&q=80",
    },
    {
        "employee_id": "EMP-1006",
        "name": "Arun Varma",
        "role": "admin",
        "title": "Central Bed Allocation & Capacity Coordinator",
        "department": "Admissions & Bed Management Unit",
        "specialization": "Pessimistic Locking & LP Surge Optimization",
        "shift": "morning",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
    },
    {
        "employee_id": "EMP-1003",
        "name": "CAD Dispatcher #402",
        "role": "paramedic",
        "title": "Surat Regional EMS Telemetry Controller",
        "department": "Central CAD Command & Fleet Logistics",
        "specialization": "ALS/BLS Inbound Routing & Divert Controller",
        "shift": "morning",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
    },
    {
        "employee_id": "PAT-88219",
        "name": "Arjun Sharma (Patient)",
        "role": "patient",
        "title": "Admitted Patient / Family Portal",
        "department": "Cardiology Observation (OPD Token #B-24)",
        "specialization": "Patient Pass & Cryptographic E-Prescription",
        "shift": "active",
        "hospital": "SIDS Hospital Surat",
        "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
    },
]


@router.get("/quick-profiles")
def get_quick_profiles():
    """Returns preset clinical profiles for one-click login."""
    return DEFAULT_PROFILES


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with Employee ID, email, or preset clinical role."""
    ident = request.identifier.strip()
    
    # Check default presets first
    matched = None
    for prof in DEFAULT_PROFILES:
        if (
            ident.lower() in prof["employee_id"].lower()
            or ident.lower() in prof["name"].lower()
            or ident.lower() in prof["role"].lower()
            or ident.lower() in prof.get("title", "").lower()
        ):
            matched = prof
            break
            
    # Check database staff
    if not matched:
        staff_member = (
            db.query(Staff)
            .filter(
                (Staff.employee_id.ilike(f"%{ident}%"))
                | (Staff.name.ilike(f"%{ident}%"))
            )
            .first()
        )
        if staff_member:
            matched = {
                "employee_id": staff_member.employee_id,
                "name": staff_member.name,
                "role": staff_member.role,
                "title": f"{staff_member.role.capitalize()} • {staff_member.specialization or 'Clinical Staff'}",
                "department": "Hospital Clinical Unit",
                "specialization": staff_member.specialization or "Emergency & Critical Care",
                "shift": staff_member.current_shift,
                "hospital": "SIDS Hospital Surat",
                "avatar_url": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=150&auto=format&fit=crop&q=80",
            }

    # Fallback default if custom name entered
    if not matched:
        matched = {
            "employee_id": f"EMP-{uuid.uuid4().hex[:4].upper()}",
            "name": ident.title(),
            "role": request.role or "doctor",
            "title": "Hospital Medical Officer",
            "department": "Emergency Operations",
            "specialization": "Emergency Medicine",
            "shift": "morning",
            "hospital": "SIDS Hospital Surat",
            "avatar_url": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=150&auto=format&fit=crop&q=80",
        }

    session_token = f"MEDISESSION-{uuid.uuid4().hex.upper()}"
    return {
        "status": "success",
        "message": f"Welcome back, {matched['name']}",
        "token": session_token,
        "user": matched,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/me")
def get_current_user():
    """Get active session details or return default lead surgeon."""
    return {
        "authenticated": True,
        "user": DEFAULT_PROFILES[0],
    }
