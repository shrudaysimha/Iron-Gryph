"""Dashboard API — aggregated views for the frontend."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.database import get_db
from app.models.hospital import Hospital, Ward, Bed
from app.models.patient import Admission
from app.models.staff import Staff
from app.models.ambulance import Ambulance
from app.models.alert import Alert
from app.models.prediction import Prediction
from app.schemas.dashboard import (
    DashboardOverview,
    DashboardMetrics,
    TimePoint,
    DepartmentLoad,
)
from app.schemas.hospital import HospitalCapacity
from app.schemas.staff import StaffAvailability
from app.schemas.ambulance import FleetStatus

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
def get_dashboard_overview(
    hospital_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get complete dashboard overview for a hospital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Hospital not found")

    now = datetime.now(timezone.utc)

    # ---- Capacity ----
    wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.is_active == True).all()  # noqa: E712
    total_beds = sum(w.total_beds for w in wards)
    available_beds = sum(w.available_beds for w in wards)
    occupied_beds = total_beds - available_beds

    icu_wards = [w for w in wards if w.ward_type == "icu"]
    emergency_wards = [w for w in wards if w.ward_type == "emergency"]

    ventilator_beds = (
        db.query(Bed).join(Ward)
        .filter(Ward.hospital_id == hospital_id, Bed.bed_type == "ventilator")
        .all()
    )

    capacity = HospitalCapacity(
        hospital_id=hospital_id,
        hospital_name=hospital.name,
        total_beds=total_beds,
        occupied_beds=occupied_beds,
        available_beds=available_beds,
        occupancy_rate=round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 1),
        icu_total=sum(w.total_beds for w in icu_wards),
        icu_available=sum(w.available_beds for w in icu_wards),
        emergency_total=sum(w.total_beds for w in emergency_wards),
        emergency_available=sum(w.available_beds for w in emergency_wards),
        ventilator_total=len(ventilator_beds),
        ventilator_available=len([b for b in ventilator_beds if b.status == "available"]),
    )

    # ---- Staff ----
    all_staff = db.query(Staff).filter(Staff.hospital_id == hospital_id, Staff.is_active == True).all()  # noqa: E712
    on_duty = [s for s in all_staff if s.on_duty]
    current_patients = (
        db.query(Admission)
        .filter(
            Admission.hospital_id == hospital_id,
            Admission.status.in_(["admitted", "in_treatment", "observation"]),
        )
        .count()
    )
    on_duty_count = len(on_duty)
    ratio = on_duty_count / current_patients if current_patients > 0 else 0

    staff_avail = StaffAvailability(
        hospital_id=hospital_id,
        total_staff=len(all_staff),
        on_duty=on_duty_count,
        off_duty=len(all_staff) - on_duty_count,
        doctors_on_duty=len([s for s in on_duty if s.role == "doctor"]),
        nurses_on_duty=len([s for s in on_duty if s.role == "nurse"]),
        paramedics_on_duty=len([s for s in on_duty if s.role == "paramedic"]),
        staff_to_patient_ratio=round(ratio, 3),
    )

    # ---- Fleet ----
    ambulances = db.query(Ambulance).filter(Ambulance.hospital_id == hospital_id).all()
    status_counts = {}
    for amb in ambulances:
        status_counts[amb.status] = status_counts.get(amb.status, 0) + 1

    fleet = FleetStatus(
        hospital_id=hospital_id,
        total_ambulances=len(ambulances),
        available=status_counts.get("available", 0),
        dispatched=status_counts.get("dispatched", 0),
        en_route=status_counts.get("en_route", 0),
        at_scene=status_counts.get("at_scene", 0),
        returning=status_counts.get("returning", 0),
        maintenance=status_counts.get("maintenance", 0),
    )

    # ---- Alerts ----
    active_alerts = (
        db.query(Alert)
        .filter(Alert.hospital_id == hospital_id, Alert.resolved == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )
    from app.schemas.alert import AlertResponse as AlertResp
    alert_responses = [AlertResp.model_validate(a) for a in active_alerts]

    critical_count = len([a for a in active_alerts if a.severity == "critical"])
    warning_count = len([a for a in active_alerts if a.severity == "warning"])

    # ---- Latest Prediction ----
    latest_pred = (
        db.query(Prediction)
        .filter(Prediction.hospital_id == hospital_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    return DashboardOverview(
        hospital_id=hospital_id,
        hospital_name=hospital.name,
        timestamp=now,
        capacity=capacity,
        staff=staff_avail,
        fleet=fleet,
        active_alerts=alert_responses,
        critical_alert_count=critical_count,
        warning_alert_count=warning_count,
        surge_predicted=latest_pred.is_surge_predicted if latest_pred else False,
        predicted_admissions_next_4h=latest_pred.predicted_total_admissions if latest_pred and latest_pred.horizon_hours == 4 else 0,
        predicted_admissions_next_12h=latest_pred.predicted_total_admissions if latest_pred and latest_pred.horizon_hours == 12 else 0,
        prediction_confidence=latest_pred.confidence_score if latest_pred else 0.0,
    )


@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    hospital_id: int = Query(...),
    period: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
    db: Session = Depends(get_db),
):
    """Get time-series metrics for dashboard charts."""
    now = datetime.now(timezone.utc)

    period_map = {"24h": 1, "7d": 7, "30d": 30}
    days = period_map.get(period, 1)
    cutoff = now - timedelta(days=days)

    # Admissions timeline — group by hour for 24h, by day for longer periods
    admissions = (
        db.query(Admission)
        .filter(
            Admission.hospital_id == hospital_id,
            Admission.admitted_at >= cutoff,
        )
        .all()
    )

    # Build timeline
    admissions_timeline = []
    if period == "24h":
        for hour_offset in range(24):
            t = now - timedelta(hours=23 - hour_offset)
            count = len([
                a for a in admissions
                if a.admitted_at and abs((a.admitted_at - t).total_seconds()) < 3600
            ])
            admissions_timeline.append(TimePoint(timestamp=t, value=count))
    else:
        for day_offset in range(days):
            t = now - timedelta(days=days - 1 - day_offset)
            count = len([
                a for a in admissions
                if a.admitted_at and a.admitted_at.date() == t.date()
            ])
            admissions_timeline.append(TimePoint(timestamp=t, value=count))

    # Department load
    departments = ["emergency", "general", "icu", "surgery", "maternity", "pediatric"]
    dept_loads = []
    for dept in departments:
        current = len([
            a for a in admissions
            if a.department == dept and a.status in ("admitted", "in_treatment", "observation")
        ])
        # Rough capacity estimation per department
        capacity_estimate = max(current + 5, 20)
        dept_loads.append(DepartmentLoad(
            department=dept,
            current_patients=current,
            capacity=capacity_estimate,
            utilization=round(current / capacity_estimate * 100, 1) if capacity_estimate > 0 else 0,
        ))

    # Average stats
    discharged = [a for a in admissions if a.length_of_stay_hours is not None]
    avg_los = sum(a.length_of_stay_hours for a in discharged) / len(discharged) if discharged else 0

    return DashboardMetrics(
        hospital_id=hospital_id,
        period=period,
        admissions_timeline=admissions_timeline,
        occupancy_timeline=[],  # Populated when we add periodic snapshots
        avg_triage_to_bed_minutes=0,  # Requires triage timestamp tracking
        avg_length_of_stay_hours=round(avg_los, 1),
        department_load=dept_loads,
    )
