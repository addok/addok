import json
import logging
import logging.handlers
from pathlib import Path

from werkzeug.exceptions import BadRequest, HTTPException, NotFound
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response

from addok import hooks
from addok.core import Result, reverse, search

from . import config

if config.LOG_NOT_FOUND:
    notfound_logger = logging.getLogger('notfound')
    notfound_logger.setLevel(logging.DEBUG)
    filename = Path(config.LOG_DIR).joinpath('notfound.log')
    handler = logging.handlers.TimedRotatingFileHandler(str(filename),
                                                        when='midnight')
    notfound_logger.addHandler(handler)


def log_notfound(query):
    if config.LOG_NOT_FOUND:
        notfound_logger.debug(query)


if config.LOG_QUERIES:
    query_logger = logging.getLogger('queries')
    query_logger.setLevel(logging.DEBUG)
    filename = Path(config.LOG_DIR).joinpath('queries.log')
    handler = logging.handlers.TimedRotatingFileHandler(str(filename),
                                                        when='midnight')
    query_logger.addHandler(handler)


def log_query(query, results):
    if config.LOG_QUERIES:
        if results:
            result = str(results[0])
            score = str(round(results[0].score, 2))
        else:
            result = '-'
            score = '-'
        query_logger.debug('\t'.join([query, result, score]))


def app(environ, start_response):
    if not config.URL_MAP:
        endpoints = []
        config.pm.hook.addok_register_http_endpoints(endpoints=endpoints)
        rules = [Rule(path, endpoint=endpoint) for path, endpoint in endpoints]
        config.URL_MAP = Map(rules, strict_slashes=False)
    urls = config.URL_MAP.bind_to_environ(environ)
    try:
        endpoint, kwargs = urls.match()
        request = Request(environ)
        response = View.serve(endpoint, request, **kwargs)
    except HTTPException as e:
        return e(environ, start_response)
    else:
        return response(environ, start_response)


class WithEndPoint(type):

    endpoints = {}

    def __new__(mcs, name, bases, attrs, **kwargs):
        cls = super().__new__(mcs, name, bases, attrs)
        if hasattr(cls, 'endpoint'):
            mcs.endpoints[cls.endpoint] = cls
        return cls


class View(object, metaclass=WithEndPoint):

    config = config

    def __init__(self, request):
        self.request = request

    def match_filters(self):
        filters = {}
        for name in config.FILTERS:
            value = self.request.args.get(name, self.request.form.get(name))
            if value:
                filters[name] = value
        return filters

    @classmethod
    def serve(cls, endpoint, request, **kwargs):
        Class = WithEndPoint.endpoints.get(endpoint)
        if not Class:
            raise BadRequest()
        view = Class(request)
        if request.method == 'POST' and hasattr(view, 'post'):
            response = view.post(**kwargs)
        elif view.request.method == 'GET' and hasattr(view, 'get'):
            response = view.get(**kwargs)
        elif view.request.method == 'OPTIONS':
            response = view.options(**kwargs)
        else:
            raise BadRequest()
        if isinstance(response, tuple):
            response = Response(*response)
        elif isinstance(response, str):
            response = Response(response)
        return cls.cors(response)

    def to_geojson(self, results, query=None, filters=None, center=None,
                   limit=None):
        results = {
            "type": "FeatureCollection",
            "version": "draft",
            "features": [r.to_geojson() for r in results],
            "attribution": config.ATTRIBUTION,
            "licence": config.LICENCE,
        }
        if query:
            results['query'] = query
        if filters:
            results['filters'] = filters
        if center:
            results['center'] = center
        if limit:
            results['limit'] = limit
        return self.json(results)

    def json(self, content):
        response = Response(json.dumps(content), mimetype='text/plain')
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    def options(self):
        return Response('')

    @staticmethod
    def cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
        return response


class Get(View):

    endpoint = 'get'

    def get(self, doc_id):
        try:
            result = Result.from_id(doc_id)
        except ValueError:
            raise NotFound()
        else:
            return self.json(result.to_geojson())


class Search(View):

    endpoint = 'search'

    def get(self):
        query = self.request.args.get('q', '')
        if not query:
            return Response('Missing query', status=400)
        try:
            limit = int(self.request.args.get('limit'))
        except (ValueError, TypeError):
            limit = 5
        try:
            autocomplete = int(self.request.args.get('autocomplete')) == 1
        except (ValueError, TypeError):
            autocomplete = True
        try:
            lat = float(self.request.args.get('lat'))
            lon = float(self.request.args.get('lon',
                        self.request.args.get('lng',
                        self.request.args.get('long'))))
            center = [lat, lon]
        except (ValueError, TypeError):
            lat = None
            lon = None
            center = None
        filters = self.match_filters()
        results = search(query, limit=limit, autocomplete=autocomplete,
                         lat=lat, lon=lon, **filters)
        if not results:
            log_notfound(query)
        log_query(query, results)
        return self.to_geojson(results, query=query, filters=filters,
                               center=center, limit=limit)


class Reverse(View):

    endpoint = 'reverse'

    def get(self):
        try:
            lat = float(self.request.args.get('lat'))
            lon = float(self.request.args.get('lon',
                        self.request.args.get('lng')))
        except (ValueError, TypeError):
            raise BadRequest()
        try:
            limit = int(self.request.args.get('limit'))
        except (ValueError, TypeError):
            limit = 1
        filters = self.match_filters()
        results = reverse(lat=lat, lon=lon, limit=limit, **filters)
        return self.to_geojson(results, filters=filters, limit=limit)


@hooks.register
def addok_register_http_endpoints(endpoints):
    endpoints.extend([
        ('/get/<doc_id>/', 'get'),
        ('/search/', 'search'),
        ('/reverse/', 'reverse'),
    ])


@hooks.register
def addok_register_command(subparsers):
    parser = subparsers.add_parser('serve', help='Run debug server')
    parser.set_defaults(func=run)
    parser.add_argument('--host', default='127.0.0.1',
                        help='Host to expose the demo serve on')
    parser.add_argument('--port', action='store_const', default=7878,
                        const=int,
                        help='Port to expose the demo server on')


def run(args):
    from werkzeug.serving import run_simple
    run_simple(args.host, int(args.port), app, use_debugger=True,
               use_reloader=True)
