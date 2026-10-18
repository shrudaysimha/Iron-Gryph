"""Incident Detection API endpoints.

Exposes the Incident Detection Engine (Member 4) through the main backend API.

ENDPOINT MAP
────────────
  POST /api/v1/incidents/analyze          → Analyse a batch of incidents
  GET  /api/v1/incidents/                 → Load & return incidents from sample file
  GET  /api/v1/incidents/alerts/latest    → Get latest alert from file data
  GET  /api/v1/incidents/weather          → Weather observations & risk
  GET  /api/v1/incidents/events           → Public events & risk
  GET  /api/v1/incidents/dashboard        → Unified dashboard summary
  POST /api/v1/incidents/forecast-feed    → Combined payload for forecasting module
  GET  /api/v1/incidents/config           → Engine configuration
  GET  /api/v1/incidents/health           → Engine health check
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.incident_service import IncidentDetectionService

router = APIRouter()

# Singleton service instance
_service = IncidentDetectionService()


# ── Request Schemas ──────────────────────────────────────────────────


class IncidentPayload(BaseModel):
    """Schema for a single incident submitted via the API."""
    incident_id: str = Field(..., min_length=1, description="Unique identifier")
    incident_type: str = Field(..., min_length=1, description="Type: road_accident, storm_report, etc.")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime = Field(..., description="ISO-8601 timestamp")
    severity: int = Field(..., ge=1, le=5)
    data_source: str = Field(..., min_length=1)
    weather_condition: str = Field(default="none")

    @field_validator("incident_type", "weather_condition", mode="before")
    @classmethod
    def normalise(cls, v: str) -> str:
        return str(v).strip().lower()


class IncidentBatchRequest(BaseModel):
    """Batch request for incident analysis."""
    incidents: list[IncidentPayload] = Field(..., min_length=1)


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/analyze")
async def analyze_incidents(request: IncidentBatchRequest):
    """Analyse a batch of incidents and return risk assessment.

    This is the primary endpoint. Submit incident data and receive
    a complete analysis with risk scores, clusters, and alerts.
    """
    try:
        incidents = [inc.model_dump() for inc in request.incidents]
        return _service.analyze_incidents(incidents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/")
async def get_incidents(
    source: str = Query(
        default="json",
        description="Data source: 'json' or 'csv'",
        pattern="^(json|csv)$",
    ),
):
    """Load incidents from sample data file and return enriched records."""
    try:
        return _service.analyze_from_file(source)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/alerts/latest")
async def get_latest_alert(
    source: str = Query(default="json", pattern="^(json|csv)$"),
):
    """Generate an alert based on the latest incident data."""
    try:
        result = _service.analyze_from_file(source)
        return result["alert"]
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/weather")
async def get_incident_weather():
    """Get current weather observations and risk assessment."""
    return await _service.get_weather()


@router.get("/events")
async def get_incident_events():
    """Get current public events and surge-risk assessment."""
    return await _service.get_events()


@router.get("/dashboard")
async def get_incident_dashboard(
    source: str = Query(
        default="json",
        description="Data source: 'json' or 'csv'",
        pattern="^(json|csv)$",
    ),
):
    """Unified dashboard: incidents + weather + events in one payload."""
    try:
        return await _service.get_dashboard_summary(source)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/forecast-feed")
async def forecast_feed(request: IncidentBatchRequest):
    """Combined payload for the forecasting module integration.

    Provides incident analysis + weather + events data for
    Members 2/3 to factor into their surge predictions.
    """
    try:
        incidents = [inc.model_dump() for inc in request.incidents]
        return await _service.get_forecast_feed(incidents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/config")
async def get_engine_config():
    """Return the current incident detection engine configuration."""
    return _service.get_engine_config()


@router.get("/health")
async def engine_health():
    """Health check for the incident detection engine."""
    return {
        "status": "healthy",
        "engine": "member4-incident-detection-engine",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
