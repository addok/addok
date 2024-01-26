import geohash
import redis

from addok.config import config
from addok.db import DB
from addok.ds import get_document

from . import iter_pipe, keys, yielder

VALUE_SEPARATOR = "|~|"


def preprocess(s):
    if s not in _CACHE:
        _CACHE[s] = list(iter_pipe(s, config.PROCESSORS))
    return _CACHE[s]


_CACHE = {}


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
        pipe.zadd(keys.token_key(token), mapping={key: boost})


def deindex_field(key, string):
    els = list(preprocess(string))
    for s in els:
        deindex_token(key, s)
    return els


def deindex_token(key, token):
    tkey = keys.token_key(token)
    DB.zrem(tkey, key)


def index_documents(docs):
    pipe = DB.pipeline(transaction=False)
    for doc in docs:
        if not doc:
            continue
        if doc.get("_action") in ["delete", "update"]:
            key = keys.document_key(doc[config.ID_FIELD]).encode()
            known_doc = get_document(key)
            if known_doc:
                deindex_document(known_doc)
        if doc.get("_action") in ["index", "update", None]:
            index_document(pipe, doc)
        yield doc
    try:
        pipe.execute()
    except redis.RedisError as e:
        msg = "Error while importing document:\n{}\n{}".format(doc, str(e))
        raise ValueError(msg)


def index_document(pipe, doc, **kwargs):
    key = keys.document_key(doc[config.ID_FIELD])
    tokens = {}
    for indexer in config.INDEXERS:
        try:
            indexer.index(pipe, key, doc, tokens, **kwargs)
        except ValueError as e:
            print(e)
            return  # Do not index.


def deindex_document(doc, **kwargs):
    key = keys.document_key(doc[config.ID_FIELD])
    tokens = []
    for indexer in config.INDEXERS:
        indexer.deindex(DB, key, doc, tokens, **kwargs)


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


def check_type_and_transform_to_array(name, values):
    # Transform to array
    if isinstance(values, (float, int, str)):
        values = [values]
    # Check type
    if not all(isinstance(item, (float, int, str)) for item in values):
        raise ValueError("{} must be of type float, integer or string (or an array of these types)".format(name))
    return values


class FieldsIndexer:
    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        importance = float(doc.get("importance", 0.0)) * config.IMPORTANCE_WEIGHT
        for field in config.FIELDS:
            name = field["key"]
            values = doc.get(name)
            if not values:
                if not field.get("null", True):
                    # A mandatory field is null.
                    raise ValueError("{} must not be null".format(name))
                continue
            if name != config.HOUSENUMBERS_FIELD:
                boost = field.get("boost", config.DEFAULT_BOOST)
                if callable(boost):
                    boost = boost(doc)
                boost = boost + importance
                values = check_type_and_transform_to_array(name, values)
                for value in values:
                    extract_tokens(tokens, str(value), boost=boost)
        index_tokens(pipe, tokens, key, **kwargs)

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        for field in config.FIELDS:
            name = field["key"]
            if name == config.HOUSENUMBERS_FIELD:
                continue
            values = doc.get(name)
            if values:
                values = check_type_and_transform_to_array(name, values)
                for value in values:
                    tokens.extend(deindex_field(key, value))


class GeohashIndexer:
    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        index_geohash(pipe, key, doc["lat"], doc["lon"])

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        deindex_geohash(key, doc["lat"], doc["lon"])


class HousenumbersIndexer:
    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        housenumbers = doc.get("housenumbers", {})
        for number, data in housenumbers.items():
            index_geohash(pipe, key, data["lat"], data["lon"])

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        housenumbers = doc.get("housenumbers", {})
        for token, data in housenumbers.items():
            deindex_geohash(key, data["lat"], data["lon"])


class FiltersIndexer:
    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        for name in config.FILTERS:
            values = doc.get(name)
            if values:
                values = check_type_and_transform_to_array(name, values)
                for value in values:
                    pipe.sadd(keys.filter_key(name, value), key)
        # Special case for housenumber type, because it's not a real type
        if (
            "type" in config.FILTERS
            and config.HOUSENUMBERS_FIELD
            and doc.get(config.HOUSENUMBERS_FIELD)
        ):
            pipe.sadd(keys.filter_key("type", "housenumber"), key)

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        for name in config.FILTERS:
            values = doc.get(name)
            if values:
                values = check_type_and_transform_to_array(name, values)
                for value in values:
                    db.srem(keys.filter_key(name, value), key)
        if "type" in config.FILTERS:
            db.srem(keys.filter_key("type", "housenumber"), key)


@yielder
def prepare_housenumbers(doc):
    # We need to have the housenumbers tokenized in the document, to match
    # from user query (see results.match_housenumber).
    if not doc:
        return
    housenumbers = doc.get(config.HOUSENUMBERS_FIELD)
    if housenumbers:
        doc["housenumbers"] = {}
        for number, data in housenumbers.items():
            # Housenumber may have multiple tokens (eg.: "dix huit").
            token = "".join(list(preprocess(number)))
            data["raw"] = number
            doc["housenumbers"][token] = data
    return doc
