"""
Integration tests for the FastAPI REST API.

Uses httpx.AsyncClient as the test client (recommended by FastAPI docs).
These tests hit the actual API endpoints and verify:
  - Status codes
  - Response structure
  - Validation error handling
  - All endpoint functionality
"""
import pytest
from httpx import AsyncClient, ASGITransport

try:
    from app.incident_detection_engine.app.main import app
except ImportError:
    from app.main import app


@pytest.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════════════════
#  UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_config(client):
    resp = await client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "hospital" in data
    assert "scoring" in data


# ═══════════════════════════════════════════════════════════════════════
#  ANALYSIS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

SAMPLE_BATCH = {
    "incidents": [
        {
            "incident_id": "INC-001",
            "incident_type": "road_accident",
            "latitude": 12.975,
            "longitude": 77.600,
            "timestamp": "2026-10-17T18:10:00Z",
            "severity": 4,
            "data_source": "SIMULATED_TEST",
            "weather_condition": "heavy_rain",
        },
        {
            "incident_id": "INC-002",
            "incident_type": "road_accident",
            "latitude": 12.978,
            "longitude": 77.603,
            "timestamp": "2026-10-17T18:45:00Z",
            "severity": 3,
            "data_source": "SIMULATED_TEST",
            "weather_condition": "none",
        },
    ]
}


@pytest.mark.asyncio
async def test_analyze_batch_success(client):
    resp = await client.post("/api/v1/analyze", json=SAMPLE_BATCH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine"] == "member4-incident-detection-engine"
    assert data["is_simulated_demo"] is True
    assert "risk" in data
    assert "clusters" in data
    assert "incidents" in data
    assert data["incident_count_total"] == 2


@pytest.mark.asyncio
async def test_analyze_batch_adds_distance(client):
    resp = await client.post("/api/v1/analyze", json=SAMPLE_BATCH)
    data = resp.json()
    for inc in data["incidents"]:
        assert "distance_km" in inc
        assert inc["distance_km"] >= 0


@pytest.mark.asyncio
async def test_analyze_batch_validation_error(client):
    bad_batch = {
        "incidents": [
            {
                "incident_id": "BAD",
                "incident_type": "test",
                "latitude": 999,  # Invalid!
                "longitude": 77.0,
                "timestamp": "2026-10-17T18:00:00Z",
                "severity": 3,
                "data_source": "TEST",
            }
        ]
    }
    resp = await client.post("/api/v1/analyze", json=bad_batch)
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_analyze_empty_batch_rejected(client):
    resp = await client.post("/api/v1/analyze", json={"incidents": []})
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
#  WEATHER & EVENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_weather_endpoint(client):
    resp = await client.get("/api/v1/weather")
    assert resp.status_code == 200
    data = resp.json()
    assert "observations" in data
    assert "risk_assessment" in data


@pytest.mark.asyncio
async def test_events_endpoint(client):
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "risk_assessment" in data


# ═══════════════════════════════════════════════════════════════════════
#  FORECAST FEED (INTEGRATION ENDPOINT)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_forecast_feed(client):
    resp = await client.post("/api/v1/forecast-feed", json=SAMPLE_BATCH)
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis" in data
    assert "weather" in data
    assert "events" in data
    assert "integration_notes" in data


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD & CORS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_dashboard_summary(client):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "hospital" in data
    assert "alert" in data
    assert "incidents" in data
    assert "clusters" in data
    assert "external_conditions" in data
    assert "weather" in data["external_conditions"]
    assert "events" in data["external_conditions"]
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_cors_headers_for_frontend(client):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    resp = await client.options("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

