"""
Event monitoring service.

This module tracks public events and gatherings that could cause surges in
hospital emergency visits (concerts, sports, protests, festivals, etc.).

Like the weather service, it supports:
  1. SIMULATED MODE — loads from `data/sample_events.json` (default).
  2. LIVE API MODE — ready for integration when an events API is available.

RISK LOGIC
----------
Large public gatherings increase the probability of:
  - Crowd crushes, stampedes
  - Heat exhaustion (outdoor events in summer)
  - Alcohol-related injuries
  - Traffic accidents near venues

The proximity of an event to the hospital matters — nearby events will send
patients to THIS hospital specifically.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .geo_utils import calculate_distance_km


# ═══════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════

def load_simulated_events() -> list[dict[str, Any]]:
    """Load public events from the sample JSON file."""
    path = Path(settings.events_data_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("events", [])


# ═══════════════════════════════════════════════════════════════════════
#  RISK ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════

def enrich_events_with_distance(
    events: list[dict[str, Any]],
    hospital_lat: float | None = None,
    hospital_lon: float | None = None,
) -> list[dict[str, Any]]:
    """Add distance_to_hospital_km to each event."""
    lat = hospital_lat or settings.hospital_latitude
    lon = hospital_lon or settings.hospital_longitude

    enriched = []
    for event in events:
        e = dict(event)
        e["distance_to_hospital_km"] = calculate_distance_km(
            e["latitude"], e["longitude"], lat, lon,
        )
        enriched.append(e)
    return enriched


def evaluate_event_risk(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess surge risk from public events.

    Events within the nearby radius with large attendance increase risk.

    Returns a summary with nearby events, total expected attendance,
    and a risk flag.
    """
    nearby_radius = settings.nearby_radius_km
    enriched = enrich_events_with_distance(events)

    nearby_events = [
        e for e in enriched
        if e.get("distance_to_hospital_km", 999) <= nearby_radius
    ]

    if not nearby_events:
        return {
            "event_risk": False,
            "nearby_event_count": 0,
            "total_expected_attendance": 0,
            "details": "No public events detected within the monitoring radius.",
            "nearby_events": [],
        }

    total_attendance = sum(
        e.get("expected_attendance", 0) or 0 for e in nearby_events
    )

    # High-risk event types
    high_risk_types = {"protest", "sports", "concert", "festival"}
    high_risk_nearby = [
        e for e in nearby_events
        if e.get("event_type", "").lower() in high_risk_types
    ]

    return {
        "event_risk": bool(nearby_events),
        "nearby_event_count": len(nearby_events),
        "total_expected_attendance": total_attendance,
        "high_risk_event_count": len(high_risk_nearby),
        "details": (
            f"{len(nearby_events)} public event(s) within {nearby_radius} km. "
            f"Total expected attendance: {total_attendance:,}. "
            f"{len(high_risk_nearby)} high-risk type event(s)."
        ),
        "nearby_events": [
            {
                "event_id": e.get("event_id"),
                "event_name": e.get("event_name"),
                "event_type": e.get("event_type"),
                "expected_attendance": e.get("expected_attendance"),
                "distance_km": e.get("distance_to_hospital_km"),
            }
            for e in nearby_events
        ],
    }


async def get_current_events() -> list[dict[str, Any]]:
    """Get event data. Currently loads simulated data.

    When a live events API becomes available, add an async HTTP call here
    similar to weather_service.fetch_live_weather().
    """
    return load_simulated_events()
