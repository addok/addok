import logging
import time

import redis

from . import config
from .pipeline import preprocess_query
from .textutils.default import make_fuzzy, compare_ngrams

DB = redis.StrictRedis(**config.DB_SETTINGS)


def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def housenumber_field_key(s):
    return 'h|{}'.format(s)


def edge_ngram_key(s):
    return 'n|{}'.format(s)


def token_key_frequency(key):
    return DB.zcard(key)


def token_frequency(token):
    return token_key_frequency(token_key(token))


def score_ngram(result, query):
    score = compare_ngrams(str(result), query)
    result.score = score


def score_autocomplete(key):
    card = DB.zcard(key)
    if card > config.COMMON_THRESHOLD:
        return 0
    else:
        return card


class Result(object):

    def __init__(self, doc):
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


class Search(object):

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=True):
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.limit = limit
        self._start = time.time()
        self._autocomplete = autocomplete

    def debug(self, *args):
        s = args[0] % args[1:]
        s = '[{}] {}'.format(str(time.time() - self._start), s)
        logging.debug(s)

    def __call__(self, query):
        self.results = []
        self.bucket = set([])  # No duplicates.
        ok_tokens = []
        not_found = []
        common_tokens = []
        self.query = query
        self.preprocess(query)
        self.search_all()
        for token in self.tokens:
            if token.is_common:
                common_tokens.append(token)
            elif token.db_key:
                ok_tokens.append(token)
            else:
                not_found.append(token)
        common_tokens.sort(key=lambda x: x.frequency)
        self.debug('Taken tokens %s', ok_tokens)
        self.debug('Common tokens %s', common_tokens)
        self.debug('Not found tokens %s', not_found)
        if len(self.tokens) == len(common_tokens):
            # Only common terms, shortcut to search
            self.add_to_bucket([t.db_key for t in self.tokens])
            if self.bucket_overflow:
                self.debug('Only common terms and too much result. Return.')
                return self.render()
        if not ok_tokens and common_tokens:
            # Only commons terms, try to reduce with autocomplete.
            self.debug('Only commons, trying autocomplete')
            self.autocomplete(common_tokens)
            if self.bucket_full or self.bucket_overflow:
                self.debug('Enough results after autocomplete %s', ok_tokens)
                return self.render()
        if not ok_tokens and common_tokens:  # Take the less common as basis.
            ok_tokens = common_tokens[:1]
        ok_keys = [t.db_key for t in ok_tokens]
        self.add_to_bucket(ok_keys)
        if self.bucket_full or (not self.fuzzy and not not_found):
            self.debug('Enough results with only rare tokens %s', ok_tokens)
            return self.render()
        for token in common_tokens:
            if token not in ok_tokens and self.bucket_overflow:
                ok_tokens.append(token)
                ok_keys = [t.db_key for t in ok_tokens]
                self.new_bucket(ok_keys)
        # Try to autocomplete
        self.autocomplete(ok_tokens)
        if self.bucket_full or (not self.fuzzy and not not_found):
            self.debug('Enough results after autocomplete %s', ok_tokens)
            return self.render()
        if self.bucket_empty:
            self.debug('Bucket empty. Trying to remove some.')
            for token in ok_tokens:
                keys = ok_keys[:]
                keys.remove(token.db_key)
                self.add_to_bucket(keys)
                if self.bucket_overflow:
                    break
        if self.fuzzy:
            self.debug('Fuzzy on. Trying.')
            not_found.sort(key=lambda t: len(t), reverse=True)
            for try_one in not_found:
                if try_one.isdigit():
                    continue
                if self.bucket_full:
                    break
                self.debug('Going fuzzy with %s', try_one)
                try_one.make_fuzzy(fuzzy=self.fuzzy)
                for key in try_one.fuzzy_keys:
                    if self.bucket_dry:
                        self.add_to_bucket(ok_keys + [key])
        return self.render()

    def render(self):
        self.compute_results()
        # Score and sort.
        for r in self.results:
            score_ngram(r, self.query)
        self.results.sort(key=lambda d: d.score, reverse=True)
        return self.results[:self.limit]

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
        self.debug('Autocompleting %s', self.last_token)
        self.last_token.autocomplete()
        keys = [t.db_key for t in tokens if not t.is_last]
        for key in self.last_token.autocomplete_keys:
            if self.bucket_overflow:
                self.debug('Trying to reduce bucket. Autocomplete %s', key)
                self.new_bucket(keys + [key])
            else:
                self.debug('Trying to extend bucket. Autocomplete %s', key)
                self.add_to_bucket(keys + [key])

    def intersect(self, keys, limit=0):
        if not limit > 0:
            limit = config.BUCKET_LIMIT - 1
        ids = []
        if keys:
            if len(keys) == 1:
                ids = DB.zrevrange(keys[0], 0, limit)
            else:
                DB.zinterstore(self.query, keys)
                ids = DB.zrevrange(self.query, 0, limit)
                DB.delete(self.query)
        return set(ids)

    def add_to_bucket(self, keys):
        self.debug('Adding to bucket with keys %s', keys)
        limit = config.BUCKET_LIMIT - len(self.bucket)
        self.bucket.update(self.intersect(keys, limit))
        self.debug('%s ids in bucket so far', len(self.bucket))

    def new_bucket(self, keys):
        self.debug('New bucket with keys %s', keys)
        self.bucket = self.intersect(keys)
        self.debug('%s ids in bucket so far', len(self.bucket))

    def compute_results(self):
        self.debug('Computing results')
        for _id in self.bucket:
            result = Result(DB.hgetall(_id))
            result.match_housenumber(self.tokens)
            self.results.append(result)
        self.debug('Done computing results')

    @property
    def bucket_full(self):
        l = len(self.bucket)
        return l >= self.limit and l < config.BUCKET_LIMIT

    @property
    def bucket_overflow(self):
        return len(self.bucket) >= config.BUCKET_LIMIT

    @property
    def bucket_dry(self):
        return len(self.bucket) < self.limit

    @property
    def bucket_empty(self):
        return not self.bucket


def search(query, match_all=False, fuzzy=1, limit=10, autocomplete=0):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit)
    return helper(query)
