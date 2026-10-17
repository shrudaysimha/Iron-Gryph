"""Staff management API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.staff import Staff
from app.models.patient import Admission
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffAvailability,
)

router = APIRouter()


@router.get("/on-duty", response_model=list[StaffResponse])
def get_on_duty_staff(
    hospital_id: int = Query(...),
    role: str | None = None,
    db: Session = Depends(get_db),
):
    """Get all currently on-duty staff at a hospital."""
    query = db.query(Staff).filter(
        Staff.hospital_id == hospital_id,
        Staff.on_duty == True,  # noqa: E712
        Staff.is_active == True,  # noqa: E712
    )
    if role:
        query = query.filter(Staff.role == role)
    return query.all()


@router.get("/availability", response_model=StaffAvailability)
def get_staff_availability(
    hospital_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get staff availability summary for a hospital."""
    all_staff = db.query(Staff).filter(
        Staff.hospital_id == hospital_id,
        Staff.is_active == True,  # noqa: E712
    ).all()

    on_duty_staff = [s for s in all_staff if s.on_duty]
    current_patients = (
        db.query(Admission)
        .filter(
            Admission.hospital_id == hospital_id,
            Admission.status.in_(["admitted", "in_treatment", "observation"]),
        )
        .count()
    )

    doctors_on_duty = len([s for s in on_duty_staff if s.role == "doctor"])
    nurses_on_duty = len([s for s in on_duty_staff if s.role == "nurse"])
    paramedics_on_duty = len([s for s in on_duty_staff if s.role == "paramedic"])

    staff_count = len(on_duty_staff)
    ratio = staff_count / current_patients if current_patients > 0 else float("inf")

    return StaffAvailability(
        hospital_id=hospital_id,
        total_staff=len(all_staff),
        on_duty=staff_count,
        off_duty=len(all_staff) - staff_count,
        doctors_on_duty=doctors_on_duty,
        nurses_on_duty=nurses_on_duty,
        paramedics_on_duty=paramedics_on_duty,
        staff_to_patient_ratio=round(ratio, 3),
    )


@router.post("/", response_model=StaffResponse, status_code=201)
def create_staff(staff: StaffCreate, db: Session = Depends(get_db)):
    """Add a new staff member."""
    existing = db.query(Staff).filter(Staff.employee_id == staff.employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    db_staff = Staff(**staff.model_dump())
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)
    return db_staff


@router.put("/{staff_id}/status", response_model=StaffResponse)
def update_staff_status(staff_id: int, update: StaffUpdate, db: Session = Depends(get_db)):
    """Update a staff member's duty status or shift."""
    staff_member = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(staff_member, field, value)

    # Auto-set shift times
    if update.on_duty is True and not staff_member.shift_start:
        staff_member.shift_start = datetime.now(timezone.utc)
    elif update.on_duty is False:
        staff_member.shift_end = datetime.now(timezone.utc)

    db.commit()
    db.refresh(staff_member)
    return staff_member
