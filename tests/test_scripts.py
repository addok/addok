from addok.helpers import scripts


def test_manual_scan(factory):
    factory(name="rue de la monnaie", city="Vitry")
    factory(name="La monnaye", city="Saint-Loup-Cammas")
    street1 = factory(name="rue de la monnaie", city="Paris", importance=1)
    street2 = factory(name="rue de la monnaie", city="Condom", importance=0.9)
    results = scripts.manual_scan(keys=['w|monnaie', 'w|rue', 'w|de'],
                                  args=[2])
    assert results == ['d|{}'.format(street1['id']).encode(),
                       'd|{}'.format(street2['id']).encode()]
