"""
Unit tests for clustering.

Tests verify:
  - Two nearby, same-time incidents form a cluster.
  - Distant incidents are NOT clustered.
  - Time-separated incidents are NOT clustered.
  - Cluster IDs are assigned correctly.
"""
import pytest
from datetime import datetime, timezone

from app.clustering import assign_cluster_ids, build_clusters


def _inc(inc_id, lat=12.975, lon=77.600, time="2026-10-17T18:10:00Z", sev=3):
    """Quick incident builder for clustering tests."""
    from app.data_processing import parse_timestamp
    return {
        "incident_id": inc_id,
        "incident_type": "road_accident",
        "latitude": lat,
        "longitude": lon,
        "timestamp": parse_timestamp(time),
        "severity": sev,
        "data_source": "TEST",
        "weather_condition": "none",
    }


class TestBuildClusters:
    def test_two_close_incidents_clustered(self):
        data = [
            _inc("A", lat=12.975, lon=77.600, time="2026-10-17T18:00:00Z"),
            _inc("B", lat=12.976, lon=77.601, time="2026-10-17T18:30:00Z"),
        ]
        clusters = build_clusters(data, radius_km=5.0, window_minutes=120)
        assert len(clusters) == 1
        assert set(clusters[0]) == {"A", "B"}

    def test_distant_incidents_not_clustered(self):
        data = [
            _inc("A", lat=12.975, lon=77.600),
            _inc("B", lat=13.200, lon=77.800),  # ~30 km away
        ]
        clusters = build_clusters(data, radius_km=5.0, window_minutes=120)
        assert len(clusters) == 0

    def test_time_separated_not_clustered(self):
        data = [
            _inc("A", time="2026-10-17T08:00:00Z"),
            _inc("B", lat=12.976, lon=77.601, time="2026-10-17T18:00:00Z"),  # 10 hours later
        ]
        clusters = build_clusters(data, radius_km=5.0, window_minutes=120)
        assert len(clusters) == 0

    def test_chain_clustering(self):
        """A links to B, B links to C, so all three form one cluster."""
        data = [
            _inc("A", lat=12.970, lon=77.590, time="2026-10-17T18:00:00Z"),
            _inc("B", lat=12.973, lon=77.593, time="2026-10-17T18:30:00Z"),
            _inc("C", lat=12.976, lon=77.596, time="2026-10-17T19:00:00Z"),
        ]
        clusters = build_clusters(data, radius_km=5.0, window_minutes=120)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_single_incident_no_cluster(self):
        clusters = build_clusters([_inc("A")], radius_km=5.0, window_minutes=120)
        assert len(clusters) == 0

    def test_empty_list(self):
        assert build_clusters([], radius_km=5.0, window_minutes=120) == []


class TestAssignClusterIds:
    def test_assigns_ids_correctly(self):
        incidents = [
            {"incident_id": "A", "other": 1},
            {"incident_id": "B", "other": 2},
            {"incident_id": "C", "other": 3},
        ]
        clusters = [["A", "B"]]
        result = assign_cluster_ids(incidents, clusters)
        assert result[0]["cluster_id"] == "CL-001"
        assert result[1]["cluster_id"] == "CL-001"
        assert result[2]["cluster_id"] is None

    def test_multiple_clusters(self):
        incidents = [{"incident_id": x} for x in ["A", "B", "C", "D"]]
        clusters = [["A", "B"], ["C", "D"]]
        result = assign_cluster_ids(incidents, clusters)
        assert result[0]["cluster_id"] == "CL-001"
        assert result[2]["cluster_id"] == "CL-002"
