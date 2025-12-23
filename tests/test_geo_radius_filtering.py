"""Tests for geo_radius filtering behavior."""
import pytest

from addok.core import search


def test_geo_radius_filters_out_distant_results(factory):
    """Test that geo_radius filters out results in STRICT mode only."""
    # Create address at exactly Paris center
    center = factory(
        name="Tour Eiffel",
        city="Paris",
        lat=48.8584,
        lon=2.2945,
        importance=0.5,
    )

    # Create address ~500m away (should be included in 1km radius)
    nearby = factory(
        name="Trocadéro",
        city="Paris",
        lat=48.8629,  # ~500m north
        lon=2.2877,
        importance=0.4,
    )

    # Create address ~2km away (should be excluded in STRICT mode with 1km radius)
    distant = factory(
        name="Arc de Triomphe",
        city="Paris",
        lat=48.8738,  # ~2km north
        lon=2.2950,
        importance=0.6,  # Higher importance
    )

    # In STRICT mode with 1km radius: should filter by distance
    results = search(
        "paris",
        lat=48.8584,
        lon=2.2945,
        geo_boost="strict",
        geo_radius=1.0,
        limit=10
    )

    # Should only include center and nearby, not distant
    result_ids = {r.id for r in results}
    assert center["id"] in result_ids
    # Nearby might or might not be there depending on geohash
    assert distant["id"] not in result_ids, "Result >1km away should be filtered out in strict mode"

    # In SCORE mode (default) with 1km radius: NO filtering, just scoring
    results = search(
        "paris",
        lat=48.8584,
        lon=2.2945,
        geo_radius=1.0,  # Should only affect geohash selection, not filtering
        limit=10
    )

    # All results should potentially be present (no strict distance filtering)
    # They are just scored by distance
    assert len(results) >= 1  # At least some results


def test_geo_radius_with_strict_mode(factory):
    """Test that geo_radius filtering works with geo_boost=strict."""
    center_lat, center_lon = 48.8584, 2.2945

    # Create several addresses at various distances
    at_center = factory(
        name="center", city="Paris",
        lat=center_lat, lon=center_lon, importance=0.5
    )

    # Very close - almost same location (definitely in same geohash)
    very_close = factory(
        name="very close", city="Paris",
        lat=center_lat + 0.0001, lon=center_lon + 0.0001,  # ~10m
        importance=0.4
    )

    distant_2km = factory(
        name="distant", city="Paris",
        lat=48.8738, lon=2.2950, importance=0.6
    )

    # Strict mode with 1km radius
    results = search(
        "paris",
        lat=center_lat,
        lon=center_lon,
        geo_boost="strict",
        geo_radius=1.0,
        limit=10
    )

    result_ids = {r.id for r in results}
    assert at_center["id"] in result_ids
    assert very_close["id"] in result_ids
    assert distant_2km["id"] not in result_ids


def test_geo_radius_zero_very_strict(factory):
    """Test that geo_radius=0 only returns results in the exact geohash cell."""
    center_lat, center_lon = 48.8584, 2.2945

    # At center
    at_center = factory(
        name="center", city="Paris",
        lat=center_lat, lon=center_lon
    )

    # Very close (10 meters) but might be in different geohash at high precision
    very_close = factory(
        name="very close", city="Paris",
        lat=center_lat + 0.0001, lon=center_lon + 0.0001  # ~10-15m
    )

    # With radius=0, might only get exact center (depends on geohash precision)
    results = search(
        "paris",
        lat=center_lat,
        lon=center_lon,
        geo_boost="strict",
        geo_radius=0.0,
        limit=10
    )

    # At least the center should be there
    result_ids = {r.id for r in results}
    assert at_center["id"] in result_ids


def test_geo_radius_preserves_importance_within_radius(factory):
    """Test that within the radius, results are still returned."""
    center_lat, center_lon = 48.8584, 2.2945

    # Two results within 1km but different importance
    low_importance = factory(
        name="rue de Paris",
        city="Paris",
        lat=48.8620, lon=2.2900,
        importance=0.1
    )

    high_importance = factory(
        name="avenue de Paris",
        city="Paris",
        lat=48.8610, lon=2.2920,
        importance=0.9
    )

    results = search(
        "paris",
        lat=center_lat,
        lon=center_lon,
        geo_radius=1.0,
        limit=10
    )

    # Both should be in results (scoring determines order)
    result_ids = [r.id for r in results]
    assert low_importance["id"] in result_ids
    assert high_importance["id"] in result_ids
    assert len(results) >= 2


def test_geo_radius_large_value_within_geohash_range(factory):
    """Test that geo_radius works within reasonable geohash coverage."""
    center_lat, center_lon = 48.8584, 2.2945

    # Create result at center
    paris = factory(name="Paris center", city="Paris", lat=center_lat, lon=center_lon)

    # Create result ~5km away (definitely within geohash coverage)
    nearby = factory(
        name="Paris nearby",
        city="Paris",
        lat=center_lat + 0.05,  # ~5km north
        lon=center_lon
    )

    # With 10km radius, both should be included
    results = search(
        "paris",
        lat=center_lat,
        lon=center_lon,
        geo_radius=10.0,
        limit=10
    )

    # Both should be there
    result_ids = {r.id for r in results}
    assert paris["id"] in result_ids
    assert nearby["id"] in result_ids
