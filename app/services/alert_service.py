"""
Alert Service — Automated detection, rule evaluation, and real-time dispatch of hospital alerts.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.hospital import Hospital, Ward, Bed
from app.models.staff import Staff
from app.models.ambulance import Ambulance
from app.models.prediction import Prediction
from app.models.patient import Admission

logger = logging.getLogger(__name__)


class AlertService:
    """Service to evaluate clinical safety thresholds and broadcast alerts."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_and_generate_alerts(self, hospital_id: int) -> List[Alert]:
        """
        Evaluate real-time metrics against hospital safety thresholds.
        Creates DB alerts and returns newly generated alerts.
        """
        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            return []

        generated_alerts: List[Alert] = []

        # 1. Check Bed Occupancy
        wards = self.db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.is_active == True).all()  # noqa: E712
        total_beds = sum(w.total_beds for w in wards)
        available_beds = sum(w.available_beds for w in wards)
        occupancy = (total_beds - available_beds) / total_beds if total_beds > 0 else 0

        if occupancy >= 0.90:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="bed_critical",
                severity="critical",
                title="Critical Bed Shortage",
                message=f"Total bed occupancy is at {occupancy:.1%}. Only {available_beds} beds remaining across all wards.",
            )
            if alert:
                generated_alerts.append(alert)
        elif occupancy >= 0.80:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="bed_warning",
                severity="warning",
                title="High Bed Occupancy",
                message=f"Total bed occupancy has reached {occupancy:.1%}. Prepare surge beds or prioritize discharges.",
            )
            if alert:
                generated_alerts.append(alert)

        # 2. Check ICU Capacity
        icu_wards = [w for w in wards if w.ward_type == "icu"]
        icu_available = sum(w.available_beds for w in icu_wards)
        icu_total = sum(w.total_beds for w in icu_wards)

        if icu_total > 0 and icu_available <= 1:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="icu_capacity",
                severity="critical",
                title="ICU Capacity Exhaustion Imminent",
                message=f"Only {icu_available} ICU bed available out of {icu_total}. Divert critical intake or prep ventilator surge.",
            )
            if alert:
                generated_alerts.append(alert)

        # 3. Check Ambulance Fleet
        ambulances = self.db.query(Ambulance).filter(Ambulance.hospital_id == hospital_id).all()
        avail_amb = sum(1 for a in ambulances if a.status == "available")
        total_amb = len(ambulances)

        if total_amb > 0 and avail_amb < 2:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="ambulance_shortage",
                severity="warning" if avail_amb == 1 else "critical",
                title="Low Ambulance Fleet Availability",
                message=f"Only {avail_amb}/{total_amb} ambulances currently available for emergency dispatch.",
            )
            if alert:
                generated_alerts.append(alert)

        # 4. Check Staffing Ratios
        current_patients = self.db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            Admission.status.in_(["admitted", "in_treatment", "observation"]),
        ).count()

        doctors_on_duty = self.db.query(Staff).filter(
            Staff.hospital_id == hospital_id,
            Staff.role == "doctor",
            Staff.on_duty == True,  # noqa: E712
        ).count()

        if doctors_on_duty > 0 and (current_patients / doctors_on_duty) > 8:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="staff_shortage",
                severity="warning",
                title="Doctor-to-Patient Ratio Strain",
                message=f"High patient load: {current_patients} patients assigned to {doctors_on_duty} on-duty doctors (>8:1 ratio).",
            )
            if alert:
                generated_alerts.append(alert)

        # 5. Check Predicted Surge
        latest_pred = self.db.query(Prediction).filter(
            Prediction.hospital_id == hospital_id
        ).order_by(Prediction.created_at.desc()).first()

        if latest_pred and latest_pred.is_surge_predicted:
            alert = self._create_alert_if_not_duplicate(
                hospital_id=hospital_id,
                alert_type="surge_predicted",
                severity="warning",
                title=f"Predicted Patient Surge (+{latest_pred.predicted_total_admissions} in {latest_pred.horizon_hours}h)",
                message=(
                    f"AI forecast indicates {latest_pred.predicted_total_admissions} upcoming arrivals "
                    f"({latest_pred.predicted_emergency_admissions} emergency, {latest_pred.predicted_icu_demand} ICU). "
                    f"Confidence: {latest_pred.confidence_score:.0%}."
                ),
            )
            if alert:
                generated_alerts.append(alert)

        if generated_alerts:
            self.db.commit()
            for a in generated_alerts:
                self.db.refresh(a)

        return generated_alerts

    def _create_alert_if_not_duplicate(
        self,
        hospital_id: int,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
    ) -> Alert | None:
        """Avoid duplicate alerts if identical unresolved alert was created within 2 hours."""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        existing = self.db.query(Alert).filter(
            Alert.hospital_id == hospital_id,
            Alert.alert_type == alert_type,
            Alert.resolved == False,  # noqa: E712
            Alert.created_at >= recent_cutoff,
        ).first()

        if existing:
            return None

        alert = Alert(
            hospital_id=hospital_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            acknowledged=False,
            resolved=False,
        )
        self.db.add(alert)
        return alert
