"""
Automated tests for Member 3's Weather-Aware Surge Predictor Integration.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app as main_app
from app.ml.surge_predictor import WeatherSurgePredictor, find_model_path, load_surge_bundle
from legal_system.app.member3_backend_integration_pack.api_example import app as member3_app
from legal_system.app.main import app as legal_app

client_main = TestClient(main_app)
client_member3 = TestClient(member3_app)
client_legal = TestClient(legal_app)

SAMPLE_TELEMETRY = {
    "timestamp": "2017-12-30T23:00:00",
    "arrivals_now": 2,
    "arrivals_1h_ago": 3,
    "arrivals_2h_ago": 2,
    "arrivals_24h_ago": 1,
    "arrivals_168h_ago": 2,
    "temperature_2m": -2.5,
    "relative_humidity_2m": 80,
    "precipitation": 0,
    "wind_speed_10m": 12,
    "weather_code": 3,
}


def test_surge_model_artifact_exists():
    """Verify that the model artifact exists and contains all required metadata."""
    artifact_path = find_model_path()
    assert artifact_path is not None
    assert artifact_path.exists()

    bundle = load_surge_bundle()
    assert "model" in bundle
    assert "feature_cols" in bundle
    assert "low_cutoff" in bundle
    assert "high_cutoff" in bundle
    assert "model_test_mae" in bundle
    assert "baseline_test_mae" in bundle
    assert bundle["model_test_mae"] < bundle["baseline_test_mae"]


def test_weather_surge_predictor_raw():
    """Test the WeatherSurgePredictor engine service directly."""
    predictor = WeatherSurgePredictor()
    assert predictor.is_available is True

    result = predictor.predict_raw(
        timestamp=datetime(2017, 12, 30, 23, 0, 0, tzinfo=timezone.utc),
        arrivals_now=2,
        arrivals_1h_ago=3,
        arrivals_2h_ago=2,
        arrivals_24h_ago=1,
        arrivals_168h_ago=2,
        temperature_2m=-2.5,
        relative_humidity_2m=80,
        precipitation=0,
        wind_speed_10m=12,
        weather_code=3,
    )

    assert result["horizon_hours"] == 2
    assert result["predicted_arrivals_next_2h"] >= 0
    assert result["dataset_relative_demand_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "evaluation" in result
    assert "held_out_model_mae" in result["evaluation"]


def test_main_app_root_predict_surge():
    """Test POST /predict/surge on the main backend application."""
    response = client_main.post("/predict/surge", json=SAMPLE_TELEMETRY)
    assert response.status_code == 200
    data = response.json()
    assert data["horizon_hours"] == 2
    assert "predicted_arrivals_next_2h" in data
    assert data["dataset_relative_demand_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "data_warning" in data
    assert "safety_note" in data


def test_main_app_root_predict_surge_health():
    """Test GET /predict/surge/health on the main backend application."""
    response = client_main.get("/predict/surge/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_artifact_available"] is True
    assert data["service"] == "member3-hospital-surge-predictor"


def test_api_v1_predictions_surge():
    """Test POST /api/v1/predictions/surge on the API v1 router."""
    response = client_main.post("/api/v1/predictions/surge", json=SAMPLE_TELEMETRY)
    assert response.status_code == 200
    data = response.json()
    assert data["horizon_hours"] == 2
    assert isinstance(data["predicted_arrivals_next_2h"], int)


def test_api_v1_predictions_surge_model_info():
    """Test GET /api/v1/predictions/surge/model-info."""
    response = client_main.get("/api/v1/predictions/surge/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["horizon_hours"] == 2
    assert data["evaluation"]["held_out_model_mae"] > 0
    assert len(data["features"]) > 0


def test_api_v1_predictions_surge_live_hospital():
    """Test GET /api/v1/predictions/surge/live?hospital_id=1 with database integration."""
    response = client_main.get("/api/v1/predictions/surge/live?hospital_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["hospital_id"] == 1
    assert "hospital_name" in data
    assert "historical_arrivals_extracted" in data
    assert "weather_conditions_observed" in data
    assert "surge_risk_alert" in data


def test_api_v1_predictions_surge_live_hospital_not_found():
    """Test GET /api/v1/predictions/surge/live for non-existent hospital."""
    response = client_main.get("/api/v1/predictions/surge/live?hospital_id=99999")
    assert response.status_code == 404


def test_member3_standalone_api():
    """Test the standalone Member 3 API in member3_backend_integration_pack."""
    health_res = client_member3.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["model_artifact_exists"] is True

    predict_res = client_member3.post("/predict/surge", json=SAMPLE_TELEMETRY)
    assert predict_res.status_code == 200
    assert predict_res.json()["horizon_hours"] == 2


def test_legal_system_mounted_surge_endpoint():
    """Test POST /predict/surge mounted on legal_system app."""
    response = client_legal.post("/predict/surge", json=SAMPLE_TELEMETRY)
    assert response.status_code == 200
    data = response.json()
    assert data["horizon_hours"] == 2


def test_surge_predictor_edge_cases():
    """Test unknown weather codes and extreme arrival rates."""
    predictor = WeatherSurgePredictor()

    # Unknown weather code (should default to 0 in one-hot features without crash)
    result_unknown_code = predictor.predict_raw(
        timestamp=datetime.now(timezone.utc),
        arrivals_now=0,
        arrivals_1h_ago=0,
        arrivals_2h_ago=0,
        arrivals_24h_ago=0,
        arrivals_168h_ago=0,
        temperature_2m=42.0,
        relative_humidity_2m=20,
        precipitation=5.0,
        wind_speed_10m=45,
        weather_code=99,
    )
    assert result_unknown_code["weather_code_seen_during_training"] is False
    assert result_unknown_code["predicted_arrivals_next_2h"] >= 0

    # High daytime surge scenario (e.g. 2 PM peak hours)
    result_high_surge = predictor.predict_raw(
        timestamp=datetime(2017, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
        arrivals_now=18,
        arrivals_1h_ago=15,
        arrivals_2h_ago=14,
        arrivals_24h_ago=12,
        arrivals_168h_ago=10,
        temperature_2m=34.0,
        relative_humidity_2m=85,
        precipitation=12.0,
        wind_speed_10m=35,
        weather_code=61,
    )
    assert result_high_surge["predicted_arrivals_next_2h"] > 10
    assert result_high_surge["dataset_relative_demand_level"] == "HIGH"
