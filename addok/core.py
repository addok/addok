import asyncio
import time

import asyncio_redis
import geohash

from . import config
from .db import DB
from .helpers import keys
from .helpers.index import VALUE_SEPARATOR
from .helpers.text import ascii


import logging
logging.basicConfig(level=logging.DEBUG)


def compute_geohash_key(geoh, with_neighbors=True):
    if with_neighbors:
        neighbors = geohash.expand(geoh)
        neighbors = [keys.geohash_key(n) for n in neighbors]
    else:
        neighbors = [geoh]
    key = 'gx|{}'.format(geoh)
    total = DB.sunionstore(key, neighbors)
    if not total:
        # No need to keep it.
        DB.delete(key)
        key = False
    else:
        DB.expire(key, 10)
    return key


class Result(object):

    def __init__(self):
        self.housenumber = None
        self._scores = {}
        self.labels = []

    @classmethod
    @asyncio.coroutine
    def load(cls, _id):
        result = cls()
        result._id = _id
        result._cache = {}
        doc = yield from config.connection.hgetall(_id.decode())
        doc = yield from doc.asdict()
        if not doc:
            raise ValueError('id "{}" not found'.format(_id[2:]))
        result._doc = doc
        result.load_housenumbers()
        return result

    def load_housenumbers(self):
        self.housenumbers = {}
        for key, value in self._doc.items():
            if key.startswith('h|'):
                self.housenumbers[key[2:]] = value

    def __getattr__(self, key):
        if key not in self._cache:
            # By convention, in case of multiple values, first value is default
            # value, others are aliases.
            value = self._rawattr(key)[0]
            self._cache[key] = value
        return self._cache[key]

    def __str__(self):
        return (str(self.labels[0]) if self.labels
                else self._rawattr(config.NAME_FIELD)[0])

    def _rawattr(self, key):
        return self._doc.get(key, '').split(VALUE_SEPARATOR)

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self.id, self.score)

    @property
    def keys(self):
        to_filter = ['importance', 'housenumbers', 'lat', 'lon']
        keys = ['housenumber']
        keys.extend(self._doc.keys())
        housenumber = getattr(self, 'housenumber', None)
        if housenumber:
            keys.extend(config.HOUSENUMBERS_PAYLOAD_FIELDS)
        for key in keys:
            if key.startswith(('_', 'h|')) or key in to_filter:
                continue
            yield key

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
        if self._score != '':
            return float(self._score)
        score, _max = zip(*self._scores.values())
        return sum(score) / sum(_max)

    @score.setter
    def score(self, value):
        self._score = value

    @property
    def str_distance(self):
        return self._scores.get('str_distance', [0.0])[0]

    @classmethod
    def from_id(self, _id):
        """Return a result from it's document id."""
        return Result(keys.document_key(_id))


class BaseHelper(object):

    def __init__(self, verbose):
        self._start = time.time()
        if not verbose:
            self.debug = lambda *args: None

    def debug(self, *args):
        s = args[0] % args[1:]
        s = '[{}] {}'.format(str((time.time() - self._start) * 1000)[:5], s)
        print(s)


class Search(BaseHelper):

    SMALL_BUCKET_LIMIT = 10
    MAX_MEANINGUL = 10

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=True,
                 verbose=False):
        super().__init__(verbose=verbose)
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.limit = limit
        self.min = self.limit
        self.autocomplete = autocomplete

    def __call__(self, query, lat=None, lon=None, **filters):
        self.lat = lat
        self.lon = lon
        self._geohash_key = None
        self.results = {}
        self.bucket = set([])  # No duplicates.
        self.meaningful = []
        self.not_found = []
        self.common = []
        self.keys = []
        self.matched_keys = set([])
        self.check_housenumber = filters.get('type') in [None, "housenumber"]
        self.filters = [keys.filter_key(k, v) for k, v in filters.items() if v]
        self.query = ascii(query.strip())
        for func in config.SEARCH_PREPROCESSORS:
            func(self)
        if not self.tokens:
            return []
        self.debug('Taken tokens: %s', self.meaningful)
        self.debug('Common tokens: %s', self.common)
        self.debug('Not found tokens: %s', self.not_found)
        self.debug('Filters: %s', ['{}={}'.format(k, v)
                                   for k, v in filters.items()])
        for collector in config.RESULTS_COLLECTORS:
            self.debug('** %s **', collector.__name__.upper())
            if collector(self):
                break
        return self.render()

    @property
    def geohash_key(self):
        if self.lat and self.lon and self._geohash_key is None:
            geoh = geohash.encode(self.lat, self.lon, config.GEOHASH_PRECISION)
            self._geohash_key = compute_geohash_key(geoh)
            if self._geohash_key:
                self.debug('Computed geohash key %s', self._geohash_key)
            else:
                self.debug('Empty geohash key, deleting %s', self._geohash_key)
        return self._geohash_key

    def render(self):
        self.convert()
        self._sorted_bucket = list(self.results.values())
        self._sorted_bucket.sort(key=lambda r: r.score, reverse=True)
        return self._sorted_bucket[:self.limit]

    def intersect(self, keys, limit=0):
        if not limit > 0:
            limit = config.BUCKET_LIMIT
        ids = []
        if keys:
            if self.filters:
                keys.extend(self.filters)
            if len(keys) == 1:
                ids = DB.zrevrange(keys[0], 0, limit - 1)
            else:
                DB.zinterstore(self.query, set(keys))
                ids = DB.zrevrange(self.query, 0, limit - 1)
                DB.delete(self.query)
        return set(ids)

    def add_to_bucket(self, keys, limit=None):
        self.debug('Adding to bucket with keys %s', keys)
        self.matched_keys.update([k for k in keys if k.startswith('w|')])
        limit = limit or (config.BUCKET_LIMIT - len(self.bucket))
        self.bucket.update(self.intersect(keys, limit))
        self.debug('%s ids in bucket so far', len(self.bucket))

    def new_bucket(self, keys, limit=0):
        self.debug('New bucket with keys %s and limit %s', keys, limit)
        self.matched_keys = set([k for k in keys if k.startswith('w|')])
        self.bucket = self.intersect(keys, limit)
        self.debug('%s ids in bucket so far', len(self.bucket))

    async def convert_result(self, _id):
        self.debug('starting task for _id: ' + _id.decode())
        result = await Result.load(_id)
        for processor in config.SEARCH_RESULT_PROCESSORS:
            processor(self, result)
        self.debug('finished task for _id: ' + _id.decode())
        return result

    def result_callback(self, future):
        result = future.result()
        self.results[result._id] = result

    def convert(self):
        self.debug('Computing results')

        tasks = []
        for _id in self.bucket:
            if _id in self.results:
                continue
            future = asyncio.ensure_future(self.convert_result(_id))
            future.add_done_callback(self.result_callback)
            tasks.append(future)
        asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))

        self.debug('Done computing results')

    @property
    def bucket_full(self):
        l = len(self.bucket)
        return l >= self.min and l < config.BUCKET_LIMIT

    @property
    def bucket_overflow(self):
        return len(self.bucket) >= config.BUCKET_LIMIT

    @property
    def bucket_dry(self):
        return len(self.bucket) < self.min

    @property
    def bucket_empty(self):
        return not self.bucket

    @property
    def cream(self):
        return len([r for _id, r in self.results.items()
                    if r.str_distance >= config.MATCH_THRESHOLD])

    def has_cream(self):
        if self.bucket_empty or self.bucket_overflow or len(self.bucket) > 10:
            return False
        self.debug('Checking cream.')
        self.convert()
        return self.cream > 0

    @property
    def pass_should_match_threshold(self):
        return len(self.matched_keys) >= self.should_match_threshold


class Reverse(BaseHelper):

    def __call__(self, lat, lon, limit=1, **filters):
        self.lat = lat
        self.lon = lon
        self.keys = set([])
        self.results = []
        self.limit = limit
        self.fetched = []
        self.check_housenumber = filters.get('type') in [None, "housenumber"]
        self.filters = [keys.filter_key(k, v) for k, v in filters.items()]
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
        self.debug('Fetching %s', hashes)
        for h in hashes:
            k = keys.geohash_key(h)
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
                processor(self, result)
            self.results.append(result)
            self.debug(result, result.distance, result.score)
        self.results.sort(key=lambda r: r.score, reverse=True)
        return self.results[:self.limit]


def search(query, match_all=False, fuzzy=1, limit=10, autocomplete=False,
           lat=None, lon=None, verbose=False, **filters):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit,
                    verbose=verbose, autocomplete=autocomplete)
    return helper(query, lat=lat, lon=lon, **filters)


def reverse(lat, lon, limit=1, verbose=False, **filters):
    helper = Reverse(verbose=verbose)
    return helper(lat, lon, limit, **filters)
