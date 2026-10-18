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


# ---- Member 3 Weather-Aware Surge Predictor Schemas ----

from pydantic import Field
from typing import Any, Dict, List


class WeatherSurgeRequest(BaseModel):
    """Forecast-origin context supplied to Member 3 weather-aware surge model."""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Forecast-origin timestamp, e.g. 2017-12-30T23:00:00"
    )
    arrivals_now: float = Field(default=0.0, ge=0, description="Arrivals in the current hour")
    arrivals_1h_ago: float = Field(default=0.0, ge=0, description="Arrivals one hour earlier")
    arrivals_2h_ago: float = Field(default=0.0, ge=0, description="Arrivals two hours earlier")
    arrivals_24h_ago: float = Field(default=0.0, ge=0, description="Arrivals at this hour yesterday")
    arrivals_168h_ago: float = Field(default=0.0, ge=0, description="Arrivals at this hour one week ago")
    temperature_2m: float = Field(default=25.0, description="Temperature in degrees Celsius")
    relative_humidity_2m: float = Field(default=60.0, ge=0, le=100, description="Relative humidity percent")
    precipitation: float = Field(default=0.0, ge=0, description="Precipitation in mm/hour")
    wind_speed_10m: float = Field(default=10.0, ge=0, description="Wind speed in km/h")
    weather_code: int = Field(default=0, ge=0, le=99, description="Open-Meteo WMO weather code")


class ModelEvaluation(BaseModel):
    held_out_model_mae: float
    simple_baseline_mae: float


class WeatherSurgeResponse(BaseModel):
    forecast_origin_timestamp: str
    horizon_hours: int = 2
    predicted_arrivals_next_2h: int
    dataset_relative_demand_level: str
    weather_code_seen_during_training: bool
    evaluation: ModelEvaluation
    data_warning: str
    safety_note: str


class LiveWeatherSurgeResponse(BaseModel):
    forecast_origin_timestamp: str
    horizon_hours: int = 2
    predicted_arrivals_next_2h: int
    dataset_relative_demand_level: str
    weather_code_seen_during_training: bool
    evaluation: ModelEvaluation
    data_warning: str
    safety_note: str
    hospital_id: int
    hospital_name: str
    historical_arrivals_extracted: Dict[str, float]
    weather_conditions_observed: Dict[str, Any]
    surge_risk_alert: bool


class SurgeModelInfoResponse(BaseModel):
    model_type: str
    model_artifact: str
    status: str
    horizon_hours: int
    evaluation: Dict[str, Any]
    thresholds: Dict[str, Any]
    feature_count: int
    features: List[str]
    known_weather_codes: List[str]
    data_note: str | None = None
