from addok.core import reverse


def test_reverse_return_closer_point(factory):
    factory(lat=78.23, lon=-15.23)
    good = factory(lat=48.234545, lon=5.235445)
    assert reverse(lat=48.234545, lon=5.235445)[0].id == good['id']


def test_reverse_return_housenumber(factory):
    factory(housenumbers={'24': {'lat': 48.234545, 'lon': 5.235445}})
    results = reverse(lat=48.234545, lon=5.235445)
    assert results[0].housenumber == '24'


def test_reverse_can_be_limited(factory):
    factory(lat=48.234545, lon=5.235445)
    factory(lat=48.234546, lon=5.235446)
    results = reverse(lat=48.234545, lon=5.235445)
    assert len(results) == 1
    results = reverse(lat=48.234545, lon=5.235445, limit=2)
    assert len(results) == 2
