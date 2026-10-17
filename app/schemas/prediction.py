"""Pydantic schemas for Predictions."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PredictionRequest(BaseModel):
    hospital_id: int
    horizon_hours: int = 4


class PredictionResponse(BaseModel):
    id: int
    hospital_id: int
    predicted_for: datetime
    horizon_hours: int
    predicted_total_admissions: int
    predicted_emergency_admissions: int
    predicted_icu_demand: int
    predicted_surgical_demand: int
    confidence_score: float
    model_version: str | None
    is_surge_predicted: bool
    features_used: dict | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PredictionHistory(BaseModel):
    id: int
    hospital_id: int
    predicted_for: datetime
    predicted_total_admissions: int
    actual_total_admissions: int | None
    confidence_score: float
    accuracy: float | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DemandForecast(BaseModel):
    """Structured demand forecast for multiple time horizons."""
    hospital_id: int
    hospital_name: str
    generated_at: datetime
    forecasts: list["HorizonForecast"]


class HorizonForecast(BaseModel):
    horizon_hours: int
    predicted_for: datetime
    total_admissions: int
    emergency_admissions: int
    icu_demand: int
    surgical_demand: int
    confidence: float
    is_surge: bool
    surge_probability: float = 0.0
