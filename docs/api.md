# API

Addok exposes an very minimal WSGI interface, you can run it with gunicorn
for example:

    gunicorn addok.server:app

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

The response format follows the [GeoCodeJSON spec](https://github.com/yohanboniface/geocodejson-spec).
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

Same response format as the `/search/` enpoint.


### /search/csv/

Batch geocode a csv file.

#### Parameters

- **data**: csv file to be processed
- **columns**: define the columns of the csv to be concatenated to create the
  search string (one column by `columns` parameter; default: all file columns are used)
- **encoding** (optional): encoding of the file (you can also specify a `charset` in the
  file mimetype), such as 'utf-8' or 'iso-8859-1'
- **delimiter** (optional): CSV delimiter
- every filter that has been declared in the [config](config.md) is available as
  parameter, and you must give the column name to use as value; for example, if you want
  to filter by 'postcode' and you have a column 'code postal' containing the post code of each row,
  you will pass `postcode=code postal` and every row will be filtered according to the value of 'code postal'
  column
- `lat` and `lon` parameters, like filters, can be used to define columns names that contain latitude and longitude
  values, for adding a preference center in the geocoding of each row

#### Examples

    http -f POST http://localhost:7878/search/csv/ columns='voie' columns='ville' data@path/to/file.csv
    http -f POST http://localhost:7878/search/csv/ columns='rue' postcode='code postal' data@path/to/file.csv

### /reverse/csv/

Batch reverse geocode a csv file.

#### Parameters

- **data**: csv file to be processed; must contain columns `latitude` (or `lat`) and
  `longitude` (or `lon` or `lng`)
- **encoding** (optional): encoding of the file (you can also specify a `charset` in the
  file mimetype), such as 'utf-8' or 'iso-8859-1'
- **delimiter** (optional): CSV delimiter
- every filter that has been declared in the [config](config.md) is available as
  parameter, and you must give the column name to use as value; for example, if you want
  to filter by 'postcode' and you have a column 'code postal' containing the post code of each row,
  you will pass `postcode=code postal` and every row will be filtered according to the value of 'code postal'
  column

### /get/&lt;doc_id&gt;/

Get a document from its id.

#### Parameters

- **doc_id**: the id of the document
