"""Tests for geohash helper functions."""
import pytest
import geohash as geohash_lib

from addok.helpers import haversine_distance
from addok.helpers.geohash import (
    get_geohash_cell_size,
    calculate_geohash_layers,
)


def test_haversine_known_distances():
    """Test haversine calculation with known distances."""
    # Paris to Lyon: ~392 km
    distance = haversine_distance((48.8566, 2.3522), (45.7640, 4.8357))
    assert 390 < distance < 395

    # Paris to Paris (same point): 0 km
    distance = haversine_distance((48.8566, 2.3522), (48.8566, 2.3522))
    assert distance < 0.001

    # Equator 1 degree longitude: ~111 km
    distance = haversine_distance((0, 0), (0, 1))
    assert 110 < distance < 112


def test_get_geohash_cell_size_paris():
    """Test cell size calculation at Paris latitude."""
    # Paris: precision 7
    gh = geohash_lib.encode(48.8566, 2.3522, 7)
    lat_size, lon_size = get_geohash_cell_size(gh)

    # Latitude dimension is relatively constant
    assert 0.15 < lat_size < 0.16  # ~153m

    # Longitude dimension is smaller at this latitude
    assert 0.09 < lon_size < 0.11  # ~100m


def test_get_geohash_cell_size_varies_with_latitude():
    """Test that longitude dimension varies with latitude."""
    precision = 7

    # Near equator (Gabon): cells are nearly square
    gh_equator = geohash_lib.encode(0.5, 9.5, precision)
    lat_eq, lon_eq = get_geohash_cell_size(gh_equator)
    assert abs(lat_eq - lon_eq) < 0.01  # Nearly equal

    # Mid-latitudes (Paris): longitude smaller
    gh_paris = geohash_lib.encode(48.8, 2.3, precision)
    lat_paris, lon_paris = get_geohash_cell_size(gh_paris)
    assert lon_paris < lat_paris * 0.7  # Noticeably smaller

    # High latitudes (Iceland): longitude much smaller
    gh_iceland = geohash_lib.encode(65.0, -18.0, precision)
    lat_ice, lon_ice = get_geohash_cell_size(gh_iceland)
    assert lon_ice < lat_ice * 0.5  # Much smaller


def test_get_geohash_cell_size_overseas_territories():
    """Test cell size calculation for French overseas territories."""
    precision = 7

    # Guyane (near equator, ~5°N)
    gh_guyane = geohash_lib.encode(4.9, -52.3, precision)
    lat_guy, lon_guy = get_geohash_cell_size(gh_guyane)
    assert 0.15 < lat_guy < 0.16
    assert 0.14 < lon_guy < 0.16  # Nearly square near equator

    # Réunion (tropical, ~21°S)
    gh_reunion = geohash_lib.encode(-21.1, 55.5, precision)
    lat_reu, lon_reu = get_geohash_cell_size(gh_reunion)
    assert 0.15 < lat_reu < 0.16
    assert 0.13 < lon_reu < 0.15  # Slightly smaller

    # Polynésie française (~17°S)
    gh_poly = geohash_lib.encode(-17.5, -149.5, precision)
    lat_poly, lon_poly = get_geohash_cell_size(gh_poly)
    assert 0.15 < lat_poly < 0.16
    assert 0.14 < lon_poly < 0.16  # Nearly square


def test_calculate_geohash_layers_adapts_to_location():
    """Test that layer calculation adapts to location."""
    radius = 0.5  # 500 meters
    precision = 7

    # Near equator: cells ~0.15km square, 500m needs 1-2 layers
    gh_equator = geohash_lib.encode(0.5, 9.5, precision)
    layers_eq = calculate_geohash_layers(radius, gh_equator)
    assert layers_eq in [1, 2]

    # High latitude: lon dimension smaller, might need more layers
    # But since we use max(lat_size, lon_size), should be similar
    gh_iceland = geohash_lib.encode(65.0, -18.0, precision)
    layers_ice = calculate_geohash_layers(radius, gh_iceland)
    assert layers_ice in [1, 2]


def test_calculate_geohash_layers_small_radius():
    """Test layer calculation with small radius."""
    gh = geohash_lib.encode(48.8566, 2.3522, 7)

    # Very small radius: 1 layer
    layers = calculate_geohash_layers(0.1, gh)
    assert layers == 1

    # Medium radius: 1-2 layers
    layers = calculate_geohash_layers(0.5, gh)
    assert layers in [1, 2, 3]


def test_calculate_geohash_layers_large_radius():
    """Test layer calculation with large radius."""
    gh = geohash_lib.encode(48.8566, 2.3522, 7)

    # Large radius: 3-4 layers
    layers = calculate_geohash_layers(2.0, gh)
    assert layers in [3, 4]

    # Very large radius: max layers
    layers = calculate_geohash_layers(10.0, gh)
    assert layers == 4


def test_calculate_geohash_layers_different_precisions():
    """Test layer calculation with different geohash precisions."""
    lat, lon = 48.8566, 2.3522
    radius = 5.0  # 5 km

    # Lower precision (larger cells): fewer layers needed
    gh5 = geohash_lib.encode(lat, lon, 5)
    layers5 = calculate_geohash_layers(radius, gh5)
    assert layers5 <= 2

    # Default precision: more layers
    gh7 = geohash_lib.encode(lat, lon, 7)
    layers7 = calculate_geohash_layers(radius, gh7)
    assert layers7 == 4

    # Higher precision (smaller cells): max layers
    gh8 = geohash_lib.encode(lat, lon, 8)
    layers8 = calculate_geohash_layers(radius, gh8)
    assert layers8 == 4
