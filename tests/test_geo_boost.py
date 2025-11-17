"""Tests for geo_boost parameter functionality."""
import pytest

from addok.core import search


def test_geo_boost_score_is_default(factory):
    """Test that geo_boost=score is the default behavior."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352, importance=0.5)
    factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85, importance=0.8)
    
    # Without geo_boost parameter (default=score)
    results = search("rue victor hugo", lat=48.856, lon=2.352, limit=10)
    
    # Both results should be found (no strict filtering)
    assert len(results) == 2


def test_geo_boost_favor_prioritizes_nearby(factory):
    """Test that geo_boost=favor prioritizes nearby results."""
    paris = factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352, importance=0.3)
    factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85, importance=0.9)
    
    # With geo_boost=favor from Paris
    results = search("rue victor hugo", lat=48.856, lon=2.352, limit=10, geo_boost="favor")
    
    # Should find both (fallback if needed)
    assert len(results) >= 1
    
    # Paris should rank higher despite lower importance
    assert results[0].id == paris["id"]


def test_geo_boost_strict_filters_by_location(factory):
    """Test that geo_boost=strict only returns nearby results."""
    paris = factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    lyon = factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85)
    
    # With geo_boost=strict from Paris
    results = search("rue victor hugo", lat=48.856, lon=2.352, limit=10, geo_boost="strict")
    
    # Should only find Paris (strict filtering)
    assert len(results) == 1
    assert results[0].id == paris["id"]
    
    # With geo_boost=strict from Lyon
    results = search("rue victor hugo", lat=45.75, lon=4.85, limit=10, geo_boost="strict")
    
    # Should only find Lyon
    assert len(results) == 1
    assert results[0].id == lyon["id"]


def test_geo_boost_strict_can_return_empty(factory):
    """Test that geo_boost=strict can return empty results."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    
    # Search far from Paris with strict mode
    results = search("rue victor hugo", lat=43.296, lon=5.370, limit=10, geo_boost="strict", verbose=True)
    
    # Debug: show what we got
    print(f"\nGot {len(results)} results:")
    for r in results:
        print(f"  - {r} at ({r.lat}, {r.lon})")
    
    # Should return empty (no match within radius)
    assert len(results) == 0


def test_geo_boost_favor_fallback_when_dry(factory):
    """Test that geo_boost=favor falls back to broader search when nearby results are insufficient."""
    # Create only 2 nearby, but request 10
    paris1 = factory(name="rue de la paix", city="Paris 1er", lat=48.857, lon=2.352, importance=0.3)
    paris2 = factory(name="rue de la paix", city="Paris 2e", lat=48.858, lon=2.353, importance=0.3)
    
    # Create distant matches with lower importance
    factory(name="rue de la paix", city="Lyon", lat=45.75, lon=4.85, importance=0.2)
    factory(name="rue de la paix", city="Marseille", lat=43.296, lon=5.370, importance=0.1)
    
    # Request 10 with favor mode from Paris
    results = search("rue de la paix", lat=48.857, lon=2.352, limit=10, geo_boost="favor")
    
    # Should find more than 2 (fallback activated)
    assert len(results) > 2
    
    # Paris results should be in top results (due to geography + importance)
    paris_ids = {paris1["id"], paris2["id"]}
    top_2_ids = {results[0].id, results[1].id}
    # At least one Paris result in top 2
    assert len(paris_ids & top_2_ids) >= 1


def test_geo_boost_with_common_terms(factory):
    """Test geo_boost behavior with common terms."""
    factory(name="rue de paris", city="Paris", lat=48.856, lon=2.352)
    factory(name="rue de lyon", city="Lyon", lat=45.75, lon=4.85)
    
    # Common terms already use geohash, but favor should reinforce
    results = search("rue de", lat=48.856, lon=2.352, limit=10, geo_boost="favor")
    
    # Should prioritize Paris area
    assert len(results) >= 1


def test_geo_boost_with_housenumber(factory):
    """Test geo_boost with housenumber search."""
    factory(
        name="rue victor hugo",
        city="Paris",
        lat=48.856,
        lon=2.352,
        housenumbers={"24": {"lat": 48.8561, "lon": 2.3521}}
    )
    factory(
        name="rue victor hugo",
        city="Lyon",
        lat=45.75,
        lon=4.85,
        housenumbers={"24": {"lat": 45.751, "lon": 4.851}}
    )
    
    # Search for specific number with favor
    results = search("24 rue victor hugo", lat=48.856, lon=2.352, limit=10, geo_boost="favor")
    
    # Should find both but prioritize Paris
    assert len(results) >= 1
    assert results[0].city == "Paris"


def test_geo_boost_with_autocomplete(factory):
    """Test geo_boost in autocomplete mode."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352)
    factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85)
    
    # Autocomplete with favor
    results = search("rue vic", lat=48.856, lon=2.352, limit=10, autocomplete=True, geo_boost="favor")
    
    # Should work with autocomplete
    assert len(results) >= 1


def test_geo_boost_without_center(factory):
    """Test that geo_boost is ignored when no center is provided."""
    paris = factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352, importance=0.3)
    lyon = factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85, importance=0.9)
    
    # geo_boost without lat/lon should be ignored
    results = search("rue victor hugo", limit=10, geo_boost="favor")
    
    # Both found, ordered by text+importance (Lyon first)
    assert len(results) == 2
    assert results[0].id == lyon["id"]


def test_geo_boost_with_filters(factory):
    """Test geo_boost combined with filters."""
    factory(name="rue victor hugo", city="Paris", lat=48.856, lon=2.352, type="street")
    factory(name="place victor hugo", city="Paris", lat=48.857, lon=2.353, type="locality")
    factory(name="rue victor hugo", city="Lyon", lat=45.75, lon=4.85, type="street")
    
    # Favor mode with type filter
    results = search(
        "victor hugo",
        lat=48.856,
        lon=2.352,
        limit=10,
        geo_boost="favor",
        type="street"
    )
    
    # Should find streets, prioritizing Paris
    assert len(results) >= 1
    assert results[0].type == "street"
    assert results[0].city == "Paris"


def test_geo_boost_invalid_value():
    """Test that invalid geo_boost value is handled (at API level, not tested here)."""
    # This would be tested in test_http.py
    pass


def test_geo_boost_favor_with_high_importance_nearby(factory):
    """Test favor mode when nearby result also has high importance."""
    paris = factory(name="notre dame", city="Paris", lat=48.853, lon=2.349, importance=0.9)
    factory(name="notre dame", city="Reims", lat=49.254, lon=4.034, importance=0.7)
    
    # Favor mode near Paris
    results = search("notre dame", lat=48.853, lon=2.349, limit=10, geo_boost="favor")
    
    # Paris should win (high importance + close)
    assert results[0].id == paris["id"]


def test_geo_boost_strict_performance(factory):
    """Test that strict mode doesn't fetch unnecessary distant results."""
    # Create many distant results
    for i in range(50):
        factory(name="rue commune", city=f"City{i}", lat=45.0 + i*0.1, lon=5.0 + i*0.1)
    
    # Create one nearby
    nearby = factory(name="rue commune", city="Paris", lat=48.856, lon=2.352)
    
    # Strict mode should be fast (not fetching 50 results)
    results = search("rue commune", lat=48.856, lon=2.352, limit=10, geo_boost="strict")
    
    # Should only find the nearby one
    assert len(results) == 1
    assert results[0].id == nearby["id"]
