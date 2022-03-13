from addok.helpers import scripts


def test_manual_scan(factory):
    factory(name="rue de la monnaie", city="Vitry")
    factory(name="La monnaye", city="Saint-Loup-Cammas")
    street1 = factory(name="rue de la monnaie", city="Paris", importance=1)
    street2 = factory(name="rue de la monnaie", city="Condom", importance=0.9)
    results = scripts.manual_scan(keys=["w|monnaie", "w|rue", "w|de"], args=[2])
    assert results == [
        "d|{}".format(street1["_id"]).encode(),
        "d|{}".format(street2["_id"]).encode(),
    ]


def test_manual_scan_with_filter(factory):
    vitry = factory(name="Vitry", type="city")
    factory(name="La monnaye", city="Saint-Loup-Cammas")
    street1 = factory(name="rue de la monnaie", city="Paris", importance=1)
    street2 = factory(name="rue de la monnaie", city="Condom", importance=0.9)
    results = scripts.manual_scan(keys=["w|rue", "w|de", "f|type|street"], args=[2])
    assert results == [
        "d|{}".format(street1["_id"]).encode(),
        "d|{}".format(street2["_id"]).encode(),
    ]
    results = scripts.manual_scan(keys=["w|rue", "w|de", "f|type|whatever"], args=[2])
    assert results == []
    results = scripts.manual_scan(keys=["w|vitry", "f|type|city"], args=[2])
    assert results == ["d|{}".format(vitry["_id"]).encode()]


def test_zinter(factory):
    docs = (
        factory(name="rue de la monnaie", city="Vitry"),
        factory(name="La monnaye", city="Saint-Loup-Cammas"),
        factory(name="rue de la monnaie", city="Paris", importance=1),
        factory(name="rue de la monnaie", city="Condom", importance=0.9),
    )
    results = scripts.zinter(keys=["w|monnaie", "w|rue", "w|de"], args=["tmp", 2])
    assert results == [
        "d|{}".format(docs[2]["_id"]).encode(),
        "d|{}".format(docs[3]["_id"]).encode(),
    ]
    results = scripts.zinter(keys=["w|monnaie", "w|rue", "w|de"], args=["tmp", 3])
    assert results == [
        "d|{}".format(docs[2]["_id"]).encode(),
        "d|{}".format(docs[3]["_id"]).encode(),
        "d|{}".format(docs[0]["_id"]).encode(),
    ]


def test_order_by_frequency(factory):
    factory(name="rue de la monnaie", city="Vitry")
    factory(name="rue des lilas", city="Vitry")
    factory(name="rue des figues", city="Vitry")
    factory(name="rue des lilas", city="Pantin")
    assert scripts.order_by_frequency(
        keys=["w|monnaie", "w|lilas", "w|vitry", "w|rue"]
    ) == [b"w|rue", b"w|vitry", b"w|lilas", b"w|monnaie"]


def test_order_by_max_score(factory):
    factory(name="rue de la monnaie", city="Vitry")
    factory(name="rue des lilas", city="Vitry")
    factory(name="rue des figues", city="Vitry")
    factory(name="rue des lilas", city="Pantin")
    factory(name="Vitry", importance=0.5)
    keys = ["w|monnaie", "w|lilas", "w|vitry", "w|rue"]
    assert scripts.order_by_max_score(keys=keys)[0] == b"w|vitry"
