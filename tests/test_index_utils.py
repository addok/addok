from addok.db import DB
from addok.index_utils import (index_edge_ngrams, index_document,
                               deindex_document, create_edge_ngrams)


def count_keys():
    """Helper method to return the number of keys in the test database."""
    try:
        return DB.info()['db15']['keys']
    except KeyError:
        return 0


def test_index_edge_ngrams():
    before = count_keys()
    index_edge_ngrams(DB, 'street')
    after = count_keys()
    assert after - before == 3
    assert DB.smembers('n|str') == set([b'street'])
    assert DB.smembers('n|stre') == set([b'street'])
    assert DB.smembers('n|stree') == set([b'street'])


DOC = {
    'id': 'xxxx',
    'type': 'street',
    'name': 'rue des Lilas',
    'city': 'Andrésy',
    'lat': '48.32545',
    'lon': '2.2565',
    'housenumbers': {
        '1': {
            'lat': '48.325451',
            'lon': '2.25651'
        }
    }
}


def test_index_document():
    index_document(DOC.copy())
    assert DB.exists('d|xxxx')
    assert DB.type('d|xxxx') == b'hash'
    assert DB.exists('w|ru')
    assert b'd|xxxx' in DB.zrange('w|ru', 0, -1)
    assert DB.exists('w|de')
    assert DB.exists('w|lila')
    assert DB.exists('w|andrezi')
    assert DB.exists('w|un')  # Housenumber.
    assert DB.exists('p|ru')
    assert DB.exists('p|de')
    assert DB.exists('p|lila')
    assert DB.exists('p|andrezi')
    assert b'lila' in DB.smembers('p|andrezi')
    assert b'andrezi' in DB.smembers('p|lila')
    assert DB.exists('p|un')
    assert DB.exists('g|u09dgm7')
    assert b'd|xxxx' in DB.smembers('g|u09dgm7')
    assert DB.exists('n|lil')
    assert DB.exists('n|and')
    assert b'andrezi' in DB.smembers('n|and')
    assert DB.exists('n|andr')
    assert b'andrezi' in DB.smembers('n|andr')
    assert DB.exists('n|andre')
    assert b'andrezi' in DB.smembers('n|andre')
    assert DB.exists('n|andrez')
    assert b'andrezi' in DB.smembers('n|andrez')
    assert b'lila' in DB.smembers('n|lil')
    assert DB.exists('f|type|street')
    assert b'd|xxxx' in DB.smembers('f|type|street')
    assert DB.exists('f|type|housenumber')
    assert b'd|xxxx' in DB.smembers('f|type|housenumber')
    assert len(DB.keys()) == 19


def test_deindex_document_should_deindex():
    index_document(DOC.copy())
    deindex_document(DOC['id'])
    assert not DB.exists('d|xxxx')
    assert not DB.exists('w|de')
    assert not DB.exists('w|lila')
    assert not DB.exists('w|un')  # Housenumber.
    assert not DB.exists('p|ru')
    assert not DB.exists('p|de')
    assert not DB.exists('p|lila')
    assert not DB.exists('p|un')
    assert not DB.exists('g|u09dgm7')
    assert not DB.exists('n|lil')
    assert not DB.exists('n|and')
    assert not DB.exists('n|andr')
    assert not DB.exists('n|andre')
    assert not DB.exists('n|andrez')
    assert not DB.exists('f|type|street')
    assert len(DB.keys()) == 0


def test_deindex_document_should_not_affect_other_docs():
    DOC2 = {
        'id': 'xxxx2',
        'type': 'street',
        'name': 'rue des Lilas',
        'city': 'Paris',
        'lat': '49.32545',
        'lon': '4.2565',
        'housenumbers': {
            '1': {
                'lat': '48.325451',  # Same geohash as DOC.
                'lon': '2.25651'
            }
        }
    }
    index_document(DOC.copy())
    index_document(DOC2)
    deindex_document(DOC['id'])
    assert not DB.exists('d|xxxx')
    assert b'd|xxxx' not in DB.zrange('w|ru', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|de', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|lila', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|un', 0, -1)
    assert DB.exists('g|u09dgm7')
    assert b'd|xxxx' not in DB.smembers('g|u09dgm7')
    assert DB.exists('w|de')
    assert DB.exists('w|lila')
    assert DB.exists('w|un')  # Housenumber.
    assert DB.exists('p|ru')
    assert b'd|xxxx2' in DB.zrange('w|ru', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|de', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|lila', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|un', 0, -1)
    assert b'd|xxxx2' in DB.smembers('g|u09dgm7')
    assert b'd|xxxx2' in DB.smembers('g|u0g08g7')
    assert DB.exists('p|de')
    assert DB.exists('p|lila')
    assert DB.exists('p|un')
    assert not DB.exists('n|and')
    assert not DB.exists('n|andr')
    assert not DB.exists('n|andre')
    assert not DB.exists('n|andrez')
    assert DB.exists('n|par')
    assert DB.exists('n|lil')
    assert b'lila' in DB.smembers('n|lil')
    assert DB.exists('f|type|street')
    assert b'd|xxxx2' in DB.smembers('f|type|street')
    assert DB.exists('f|type|housenumber')
    assert b'd|xxxx2' in DB.smembers('f|type|housenumber')
    assert len(DB.keys()) == 17


def test_index_housenumber_uses_housenumber_preprocessors():
    # By default it glues ordinal to number
    doc = {
        'id': 'xxxx',
        'type': 'street',
        'name': 'rue des Lilas',
        'city': 'Paris',
        'lat': '49.32545',
        'lon': '4.2565',
        'housenumbers': {
            '1 bis': {
                'lat': '48.325451',
                'lon': '2.25651'
            }
        }
    }
    index_document(doc)
    index = DB.hgetall('d|xxxx')
    assert index[b'h|1b'] == b'1 bis|48.325451|2.25651| '


def test_allow_list_values():
    doc = {
        'id': 'xxxx',
        'type': 'street',
        'name': ['Vernou-la-Celle-sur-Seine', 'Vernou'],
        'city': 'Paris',
        'lat': '49.32545',
        'lon': '4.2565'
    }
    index_document(doc)
    assert DB.zscore('w|vernou', 'd|xxxx') == 4
    assert DB.zscore('w|sel', 'd|xxxx') == 4 / 5


def test_deindex_document_should_deindex_list_values():
    doc = {
        'id': 'xxxx',
        'type': 'street',
        'name': ['Vernou-la-Celle-sur-Seine', 'Vernou'],
        'city': 'Paris',
        'lat': '49.32545',
        'lon': '4.2565'
    }
    index_document(doc)
    deindex_document(doc['id'])
    assert not DB.exists('d|xxxx')
    assert not DB.exists('w|vernou')
    assert not DB.exists('w|sel')
    assert len(DB.keys()) == 0


def test_deindex_document_should_not_fail_if_id_do_not_exist():
    deindex_document('xxxxx')


def test_should_be_possible_to_define_fields_from_config(config):
    config.FIELDS = [
        {'key': 'custom'},
        {'key': 'special'},
    ]
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'custom': 'rue',
        'special': 'Lilas',
        'thisone': 'is not indexed',
    }
    index_document(doc)
    assert DB.exists('d|xxxx')
    assert DB.exists('w|lila')
    assert DB.exists('w|ru')
    assert not DB.exists('w|indexed')


def test_should_be_possible_to_override_boost_from_config(config):
    config.FIELDS = [
        {'key': 'name', 'boost': 5},
        {'key': 'city'},
    ]
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': 'Lilas',
        'city': 'Cergy'
    }
    index_document(doc)
    assert DB.exists('d|xxxx')
    assert DB.zscore('w|lila', 'd|xxxx') == 5
    assert DB.zscore('w|serji', 'd|xxxx') == 1


def test_should_be_possible_to_override_boost_with_callable(config):
    config.FIELDS = [
        {'key': 'name', 'boost': lambda doc: 5},
        {'key': 'city'},
    ]
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': 'Lilas',
        'city': 'Cergy'
    }
    index_document(doc)
    assert DB.exists('d|xxxx')
    assert DB.zscore('w|lila', 'd|xxxx') == 5
    assert DB.zscore('w|serji', 'd|xxxx') == 1


def test_doc_with_null_value_should_not_be_index_if_not_allowed(config):
    config.FIELDS = [
        {'key': 'name', 'null': False},
        {'key': 'city'},
    ]
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': '',
        'city': 'Cergy'
    }
    index_document(doc)
    assert not DB.exists('d|xxxx')


def test_null_value_should_not_be_index(config):
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': 'Port-Cergy',
        'city': ''
    }
    index_document(doc)
    assert 'city' not in DB.hgetall('d|xxxx')


def test_field_with_only_non_alphanumeric_chars_is_not_indexed():
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': 'Lilas',
        'city': '//'
    }
    index_document(doc)
    assert 'city' not in DB.hgetall('d|xxxx')


def test_create_edge_ngrams(config):
    config.MIN_EDGE_NGRAMS = 2
    doc = {
        'id': 'xxxx',
        'lat': '49.32545',
        'lon': '4.2565',
        'name': '28 Lilas',  # 28 should not appear in ngrams
        'city': 'Paris'
    }
    index_document(doc, update_ngrams=False)
    assert not DB.exists('n|li')
    assert not DB.exists('n|lil')
    assert not DB.exists('n|pa')
    assert not DB.exists('n|par')
    create_edge_ngrams()
    assert DB.exists('n|li')
    assert DB.exists('n|lil')
    assert DB.exists('n|pa')
    assert DB.exists('n|par')
    assert not DB.exists('n|28')
    assert len(DB.keys()) == 12
