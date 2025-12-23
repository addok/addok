"""Unit tests for filter_by_geo_radius result processor."""
import pytest

from addok.helpers.results import filter_by_geo_radius


class MockHelper:
    """Mock helper for testing filter_by_geo_radius."""
    def __init__(self, geo_boost_mode=None, geo_radius=None, lat=None, lon=None):
        if geo_boost_mode:
            self.geo_boost_mode = geo_boost_mode
        if geo_radius is not None:
            self.geo_radius = geo_radius
        self.lat = lat
        self.lon = lon
        self.debug_messages = []
    
    def debug(self, msg, *args):
        self.debug_messages.append(msg % args if args else msg)


class MockResult:
    """Mock result for testing filter_by_geo_radius."""
    def __init__(self, lat, lon, distance_m=None):
        self.lat = lat
        self.lon = lon
        if distance_m is not None:
            self.distance = distance_m
    
    def __str__(self):
        return f"MockResult({self.lat}, {self.lon})"


def test_filter_only_in_strict_mode():
    """Test that filtering only applies in strict mode."""
    helper_score = MockHelper(geo_boost_mode="score", geo_radius=1.0, lat=48.8584, lon=2.2945)
    helper_favor = MockHelper(geo_boost_mode="favor", geo_radius=1.0, lat=48.8584, lon=2.2945)
    helper_strict = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result 2km away (beyond 1km radius)
    result = MockResult(lat=48.8738, lon=2.2950, distance_m=2000)
    
    # Score mode: should NOT filter
    assert filter_by_geo_radius(helper_score, result) is None
    
    # Favor mode: should NOT filter
    assert filter_by_geo_radius(helper_favor, result) is None
    
    # Strict mode: SHOULD filter
    assert filter_by_geo_radius(helper_strict, result) is False


def test_filter_requires_geo_radius():
    """Test that filtering requires geo_radius to be set."""
    # Strict mode but no geo_radius
    helper = MockHelper(geo_boost_mode="strict", lat=48.8584, lon=2.2945)
    result = MockResult(lat=48.8738, lon=2.2950, distance_m=2000)
    
    # Should NOT filter without geo_radius
    assert filter_by_geo_radius(helper, result) is None


def test_filter_requires_center():
    """Test that filtering requires a center point."""
    # Strict mode with radius but no center
    helper_no_lat = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lon=2.2945)
    helper_no_lon = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584)
    
    result = MockResult(lat=48.8738, lon=2.2950, distance_m=2000)
    
    # Should NOT filter without center
    assert filter_by_geo_radius(helper_no_lat, result) is None
    assert filter_by_geo_radius(helper_no_lon, result) is None


def test_filter_keeps_results_within_radius():
    """Test that results within radius are kept."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result 500m away (within 1km radius)
    result = MockResult(lat=48.8620, lon=2.2900, distance_m=500)
    
    # Should NOT filter
    assert filter_by_geo_radius(helper, result) is None


def test_filter_removes_results_beyond_radius():
    """Test that results beyond radius are removed."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result 2km away (beyond 1km radius)
    result = MockResult(lat=48.8738, lon=2.2950, distance_m=2000)
    
    # Should filter out
    assert filter_by_geo_radius(helper, result) is False
    
    # Check debug message
    assert len(helper.debug_messages) == 1
    assert "Filtering out" in helper.debug_messages[0]
    assert "2.00 km > 1.00 km" in helper.debug_messages[0]


def test_filter_exact_boundary():
    """Test filtering at exact radius boundary."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result exactly at 1km
    result_at_boundary = MockResult(lat=48.8584, lon=2.2945, distance_m=1000)
    assert filter_by_geo_radius(helper, result_at_boundary) is None  # Keep (<=)
    
    # Result just beyond 1km
    result_beyond = MockResult(lat=48.8584, lon=2.2945, distance_m=1001)
    assert filter_by_geo_radius(helper, result_beyond) is False  # Filter (>)


def test_filter_calculates_distance_if_missing():
    """Test that distance is calculated if not already set."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result without distance attribute (2km away)
    result = MockResult(lat=48.8738, lon=2.2950)
    
    # Should calculate distance and filter
    assert filter_by_geo_radius(helper, result) is False
    
    # Distance should now be set
    assert hasattr(result, 'distance')
    assert result.distance > 1000  # > 1km in meters


def test_filter_with_zero_radius():
    """Test filtering with zero radius."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=0.0, lat=48.8584, lon=2.2945)
    
    # Result at exact center
    result_center = MockResult(lat=48.8584, lon=2.2945, distance_m=0)
    assert filter_by_geo_radius(helper, result_center) is None  # Keep
    
    # Result 1m away
    result_near = MockResult(lat=48.8584, lon=2.2945, distance_m=1)
    assert filter_by_geo_radius(helper, result_near) is False  # Filter


def test_filter_with_large_radius():
    """Test filtering with large radius."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=100.0, lat=48.8584, lon=2.2945)
    
    # Result 50km away (within 100km radius)
    result = MockResult(lat=48.4, lon=2.3, distance_m=50000)
    assert filter_by_geo_radius(helper, result) is None  # Keep
    
    # Result 150km away (beyond 100km radius)
    result_far = MockResult(lat=47.0, lon=2.3, distance_m=150000)
    assert filter_by_geo_radius(helper, result_far) is False  # Filter


def test_filter_uses_existing_distance():
    """Test that existing distance is reused (no recalculation)."""
    helper = MockHelper(geo_boost_mode="strict", geo_radius=1.0, lat=48.8584, lon=2.2945)
    
    # Result with pre-calculated distance (2km in meters)
    result = MockResult(lat=48.8584, lon=2.2945, distance_m=2000)
    
    # Store original distance
    original_distance = result.distance
    
    # Filter should use existing distance
    filter_by_geo_radius(helper, result)
    
    # Distance should not have changed
    assert result.distance == original_distance
