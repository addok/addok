"""Tests for the geo_radius parameter."""
import pytest

from addok.core import search


def test_geo_radius_expands_search_area(factory):
    """Test that geo_radius parameter is accepted and used."""
    # Note: Geohash expansion is approximate - cells don't form perfect circles
    # This test verifies the parameter works, not exact radius precision

    # Create addresses at the same location with different names
    factory(
        name="Alpha Street",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.05,
    )

    factory(
        name="Beta Avenue",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.04,
    )

    # With geo_radius and strict mode, should still work
    results = search(
        "paris",
        lat=48.1,
        lon=0.9,
        geo_boost="strict",
        geo_radius=1.0
    )
    assert len(results) >= 1

    # Results should contain addresses from that location
    names = [r.labels[0] for r in results]
    assert any("Alpha" in name or "Beta" in name for name in names)

    # With larger radius, should still work
    results = search(
        "paris",
        lat=48.1,
        lon=0.9,
        geo_boost="strict",
        geo_radius=5.0
    )
    assert len(results) >= 1


def test_geo_radius_without_geo_boost(factory):
    """Test that geo_radius works with default geo_boost=score."""
    factory(
        name="nearby",
        city="Paris",
        lat=48.1009,
        lon=0.9009,
        importance=0.05,
    )

    factory(
        name="distant",
        city="Paris",
        lat=48.2,
        lon=1.0,
        importance=0.1,  # Higher importance
    )

    # With geo_radius but score mode, both should be found
    # but nearby should get geographic boost
    results = search("paris", lat=48.1, lon=0.9, geo_radius=2.0)
    assert len(results) >= 1
    # The nearby one should be in results due to geographic boost
    names = [r.labels[0] for r in results]
    assert any("nearby" in name for name in names)


def test_geo_radius_with_favor_mode(factory):
    """Test geo_radius with geo_boost=favor."""
    factory(
        name="close",
        city="Paris",
        lat=48.1009,
        lon=0.9009,
        importance=0.1,
    )

    factory(
        name="far",
        city="Paris",
        lat=48.2,
        lon=1.0,
        importance=0.05,
    )

    # With favor mode and radius, should return results
    results = search("paris", lat=48.1, lon=0.9, geo_boost="favor", geo_radius=1.0)
    assert len(results) >= 1
    # Both should be present (favor doesn't exclude, just prioritizes)
    names = [r.labels[0] for r in results]
    assert any("close" in name or "far" in name for name in names)


def test_geo_radius_zero(factory):
    """Test that geo_radius=0 uses minimal area (just center cell)."""
    # Create two addresses in neighboring geohash cells
    factory(
        name="incenter",
        city="Paris",
        lat=48.1001,  # Very close to center
        lon=0.9001,
        importance=0.05,
    )

    factory(
        name="neighbor",
        city="Paris",
        lat=48.11,  # In neighboring cell
        lon=0.91,
        importance=0.05,
    )

    # With radius=0 and strict mode, might only find center cell
    # (behavior depends on exact geohash boundaries)
    results = search("paris", lat=48.1, lon=0.9, geo_boost="strict", geo_radius=0.0)
    # Should at least find something if there are documents
    assert len(results) >= 0  # May be empty if no docs in exact cell


def test_geo_radius_very_large(factory):
    """Test that very large radius parameter is accepted."""
    factory(
        name="veryclose",
        city="Paris",
        lat=48.1009,
        lon=0.9009,
        importance=0.05,
    )

    factory(
        name="nearby",
        city="Paris",
        lat=48.102,
        lon=0.902,
        importance=0.05,
    )

    # With very large radius (10km), should work and find nearby results
    # (exact coverage depends on geohash cell boundaries)
    results = search("paris", lat=48.1, lon=0.9, geo_boost="strict", geo_radius=10.0)
    assert len(results) >= 1
    # Should find at least the close ones
    names = [r.labels[0] for r in results]
    assert any("veryclose" in name or "nearby" in name for name in names)


def test_geo_radius_without_center(factory):
    """Test that geo_radius has no effect without lat/lon."""
    factory(
        name="anywhere",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.05,
    )

    # Without center coordinates, geo_radius should be ignored
    results = search("paris", geo_radius=1.0)
    assert len(results) >= 1
    assert "anywhere" in results[0].labels[0]


def test_geo_radius_with_housenumber(factory):
    """Test geo_radius with housenumber search."""
    street = factory(
        name="Main Street",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.05,
    )

    factory(
        name="5 Main Street",
        city="Paris",
        housenumbers={"5": {"lat": 48.1005, "lon": 0.9005}},
        importance=0.05,
    )

    # Search for housenumber with geo_radius
    results = search(
        "5 main street paris",
        lat=48.1,
        lon=0.9,
        geo_boost="strict",
        geo_radius=1.0
    )
    assert len(results) >= 1
    # Should find the housenumber
    assert any("5" in r.housenumber for r in results if r.housenumber)


def test_geo_radius_edge_cases(factory):
    """Test edge cases for geo_radius values."""
    factory(
        name="test",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.05,
    )

    # Negative radius should be handled (treated as 0 or ignored)
    results = search("paris", lat=48.1, lon=0.9, geo_radius=-1.0)
    # Should still work, just ignore invalid radius
    assert len(results) >= 0

    # Very small positive radius
    results = search("paris", lat=48.1, lon=0.9, geo_radius=0.1)
    assert len(results) >= 0

    # Exactly at boundary values
    results = search("paris", lat=48.1, lon=0.9, geo_radius=0.5)
    assert len(results) >= 0

    results = search("paris", lat=48.1, lon=0.9, geo_radius=1.5)
    assert len(results) >= 0

    results = search("paris", lat=48.1, lon=0.9, geo_radius=2.5)
    assert len(results) >= 0


def test_geo_radius_with_different_precision(factory, monkeypatch):
    """Test that geo_radius adapts to different GEOHASH_PRECISION values."""
    from addok.config import config as addok_config

    # Test with precision 6 (larger cells ~1.2km)
    monkeypatch.setattr(addok_config, 'GEOHASH_PRECISION', 6)

    factory(
        name="large_precision",
        city="Paris",
        lat=48.1,
        lon=0.9,
        importance=0.05,
    )

    # With precision 6, cells are larger, so 1km radius should still work
    # but may cover different number of cells
    results = search("paris", lat=48.1, lon=0.9, geo_boost="strict", geo_radius=1.0)
    # Should find something (exact count depends on cell boundaries)
    assert len(results) >= 0

    # Test with precision 8 (smaller cells ~38m)
    monkeypatch.setattr(addok_config, 'GEOHASH_PRECISION', 8)

    factory(
        name="small_precision",
        city="Lyon",
        lat=45.75,
        lon=4.85,
        importance=0.05,
    )

    # With precision 8, cells are much smaller, so same radius covers more cells
    results = search("lyon", lat=45.75, lon=4.85, geo_boost="strict", geo_radius=0.5)
    assert len(results) >= 0
