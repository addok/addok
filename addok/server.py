import codecs
import csv
import io
import json
import logging
import logging.handlers
import os

from pathlib import Path

from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response

from .core import reverse, search
from . import config

url_map = Map([
    Rule('/search/', endpoint='search'),
    Rule('/reverse/', endpoint='reverse'),
    Rule('/csv/', endpoint='csv'),
])

if config.LOG_NOT_FOUND:
    notfound = logging.getLogger('notfound')
    notfound.setLevel(logging.DEBUG)
    filename = Path(config.LOG_DIR).joinpath('notfound.log')
    notfound.addHandler(
        logging.handlers.TimedRotatingFileHandler(str(filename)))

if config.LOG_BATCH_QUERIES:
    log_queries = logging.getLogger('queries')
    log_queries.setLevel(logging.DEBUG)
    filename = Path(config.LOG_DIR).joinpath('batch_queries.log')
    log_queries.addHandler(
        logging.handlers.TimedRotatingFileHandler(str(filename)))


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
        elif endpoint == 'csv':
            response = on_csv(request)
    return response(environ, start_response)


def match_filters(request):
    filters = {}
    for name in config.FILTERS:
        value = request.args.get(name)
        if value:
            filters[name] = value
    return filters


def on_search(request):
    query = request.args.get('q', '')
    if not query:
        response = Response('Missing query', status=400)
        cors(response)
        return response
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
    filters = match_filters(request)
    results = search(query, limit=limit, autocomplete=autocomplete, lat=lat,
                     lon=lon, **filters)
    if config.LOG_NOT_FOUND and not results:
        notfound.debug(query)
    return serve_results(results, query=query)


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
    filters = match_filters(request)
    results = reverse(lat=lat, lon=lon, limit=limit, **filters)
    return serve_results(results)


def serve_results(results, query=None):
    results = {
        "type": "FeatureCollection",
        "version": "draft",
        "features": [r.to_geojson() for r in results],
        "attribution": config.ATTRIBUTION,
        "licence": config.LICENCE,
    }
    if query:
        results['query'] = query
    response = Response(json.dumps(results), mimetype='text/plain')
    cors(response)
    return response


def on_csv(request):
    if request.method == 'POST':
        f = request.files['data']
        dialect = csv.Sniffer().sniff(f.read(4096).decode())
        # Escape double quotes with double quotes if needed.
        # See 2.7 in http://tools.ietf.org/html/rfc4180
        dialect.doublequote = True
        f.seek(0)
        # Replace bad carriage returns, as per
        # http://tools.ietf.org/html/rfc4180
        # We may want not to load all file in memory at some point.
        content = f.read().decode().replace('\r', '').replace('\n', '\r\n')
        # Keep ends, not to glue lines when a field is multilined.
        rows = csv.DictReader(content.splitlines(keepends=True),
                              dialect=dialect)
        fieldnames = rows.fieldnames[:]
        columns = request.form.getlist('columns') or rows.fieldnames
        for key in ['latitude', 'longitude', 'result_address', 'result_score',
                    'result_type', 'result_id']:
            if key not in fieldnames:
                fieldnames.append(key)
        output = io.StringIO()
        # Make Excel happy with UTF-8
        output.write(codecs.BOM_UTF8.decode('utf-8'))
        writer = csv.DictWriter(output, fieldnames, dialect=dialect)
        writer.writeheader()
        for row in rows:
            # We don't want None in a join.
            q = ' '.join([row[k] or '' for k in columns])
            if config.LOG_BATCH_QUERIES:
                log_queries.debug(q)
            results = search(q, autocomplete=False, limit=1)
            if results:
                row.update({
                    'latitude': results[0].lat,
                    'longitude': results[0].lon,
                    'result_address': str(results[0]),
                    'result_score': round(results[0].score, 2),
                    'result_type': results[0].type,
                    'result_id': results[0].id,
                })
            elif config.LOG_NOT_FOUND:
                notfound.debug(q)
            writer.writerow(row)
        output.seek(0)
        response = Response(output.read())
        filename, ext = os.path.splitext(f.filename)
        attachment = 'attachment; filename="{name}.geocoded.csv"'.format(
                                                                 name=filename)
        response.headers['Content-Disposition'] = attachment
        response.headers['Content-Type'] = 'text/csv'
        cors(response)
        return response
    elif request.method == 'OPTIONS':
        response = Response('')
        cors(response)
        return response


def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
