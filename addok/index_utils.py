import geohash

from . import config
from .core import (DB, token_key, document_key, housenumber_field_key,
                   edge_ngram_key, geohash_key)
from .pipeline import preprocess
from .textutils.default import compute_edge_ngrams


def index_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.sadd(edge_ngram_key(ngram), token)


def index_housenumber(pipe, key, document):
    val = '|'.join([
        str(document['housenumber']), str(document['lat']),
        str(document['lon'])
    ])
    for hn in preprocess(str(document['housenumber'])):
        pipe.hset(key, housenumber_field_key(hn), val)


def index_field(pipe, key, string, boost=1.0):
    els = list(preprocess(string))
    for s in els:
        pipe.zadd(token_key(s), 1.0 / len(els) * boost, key)


def index_document(document):
    key = document_key(document['id'])
    exists = DB.exists(key)
    pipe = DB.pipeline()
    if document['type'] == 'housenumber':
        index_housenumber(pipe, key, document)
        index_field(pipe, key, str(document['housenumber']))
    index_geohash(pipe, document)
    if not exists or document['type'] != 'housenumber':
        document.pop('housenumber', None)  # When we create the street from the
                                           # housenumber row.
        pipe.hmset(key, document)
        name = document['name']
        index_field(pipe, key, name, boost=4.0)
        city = document.get('city')
        if city and city != name:
            index_field(pipe, key, city)
        postcode = document.get('postcode')
        if postcode:
            boost = 1.2 if document['type'] == 'commune' else 1
            index_field(pipe, key, postcode, boost=boost)
        context = document.get('context')
        if context:
            index_field(pipe, key, context)
    pipe.execute()


def index_geohash(pipe, doc):
    key = '|'.join([doc['id'], str(doc.get('housenumber', ''))])
    lat = float(doc['lat'])
    lon = float(doc['lon'])
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    pipe.sadd(geok, key)
