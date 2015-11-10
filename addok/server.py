import codecs
import csv
import io
import json
import logging
import logging.handlers
import os
from pathlib import Path

from werkzeug.exceptions import BadRequest, HTTPException, NotFound
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response

from . import config
from .core import Result, reverse, search

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
    # Hook for plugins to register themselves.
    if hasattr(config, 'ON_LOAD'):
        config.ON_LOAD()

    if not config.URL_MAP:
        rules = [Rule(path, endpoint=endpoint) for path, endpoint in config.API_ENDPOINTS]  # noqa
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


class BaseCSV(View):

    MISSING_DELIMITER_MSG = ('Unable to sniff delimiter, please add one with '
                             '"delimiter" parameter.')

    def compute_encodings(self):
        self.input_encoding = 'utf-8'
        self.output_encoding = 'utf-8'
        file_encoding = self.f.mimetype_params.get('charset')
        # When file_encoding is passed as charset in the file mimetype,
        # Werkzeug will reencode the content to utf-8 for us, so don't try
        # to reencode.
        if not file_encoding:
            self.input_encoding = self.request.form.get('encoding',
                                                        self.input_encoding)

    def compute_content(self):

        # Replace bad carriage returns, as per
        # http://tools.ietf.org/html/rfc4180
        # We may want not to load whole file in memory at some point.
        self.content = self.f.read().decode(self.input_encoding)
        self.content = self.content.replace('\r', '').replace('\n', '\r\n')
        self.f.seek(0)

    def compute_dialect(self):
        try:
            extract = self.f.read(4096).decode(self.input_encoding)
        except (LookupError, UnicodeDecodeError):
            raise BadRequest('Unknown encoding {}'.format(self.input_encoding))
        try:
            dialect = csv.Sniffer().sniff(extract)
        except csv.Error:
            dialect = csv.unix_dialect()
        self.f.seek(0)

        # Escape double quotes with double quotes if needed.
        # See 2.7 in http://tools.ietf.org/html/rfc4180
        dialect.doublequote = True
        delimiter = self.request.form.get('delimiter')
        if delimiter:
            dialect.delimiter = delimiter

        # See https://github.com/etalab/addok/issues/90#event-353675239
        # and http://bugs.python.org/issue2078:
        # one column files will end up with non-sense delimiters.
        if dialect.delimiter.isalnum():
            # We guess we are in one column file, let's try to use a character
            # that will not be in the file content.
            for char in '|~^°':
                if char not in self.content:
                    dialect.delimiter = char
                    break
            else:
                raise BadRequest(self.MISSING_DELIMITER_MSG)

        self.dialect = dialect

    def compute_rows(self):
        # Keep ends, not to glue lines when a field is multilined.
        self.rows = csv.DictReader(self.content.splitlines(keepends=True),
                                   dialect=self.dialect)

    def compute_fieldnames(self):
        self.fieldnames = self.rows.fieldnames[:]
        self.columns = self.request.form.getlist('columns') or self.rows.fieldnames  # noqa
        for column in self.columns:
            if column not in self.fieldnames:
                raise BadRequest("Cannot found column '{}' in columns "
                                 "{}".format(column, self.fieldnames))
        for key in self.result_headers:
            if key not in self.fieldnames:
                self.fieldnames.append(key)

    def compute_output(self):
        self.output = io.StringIO()

    def compute_writer(self):
        if (self.output_encoding == 'utf-8'
                and self.request.form.get('with_bom')):
            # Make Excel happy with UTF-8
            self.output.write(codecs.BOM_UTF8.decode('utf-8'))
        self.writer = csv.DictWriter(self.output, self.fieldnames,
                                     dialect=self.dialect)
        self.writer.writeheader()

    def compute_filters(self):
        self.filters = self.match_filters()

    def process_rows(self):
        for row in self.rows:
            self.process_row(row)
            self.writer.writerow(row)
        self.output.seek(0)

    def compute_response(self):
        self.response = Response(
                            self.output.read().encode(self.output_encoding))
        filename, ext = os.path.splitext(self.f.filename)
        attachment = 'attachment; filename="{name}.geocoded.csv"'.format(
                                                                 name=filename)
        self.response.headers['Content-Disposition'] = attachment
        content_type = 'text/csv; charset={encoding}'.format(
            encoding=self.output_encoding)
        self.response.headers['Content-Type'] = content_type

    def post(self):
        self.f = self.request.files['data']
        self.compute_encodings()
        self.compute_content()
        self.compute_dialect()
        self.compute_rows()
        self.compute_fieldnames()
        self.compute_output()
        self.compute_writer()
        self.compute_filters()
        self.process_rows()
        self.compute_response()
        return self.response

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

    def match_row_filters(self, row):
        return {k: row.get(v) for k, v in self.filters.items()}


class CSVSearch(BaseCSV):

    endpoint = 'search.csv'
    base_headers = ['latitude', 'longitude', 'result_label', 'result_score',
                    'result_type', 'result_id', 'result_housenumber']

    def process_row(self, row):
        # We don't want None in a join.
        q = ' '.join([row[k] or '' for k in self.columns])
        filters = self.match_row_filters(row)
        lat_column = self.request.form.get('lat')
        lon_column = self.request.form.get('lon')
        if lon_column and lat_column:
            lat = row.get(lat_column)
            lon = row.get(lon_column)
            if lat and lon:
                filters['lat'] = float(lat)
                filters['lon'] = float(lon)
        results = search(q, autocomplete=False, limit=1, **filters)
        log_query(q, results)
        if results:
            result = results[0]
            row.update({
                'latitude': result.lat,
                'longitude': result.lon,
                'result_label': str(result),
                'result_score': round(result.score, 2),
                'result_type': result.type,
                'result_id': result.id,
                'result_housenumber': result.housenumber,
            })
            self.add_fields(row, result)
        else:
            log_notfound(q)


class CSVReverse(BaseCSV):

    endpoint = 'reverse.csv'
    base_headers = ['result_latitude', 'result_longitude', 'result_label',
                    'result_distance', 'result_type', 'result_id',
                    'result_housenumber']

    def process_row(self, row):
        lat = row.get('latitude', row.get('lat', None))
        lon = row.get('longitude', row.get('lon', row.get('lng', row.get('long',None))))
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return
        filters = self.match_row_filters(row)
        results = reverse(lat=lat, lon=lon, limit=1, **filters)
        if results:
            result = results[0]
            row.update({
                'result_latitude': result.lat,
                'result_longitude': result.lon,
                'result_label': str(result),
                'result_distance': int(result.distance),
                'result_type': result.type,
                'result_id': result.id,
                'result_housenumber': result.housenumber,
            })
            self.add_fields(row, result)
