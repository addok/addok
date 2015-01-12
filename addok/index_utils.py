import geohash

from . import config
from .core import (DB, token_key, document_key, housenumber_field_key,
                   edge_ngram_key, geohash_key, pair_key)
from .pipeline import preprocess
from .textutils.default import compute_edge_ngrams


def index_edge_ngrams(pipe, token):
    for ngram in compute_edge_ngrams(token):
        pipe.sadd(edge_ngram_key(ngram), token)


def index_field(pipe, key, string, boost=1.0, update_ngrams=True):
    els = list(preprocess(string))
    for s in els:
        pipe.zadd(token_key(s), 1.0 / len(els) * boost, key)
        if update_ngrams:
            index_edge_ngrams(pipe, s)
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


def index_document(doc, update_ngrams=True):
    key = document_key(doc['id'])
    pipe = DB.pipeline()
    index_geohash(pipe, doc['id'], '', doc['lat'], doc['lon'])
    name = doc['name']
    importance = doc.get('importance', 0.0)
    pair_els = []
    city = doc.get('city')
    if city and city != name:
        pair_els.extend(index_field(pipe, key, city,
                                    update_ngrams=update_ngrams))
    postcode = doc.get('postcode')
    if postcode:
        boost = 1.2 if doc['type'] == 'commune' else 1
        els = index_field(pipe, key, postcode, boost=boost,
                          update_ngrams=update_ngrams)
        pair_els.extend(els)
    context = doc.get('context')
    if context:
        els = index_field(pipe, key, context, update_ngrams=update_ngrams)
        pair_els.extend(els)
    housenumbers = doc.get('housenumbers')
    if housenumbers:
        del doc['housenumbers']
        for number, point in housenumbers.items():
            val = '|'.join([str(number), str(point['lat']), str(point['lon'])])
            for hn in preprocess(number):
                doc[housenumber_field_key(hn)] = val
            index_field(pipe, key, str(number), update_ngrams=update_ngrams)
            index_geohash(pipe, doc['id'], number, point['lat'], point['lon'])
    # Process name last, to give priority to higher score, in case same token
    # is in two fields (for example: "rue de xxx, ile de france" contains
    # twice "de")
    pair_els.extend(index_field(pipe, key, name, boost=4.0 + importance,
                                update_ngrams=update_ngrams))
    index_pairs(pipe, pair_els)
    pipe.hmset(key, doc)
    pipe.execute()


def index_geohash(pipe, _id, number, lat, lon):
    key = '|'.join([_id, str(number)])
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    pipe.sadd(geok, key)
