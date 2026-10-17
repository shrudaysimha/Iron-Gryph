"""Pydantic schemas for Dashboard aggregation."""

from datetime import datetime
from pydantic import BaseModel

from app.schemas.hospital import HospitalCapacity
from app.schemas.staff import StaffAvailability
from app.schemas.ambulance import FleetStatus
from app.schemas.alert import AlertResponse


class DashboardOverview(BaseModel):
    """Top-level dashboard view combining all key metrics."""
    hospital_id: int
    hospital_name: str
    timestamp: datetime

    # Capacity
    capacity: HospitalCapacity

    # Staff
    staff: StaffAvailability

    # Ambulances
    fleet: FleetStatus

    # Active alerts
    active_alerts: list[AlertResponse] = []
    critical_alert_count: int = 0
    warning_alert_count: int = 0

    # Predictions (latest)
    surge_predicted: bool = False
    predicted_admissions_next_4h: int = 0
    predicted_admissions_next_12h: int = 0
    prediction_confidence: float = 0.0


class DashboardMetrics(BaseModel):
    """Time-series metrics for charts."""
    hospital_id: int
    period: str  # "24h", "7d", "30d"

    # Admissions over time
    admissions_timeline: list["TimePoint"] = []

    # Occupancy over time
    occupancy_timeline: list["TimePoint"] = []

    # Average wait times
    avg_triage_to_bed_minutes: float = 0.0
    avg_length_of_stay_hours: float = 0.0

    # Department load
    department_load: list["DepartmentLoad"] = []


class TimePoint(BaseModel):
    timestamp: datetime
    value: float


class DepartmentLoad(BaseModel):
    department: str
    current_patients: int
    capacity: int
    utilization: float
