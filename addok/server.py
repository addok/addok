import json

from werkzeug.exceptions import HTTPException, BadRequest
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response

from .core import search, reverse

url_map = Map([
    Rule('/search/', endpoint='search'),
    Rule('/reverse/', endpoint='reverse'),
])


def app(environ, start_response):
    urls = url_map.bind_to_environ(environ)
    try:
        endpoint, args = urls.match()
    except HTTPException as e:
        return e(environ, start_response)
    else:
        request = Request(environ)
        if endpoint == 'search':
            response = on_search(request)
        elif endpoint == 'reverse':
            response = on_reverse(request)
    return response(environ, start_response)


def on_search(request):
    query = request.args.get('q', '')
    try:
        limit = int(request.args.get('limit'))
    except (ValueError, TypeError):
        limit = 5
    try:
        autocomplete = int(request.args.get('autocomplete')) == '1'
    except (ValueError, TypeError):
        autocomplete = True
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (ValueError, TypeError):
        lat = None
        lon = None
    results = search(query, limit=limit, autocomplete=autocomplete, lat=lat,
                     lon=lon)
    return serve_results(results)


def on_reverse(request):
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (ValueError, TypeError):
        raise BadRequest()
    try:
        limit = int(request.args.get('limit'))
    except (ValueError, TypeError):
        limit = 1
    results = reverse(lat=lat, lon=lon, limit=limit)
    return serve_results(results)


def serve_results(results):
    results = {
        "type": "FeatureCollection",
        "features": [r.to_geojson() for r in results]
    }
    response = Response(json.dumps(results), mimetype='text/plain')
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
    return response
