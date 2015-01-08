import geohash

from . import config
from .core import (DB, token_key, document_key, housenumber_field_key,
                   edge_ngram_key, geohash_key)
from .pipeline import preprocess
from .textutils.default import compute_edge_ngrams


def index_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.sadd(edge_ngram_key(ngram), token)


def index_field(pipe, key, string, boost=1.0):
    els = list(preprocess(string))
    for s in els:
        pipe.zadd(token_key(s), 1.0 / len(els) * boost, key)


def index_document(doc):
    key = document_key(doc['id'])
    pipe = DB.pipeline()
    index_geohash(pipe, doc['id'], '', doc['lat'], doc['lon'])
    name = doc['name']
    index_field(pipe, key, name, boost=4.0)
    city = doc.get('city')
    if city and city != name:
        index_field(pipe, key, city)
    postcode = doc.get('postcode')
    if postcode:
        boost = 1.2 if doc['type'] == 'commune' else 1
        index_field(pipe, key, postcode, boost=boost)
    context = doc.get('context')
    if context:
        index_field(pipe, key, context)
    housenumbers = doc.get('housenumbers')
    if housenumbers:
        del doc['housenumbers']
        for number, point in housenumbers.items():
            val = '|'.join([str(number), str(point['lat']), str(point['lon'])])
            for hn in preprocess(number):
                doc[housenumber_field_key(hn)] = val
            index_field(pipe, key, str(number))
            index_geohash(pipe, doc['id'], number, point['lat'], point['lon'])
    pipe.hmset(key, doc)
    pipe.execute()


def index_geohash(pipe, _id, number, lat, lon):
    key = '|'.join([_id, str(number)])
    lat = float(lat)
    lon = float(lon)
    geoh = geohash.encode(lat, lon, config.GEOHASH_PRECISION)
    geok = geohash_key(geoh)
    pipe.sadd(geok, key)
