"""Ambulance API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ambulance import Ambulance
from app.schemas.ambulance import (
    AmbulanceCreate,
    AmbulanceUpdate,
    AmbulanceResponse,
    DispatchRequest,
    FleetStatus,
)

router = APIRouter()


@router.get("/", response_model=list[AmbulanceResponse])
def list_ambulances(
    hospital_id: int = Query(...),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """List ambulances for a hospital."""
    query = db.query(Ambulance).filter(Ambulance.hospital_id == hospital_id)
    if status:
        query = query.filter(Ambulance.status == status)
    return query.all()


@router.get("/fleet-status", response_model=FleetStatus)
def get_fleet_status(hospital_id: int = Query(...), db: Session = Depends(get_db)):
    """Get aggregated fleet status for a hospital."""
    ambulances = db.query(Ambulance).filter(Ambulance.hospital_id == hospital_id).all()

    status_counts = {}
    for amb in ambulances:
        status_counts[amb.status] = status_counts.get(amb.status, 0) + 1

    return FleetStatus(
        hospital_id=hospital_id,
        total_ambulances=len(ambulances),
        available=status_counts.get("available", 0),
        dispatched=status_counts.get("dispatched", 0),
        en_route=status_counts.get("en_route", 0),
        at_scene=status_counts.get("at_scene", 0),
        returning=status_counts.get("returning", 0),
        maintenance=status_counts.get("maintenance", 0),
    )


@router.post("/", response_model=AmbulanceResponse, status_code=201)
def create_ambulance(ambulance: AmbulanceCreate, db: Session = Depends(get_db)):
    """Register a new ambulance."""
    existing = db.query(Ambulance).filter(Ambulance.vehicle_number == ambulance.vehicle_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle number already exists")

    db_ambulance = Ambulance(**ambulance.model_dump())
    db.add(db_ambulance)
    db.commit()
    db.refresh(db_ambulance)
    return db_ambulance


@router.put("/{ambulance_id}/dispatch", response_model=AmbulanceResponse)
def dispatch_ambulance(
    ambulance_id: int,
    request: DispatchRequest,
    db: Session = Depends(get_db),
):
    """Dispatch an ambulance to a destination."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    if ambulance.status != "available":
        raise HTTPException(
            status_code=400,
            detail=f"Ambulance is currently '{ambulance.status}', cannot dispatch",
        )

    ambulance.status = "dispatched"
    ambulance.destination_lat = request.destination_lat
    ambulance.destination_lon = request.destination_lon
    ambulance.destination_address = request.destination_address
    ambulance.eta_minutes = request.eta_minutes
    ambulance.last_dispatched_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ambulance)
    return ambulance


@router.put("/{ambulance_id}/status", response_model=AmbulanceResponse)
def update_ambulance_status(
    ambulance_id: int,
    update: AmbulanceUpdate,
    db: Session = Depends(get_db),
):
    """Update ambulance status and location."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(ambulance, field, value)

    # Clear destination when returning to available
    if update.status == "available":
        ambulance.destination_lat = None
        ambulance.destination_lon = None
        ambulance.destination_address = None
        ambulance.eta_minutes = None

    db.commit()
    db.refresh(ambulance)
    return ambulance
