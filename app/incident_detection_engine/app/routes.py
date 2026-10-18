"""
REST API routes for the Incident Detection Engine.

ENDPOINT MAP
────────────
  GET  /                     → Welcome message
  GET  /health               → Health check
  GET  /config               → Current engine configuration

  POST /api/v1/analyze       → Analyse a batch of incidents (main endpoint)
  GET  /api/v1/incidents     → Load & return enriched incidents from file
  GET  /api/v1/alerts/latest → Generate current alert from file data

  GET  /api/v1/weather       → Current weather observations
  GET  /api/v1/events        → Current public events

  POST /api/v1/forecast-feed → Package data for the forecasting module

All endpoints return JSON with consistent error handling.
CORS is enabled so the frontend dashboard can call these APIs.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis_engine import analyze_file, analyze_incidents
from .config import settings
from .event_service import (
    enrich_events_with_distance,
    evaluate_event_risk,
    get_current_events,
)
from .schemas import (
    AnalysisResponse,
    AlertResponse,
    HealthResponse,
    IncidentBatchRequest,
)
from .weather_service import evaluate_weather_risk, get_current_weather

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════
#  UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/", tags=["Utility"])
async def root():
    """Welcome endpoint — confirms the API is running."""
    return {
        "message": "Hospital Patient Surge Prediction — Incident Detection Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health", response_model=HealthResponse, tags=["Utility"])
async def health_check():
    """Health check for load balancers and monitoring."""
    return HealthResponse()


@router.get("/config", tags=["Utility"])
async def get_config():
    """Return the current engine configuration (useful for debugging)."""
    return {
        "hospital": {
            "latitude": settings.hospital_latitude,
            "longitude": settings.hospital_longitude,
            "name": settings.hospital_name,
        },
        "clustering": {
            "cluster_radius_km": settings.cluster_radius_km,
            "cluster_window_minutes": settings.cluster_window_minutes,
        },
        "scoring": {
            "nearby_radius_km": settings.nearby_radius_km,
            "high_risk_threshold": settings.high_risk_threshold,
            "moderate_risk_threshold": settings.moderate_risk_threshold,
            "weights": {
                "count": settings.count_weight,
                "severity": settings.severity_weight,
                "proximity": settings.proximity_weight,
                "weather": settings.weather_weight,
            },
        },
        "data_sources": {
            "weather_api_configured": bool(settings.weather_api_key),
            "events_api_configured": bool(settings.events_api_key),
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  CORE ANALYSIS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.post("/api/v1/analyze", tags=["Analysis"])
async def analyze_batch(request: IncidentBatchRequest):
    """Analyse a batch of incidents submitted via POST.

    This is the MAIN endpoint. The frontend or forecasting module sends
    incident data here and receives a complete analysis with risk score,
    clusters, distances, and an alert.

    Request body:
    ```json
    {
      "incidents": [
        {
          "incident_id": "INC-001",
          "incident_type": "road_accident",
          "latitude": 12.975,
          "longitude": 77.600,
          "timestamp": "2026-10-17T18:10:00Z",
          "severity": 4,
          "data_source": "SIMULATED_DATASET",
          "weather_condition": "heavy_rain"
        }
      ]
    }
    ```
    """
    try:
        incidents = [inc.model_dump() for inc in request.incidents]
        result = analyze_incidents(incidents)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/api/v1/incidents", tags=["Analysis"])
async def get_incidents(
    source: str = Query(
        default="json",
        description="Data source: 'json' or 'csv'",
        pattern="^(json|csv)$",
    ),
):
    """Load incidents from the sample data file and return enriched records.

    Each incident includes its distance to the hospital.
    Use `?source=csv` to load from CSV instead of JSON.
    """
    try:
        if source == "csv":
            path = Path(settings.incidents_csv_path)
        else:
            path = Path(settings.incidents_json_path)

        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Data file not found: {path}. Make sure sample data exists.",
            )

        result = analyze_file(path)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/api/v1/alerts/latest", tags=["Alerts"])
async def get_latest_alert(
    source: str = Query(default="json", pattern="^(json|csv)$"),
):
    """Generate a current alert based on the latest incident data.

    This is a simplified endpoint that returns just the alert payload,
    designed for the frontend dashboard alert card.
    """
    try:
        path = Path(settings.incidents_json_path if source == "json" else settings.incidents_csv_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Data file not found: {path}")

        result = analyze_file(path)
        return result["alert"]
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
#  WEATHER & EVENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/api/v1/weather", tags=["External Intelligence"])
async def get_weather():
    """Get current weather observations and risk assessment.

    Returns simulated data unless WEATHER_API_KEY is configured.
    """
    weather_data = await get_current_weather()
    risk = evaluate_weather_risk(weather_data)
    is_live = any(not w.get("is_simulated", True) for w in weather_data)
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": now_utc,
        "data_source": "LIVE_API" if is_live else "SIMULATED",
        "observations": weather_data,
        "risk_assessment": risk,
    }


@router.get("/api/v1/events", tags=["External Intelligence"])
async def get_events():
    """Get current public events and their surge-risk assessment.

    Returns simulated data unless an events API is configured.
    Enriches all events with distance_to_hospital_km for map plotting.
    """
    events = await get_current_events()
    enriched_events = enrich_events_with_distance(events)
    risk = evaluate_event_risk(events)
    is_live = any(not e.get("is_simulated", True) for e in events)
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": now_utc,
        "data_source": "LIVE_API" if is_live else "SIMULATED",
        "events": enriched_events,
        "risk_assessment": risk,
    }


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD & INTEGRATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/api/v1/dashboard/summary", tags=["Dashboard"])
async def get_dashboard_summary(
    source: str = Query(
        default="json",
        description="Data source: 'json' or 'csv'",
        pattern="^(json|csv)$",
    ),
):
    """Unified endpoint for frontend dashboards (React, Vite, Next.js).

    Consolidates the complete context-intelligence picture:
      - Hospital location & monitoring parameters
      - Latest potential surge-risk alert card payload
      - Recent incidents enriched with hospital distance (for map markers)
      - Detected incident clusters (for map overlays & grouping)
      - Current external conditions (weather observations & public events)
      - Data freshness and provenance (timestamps and source indicators)
    """
    try:
        path = Path(settings.incidents_json_path if source == "json" else settings.incidents_csv_path)
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Data file not found: {path}. Ensure sample data exists.",
            )

        analysis = analyze_file(path)
        weather_data = await get_current_weather()
        weather_risk = evaluate_weather_risk(weather_data)
        is_weather_live = any(not w.get("is_simulated", True) for w in weather_data)

        raw_events = await get_current_events()
        enriched_events = enrich_events_with_distance(raw_events)
        event_risk = evaluate_event_risk(raw_events)
        is_events_live = any(not e.get("is_simulated", True) for e in raw_events)

        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            "timestamp": now_utc,
            "engine": analysis["engine"],
            "is_simulated_demo": analysis["is_simulated_demo"],
            "clinical_validation": analysis["clinical_validation"],
            "hospital": analysis["hospital"],
            "alert": analysis["alert"],
            "incidents": analysis["incidents"],
            "incident_count_total": analysis["incident_count_total"],
            "incident_count_scored": analysis["incident_count_scored"],
            "clusters": analysis["clusters"],
            "external_conditions": {
                "weather": {
                    "timestamp": now_utc,
                    "data_source": "LIVE_API" if is_weather_live else "SIMULATED",
                    "observations": weather_data,
                    "risk_assessment": weather_risk,
                },
                "events": {
                    "timestamp": now_utc,
                    "data_source": "LIVE_API" if is_events_live else "SIMULATED",
                    "events": enriched_events,
                    "risk_assessment": event_risk,
                },
            },
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
#  INTEGRATION ENDPOINTS (for forecasting module & frontend)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/api/v1/forecast-feed", tags=["Integration"])
async def forecast_feed(request: IncidentBatchRequest):
    """Package incident + weather + event data for the forecasting module.

    The forecasting team (Member 2/3) calls this endpoint to get a combined
    payload that includes:
      - Incident analysis (risk, clusters, distances)
      - Current weather conditions
      - Nearby public events

    This gives them everything needed to factor external intelligence into
    their patient-surge predictions.
    """
    try:
        incidents = [inc.model_dump() for inc in request.incidents]
        analysis = analyze_incidents(incidents)
        weather_data = await get_current_weather()
        weather_risk = evaluate_weather_risk(weather_data)
        events = await get_current_events()
        event_risk = evaluate_event_risk(events)

        return {
            "engine": "member4-incident-detection-engine",
            "is_simulated_demo": True,
            "analysis": analysis,
            "weather": {
                "observations": weather_data,
                "risk_assessment": weather_risk,
            },
            "events": {
                "data": events,
                "risk_assessment": event_risk,
            },
            "integration_notes": (
                "This payload combines incident analysis, weather, and event data. "
                "Use analysis.risk.risk_score as the primary surge signal. "
                "Weather and event risk assessments are supplementary context."
            ),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
