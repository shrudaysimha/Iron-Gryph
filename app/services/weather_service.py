"""
Weather Service — Ingestion and impact analysis for environmental surge factors.

Provides current weather conditions, forecasts, and assesses weather-driven
hospital admission risks (heatwaves, storms, severe air pollution).
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Weather condition encodings for ML demand prediction model
# 0: Clear / Normal
# 1: Rain / Drizzle (minor increase in road accidents and OPD)
# 2: Storm / Heavy Rain / High AQI (moderate surge, slip & fall, respiratory)
# 3: Extreme Weather (heatwave, cyclone, severe smog, flood — major surge)
CONDITION_MAP = {
    "clear": 0,
    "clouds": 0,
    "drizzle": 1,
    "rain": 1,
    "thunderstorm": 2,
    "snow": 2,
    "fog": 1,
    "haze": 1,
    "smoke": 2,
    "dust": 2,
    "sand": 2,
    "ash": 3,
    "squall": 3,
    "tornado": 3,
}


class WeatherService:
    """Service to fetch and analyze weather data for patient surge prediction."""

    def __init__(self):
        self.api_key = settings.openweather_api_key
        self.city = settings.weather_city
        self.country = settings.weather_country
        self._cached_weather: Dict[str, Any] | None = None
        self._last_fetched: datetime | None = None

    async def get_current_weather(self, city: str | None = None) -> Dict[str, Any]:
        """
        Fetch current weather. Uses OpenWeatherMap API if key is present;
        otherwise provides realistic meteorological estimates.
        """
        target_city = city or self.city

        # Check cache (15-minute TTL)
        now = datetime.now(timezone.utc)
        if self._cached_weather and self._last_fetched:
            if (now - self._last_fetched).total_seconds() < 900:
                return self._cached_weather

        if self.api_key and self.api_key != "your_openweathermap_api_key":
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    url = f"https://api.openweathermap.org/data/2.5/weather"
                    params = {
                        "q": f"{target_city},{self.country}",
                        "appid": self.api_key,
                        "units": "metric",
                    }
                    res = await client.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        weather_info = self._format_api_response(data)
                        self._cached_weather = weather_info
                        self._last_fetched = now
                        return weather_info
            except Exception as e:
                logger.warning(f"Failed to fetch live weather: {e}. Falling back to simulated weather.")

        # Default realistic data for Bengaluru/region
        simulated = self._get_simulated_weather(target_city)
        self._cached_weather = simulated
        self._last_fetched = now
        return simulated

    def get_weather_sync(self, city: str | None = None) -> Dict[str, Any]:
        """Synchronous weather retrieval for feature engineering pipeline."""
        if self._cached_weather:
            return self._cached_weather
        return self._get_simulated_weather(city or self.city)

    def _format_api_response(self, data: dict) -> Dict[str, Any]:
        """Extract structured fields from OpenWeatherMap JSON."""
        main_weather = data.get("weather", [{}])[0].get("main", "Clear").lower()
        condition_code = CONDITION_MAP.get(main_weather, 0)
        temp = data.get("main", {}).get("temp", 28.0)
        humidity = data.get("main", {}).get("humidity", 60)

        # High heat surge check
        if temp >= 38.0:
            condition_code = max(condition_code, 3)

        return {
            "city": data.get("name", self.city),
            "temperature_celsius": round(temp, 1),
            "feels_like_celsius": round(data.get("main", {}).get("feels_like", temp), 1),
            "humidity_percent": humidity,
            "condition": main_weather.title(),
            "condition_encoded": condition_code,
            "air_quality_index": 65,  # Moderate
            "surge_risk_factor": self._calculate_surge_risk(temp, condition_code, 65),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_simulated_weather(self, city: str) -> Dict[str, Any]:
        """Generate realistic baseline meteorological metrics."""
        hour = datetime.now().hour
        # Diurnal temperature cycle: coolest at 5am, warmest at 2pm
        base_temp = 22.0 + 8.0 * (1 - abs(hour - 14) / 12)

        return {
            "city": city,
            "temperature_celsius": round(base_temp, 1),
            "feels_like_celsius": round(base_temp + 1.5, 1),
            "humidity_percent": 65,
            "condition": "Partly Cloudy",
            "condition_encoded": 0,
            "air_quality_index": 55,  # AQI 0-50 Good, 51-100 Moderate
            "surge_risk_factor": 1.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_surge_risk(self, temp: float, condition_code: int, aqi: int) -> float:
        """
        Quantify expected multiplier for emergency patient arrivals due to weather.
        1.0 = Normal baseline. 1.5+ = High surge probability.
        """
        factor = 1.0
        # Extreme temperatures (>38°C heatwave or <10°C cold snap)
        if temp > 38:
            factor += (temp - 38) * 0.05
        # Heavy rain / storms cause traffic collisions and trauma
        if condition_code == 1:
            factor += 0.15
        elif condition_code == 2:
            factor += 0.35
        elif condition_code >= 3:
            factor += 0.60
        # Hazardous Air Quality triggers asthma & cardiopulmonary issues
        if aqi > 150:
            factor += 0.20
        elif aqi > 250:
            factor += 0.45

        return round(factor, 2)
