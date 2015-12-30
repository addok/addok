from addok.db import DB
from addok.index_utils import index_document, deindex_document


def count_keys():
    """Helper method to return the number of keys in the test database."""
    try:
        return DB.info()['db15']['keys']
    except KeyError:
        return 0

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
    assert DB.exists('t|ru')
    assert b'd|xxxx' in DB.zrange('t|ru', 0, -1)
    assert DB.exists('t|de')
    assert DB.exists('t|lil')
    assert DB.exists('t|ila')
    assert DB.exists('t|and')
    assert DB.exists('t|ndr')
    assert DB.exists('t|dre')
    assert DB.exists('t|rez')
    assert DB.exists('t|ezi')
    assert DB.exists('t|un')  # Housenumber.
    assert DB.exists('g|u09dgm7')
    assert b'd|xxxx' in DB.smembers('g|u09dgm7')
    assert DB.exists('f|type|street')
    assert b'd|xxxx' in DB.smembers('f|type|street')
    assert DB.exists('f|type|housenumber')
    assert b'd|xxxx' in DB.smembers('f|type|housenumber')
    assert len(DB.keys()) == 14


def test_deindex_document_should_deindex():
    index_document(DOC.copy())
    deindex_document(DOC['id'])
    assert not DB.exists('d|xxxx')
    assert not DB.exists('t|de')
    assert not DB.exists('t|lil')
    assert not DB.exists('t|ila')
    assert not DB.exists('t|and')
    assert not DB.exists('t|ndr')
    assert not DB.exists('t|dre')
    assert not DB.exists('t|rez')
    assert not DB.exists('t|ezi')
    assert not DB.exists('t|un')  # Housenumber.
    assert not DB.exists('g|u09dgm7')
    assert not DB.exists('f|type|street')
    assert not DB.exists('f|type|housenumber')
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
    assert DB.exists('t|ru')
    assert DB.exists('t|de')
    assert DB.exists('t|lil')
    assert DB.exists('t|un')  # Housenumber.
    assert b'd|xxxx' not in DB.zrange('t|ru', 0, -1)
    assert b'd|xxxx' not in DB.zrange('t|de', 0, -1)
    assert b'd|xxxx' not in DB.zrange('t|lil', 0, -1)
    assert b'd|xxxx' not in DB.zrange('t|un', 0, -1)
    assert DB.exists('g|u09dgm7')
    assert b'd|xxxx' not in DB.smembers('g|u09dgm7')
    assert b'd|xxxx2' in DB.zrange('t|ru', 0, -1)
    assert b'd|xxxx2' in DB.zrange('t|de', 0, -1)
    assert b'd|xxxx2' in DB.zrange('t|lil', 0, -1)
    assert b'd|xxxx2' in DB.zrange('t|un', 0, -1)
    assert b'd|xxxx2' in DB.smembers('g|u09dgm7')
    assert b'd|xxxx2' in DB.smembers('g|u0g08g7')
    assert DB.exists('f|type|street')
    assert b'd|xxxx2' in DB.smembers('f|type|street')
    assert DB.exists('f|type|housenumber')
    assert b'd|xxxx2' in DB.smembers('f|type|housenumber')
    assert len(DB.keys()) == 12


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
    assert index[b'h|1b'] == b'1 bis|48.325451|2.25651'


def test_index_should_join_housenumbers_payload_fields(config):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['key', 'one']
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
                'lon': '2.25651',
                'key': 'myvalue',
                'thisone': 'no',
                'one': 'two',
            }
        }
    }
    index_document(doc)
    index = DB.hgetall('d|xxxx')
    assert index[b'h|1b'] == b'1 bis|48.325451|2.25651|myvalue|two'


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
    assert DB.zscore('t|ver', 'd|xxxx') == 4
    assert DB.zscore('t|sel', 'd|xxxx') == 4 / 5


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
    assert not DB.exists('t|ver')
    assert not DB.exists('t|sel')
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
    assert DB.exists('t|lil')
    assert DB.exists('t|ru')
    assert not DB.exists('t|ind')


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
    assert DB.zscore('t|lil', 'd|xxxx') == 5
    assert DB.zscore('t|ser', 'd|xxxx') == 1


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
    assert DB.zscore('t|lil', 'd|xxxx') == 5
    assert DB.zscore('t|ser', 'd|xxxx') == 1


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
