"""
Centralised configuration for the Incident Detection Engine.

WHY A SEPARATE CONFIG FILE?
----------------------------
Keeping all tuneable values (hospital location, thresholds, API keys, file
paths) in one place means:
  - No magic numbers scattered across the codebase.
  - Team members can adjust behaviour WITHOUT reading or editing core logic.
  - Environment-variable overrides (via pydantic-settings) let you change
    settings per deployment without touching code at all.

HOW IT WORKS
------------
pydantic-settings reads values in this priority order:
  1. Values you pass explicitly in code   (highest priority)
  2. Environment variables                (e.g. HOSPITAL_LATITUDE=13.0)
  3. A `.env` file in the project root    (loaded automatically)
  4. The default values written below      (lowest priority)

To override ANY setting, just set the matching environment variable.
Example:
    export HOSPITAL_LATITUDE=19.0760
    export HOSPITAL_LONGITUDE=72.8777
    export HIGH_RISK_THRESHOLD=80
    python -m uvicorn app.main:app
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENGINE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configurable parameters for the engine.

    Every field has a sensible default so the app runs out-of-the-box.
    Override via environment variables or a `.env` file.
    """

    # ── Hospital Location (Bengaluru demo default) ──────────────────────
    hospital_latitude: float = 12.9716
    hospital_longitude: float = 77.5946
    hospital_name: str = "Demo Hospital — Bengaluru"

    # ── Clustering Parameters ───────────────────────────────────────────
    # Two incidents are "linked" if they are within BOTH these limits.
    cluster_radius_km: float = 5.0          # max distance between linked incidents
    cluster_window_minutes: int = 120        # max time gap (minutes) between linked incidents

    # ── Scoring Parameters ──────────────────────────────────────────────
    nearby_radius_km: float = 15.0           # only incidents within this radius affect score
    high_risk_threshold: float = 70.0        # score >= this → HIGH alert
    moderate_risk_threshold: float = 35.0    # score >= this (and < high) → MODERATE alert

    # Weights for scoring formula (should sum to 100 for easy interpretation)
    count_weight: float = 35.0
    severity_weight: float = 30.0
    proximity_weight: float = 20.0
    weather_weight: float = 15.0

    # ── Data File Paths ─────────────────────────────────────────────────
    incidents_csv_path: str = str(_ENGINE_DIR / "data" / "sample_incidents.csv")
    incidents_json_path: str = str(_ENGINE_DIR / "data" / "sample_incidents.json")
    weather_data_path: str = str(_ENGINE_DIR / "data" / "sample_weather.json")
    events_data_path: str = str(_ENGINE_DIR / "data" / "sample_events.json")

    # ── External API Keys (optional — leave blank to use simulated data) ─
    weather_api_key: str = ""
    weather_api_url: str = "https://api.openweathermap.org/data/2.5/weather"
    events_api_key: str = ""
    events_api_url: str = ""

    # ── Server & CORS ───────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=str(_ENGINE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton instance — import this everywhere instead of creating new Settings()
settings = Settings()
