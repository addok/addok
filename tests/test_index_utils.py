from addok.core import DB
from addok.index_utils import index_edge_ngrams


def count_keys():
    """Helper method to return the number of keys in the test database."""
    try:
        return DB.info()['db15']['keys']
    except KeyError:
        return 0


def test_index_edge_ngrams():
    before = count_keys()
    index_edge_ngrams('street')
    after = count_keys()
    assert after - before == 3
    assert DB.smembers('n|str') == set([b'street'])
    assert DB.smembers('n|stre') == set([b'street'])
    assert DB.smembers('n|stree') == set([b'street'])
