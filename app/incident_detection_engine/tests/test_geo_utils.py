"""
Unit tests for geospatial utility functions.

These tests verify:
  - Distance calculations are accurate.
  - Zero distance for same-point checks.
  - The is_within_radius helper works correctly.
  - Edge cases (poles, antimeridian) don't crash.
"""
import pytest
from app.geo_utils import calculate_distance_km, haversine_km, is_within_radius


# ── Known reference distances ──────────────────────────────────────────
# Bengaluru hospital to a point ~0.7 km away
HOSPITAL = (12.9716, 77.5946)
NEARBY_POINT = (12.975, 77.600)


class TestCalculateDistanceKm:
    """Tests for the primary geodesic distance function."""

    def test_same_point_is_zero(self):
        assert calculate_distance_km(*HOSPITAL, *HOSPITAL) == 0.0

    def test_nearby_point_is_reasonable(self):
        dist = calculate_distance_km(*HOSPITAL, *NEARBY_POINT)
        # Should be roughly 0.6–0.8 km
        assert 0.5 < dist < 1.0

    def test_known_city_distance(self):
        # Bengaluru to Mumbai ≈ 840 km
        dist = calculate_distance_km(12.9716, 77.5946, 19.0760, 72.8777)
        assert 830 < dist < 850

    def test_symmetry(self):
        d1 = calculate_distance_km(*HOSPITAL, *NEARBY_POINT)
        d2 = calculate_distance_km(*NEARBY_POINT, *HOSPITAL)
        assert abs(d1 - d2) < 0.001

    def test_poles(self):
        # North pole to south pole ≈ 20,004 km
        dist = calculate_distance_km(90, 0, -90, 0)
        assert 19900 < dist < 20100


class TestHaversineKm:
    """Tests for the Haversine fallback."""

    def test_same_point(self):
        assert haversine_km(*HOSPITAL, *HOSPITAL) == 0.0

    def test_agrees_with_geodesic(self):
        geo = calculate_distance_km(*HOSPITAL, *NEARBY_POINT)
        hav = haversine_km(*HOSPITAL, *NEARBY_POINT)
        # Haversine and geodesic should agree within 1%
        assert abs(geo - hav) / max(geo, 0.001) < 0.01


class TestIsWithinRadius:
    """Tests for the radius check helper."""

    def test_point_within_radius(self):
        assert is_within_radius(*HOSPITAL, *NEARBY_POINT, radius_km=5.0) is True

    def test_point_outside_radius(self):
        assert is_within_radius(*HOSPITAL, *NEARBY_POINT, radius_km=0.1) is False

    def test_same_point_always_within(self):
        assert is_within_radius(*HOSPITAL, *HOSPITAL, radius_km=0.001) is True
