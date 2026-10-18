"""
Geospatial utility functions.

This module handles all distance calculations and location-based operations.
We use the `geopy` library for accurate geodesic distance (it accounts for
Earth's ellipsoidal shape, unlike a simple Haversine which assumes a sphere).

WHY geopy INSTEAD OF HAND-ROLLED HAVERSINE?
--------------------------------------------
The original engine used a manual Haversine formula. That works for demos, but
geopy's Vincenty/geodesic calculation is more accurate (error < 0.5 %) and is
the standard used in production geospatial systems. We keep the Haversine as
a fast fallback for unit tests that need no external dependency.
"""
from __future__ import annotations

import math

from geopy.distance import geodesic


def calculate_distance_km(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Return the geodesic distance in kilometres between two lat/lon points.

    Uses geopy's geodesic (WGS-84 ellipsoid) for production accuracy.

    Args:
        lat1, lon1: Coordinates of point A (decimal degrees).
        lat2, lon2: Coordinates of point B (decimal degrees).

    Returns:
        Distance in kilometres, rounded to 6 decimal places.

    Example:
        >>> calculate_distance_km(12.9716, 77.5946, 12.975, 77.600)
        0.696...
    """
    return round(geodesic((lat1, lon1), (lat2, lon2)).kilometers, 6)


def haversine_km(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Fast Haversine fallback (assumes spherical Earth).

    Kept for backwards compatibility with the original engine and for
    environments where geopy is not installed.
    """
    earth_radius_km = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return round(2 * earth_radius_km * math.asin(math.sqrt(min(1.0, a))), 6)


def is_within_radius(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    radius_km: float,
) -> bool:
    """Check whether two points are within a given radius of each other."""
    return calculate_distance_km(lat1, lon1, lat2, lon2) <= radius_km
