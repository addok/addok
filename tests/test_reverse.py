from addok.core import reverse
from addok.index_utils import index_document


def test_reverse_return_closer_point(factory):
    doc1 = factory(lat=78.23, lon=-15.23)
    doc2 = factory(lat=48.234545, lon=5.235445)
    index_document(doc1)
    index_document(doc2)
    assert reverse(lat=48.234545, lon=5.235445)[0].id == doc2['id']


def test_reverse_return_housenumber(factory):
    doc = factory(housenumbers={'24': {'lat': 48.234545, 'lon': 5.235445}})
    index_document(doc)
    results = reverse(lat=48.234545, lon=5.235445)
    assert results[0].housenumber == '24'


def test_reverse_can_be_limited(factory):
    doc1 = factory(lat=48.234545, lon=5.235445)
    doc2 = factory(lat=48.234546, lon=5.235446)
    index_document(doc1)
    index_document(doc2)
    results = reverse(lat=48.234545, lon=5.235445)
    assert len(results) == 1
    results = reverse(lat=48.234545, lon=5.235445, limit=2)
    assert len(results) == 2
