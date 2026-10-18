"""Example FastAPI service for Member 3's hospital surge predictor.

Run after training and saving surge_model.joblib:
    uvicorn api_example:app --reload
Then open http://127.0.0.1:8000/docs

This is a hackathon prototype, not for clinical or staffing decisions.
"""
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_MODEL_FILES = [
    BASE_DIR / "surge_model.joblib",
    BASE_DIR.parent.parent.parent / "app" / "ml" / "saved_models" / "surge_model.joblib",
    Path.cwd() / "legal_system" / "app" / "member3_backend_integration_pack" / "surge_model.joblib",
    Path.cwd() / "app" / "ml" / "saved_models" / "surge_model.joblib",
]


def resolve_model_file() -> Path:
    for candidate in CANDIDATE_MODEL_FILES:
        if candidate.exists():
            return candidate
    return BASE_DIR / "surge_model.joblib"


MODEL_FILE = resolve_model_file()
app = FastAPI(
    title="Hospital Surge Predictor — Member 3",
    description=(
        "Prototype API estimating arrivals over the following two hours. "
        "Historical US data and Des Moines weather proxy; not clinically validated."
    ),
    version="0.1.0",
)


class SurgeRequest(BaseModel):
    """Current context supplied by the backend for a forecast origin."""
    timestamp: datetime = Field(description="Forecast-origin timestamp, e.g. 2017-12-30T23:00:00")
    arrivals_now: float = Field(ge=0, description="Arrivals in the current hour")
    arrivals_1h_ago: float = Field(ge=0, description="Arrivals one hour earlier")
    arrivals_2h_ago: float = Field(ge=0, description="Arrivals two hours earlier")
    arrivals_24h_ago: float = Field(ge=0, description="Arrivals at this hour yesterday")
    arrivals_168h_ago: float = Field(ge=0, description="Arrivals at this hour one week ago")
    temperature_2m: float = Field(description="Temperature in degrees Celsius")
    relative_humidity_2m: float = Field(ge=0, le=100, description="Relative humidity percent")
    precipitation: float = Field(ge=0, description="Precipitation in mm/hour")
    wind_speed_10m: float = Field(ge=0, description="Wind speed in km/h")
    weather_code: int = Field(ge=0, le=99, description="Open-Meteo WMO weather code")


@lru_cache(maxsize=1)
def load_bundle() -> dict[str, Any]:
    target_file = resolve_model_file()
    if not target_file.exists():
        raise FileNotFoundError(
            f"Model file not found: {target_file.name}. Run python train_and_save_model.py first."
        )
    return joblib.load(target_file)


def build_input_row(request: SurgeRequest, bundle: dict[str, Any]) -> pd.DataFrame:
    ts = request.timestamp
    values = {
        "hour": ts.hour,
        "day_of_week": ts.weekday(),  # Monday=0, matching pandas datetime index
        "month": ts.month,
        "arrivals_now": request.arrivals_now,
        "arrivals_1h_ago": request.arrivals_1h_ago,
        "arrivals_2h_ago": request.arrivals_2h_ago,
        "arrivals_24h_ago": request.arrivals_24h_ago,
        "arrivals_168h_ago": request.arrivals_168h_ago,
        "temperature_2m": request.temperature_2m,
        "relative_humidity_2m": request.relative_humidity_2m,
        "precipitation": request.precipitation,
        "wind_speed_10m": request.wind_speed_10m,
    }
    row = pd.DataFrame([values])
    code_series = pd.Series(pd.array([request.weather_code], dtype="Int64")).astype("string")
    code_dummies = pd.get_dummies(code_series, prefix="weather_code", dtype=int)
    row = pd.concat([row, code_dummies], axis=1)
    # Ensures the API columns and order exactly match the trained model.
    row = row.reindex(columns=bundle["feature_cols"], fill_value=0)
    return row


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "model_artifact_exists": resolve_model_file().exists(),
        "service": "member3-hospital-surge-predictor",
    }


@app.post("/predict/surge")
def predict_surge(request: SurgeRequest) -> dict[str, Any]:
    try:
        bundle = load_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    row = build_input_row(request, bundle)
    raw_prediction = float(bundle["model"].predict(row)[0])
    prediction = max(0, int(round(raw_prediction)))
    if prediction <= bundle["low_cutoff"]:
        level = "LOW"
    elif prediction <= bundle["high_cutoff"]:
        level = "MEDIUM"
    else:
        level = "HIGH"

    weather_code_known = str(request.weather_code) in bundle.get("known_weather_codes", [])
    return {
        "forecast_origin_timestamp": request.timestamp.isoformat(),
        "horizon_hours": 2,
        "predicted_arrivals_next_2h": prediction,
        "dataset_relative_demand_level": level,
        "weather_code_seen_during_training": weather_code_known,
        "evaluation": {
            "held_out_model_mae": round(bundle["model_test_mae"], 3),
            "simple_baseline_mae": round(bundle["baseline_test_mae"], 3),
        },
        "data_warning": bundle["data_note"],
        "safety_note": "Prototype forecast only. Hospital staff must make operational decisions.",
    }
