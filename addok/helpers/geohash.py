"""Geohash-related helper functions for geographic search operations."""

from functools import lru_cache

import geohash

from addok.config import config
from addok.db import DB
from addok.helpers import haversine_distance, keys as dbkeys


@lru_cache(maxsize=128)
def get_geohash_cell_size(geoh):
    """Calculate the actual dimensions of a geohash cell in kilometers.
    
    Uses the geohash bounding box and Haversine formula to compute
    the real dimensions of the cell at its specific latitude.
    
    Args:
        geoh: Geohash string
    
    Returns:
        tuple: (lat_size_km, lon_size_km) - cell dimensions in kilometers
    
    Note:
        The latitude dimension is relatively constant globally (~111km per degree),
        but the longitude dimension varies with latitude due to the Earth's curvature,
        becoming smaller near the poles.
        
        This function is cached for performance since the calculation involves
        expensive trigonometric operations (Haversine formula). Cache hits provide
        ~50-100x speedup for frequently queried locations.
    """
    bbox = geohash.bbox(geoh)
    
    # Calculate latitude dimension (north-south)
    lat_size_km = haversine_distance((bbox['s'], bbox['w']), (bbox['n'], bbox['w']))
    
    # Calculate longitude dimension (east-west)
    lon_size_km = haversine_distance((bbox['s'], bbox['w']), (bbox['s'], bbox['e']))
    
    return lat_size_km, lon_size_km


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
            # Calculate number of layers based on actual cell size at this location
            layers = calculate_geohash_layers(radius_km, geoh)
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


def calculate_geohash_layers(radius_km, geoh):
    """Calculate the number of geohash neighbor layers needed for a given radius.

    Args:
        radius_km: Desired radius in kilometers
        geoh: Geohash string (used to determine cell size at this location)

    Returns:
        Number of layers (1-4) to cover approximately the requested radius

    Notes:
        This function calculates the actual cell dimensions at the geohash's
        specific latitude using geohash.bbox() and the Haversine formula.
        This ensures accurate radius coverage regardless of location:
        
        - Near equator: cells are roughly square
        - Near poles: longitude dimension becomes much smaller
        - Works globally: France, overseas territories, other countries
        
        Each layer adds approximately 2 * cell_size to the radius:
        - Layer 1: ~3 * cell_size radius (center + 8 neighbors)
        - Layer 2: ~5 * cell_size radius (+ 16 more neighbors)
        - Layer 3: ~7 * cell_size radius (+ 24 more neighbors)
        - Layer 4: ~9 * cell_size radius (+ 32 more neighbors)
    """
    # Get actual cell dimensions at this location
    lat_size_km, lon_size_km = get_geohash_cell_size(geoh)
    
    # Use the maximum dimension for conservative coverage
    # (ensures we cover the requested radius in all directions)
    cell_size = max(lat_size_km, lon_size_km)

    # Calculate number of layers needed
    # Each layer expands the coverage by roughly 2 * cell_size
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
