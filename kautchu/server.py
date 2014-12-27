import json

from werkzeug.wrappers import Request, Response

from kautchu.core import search


def app(environ, start_response):
    request = Request(environ)
    query = request.args.get('q', '')
    try:
        limit = int(request.args.get('limit'))
    except ValueError:
        limit = 5
    results = {
        "type": "FeatureCollection",
        "features": [r.to_geojson() for r in search(query, limit=limit)]
    }
    response = Response(json.dumps(results), mimetype='text/plain')
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
    return response(environ, start_response)


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', 7878, app, use_debugger=True, use_reloader=True)
