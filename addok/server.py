import json

from werkzeug.wrappers import Request, Response

from .core import search


def app(environ, start_response):
    request = Request(environ)
    query = request.args.get('q', '')
    try:
        limit = int(request.args.get('limit'))
    except ValueError:
        limit = 5
    try:
        autocomplete = int(request.args.get('autocomplete')) == '1'
    except (ValueError, TypeError):
        autocomplete = True
    results = search(query, limit=limit, autocomplete=autocomplete)
    results = {
        "type": "FeatureCollection",
        "features": [r.to_geojson() for r in results]
    }
    response = Response(json.dumps(results), mimetype='text/plain')
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
    return response(environ, start_response)
