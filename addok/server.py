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
    Rule('/search/csv/', endpoint='search.csv'),
    Rule('/reverse/csv/', endpoint='reverse.csv'),
    Rule('/csv/', endpoint='search.csv'),  # Retrocompat.
], strict_slashes=False)

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
    urls = url_map.bind_to_environ(environ)
    try:
        endpoint, args = urls.match()
        request = Request(environ)
        response = View.serve(endpoint, request)
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

    def __init__(self, request):
        self.request = request

    def match_filters(self):
        filters = {}
        for name in config.FILTERS:
            value = self.request.args.get(name)
            if value:
                filters[name] = value
        return filters

    @classmethod
    def serve(cls, endpoint, request):
        Class = WithEndPoint.endpoints.get(endpoint)
        if not Class:
            raise BadRequest()
        view = Class(request)
        if request.method == 'POST' and hasattr(view, 'post'):
            response = view.post()
        elif view.request.method == 'GET' and hasattr(view, 'get'):
            response = view.get()
        elif view.request.method == 'OPTIONS':
            response = view.options()
        else:
            raise BadRequest()
        return cls.cors(response)

    def to_geojson(self, results, query=None):
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
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    def options(self):
        return Response('')

    @staticmethod
    def cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
        return response


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
            autocomplete = int(self.request.args.get('autocomplete')) == '1'
        except (ValueError, TypeError):
            autocomplete = True
        try:
            lat = float(self.request.args.get('lat'))
            lon = float(self.request.args.get('lon'))
        except (ValueError, TypeError):
            lat = None
            lon = None
        filters = self.match_filters()
        results = search(query, limit=limit, autocomplete=autocomplete,
                         lat=lat, lon=lon, **filters)
        if not results:
            log_notfound(query)
        log_query(query, results)
        return self.to_geojson(results, query=query)


class Reverse(View):

    endpoint = 'reverse'

    def get(self):
        try:
            lat = float(self.request.args.get('lat'))
            lon = float(self.request.args.get('lon'))
        except (ValueError, TypeError):
            raise BadRequest()
        try:
            limit = int(self.request.args.get('limit'))
        except (ValueError, TypeError):
            limit = 1
        filters = self.match_filters()
        results = reverse(lat=lat, lon=lon, limit=limit, **filters)
        return self.to_geojson(results)


class BaseCSV(View):

    def post(self):
        f = self.request.files['data']
        input_encoding = 'utf-8'
        output_encoding = 'utf-8'
        file_encoding = f.mimetype_params.get('charset')
        # When file_encoding is passed as charset in the file mimetype,
        # Werkzeug will reencode the content to utf-8 for us, so don't try
        # to reencode.
        if not file_encoding:
            input_encoding = self.request.form.get('encoding', input_encoding)
        try:
            extract = f.read(4096).decode(input_encoding)
        except (LookupError, UnicodeDecodeError):
            raise BadRequest('Unknown encoding {}'.format(input_encoding))
        dialect = csv.Sniffer().sniff(extract)
        # Escape double quotes with double quotes if needed.
        # See 2.7 in http://tools.ietf.org/html/rfc4180
        dialect.doublequote = True
        delimiter = self.request.form.get('delimiter')
        if delimiter:
            dialect.delimiter = delimiter
        f.seek(0)
        # Replace bad carriage returns, as per
        # http://tools.ietf.org/html/rfc4180
        # We may want not to load whole file in memory at some point.
        content = f.read().decode(input_encoding)
        content = content.replace('\r', '').replace('\n', '\r\n')
        # Keep ends, not to glue lines when a field is multilined.
        rows = csv.DictReader(content.splitlines(keepends=True),
                              dialect=dialect)
        fieldnames = rows.fieldnames[:]
        self.columns = self.request.form.getlist('columns') or rows.fieldnames
        for column in self.columns:
            if column not in fieldnames:
                raise BadRequest("Cannot found column '{}' in columns "
                                 "{}".format(column, fieldnames))
        for key in self.result_headers:
            if key not in fieldnames:
                fieldnames.append(key)
        output = io.StringIO()
        if output_encoding == 'utf-8':
            # Make Excel happy with UTF-8
            output.write(codecs.BOM_UTF8.decode('utf-8'))
        writer = csv.DictWriter(output, fieldnames, dialect=dialect)
        writer.writeheader()
        for row in rows:
            self.process_row(row)
            writer.writerow(row)
        output.seek(0)
        response = Response(output.read().encode(output_encoding))
        output.seek(0)
        filename, ext = os.path.splitext(f.filename)
        attachment = 'attachment; filename="{name}.geocoded.csv"'.format(
                                                                 name=filename)
        response.headers['Content-Disposition'] = attachment
        content_type = 'text/csv; charset={encoding}'.format(
            encoding=output_encoding)
        response.headers['Content-Type'] = content_type
        return response

    def add_fields(self, row, result):
        for field in config.FIELDS:
            if field.get('type') == 'housenumbers':
                continue
            key = field['key']
            row['result_{}'.format(key)] = getattr(result, key, '')

    @property
    def result_headers(self):
        if not hasattr(self, '_result_headers'):
            headers = []
            for field in config.FIELDS:
                if field.get('type') == 'housenumbers':
                    continue
                key = 'result_{}'.format(field['key'])
                if key not in headers:
                    headers.append(key)
            self._result_headers = self.base_headers + headers
        return self._result_headers


class CSVSearch(BaseCSV):

    endpoint = 'search.csv'
    base_headers = ['latitude', 'longitude', 'result_address', 'result_score',
                    'result_type', 'result_id']

    def process_row(self, row):
        # We don't want None in a join.
        q = ' '.join([row[k] or '' for k in self.columns])
        results = search(q, autocomplete=False, limit=1)
        log_query(q, results)
        if results:
            result = results[0]
            row.update({
                'latitude': result.lat,
                'longitude': result.lon,
                'result_address': str(result),
                'result_score': round(result.score, 2),
                'result_type': result.type,
                'result_id': result.id,
            })
            self.add_fields(row, result)
        else:
            log_notfound(q)


class CSVReverse(BaseCSV):

    endpoint = 'reverse.csv'
    base_headers = ['result_latitude', 'result_longitude', 'result_address',
                    'result_distance', 'result_type', 'result_id']

    def process_row(self, row):
        lat = row.get('latitude', row.get('lat', None))
        lon = row.get('longitude', row.get('lon', row.get('lng', None)))
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return
        results = reverse(lat=lat, lon=lon, limit=1)
        if results:
            result = results[0]
            row.update({
                'result_latitude': result.lat,
                'result_longitude': result.lon,
                'result_address': str(result),
                'result_distance': round(result.distance, 3),
                'result_type': result.type,
                'result_id': result.id,
            })
            self.add_fields(row, result)
