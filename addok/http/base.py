import asyncio
import json
import logging
import logging.handlers
from http import HTTPStatus
from pathlib import Path

import uvloop
from addok.config import config
from addok.core import reverse, search
from addok.helpers.text import EntityTooLarge
from roll import HttpError, Protocol, Query, Response, Roll
from roll.extensions import simple_server

asyncio.set_event_loop(uvloop.new_event_loop())
notfound_logger = None
query_logger = None


@config.on_load
def on_load():
    if config.LOG_NOT_FOUND:
        global notfound_logger
        notfound_logger = logging.getLogger('notfound')
        notfound_logger.setLevel(logging.DEBUG)
        filename = Path(config.LOG_DIR).joinpath('notfound.log')
        try:
            handler = logging.handlers.TimedRotatingFileHandler(
                str(filename), when='midnight')
        except FileNotFoundError:
            print('Unable to write to {}'.format(filename))
        else:
            notfound_logger.addHandler(handler)

    if config.LOG_QUERIES:
        global query_logger
        query_logger = logging.getLogger('queries')
        query_logger.setLevel(logging.DEBUG)
        filename = Path(config.LOG_DIR).joinpath('queries.log')
        try:
            handler = logging.handlers.TimedRotatingFileHandler(
                str(filename), when='midnight')
        except FileNotFoundError:
            print('Unable to write to {}'.format(filename))
        else:
            query_logger.addHandler(handler)


def log_notfound(query):
    if config.LOG_NOT_FOUND:
        notfound_logger.debug(query)


def log_query(query, results):
    if config.LOG_QUERIES:
        if results:
            result = str(results[0])
            score = str(round(results[0].score, 2))
        else:
            result = '-'
            score = '-'
        query_logger.debug('\t'.join([query, result, score]))


class AddokQuery(Query):

    @property
    def q(self):
        if 'q' in self:
            return self.get('q')
        else:
            raise HttpError(HTTPStatus.BAD_REQUEST, 'Missing query')

    @property
    def limit(self):
        return self.int('limit', 5)  # Use config.

    @property
    def autocomplete(self):
        return self.bool('autocomplete', True)

    @property
    def lon(self):
        for key in ('lon', 'lng', 'long'):
            try:
                return self.float(key)
            except HttpError:
                pass
        return None

    @property
    def lat(self):
        try:
            return self.float('lat')
        except HttpError:
            return None

    @property
    def filters(self):
        filters = {}
        for name in config.FILTERS:
            result = self.get(name, None)
            if result is not None:
                filters[name] = result
        return filters


class AddokResponse(Response):

    def json(self, value: dict):
        self.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.body = json.dumps(value)

    json = property(None, json)

    def to_geojson(self, results, extras):
        results = {
            'type': 'FeatureCollection',
            'version': 'draft',
            'features': [r.format() for r in results],
            'attribution': config.ATTRIBUTION,
            'licence': config.LICENCE,
        }
        results.update(**extras)
        return results


class AddokProtocol(Protocol):
    Query = AddokQuery
    Response = AddokResponse


class AddokRoll(Roll):
    Protocol = AddokProtocol


app = AddokRoll()
app.config = config


def cors(app):

    @app.listen('response')
    async def add_cors_headers(request, response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'X-Requested-With'


cors(app)


@app.route('/search')
@app.route('/search/')
async def search_view(request, response):
    needle = request.query.q
    extras = {
        'query': needle
    }
    limit = request.query.limit
    if limit:
        extras['limit'] = limit
    autocomplete = request.query.autocomplete
    lon = request.query.lon
    lat = request.query.lat
    if lon and lat:
        extras['center'] = (lon, lat)
    filters = request.query.filters
    if filters:
        extras['filters'] = filters
    try:
        results = search(needle, limit=limit, autocomplete=autocomplete,
                         lat=lat, lon=lon, **filters)
    except EntityTooLarge as e:
        raise HttpError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, str(e))
    if not results:
        log_notfound(needle)
    log_query(needle, results)
    response.json = response.to_geojson(results, extras)


@app.route('/reverse')
@app.route('/reverse/')
async def reverse_view(request, response):
    extras = {}
    lon = request.query.lon
    lat = request.query.lat
    if lon is None or lat is None:
        raise HttpError(HTTPStatus.BAD_REQUEST, 'Invalid args')
    limit = request.query.limit
    if limit:
        extras['limit'] = limit
    filters = request.query.filters
    if filters:
        extras['filters'] = filters
    results = reverse(lat=lat, lon=lon, limit=limit, **filters)
    response.json = response.to_geojson(results, extras)


def register_command(subparsers):
    parser = subparsers.add_parser('serve', help='Run debug server')
    parser.set_defaults(func=run)


def run(args):
    simple_server(app)
