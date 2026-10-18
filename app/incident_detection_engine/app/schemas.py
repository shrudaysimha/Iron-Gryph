"""
Pydantic schemas for request/response validation.

WHY SCHEMAS?
------------
FastAPI uses Pydantic models for two purposes:
  1. **Input validation** — automatically rejects malformed API requests with
     clear error messages (no manual if/else checking needed).
  2. **Response documentation** — the `/docs` Swagger page shows the exact
     shape of every response, making integration easy for the frontend and
     forecasting teams.

Each class below maps to one JSON structure the API accepts or returns.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════
#  INPUT SCHEMAS (what the API receives)
# ═══════════════════════════════════════════════════════════════════════

class IncidentCreate(BaseModel):
    """Schema for a single incident submitted via the API.

    Every field has validation rules so bad data is rejected immediately.
    """
    incident_id: str = Field(..., min_length=1, description="Unique identifier for the incident")
    incident_type: str = Field(..., min_length=1, description="Type: road_accident, storm_report, public_gathering, fire, etc.")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    timestamp: datetime = Field(..., description="When the incident occurred (ISO-8601)")
    severity: int = Field(..., ge=1, le=5, description="Severity scale: 1 (minor) to 5 (critical)")
    data_source: str = Field(..., min_length=1, description="Source label, e.g. 'SIMULATED_DATASET' or 'POLICE_FEED'")
    weather_condition: str = Field(
        default="none",
        description="Weather at incident location: none, heavy_rain, extreme_heat, storm, flood",
    )

    @field_validator("incident_type", "weather_condition", mode="before")
    @classmethod
    def normalise_to_lowercase(cls, v: str) -> str:
        return str(v).strip().lower()


class IncidentBatchRequest(BaseModel):
    """Wrapper for submitting multiple incidents at once."""
    incidents: list[IncidentCreate] = Field(..., min_length=1, description="List of incidents to analyse")


class WeatherReport(BaseModel):
    """Schema for a weather observation (from API or simulated data)."""
    location_name: str = Field(..., description="Name of the location")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    condition: str = Field(..., description="Weather condition: clear, heavy_rain, extreme_heat, storm, flood")
    temperature_celsius: Optional[float] = Field(None, description="Temperature in °C")
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = Field(None, ge=0)
    timestamp: datetime = Field(..., description="Observation time (ISO-8601)")
    data_source: str = Field(default="SIMULATED", description="Source: SIMULATED or API provider name")
    is_simulated: bool = Field(default=True)


class EventReport(BaseModel):
    """Schema for a public event or gathering."""
    event_id: str = Field(..., min_length=1)
    event_name: str = Field(..., min_length=1)
    event_type: str = Field(..., description="Type: concert, sports, protest, festival, etc.")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    start_time: datetime
    end_time: Optional[datetime] = None
    expected_attendance: Optional[int] = Field(None, ge=0)
    data_source: str = Field(default="SIMULATED")
    is_simulated: bool = Field(default=True)


# ═══════════════════════════════════════════════════════════════════════
#  OUTPUT SCHEMAS (what the API returns)
# ═══════════════════════════════════════════════════════════════════════

class HospitalInfo(BaseModel):
    latitude: float
    longitude: float
    name: str


class WeightsInfo(BaseModel):
    count: float
    severity: float
    proximity: float
    weather: float


class ConfigurationInfo(BaseModel):
    cluster_radius_km: float
    cluster_window_minutes: int
    nearby_radius_km: float
    moderate_risk_threshold: float
    high_risk_threshold: float
    weights: WeightsInfo


class RiskFactors(BaseModel):
    incident_count: int
    count_factor: float
    average_severity: float
    nearest_distance_km: float
    weather_signal_present: bool


class RiskAssessment(BaseModel):
    risk_score: float
    risk_category: str
    reasons: list[str]
    factors: RiskFactors


class ClusterInfo(BaseModel):
    cluster_id: str
    incident_ids: list[str]


class IncidentEnriched(BaseModel):
    """An incident record after enrichment (distance + cluster assignment)."""
    incident_id: str
    incident_type: str
    latitude: float
    longitude: float
    timestamp: str
    severity: int
    data_source: str
    weather_condition: str
    distance_km: float
    cluster_id: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Complete analysis result returned by the API."""
    engine: str = "member4-incident-detection-engine"
    is_simulated_demo: bool = True
    clinical_validation: str = "NOT_VALIDATED"
    hospital: HospitalInfo
    configuration: ConfigurationInfo
    incident_count_total: int
    incident_count_scored: int
    clusters: list[ClusterInfo]
    incidents: list[IncidentEnriched]
    risk: RiskAssessment
    alert: str


class HealthResponse(BaseModel):
    status: str = "healthy"
    engine: str = "member4-incident-detection-engine"
    version: str = "1.0.0"


class AlertResponse(BaseModel):
    """Simplified alert payload for the frontend dashboard."""
    alert_id: str
    timestamp: str
    risk_category: str
    risk_score: float
    alert_message: str
    incident_count: int
    nearest_incident_km: float
    weather_active: bool
    cluster_count: int
    hospital: HospitalInfo
