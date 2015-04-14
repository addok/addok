import time
from math import ceil

import geohash

from . import config
from .db import DB
from .index_utils import (PROCESSORS, edge_ngram_key, filter_key, geohash_key,
                          pair_key, token_key)
from .textutils.default import (ascii, compare_ngrams, contains, equals,
                                make_fuzzy, startswith)
from .utils import haversine_distance, import_by_path, iter_pipe, km_to_score

QUERY_PROCESSORS = [import_by_path(path) for path in config.QUERY_PROCESSORS]


def preprocess_query(s):
    return list(iter_pipe(s, QUERY_PROCESSORS + PROCESSORS))


def token_key_frequency(key):
    return DB.zcard(key)


def token_frequency(token):
    return token_key_frequency(token_key(token))


def score_autocomplete(key):
    card = DB.zcard(key)
    if card > config.COMMON_THRESHOLD:
        return 0
    else:
        return card


class Result(object):

    def __init__(self, _id):
        self.housenumbers = {}
        self.housenumber = None
        self.importance = 0.0  # Default value, can be overriden by db values.
        self._scores = {}
        self.load(_id)
        if self.MAX_IMPORTANCE:
            self.add_score('importance',
                           float(self.importance) * config.IMPORTANCE_WEIGHT,
                           self.MAX_IMPORTANCE)

    def load(self, _id):
        doc = DB.hgetall(_id)
        for key, value in doc.items():
            self.load_db_field(key.decode(), value.decode())

    def load_db_field(self, key, value):
        if key.startswith('h|'):
            self.housenumbers[key[2:]] = value
        else:
            setattr(self, key, value)

    def __str__(self):
        return getattr(config, 'LABEL', self._label)()

    def _label(self):
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
        originals = [t.original for t in tokens]
        for token in tokens:
            if token.original in self.housenumbers:
                raw, lat, lon = self.housenumbers[token.original].split('|')
                if raw in self.name and originals.count(token.original) != 2:
                    # Consider that user is not requesting a housenumber if
                    # token is also in name (ex. rue du 8 mai), unless this
                    # token is twice in the query (8 rue du 8 mai).
                    continue
                self.housenumber = raw
                self.lat = lat
                self.lon = lon
                self.type = 'housenumber'
                break

    @property
    def keys(self):
        to_filter = ['importance', 'housenumbers', 'lat', 'lon']
        for key in self.__dict__.keys():
            if key.startswith('_') or key in to_filter:
                continue
            yield key

    def to_geojson(self):
        properties = {
            "label": str(self),
            "score": self.score,
        }
        for key in self.keys:
            val = getattr(self, key, None)
            if val:
                properties[key] = val
        housenumber = getattr(self, 'housenumber', None)
        if housenumber:
            properties['name'] = '{} {}'.format(housenumber,
                                                properties.get('name'))
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(self.lon), float(self.lat)]
            },
            "properties": properties
        }

    def add_score(self, name, score, ceiling):
        self._scores[name] = (score, ceiling)

    @property
    def score(self):
        score, _max = zip(*self._scores.values())
        return sum(score) / sum(_max)

    @property
    def str_distance(self):
        return self._scores.get('str_distance', [0.0])[0]

    def score_by_autocomplete_distance(self, query):
        score = 0
        query = ascii(query)
        name = ascii(self.name)
        label = str(self)
        if equals(query, name) or equals(query, label):
            score = 1.0
        elif startswith(query, label):
            score = 0.9
        elif contains(query, name):
            score = 0.7
        if score:
            self.add_score('str_distance', score, ceiling=1.0)
        else:
            self.score_by_ngram_distance(query, label)

    def score_by_ngram_distance(self, query, label=None):
        # Label can be given, so we cache all the preprocessing on the string.
        score = compare_ngrams(label or str(self), query)
        self.add_score('str_distance', score, ceiling=1.0)

    def score_by_geo_distance(self, center):
        km = haversine_distance((float(self.lat), float(self.lon)), center)
        self.distance = km
        self.add_score('geo_distance', km_to_score(km), ceiling=0.1)

    def score_by_contain(self, query):
        score = 0.0
        if contains(query, str(self)):
            score = 0.1
        self.add_score('contains_boost', score, ceiling=0.1)


class SearchResult(Result):

    MAX_IMPORTANCE = config.IMPORTANCE_WEIGHT


class ReverseResult(Result):

    MAX_IMPORTANCE = 0.0

    def load(self, *args, **kwargs):
        self.housenumbers = []
        super().load(*args, **kwargs)

    def load_db_field(self, key, value):
        if key.startswith('h|'):
            self.housenumbers.append(value.split('|'))
        else:
            setattr(self, key, value)

    def load_closer(self, lat, lon):

        def sort(h):
            return haversine_distance((float(h[1]), float(h[2])), (lat, lon))

        candidates = self.housenumbers + [(None, self.lat, self.lon)]
        candidates.sort(key=sort)
        closer = candidates[0]
        if closer[0]:  # Means a housenumber is closer than street centerpoint.
            self.housenumber = closer[0]
            self.lat = closer[1]
            self.lon = closer[2]
            self.type = "housenumber"


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

    def make_fuzzy(self, fuzzy=1):
        self.neighbors = make_fuzzy(self.original, fuzzy)

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

    def __init__(self, match_all=False, fuzzy=1, limit=10, autocomplete=True,
                 verbose=False):
        super().__init__(verbose=verbose)
        self.match_all = match_all
        self._fuzzy = fuzzy
        self.limit = limit
        self.min = self.limit
        self._autocomplete = autocomplete

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
        self.check_housenumber = filters.get('type') in [None, "housenumber"]
        self.filters = [filter_key(k, v) for k, v in filters.items()]
        self.query = query.strip()
        self.preprocess()
        if not self.tokens:
            return []
        self.search_all()
        self.set_should_match_threshold()
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
        steps = [
            self.step_only_commons,
            self.step_no_meaningful_but_common_try_autocomplete,
            self.step_bucket_with_meaningful,
            self.step_reduce_with_other_commons,
            self.step_ensure_geohash_results_are_included_if_center_is_given,
            self.step_autocomplete,
            self.step_check_bucket_full,
            self.step_check_cream,
            self.step_fuzzy,
            self.step_extend_results_reducing_tokens,
        ]
        for step in steps:
            self.debug('** %s **', step.__name__.upper())
            if step():
                return self.render()
        return self.render()

    def step_only_commons(self):
        if len(self.tokens) == len(self.common):
            # Only common terms, shortcut to search
            keys = [t.db_key for t in self.tokens]
            if self.geohash_key:
                keys.append(self.geohash_key)
                self.debug('Adding geohash %s', self.geohash_key)
            if len(keys) == 1 or self.geohash_key:
                self.add_to_bucket(keys)
            if self.bucket_dry and len(keys) > 1:
                count = 0
                # Scan the less frequent token.
                self.tokens.sort(key=lambda t: t.frequency)
                first = self.tokens[0]
                if first.frequency < config.INTERSECT_LIMIT:
                    self.debug('Under INTERSECT_LIMIT, brut force.')
                    keys = [t.db_key for t in self.tokens]
                    self.add_to_bucket(keys)
                else:
                    self.debug('INTERSECT_LIMIT hit, manual scan on %s', first)
                    others = [t.db_key for t in self.tokens[1:]]
                    ids = DB.zrevrange(first.db_key, 0, 500)
                    for id_ in ids:
                        count += 1
                        if all(DB.zrank(k, id_) for k in others):
                            self.bucket.add(id_)
                        if self.bucket_full:
                            break
                    self.debug('%s results after scan (%s loops)',
                               len(self.bucket), count)
            self.autocomplete(self.tokens, skip_commons=True)
            if not self.bucket_empty:
                self.debug('Only common terms. Return.')
                return True

    def step_no_meaningful_but_common_try_autocomplete(self):
        if not self.meaningful and self.common:
            # Only commons terms, try to reduce with autocomplete.
            self.debug('Only commons, trying autocomplete')
            self.autocomplete(self.common)
            self.meaningful = self.common[:1]
            if not self.pass_should_match_threshold:
                return False
            if self.bucket_full or self.bucket_overflow or self.has_cream():
                return True

    def step_bucket_with_meaningful(self):
        if len(self.meaningful) == 1 and self.common:
            # Avoid running with too less tokens while having commons terms.
            for token in self.common:
                if token not in self.meaningful:
                    self.meaningful.append(token)
                    break  # We want only one more.
        self.keys = [t.db_key for t in self.meaningful]
        if self.bucket_empty:
            self.new_bucket(self.keys, self.SMALL_BUCKET_LIMIT)
            if not self._autocomplete and self.has_cream():
                # Do not check cream before computing autocomplete when
                # autocomplete is on.
                self.debug('Cream found. Returning.')
                return True
            if len(self.bucket) == self.SMALL_BUCKET_LIMIT:
                # Do not rerun if bucket with limit 10 has returned less
                # than 10 results.
                self.new_bucket(self.keys)
        else:
            self.add_to_bucket(self.keys)

    def step_reduce_with_other_commons(self):
        for token in self.common:  # Already ordered by frequency asc.
            if token not in self.meaningful and self.bucket_overflow:
                self.debug('Now considering also common token %s', token)
                self.meaningful.append(token)
                self.keys = [t.db_key for t in self.meaningful]
                self.new_bucket(self.keys)

    def step_ensure_geohash_results_are_included_if_center_is_given(self):
        if self.bucket_overflow and self.geohash_key:
            self.debug('Bucket overflow and center, force nearby look up')
            self.add_to_bucket(self.keys + [self.geohash_key], self.limit)

    def step_autocomplete(self):
        if self.bucket_overflow:
            return
        if not self._autocomplete:
            self.debug('Autocomplete not active. Abort.')
            return
        if self.geohash_key:
            self.autocomplete(self.meaningful, use_geohash=True)
        self.autocomplete(self.meaningful)

    def step_fuzzy(self):
        if self._fuzzy and not self.has_cream():
            if self.not_found:
                self.fuzzy(self.not_found)
            if self.bucket_dry and not self.has_cream():
                self.fuzzy(self.meaningful)
            if self.bucket_dry and not self.has_cream():
                self.fuzzy(self.meaningful, include_common=False)

    def step_extend_results_reducing_tokens(self):
        if self.has_cream():
            return  # No need.
        if self.bucket_dry:
            self.reduce_tokens()

    def step_check_bucket_full(self):
        return self.bucket_full

    def step_check_cream(self):
        return self.has_cream()

    @property
    def geohash_key(self):
        if self.lat and self.lon and self._geohash_key is None:
            geoh = geohash.encode(self.lat, self.lon, config.GEOHASH_PRECISION)
            neighbors = geohash.expand(geoh)
            neighbors = [geohash_key(n) for n in neighbors]
            self._geohash_key = 'gx|{}'.format(geoh)
            self.debug('Compute geohash key %s', self._geohash_key)
            total = DB.sunionstore(self._geohash_key, neighbors)
            if not total:
                self.debug('Empty geohash key, deleting %s', self._geohash_key)
                DB.delete(self._geohash_key)
                self._geohash_key = False
            else:
                DB.expire(self._geohash_key, 10)
        return self._geohash_key

    def render(self):
        self.convert()
        self._sorted_bucket = list(self.results.values())
        self._sorted_bucket.sort(key=lambda r: r.score, reverse=True)
        return self._sorted_bucket[:self.limit]

    def preprocess(self):
        self.tokens = []
        token = None
        for position, token in enumerate(preprocess_query(self.query)):
            token = Token(token, position=position)
            self.tokens.append(token)
        if token:
            token.is_last = True
            self.last_token = token
        self.tokens.sort(key=lambda x: len(x), reverse=True)

    def search_all(self):
        for token in self.tokens:
            token.search()

    def autocomplete(self, tokens, skip_commons=False, use_geohash=False):
        self.debug('Autocompleting %s', self.last_token)
        # self.last_token.autocomplete()
        keys = [t.db_key for t in tokens if not t.is_last]
        pair_keys = [pair_key(t.original) for t in tokens if not t.is_last]
        key = edge_ngram_key(self.last_token.original)
        autocomplete_tokens = DB.sinter(pair_keys + [key])
        self.debug('Found tokens to autocomplete %s', autocomplete_tokens)
        for token in autocomplete_tokens:
            key = token_key(token.decode())
            if skip_commons\
               and token_key_frequency(key) > config.COMMON_THRESHOLD:
                self.debug('Skip common token to autocomplete %s', key)
                continue
            if not self.bucket_overflow or self.last_token in self.not_found:
                self.debug('Trying to extend bucket. Autocomplete %s', key)
                extra_keys = [key]
                if use_geohash and self.geohash_key:
                    extra_keys.append(self.geohash_key)
                self.add_to_bucket(keys + extra_keys)

    def fuzzy(self, tokens, include_common=True):
        if not self.bucket_dry:
            return
        self.debug('Fuzzy on. Trying with %s.', tokens)
        tokens.sort(key=lambda t: len(t), reverse=True)
        allkeys = self.keys[:]
        if include_common:
            # As we are in fuzzy, try to narrow as much as possible by adding
            # unused commons tokens.
            common = [t for t in self.common if t.db_key not in self.keys]
            allkeys.extend([t.db_key for t in common])
        for try_one in tokens:
            if self.bucket_full:
                break
            keys = allkeys[:]
            if try_one.db_key in keys:
                keys.remove(try_one.db_key)
            if try_one.isdigit():
                continue
            self.debug('Going fuzzy with %s', try_one)
            try_one.make_fuzzy(fuzzy=self.fuzzy)
            # Only retains tokens that have been seen in the index at least
            # once with the other tokens.
            DB.sadd(self.query, *try_one.neighbors)
            interkeys = [pair_key(k[2:]) for k in keys]
            interkeys.append(self.query)
            fuzzy_words = DB.sinter(interkeys)
            DB.delete(self.query)
            # Keep the priority we gave in building fuzzy terms (inversion
            # first, then substitution, etc.).
            fuzzy_words = [w.decode() for w in fuzzy_words]
            fuzzy_words.sort(key=lambda x: try_one.neighbors.index(x))
            self.debug('Found fuzzy candidates %s', fuzzy_words)
            fuzzy_keys = [token_key(w) for w in fuzzy_words]
            for key in fuzzy_keys:
                if self.bucket_dry:
                    self.add_to_bucket(keys + [key])

    def reduce_tokens(self):
        # Only if bucket is empty or we have margin on should_match_threshold.
        if self.bucket_empty\
           or len(self.meaningful) - 1 > self.should_match_threshold:
            self.debug('Bucket dry. Trying to remove some tokens.')

            def sorter(t):
                # First numbers, then by frequency
                return (2 if t.original.isdigit() else 1, t.frequency)

            self.meaningful.sort(key=sorter, reverse=True)
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
        if self.filters:
            keys.extend(self.filters)
        if keys:
            if len(keys) == 1:
                ids = DB.zrevrange(keys[0], 0, limit - 1)
            else:
                DB.zinterstore(self.query, keys)
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

    def convert(self):
        self.debug('Computing results')
        for _id in self.bucket:
            if _id in self.results:
                continue
            result = SearchResult(_id)
            if self.check_housenumber:
                result.match_housenumber(self.tokens)
            if self._autocomplete:
                result.score_by_autocomplete_distance(self.query)
            else:
                result.score_by_ngram_distance(self.query)
            if self.lat and self.lon:
                result.score_by_geo_distance((self.lat, self.lon))
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
    def bucket_greasy(self):
        return any(r.str_distance >= config.MATCH_THRESHOLD
                   for _id, r in self.results.items())

    def has_cream(self):
        if self.bucket_empty or self.bucket_overflow or len(self.bucket) > 10:
            return False
        self.debug('Checking cream.')
        self.convert()
        return self.bucket_greasy

    def set_should_match_threshold(self):
        self.matched_keys = set([])
        self.should_match_threshold = ceil(2 / 3 * len(self.tokens))

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
        self.filters = [filter_key(k, v) for k, v in filters.items()]
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
            k = geohash_key(h)
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
            r = ReverseResult(_id)
            if self.check_housenumber:
                r.load_closer(self.lat, self.lon)
            r.score_by_geo_distance((self.lat, self.lon))
            self.results.append(r)
            self.debug(r, r.distance, r.score)
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
