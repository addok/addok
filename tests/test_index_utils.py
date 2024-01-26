import json
import sys
import pytest

from addok import ds
from addok.autocomplete import create_edge_ngrams, index_edge_ngrams
from addok.batch import process_documents
from addok.db import DB


def index_document(doc):
    process_documents(json.dumps(doc))


def deindex_document(_id):
    process_documents(json.dumps({"_id": _id, "_action": "delete"}))


def count_keys():
    """Helper method to return the number of keys in the test database."""
    try:
        return DB.info()["db14"]["keys"]
    except KeyError:
        return 0


def test_index_edge_ngrams():
    before = count_keys()
    index_edge_ngrams(DB, "street")
    after = count_keys()
    assert after - before == 3
    assert DB.smembers("n|str") == set([b"street"])
    assert DB.smembers("n|stre") == set([b"street"])
    assert DB.smembers("n|stree") == set([b"street"])


DOC = {
    "id": "xxxx",
    "_id": "yyyy",
    "type": "street",
    "name": "rue des Lilas",
    "city": "Andrésy",
    "lat": "48.32545",
    "lon": "2.2565",
    "housenumbers": {"1": {"lat": "48.325451", "lon": "2.25651"}},
}


def test_index_document():
    index_document(DOC.copy())
    assert ds._DB.exists("d|yyyy")
    assert ds._DB.type("d|yyyy") == b"string"
    assert DB.exists("w|rue")
    assert b"d|yyyy" in DB.zrange("w|rue", 0, -1)
    assert DB.exists("w|des")
    assert DB.exists("w|lilas")
    assert DB.exists("w|andresy")
    assert DB.exists("p|rue")
    assert DB.exists("p|des")
    assert DB.exists("p|lilas")
    assert DB.exists("p|andresy")
    assert b"lilas" in DB.smembers("p|andresy")
    assert b"andresy" in DB.smembers("p|lilas")
    assert DB.exists("g|u09dgm7")
    assert b"d|yyyy" in DB.smembers("g|u09dgm7")
    assert DB.exists("n|lil")
    assert DB.exists("n|lila")
    assert DB.exists("n|and")
    assert b"andresy" in DB.smembers("n|and")
    assert DB.exists("n|andr")
    assert b"andresy" in DB.smembers("n|andr")
    assert DB.exists("n|andre")
    assert b"andresy" in DB.smembers("n|andre")
    assert DB.exists("n|andres")
    assert b"andresy" in DB.smembers("n|andres")
    assert b"lilas" in DB.smembers("n|lil")
    assert DB.exists("f|type|street")
    assert b"d|yyyy" in DB.smembers("f|type|street")
    assert DB.exists("f|type|housenumber")
    assert b"d|yyyy" in DB.smembers("f|type|housenumber")
    assert len(DB.keys()) == 17
    assert len(ds._DB.keys()) == 1


def test_index_document_without_explicit_id():
    doc = DOC.copy()
    del doc["_id"]
    index_document(doc)
    assert ds._DB.exists("d|jR")
    assert ds._DB.type("d|jR") == b"string"
    assert DB.exists("w|rue")


def test_deindex_document_should_deindex():
    index_document(DOC.copy())
    deindex_document(DOC["_id"])
    assert not ds._DB.exists("d|xxxx")
    assert not ds._DB.exists("d|yyyy")
    assert not DB.exists("w|de")
    assert not DB.exists("w|lilas")
    assert not DB.exists("w|1")  # Housenumber.
    assert not DB.exists("p|rue")
    assert not DB.exists("p|des")
    assert not DB.exists("p|lilas")
    assert not DB.exists("p|1")
    assert not DB.exists("g|u09dgm7")
    assert not DB.exists("n|lil")
    assert not DB.exists("n|and")
    assert not DB.exists("n|andr")
    assert not DB.exists("n|andre")
    assert not DB.exists("n|andres")
    assert not DB.exists("f|type|street")
    assert len(DB.keys()) == 0
    assert len(ds._DB.keys()) == 0


def test_deindex_document_should_not_affect_other_docs():
    DOC2 = {
        "id": "xxxx2",
        "_id": "yyyy2",
        "type": "street",
        "name": "rue des Lilas",
        "city": "Paris",
        "lat": "49.32545",
        "lon": "4.2565",
        "housenumbers": {
            "1": {"lat": "48.325451", "lon": "2.25651"}  # Same geohash as DOC.
        },
    }
    DOC1 = json.loads(json.dumps(DOC))  # deepcopy.
    # Add new housenumber so we can check it's deindexed.
    DOC1["housenumbers"]["2"] = {"lat": "48.325459", "lon": "2.25659"}
    index_document(DOC1)
    index_document(DOC2)
    deindex_document(DOC1["_id"])
    assert not ds._DB.exists("d|yyyy")
    assert b"d|yyyy" not in DB.zrange("w|rue", 0, -1)
    assert b"d|yyyy" not in DB.zrange("w|des", 0, -1)
    assert b"d|yyyy" not in DB.zrange("w|lilas", 0, -1)
    assert DB.exists("g|u09dgm7")
    assert b"d|yyyy" not in DB.smembers("g|u09dgm7")
    assert DB.exists("w|des")
    assert DB.exists("w|lilas")
    assert DB.exists("p|rue")
    assert b"d|yyyy2" in DB.zrange("w|rue", 0, -1)
    assert b"d|yyyy2" in DB.zrange("w|des", 0, -1)
    assert b"d|yyyy2" in DB.zrange("w|lilas", 0, -1)
    assert b"d|yyyy2" in DB.smembers("g|u09dgm7")
    assert b"d|yyyy2" in DB.smembers("g|u0g08g7")
    assert DB.exists("p|des")
    assert DB.exists("p|lilas")
    assert not DB.exists("n|and")
    assert not DB.exists("n|andr")
    assert not DB.exists("n|andre")
    assert not DB.exists("n|andres")
    assert DB.exists("n|par")
    assert DB.exists("n|pari")
    assert DB.exists("n|lil")
    assert DB.exists("n|lila")
    assert b"lilas" in DB.smembers("n|lil")
    assert b"lilas" in DB.smembers("n|lila")
    assert DB.exists("f|type|street")
    assert b"d|yyyy2" in DB.smembers("f|type|street")
    assert DB.exists("f|type|housenumber")
    assert b"d|yyyy2" in DB.smembers("f|type|housenumber")
    assert len(DB.keys()) == 16
    assert len(ds._DB.keys()) == 1


def test_allow_list_values():
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "type": "street",
        "name": ["Vernou-la-Celle-sur-Seine", "Vernou"],
        "city": "Paris",
        "lat": "49.32545",
        "lon": "4.2565",
    }
    index_document(doc)
    assert DB.zscore("w|vernou", "d|yyyy") == 4
    assert DB.zscore("w|celle", "d|yyyy") == 4 / 5


def test_deindex_document_should_deindex_list_values():
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "type": "street",
        "name": ["Vernou-la-Celle-sur-Seine", "Vernou"],
        "city": "Paris",
        "lat": "49.32545",
        "lon": "4.2565",
    }
    index_document(doc)
    deindex_document(doc["_id"])
    assert not ds._DB.exists("d|yyyy")
    assert not DB.exists("w|vernou")
    assert not DB.exists("w|celle")
    assert len(DB.keys()) == 0


def test_deindex_document_should_not_fail_if_id_do_not_exist():
    deindex_document("xxxxx")


def test_should_be_possible_to_define_fields_from_config(config):
    config.FIELDS = [
        {"key": "custom"},
        {"key": "special"},
    ]
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "custom": "rue",
        "special": "Lilas",
        "thisone": "is not indexed",
    }
    index_document(doc)
    assert ds._DB.exists("d|yyyy")
    assert DB.exists("w|lilas")
    assert DB.exists("w|rue")
    assert not DB.exists("w|indexed")


def test_should_be_possible_to_override_boost_from_config(config):
    config.FIELDS = [
        {"key": "name", "boost": 5},
        {"key": "city"},
    ]
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "name": "Lilas",
        "city": "Cergy",
    }
    index_document(doc)
    assert ds._DB.exists("d|yyyy")
    assert DB.zscore("w|lilas", "d|yyyy") == 5
    assert DB.zscore("w|cergy", "d|yyyy") == 1


def test_should_be_possible_to_override_boost_with_callable(config):
    config.FIELDS = [
        {"key": "name", "boost": lambda doc: 5},
        {"key": "city"},
    ]
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "name": "Lilas",
        "city": "Cergy",
    }
    index_document(doc)
    assert ds._DB.exists("d|yyyy")
    assert DB.zscore("w|lilas", "d|yyyy") == 5
    assert DB.zscore("w|cergy", "d|yyyy") == 1


def test_doc_with_null_value_should_not_be_index_if_not_allowed(config):
    config.FIELDS = [
        {"key": "name", "null": False},
        {"key": "city"},
    ]
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "name": "",
        "city": "Cergy",
    }
    index_document(doc)
    assert not DB.exists("w|cergy")


def test_doc_with_array_of_array_value_should_not_be_index_if_not_allowed(config):
    config.FIELDS = [
        {"key": "name", "null": False},
        {"key": "city"},
    ]
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "name": [["Lilas"]],
        "city": "Cergy",
    }
    index_document(doc)
    assert not DB.exists("w|cergy")


def test_create_edge_ngrams(config):
    config.MIN_EDGE_NGRAMS = 2
    config.INDEX_EDGE_NGRAMS = False
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "lat": "49.32545",
        "lon": "4.2565",
        "name": "28 Lilas",  # 28 should not appear in ngrams
        "city": "Paris",
    }
    index_document(doc)
    assert not DB.exists("n|li")
    assert not DB.exists("n|lil")
    assert not DB.exists("n|lila")
    assert not DB.exists("n|pa")
    assert not DB.exists("n|par")
    assert not DB.exists("n|pari")
    create_edge_ngrams()
    assert DB.exists("n|li")
    assert DB.exists("n|lil")
    assert DB.exists("n|pa")
    assert DB.exists("n|par")
    assert not DB.exists("n|28")
    assert len(DB.keys()) == 13
    assert len(ds._DB.keys()) == 1


def test_index_document_with_custom_id(config):
    config.ID_FIELD = "custom"
    doc = DOC.copy()
    doc["custom"] = "custom_id"
    index_document(doc)
    assert ds._DB.exists("d|custom_id")
