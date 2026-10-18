"""
Central analysis engine — the orchestrator.

This module ties together ALL the components:
  data_processing → clustering → risk_scoring → alert generation

It provides two entry points:
  1. `analyze_incidents()` — for programmatic use (called by API routes).
  2. `analyze_file()`     — for CLI / file-based analysis.

Think of this as the "brain" that coordinates the "eyes" (weather, events,
incident data) and the "mouth" (alerts, API responses).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .clustering import assign_cluster_ids, build_clusters
from .config import settings
from .data_processing import (
    enrich_with_distance,
    load_incidents_from_file,
    parse_timestamp,
    validate_incident,
)
from .risk_scoring import generate_alert, score_risk


def analyze_incidents(
    raw_incidents: Iterable[dict[str, Any]],
    hospital_lat: float | None = None,
    hospital_lon: float | None = None,
) -> dict[str, Any]:
    """Run the full analysis pipeline on a batch of incidents.

    Steps:
      1. Validate every incident record.
      2. Compute distance from each incident to the hospital.
      3. Cluster nearby incidents by space + time.
      4. Score surge risk using only incidents within the nearby radius.
      5. Generate a human-readable alert.

    Args:
        raw_incidents: Iterable of raw incident dicts (from API, file, etc.).
        hospital_lat, hospital_lon: Override hospital location (defaults to settings).

    Returns:
        A complete analysis result dict matching the AnalysisResponse schema.
    """
    h_lat = hospital_lat if hospital_lat is not None else settings.hospital_latitude
    h_lon = hospital_lon if hospital_lon is not None else settings.hospital_longitude

    # Step 1: Validate
    incidents = [validate_incident(dict(x)) for x in raw_incidents]
    ids = [x["incident_id"] for x in incidents]
    if len(ids) != len(set(ids)):
        raise ValueError("incident_id values must be unique within an analysis batch.")

    # Step 2: Enrich with distance
    enriched = enrich_with_distance(incidents, h_lat, h_lon)

    # Step 3: Serialise timestamps for output, but keep datetime for clustering
    for row in enriched:
        if hasattr(row["timestamp"], "isoformat"):
            row["timestamp"] = row["timestamp"].isoformat().replace("+00:00", "Z")

    # Step 4: Cluster (needs datetime objects)
    cluster_input = []
    for row in enriched:
        temp = dict(row)
        temp["timestamp"] = parse_timestamp(row["timestamp"])
        cluster_input.append(temp)

    clusters = build_clusters(
        cluster_input,
        radius_km=settings.cluster_radius_km,
        window_minutes=settings.cluster_window_minutes,
    )

    # Step 5: Assign cluster IDs to enriched records
    enriched = assign_cluster_ids(enriched, clusters)

    # Step 6: Score only nearby incidents
    relevant = [x for x in enriched if x["distance_km"] <= settings.nearby_radius_km]
    risk = score_risk(relevant)

    # Step 7: Generate alert
    alert_data = generate_alert(risk, clusters, relevant)

    return {
        "engine": "member4-incident-detection-engine",
        "is_simulated_demo": True,
        "clinical_validation": "NOT_VALIDATED",
        "hospital": {
            "latitude": h_lat,
            "longitude": h_lon,
            "name": settings.hospital_name,
        },
        "configuration": {
            "cluster_radius_km": settings.cluster_radius_km,
            "cluster_window_minutes": settings.cluster_window_minutes,
            "nearby_radius_km": settings.nearby_radius_km,
            "moderate_risk_threshold": settings.moderate_risk_threshold,
            "high_risk_threshold": settings.high_risk_threshold,
            "weights": {
                "count": settings.count_weight,
                "severity": settings.severity_weight,
                "proximity": settings.proximity_weight,
                "weather": settings.weather_weight,
            },
        },
        "incident_count_total": len(enriched),
        "incident_count_scored": len(relevant),
        "clusters": [
            {"cluster_id": f"CL-{i:03d}", "incident_ids": cluster}
            for i, cluster in enumerate(clusters, start=1)
        ],
        "incidents": enriched,
        "risk": risk,
        "alert": alert_data,
    }


def analyze_file(
    path: str | Path,
    hospital_lat: float | None = None,
    hospital_lon: float | None = None,
) -> dict[str, Any]:
    """Load incidents from a file and run the full analysis.

    Convenience wrapper for CLI and testing.
    """
    incidents = load_incidents_from_file(path)
    return analyze_incidents(incidents, hospital_lat, hospital_lon)
