"""Pydantic schemas for Ambulance."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AmbulanceBase(BaseModel):
    vehicle_number: str
    vehicle_type: str = "basic"
    driver_name: str | None = None
    paramedic_name: str | None = None


class AmbulanceCreate(AmbulanceBase):
    hospital_id: int


class AmbulanceUpdate(BaseModel):
    status: str | None = None
    current_lat: float | None = None
    current_lon: float | None = None
    destination_lat: float | None = None
    destination_lon: float | None = None
    destination_address: str | None = None
    eta_minutes: int | None = None
    driver_name: str | None = None
    paramedic_name: str | None = None


class DispatchRequest(BaseModel):
    destination_lat: float
    destination_lon: float
    destination_address: str | None = None
    eta_minutes: int | None = None


class AmbulanceResponse(AmbulanceBase):
    id: int
    hospital_id: int
    status: str
    current_lat: float | None
    current_lon: float | None
    destination_lat: float | None
    destination_lon: float | None
    destination_address: str | None
    eta_minutes: int | None
    last_dispatched_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FleetStatus(BaseModel):
    hospital_id: int
    total_ambulances: int
    available: int
    dispatched: int
    en_route: int
    at_scene: int
    returning: int
    maintenance: int
