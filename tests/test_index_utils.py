from addok.core import DB
from addok.index_utils import (index_edge_ngrams, index_document,
                               deindex_document)


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
    index_document(DOC)
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
    assert DB.exists('g|u09dgm7h')
    assert b'd|xxxx' in DB.smembers('g|u09dgm7h')
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
    assert len(DB.keys()) == 17


def test_deindex_document():
    index_document(DOC)
    deindex_document(DOC['id'])
    assert not DB.exists('d|xxxx')
    assert not DB.exists('w|de')
    assert not DB.exists('w|lila')
    assert not DB.exists('w|un')  # Housenumber.
    assert not DB.exists('p|ru')
    assert not DB.exists('p|de')
    assert not DB.exists('p|lila')
    assert not DB.exists('p|un')
    assert not DB.exists('g|u09dgm7h')
    assert not DB.exists('n|lil')
    assert not DB.exists('n|and')
    assert not DB.exists('n|andr')
    assert not DB.exists('n|andre')
    assert not DB.exists('n|andrez')
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
    index_document(DOC)
    index_document(DOC2)
    deindex_document(DOC['id'])
    assert not DB.exists('d|xxxx')
    assert b'd|xxxx' not in DB.zrange('w|ru', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|de', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|lila', 0, -1)
    assert b'd|xxxx' not in DB.zrange('w|un', 0, -1)
    assert DB.exists('g|u09dgm7h')
    assert b'd|xxxx' not in DB.smembers('g|u09dgm7h')
    assert DB.exists('w|de')
    assert DB.exists('w|lila')
    assert DB.exists('w|un')  # Housenumber.
    assert DB.exists('p|ru')
    assert b'd|xxxx2' in DB.zrange('w|ru', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|de', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|lila', 0, -1)
    assert b'd|xxxx2' in DB.zrange('w|un', 0, -1)
    assert b'd|xxxx2' in DB.smembers('g|u09dgm7h')
    assert b'd|xxxx2' in DB.smembers('g|u0g08g7m')
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
    assert len(DB.keys()) == 15


def test_deindex_document_should_not_fail_if_id_do_not_exist():
    deindex_document('xxxxx')
