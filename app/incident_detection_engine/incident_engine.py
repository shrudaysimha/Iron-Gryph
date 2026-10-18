# """Demonstration incident detection engine for hospital surge-risk signals.

# Uses only the Python standard library. Scores are illustrative operational heuristics,
# not clinically validated predictions and not a substitute for clinical/operational judgment.
# """
from __future__ import annotations

import csv
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = {
    "incident_id", "incident_type", "latitude", "longitude",
    "timestamp", "severity", "data_source",
}


@dataclass(frozen=True)
class EngineConfig:
    hospital_latitude: float
    hospital_longitude: float
    cluster_radius_km: float = 5.0
    cluster_window_minutes: int = 120
    nearby_radius_km: float = 15.0
    high_risk_threshold: float = 70.0
    moderate_risk_threshold: float = 35.0
    # Illustrative rule weights; adjust only for a demo until validated locally.
    count_weight: float = 35.0
    severity_weight: float = 30.0
    proximity_weight: float = 20.0
    weather_weight: float = 15.0

    def __post_init__(self):
        if not -90 <= self.hospital_latitude <= 90:
            raise ValueError("Hospital latitude must be between -90 and 90.")
        if not -180 <= self.hospital_longitude <= 180:
            raise ValueError("Hospital longitude must be between -180 and 180.")
        if self.cluster_radius_km <= 0 or self.cluster_window_minutes <= 0:
            raise ValueError("Cluster radius and time window must be positive.")
        if not 0 <= self.moderate_risk_threshold < self.high_risk_threshold <= 100:
            raise ValueError("Thresholds must satisfy 0 <= moderate < high <= 100.")


def parse_timestamp(value: Any) -> datetime:
    """Parse ISO-8601 timestamp; timezone-naive values are interpreted as UTC."""
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


def validate_incident(raw: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Incident is missing required fields: {', '.join(sorted(missing))}")
    item = dict(raw)
    item["incident_id"] = str(item["incident_id"]).strip()
    item["incident_type"] = str(item["incident_type"]).strip().lower()
    item["data_source"] = str(item["data_source"]).strip()
    if not item["incident_id"] or not item["incident_type"] or not item["data_source"]:
        raise ValueError("incident_id, incident_type, and data_source cannot be empty.")
    try:
        item["latitude"] = float(item["latitude"])
        item["longitude"] = float(item["longitude"])
        item["severity"] = int(item["severity"])
    except (TypeError, ValueError) as exc:
        raise ValueError("latitude/longitude must be numbers and severity must be an integer 1-5.") from exc
    if not -90 <= item["latitude"] <= 90:
        raise ValueError(f"Latitude out of range for incident {item['incident_id']}.")
    if not -180 <= item["longitude"] <= 180:
        raise ValueError(f"Longitude out of range for incident {item['incident_id']}.")
    if not 1 <= item["severity"] <= 5:
        raise ValueError(f"Severity for incident {item['incident_id']} must be between 1 and 5.")
    item["timestamp"] = parse_timestamp(item["timestamp"])
    # Optional weather context can be attached per incident or provided as a separate record.
    item["weather_condition"] = str(item.get("weather_condition", "none")).strip().lower()
    return item


def load_incidents(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a CSV or JSON file. JSON may be a list or {'incidents': [...]}."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        with file_path.open("r", newline="", encoding="utf-8-sig") as handle:
            records = list(csv.DictReader(handle))
    elif suffix == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        records = payload.get("incidents", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("JSON must be a list of incident objects or an object with an 'incidents' list.")
    else:
        raise ValueError("Unsupported file type. Use .csv or .json.")
    incidents = [validate_incident(record) for record in records]
    ids = [x["incident_id"] for x in incidents]
    if len(ids) != len(set(ids)):
        raise ValueError("incident_id values must be unique within an input file.")
    return incidents


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two latitude/longitude points."""
    earth_radius_km = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(min(1.0, a)))


def build_clusters(incidents: list[dict[str, Any]], radius_km: float, window_minutes: int) -> list[list[str]]:
    """Return connected groups where members are linked by both distance and time.

    This is connected-component clustering: A may link to B and B to C even if A-C
    exceeds the radius/window. It is intentionally simple for a small demo dataset.
    """
    n = len(incidents)
    adjacency = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            distance = haversine_km(
                incidents[i]["latitude"], incidents[i]["longitude"],
                incidents[j]["latitude"], incidents[j]["longitude"],
            )
            minutes = abs((incidents[i]["timestamp"] - incidents[j]["timestamp"]).total_seconds()) / 60
            if distance <= radius_km and minutes <= window_minutes:
                adjacency[i].append(j)
                adjacency[j].append(i)
    seen, clusters = set(), []
    for i in range(n):
        if i in seen:
            continue
        stack, component = [i], []
        seen.add(i)
        while stack:
            current = stack.pop()
            component.append(incidents[current]["incident_id"])
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if len(component) >= 2:
            clusters.append(sorted(component))
    return clusters


def score_risk(incidents: list[dict[str, Any]], config: EngineConfig) -> dict[str, Any]:
    """Compute an illustrative 0-100 risk score using documented weighted rules."""
    if not incidents:
        return {
            "risk_score": 0.0, "risk_category": "LOW",
            "reasons": ["No incidents were supplied."],
        }

    count = len(incidents)
    # Count signal: 1 incident = 0.25; 2 = 0.5; 3+ = 1.0.
    count_factor = min(count / 3.0, 1.0)
    # Severity signal: average severity on a 1-5 scale, mapped to 0-1.
    severity_factor = (sum(x["severity"] for x in incidents) / count - 1) / 4
    # Proximity signal: nearest incident at/inside 2 km => 1; at/over nearby_radius => 0.
    nearest_km = min(x["distance_km"] for x in incidents)
    proximity_factor = max(0.0, min(1.0, 1 - nearest_km / config.nearby_radius_km))
    # Weather signal: any severe weather condition among records increases this component.
    weather_types = {"heavy_rain", "extreme_heat", "storm", "flood"}
    weather_present = any(x.get("weather_condition", "none") in weather_types for x in incidents)
    weather_factor = 1.0 if weather_present else 0.0

    score = (
        config.count_weight * count_factor
        + config.severity_weight * severity_factor
        + config.proximity_weight * proximity_factor
        + config.weather_weight * weather_factor
    )
    score = round(max(0.0, min(100.0, score)), 1)

    if score >= config.high_risk_threshold:
        category = "HIGH"
    elif score >= config.moderate_risk_threshold:
        category = "MODERATE"
    else:
        category = "LOW"

    reasons = [
        f"{count} incident(s) considered (count contribution: {config.count_weight * count_factor:.1f}/ {config.count_weight:.1f}).",
        f"Average severity is {sum(x['severity'] for x in incidents) / count:.1f}/5 (severity contribution: {config.severity_weight * severity_factor:.1f}/ {config.severity_weight:.1f}).",
        f"Nearest incident is {nearest_km:.2f} km away (proximity contribution: {config.proximity_weight * proximity_factor:.1f}/ {config.proximity_weight:.1f}).",
        f"Relevant weather signal {'present' if weather_present else 'not present'} (weather contribution: {config.weather_weight * weather_factor:.1f}/ {config.weather_weight:.1f}).",
    ]
    return {
        "risk_score": score,
        "risk_category": category,
        "reasons": reasons,
        "factors": {
            "incident_count": count,
            "count_factor": round(count_factor, 3),
            "average_severity": round(sum(x["severity"] for x in incidents) / count, 2),
            "nearest_distance_km": round(nearest_km, 2),
            "weather_signal_present": weather_present,
        },
    }


def analyze_incidents(
    raw_incidents: Iterable[dict[str, Any]],
    config: EngineConfig,
) -> dict[str, Any]:
    """Validate, enrich, cluster and score incidents into JSON-serializable output."""
    incidents = [validate_incident(dict(x)) for x in raw_incidents]
    ids = [x["incident_id"] for x in incidents]
    if len(ids) != len(set(ids)):
        raise ValueError("incident_id values must be unique within an analysis batch.")

    enriched = []
    for item in incidents:
        row = dict(item)
        row["distance_km"] = haversine_km(
            row["latitude"], row["longitude"],
            config.hospital_latitude, config.hospital_longitude,
        )
        row["timestamp"] = row["timestamp"].isoformat().replace("+00:00", "Z")
        enriched.append(row)

    # Convert timestamp back for clustering after serialization.
    cluster_input = []
    for row in enriched:
        temp = dict(row)
        temp["timestamp"] = parse_timestamp(row["timestamp"])
        cluster_input.append(temp)
    clusters = build_clusters(cluster_input, config.cluster_radius_km, config.cluster_window_minutes)

    # Score incidents within the nearby radius; far incidents remain listed but do not affect score.
    relevant = [x for x in enriched if x["distance_km"] <= config.nearby_radius_km]
    risk = score_risk(relevant, config)
    cluster_map = {incident_id: cluster for cluster in clusters for incident_id in cluster}
    for row in enriched:
        row["cluster_id"] = None
        for idx, cluster in enumerate(clusters, start=1):
            if row["incident_id"] in cluster:
                row["cluster_id"] = f"CL-{idx:03d}"
                break

    cluster_reasons = [f"Detected {len(clusters)} nearby cluster(s): " + ", ".join(", ".join(c) for c in clusters)] if clusters else ["No incident cluster met both configured distance and time limits."]
    alert = (
        f"{risk['risk_category']} potential surge-risk alert (demo score {risk['risk_score']}/100). "
        + " ".join(risk["reasons"])
        + " "
        + " ".join(cluster_reasons)
        + " This is a simulated operational heuristic, not a clinically validated prediction."
    )
    return {
        "engine": "member4-incident-detection-demo",
        "is_simulated_demo": True,
        "clinical_validation": "NOT_VALIDATED",
        "hospital": {
            "latitude": config.hospital_latitude,
            "longitude": config.hospital_longitude,
        },
        "configuration": {
            "cluster_radius_km": config.cluster_radius_km,
            "cluster_window_minutes": config.cluster_window_minutes,
            "nearby_radius_km": config.nearby_radius_km,
            "moderate_risk_threshold": config.moderate_risk_threshold,
            "high_risk_threshold": config.high_risk_threshold,
            "weights": {
                "count": config.count_weight, "severity": config.severity_weight,
                "proximity": config.proximity_weight, "weather": config.weather_weight,
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
        "alert": alert,
    }


def analyze_file(path: str | Path, config: EngineConfig) -> dict[str, Any]:
    return analyze_incidents(load_incidents(path), config)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Demonstration hospital incident risk engine")
    parser.add_argument("input_file", help="Path to incidents.csv or incidents.json")
    parser.add_argument("--hospital-lat", type=float, default=12.9716, help="Hospital latitude (demo default: Bengaluru)")
    parser.add_argument("--hospital-lon", type=float, default=77.5946, help="Hospital longitude (demo default: Bengaluru)")
    parser.add_argument("--output", help="Optional output JSON file; prints to stdout if omitted")
    args = parser.parse_args()
    config = EngineConfig(args.hospital_lat, args.hospital_lon)
    result = analyze_file(args.input_file, config)
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
