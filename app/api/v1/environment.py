"""
Environment API — Weather, external events, and mass incident telemetry.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.services.weather_service import WeatherService
from app.services.event_service import EventService

router = APIRouter()
weather_service = WeatherService()
event_service = EventService()


class EventCreateRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "City Marathon 2026"})
    type: str = Field(..., json_schema_extra={"example": "sports"})
    expected_attendance: int = Field(..., ge=100, json_schema_extra={"example": 25000})
    radius_km: float = Field(default=5.0, ge=0.5, json_schema_extra={"example": 5.0})
    risk_level: str = Field(default="medium", json_schema_extra={"example": "medium"})
    impact_multiplier: float = Field(default=1.2, ge=1.0, le=2.5, json_schema_extra={"example": 1.25})


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Expressway Bus Collision"})
    severity: str = Field(default="critical", json_schema_extra={"example": "critical"})
    estimated_casualties: int = Field(..., ge=1, json_schema_extra={"example": 12})


@router.get("/weather")
async def get_weather(city: str | None = Query(None)):
    """Get current weather conditions and patient surge risk multiplier."""
    return await weather_service.get_current_weather(city)


@router.get("/events")
def get_events(hospital_id: int = Query(default=1)):
    """Get active local events and emergency incidents affecting coverage area."""
    return event_service.get_events_for_hospital(hospital_id)


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(event: EventCreateRequest):
    """Register a new mass gathering event."""
    return event_service.register_event(event.model_dump())


@router.post("/incident", status_code=status.HTTP_201_CREATED)
def report_incident(incident: IncidentCreateRequest):
    """Report an emergency mass casualty or traffic incident."""
    return event_service.report_emergency_incident(incident.model_dump())
