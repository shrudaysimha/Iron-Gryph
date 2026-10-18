"""
Incident data loading and processing with pandas.

This module is responsible for:
  1. Loading incident records from CSV or JSON files.
  2. Validating every record (types, ranges, required fields).
  3. Enriching records with distance-to-hospital calculations.
  4. Converting raw data into a clean pandas DataFrame for analysis.

WHY PANDAS?
-----------
For a small demo dataset, plain Python dicts work fine. But when the system
scales to hundreds or thousands of real incidents (police feeds, 911 data),
pandas gives us:
  - Vectorised operations (fast filtering, aggregation).
  - Easy CSV/JSON I/O with dtype enforcement.
  - Built-in time-series handling for timestamp columns.
  - Simple integration with visualisation and ML libraries later.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import settings
from .geo_utils import calculate_distance_km


# ═══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

REQUIRED_FIELDS = {
    "incident_id", "incident_type", "latitude", "longitude",
    "timestamp", "severity", "data_source",
}

VALID_WEATHER_CONDITIONS = {
    "none", "clear", "heavy_rain", "extreme_heat", "storm", "flood",
}


# ═══════════════════════════════════════════════════════════════════════
#  TIMESTAMP PARSING
# ═══════════════════════════════════════════════════════════════════════

def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime.

    Rules:
      - If the string ends with 'Z', replace it with '+00:00' (Python needs this).
      - If no timezone info is present, assume UTC.

    Args:
        value: A datetime object or an ISO-8601 string.

    Returns:
        A timezone-aware datetime in UTC.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════

def validate_incident(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a single incident record.

    Checks:
      - All required fields are present.
      - Latitude/longitude are valid numbers within range.
      - Severity is an integer between 1 and 5.
      - Timestamp is a parseable ISO-8601 string.
      - Weather condition is normalised to lowercase.

    Returns:
        A cleaned copy of the record (original is not mutated).

    Raises:
        ValueError: With a descriptive message if any check fails.
    """
    missing = REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Incident is missing required fields: {', '.join(sorted(missing))}")

    item = dict(raw)  # work on a copy

    # Normalise strings
    item["incident_id"] = str(item["incident_id"]).strip()
    item["incident_type"] = str(item["incident_type"]).strip().lower()
    item["data_source"] = str(item["data_source"]).strip()
    if not item["incident_id"] or not item["incident_type"] or not item["data_source"]:
        raise ValueError("incident_id, incident_type, and data_source cannot be empty.")

    # Numeric validation
    try:
        item["latitude"] = float(item["latitude"])
        item["longitude"] = float(item["longitude"])
        item["severity"] = int(item["severity"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "latitude/longitude must be numbers and severity must be an integer 1–5."
        ) from exc

    if not -90 <= item["latitude"] <= 90:
        raise ValueError(f"Latitude out of range for incident {item['incident_id']}.")
    if not -180 <= item["longitude"] <= 180:
        raise ValueError(f"Longitude out of range for incident {item['incident_id']}.")
    if not 1 <= item["severity"] <= 5:
        raise ValueError(f"Severity for incident {item['incident_id']} must be between 1 and 5.")

    # Timestamp
    item["timestamp"] = parse_timestamp(item["timestamp"])

    # Weather (optional field)
    item["weather_condition"] = str(item.get("weather_condition", "none")).strip().lower()

    return item


# ═══════════════════════════════════════════════════════════════════════
#  FILE LOADING
# ═══════════════════════════════════════════════════════════════════════

def load_incidents_from_file(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate incidents from a CSV or JSON file.

    Supports:
      - JSON: either a plain list `[{...}, ...]` or `{"incidents": [{...}, ...]}`.
      - CSV: standard header row with the required column names.

    Returns:
        A list of validated incident dicts.

    Raises:
        ValueError: If the file format is unsupported or data is invalid.
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Incident file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, encoding="utf-8-sig")
        records = df.to_dict(orient="records")
    elif suffix == ".json":
        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        records = payload.get("incidents", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("JSON must be a list of incidents or {\"incidents\": [...]}.")
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Use .csv or .json.")

    # Validate every record
    incidents = [validate_incident(record) for record in records]

    # Check for duplicate IDs
    ids = [x["incident_id"] for x in incidents]
    if len(ids) != len(set(ids)):
        raise ValueError("incident_id values must be unique within an input file.")

    return incidents


def incidents_to_dataframe(incidents: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert a list of validated incident dicts into a pandas DataFrame.

    This is useful for bulk analysis, filtering, and aggregation.
    """
    df = pd.DataFrame(incidents)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def enrich_with_distance(
    incidents: list[dict[str, Any]],
    hospital_lat: float | None = None,
    hospital_lon: float | None = None,
) -> list[dict[str, Any]]:
    """Add a `distance_km` field to each incident, measuring distance to the hospital.

    Uses the configurable hospital location from settings if not provided.
    """
    lat = hospital_lat if hospital_lat is not None else settings.hospital_latitude
    lon = hospital_lon if hospital_lon is not None else settings.hospital_longitude

    enriched = []
    for item in incidents:
        row = dict(item)
        row["distance_km"] = calculate_distance_km(
            row["latitude"], row["longitude"], lat, lon,
        )
        enriched.append(row)
    return enriched
