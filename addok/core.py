import hashlib
import re
import uuid
import time

import geohash

from .config import config
from .db import DB
from .ds import get_document, get_documents
from .helpers import keys as dbkeys, scripts
from .helpers.text import ascii

REDIS_UNIQUE_ID = str(uuid.uuid4())  # Really unique id for tmp values in redis.


def compute_geohash_key(geoh, with_neighbors=True):
    if with_neighbors:
        neighbors = geohash.expand(geoh)
        neighbors = [dbkeys.geohash_key(n) for n in neighbors]
    else:
        neighbors = [geoh]
    key = "gx|{}".format(geoh)
    total = DB.sunionstore(key, neighbors)
    if not total:
        # No need to keep it.
        DB.delete(key)
        key = False
    else:
        DB.expire(key, 10)
    return key


class Result:
    def __init__(self, _id):
        self.housenumber = None
        self._scores = {}
        self.load(_id)
        self.labels = []

    def load(self, doc_or_id):
        self._cache = {}
        if isinstance(doc_or_id, dict):
            doc = doc_or_id
        else:
            doc = get_document(doc_or_id)
        if not doc:
            raise ValueError('id "{}" not found'.format(doc_or_id[2:]))
        self._doc = doc

    def __getattr__(self, key):
        if key == "_id":
            # result._id should load the id whatever the real field used.
            key = config.ID_FIELD
        if key not in self._cache:
            # By convention, in case of multiple values, first value is default
            # value, others are aliases.
            value = self._rawattr(key)[0]
            self._cache[key] = value
        return self._cache[key]

    def __str__(self):
        return (
            str(self.labels[0]) if self.labels else self._rawattr(config.NAME_FIELD)[0]
        )

    def _rawattr(self, key):
        value = self._doc.get(key, "")
        if not isinstance(value, (tuple, list)):
            value = [value]
        return value

    def __repr__(self):
        return "<{} - {} ({})>".format(str(self), self._id, self.score)

    @property
    def keys(self):
        keys = ["housenumber"] + list(self._doc.keys())
        # housenumbers are too verbose for a given street.
        yield from (key for key in keys if key != "housenumbers")

    def update(self, data):
        self._doc.update(data)
        self._cache.update(data)

    def format(self):
        result = self
        for formatter in config.RESULTS_FORMATTERS:
            result = formatter(result)
        return result

    def add_score(self, name, score, ceiling):
        if score >= self._scores.get(name, (0, 0))[0]:
            self._scores[name] = (score, ceiling)

    @property
    def score(self):
        if self._score != "":
            return float(self._score)
        score, _max = zip(*self._scores.values())
        return sum(score) / sum(_max)

    @score.setter
    def score(self, value):
        self._score = value

    @property
    def str_distance(self):
        return self._scores.get("str_distance", [0.0])[0]

    @classmethod
    def from_id(self, _id):
        """Return a result from it's document _id."""
        return Result(dbkeys.document_key(_id))


class BaseHelper:
    def __init__(self, verbose):
        self._start = time.time()
        self._debug = []
        if not verbose:
            self.debug = lambda *args: None

    def debug(self, *args):
        s = args[0] % args[1:]
        s = "[{}] {}".format(str((time.time() - self._start) * 1000)[:5], s)
        self._debug.append(s)

    def report(self):  # pragma: no cover
        for msg in self._debug:
            print(msg)

    def _normalize_filter_values(self, values):
        """Normalize filter values by deduplicating and sorting.

        Args:
            values: List of filter values (e.g., ["street", "city", "street"])

        Returns:
            Sorted list of unique values, limited to MAX_FILTER_VALUES
        """
        if not values:
            return []

        # Deduplicate while preserving order, then limit and sort
        # Filter after stripping to catch whitespace-only strings
        unique_values = list(dict.fromkeys(s for s in (str(v).strip() for v in values) if s))
        return sorted(unique_values[:config.MAX_FILTER_VALUES])

    def _compute_multifilter(self, filter_name, values):
        """Create temporary Redis key for OR filter using SUNIONSTORE.

        Example: type=["street", "city"] matches documents where type is "street" OR "city".
        Result is cached (10s) or persisted if large (>100k items).

        Args:
            filter_name: Filter field name (e.g., "type")
            values: List of filter values (e.g., ["street", "city"])

        Returns:
            Redis key for the combined filter
        """
        # Create a stable key based on sorted values (use | as internal separator)
        normalized_value = '|'.join(values)
        key = dbkeys.filter_key(filter_name, normalized_value)

        if not DB.exists(key):
            self.debug(f'MultiFilter created: {filter_name}={normalized_value}')
            keys = [dbkeys.filter_key(filter_name, v) for v in values]
            DB.sunionstore(key, keys)

        # Persist large filters, expire small ones
        if DB.scard(key) > 100000:
            DB.persist(key)
            self.debug(f'MultiFilter persistent: {filter_name}={normalized_value}')
        else:
            DB.expire(key, 10)

        return key

    def _build_filters(self, filters):
        """Build filter keys from list-based filter parameters.

        This method expects filter values as lists, but also accepts strings
        for backward compatibility (treated as single-value lists).
        It creates Redis keys for single or multi-value filters, and optionally
        combines multiple filters with AND logic.

        Args:
            filters: Dict with list or string values 
                     (e.g., {"type": ["street", "city"]} or {"type": "street"})

        Returns:
            List of filter keys to use in queries
        """
        filter_keys = []
        for k, v in filters.items():
            # Backward compatibility: convert string to single-value list
            if isinstance(v, str):
                v = [v]
            elif not isinstance(v, (list, tuple)):
                v = [v]

            normalized_values = self._normalize_filter_values(v)
            if not normalized_values:
                continue

            # Single value: direct filter key
            if len(normalized_values) == 1:
                filter_key = dbkeys.filter_key(k, normalized_values[0])
                filter_keys.append(filter_key)
            # Multi-value: create OR filter
            else:
                filter_key = self._compute_multifilter(k, normalized_values)
                filter_keys.append(filter_key)

        # Combine with AND logic if multiple filters
        if len(filter_keys) > 1:
            return self._combine_filters_with_keys(filter_keys)

        return filter_keys

    def _combine_filters_with_keys(self, filter_keys):
        """Combine filter keys with AND logic using Redis SINTERSTORE.

        Args:
            filter_keys: List of filter keys to combine

        Returns:
            List containing a single combined filter key
        """
        # Use a stable hash instead of repr() for the cache key
        filter_string = '|'.join(sorted(filter_keys))
        key_hash = hashlib.md5(filter_string.encode()).hexdigest()
        key = f"combined:{key_hash}"

        if not DB.exists(key):
            self.debug(f'Combined filter: {filter_string}')
            DB.sinterstore(key, filter_keys)

        DB.expire(key, 10)
        return [key]


class Search(BaseHelper):

    MAX_MEANINGFUL = 10

    def __init__(self, fuzzy=1, limit=10, autocomplete=True, verbose=False):
        super().__init__(verbose=verbose)
        self.fuzzy = fuzzy
        self.wanted = limit
        self.autocomplete = autocomplete
        self.pid = REDIS_UNIQUE_ID

    def __call__(self, query, lat=None, lon=None, **filters):
        self.lat = lat
        self.lon = lon
        self._geohash_key = None
        self.results = {}
        self.bucket = set([])  # No duplicates.
        self.meaningful = []
        self.not_found = []
        self.common = []
        self.housenumbers = []
        self.keys = []
        self.matched_keys = set([])
        self.check_housenumber = filters.get("type") in [None, "housenumber"]
        self.only_housenumber = filters.get("type") == "housenumber"
        # Build filter keys with normalized multi-value support
        self.filters = self._build_filters(filters)

        self.query = ascii(query.strip())
        for func in config.SEARCH_PREPROCESSORS:
            func(self)
        self.debug("Taken tokens: %s", self.meaningful)
        self.debug("Common tokens: %s", self.common)
        self.debug("Housenumbers token: %s", self.housenumbers)
        self.debug("Not found tokens: %s", self.not_found)

        self.debug('Filters: %s', [f'{k}={v}' for k, v in filters.items()])

        for collector in config.RESULTS_COLLECTORS:
            self.debug("** %s **", collector.__name__.upper())
            if collector(self):
                break
        return list(self.render())

    @property
    def geohash_key(self):
        if self.lat and self.lon and self._geohash_key is None:
            geoh = geohash.encode(self.lat, self.lon, config.GEOHASH_PRECISION)
            self._geohash_key = compute_geohash_key(geoh)
            if self._geohash_key:
                self.debug("Computed geohash key %s", self._geohash_key)
            else:
                self.debug("Empty geohash key, deleting %s", self._geohash_key)
        return self._geohash_key

    def render(self):
        self.convert()
        self._sorted_bucket = list(self.results.values())
        self._sorted_bucket.sort(key=lambda r: r.score, reverse=True)
        for result in self._sorted_bucket[: self.wanted]:
            if result.score < config.MIN_SCORE:
                self.debug("Score too low (%s), removing `%s`", result.score, result)
                continue
            yield result

    def intersect(self, keys, limit=0):
        if not limit > 0:
            limit = max(self.wanted, config.BUCKET_MAX)
        ids = []
        if keys:
            if self.filters:
                keys.extend(self.filters)
            if len(keys) == 1:
                key = keys[0]
                if key.startswith(dbkeys.TOKEN_PREFIX):
                    ids = DB.zrevrange(key, 0, limit - 1)
                else:
                    ids = DB.smembers(key)
            else:
                ids = scripts.zinter(keys=set(keys), args=[self.pid, limit])
        return set(ids)

    def add_to_bucket(self, keys, limit=None):
        self.debug("Adding to bucket with keys %s", keys)
        self.matched_keys.update([k for k in keys if k.startswith(dbkeys.TOKEN_PREFIX)])
        limit = limit or (config.BUCKET_MAX - len(self.bucket))
        self.bucket.update(self.intersect(keys, limit))
        self.debug("%s ids in bucket so far", len(self.bucket))

    def new_bucket(self, keys, limit=0):
        self.debug("New bucket with keys %s and limit %s", keys, limit)
        self.matched_keys = set([k for k in keys if k.startswith(dbkeys.TOKEN_PREFIX)])
        self.bucket = self.intersect(keys, limit)
        self.debug("%s ids in bucket so far", len(self.bucket))

    def convert(self):
        self.debug("Computing results")
        ids = [i for i in self.bucket if i not in self.results]
        if ids:
            documents = get_documents(*ids)
            self.debug("Done getting results data")
            for _id, doc in documents:
                result = Result(doc)
                for processor in config.SEARCH_RESULT_PROCESSORS:
                    valid = processor(self, result)
                    if valid is False:
                        break
                else:
                    self.results[_id] = result
        self.debug("Done computing results")

    @property
    def bucket_full(self):
        l = len(self.bucket)
        return l >= self.wanted and l < config.BUCKET_MAX

    @property
    def bucket_overflow(self):
        return len(self.bucket) >= config.BUCKET_MAX

    @property
    def bucket_dry(self):
        return len(self.bucket) < self.wanted

    @property
    def bucket_empty(self):
        return not self.bucket

    @property
    def cream(self):
        return len(
            [
                r
                for _id, r in self.results.items()
                if r.str_distance >= config.MATCH_THRESHOLD
            ]
        )

    def has_cream(self):
        if (
            self.bucket_empty
            or self.bucket_overflow
            or len(self.bucket) > config.BUCKET_MIN
        ):
            return False
        self.debug("Checking cream.")
        self.convert()
        return self.cream > 0

    @property
    def pass_should_match_threshold(self):
        return len(self.matched_keys) >= self.should_match_threshold

    @property
    def only_commons(self):
        return self.tokens and len(self.tokens) == len(self.common)


class Reverse(BaseHelper):
    def __call__(self, lat, lon, limit=1, **filters):
        self.lat = lat
        self.lon = lon
        self.keys = set([])
        self.results = []
        self.wanted = limit
        self.fetched = []
        self.check_housenumber = filters.get("type") in [None, "housenumber"]
        self.only_housenumber = filters.get("type") == "housenumber"
        # Build filter keys with normalized multi-value support
        self.filters = self._build_filters(filters)
        self.debug('Filters: %s', [f'{k}={v}' for k, v in filters.items()])
        geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
        hashes = self.expand([geoh])
        self.fetch(hashes)
        if not self.keys:
            hashes = self.expand(hashes)
            self.fetch(hashes)
        return self.convert()

    def expand(self, hashes):
        new = []
        for h in hashes:
            neighbors = geohash.expand(h)
            for n in neighbors:
                if n not in self.fetched:
                    new.append(n)
        return new

    def fetch(self, hashes):
        self.debug("Fetching %s", hashes)
        for h in hashes:
            k = dbkeys.geohash_key(h)
            self.intersect(k)
            self.fetched.append(h)

    def intersect(self, key):
        if self.filters:
            keys = DB.sinter([key] + self.filters)
        else:
            keys = DB.smembers(key)
        self.keys.update(keys)

    def convert(self):
        for _id in self.keys:
            result = Result(_id)
            for processor in config.REVERSE_RESULT_PROCESSORS:
                valid = processor(self, result)
                if valid is False:
                    self.debug("Result removed by processor: %s", result)
                    break
            else:
                self.results.append(result)
                self.debug(result, result.distance, result.score)
        self.results.sort(key=lambda r: r.score, reverse=True)
        return self.results[: self.wanted]


def search(
    query,
    fuzzy=1,
    limit=10,
    autocomplete=False,
    lat=None,
    lon=None,
    verbose=False,
    **filters
):
    helper = Search(
        fuzzy=fuzzy,
        limit=limit,
        verbose=verbose,
        autocomplete=autocomplete,
    )
    return helper(query, lat=lat, lon=lon, **filters)


def reverse(lat, lon, limit=1, verbose=False, **filters):
    helper = Reverse(verbose=verbose)
    return helper(lat, lon, limit, **filters)
