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
    assert "Hospital Surge AI" in data["message"]
    assert "endpoints" in data

    # Verify JSON API info endpoint
    info_resp = client.get("/api/info")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert "endpoints" in info_data
    assert info_data["version"] == "1.0.0"



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


def test_bed_grid_and_reservation_flow():
    # 1. Fetch live bed grid
    grid_res = client.get("/api/v1/beds/grid?hospital_id=1")
    assert grid_res.status_code == 200
    grid = grid_res.json()
    assert grid["hospital_id"] == 1
    assert "wards" in grid
    assert len(grid["wards"]) > 0

    # Find an available bed
    target_bed = None
    for ward in grid["wards"]:
        for bed in ward["beds"]:
            if bed["status"] == "available":
                target_bed = bed
                break
        if target_bed:
            break

    assert target_bed is not None, "At least one bed should be available in seeded db"

    # 2. Reserve the bed
    reserve_payload = {
        "bed_id": target_bed["id"],
        "hospital_id": 1,
        "patient_name": "Test Emergency Patient",
        "triage_score": 1,
    }
    res_1 = client.post("/api/v1/beds/reserve", json=reserve_payload)
    assert res_1.status_code == 200
    res_data = res_1.json()
    assert res_data["success"] is True
    assert res_data["status"] == "reserved"
    token = res_data["reservation_token"]

    # 3. Simulate concurrency collision: Second user attempts to reserve the same bed
    res_2 = client.post("/api/v1/beds/reserve", json={
        "bed_id": target_bed["id"],
        "hospital_id": 1,
        "patient_name": "Concurrent Conflicting Patient",
        "triage_score": 2,
    })
    assert res_2.status_code == 409
    conflict_detail = res_2.json()["detail"]
    assert conflict_detail["error"] == "bed_unavailable"
    assert "alternative_beds" in conflict_detail

    # 4. Release reservation
    release_res = client.post(f"/api/v1/beds/release?bed_id={target_bed['id']}&reservation_token={token}")
    assert release_res.status_code == 200
    assert release_res.json()["status"] == "available"

