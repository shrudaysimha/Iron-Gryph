"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Hospital Surge AI"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-this-to-a-random-secret-key"

    # Database (defaults to SQLite; set DATABASE_URL in .env for PostgreSQL)
    database_url: str = "sqlite:///./hospital_surge.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # External APIs
    openweather_api_key: str = ""
    weather_city: str = "Bangalore"
    weather_country: str = "IN"

    # ML Model
    model_retrain_interval_hours: int = 24
    prediction_horizon_hours: int = 24

    # Alert Thresholds
    bed_occupancy_warning: float = 0.80
    bed_occupancy_critical: float = 0.90
    staff_ratio_min: float = 0.15
    ambulance_available_min: int = 2

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
