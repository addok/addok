import re

import redis
import ngram
from unidecode import unidecode

from .config import DB_SETTINGS
from .fuzzy import fuzzy as make_fuzzy

DB = redis.StrictRedis(**DB_SETTINGS)


def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def housenumber_lat_key(s):
    return 'lat|{}'.format(s)


def housenumber_lon_key(s):
    return 'lon|{}'.format(s)


def tokenize(text, lang="fr"):
    """
    Split text into a list of tokens.
    """
    if lang == "fr":
        pattern = r"[\w]+"
    else:
        raise NotImplementedError
    return re.compile(pattern, re.U | re.X).findall(text)


def normalize(text, lang="fr"):
    if lang == "fr":
        return unidecode(text.lower())
    else:
        raise NotImplementedError


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


class Result(object):

    def __init__(self, doc):
        for key, value in doc.items():
            setattr(self, key.decode(), value.decode())
        self.score = float(self.importance)

    def __str__(self):
        label = self.name
        city = getattr(self, 'city', None)
        if city:
            label = '{} {}'.format(label, city)
        housenumber = getattr(self, 'housenumber', None)
        if housenumber:
            label = '{} {}'.format(housenumber, label)
        return label

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self.id, self.score)

    def is_housenumber(self, tokens):
        for token in tokens:
            key = document_key(self.id)
            lat_key = housenumber_lat_key(token.original)
            if DB.hexists(key, lat_key):
                self.housenumber = token.original
                self.lat = DB.hget(key, lat_key)
                lon_key = housenumber_lon_key(token.original)
                self.lon = DB.hget(key, lon_key)


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

    def make_fuzzy(self):
        neighbors = self.neighbors
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
    def neighbors(self):
        return make_fuzzy(self.original)

    @property
    def is_common(self):
        return self.frequency > 1000

    @property
    def frequency(self):
        if not hasattr(self, '_frequency'):
            self._frequency = token_frequency(self.original)
        return self._frequency

    @property
    def is_fuzzy(self):
        return not self.db_key and self.fuzzy_keys


def score_ngram(result, query):
    # TODO: case and accents.
    score = ngram.NGram.compare(result.name, query)
    result.score += score


def keys_sets_temp_key(keys_sets):
    return 'kstmp|{}'.format('.'.join(keys_sets))


class Empty(Exception):
    pass


class Search(object):

    HARD_LIMIT = 100

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=0):
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.limit = limit

    def __call__(self, query):
        self.results = []
        ok_tokens = []
        pending_tokens = []
        self.query = query
        self.preprocess(query)
        self.search_all()
        for token in self.tokens:
            if token.db_key and not token.is_common:
                ok_tokens.append(token)
            else:
                pending_tokens.append(token)
        if not ok_tokens:  # Take the less common as basis.
            commons = [t for t in self.tokens if t.is_common]
            if commons:
                commons.sort(lambda x: x.frequency)
                ok_tokens = commons[:1]
        ok_keys = [t.db_key for t in ok_tokens]
        ids = self.intersect(ok_keys)
        if (ids and len(ids) >= self.limit and len(ids) < self.HARD_LIMIT)\
           or not pending_tokens:
            return self.render(ids)
        # Try to autocomplete
        self.last_token.autocomplete()
        ids = set([])  # We don't want duplicates.
        for key in self.last_token.autocomplete_keys:
            keys = [t.db_key for t in ok_tokens if not t.is_last]
            ids.update(self.intersect(keys + [key]))
        if (ids and len(ids) >= self.limit and len(ids) < self.HARD_LIMIT)\
           or not pending_tokens:
            return self.render(ids)
        # Retrieve not found.
        not_found = []
        for token in pending_tokens:
            if not token.db_key:
                not_found.append(token)
        if not_found and self.fuzzy:
            not_found.sort(key=lambda t: len(t), reverse=True)
            try_one = not_found[0]  # Take the longest one.
            print('trying with', try_one)
            try_one.make_fuzzy()
            for key in try_one.fuzzy_keys:
                ids = self.intersect(ok_keys + [key])
                if ids:
                    return self.render(ids)
        return self.render(ids)

    def render(self, ids):
        self.compute_results(ids)
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
            ids = DB.zrevrange(self.query, 0, self.HARD_LIMIT - 1)
            DB.delete(self.query)
        return ids

    def compute_results(self, ids):
        for _id in ids:
            result = Result(DB.hgetall(_id))
            result.is_housenumber(self.tokens)
            self.results.append(result)


def search(query, match_all=False, fuzzy=0, limit=10, autocomplete=0):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit)
    return helper(query)
