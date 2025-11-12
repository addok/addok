import json
import logging
import logging.handlers
from pathlib import Path
import time

import falcon

from addok.config import config
from addok.core import reverse, search
from addok.db import DB
from addok.helpers.text import EntityTooLarge

notfound_logger = None
query_logger = None
slow_query_logger = None


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    filename = Path(config.LOG_DIR).joinpath("{}.log".format(name))
    try:
        handler = logging.handlers.TimedRotatingFileHandler(
            str(filename), when="midnight"
        )
    except FileNotFoundError:
        print("Unable to write to {}".format(filename))
    else:
        logger.addHandler(handler)
    return logger


@config.on_load
def on_load():
    if config.LOG_NOT_FOUND:
        global notfound_logger
        notfound_logger = get_logger("notfound")

    if config.LOG_QUERIES:
        global query_logger
        query_logger = get_logger("queries")

    if config.SLOW_QUERIES:
        global slow_query_logger
        slow_query_logger = get_logger("slow_queries")


def log_notfound(query):
    if config.LOG_NOT_FOUND:
        notfound_logger.debug(query)


def log_query(query, results):
    if config.LOG_QUERIES:
        if results:
            result = str(results[0])
            score = str(round(results[0].score, 2))
        else:
            result = "-"
            score = "-"
        query_logger.debug("\t".join([query, result, score]))


def log_slow_query(query, results, timer):
    if config.SLOW_QUERIES:
        if results:
            result = str(results[0])
            score = str(round(results[0].score, 2))
            id_ = results[0].id
        else:
            result = "-"
            score = "-"
            id_ = "-"
        slow_query_logger.debug("\t".join([str(timer), query, id_, result, score]))


class CorsMiddleware:
    def process_response(self, req, resp, resource, req_succeeded):
        resp.set_header("Access-Control-Allow-Origin", "*")
        resp.set_header("Access-Control-Allow-Headers", "X-Requested-With")


class View:

    config = config

    def match_filters(self, req):
        """Parse filter parameters from HTTP request.
        
        Handles both single and multi-value filters, converting them to lists.
        If FILTERS_MULTI_VALUE_SEPARATOR is set, also splits string values.
        
        Returns:
            Dict with filter names as keys and lists of values
            (e.g., {"type": ["street", "city"]})
        """
        filters = {}
        separator = config.FILTERS_MULTI_VALUE_SEPARATOR
        
        for name in config.FILTERS:
            # Get all values for this parameter (e.g., ?type=street&type=city)
            values = req.get_param_as_list(name)
            
            if not values:
                continue
            
            # If separator is configured, also split individual values
            # (e.g., ?type=street city → ["street", "city"])
            if separator:
                expanded_values = []
                for value in values:
                    if separator in value:
                        expanded_values.extend(v.strip() for v in value.split(separator) if v.strip())
                    else:
                        expanded_values.append(value.strip())
                filters[name] = expanded_values
            else:
                # No separator: keep all values from multi-parameters, strip whitespace
                filters[name] = [v.strip() for v in values if v.strip()]
        
        return filters

    def render(
        self, req, resp, results, query=None, filters=None, center=None, limit=None
    ):
        results = {
            "type": "FeatureCollection",
            "version": "draft",
            "features": [r.format() for r in results],
            "attribution": config.ATTRIBUTION,
            "licence": config.LICENCE,
        }
        if query:
            results["query"] = query
        if filters:
            results["filters"] = filters
        if center:
            results["center"] = center
        if limit:
            results["limit"] = limit
        self.json(req, resp, results)

    to_geojson = render  # retrocompat.

    def json(self, req, resp, content):
        resp.text = json.dumps(content)
        resp.content_type = "application/json; charset=utf-8"

    def parse_float(sel, req, *keys):
        try:
            for key in keys:
                val = req.get_param(key)
                if val is not None:
                    return float(val)
        except (ValueError, TypeError):
            raise falcon.HTTPInvalidParam("invalid value", key)
        return None

    def parse_lon_lat(self, req):
        lat = self.parse_float(req, "lat", "latitude")
        lon = self.parse_float(req, "lon", "lng", "long", "longitude")

        if lon and (lon > 180 or lon < -180):
            raise falcon.HTTPInvalidParam("out of range", "lon")
        elif lat and (lat > 90 or lat < -90):
            raise falcon.HTTPInvalidParam("out of range", "lat")
        return lon, lat


class Search(View):
    def on_get(self, req, resp, **kwargs):
        query = req.get_param("q")
        if not query:
            raise falcon.HTTPMissingParam("q")
        limit = req.get_param_as_int("limit") or 5  # use config
        if limit < 1 or limit > 100:
            raise falcon.HTTPInvalidParam("out of range (1..100)", "limit")
        autocomplete = req.get_param_as_bool("autocomplete")
        if autocomplete is None:
            # Default is True.
            # https://github.com/falconry/falcon/pull/493#discussion_r44376219
            autocomplete = True
        lon, lat = self.parse_lon_lat(req)
        center = None
        if lon and lat:
            center = (lon, lat)
        filters = self.match_filters(req)
        timer = time.perf_counter()
        try:
            results = search(
                query,
                limit=limit,
                autocomplete=autocomplete,
                lat=lat,
                lon=lon,
                **filters
            )
        except EntityTooLarge as e:
            raise falcon.HTTPContentTooLarge(title=str(e))
        timer = int((time.perf_counter() - timer) * 1000)
        if not results:
            log_notfound(query)
        log_query(query, results)
        if config.SLOW_QUERIES and timer > config.SLOW_QUERIES:
            log_slow_query(query, results, timer)
        self.render(
            req, resp, results, query=query, filters=filters, center=center, limit=limit
        )


class Reverse(View):
    def on_get(self, req, resp, **kwargs):
        lon, lat = self.parse_lon_lat(req)
        if lon is None:
            raise falcon.HTTPMissingParam("lon")
        if lat is None:
            raise falcon.HTTPMissingParam("lat")
        limit = req.get_param_as_int("limit") or 1
        filters = self.match_filters(req)
        results = reverse(lat=lat, lon=lon, limit=limit, **filters)
        self.render(req, resp, results, filters=filters, limit=limit)


class Health(View):
    def on_get(self, req, resp):
        return self.json(
            req,
            resp,
            {"status": "HEALTHY", "redis_version": DB.info().get("redis_version")},
        )


def register_http_endpoint(api):
    api.add_route("/search", Search())
    api.add_route("/reverse", Reverse())
    api.add_route("/health", Health())


def register_command(subparsers):
    parser = subparsers.add_parser("serve", help="Run debug server")
    parser.set_defaults(func=run)
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to expose the demo serve on"
    )
    parser.add_argument(
        "--port", default="7878", help="Port to expose the demo server on"
    )


def run(args):
    # Do not import at load time for preventing config import loop.
    from .wsgi import simple

    simple(args)
