"""Tests for geo_boost and geo_radius parameter validation."""
import pytest

from addok.core import search


def test_invalid_geo_boost_value_raises_error(factory):
    """Test that invalid geo_boost values raise ValueError."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    with pytest.raises(ValueError, match="geo_boost must be one of"):
        search("rue victor hugo", lat=48.856, lon=2.352, geo_boost="invalid")


def test_invalid_geo_radius_negative_raises_error(factory):
    """Test that negative geo_radius raises ValueError."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    with pytest.raises(ValueError, match="geo_radius must be between 0 and 100"):
        search("rue victor hugo", lat=48.856, lon=2.352, geo_radius=-1.0)


def test_invalid_geo_radius_too_large_raises_error(factory):
    """Test that geo_radius > 100 raises ValueError."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    with pytest.raises(ValueError, match="geo_radius must be between 0 and 100"):
        search("rue victor hugo", lat=48.856, lon=2.352, geo_radius=150.0)


def test_invalid_geo_radius_type_raises_error(factory):
    """Test that non-numeric geo_radius raises TypeError."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    with pytest.raises(TypeError, match="geo_radius must be a number"):
        search("rue victor hugo", lat=48.856, lon=2.352, geo_radius="invalid")


def test_valid_geo_radius_zero_accepted(factory):
    """Test that geo_radius=0 is valid."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    # Should not raise
    results = search("rue victor hugo", lat=48.856, lon=2.352, geo_radius=0.0)
    assert isinstance(results, list)


def test_geo_boost_with_lat_but_no_lon(factory):
    """Test geo_boost behavior with only lat provided."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    # Should work but not apply geographic filtering (no center)
    results = search("rue victor hugo", lat=48.856, geo_boost="favor")
    assert len(results) >= 1


def test_geo_boost_with_lon_but_no_lat(factory):
    """Test geo_boost behavior with only lon provided."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    # Should work but not apply geographic filtering (no center)
    results = search("rue victor hugo", lon=2.352, geo_boost="favor")
    assert len(results) >= 1


def test_geo_radius_without_center(factory):
    """Test that geo_radius without center point is ignored."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    # Should work, radius simply ignored without center
    results = search("rue victor hugo", geo_radius=5.0)
    assert len(results) >= 1
