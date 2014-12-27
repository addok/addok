import logging

import redis

from . import config
from .utils import make_fuzzy, compare_ngrams, tokenize, normalize

DB = redis.StrictRedis(**config.DB_SETTINGS)
logging.basicConfig(level=logging.DEBUG)


def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def housenumber_field_key(s):
    return 'h|{}'.format(s)


def prepare(text):
    for s in tokenize(text):
        yield normalize(s)


def token_key_frequency(key):
    return DB.zcard(key)


def token_frequency(token):
    return token_key_frequency(token_key(token))


def word_frequency(word):
    token = normalize(word)
    return token_frequency(token)


def common_term(token):
    return token_frequency(token) > 1000  # TODO: Take a % of nb of docs.


def score_ngram(result, query):
    score = compare_ngrams(str(result), query)
    result.score = score


class Result(object):

    def __init__(self, doc):
        for key, value in doc.items():
            setattr(self, key.decode(), value.decode())
        self.score = float(self.importance)

    def __str__(self):
        label = self.name
        city = getattr(self, 'city', None)
        if city and city != self.name:
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
        keys = ['name', 'type', 'city', 'housenumber', 'score']
        for key in keys:
            val = getattr(self, key, None)
            if val:
                properties[key] = val
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(self.lon), float(self.lat)]
            },
            "properties": properties
        }


class Token(object):

    def __init__(self, original, position, is_last=False):
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
        # TODO: find a way to limit number of results when word is small:
        # - target only "rare" keys?
        key = '{}*'.format(token_key(self.original))
        self.autocomplete_keys = DB.keys(key)

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


class Empty(Exception):
    pass


class Search(object):

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=0):
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.limit = limit

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
        if not ok_tokens and common_tokens:  # Take the less common as basis.
            ok_tokens = common_tokens[:1]
        ok_keys = [t.db_key for t in ok_tokens]
        self.add_to_bucket(ok_keys)
        if self.bucket_full or (not self.fuzzy and not not_found):
            logging.debug('Enough results with only rare tokens %s', ok_tokens)
            return self.render()
        for token in common_tokens:
            if token not in ok_tokens and self.bucket_overflow:
                ok_tokens.append(token)
                ok_keys = [t.db_key for t in ok_tokens]
                self.new_bucket(ok_keys)
        # Try to autocomplete
        self.last_token.autocomplete()
        for key in self.last_token.autocomplete_keys:
            keys = [t.db_key for t in ok_tokens if not t.is_last]
            if not self.bucket_overflow:
                self.add_to_bucket(keys + [key])
        if self.bucket_full or (not self.fuzzy and not not_found):
            logging.debug('Enough results after autocomplete %s', ok_tokens)
            return self.render()
        if self.bucket_empty:
            for token in ok_tokens:
                keys = ok_keys[:]
                keys.remove(token.db_key)
                self.add_to_bucket(keys)
                if self.bucket_full:
                    break
        if self.fuzzy:
            # Retrieve not found.
            logging.debug('Not found %s', not_found)
            not_found.sort(key=lambda t: len(t), reverse=True)
            for try_one in not_found:
                if self.bucket_full:
                    break
                logging.debug('Going fuzzy with %s', try_one)
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
        for position, token in enumerate(prepare(query)):
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

    def intersect(self, keys):
        ids = []
        if keys:
            DB.zinterstore(self.query, keys)
            ids = DB.zrevrange(self.query, 0, config.BUCKET_LIMIT - 1)
            DB.delete(self.query)
        return set(ids)

    def add_to_bucket(self, keys):
        self.bucket.update(self.intersect(keys))

    def new_bucket(self, keys):
        self.bucket = self.intersect(keys)

    def compute_results(self):
        for _id in self.bucket:
            result = Result(DB.hgetall(_id))
            result.match_housenumber(self.tokens)
            self.results.append(result)

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
