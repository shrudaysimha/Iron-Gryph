"""Hospital API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hospital import Hospital, Ward, Bed
from app.schemas.hospital import (
    HospitalCreate,
    HospitalUpdate,
    HospitalResponse,
    HospitalDetail,
    HospitalCapacity,
    WardCreate,
    WardSummary,
)

router = APIRouter()


@router.get("/", response_model=list[HospitalResponse])
def list_hospitals(
    skip: int = 0,
    limit: int = 50,
    city: str | None = None,
    tier: str | None = None,
    db: Session = Depends(get_db),
):
    """List all hospitals with optional filtering."""
    query = db.query(Hospital).filter(Hospital.is_active == True)  # noqa: E712
    if city:
        query = query.filter(Hospital.city == city)
    if tier:
        query = query.filter(Hospital.tier == tier)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=HospitalResponse, status_code=201)
def create_hospital(hospital: HospitalCreate, db: Session = Depends(get_db)):
    """Create a new hospital."""
    db_hospital = Hospital(**hospital.model_dump())
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)
    return db_hospital


@router.get("/{hospital_id}", response_model=HospitalDetail)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    """Get hospital details including ward summary."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.is_active == True).all()  # noqa: E712
    ward_summaries = []
    for ward in wards:
        occupancy = (
            (ward.total_beds - ward.available_beds) / ward.total_beds * 100
            if ward.total_beds > 0
            else 0
        )
        ward_summaries.append(
            WardSummary(
                id=ward.id,
                name=ward.name,
                ward_type=ward.ward_type,
                total_beds=ward.total_beds,
                available_beds=ward.available_beds,
                occupancy_rate=round(occupancy, 1),
            )
        )

    result = HospitalDetail.model_validate(hospital)
    result.wards = ward_summaries
    return result


@router.put("/{hospital_id}", response_model=HospitalResponse)
def update_hospital(hospital_id: int, update: HospitalUpdate, db: Session = Depends(get_db)):
    """Update hospital information."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)

    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/{hospital_id}/capacity", response_model=HospitalCapacity)
def get_hospital_capacity(hospital_id: int, db: Session = Depends(get_db)):
    """Get current capacity status for a hospital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.is_active == True).all()  # noqa: E712

    total_beds = sum(w.total_beds for w in wards)
    available_beds = sum(w.available_beds for w in wards)
    occupied_beds = total_beds - available_beds

    # Count by type
    icu_wards = [w for w in wards if w.ward_type == "icu"]
    emergency_wards = [w for w in wards if w.ward_type == "emergency"]

    icu_total = sum(w.total_beds for w in icu_wards)
    icu_available = sum(w.available_beds for w in icu_wards)
    emergency_total = sum(w.total_beds for w in emergency_wards)
    emergency_available = sum(w.available_beds for w in emergency_wards)

    # Count ventilator beds
    ventilator_beds = (
        db.query(Bed)
        .join(Ward)
        .filter(Ward.hospital_id == hospital_id, Bed.bed_type == "ventilator")
        .all()
    )
    ventilator_total = len(ventilator_beds)
    ventilator_available = len([b for b in ventilator_beds if b.status == "available"])

    occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0

    return HospitalCapacity(
        hospital_id=hospital_id,
        hospital_name=hospital.name,
        total_beds=total_beds,
        occupied_beds=occupied_beds,
        available_beds=available_beds,
        occupancy_rate=round(occupancy_rate, 1),
        icu_total=icu_total,
        icu_available=icu_available,
        emergency_total=emergency_total,
        emergency_available=emergency_available,
        ventilator_total=ventilator_total,
        ventilator_available=ventilator_available,
    )


@router.post("/{hospital_id}/wards", response_model=WardSummary, status_code=201)
def create_ward(hospital_id: int, ward: WardCreate, db: Session = Depends(get_db)):
    """Create a new ward in a hospital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    db_ward = Ward(hospital_id=hospital_id, **ward.model_dump(exclude={"hospital_id"}))
    db.add(db_ward)
    db.commit()
    db.refresh(db_ward)

    return WardSummary(
        id=db_ward.id,
        name=db_ward.name,
        ward_type=db_ward.ward_type,
        total_beds=db_ward.total_beds,
        available_beds=db_ward.available_beds,
        occupancy_rate=0.0,
    )
