"""Patient and Admission API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hospital import Bed, Ward
from app.models.patient import Patient, Admission
from app.models.staff import Staff
from app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    AdmitPatientRequest,
    AdmissionResponse,
    AdmissionDetail,
    DischargeRequest,
)

router = APIRouter()


@router.post("/admit", response_model=AdmissionDetail, status_code=201)
def admit_patient(request: AdmitPatientRequest, db: Session = Depends(get_db)):
    """Create a patient and admit them to a hospital in one step."""
    # Create patient
    patient = Patient(
        name=request.name,
        age=request.age,
        gender=request.gender,
        blood_group=request.blood_group,
        phone=request.phone,
        emergency_contact=request.emergency_contact,
        condition=request.condition,
        triage_score=request.triage_score,
        arrival_mode=request.arrival_mode,
    )
    db.add(patient)
    db.flush()  # Get patient.id without committing

    # Auto-assign bed if not specified
    bed_id = request.bed_id
    if not bed_id:
        # Find an available bed matching the department
        ward_type_map = {
            "emergency": "emergency",
            "icu": "icu",
            "surgery": "surgical",
            "maternity": "maternity",
            "pediatric": "pediatric",
        }
        ward_type = ward_type_map.get(request.department, "general")

        available_bed = (
            db.query(Bed)
            .join(Ward)
            .filter(
                Ward.hospital_id == request.hospital_id,
                Ward.ward_type == ward_type,
                Bed.status == "available",
            )
            .first()
        )
        if not available_bed:
            # Fallback: try any available bed
            available_bed = (
                db.query(Bed)
                .join(Ward)
                .filter(
                    Ward.hospital_id == request.hospital_id,
                    Bed.status == "available",
                )
                .first()
            )

        if available_bed:
            bed_id = available_bed.id
            available_bed.status = "occupied"
            # Update ward available count
            ward = db.query(Ward).filter(Ward.id == available_bed.ward_id).first()
            if ward and ward.available_beds > 0:
                ward.available_beds -= 1

    # Create admission
    admission = Admission(
        patient_id=patient.id,
        hospital_id=request.hospital_id,
        bed_id=bed_id,
        department=request.department,
        diagnosis=request.diagnosis,
        severity=request.severity,
        attending_doctor_id=request.attending_doctor_id,
    )
    db.add(admission)

    # Update doctor patient count
    if request.attending_doctor_id:
        doctor = db.query(Staff).filter(Staff.id == request.attending_doctor_id).first()
        if doctor:
            doctor.current_patients += 1

    db.commit()
    db.refresh(admission)
    db.refresh(patient)

    return AdmissionDetail(
        **AdmissionResponse.model_validate(admission).model_dump(),
        patient=PatientResponse.model_validate(patient),
    )


@router.put("/{admission_id}/discharge", response_model=AdmissionResponse)
def discharge_patient(
    admission_id: int,
    request: DischargeRequest,
    db: Session = Depends(get_db),
):
    """Discharge a patient and free their bed."""
    admission = db.query(Admission).filter(Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=404, detail="Admission not found")

    if admission.status == "discharged":
        raise HTTPException(status_code=400, detail="Patient already discharged")

    now = datetime.now(timezone.utc)
    admission.status = "discharged"
    admission.discharged_at = now
    admission.notes = request.notes or admission.notes

    # Calculate length of stay
    if admission.admitted_at:
        delta = now - admission.admitted_at
        admission.length_of_stay_hours = round(delta.total_seconds() / 3600, 1)

    # Free the bed
    if admission.bed_id:
        bed = db.query(Bed).filter(Bed.id == admission.bed_id).first()
        if bed:
            bed.status = "available"
            ward = db.query(Ward).filter(Ward.id == bed.ward_id).first()
            if ward:
                ward.available_beds += 1

    # Update doctor patient count
    if admission.attending_doctor_id:
        doctor = db.query(Staff).filter(Staff.id == admission.attending_doctor_id).first()
        if doctor and doctor.current_patients > 0:
            doctor.current_patients -= 1

    db.commit()
    db.refresh(admission)
    return admission


@router.get("/current", response_model=list[AdmissionDetail])
def get_current_patients(
    hospital_id: int = Query(...),
    department: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
):
    """List all currently admitted patients at a hospital."""
    query = (
        db.query(Admission)
        .filter(
            Admission.hospital_id == hospital_id,
            Admission.status.in_(["admitted", "in_treatment", "observation"]),
        )
    )
    if department:
        query = query.filter(Admission.department == department)
    if severity:
        query = query.filter(Admission.severity == severity)

    admissions = query.order_by(Admission.admitted_at.desc()).all()

    results = []
    for adm in admissions:
        patient = db.query(Patient).filter(Patient.id == adm.patient_id).first()
        results.append(
            AdmissionDetail(
                **AdmissionResponse.model_validate(adm).model_dump(),
                patient=PatientResponse.model_validate(patient) if patient else None,
            )
        )
    return results


@router.get("/history", response_model=list[AdmissionResponse])
def get_admission_history(
    hospital_id: int = Query(...),
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get admission history for the last N days."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    admissions = (
        db.query(Admission)
        .filter(
            Admission.hospital_id == hospital_id,
            Admission.admitted_at >= cutoff,
        )
        .order_by(Admission.admitted_at.desc())
        .all()
    )
    return admissions
