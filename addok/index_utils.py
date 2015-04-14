import time
from multiprocessing import Pool

import geohash

from . import config
from .utils import import_by_path, iter_pipe
from .db import DB
from .textutils.default import compute_edge_ngrams


PROCESSORS = [import_by_path(path) for path in config.PROCESSORS]


def preprocess(s):
    if s not in _CACHE:
        _CACHE[s] = list(iter_pipe(s, PROCESSORS))
    return _CACHE[s]
_CACHE = {}


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


def pair_key(s):
    return 'p|{}'.format(s)


def filter_key(k, v):
    return 'f|{}|{}'.format(k, v)


def index_edge_ngrams(pipe, token):
    for ngram in compute_edge_ngrams(token):
        pipe.sadd(edge_ngram_key(ngram), token)


def deindex_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.srem(edge_ngram_key(ngram), token)


def extract_tokens(tokens, string, boost):
    els = list(preprocess(string))
    if not els:
        return
    boost = config.DEFAULT_BOOST / len(els) * boost
    for token in els:
        if tokens.get(token, 0) < boost:
            tokens[token] = boost


def index_tokens(pipe, tokens, key, update_ngrams=True):
    for token, boost in tokens.items():
        pipe.zadd(token_key(token), boost, key)
        if update_ngrams:
            index_edge_ngrams(pipe, token)


def deindex_field(key, string):
    els = list(preprocess(string.decode()))
    for s in els:
        deindex_token(key, s)
    return els


def deindex_token(key, token):
    tkey = token_key(token)
    DB.zrem(tkey, key)
    if not DB.exists(tkey):
        deindex_edge_ngrams(token)


def index_pairs(pipe, els):
    els = set(els)  # Unique values.
    for el in els:
        values = set([])
        for el2 in els:
            if el != el2:
                values.add(el2)
        if values:
            pipe.sadd(pair_key(el), *values)


def deindex_pairs(els):
    els = list(set(els))  # Unique values.
    loop = 0
    for el in els:
        for el2 in els[loop:]:
            if el != el2:
                key = '|'.join(['didx', el, el2])
                # Do we have other documents that share el and el2?
                commons = DB.zinterstore(key, [token_key(el), token_key(el2)])
                DB.delete(key)
                if not commons:
                    DB.srem(pair_key(el), el2)
                    DB.srem(pair_key(el2), el)
        loop += 1


def index_housenumbers(pipe, housenumbers, doc, key, tokens, update_ngrams):
    if not housenumbers:
        return
    del doc['housenumbers']
    to_index = {}
    for number, point in housenumbers.items():
        val = '|'.join([str(number), str(point['lat']), str(point['lon'])])
        for hn in preprocess(number):
            doc[housenumber_field_key(hn)] = val
            # Pair every document term to each housenumber, but do not pair
            # housenumbers together.
            pipe.sadd(pair_key(hn), *tokens.keys())
            to_index[hn] = config.DEFAULT_BOOST
        index_geohash(pipe, key, point['lat'], point['lon'])
    index_tokens(pipe, to_index, key, update_ngrams)


def deindex_housenumbers(key, doc, tokens):
    for field, value in doc.items():
        field = field.decode()
        if not field.startswith('h|'):
            continue
        number, lat, lon = value.decode().split('|')
        hn = field[2:]
        for token in tokens:
            k = '|'.join(['didx', hn, token])
            commons = DB.zinterstore(k, [token_key(hn), token_key(token)])
            DB.delete(k)
            if not commons:
                DB.srem(pair_key(hn), token)
                DB.srem(pair_key(token), hn)
        deindex_geohash(key, lat, lon)
        deindex_token(key, hn)


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


def index_document(doc, update_ngrams=True):
    key = document_key(doc['id'])
    pipe = DB.pipeline()
    housenumbers = None
    index_geohash(pipe, key, doc['lat'], doc['lon'])
    importance = float(doc.get('importance', 0.0)) * config.IMPORTANCE_WEIGHT
    tokens = {}
    for field in config.FIELDS:
        name = field['key']
        value = doc.get(name)
        if not value:
            if not field.get('null', True):
                # A mandatory field is null.
                return
            continue
        if name == config.HOUSENUMBERS_FIELD:
            housenumbers = value
        else:
            boost = field.get('boost', config.DEFAULT_BOOST)
            if callable(boost):
                boost = boost(doc)
            boost = boost + importance
            extract_tokens(tokens, value, boost=boost)
    index_tokens(pipe, tokens, key, update_ngrams)
    index_pairs(pipe, tokens.keys())
    index_filters(pipe, key, doc)
    index_housenumbers(pipe, housenumbers, doc, key, tokens, update_ngrams)
    pipe.hmset(key, doc)
    pipe.execute()


def deindex_document(id_):
    key = document_key(id_)
    doc = DB.hgetall(key)
    if not doc:
        return
    DB.delete(key)
    deindex_geohash(key, doc[b'lat'], doc[b'lon'])
    tokens = []
    for field in config.FIELDS:
        name = field['key']
        value = doc.get(name.encode())
        if value:
            tokens.extend(deindex_field(key, value))
    deindex_pairs(tokens)
    deindex_filters(key, doc)
    deindex_housenumbers(key, doc, tokens)


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


def index_ngram_key(key):
    key = key.decode()
    _, token = key.split('|')
    if token.isdigit():
        return
    index_edge_ngrams(DB, token)


def create_edge_ngrams():
    start = time.time()
    pool = Pool()
    count = 0
    chunk = []
    for key in DB.scan_iter(match='w|*'):
        count += 1
        chunk.append(key)
        if count % 10000 == 0:
            pool.map(index_ngram_key, chunk)
            print("Done", count, time.time() - start)
            chunk = []
    if chunk:
        pool.map(index_ngram_key, chunk)
    pool.close()
    pool.join()
    print('Done', count, 'in', time.time() - start)
