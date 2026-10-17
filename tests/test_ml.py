"""
Tests for ML feature extraction and demand prediction model.
"""

from datetime import datetime, timezone
from app.database import SessionLocal
from app.ml.demand_model import DemandModel
from app.ml.feature_engineering import FeatureEngineer
from app.ml.optimizer import ResourceOptimizer
from app.models.prediction import Prediction


def test_feature_engineering():
    db = SessionLocal()
    try:
        fe = FeatureEngineer(db)
        now = datetime.now(timezone.utc)
        features = fe.extract_features(hospital_id=1, target_time=now)

        assert "hour_of_day" in features
        assert "day_of_week" in features
        assert "rolling_avg_7d" in features
        assert "weather_temperature" in features
        assert "local_event_flag" in features
        assert features["occupancy_rate"] >= 0.0
    finally:
        db.close()


def test_demand_model_prediction():
    model = DemandModel()
    dummy_features = {
        "hour_of_day": 14,
        "day_of_week": 2,
        "month": 10,
        "is_weekend": 0,
        "is_night": 0,
        "is_holiday": 0,
        "rolling_avg_7d": 12.5,
        "rolling_avg_24h": 15.0,
        "rolling_avg_3d": 13.0,
        "admissions_last_1h": 2,
        "emergency_arrivals_4h": 5,
        "occupancy_rate": 0.75,
        "available_beds": 25,
        "icu_occupancy_rate": 0.8,
        "ambulances_dispatched": 2,
        "ambulances_available": 3,
        "critical_ratio_24h": 0.2,
        "severe_ratio_24h": 0.3,
        "weather_temperature": 29.0,
        "weather_condition_encoded": 0,
        "air_quality_index": 55,
        "local_event_flag": 0,
        "local_event_size": 0,
        "nearby_accident_flag": 0,
    }

    pred = model.predict(dummy_features)
    assert pred["total_admissions"] >= 1
    assert pred["emergency_admissions"] >= 1
    assert pred["confidence"] > 0


def test_resource_optimizer():
    optimizer = ResourceOptimizer()
    dummy_pred = Prediction(
        predicted_total_admissions=25,
        predicted_emergency_admissions=12,
        predicted_icu_demand=5,
        predicted_surgical_demand=3,
        horizon_hours=4,
    )
    current_state = {
        "total_beds": 100,
        "available_beds": 8,  # Critical occupancy: 92%
        "icu_available": 1,   # Critical ICU
        "doctors_on_duty": 2, # Under-staffed
        "nurses_on_duty": 4,
        "available_ambulances": 1,
        "total_ambulances": 5,
        "ventilator_available": 1,
        "current_patients": 40,
    }

    recs = optimizer.optimize(dummy_pred, current_state)
    assert len(recs) >= 4
    # Should flag critical bed or ICU shortages
    priorities = [r["priority"] for r in recs]
    assert "critical" in priorities or "high" in priorities
