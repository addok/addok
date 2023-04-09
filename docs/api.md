# API

Addok exposes an very minimal WSGI interface, you can run it with gunicorn
for example:

    gunicorn addok.http.wsgi

For debug, you can run the simple Werkzeug server:

    addok serve

## Endpoints

### /search/

Issue a full text search.

#### Parameters

- **q** *(required)*: string to be searched
- **limit**: limit the number of results (default: 5)
- **autocomplete**: activate or deactivate the autocompletion (default: 1)
- **lat**/**lon**: define a center for giving priority to results close to this
  center (**lng** is also accepted instead of **lon**)
- every filter that has been declared in the [config](config.md) is available as
  parameters

#### Response format

The response format follows the [GeoCodeJSON spec](https://github.com/geocoders/geocodejson-spec).
Here is an example:

```
{
    "attribution": "BANO",
    "licence": "ODbL",
    "query": "8 bd du port",
    "type": "FeatureCollection",
    "version": "draft",
    "features": [
        {
            "properties":
            {
                "context": "80, Somme, Picardie",
                "housenumber": "8",
                "label": "8 Boulevard du Port 80000 Amiens",
                "postcode": "80000",
                "id": "800216590L",
                "score": 0.3351181818181818,
                "name": "8 Boulevard du Port",
                "city": "Amiens",
                "type": "housenumber"
            },
            "geometry":
            {
                "type": "Point",
                "coordinates": [2.29009, 49.897446]
            },
            "type": "Feature"
        },
        {
            "properties":
            {
                "context": "34, H\u00e9rault, Languedoc-Roussillon",
                "housenumber": "8",
                "label": "8 Boulevard du Port 34140 M\u00e8ze",
                "postcode": "34140",
                "id": "341570770U",
                "score": 0.3287575757575757,
                "name": "8 Boulevard du Port",
                "city": "M\u00e8ze",
                "type": "housenumber"
            },
            "geometry":
            {
                "type": "Point",
                "coordinates": [3.605875, 43.425232]
            },
            "type": "Feature"
        }
    ]
}
```

### /reverse/

Issue a reverse geocoding.

Parameters:

- **lat**/**lon** *(required)*: center to reverse geocode (**lng** is also
  accepted instead of **lon**)
- every filter that has been declared in the [config](config.md) is available as
  parameters

Same response format as the `/search/` endpoint.
