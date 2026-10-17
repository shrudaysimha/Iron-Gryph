"""Feature engineering pipeline for the demand prediction model."""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.patient import Admission
from app.models.hospital import Ward
from app.models.ambulance import Ambulance
from app.services.weather_service import WeatherService
from app.services.event_service import EventService


class FeatureEngineer:
    """Extracts features from database state for ML model input."""

    def __init__(self, db: Session):
        self.db = db
        self.weather_service = WeatherService()
        self.event_service = EventService()

    def extract_features(self, hospital_id: int, target_time: datetime) -> dict:
        """
        Extract a feature dictionary for the prediction model.

        Features:
        - Temporal: hour, day of week, month, weekend/holiday flags
        - Historical: rolling averages of admissions
        - Real-time: current occupancy, emergency arrivals, ambulance dispatches
        - External: weather, events (placeholder for now)
        """
        now = datetime.now(timezone.utc)

        features = {}

        # ---- Temporal Features ----
        features["hour_of_day"] = target_time.hour
        features["day_of_week"] = target_time.weekday()  # 0=Monday
        features["month"] = target_time.month
        features["is_weekend"] = 1 if target_time.weekday() >= 5 else 0
        features["is_night"] = 1 if target_time.hour < 6 or target_time.hour >= 22 else 0

        # Holiday detection (simplified — Indian national holidays)
        features["is_holiday"] = self._is_holiday(target_time)

        # ---- Historical Admission Features ----
        features["rolling_avg_7d"] = self._rolling_avg_admissions(hospital_id, now, days=7)
        features["rolling_avg_24h"] = self._rolling_avg_admissions(hospital_id, now, days=1)
        features["rolling_avg_3d"] = self._rolling_avg_admissions(hospital_id, now, days=3)

        # Admissions in the last hour
        one_hour_ago = now - timedelta(hours=1)
        features["admissions_last_1h"] = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.admitted_at >= one_hour_ago,
            )
            .count()
        )

        # Emergency arrivals in last 4 hours
        four_hours_ago = now - timedelta(hours=4)
        features["emergency_arrivals_4h"] = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.department == "emergency",
                Admission.admitted_at >= four_hours_ago,
            )
            .count()
        )

        # ---- Current State Features ----
        wards = (
            self.db.query(Ward)
            .filter(Ward.hospital_id == hospital_id, Ward.is_active == True)  # noqa: E712
            .all()
        )
        total_beds = sum(w.total_beds for w in wards)
        available_beds = sum(w.available_beds for w in wards)
        features["occupancy_rate"] = (
            (total_beds - available_beds) / total_beds if total_beds > 0 else 0
        )
        features["available_beds"] = available_beds

        # ICU occupancy
        icu_wards = [w for w in wards if w.ward_type == "icu"]
        icu_total = sum(w.total_beds for w in icu_wards)
        icu_available = sum(w.available_beds for w in icu_wards)
        features["icu_occupancy_rate"] = (
            (icu_total - icu_available) / icu_total if icu_total > 0 else 0
        )

        # ---- Ambulance Features ----
        ambulances = (
            self.db.query(Ambulance)
            .filter(Ambulance.hospital_id == hospital_id)
            .all()
        )
        features["ambulances_dispatched"] = len(
            [a for a in ambulances if a.status in ("dispatched", "en_route", "at_scene")]
        )
        features["ambulances_available"] = len(
            [a for a in ambulances if a.status == "available"]
        )

        # ---- Severity Distribution (last 24h) ----
        recent_admissions = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.admitted_at >= now - timedelta(hours=24),
            )
            .all()
        )
        total_recent = len(recent_admissions)
        features["critical_ratio_24h"] = (
            len([a for a in recent_admissions if a.severity == "critical"]) / total_recent
            if total_recent > 0
            else 0
        )
        features["severe_ratio_24h"] = (
            len([a for a in recent_admissions if a.severity == "severe"]) / total_recent
            if total_recent > 0
            else 0
        )

        # ---- External Features (Weather & Local Events) ----
        try:
            weather = self.weather_service.get_weather_sync()
            features["weather_temperature"] = weather.get("temperature_celsius", 28.0)
            features["weather_condition_encoded"] = weather.get("condition_encoded", 0)
            features["air_quality_index"] = weather.get("air_quality_index", 50)
        except Exception:
            features["weather_temperature"] = 28.0
            features["weather_condition_encoded"] = 0
            features["air_quality_index"] = 50

        try:
            event_data = self.event_service.get_events_for_hospital(hospital_id)
            features["local_event_flag"] = event_data.get("has_local_event", 0)
            features["local_event_size"] = event_data.get("max_event_size", 0)
            features["nearby_accident_flag"] = event_data.get("has_nearby_accident", 0)
        except Exception:
            features["local_event_flag"] = 0
            features["local_event_size"] = 0
            features["nearby_accident_flag"] = 0

        return features

    def _rolling_avg_admissions(self, hospital_id: int, now: datetime, days: int) -> float:
        """Calculate rolling average of daily admissions over N days."""
        cutoff = now - timedelta(days=days)
        count = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.admitted_at >= cutoff,
            )
            .count()
        )
        return count / days if days > 0 else 0

    def _is_holiday(self, dt: datetime) -> int:
        """Check if a date is an Indian national holiday (simplified)."""
        holidays = [
            (1, 26),   # Republic Day
            (3, 29),   # Holi (approximate)
            (8, 15),   # Independence Day
            (10, 2),   # Gandhi Jayanti
            (10, 24),  # Dussehra (approximate)
            (11, 12),  # Diwali (approximate)
            (12, 25),  # Christmas
        ]
        return 1 if (dt.month, dt.day) in holidays else 0
