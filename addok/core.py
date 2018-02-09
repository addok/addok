import os
import time

import geohash

from .config import config
from .db import DB
from .ds import get_document, get_documents
from .helpers import keys as dbkeys, scripts
from .helpers.text import ascii


def compute_geohash_key(geoh, with_neighbors=True):
    if with_neighbors:
        neighbors = geohash.expand(geoh)
        neighbors = [dbkeys.geohash_key(n) for n in neighbors]
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
        value = self._doc.get(key, '')
        if not isinstance(value, (tuple, list)):
            value = [value]
        return value

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self._id, self.score)

    @property
    def keys(self):
        keys = ['housenumber'] + list(self._doc.keys())
        # housenumbers are too verbose for a given street.
        yield from (key for key in keys if key != 'housenumbers')

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
        s = '[{}] {}'.format(str((time.time() - self._start) * 1000)[:5], s)
        self._debug.append(s)

    def report(self):  # pragma: no cover
        for msg in self._debug:
            print(msg)


class Search(BaseHelper):

    MAX_MEANINGFUL = 10

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=True,
                 verbose=False):
        super().__init__(verbose=verbose)
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.wanted = limit
        self.autocomplete = autocomplete
        self.pid = os.getpid()  # Unique id for tmp values in redis.

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
        self.check_housenumber = filters.get('type') in [None, "housenumber"]
        self.filters = [dbkeys.filter_key(k, v.strip())
                        for k, v in filters.items() if v.strip()]
        self.query = ascii(query.strip())
        for func in config.SEARCH_PREPROCESSORS:
            func(self)
        self.debug('Taken tokens: %s', self.meaningful)
        self.debug('Common tokens: %s', self.common)
        self.debug('Housenumbers token: %s', self.housenumbers)
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
        return [r for r in self._sorted_bucket[:self.wanted]
                if r.score >= config.MIN_SCORE]

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
        self.debug('Adding to bucket with keys %s', keys)
        self.matched_keys.update([k for k in keys
                                  if k.startswith(dbkeys.TOKEN_PREFIX)])
        limit = limit or (config.BUCKET_MAX - len(self.bucket))
        self.bucket.update(self.intersect(keys, limit))
        self.debug('%s ids in bucket so far', len(self.bucket))

    def new_bucket(self, keys, limit=0):
        self.debug('New bucket with keys %s and limit %s', keys, limit)
        self.matched_keys = set([k for k in keys
                                 if k.startswith(dbkeys.TOKEN_PREFIX)])
        self.bucket = self.intersect(keys, limit)
        self.debug('%s ids in bucket so far', len(self.bucket))

    def convert(self):
        self.debug('Computing results')
        ids = [i for i in self.bucket if i not in self.results]
        if ids:
            documents = get_documents(*ids)
            self.debug('Done getting results data')
            for _id, doc in documents:
                result = Result(doc)
                for processor in config.SEARCH_RESULT_PROCESSORS:
                    processor(self, result)
                self.results[_id] = result
        self.debug('Done computing results')

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
        return len([r for _id, r in self.results.items()
                    if r.str_distance >= config.MATCH_THRESHOLD])

    def has_cream(self):
        if (self.bucket_empty
           or self.bucket_overflow
           or len(self.bucket) > config.BUCKET_MIN):
            return False
        self.debug('Checking cream.')
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
        self.check_housenumber = filters.get('type') in [None, "housenumber"]
        self.filters = [dbkeys.filter_key(k, v) for k, v in filters.items()]
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
                processor(self, result)
            self.results.append(result)
            self.debug(result, result.distance, result.score)
        self.results.sort(key=lambda r: r.score, reverse=True)
        return self.results[:self.wanted]


def search(query, match_all=False, fuzzy=1, limit=10, autocomplete=False,
           lat=None, lon=None, verbose=False, **filters):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit,
                    verbose=verbose, autocomplete=autocomplete)
    return helper(query, lat=lat, lon=lon, **filters)


def reverse(lat, lon, limit=1, verbose=False, **filters):
    helper = Reverse(verbose=verbose)
    return helper(lat, lon, limit, **filters)
