import geohash

from . import config
from .db import DB
from .textutils.default import compute_trigrams
from .utils import import_by_path, iter_pipe

VALUE_SEPARATOR = '|~|'

PROCESSORS = [import_by_path(path) for path in config.PROCESSORS]
HOUSENUMBER_PROCESSORS = [import_by_path(path) for path in
                          config.HOUSENUMBER_PROCESSORS + config.PROCESSORS]


def preprocess(s):
    if s not in _CACHE:
        _CACHE[s] = list(iter_pipe(s, PROCESSORS))
    return _CACHE[s]
_CACHE = {}


def preprocess_housenumber(s):
    if s not in _HOUSENUMBER_CACHE:
        _HOUSENUMBER_CACHE[s] = list(iter_pipe(s, HOUSENUMBER_PROCESSORS))
    return _HOUSENUMBER_CACHE[s]
_HOUSENUMBER_CACHE = {}


def token_key(s):
    return 't|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def housenumber_field_key(s):
    return 'h|{}'.format(s)


def edge_ngram_key(s):
    return 'n|{}'.format(s)


def geohash_key(s):
    return 'g|{}'.format(s)


def pair_key(s):
    return 'p|{}'.format(s)


def filter_key(k, v):
    return 'f|{}|{}'.format(k, v)


def extract_trigrams(trigrams, string, boost):
    tokens = list(preprocess(string))
    if not tokens:
        return
    boost = config.DEFAULT_BOOST / len(tokens) * boost
    for token in tokens:
        els = compute_trigrams(token)
        if not els:
            print('No trigrams for', token, 'returning')
            continue
        for trigram in els:
            if trigrams.get(trigram, 0) < boost:
                trigrams[trigram] = boost


def index_trigrams(pipe, trigrams, key):
    for token, boost in trigrams.items():
        pipe.zadd(token_key(token), boost, key)


def deindex_field(key, string):
    tokens = list(preprocess(string.decode()))
    for token in tokens:
        trigrams = compute_trigrams(token)
        for trigram in trigrams:
            deindex_trigram(key, trigram)
    return tokens


def deindex_trigram(key, trigram):
    tkey = token_key(trigram)
    DB.zrem(tkey, key)


def index_housenumbers(pipe, housenumbers, doc, key):
    if not housenumbers:
        return
    del doc['housenumbers']
    to_index = {}
    for number, point in housenumbers.items():
        vals = [number, point['lat'], point['lon']]
        for field in config.HOUSENUMBERS_PAYLOAD_FIELDS:
            vals.append(point.get(field, ''))
        val = '|'.join(map(str, vals))
        for hn in preprocess_housenumber(number):
            doc[housenumber_field_key(hn)] = val
            trigrams = compute_trigrams(hn)
            for trigram in trigrams:
                to_index[trigram] = config.DEFAULT_BOOST
        index_geohash(pipe, key, point['lat'], point['lon'])
    index_trigrams(pipe, to_index, key)


def deindex_housenumbers(key, doc):
    for field, value in doc.items():
        field = field.decode()
        if not field.startswith('h|'):
            continue
        number, lat, lon, *extra = value.decode().split('|')
        hn = field[2:]
        deindex_geohash(key, lat, lon)
        for trigram in compute_trigrams(hn):
            deindex_trigram(key, hn)


def index_filters(pipe, key, doc):
    for name in config.FILTERS:
        value = doc.get(name)
        if value:
            # We need a SortedSet because it will be used in intersect with
            # tokens SortedSets.
            pipe.sadd(filter_key(name, value), key)
    # Special case for housenumber type, because it's not a real type
    if "type" in config.FILTERS and config.HOUSENUMBERS_FIELD \
       and doc.get(config.HOUSENUMBERS_FIELD):
        pipe.sadd(filter_key("type", "housenumber"), key)


def deindex_filters(key, doc):
    for name in config.FILTERS:
        # Doc is raw from DB, so it has byte keys.
        value = doc.get(name.encode())
        if value:
            # Doc is raw from DB, so it has byte values.
            DB.srem(filter_key(name, value.decode()), key)
    if "type" in config.FILTERS:
        DB.srem(filter_key("type", "housenumber"), key)


def index_document(doc):
    key = document_key(doc['id'])
    pipe = DB.pipeline()
    housenumbers = None
    index_geohash(pipe, key, doc['lat'], doc['lon'])
    importance = float(doc.get('importance', 0.0)) * config.IMPORTANCE_WEIGHT
    tokens = {}
    for field in config.FIELDS:
        name = field['key']
        values = doc.get(name)
        if not values:
            if not field.get('null', True):
                # A mandatory field is null.
                return
            continue
        if name == config.HOUSENUMBERS_FIELD:
            housenumbers = values
        else:
            boost = field.get('boost', config.DEFAULT_BOOST)
            if callable(boost):
                boost = boost(doc)
            boost = boost + importance
            if isinstance(values, (list, tuple)):
                # We can't save a list as redis hash value.
                doc[name] = VALUE_SEPARATOR.join(values)
            else:
                values = [values]
            for value in values:
                extract_trigrams(tokens, value, boost=boost)
    index_trigrams(pipe, tokens, key)
    index_filters(pipe, key, doc)
    index_housenumbers(pipe, housenumbers, doc, key)
    pipe.hmset(key, doc)
    pipe.execute()


def deindex_document(id_):
    key = document_key(id_)
    doc = DB.hgetall(key)
    if not doc:
        return
    DB.delete(key)
    deindex_geohash(key, doc[b'lat'], doc[b'lon'])
    for field in config.FIELDS:
        name = field['key']
        values = doc.get(name.encode())
        if values:
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                deindex_field(key, value)
    deindex_filters(key, doc)
    deindex_housenumbers(key, doc)


def index_geohash(pipe, key, lat, lon):
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    pipe.sadd(geok, key)


def deindex_geohash(key, lat, lon):
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    DB.srem(geok, key)
