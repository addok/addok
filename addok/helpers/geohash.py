"""Geohash-related helper functions for geographic search operations."""

from functools import lru_cache

import geohash

from addok.config import config
from addok.db import DB
from addok.helpers import keys as dbkeys


def compute_geohash_key(geoh, with_neighbors=True, radius_km=None):
    """Compute a temporary Redis key for geohash-based filtering.

    Args:
        geoh: The geohash string
        with_neighbors: If True, includes neighboring geohash cells
        radius_km: Optional radius in kilometers to determine neighbor layers
                  If None, uses single layer (8 neighbors)

    Returns:
        A temporary Redis key containing the union of all documents in the
        geohash area, or False if no documents found.

    Notes:
        The number of layers is calculated based on the configured
        GEOHASH_PRECISION and the requested radius_km:
        - Each layer adds ~(cell_size * 2) to the covered diameter
        - cell_size depends on precision (e.g., ~153m at precision 7)
    """
    if with_neighbors:
        if radius_km is not None and radius_km > 0:
            # Calculate number of layers based on precision and radius
            layers = calculate_geohash_layers(radius_km, len(geoh))
            neighbors = expand_geohash_layers(geoh, layers)
        else:
            # Default: single layer (8 neighbors + center)
            neighbors = geohash.expand(geoh)

        neighbors = [dbkeys.geohash_key(n) for n in neighbors]
    else:
        neighbors = [dbkeys.geohash_key(geoh)]

    key = "gx|{}".format(geoh)
    total = DB.sunionstore(key, neighbors)
    if not total:
        # No need to keep it.
        DB.delete(key)
        key = False
    else:
        DB.expire(key, 10)
    return key


def calculate_geohash_layers(radius_km, precision):
    """Calculate the number of geohash neighbor layers needed for a given radius.

    Args:
        radius_km: Desired radius in kilometers
        precision: Geohash precision (length of geohash string)

    Returns:
        Number of layers (1-4) to cover approximately the requested radius

    Notes:
        Approximate cell dimensions by precision (at equator):
        - precision 5: ~4.9 km × ~4.9 km
        - precision 6: ~1.2 km × ~0.61 km
        - precision 7: ~153 m × ~153 m
        - precision 8: ~38 m × ~19 m

        Each layer adds roughly (cell_size * 2) to the diameter.
        We use a conservative approach: 1 layer ≈ 3×cell_size radius coverage.
    """
    # Approximate cell size in km (latitude dimension, roughly square)
    # These are empirical values at mid-latitudes
    cell_sizes_km = {
        5: 4.9,
        6: 1.2,
        7: 0.153,
        8: 0.038,
        9: 0.0095,
    }

    # Default for unknown precisions (use precision 7 as baseline)
    cell_size = cell_sizes_km.get(precision, 0.153)

    # Each layer adds approximately 2 * cell_size to the radius
    # Layer 1: ~3 * cell_size radius (center + 8 neighbors)
    # Layer 2: ~5 * cell_size radius
    # Layer 3: ~7 * cell_size radius
    # Layer 4: ~9 * cell_size radius

    if radius_km <= 3 * cell_size:
        return 1
    elif radius_km <= 5 * cell_size:
        return 2
    elif radius_km <= 7 * cell_size:
        return 3
    else:
        return 4


@lru_cache(maxsize=128)
def expand_geohash_layers(geoh, layers=1):
    """Expand a geohash to include multiple layers of neighbors.

    Args:
        geoh: The central geohash string
        layers: Number of neighbor layers to include (1-4)

    Returns:
        Frozenset of geohash strings including center and all neighbor layers
        
    Note:
        This function is cached for performance. The result is a frozenset
        to ensure hashability for the cache.
    """
    if layers < 1:
        return frozenset([geoh])

    # Start with center
    current_layer = {geoh}
    all_cells = {geoh}

    # Add each layer
    for _ in range(layers):
        next_layer = set()
        for cell in current_layer:
            # Get all 9 cells (center + 8 neighbors) for this cell
            expanded = geohash.expand(cell)
            for neighbor in expanded:
                if neighbor not in all_cells:
                    next_layer.add(neighbor)
                    all_cells.add(neighbor)
        current_layer = next_layer

        if not current_layer:
            break

    return frozenset(all_cells)
