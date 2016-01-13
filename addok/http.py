import json
import logging
import logging.handlers
from pathlib import Path

import falcon

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


class CorsMiddleware:

    def process_response(self, req, resp, resource):
        resp.set_header('Access-Control-Allow-Origin', '*')
        resp.set_header('Access-Control-Allow-Headers', 'X-Requested-With')


api = application = falcon.API(middleware=[CorsMiddleware()])


class WithEndPoint(type):

    endpoints = {}

    def __new__(mcs, name, bases, attrs, **kwargs):
        cls = super().__new__(mcs, name, bases, attrs)
        if hasattr(cls, 'url'):
            api.add_route(cls.url, cls())
        return cls


class View(object, metaclass=WithEndPoint):

    config = config

    def match_filters(self, req):
        filters = {}
        for name in config.FILTERS:
            req.get_param(name, store=filters)
        return filters

    def to_geojson(self, req, resp, results, query=None, filters=None,
                   center=None, limit=None):
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
        self.json(req, resp, results)

    def json(self, req, resp, content):
        resp.body = json.dumps(content)
        resp.content_type = 'application/json; charset=utf-8'

    def parse_lon_lat(self, req):
        try:
            lat = float(req.get_param('lat'))
            for key in ('lon', 'lng', 'long'):
                lon = req.get_param(key)
                if lon is not None:
                    lon = float(lon)
                    break
        except (ValueError, TypeError):
            lat = None
            lon = None
        return lon, lat


class Get(View):

    url = '/get/{doc_id}'

    def on_get(self, req, resp, doc_id, **kwargs):
        try:
            result = Result.from_id(doc_id)
        except ValueError:
            raise falcon.HTTPNotFound()
        else:
            self.json(req, resp, result.to_geojson())


class Search(View):

    url = '/search'

    def on_get(self, req, resp, **kwargs):
        query = req.get_param('q')
        if not query:
            raise falcon.HTTPBadRequest('Missing query', 'Missing query')
        limit = req.get_param_as_int('limit') or 5  # use config
        autocomplete = req.get_param_as_bool('autocomplete')
        lon, lat = self.parse_lon_lat(req)
        center = None
        if lon and lat:
            center = (lon, lat)
        filters = self.match_filters(req)
        results = search(query, limit=limit, autocomplete=autocomplete,
                         lat=lat, lon=lon, **filters)
        if not results:
            log_notfound(query)
        log_query(query, results)
        self.to_geojson(req, resp, results, query=query, filters=filters,
                        center=center, limit=limit)


class Reverse(View):

    url = '/reverse'

    def on_get(self, req, resp, **kwargs):
        lon, lat = self.parse_lon_lat(req)
        if lon is None or lat is None:
            raise falcon.HTTPBadRequest('Invalid args', 'Invalid args')
        limit = req.get_param_as_int('limit') or 1
        filters = self.match_filters(req)
        results = reverse(lat=lat, lon=lon, limit=limit, **filters)
        self.to_geojson(req, resp, results, filters=filters, limit=limit)


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
    from wsgiref.simple_server import make_server
    httpd = make_server(args.host, int(args.port), application)
    print("Serving HTTP on {}:{}...".format(args.host, args.port))
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, EOFError):
        print('Bye!')
