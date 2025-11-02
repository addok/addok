# Geographic Boost Control

## Overview

The `geo_boost` parameter allows fine-grained control over how geographic coordinates (lat/lon) influence search results when a center point is provided.

## Problem Solved

Previously, when searching with a center point (e.g., in Paris) for common street names like "rue victor hugo", results could be dominated by distant locations with higher importance scores, even when nearby matches existed. The geographic scoring alone (10% weight) wasn't sufficient to prioritize local results.

## API Parameters

### `geo_boost`

Controls how the provided center point is used in the search.

**Values:**
- `score` (default): Center used only for scoring. Backward compatible behavior.
- `favor`: Strongly prioritizes nearby results by using geohash filtering when possible, with fallback to broader search if insufficient results.
- `strict`: Always filters by geohash (similar to reverse geocoding). Only returns results within ~500m radius (9 geohash cells at precision 7).

**Example:**
```
GET /search/?q=rue victor hugo&lat=48.8566&lon=2.3522&geo_boost=favor
```

### `geo_radius`

Controls the search radius in kilometers when a center point is provided. Works with all `geo_boost` modes to dynamically adjust the geographic area.

**Values:**
- Numeric value between 0 and 100 (kilometers)
- Default: `None` (uses default radius based on geohash precision)

**Behavior:**
The implementation automatically adapts to the configured `GEOHASH_PRECISION`:
- **Precision 5** (~4.9km cells): Suitable for country-level searches
- **Precision 6** (~1.2km cells): City-level searches
- **Precision 7** (~153m cells): Street-level searches (default)
- **Precision 8** (~38m cells): Building-level precision

For each precision, the system calculates the appropriate number of geohash neighbor layers to approximate the requested radius:
- **1 layer**: ~3× cell size radius (e.g., ~460m at precision 7)
- **2 layers**: ~5× cell size radius (e.g., ~765m at precision 7)
- **3 layers**: ~7× cell size radius (e.g., ~1070m at precision 7)
- **4 layers**: ~9× cell size radius (e.g., ~1370m at precision 7)

**Examples:**
```bash
# Search within 1km
GET /search/?q=restaurant&lat=48.8566&lon=2.3522&geo_radius=1.0

# Strict filter with custom radius (only results within 500m)
GET /search/?q=pharmacy&lat=48.8566&lon=2.3522&geo_boost=strict&geo_radius=0.5

# Favor nearby with wide fallback area (try 2km first)
GET /search/?q=hotel&lat=48.8566&lon=2.3522&geo_boost=favor&geo_radius=2.0
```
```
GET /search/?q=rue victor hugo&lat=48.8566&lon=2.3522&geo_boost=favor&geo_radius=5
```

## Configuration

Default behavior can be configured in your settings:

```python
# Default geo_boost mode when not specified in query
GEO_BOOST_DEFAULT = "score"  # or "favor" or "strict"

# Default radius in km (future feature)
GEO_RADIUS_DEFAULT = None
```

## Behavior Details

### Mode: `score` (default)

**When it applies:**
- All searches with lat/lon provided
- Backward compatible behavior

**How it works:**
1. Search is performed primarily on text tokens
2. Geographic filtering only applied when:
   - Only common tokens (e.g., "rue de")
   - Bucket overflow (≥100 results)
   - Autocomplete mode
3. Geographic distance adds up to 10% to final score

**Use case:** General search where geography is a preference, not a requirement.

**Example:**
```
# Search in Paris
GET /search/?q=24 avenue victor hugo&lat=48.8566&lon=2.3522

# Will find "24 avenue victor hugo" everywhere in France
# Paris results will score slightly higher due to proximity
# But if Lyon has higher importance, it might rank first
```

---

### Mode: `favor`

**When it applies:**
- Searches where nearby results should be strongly preferred
- User has a clear geographic context

**How it works:**
1. For meaningful tokens, **attempts geohash filtering first**
2. Retrieves results from ~500m radius (9 geohash cells)
3. If insufficient results (< limit), **automatically falls back** to broader search
4. Also applied in `ensure_geohash_results...` collector even without overflow

**Use case:** "Search near me" functionality, local business discovery, address lookup in known area.

**Example:**
```
# Search in Paris
GET /search/?q=rue victor hugo&lat=48.8566&lon=2.3522&geo_boost=favor&limit=10

# First tries to find 10 results within ~500m of Paris center
# If only 3 found nearby, expands to find 7 more from entire dataset
# Nearby results strongly prioritized in final ranking
```

---

### Mode: `strict`

**When it applies:**
- Searches where only nearby results are acceptable
- Mobile apps with "current location" context
- Map-based search interfaces

**How it works:**
1. **Always** filters by geohash
2. Only returns results within ~500m radius (9 geohash cells at precision 7)
3. No fallback to broader search
4. Similar to `/reverse/` endpoint behavior

**Use case:** "What's around me right now", POI search on mobile, map tile queries.

**Example:**
```
# Search in Paris
GET /search/?q=rue victor hugo&lat=48.8566&lon=2.3522&geo_boost=strict&limit=10

# ONLY returns "rue victor hugo" within ~500m of coordinates
# If none exist nearby, returns empty results
# Never returns distant matches regardless of text relevance
```

---

## Comparison Table

| Aspect | `score` | `favor` | `strict` |
|--------|---------|---------|----------|
| **Geohash filtering** | Conditional | First attempt | Always |
| **Fallback to broad search** | N/A | Yes (if dry) | No |
| **Empty results possible** | No (if matches exist) | No (due to fallback) | Yes |
| **Max distance** | Unlimited | Unlimited (after fallback) | ~500m |
| **Best for** | General search | "Near me" search | "Around me" search |
| **Backward compatible** | Yes | No | No |

## Implementation Notes

### Geohash Precision

- Default precision: 7 (configured via `GEOHASH_PRECISION`)
- At precision 7: ~153m × 153m per cell
- 9 cells (center + 8 neighbors) ≈ 500m radius
- Future: `geo_radius` parameter could dynamically adjust precision

### Performance Impact

**Mode `score`:**
- No performance change from previous behavior
- Geohash only used when necessary (overflow, commons)

**Mode `favor`:**
- Slight overhead: one additional intersection with geohash key
- Fallback search if dry adds minimal cost
- Recommended for most use cases with geographic context

**Mode `strict`:**
- Fastest mode when results exist nearby
- No fallback search = no additional queries
- May return empty faster than other modes

### Collectors Affected

1. **`bucket_with_meaningful()`**: Now checks `geo_boost_mode` and adjusts strategy
2. **`ensure_geohash_results_are_included_if_center_is_given()`**: Respects modes
3. Other collectors unchanged (commons, autocomplete, etc.)

## Migration Guide

### From Previous Version

**No changes required** - default behavior (`geo_boost=score`) matches previous implementation.

### Recommended Settings

**For address lookup service:**
```python
GEO_BOOST_DEFAULT = "score"  # Keep compatibility
```

**For mobile "search near me":**
```python
GEO_BOOST_DEFAULT = "favor"  # Prioritize nearby
```

**For map-based POI search:**
```python
GEO_BOOST_DEFAULT = "strict"  # Only show what's visible
```

## Examples

### Example 1: Tourist searching in Paris

```bash
# Without geo_boost (score mode)
curl "http://api/search/?q=notre dame&lat=48.8566&lon=2.3522&limit=5"
# Returns: Notre-Dame de Paris, Notre-Dame de Reims, Notre-Dame de Strasbourg...

# With geo_boost=favor
curl "http://api/search/?q=notre dame&lat=48.8566&lon=2.3522&limit=5&geo_boost=favor"
# Returns: Notre-Dame de Paris first, then others if available nearby

# With geo_boost=strict
curl "http://api/search/?q=notre dame&lat=48.8566&lon=2.3522&limit=5&geo_boost=strict"
# Returns: Only Notre-Dame de Paris (if within 500m of coordinates)
```

### Example 2: Address autocomplete

```bash
# User typing "24 rue vic..." in Paris
curl "http://api/search/?q=24 rue vic&lat=48.8566&lon=2.3522&autocomplete=1&geo_boost=favor"
# Suggests: "24 rue victor hugo" in Paris neighborhoods first
# Then suggests from other cities if more results needed
```

### Example 3: Finding nearest pharmacy

```bash
# Mobile app with GPS location
curl "http://api/search/?q=pharmacie&lat=48.8566&lon=2.3522&geo_boost=strict&limit=10"
# Returns: Only pharmacies within walking distance (~500m)
```

## Future Enhancements

1. **Dynamic radius**: Implement `geo_radius` parameter to control search area
2. **Adaptive fallback**: Smart expansion based on query specificity
3. **Geohash precision adjustment**: Auto-adjust precision based on radius
4. **Performance metrics**: Track mode usage and success rates

## See Also

- [API Documentation](api.md)
- [Concepts](concepts.md)
- [Configuration](config.md)
