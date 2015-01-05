import geohash

from . import config
from .core import (DB, token_key, document_key, housenumber_field_key,
                   edge_ngram_key, geohash_key)
from .pipeline import preprocess
from .textutils.default import compute_edge_ngrams


def index_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.sadd(edge_ngram_key(ngram), token)


def index_housenumber(key, document):
    val = '|'.join([document['housenumber'], document['lat'], document['lon']])
    for hn in preprocess(document['housenumber']):
        DB.hset(key, housenumber_field_key(hn), val)


def index_field(key, string, boost=1.0):
    els = list(preprocess(string))
    for s in els:
        DB.zadd(token_key(s), 1.0 / len(els) * boost, key)


def index_document(document):
    key = document_key(document['id'])
    exists = DB.exists(key)
    if document['type'] == 'housenumber':
        index_housenumber(key, document)
        index_field(key, document['housenumber'])
    if not exists or document['type'] != 'housenumber':
        document.pop('housenumber', None)  # When we create the street from the
                                           # housenumber row.
        DB.hmset(key, document)
        name = document['name']
        index_field(key, name, boost=3.0)
        city = document.get('city')
        if city and city != name:
            index_field(key, city)
        postcode = document.get('postcode')
        if postcode:
            boost = 1.2 if document['type'] == 'city' else 1
            index_field(key, postcode, boost=boost)
    index_geohash(key, float(document['lat']), float(document['lon']))


def index_geohash(key, lat, lon):
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    DB.sadd(geok, key)
