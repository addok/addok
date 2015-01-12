from addok.core import DB
from addok.index_utils import index_edge_ngrams, index_document


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


def test_index_document():
    doc = {
        'id': 'xxxx',
        'type': 'street',
        'name': 'rue des Lilas',
        'lat': '48.32545',
        'lon': '2.2565',
        'housenumbers': {
            '1': {
                'lat': '48.325451',
                'lon': '2.25651'
            }
        }
    }
    index_document(doc)
    assert DB.exists('d|xxxx')
    assert DB.type('d|xxxx') == b'hash'
    assert DB.exists('w|ru')
    assert b'd|xxxx' in DB.zrange('w|ru', 0, -1)
    assert DB.exists('w|de')
    assert DB.exists('w|lila')
    assert DB.exists('w|un')  # Housenumber.
    assert DB.exists('p|ru')
    assert DB.exists('p|de')
    assert DB.exists('p|lila')
    assert DB.exists('g|u09dgm7h')
    assert b'xxxx|' in DB.smembers('g|u09dgm7h')
    assert b'xxxx|1' in DB.smembers('g|u09dgm7h')
    assert DB.exists('n|lil')
    assert b'lila' in DB.smembers('n|lil')
    assert len(DB.keys()) == 10
