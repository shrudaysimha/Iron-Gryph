"""
Unit tests for incident data processing.

Tests cover:
  - Timestamp parsing (ISO-8601, Z suffix, timezone-naive).
  - Validation (required fields, ranges, types).
  - File loading (CSV and JSON).
  - Distance enrichment.
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.data_processing import (
    enrich_with_distance,
    incidents_to_dataframe,
    load_incidents_from_file,
    parse_timestamp,
    validate_incident,
)


# ── Helper: build a valid incident dict ────────────────────────────────

def make_incident(**overrides) -> dict:
    """Create a valid incident dict with optional field overrides."""
    base = {
        "incident_id": "INC-TEST",
        "incident_type": "road_accident",
        "latitude": 12.975,
        "longitude": 77.600,
        "timestamp": "2026-10-17T18:10:00Z",
        "severity": 3,
        "data_source": "SIMULATED_TEST",
        "weather_condition": "none",
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════
#  TIMESTAMP PARSING
# ═══════════════════════════════════════════════════════════════════════

class TestParseTimestamp:
    def test_z_suffix(self):
        dt = parse_timestamp("2026-10-17T18:10:00Z")
        assert dt.tzinfo is not None
        assert dt.year == 2026

    def test_offset_string(self):
        dt = parse_timestamp("2026-10-17T23:40:00+05:30")
        assert dt.tzinfo is not None

    def test_naive_assumed_utc(self):
        dt = parse_timestamp("2026-10-17T18:10:00")
        assert dt.tzinfo == timezone.utc

    def test_datetime_object(self):
        now = datetime.now(timezone.utc)
        assert parse_timestamp(now) == now

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Invalid ISO-8601"):
            parse_timestamp("not-a-date")


# ═══════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════

class TestValidateIncident:
    def test_valid_incident_passes(self):
        result = validate_incident(make_incident())
        assert result["incident_id"] == "INC-TEST"
        assert isinstance(result["timestamp"], datetime)

    def test_missing_field_raises(self):
        bad = make_incident()
        del bad["incident_id"]
        with pytest.raises(ValueError, match="missing required fields"):
            validate_incident(bad)

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_incident(make_incident(incident_id="   "))

    def test_latitude_out_of_range(self):
        with pytest.raises(ValueError, match="Latitude out of range"):
            validate_incident(make_incident(latitude=91.0))

    def test_longitude_out_of_range(self):
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_incident(make_incident(longitude=181.0))

    def test_severity_too_high(self):
        with pytest.raises(ValueError, match="must be between 1 and 5"):
            validate_incident(make_incident(severity=6))

    def test_severity_too_low(self):
        with pytest.raises(ValueError, match="must be between 1 and 5"):
            validate_incident(make_incident(severity=0))

    def test_weather_normalised_to_lowercase(self):
        result = validate_incident(make_incident(weather_condition="HEAVY_RAIN"))
        assert result["weather_condition"] == "heavy_rain"

    def test_default_weather_is_none(self):
        inc = make_incident()
        del inc["weather_condition"]
        result = validate_incident(inc)
        assert result["weather_condition"] == "none"


# ═══════════════════════════════════════════════════════════════════════
#  FILE LOADING
# ═══════════════════════════════════════════════════════════════════════

class TestLoadIncidentsFromFile:
    def test_load_json_list(self, tmp_path):
        path = tmp_path / "incidents.json"
        path.write_text(json.dumps([make_incident()]), encoding="utf-8")
        result = load_incidents_from_file(path)
        assert len(result) == 1

    def test_load_json_wrapper(self, tmp_path):
        path = tmp_path / "incidents.json"
        path.write_text(json.dumps({"incidents": [make_incident()]}), encoding="utf-8")
        result = load_incidents_from_file(path)
        assert len(result) == 1

    def test_load_csv(self, tmp_path):
        path = tmp_path / "incidents.csv"
        path.write_text(
            "incident_id,incident_type,latitude,longitude,timestamp,severity,data_source\n"
            "INC-1,road_accident,12.975,77.600,2026-10-17T18:10:00Z,3,SIMULATED\n",
            encoding="utf-8",
        )
        result = load_incidents_from_file(path)
        assert len(result) == 1

    def test_duplicate_ids_rejected(self, tmp_path):
        path = tmp_path / "incidents.json"
        path.write_text(
            json.dumps([make_incident(), make_incident()]),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unique"):
            load_incidents_from_file(path)

    def test_unsupported_format(self, tmp_path):
        path = tmp_path / "data.xml"
        path.write_text("<data/>")
        with pytest.raises(ValueError, match="Unsupported"):
            load_incidents_from_file(path)

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_incidents_from_file("/nonexistent/file.json")


# ═══════════════════════════════════════════════════════════════════════
#  ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════

class TestEnrichWithDistance:
    def test_adds_distance_field(self):
        incidents = [validate_incident(make_incident())]
        enriched = enrich_with_distance(incidents, 12.9716, 77.5946)
        assert "distance_km" in enriched[0]
        assert enriched[0]["distance_km"] > 0

    def test_same_location_distance_zero(self):
        inc = validate_incident(make_incident(latitude=12.9716, longitude=77.5946))
        enriched = enrich_with_distance([inc], 12.9716, 77.5946)
        assert enriched[0]["distance_km"] == 0.0


class TestIncidentsToDataframe:
    def test_returns_dataframe(self):
        incidents = [validate_incident(make_incident())]
        df = incidents_to_dataframe(incidents)
        assert len(df) == 1
        assert "incident_id" in df.columns
