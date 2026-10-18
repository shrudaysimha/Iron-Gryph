"""Incident Detection Service — Bridge between the main backend and the Incident Detection Engine.

This service wraps Member 4's incident detection engine, providing a clean interface
for the main backend to analyse external incidents (accidents, weather events,
public gatherings) and assess their surge-risk impact on hospitals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.incident_detection_engine.app.config import settings as engine_settings
from app.incident_detection_engine.app.analysis_engine import analyze_incidents as _analyze
from app.incident_detection_engine.app.analysis_engine import analyze_file as _analyze_file
from app.incident_detection_engine.app.weather_service import (
    get_current_weather as _get_weather,
    evaluate_weather_risk as _evaluate_weather_risk,
)
from app.incident_detection_engine.app.event_service import (
    get_current_events as _get_events,
    enrich_events_with_distance as _enrich_events,
    evaluate_event_risk as _evaluate_event_risk,
)

logger = logging.getLogger("hospital_surge_ai.incident_detection")


class IncidentDetectionService:
    """Facade for the incident detection engine.

    All methods are designed to be called from API route handlers.
    Errors are caught and re-raised with descriptive messages.
    """

    def __init__(
        self,
        hospital_lat: float | None = None,
        hospital_lon: float | None = None,
    ):
        self.hospital_lat = hospital_lat or engine_settings.hospital_latitude
        self.hospital_lon = hospital_lon or engine_settings.hospital_longitude

    def analyze_incidents(self, incidents: list[dict[str, Any]]) -> dict[str, Any]:
        """Run the full analysis pipeline on a batch of incidents.

        Args:
            incidents: List of raw incident dicts matching the IncidentCreate schema.

        Returns:
            Complete analysis result including risk score, clusters, and alert.
        """
        return _analyze(incidents, self.hospital_lat, self.hospital_lon)

    def analyze_from_file(self, source: str = "json") -> dict[str, Any]:
        """Load incidents from a sample data file and run analysis.

        Args:
            source: "json" or "csv" — which sample file to load.
        """
        if source == "csv":
            path = Path(engine_settings.incidents_csv_path)
        else:
            path = Path(engine_settings.incidents_json_path)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        return _analyze_file(path, self.hospital_lat, self.hospital_lon)

    async def get_weather(self) -> dict[str, Any]:
        """Get current weather observations and risk assessment."""
        weather_data = await _get_weather()
        risk = _evaluate_weather_risk(weather_data)
        is_live = any(not w.get("is_simulated", True) for w in weather_data)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data_source": "LIVE_API" if is_live else "SIMULATED",
            "observations": weather_data,
            "risk_assessment": risk,
        }

    async def get_events(self) -> dict[str, Any]:
        """Get current public events and their surge-risk assessment."""
        events = await _get_events()
        enriched = _enrich_events(events)
        risk = _evaluate_event_risk(events)
        is_live = any(not e.get("is_simulated", True) for e in events)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data_source": "LIVE_API" if is_live else "SIMULATED",
            "events": enriched,
            "risk_assessment": risk,
        }

    async def get_dashboard_summary(self, source: str = "json") -> dict[str, Any]:
        """Unified dashboard payload combining incidents, weather, and events."""
        analysis = self.analyze_from_file(source)
        weather = await self.get_weather()
        events = await self.get_events()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "engine": analysis["engine"],
            "is_simulated_demo": analysis["is_simulated_demo"],
            "clinical_validation": analysis["clinical_validation"],
            "hospital": analysis["hospital"],
            "alert": analysis["alert"],
            "incidents": analysis["incidents"],
            "incident_count_total": analysis["incident_count_total"],
            "incident_count_scored": analysis["incident_count_scored"],
            "clusters": analysis["clusters"],
            "risk": analysis["risk"],
            "external_conditions": {
                "weather": weather,
                "events": events,
            },
        }

    async def get_forecast_feed(self, incidents: list[dict[str, Any]]) -> dict[str, Any]:
        """Combined payload for the forecasting module (Member 2/3 integration)."""
        analysis = self.analyze_incidents(incidents)
        weather = await self.get_weather()
        events = await self.get_events()

        return {
            "engine": "member4-incident-detection-engine",
            "is_simulated_demo": True,
            "analysis": analysis,
            "weather": weather,
            "events": events,
            "integration_notes": (
                "This payload combines incident analysis, weather, and event data. "
                "Use analysis.risk.risk_score as the primary surge signal. "
                "Weather and event risk assessments are supplementary context."
            ),
        }

    def get_engine_config(self) -> dict[str, Any]:
        """Return the current engine configuration."""
        return {
            "hospital": {
                "latitude": engine_settings.hospital_latitude,
                "longitude": engine_settings.hospital_longitude,
                "name": engine_settings.hospital_name,
            },
            "clustering": {
                "cluster_radius_km": engine_settings.cluster_radius_km,
                "cluster_window_minutes": engine_settings.cluster_window_minutes,
            },
            "scoring": {
                "nearby_radius_km": engine_settings.nearby_radius_km,
                "high_risk_threshold": engine_settings.high_risk_threshold,
                "moderate_risk_threshold": engine_settings.moderate_risk_threshold,
                "weights": {
                    "count": engine_settings.count_weight,
                    "severity": engine_settings.severity_weight,
                    "proximity": engine_settings.proximity_weight,
                    "weather": engine_settings.weather_weight,
                },
            },
            "data_sources": {
                "weather_api_configured": bool(engine_settings.weather_api_key),
                "events_api_configured": bool(engine_settings.events_api_key),
            },
        }
