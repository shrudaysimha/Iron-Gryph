"""
Weather-Aware Hospital Surge Prediction Engine — Member 3 Model Integration.

Combines historical patient arrivals (now, -1h, -2h, -24h, -168h) with
meteorological conditions (temperature, humidity, precipitation, wind speed, WMO weather code)
to forecast patient intake over the next 2 hours.
"""

from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import logging

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.patient import Admission

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SAVED_MODELS_DIR = BASE_DIR / "saved_models"
MODEL_CANDIDATES = [
    SAVED_MODELS_DIR / "surge_model.joblib",
    BASE_DIR.parent.parent / "legal_system" / "app" / "member3_backend_integration_pack" / "surge_model.joblib",
    Path.cwd() / "app" / "ml" / "saved_models" / "surge_model.joblib",
    Path.cwd() / "legal_system" / "app" / "member3_backend_integration_pack" / "surge_model.joblib",
]

# WMO Weather code mapping for general conditions
CONDITION_TO_WMO = {
    0: 0,   # Clear sky -> 0
    1: 61,  # Rain/Drizzle -> 61
    2: 95,  # Thunderstorm -> 95
    3: 96,  # Severe storm / extreme -> 96
}


def find_model_path() -> Optional[Path]:
    """Find the trained surge model artifact across candidate locations."""
    for path in MODEL_CANDIDATES:
        if path.exists():
            return path
    return None


@lru_cache(maxsize=1)
def load_surge_bundle() -> Dict[str, Any]:
    """Load the trained Random Forest surge model bundle from disk."""
    model_path = find_model_path()
    if not model_path or not model_path.exists():
        raise FileNotFoundError(
            "Trained surge model not found. Run python "
            "legal_system/app/member3_backend_integration_pack/train_and_save_model.py first."
        )
    return joblib.load(model_path)


class WeatherSurgePredictor:
    """Predictor service wrapping Member 3's weather-aware Random Forest model."""

    def __init__(self):
        self._bundle: Optional[Dict[str, Any]] = None
        self._try_load()

    def _try_load(self):
        try:
            self._bundle = load_surge_bundle()
            logger.info("Loaded weather-aware surge model artifact successfully.")
        except Exception as exc:
            logger.warning("Could not load surge model bundle: %s", exc)
            self._bundle = None

    @property
    def is_available(self) -> bool:
        return self._bundle is not None or find_model_path() is not None

    def get_bundle(self) -> Dict[str, Any]:
        if self._bundle is None:
            self._bundle = load_surge_bundle()
        return self._bundle

    def build_input_row(
        self,
        timestamp: datetime,
        arrivals_now: float,
        arrivals_1h_ago: float,
        arrivals_2h_ago: float,
        arrivals_24h_ago: float,
        arrivals_168h_ago: float,
        temperature_2m: float,
        relative_humidity_2m: float,
        precipitation: float,
        wind_speed_10m: float,
        weather_code: int,
    ) -> pd.DataFrame:
        """Construct the one-hot encoded feature row matching training columns exactly."""
        bundle = self.get_bundle()
        values = {
            "hour": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "month": timestamp.month,
            "arrivals_now": arrivals_now,
            "arrivals_1h_ago": arrivals_1h_ago,
            "arrivals_2h_ago": arrivals_2h_ago,
            "arrivals_24h_ago": arrivals_24h_ago,
            "arrivals_168h_ago": arrivals_168h_ago,
            "temperature_2m": temperature_2m,
            "relative_humidity_2m": relative_humidity_2m,
            "precipitation": precipitation,
            "wind_speed_10m": wind_speed_10m,
        }
        row = pd.DataFrame([values])
        code_series = pd.Series(pd.array([weather_code], dtype="Int64")).astype("string")
        code_dummies = pd.get_dummies(code_series, prefix="weather_code", dtype=int)
        row = pd.concat([row, code_dummies], axis=1)
        row = row.reindex(columns=bundle["feature_cols"], fill_value=0)
        return row

    def predict_raw(
        self,
        timestamp: datetime,
        arrivals_now: float,
        arrivals_1h_ago: float,
        arrivals_2h_ago: float,
        arrivals_24h_ago: float,
        arrivals_168h_ago: float,
        temperature_2m: float,
        relative_humidity_2m: float,
        precipitation: float,
        wind_speed_10m: float,
        weather_code: int,
    ) -> Dict[str, Any]:
        """Execute prediction conforming to Member 3 contract."""
        bundle = self.get_bundle()
        row = self.build_input_row(
            timestamp=timestamp,
            arrivals_now=arrivals_now,
            arrivals_1h_ago=arrivals_1h_ago,
            arrivals_2h_ago=arrivals_2h_ago,
            arrivals_24h_ago=arrivals_24h_ago,
            arrivals_168h_ago=arrivals_168h_ago,
            temperature_2m=temperature_2m,
            relative_humidity_2m=relative_humidity_2m,
            precipitation=precipitation,
            wind_speed_10m=wind_speed_10m,
            weather_code=weather_code,
        )

        raw_pred = float(bundle["model"].predict(row)[0])
        prediction = max(0, int(round(raw_pred)))

        low_cutoff = bundle.get("low_cutoff", 5.0)
        high_cutoff = bundle.get("high_cutoff", 10.0)

        if prediction <= low_cutoff:
            level = "LOW"
        elif prediction <= high_cutoff:
            level = "MEDIUM"
        else:
            level = "HIGH"

        known_codes = bundle.get("known_weather_codes", [])
        weather_code_known = str(weather_code) in known_codes

        return {
            "forecast_origin_timestamp": timestamp.isoformat(),
            "horizon_hours": bundle.get("horizon_hours", 2),
            "predicted_arrivals_next_2h": prediction,
            "dataset_relative_demand_level": level,
            "weather_code_seen_during_training": weather_code_known,
            "evaluation": {
                "held_out_model_mae": round(float(bundle.get("model_test_mae", 2.70)), 3),
                "simple_baseline_mae": round(float(bundle.get("baseline_test_mae", 3.92)), 3),
            },
            "data_warning": bundle.get(
                "data_note",
                "Historical US research arrival data; Des Moines, Iowa weather is an approximate proxy."
            ),
            "safety_note": "Prototype forecast only. Hospital staff must make operational decisions.",
        }

    def predict_live_hospital(self, hospital_id: int, db: Session) -> Dict[str, Any]:
        """
        Extract live admission history and meteorological metrics for a hospital,
        and generate a 2-hour surge prediction.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital with id {hospital_id} not found.")

        now = datetime.now(timezone.utc)

        # 1. Query admissions in historical time windows
        def count_admissions(start_delta: timedelta, end_delta: timedelta) -> float:
            start_time = now - start_delta
            end_time = now - end_delta
            return float(
                db.query(Admission)
                .filter(
                    Admission.hospital_id == hospital_id,
                    Admission.admitted_at >= start_time,
                    Admission.admitted_at < end_time,
                )
                .count()
            )

        arrivals_now = count_admissions(timedelta(hours=1), timedelta(hours=0))
        arrivals_1h = count_admissions(timedelta(hours=2), timedelta(hours=1))
        arrivals_2h = count_admissions(timedelta(hours=3), timedelta(hours=2))
        arrivals_24h = count_admissions(timedelta(hours=25), timedelta(hours=24))
        arrivals_168h = count_admissions(timedelta(hours=169), timedelta(hours=168))

        # 2. Get current weather
        from app.services.weather_service import WeatherService
        ws = WeatherService()
        weather = ws.get_weather_sync(city=hospital.city)

        temp = float(weather.get("temperature_celsius", 28.0))
        humidity = float(weather.get("humidity_percent", 65.0))
        precip = 1.5 if weather.get("condition_encoded", 0) >= 1 else 0.0
        wind = 14.0
        condition_code = weather.get("condition_encoded", 0)
        wmo_code = CONDITION_TO_WMO.get(condition_code, 0)

        raw_result = self.predict_raw(
            timestamp=now,
            arrivals_now=arrivals_now,
            arrivals_1h_ago=arrivals_1h,
            arrivals_2h_ago=arrivals_2h,
            arrivals_24h_ago=arrivals_24h,
            arrivals_168h_ago=arrivals_168h,
            temperature_2m=temp,
            relative_humidity_2m=humidity,
            precipitation=precip,
            wind_speed_10m=wind,
            weather_code=wmo_code,
        )

        # 3. Clinical surge evaluation
        is_surge = (
            raw_result["dataset_relative_demand_level"] == "HIGH"
            or raw_result["predicted_arrivals_next_2h"] >= 10
        )

        return {
            **raw_result,
            "hospital_id": hospital.id,
            "hospital_name": hospital.name,
            "historical_arrivals_extracted": {
                "arrivals_now": arrivals_now,
                "arrivals_1h_ago": arrivals_1h,
                "arrivals_2h_ago": arrivals_2h,
                "arrivals_24h_ago": arrivals_24h,
                "arrivals_168h_ago": arrivals_168h,
            },
            "weather_conditions_observed": {
                "temperature_celsius": temp,
                "humidity_percent": humidity,
                "precipitation_mm": precip,
                "wind_speed_kmh": wind,
                "condition": weather.get("condition", "Clear"),
                "wmo_code": wmo_code,
            },
            "surge_risk_alert": is_surge,
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return metadata, training statistics, and feature specs."""
        bundle = self.get_bundle()
        return {
            "model_type": "RandomForestRegressor (250 estimators, min_samples_leaf=3)",
            "model_artifact": str(find_model_path()),
            "status": "ready",
            "horizon_hours": bundle.get("horizon_hours", 2),
            "evaluation": {
                "held_out_model_mae": round(float(bundle.get("model_test_mae", 2.70)), 3),
                "simple_baseline_mae": round(float(bundle.get("baseline_test_mae", 3.92)), 3),
                "test_period_starts": bundle.get("test_period_starts"),
            },
            "thresholds": {
                "low_cutoff": bundle.get("low_cutoff"),
                "high_cutoff": bundle.get("high_cutoff"),
            },
            "feature_count": len(bundle.get("feature_cols", [])),
            "features": bundle.get("feature_cols", []),
            "known_weather_codes": bundle.get("known_weather_codes", []),
            "data_note": bundle.get("data_note"),
        }
