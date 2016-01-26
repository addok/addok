import geohash

from addok import config
from addok.db import DB

from . import iter_pipe, keys

VALUE_SEPARATOR = '|~|'

HOUSENUMBER_PROCESSORS = []


def preprocess(s):
    if s not in _CACHE:
        _CACHE[s] = list(iter_pipe(s, config.PROCESSORS))
    return _CACHE[s]
_CACHE = {}


def preprocess_housenumber(s):
    if not HOUSENUMBER_PROCESSORS:
        HOUSENUMBER_PROCESSORS.extend(config.HOUSENUMBER_PROCESSORS)
        HOUSENUMBER_PROCESSORS.extend(config.PROCESSORS)
    if s not in _HOUSENUMBER_CACHE:
        _HOUSENUMBER_CACHE[s] = list(iter_pipe(s, HOUSENUMBER_PROCESSORS))
    return _HOUSENUMBER_CACHE[s]
_HOUSENUMBER_CACHE = {}


def token_key_frequency(key):
    return DB.zcard(key)


def token_frequency(token):
    return token_key_frequency(keys.token_key(token))


def extract_tokens(tokens, string, boost):
    els = list(preprocess(string))
    if not els:
        return
    boost = config.DEFAULT_BOOST / len(els) * boost
    for token in els:
        if tokens.get(token, 0) < boost:
            tokens[token] = boost


def index_tokens(pipe, tokens, key, **kwargs):
    for token, boost in tokens.items():
        pipe.zadd(keys.token_key(token), boost, key)


def deindex_field(key, string):
    els = list(preprocess(string.decode()))
    for s in els:
        deindex_token(key, s)
    return els


def deindex_token(key, token):
    tkey = keys.token_key(token)
    DB.zrem(tkey, key)


def index_document(doc, **kwargs):
    key = keys.document_key(doc['id'])
    pipe = DB.pipeline()
    tokens = {}
    for indexer in config.INDEXERS:
        try:
            indexer(pipe, key, doc, tokens, **kwargs)
        except ValueError as e:
            print(e)
            return  # Do not index.
    pipe.execute()


def deindex_document(id_, **kwargs):
    key = keys.document_key(id_)
    doc = DB.hgetall(key)
    if not doc:
        return
    tokens = []
    for indexer in config.DEINDEXERS:
        indexer(DB, key, doc, tokens, **kwargs)


def index_geohash(pipe, key, lat, lon):
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = keys.geohash_key(geoh)
    pipe.sadd(geok, key)


def deindex_geohash(key, lat, lon):
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = keys.geohash_key(geoh)
    DB.srem(geok, key)


def fields_indexer(pipe, key, doc, tokens, **kwargs):
    importance = float(doc.get('importance', 0.0)) * config.IMPORTANCE_WEIGHT
    for field in config.FIELDS:
        name = field['key']
        values = doc.get(name)
        if not values:
            if not field.get('null', True):
                # A mandatory field is null.
                raise ValueError('{} must not be null'.format(name))
            continue
        if name != config.HOUSENUMBERS_FIELD:
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
                extract_tokens(tokens, value, boost=boost)
    index_tokens(pipe, tokens, key, **kwargs)


def fields_deindexer(db, key, doc, tokens, **kwargs):
    for field in config.FIELDS:
        name = field['key']
        values = doc.get(name.encode())
        if values:
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                tokens.extend(deindex_field(key, value))


def document_indexer(pipe, key, doc, tokens, **kwargs):
    index_geohash(pipe, key, doc['lat'], doc['lon'])
    pipe.hmset(key, doc)


def document_deindexer(db, key, doc, tokens, **kwargs):
    db.delete(key)
    deindex_geohash(key, doc[b'lat'], doc[b'lon'])


def housenumbers_indexer(pipe, key, doc, tokens, **kwargs):
    housenumbers = doc.get(config.HOUSENUMBERS_FIELD)
    if not housenumbers:
        return
    del doc['housenumbers']
    to_index = {}
    for number, point in housenumbers.items():
        vals = [number, point['lat'], point['lon']]
        for field in config.HOUSENUMBERS_PAYLOAD_FIELDS:
            vals.append(point.get(field, ''))
        val = '|'.join(map(str, vals))
        for hn in preprocess_housenumber(number.replace(' ', '')):
            doc[keys.housenumber_field_key(hn)] = val
            to_index[hn] = config.DEFAULT_BOOST
        index_geohash(pipe, key, point['lat'], point['lon'])
    index_tokens(pipe, to_index, key, **kwargs)


def housenumbers_deindexer(db, key, doc, tokens, **kwargs):
    for field, value in doc.items():
        field = field.decode()
        if not field.startswith('h|'):
            continue
        number, lat, lon, *extra = value.decode().split('|')
        hn = field[2:]
        deindex_geohash(key, lat, lon)
        deindex_token(key, hn)


def filters_indexer(pipe, key, doc, tokens, **kwargs):
    for name in config.FILTERS:
        value = doc.get(name)
        if value:
            # We need a SortedSet because it will be used in intersect with
            # tokens SortedSets.
            pipe.sadd(keys.filter_key(name, value), key)
    # Special case for housenumber type, because it's not a real type
    if "type" in config.FILTERS and config.HOUSENUMBERS_FIELD \
       and doc.get(config.HOUSENUMBERS_FIELD):
        pipe.sadd(keys.filter_key("type", "housenumber"), key)


def filters_deindexer(db, key, doc, tokens, **kwargs):
    for name in config.FILTERS:
        # Doc is raw from DB, so it has byte keys.
        value = doc.get(name.encode())
        if value:
            # Doc is raw from DB, so it has byte values.
            db.srem(keys.filter_key(name, value.decode()), key)
    if "type" in config.FILTERS:
        db.srem(keys.filter_key("type", "housenumber"), key)
