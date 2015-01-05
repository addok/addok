import logging
import time

import geohash
import redis

from . import config
from .pipeline import preprocess_query
from .textutils.default import make_fuzzy, compare_ngrams
from .utils import haversine_distance, km_to_score

DB = redis.StrictRedis(**config.DB_SETTINGS)


def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def housenumber_field_key(s):
    return 'h|{}'.format(s)


def edge_ngram_key(s):
    return 'n|{}'.format(s)


def geohash_key(s):
    return 'g|{}'.format(s)


def token_key_frequency(key):
    return DB.zcard(key)


def token_frequency(token):
    return token_key_frequency(token_key(token))


def score_by_ngram_distance(result, query):
    score = compare_ngrams(result.name, query)
    if score < config.MATCH_THRESHOLD:
        score = max(score, compare_ngrams(str(result), query))
    result.score = score


def score_by_geo_distance(result, center):
    km = haversine_distance((float(result.lat), float(result.lon)), center)
    result.score += km_to_score(km)


def score_autocomplete(key):
    card = DB.zcard(key)
    if card > config.COMMON_THRESHOLD:
        return 0
    else:
        return card


class Result(object):

    def __init__(self, _id):
        doc = DB.hgetall(_id)
        for key, value in doc.items():
            setattr(self, key.decode(), value.decode())
        self.score = float(self.importance)

    def __str__(self):
        label = self.name
        city = getattr(self, 'city', None)
        if city and city != self.name:
            postcode = getattr(self, 'postcode', None)
            if postcode:
                label = '{} {}'.format(label, postcode)
            label = '{} {}'.format(label, city)
        housenumber = getattr(self, 'housenumber', None)
        if housenumber:
            label = '{} {}'.format(housenumber, label)
        return label

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self.id, self.score)

    def match_housenumber(self, tokens):
        for token in tokens:
            key = document_key(self.id)
            field = housenumber_field_key(token.original)
            if DB.hexists(key, field):
                raw, lat, lon = DB.hget(key, field).decode().split('|')
                self.housenumber = raw
                self.lat = lat
                self.lon = lon

    def to_geojson(self):
        properties = {"label": str(self)}
        keys = ['name', 'type', 'city', 'housenumber', 'score', 'postcode']
        for key in keys:
            val = getattr(self, key, None)
            if val:
                properties[key] = val
        housenumber = getattr(self, 'housenumber', None)
        if housenumber:
            properties['name'] = '{} {}'.format(housenumber,
                                                properties['name'])
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(self.lon), float(self.lat)]
            },
            "properties": properties
        }


class Token(object):

    def __init__(self, original, position=0, is_last=False):
        self.original = original
        self.position = position
        self.is_last = is_last
        self.key = token_key(original)
        self.db_key = None
        self.fuzzy_keys = []

    def __len__(self):
        return len(self.original)

    def __str__(self):
        return self.original

    def __repr__(self):
        return '<Token {}>'.format(self.original)

    def search(self):
        if DB.exists(self.key):
            self.db_key = self.key

    def make_fuzzy(self, fuzzy):
        neighbors = make_fuzzy(self.original, fuzzy)
        keys = []
        if neighbors:
            for neighbor in neighbors:
                key = token_key(neighbor)
                count = DB.zcard(key)
                if count:
                    keys.append((key, count))
        keys.sort(key=lambda x: x[1])
        for key, count in keys:
            self.fuzzy_keys.append(key)

    def autocomplete(self):
        key = edge_ngram_key(self.original)
        self.autocomplete_keys = [token_key(k.decode())
                                  for k in DB.smembers(key)]
        self.autocomplete_keys.sort(key=score_autocomplete, reverse=True)

    @property
    def is_common(self):
        return self.frequency > config.COMMON_THRESHOLD

    @property
    def frequency(self):
        if not hasattr(self, '_frequency'):
            self._frequency = token_frequency(self.original)
        return self._frequency

    @property
    def is_fuzzy(self):
        return not self.db_key and self.fuzzy_keys

    def isdigit(self):
        return self.original.isdigit()


class Empty(Exception):
    pass


class BaseHelper(object):

    def __init__(self):
        self._start = time.time()

    def debug(self, *args):
        s = args[0] % args[1:]
        s = '[{}] {}'.format(str(time.time() - self._start), s)
        logging.debug(s)


class Search(BaseHelper):

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=True):
        super().__init__()
        self.match_all = match_all
        self._fuzzy = fuzzy
        self.limit = limit
        self.min = self.limit
        self._autocomplete = autocomplete

    def __call__(self, query):
        self.results = {}
        self.bucket = set([])  # No duplicates.
        self.meaningful = []
        self.not_found = []
        self.common = []
        self.keys = []
        self.query = query
        self.preprocess(query)
        self.search_all()
        for token in self.tokens:
            if token.is_common:
                self.common.append(token)
            elif token.db_key:
                self.meaningful.append(token)
            else:
                self.not_found.append(token)
        self.common.sort(key=lambda x: x.frequency)
        self.debug('Taken tokens %s', self.meaningful)
        self.debug('Common tokens %s', self.common)
        self.debug('Not found tokens %s', self.not_found)
        if len(self.tokens) == len(self.common):
            # Only common terms, shortcut to search
            keys = [t.db_key for t in self.tokens]
            self.new_bucket(keys, 10)
            if self.has_cream():
                self.debug('Cream found. Returning.')
                return self.render()
            self.new_bucket(keys)
            if self.bucket_overflow or self.has_cream():
                self.debug('Only common terms and too much result. Return.')
                return self.render()
        if not self.meaningful and self.common:
            # Only commons terms, try to reduce with autocomplete.
            self.debug('Only commons, trying autocomplete')
            self.autocomplete(self.common)
            if self.bucket_full or self.bucket_overflow or self.has_cream():
                return self.render()
        if not self.meaningful and self.common:  # Take the less common.
            self.meaningful = self.common[:1]
        self.keys = [t.db_key for t in self.meaningful]
        if self.bucket_empty:
            self.new_bucket(self.keys, 10)
            if self.has_cream():
                self.debug('Cream found. Returning.')
                return self.render()
            self.new_bucket(self.keys)
        else:
            self.add_to_bucket(self.keys)
        if self.bucket_full or self.has_cream():
            return self.render()
        for token in self.common:
            if token not in self.meaningful and self.bucket_overflow:
                self.meaningful.append(token)
                self.keys = [t.db_key for t in self.meaningful]
                self.new_bucket(self.keys)
        # Try to autocomplete
        self.autocomplete(self.meaningful)
        if self.bucket_full or self.has_cream():
            self.debug('Enough results after autocomplete %s', self.meaningful)
            return self.render()
        if self._fuzzy and not self.has_cream():
            self.fuzzy(self.not_found)
            if self.bucket_dry and not self.has_cream():
                self.fuzzy(self.meaningful)
        if self.bucket_dry and not self.has_cream():
            self.reduce_tokens()
        return self.render()

    def render(self):
        self.convert()
        results = list(self.results.values())
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:self.limit]

    def preprocess(self, query):
        self.tokens = []
        for position, token in enumerate(preprocess_query(query)):
            token = Token(token, position=position)
            self.tokens.append(token)
        token.is_last = True
        self.last_token = token
        self.tokens.sort(key=lambda x: len(x), reverse=True)

    def search_all(self):
        for token in self.tokens:
            token.search()
            if (self.match_all and (not self.fuzzy or not token.fuzzy_keys)
               and not token.db_key):
                raise Empty

    def autocomplete(self, tokens):
        if not self._autocomplete:
            self.debug('Autocomplete not active. Abort.')
            return
        self.debug('** Autocompleting %s', self.last_token)
        self.last_token.autocomplete()
        keys = [t.db_key for t in tokens if not t.is_last]
        for key in self.last_token.autocomplete_keys:
            if self.bucket_overflow:
                self.debug('Trying to reduce bucket. Autocomplete %s', key)
                self.new_bucket(keys + [key])
            else:
                self.debug('Trying to extend bucket. Autocomplete %s', key)
                self.add_to_bucket(keys + [key])

    def fuzzy(self, tokens):
        self.debug('** Fuzzy on. Trying with %s.', tokens)
        tokens.sort(key=lambda t: len(t), reverse=True)
        for try_one in tokens:
            keys = self.keys[:]
            if try_one.db_key in keys:
                keys.remove(try_one.db_key)
            if try_one.isdigit():
                continue
            if self.bucket_full:
                break
            self.debug('Going fuzzy with %s', try_one)
            try_one.make_fuzzy(fuzzy=self.fuzzy)
            for key in try_one.fuzzy_keys:
                if self.bucket_dry:
                    self.add_to_bucket(keys + [key])

    def reduce_tokens(self):
        self.debug('** Bucket dry. Trying to remove some.')
        self.meaningful.sort(key=lambda x: x.frequency)
        for token in self.meaningful:
            keys = self.keys[:]
            keys.remove(token.db_key)
            self.add_to_bucket(keys)
            if self.bucket_overflow:
                break

    def intersect(self, keys, limit=0):
        if not limit > 0:
            limit = config.BUCKET_LIMIT
        ids = []
        if keys:
            if len(keys) == 1:
                ids = DB.zrevrange(keys[0], 0, limit - 1)
            else:
                DB.zinterstore(self.query, keys)
                ids = DB.zrevrange(self.query, 0, limit - 1)
                DB.delete(self.query)
        return set(ids)

    def add_to_bucket(self, keys):
        self.debug('Adding to bucket with keys %s', keys)
        limit = config.BUCKET_LIMIT - len(self.bucket)
        self.bucket.update(self.intersect(keys, limit))
        self.debug('%s ids in bucket so far', len(self.bucket))

    def new_bucket(self, keys, limit=0):
        self.debug('New bucket with keys %s and limit %s', keys, limit)
        self.bucket = self.intersect(keys, limit)
        self.debug('%s ids in bucket so far', len(self.bucket))

    def convert(self):
        self.debug('Computing results')
        for _id in self.bucket:
            if _id in self.results:
                continue
            result = Result(_id)
            result.match_housenumber(self.tokens)
            score_by_ngram_distance(result, self.query)
            self.results[_id] = result
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
    def bucket_cream(self):
        return any(r.score > config.MATCH_THRESHOLD
                   for _id, r in self.results.items())

    def has_cream(self):
        if self.bucket_empty or self.bucket_overflow or len(self.bucket) > 10:
            return False
        self.debug('Checking cream.')
        self.convert()
        return self.bucket_cream


class Reverse(BaseHelper):

    def __call__(self, lat, lon, limit=1):
        self.lat = lat
        self.lon = lon
        self.ids = set([])
        self.results = []
        self.limit = limit
        self.fetched = []
        geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
        hashes = self.expand([geoh])
        self.fetch(hashes)
        if not self.ids:
            hashes = self.expand(hashes)
            self.fetch(hashes)
        return self.convert()

    def expand(self, hashes):
        new = []
        for h in hashes:
            neighbors = geohash.expand(h)
            for n in neighbors:
                if not n in self.fetched:
                    new.append(n)
        return new

    def fetch(self, hashes):
        self.debug('Fetching %s', hashes)
        for h in hashes:
            k = geohash_key(h)
            self.ids.update(DB.smembers(k))
            self.fetched.append(h)

    def convert(self):
        for _id in self.ids:
            r = Result(_id)
            score_by_geo_distance(r, (self.lat, self.lon))
            self.results.append(r)
            self.results.sort(key=lambda r: r.score)
        return self.results[:self.limit]


def search(query, match_all=False, fuzzy=1, limit=10, autocomplete=0):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit)
    return helper(query)


def reverse(lat, lon):
    helper = Reverse()
    return helper(lat, lon)
