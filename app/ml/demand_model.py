"""XGBoost-based demand prediction model."""

import os
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Feature order must match training
FEATURE_NAMES = [
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "is_night",
    "is_holiday",
    "rolling_avg_7d",
    "rolling_avg_24h",
    "rolling_avg_3d",
    "admissions_last_1h",
    "emergency_arrivals_4h",
    "occupancy_rate",
    "available_beds",
    "icu_occupancy_rate",
    "ambulances_dispatched",
    "ambulances_available",
    "critical_ratio_24h",
    "severe_ratio_24h",
    "weather_temperature",
    "weather_condition_encoded",
    "air_quality_index",
    "local_event_flag",
    "local_event_size",
    "nearby_accident_flag",
]

MODEL_DIR = Path(__file__).parent / "saved_models"


class DemandModel:
    """
    XGBoost demand prediction model.

    When a trained model exists on disk, it is loaded and used for predictions.
    Otherwise, a heuristic-based fallback is used until training data is available.
    """

    def __init__(self):
        self.model = None
        self.version = "heuristic-v1"
        self._try_load_model()

    def _try_load_model(self):
        """Attempt to load a trained model from disk."""
        model_path = MODEL_DIR / "demand_model.joblib"
        if model_path.exists():
            try:
                import joblib
                self.model = joblib.load(model_path)
                self.version = "xgboost-v1"
                logger.info("Loaded trained demand model from %s", model_path)
            except Exception as e:
                logger.warning("Failed to load model: %s. Using heuristic fallback.", e)
                self.model = None

    def predict(self, features: dict) -> dict:
        """
        Predict demand based on extracted features.

        Returns:
            dict with keys: total_admissions, emergency_admissions, icu_demand,
                            surgical_demand, confidence
        """
        if self.model is not None:
            return self._predict_with_model(features)
        return self._predict_heuristic(features)

    def _predict_with_model(self, features: dict) -> dict:
        """Use the trained XGBoost model for prediction."""
        import pandas as pd

        # Build feature vector in correct order
        feature_vector = np.array([[features.get(f, 0) for f in FEATURE_NAMES]])
        df = pd.DataFrame(feature_vector, columns=FEATURE_NAMES)

        prediction = self.model.predict(df)[0]

        # The model predicts total admissions; estimate breakdown
        total = max(1, int(round(prediction)))

        # Use current ratios to estimate breakdown
        emergency_ratio = 0.4 + features.get("critical_ratio_24h", 0) * 0.2
        icu_ratio = features.get("icu_occupancy_rate", 0.3) * 0.3
        surgical_ratio = 0.15

        return {
            "total_admissions": total,
            "emergency_admissions": max(1, int(total * emergency_ratio)),
            "icu_demand": max(0, int(total * icu_ratio)),
            "surgical_demand": max(0, int(total * surgical_ratio)),
            "confidence": 0.85,  # Will be replaced with actual model confidence
        }

    def _predict_heuristic(self, features: dict) -> dict:
        """
        Heuristic fallback prediction when no trained model is available.

        Uses weighted combination of available features to estimate demand.
        This provides reasonable estimates until enough training data is collected.
        """
        # Base prediction from rolling averages
        base = features.get("rolling_avg_24h", 10)
        trend = features.get("rolling_avg_7d", base)

        # Time-of-day multiplier (hospitals see peaks at certain hours)
        hour = features.get("hour_of_day", 12)
        time_multipliers = {
            # Morning rush (8-12)
            8: 1.3, 9: 1.5, 10: 1.6, 11: 1.5, 12: 1.3,
            # Afternoon
            13: 1.1, 14: 1.0, 15: 1.0, 16: 1.1,
            # Evening (5-9 PM — accident peak)
            17: 1.3, 18: 1.5, 19: 1.6, 20: 1.4, 21: 1.2,
            # Night (lower)
            22: 0.8, 23: 0.6, 0: 0.5, 1: 0.4, 2: 0.3, 3: 0.3,
            4: 0.4, 5: 0.5, 6: 0.7, 7: 1.0,
        }
        time_mult = time_multipliers.get(hour, 1.0)

        # Occupancy pressure
        occupancy = features.get("occupancy_rate", 0.5)
        occupancy_factor = 1 + (occupancy - 0.5) * 0.3  # Higher occupancy → expect more

        # Weekend/holiday effect
        weekend_mult = 0.85 if features.get("is_weekend", 0) else 1.0
        holiday_mult = 0.7 if features.get("is_holiday", 0) else 1.0

        # Weather impact
        weather_code = features.get("weather_condition_encoded", 0)
        weather_mult = {0: 1.0, 1: 1.1, 2: 1.4, 3: 1.8}.get(weather_code, 1.0)

        # Event impact
        event_mult = 1.0
        if features.get("local_event_flag", 0):
            event_size = features.get("local_event_size", 0)
            event_mult = 1.0 + min(event_size / 10000, 0.5)  # Cap at 1.5x

        # Accident flag
        accident_mult = 1.3 if features.get("nearby_accident_flag", 0) else 1.0

        # Recent emergency spike detection
        recent_emergency = features.get("emergency_arrivals_4h", 0)
        last_hour = features.get("admissions_last_1h", 0)
        spike_mult = 1.0
        if last_hour > base * 0.3:  # If last hour > 30% of daily average
            spike_mult = 1.2 + (last_hour / base) * 0.3

        # Combine all factors
        predicted = (
            max(base, trend)
            * time_mult
            * occupancy_factor
            * weekend_mult
            * holiday_mult
            * weather_mult
            * event_mult
            * accident_mult
            * spike_mult
        )

        total = max(1, int(round(predicted)))

        # Estimate breakdown
        emergency_ratio = 0.35 + (recent_emergency / max(total, 1)) * 0.2
        icu_ratio = 0.1 + features.get("critical_ratio_24h", 0) * 0.3
        surgical_ratio = 0.12

        # Confidence is lower for heuristic
        confidence = 0.55
        if base > 5:
            confidence += 0.15  # More data → higher confidence
        if trend > 0:
            confidence += 0.05

        return {
            "total_admissions": total,
            "emergency_admissions": max(1, int(total * min(emergency_ratio, 0.6))),
            "icu_demand": max(0, int(total * min(icu_ratio, 0.3))),
            "surgical_demand": max(0, int(total * surgical_ratio)),
            "confidence": round(min(confidence, 0.95), 2),
        }
