"""
Risk scoring and alert generation.

SCORING FORMULA
---------------
The risk score is a weighted sum of four signals, each normalised to 0–1:

  score = count_weight   × count_factor
        + severity_weight × severity_factor
        + proximity_weight × proximity_factor
        + weather_weight  × weather_factor

Default weights sum to 100, so the score is directly interpretable as a
percentage. Each factor is explained below:

  count_factor    = min(incident_count / 3, 1.0)
                    → 1 incident = 0.33, 2 = 0.67, 3+ = 1.0.

  severity_factor = (average_severity - 1) / 4
                    → Maps severity 1–5 to the 0–1 range.

  proximity_factor = clamp(1 - nearest_km / nearby_radius_km, 0, 1)
                    → Incident AT the hospital = 1.0; at the radius edge = 0.0.

  weather_factor   = 1.0 if any scored incident has severe weather, else 0.0.
                    → Binary signal; heavy rain / storm / flood increases risk.

RISK CATEGORIES
---------------
  HIGH     : score ≥ high_risk_threshold     (default 70)
  MODERATE : score ≥ moderate_risk_threshold  (default 35)
  LOW      : score < moderate_risk_threshold

DISCLAIMER: These rules are illustrative heuristics for a hackathon demo,
NOT clinically validated predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import settings


# Weather conditions that increase risk
SEVERE_WEATHER_CONDITIONS = {"heavy_rain", "extreme_heat", "storm", "flood"}


def score_risk(
    incidents: list[dict[str, Any]],
    nearby_radius_km: float | None = None,
    count_weight: float | None = None,
    severity_weight: float | None = None,
    proximity_weight: float | None = None,
    weather_weight: float | None = None,
    high_threshold: float | None = None,
    moderate_threshold: float | None = None,
) -> dict[str, Any]:
    """Compute the surge-risk score for a set of incidents.

    All parameters fall back to `settings` defaults if not provided.

    Args:
        incidents: Enriched incident dicts (must have 'distance_km', 'severity',
                   'weather_condition').

    Returns:
        A dict with: risk_score, risk_category, reasons (human-readable list),
        and factors (numeric breakdown).
    """
    # Fall back to settings
    _nearby = nearby_radius_km or settings.nearby_radius_km
    _cw = count_weight or settings.count_weight
    _sw = severity_weight or settings.severity_weight
    _pw = proximity_weight or settings.proximity_weight
    _ww = weather_weight or settings.weather_weight
    _high = high_threshold or settings.high_risk_threshold
    _mod = moderate_threshold or settings.moderate_risk_threshold

    if not incidents:
        return {
            "risk_score": 0.0,
            "risk_category": "LOW",
            "reasons": ["No incidents were supplied."],
            "factors": {
                "incident_count": 0,
                "count_factor": 0.0,
                "average_severity": 0.0,
                "nearest_distance_km": 0.0,
                "weather_signal_present": False,
            },
        }

    count = len(incidents)

    # ── Factor 1: Incident count ────────────────────────────────────
    count_factor = min(count / 3.0, 1.0)

    # ── Factor 2: Average severity ──────────────────────────────────
    avg_severity = sum(x["severity"] for x in incidents) / count
    severity_factor = (avg_severity - 1) / 4

    # ── Factor 3: Proximity (nearest incident) ──────────────────────
    nearest_km = min(x["distance_km"] for x in incidents)
    proximity_factor = max(0.0, min(1.0, 1 - nearest_km / _nearby))

    # ── Factor 4: Weather ───────────────────────────────────────────
    weather_present = any(
        x.get("weather_condition", "none") in SEVERE_WEATHER_CONDITIONS
        for x in incidents
    )
    weather_factor = 1.0 if weather_present else 0.0

    # ── Weighted sum ────────────────────────────────────────────────
    score = (
        _cw * count_factor
        + _sw * severity_factor
        + _pw * proximity_factor
        + _ww * weather_factor
    )
    score = round(max(0.0, min(100.0, score)), 1)

    # ── Category ────────────────────────────────────────────────────
    if score >= _high:
        category = "HIGH"
    elif score >= _mod:
        category = "MODERATE"
    else:
        category = "LOW"

    # ── Human-readable reasons ──────────────────────────────────────
    reasons = [
        f"{count} incident(s) considered (count contribution: {_cw * count_factor:.1f}/{_cw:.1f}).",
        f"Average severity is {avg_severity:.1f}/5 (severity contribution: {_sw * severity_factor:.1f}/{_sw:.1f}).",
        f"Nearest incident is {nearest_km:.2f} km away (proximity contribution: {_pw * proximity_factor:.1f}/{_pw:.1f}).",
        f"Relevant weather signal {'present' if weather_present else 'not present'} (weather contribution: {_ww * weather_factor:.1f}/{_ww:.1f}).",
    ]

    return {
        "risk_score": score,
        "risk_category": category,
        "reasons": reasons,
        "factors": {
            "incident_count": count,
            "count_factor": round(count_factor, 3),
            "average_severity": round(avg_severity, 2),
            "nearest_distance_km": round(nearest_km, 2),
            "weather_signal_present": weather_present,
        },
    }


def generate_alert(
    risk: dict[str, Any],
    clusters: list[list[str]],
    incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured alert from risk assessment results.

    This is the payload that gets sent to the frontend dashboard and the
    forecasting module. It includes everything they need to display an
    alert card and factor it into their predictions.

    Returns:
        A dict matching the AlertResponse schema.
    """
    factors = risk.get("factors", {})

    # Build the human-readable alert message
    cluster_summary = (
        f"Detected {len(clusters)} nearby cluster(s)."
        if clusters
        else "No incident clusters detected."
    )
    message = (
        f"{risk['risk_category']} potential surge-risk alert "
        f"(demo score {risk['risk_score']}/100). "
        + " ".join(risk["reasons"])
        + f" {cluster_summary}"
        + " This is a simulated operational heuristic, not a clinically validated prediction."
    )

    return {
        "alert_id": f"ALERT-{uuid4().hex[:8].upper()}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "risk_category": risk["risk_category"],
        "risk_score": risk["risk_score"],
        "alert_message": message,
        "incident_count": factors.get("incident_count", 0),
        "nearest_incident_km": factors.get("nearest_distance_km", 0.0),
        "weather_active": factors.get("weather_signal_present", False),
        "cluster_count": len(clusters),
        "hospital": {
            "latitude": settings.hospital_latitude,
            "longitude": settings.hospital_longitude,
            "name": settings.hospital_name,
        },
    }
