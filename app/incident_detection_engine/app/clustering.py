"""
Incident clustering engine.

PURPOSE
-------
When multiple incidents happen close together in space AND time, they likely
share a common cause (e.g., a pile-up on a highway, a storm cell moving
through an area). Clustering helps the hospital prepare for a SURGE rather
than treating each incident report independently.

ALGORITHM: Connected-Component Clustering
------------------------------------------
1. Build a graph where each incident is a node.
2. Draw an edge between two incidents if:
   - Their geographic distance ≤ cluster_radius_km   AND
   - Their time difference ≤ cluster_window_minutes
3. Find connected components using BFS.
4. Any component with ≥ 2 incidents is reported as a cluster.

This is O(n²) which is fine for demo/moderate datasets. For production with
thousands of incidents, consider spatial indexing (R-tree) or DBSCAN.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .geo_utils import calculate_distance_km


def build_clusters(
    incidents: list[dict[str, Any]],
    radius_km: float,
    window_minutes: int,
) -> list[list[str]]:
    """Group incidents into clusters based on proximity and time.

    Args:
        incidents: List of incident dicts, each must have 'incident_id',
                   'latitude', 'longitude', and 'timestamp' (datetime).
        radius_km: Maximum distance (km) for two incidents to be linked.
        window_minutes: Maximum time gap (minutes) for two incidents to be linked.

    Returns:
        A list of clusters. Each cluster is a sorted list of incident_id strings.
        Only clusters with 2+ incidents are returned.

    Example:
        >>> clusters = build_clusters(incidents, radius_km=5.0, window_minutes=120)
        >>> # [['INC-001', 'INC-002', 'INC-003']]
    """
    n = len(incidents)
    if n < 2:
        return []

    # Step 1: Build adjacency list
    adjacency: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # Check distance
            dist = calculate_distance_km(
                incidents[i]["latitude"], incidents[i]["longitude"],
                incidents[j]["latitude"], incidents[j]["longitude"],
            )
            # Check time gap
            ts_i = incidents[i]["timestamp"]
            ts_j = incidents[j]["timestamp"]
            if isinstance(ts_i, str):
                from .data_processing import parse_timestamp
                ts_i = parse_timestamp(ts_i)
            if isinstance(ts_j, str):
                from .data_processing import parse_timestamp
                ts_j = parse_timestamp(ts_j)

            minutes_apart = abs((ts_i - ts_j).total_seconds()) / 60

            if dist <= radius_km and minutes_apart <= window_minutes:
                adjacency[i].append(j)
                adjacency[j].append(i)

    # Step 2: BFS to find connected components
    seen: set[int] = set()
    clusters: list[list[str]] = []

    for i in range(n):
        if i in seen:
            continue
        # BFS from node i
        queue = [i]
        seen.add(i)
        component: list[str] = []
        while queue:
            current = queue.pop(0)
            component.append(incidents[current]["incident_id"])
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)

        # Only report clusters with 2+ incidents
        if len(component) >= 2:
            clusters.append(sorted(component))

    return clusters


def assign_cluster_ids(
    incidents: list[dict[str, Any]],
    clusters: list[list[str]],
) -> list[dict[str, Any]]:
    """Add a 'cluster_id' field to each incident based on cluster membership.

    Incidents not in any cluster get cluster_id = None.
    Cluster IDs are formatted as 'CL-001', 'CL-002', etc.
    """
    result = []
    for item in incidents:
        row = dict(item)
        row["cluster_id"] = None
        for idx, cluster in enumerate(clusters, start=1):
            if row["incident_id"] in cluster:
                row["cluster_id"] = f"CL-{idx:03d}"
                break
        result.append(row)
    return result
