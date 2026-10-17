"""
Event Service — Local events, mass gatherings, and major accident detection.

Tracks scheduled local gatherings (cricket matches, festivals, marathons)
and unpredicted civil or industrial emergencies (highway collisions, fires).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class EventService:
    """Manages active local events and emergency accident flags near hospitals."""

    def __init__(self):
        # In-memory registry of current/upcoming local events
        # In production this would query an external events API or emergency dispatch feed
        self._active_events: List[Dict[str, Any]] = [
            {
                "id": "EVT-101",
                "name": "Chinnaswamy Stadium Cricket Match",
                "type": "sports",
                "expected_attendance": 35000,
                "radius_km": 5.0,
                "risk_level": "medium",
                "start_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "impact_multiplier": 1.25,
            },
            {
                "id": "EVT-102",
                "name": "Tech Expo & Convention",
                "type": "conference",
                "expected_attendance": 12000,
                "radius_km": 8.0,
                "risk_level": "low",
                "start_time": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
                "impact_multiplier": 1.05,
            },
        ]

        self._active_accidents: List[Dict[str, Any]] = [
            {
                "id": "INC-809",
                "title": "Outer Ring Road Multi-Vehicle Collision",
                "severity": "severe",
                "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat(),
                "estimated_casualties": 8,
                "is_active": True,
            }
        ]

    def get_events_for_hospital(self, hospital_id: int) -> Dict[str, Any]:
        """
        Evaluate nearby events affecting a specific hospital.
        Returns event flag, highest attendance size, and combined surge multiplier.
        """
        active_count = len(self._active_events)
        max_size = max([e["expected_attendance"] for e in self._active_events], default=0)
        has_accident = any(a["is_active"] for a in self._active_accidents)

        surge_factor = 1.0
        for event in self._active_events:
            surge_factor = max(surge_factor, event.get("impact_multiplier", 1.0))

        if has_accident:
            surge_factor += 0.25

        return {
            "has_local_event": 1 if active_count > 0 else 0,
            "event_count": active_count,
            "max_event_size": max_size,
            "has_nearby_accident": 1 if has_accident else 0,
            "active_events": self._active_events,
            "active_incidents": self._active_accidents,
            "event_surge_multiplier": round(surge_factor, 2),
        }

    def register_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new mass event."""
        event_id = f"EVT-{len(self._active_events) + 101}"
        new_event = {
            "id": event_id,
            "name": event_data.get("name", "Local Mass Event"),
            "type": event_data.get("type", "festival"),
            "expected_attendance": event_data.get("expected_attendance", 5000),
            "radius_km": event_data.get("radius_km", 5.0),
            "risk_level": event_data.get("risk_level", "medium"),
            "start_time": event_data.get("start_time", datetime.now(timezone.utc).isoformat()),
            "end_time": event_data.get("end_time", (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()),
            "impact_multiplier": event_data.get("impact_multiplier", 1.2),
        }
        self._active_events.append(new_event)
        return new_event

    def report_emergency_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Report a major accident or incident in the coverage zone."""
        inc_id = f"INC-{len(self._active_accidents) + 810}"
        incident = {
            "id": inc_id,
            "title": incident_data.get("title", "Mass Casualty Incident"),
            "severity": incident_data.get("severity", "critical"),
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "estimated_casualties": incident_data.get("estimated_casualties", 5),
            "is_active": True,
        }
        self._active_accidents.append(incident)
        return incident
