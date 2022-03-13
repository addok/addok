from addok.core import reverse


def test_reverse_return_closer_point(factory):
    factory(lat=78.23, lon=-15.23)
    good = factory(lat=48.234545, lon=5.235445)
    assert reverse(lat=48.234545, lon=5.235445)[0].id == good["id"]


def test_reverse_return_housenumber(factory):
    factory(housenumbers={"24": {"lat": 48.234545, "lon": 5.235445, "key": "value"}})
    results = reverse(lat=48.234545, lon=5.235445)
    assert results[0].housenumber == "24"
    assert results[0].type == "housenumber"
    assert results[0].key == "value"
    assert not results[0].raw


def test_reverse_can_be_limited(factory):
    factory(lat=48.234545, lon=5.235445)
    factory(lat=48.234546, lon=5.235446)
    results = reverse(lat=48.234545, lon=5.235445)
    assert len(results) == 1
    results = reverse(lat=48.234545, lon=5.235445, limit=2)
    assert len(results) == 2


def test_reverse_can_be_filtered(factory):
    factory(lat=48.234545, lon=5.235445, type="street")
    factory(lat=48.234546, lon=5.235446, type="city")
    results = reverse(lat=48.234545, lon=5.235445, type="city")
    assert len(results) == 1
    assert results[0].type == "city"


def test_reverse_should_not_return_housenumber_if_filtered(factory):
    factory(
        lat=48.234544,
        lon=5.235444,
        housenumbers={"24": {"lat": 48.234545, "lon": 5.235445}},
    )
    results = reverse(lat=48.234545, lon=5.235445, type="street")
    assert results[0].type == "street"
    results = reverse(lat=48.234545, lon=5.235445)
    assert results[0].type == "housenumber"
    results = reverse(lat=48.234545, lon=5.235445, type="housenumber")
    assert results[0].type == "housenumber"


def test_reverse_should_enforce_housenumber_if_filtered(factory):
    factory(
        lat=48.234544,
        lon=5.235444,
        housenumbers={"24": {"lat": 48.234545, "lon": 5.235445}},
    )
    results = reverse(lat=48.234544, lon=5.235444, type="housenumber")
    assert results[0].type == "housenumber"
