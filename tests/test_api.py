"""
Automated tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "app_name" in data


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert data["version"] == "1.0.0"


def test_list_hospitals():
    response = client.get("/api/v1/hospitals/")
    assert response.status_code == 200
    hospitals = response.json()
    assert len(hospitals) >= 1
    assert "name" in hospitals[0]
    assert "total_beds" in hospitals[0]


def test_get_hospital_capacity():
    response = client.get("/api/v1/hospitals/1/capacity")
    assert response.status_code == 200
    data = response.json()
    assert data["hospital_id"] == 1
    assert "total_beds" in data
    assert "available_beds" in data
    assert "occupancy_rate" in data


def test_dashboard_overview():
    response = client.get("/api/v1/dashboard/overview?hospital_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["hospital_id"] == 1
    assert "capacity" in data
    assert "staff" in data
    assert "fleet" in data


def test_ambulances_fleet():
    response = client.get("/api/v1/ambulances/?hospital_id=1")
    assert response.status_code == 200
    ambulances = response.json()
    assert isinstance(ambulances, list)


def test_staff_on_duty():
    response = client.get("/api/v1/staff/on-duty?hospital_id=1")
    assert response.status_code == 200
    staff = response.json()
    assert isinstance(staff, list)


def test_predictions_demand():
    # Trigger a prediction first
    gen_res = client.post("/api/v1/predictions/generate", json={"hospital_id": 1, "horizon_hours": 4})
    assert gen_res.status_code == 201
    preds = gen_res.json()
    assert len(preds) >= 1
    assert "predicted_total_admissions" in preds[0]
    assert "confidence_score" in preds[0]


def test_allocations_recommend():
    response = client.get("/api/v1/allocations/recommend?hospital_id=1")
    assert response.status_code == 200
    plan = response.json()
    assert plan["hospital_id"] == 1
    assert "recommendations" in plan
    assert len(plan["recommendations"]) >= 1
    assert "overall_risk_level" in plan


def test_alerts():
    response = client.get("/api/v1/alerts/?hospital_id=1")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)


def test_environment_weather():
    response = client.get("/api/v1/environment/weather")
    assert response.status_code == 200
    data = response.json()
    assert "temperature_celsius" in data
    assert "surge_risk_factor" in data


def test_environment_events():
    response = client.get("/api/v1/environment/events?hospital_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "has_local_event" in data
    assert "event_surge_multiplier" in data
