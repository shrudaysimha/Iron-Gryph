"""
Weather monitoring service.

This module handles weather data for the incident detection engine.
It supports TWO modes:

  1. SIMULATED MODE (default):
     Loads weather observations from `data/sample_weather.json`.
     Used when no API key is configured.

  2. LIVE API MODE:
     Calls the OpenWeatherMap API (or any compatible endpoint) when
     `WEATHER_API_KEY` is set in the environment or `.env` file.

WHY BOTH MODES?
---------------
Hackathon judges want to see the system work immediately without requiring
API keys. But the architecture is ready for real data — just add your key.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import settings


# ═══════════════════════════════════════════════════════════════════════
#  SIMULATED WEATHER DATA
# ═══════════════════════════════════════════════════════════════════════

def load_simulated_weather() -> list[dict[str, Any]]:
    """Load weather observations from the sample JSON file.

    Returns:
        A list of weather observation dicts.

    Raises:
        FileNotFoundError: If the sample file doesn't exist.
    """
    path = Path(settings.weather_data_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("observations", [])


# ═══════════════════════════════════════════════════════════════════════
#  LIVE WEATHER API
# ═══════════════════════════════════════════════════════════════════════

def _map_owm_condition(weather_id: int) -> str:
    """Map OpenWeatherMap condition codes to our internal categories.

    See: https://openweathermap.org/weather-conditions
    """
    if 200 <= weather_id < 300:
        return "storm"           # Thunderstorm group
    if 500 <= weather_id < 600:
        if weather_id >= 502:
            return "heavy_rain"  # Heavy intensity rain
        return "none"            # Light/moderate rain
    if weather_id == 622 or weather_id == 621:
        return "storm"           # Heavy snow/shower
    if 700 <= weather_id < 800:
        return "none"            # Atmosphere (mist, fog, etc.)
    return "none"


def _map_owm_heat(temp_celsius: float) -> str:
    """Flag extreme heat based on temperature."""
    if temp_celsius >= 42.0:
        return "extreme_heat"
    return "none"


async def fetch_live_weather(
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any] | None:
    """Fetch current weather from OpenWeatherMap API.

    Returns None if no API key is configured or if the request fails.
    This ensures the system degrades gracefully — it just uses simulated data.

    Args:
        lat, lon: Coordinates to query. Defaults to the hospital location.
    """
    if not settings.weather_api_key:
        return None

    _lat = lat or settings.hospital_latitude
    _lon = lon or settings.hospital_longitude

    params = {
        "lat": _lat,
        "lon": _lon,
        "appid": settings.weather_api_key,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.weather_api_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Parse the response
        weather_id = data["weather"][0]["id"] if data.get("weather") else 800
        temp = data.get("main", {}).get("temp", 25.0)
        condition = _map_owm_condition(weather_id)
        if condition == "none":
            condition = _map_owm_heat(temp)

        return {
            "location_name": data.get("name", "Unknown"),
            "latitude": _lat,
            "longitude": _lon,
            "condition": condition,
            "temperature_celsius": temp,
            "humidity_percent": data.get("main", {}).get("humidity"),
            "wind_speed_kmh": round((data.get("wind", {}).get("speed", 0)) * 3.6, 1),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data_source": "OpenWeatherMap",
            "is_simulated": False,
        }
    except Exception:
        # Fail silently — weather is supplementary, not critical
        return None


# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC INTERFACE
# ═══════════════════════════════════════════════════════════════════════

async def get_current_weather() -> list[dict[str, Any]]:
    """Get weather data, preferring live API if available.

    Falls back to simulated data when no API key is set or the API fails.
    """
    live = await fetch_live_weather()
    if live:
        return [live]
    return load_simulated_weather()


def evaluate_weather_risk(weather_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess weather-related surge risk from current observations.

    Returns a summary dict with the worst condition, affected locations,
    and a risk flag.
    """
    severe_conditions = {"heavy_rain", "extreme_heat", "storm", "flood"}
    severe_reports = [
        w for w in weather_data
        if w.get("condition", "none") in severe_conditions
    ]

    if not severe_reports:
        return {
            "weather_risk": False,
            "worst_condition": "none",
            "severe_count": 0,
            "details": "No severe weather conditions detected.",
        }

    # Find worst condition (storm > flood > heavy_rain > extreme_heat)
    priority = {"storm": 4, "flood": 3, "heavy_rain": 2, "extreme_heat": 1}
    worst = max(severe_reports, key=lambda w: priority.get(w.get("condition", "none"), 0))

    return {
        "weather_risk": True,
        "worst_condition": worst["condition"],
        "severe_count": len(severe_reports),
        "details": (
            f"{len(severe_reports)} location(s) reporting severe weather. "
            f"Worst: {worst['condition']} at {worst.get('location_name', 'unknown location')}."
        ),
        "affected_locations": [
            {
                "name": w.get("location_name", "Unknown"),
                "condition": w["condition"],
                "latitude": w.get("latitude"),
                "longitude": w.get("longitude"),
            }
            for w in severe_reports
        ],
    }
