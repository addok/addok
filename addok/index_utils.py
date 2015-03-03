import time

import geohash
from multiprocessing import Pool

from . import config
from .core import (DB, document_key, edge_ngram_key, geohash_key,
                   housenumber_field_key, pair_key, token_key)
from .pipeline import preprocess
from .textutils.default import compute_edge_ngrams


def index_edge_ngrams(pipe, token):
    for ngram in compute_edge_ngrams(token):
        pipe.sadd(edge_ngram_key(ngram), token)


def deindex_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.srem(edge_ngram_key(ngram), token)


def extract_tokens(tokens, string, boost):
    els = list(preprocess(string))
    boost = config.DEFAULT_BOOST / len(els) * boost
    for token in els:
        if token not in tokens or tokens.get(token) < boost:
            tokens[token] = boost


def index_tokens(pipe, tokens, key, update_ngrams=True):
    for token, boost in tokens.items():
        pipe.zadd(token_key(token), boost, key)
        if update_ngrams:
            index_edge_ngrams(pipe, token)


def deindex_field(key, string):
    els = list(preprocess(string.decode()))
    for s in els:
        tkey = token_key(s)
        DB.zrem(tkey, key)
        if not DB.exists(tkey):
            deindex_edge_ngrams(s)
    return els


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
    els = set(els)  # Unique values.
    for el in els:
        for el2 in els:
            if el != el2:
                key = '|'.join(['didx', el, el2])
                # Do we have other documents that share el and el2?
                commons = DB.zinterstore(key, [token_key(el), token_key(el2)])
                DB.delete(key)
                if not commons:
                    DB.srem(pair_key(el), el2)
                    DB.srem(pair_key(el2), el)


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


def index_document(doc, update_ngrams=True):
    key = document_key(doc['id'])
    pipe = DB.pipeline()
    housenumbers = None
    index_geohash(pipe, key, doc['lat'], doc['lon'])
    importance = doc.get('importance', 0.0) * config.IMPORTANCE_WEIGHT
    tokens = {}
    for field in config.FIELDS:
        value = doc.get(field['key'])
        if not value:
            if not field.get('null', True):
                # A mandatory field is null.
                return
            continue
        if field.get('type') == 'housenumbers':
            housenumbers = value
        else:
            boost = field.get('boost', config.DEFAULT_BOOST)
            if callable(boost):
                boost = boost(doc)
            boost = boost + importance
            extract_tokens(tokens, value, boost=boost)
    index_tokens(pipe, tokens, key, update_ngrams)
    index_pairs(pipe, tokens.keys())
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
    pair_els = []
    for name, value in doc.items():
        pair_els.extend(deindex_field(key, value))
    deindex_pairs(pair_els)


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
