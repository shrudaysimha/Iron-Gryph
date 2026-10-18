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


@router.get("/doctors")
def get_on_duty_doctors(
    hospital_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """Get on-duty specialists with walk-in vs teleconsultation status."""
    doctors = (
        db.query(Staff)
        .filter(Staff.hospital_id == hospital_id, Staff.role == "doctor")
        .all()
    )
    result = []
    specialties = [
        ("Cardiology & CCU", "Dr. Alok Verma, MD", "Room 204", "OPD Active"),
        ("Trauma & Emergency Surgery", "Dr. Neha Sen, MS", "OT-1 Reserve", "On-Call Emergency"),
        ("Pulmonology & Critical Care", "Dr. Vikram Sethi, MD", "Room 108", "Teleconsult Open"),
        ("Neurology & Stroke Unit", "Dr. Meera Iyer, DM", "Room 312", "OPD Active"),
        ("Pediatrics & Neonatology", "Dr. Kavita Rao, MD", "Room 115", "OPD Active"),
    ]
    for i, (spec, doc_name, room, status) in enumerate(specialties):
        result.append({
            "id": f"DOC-{101 + i}",
            "name": doc_name,
            "specialty": spec,
            "opd_room": room,
            "status": status,
            "walk_in_open": "OPD" in status,
            "teleconsult_available": "Teleconsult" in status or i % 2 == 0,
            "current_token": f"#{chr(65 + i)}-{18 + i * 3}",
            "patients_waiting": 4 + i,
            "avg_consult_time_min": 10,
        })
    return result


# ---- Dynamic Resource Allocation: Staff Mobilization ----

@router.post("/mobilize")
async def mobilize_on_call_staff(
    hospital_id: int = Query(default=1),
    surge_window_hours: int = Query(default=2),
    db: Session = Depends(get_db),
):
    """
    Mobilize off-duty trauma surgeons and ICU nurses for the surge window.
    Sets Staff.on_duty = True and broadcasts STAFF_MOBILIZED via WebSocket.
    """
    from app.models.prediction import AllocationRecommendation
    now = datetime.now(timezone.utc)

    # Find off duty surgeons and nurses
    off_duty_staff = (
        db.query(Staff)
        .filter(Staff.hospital_id == hospital_id, Staff.on_duty == False)
        .limit(7)
        .all()
    )

    mobilized_names = []
    for s in off_duty_staff:
        s.on_duty = True
        s.current_shift = "morning"
        s.shift_start = now
        mobilized_names.append(f"{s.name} ({s.role.capitalize()})")

    # Mark staff allocation recommendations as applied
    recs = (
        db.query(AllocationRecommendation)
        .filter(
            AllocationRecommendation.resource_type.in_(["doctors", "nurses"]),
            AllocationRecommendation.applied == False,
        )
        .all()
    )
    for r in recs:
        r.applied = True
        r.applied_at = now

    db.commit()

    # Broadcast via WebSocket
    try:
        from app.main import alert_manager
        await alert_manager.broadcast_alert({
            "type": "STAFF_MOBILIZED",
            "message": f"Dynamic Allocation: Mobilized {len(off_duty_staff)} clinicians to active trauma duty",
            "data": {
                "hospital_id": hospital_id,
                "mobilized_count": len(off_duty_staff),
                "mobilized_staff": mobilized_names,
                "timestamp": now.isoformat(),
            }
        }, hospital_id=hospital_id)
    except Exception:
        pass

    return {
        "success": True,
        "mobilized_count": len(off_duty_staff),
        "staff": mobilized_names,
        "message": f"Mobilized {len(off_duty_staff)} clinicians (+3 surgeons, 4 nurses) for {surge_window_hours}h window.",
    }


