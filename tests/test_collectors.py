from addok.helpers.collectors import _extract_manytomany_relations
from addok.helpers.text import Token


def test_extract_manytomany_relations(factory, config):
    config.COMMON_THRESHOLD = 2
    factory(name="rue de Paris", housenumbers={'513': {'lat': 1, 'lon': 2}})
    factory(name="rue de la porte")
    factory(name="rue de dieppe", housenumbers={'506': {'lat': 1, 'lon': 2}})
    tokens = [Token(s) for s in '513 rue de paris porte 506'.split()]
    groups = _extract_manytomany_relations(tokens)
    assert groups == [
        set([Token('513'), Token('paris')])
    ]


def test_extract_manytomany_relations_2(factory, config):
    config.COMMON_THRESHOLD = 2
    factory(name="rue de falaise", city='dieppe', postcode='76370',
            housenumbers={'1': {'lat': 1, 'lon': 2}})
    factory(name="chemin du semaphore", city='dieppe', postcode='76370',
            housenumbers={'1': {'lat': 1, 'lon': 2}})
    factory(name="chemin de neuville")
    factory(name="chemin de la tour", housenumbers={'1': {'lat': 1, 'lon': 2}})
    tokens = [Token(s) for s in
              '1 chemin de la falaise le semaphore neuville les 76370 '
              'dieppe'.split()]
    groups = _extract_manytomany_relations(tokens)
    assert len(groups) == 2
    assert {Token('dieppe'), Token('falaise'), Token('76370')} in groups
    assert {Token('dieppe'), Token('76370'), Token('semaphore')} in groups


def test_extract_manytomany_relations_3(factory, config):
    config.COMMON_THRESHOLD = 2
    latlon = {'lat': 1, 'lon': 2}
    factory(name="Rue Maréchal de Lattre de Tassigny",
            city='Mont-Saint-Aignan', postcode='76130',
            housenumbers={'45': latlon, '3': latlon})
    factory(name="rue du port", city='Saint-Denis', postcode='76370',
            housenumbers={'45': latlon, '3': latlon})
    factory(name="rue à l'eau", city='Saint-Pierre-de-Rouergue')
    factory(name="rue de Saint-Jean", housenumbers={'45': latlon, '3': latlon})
    tokens = [Token(s) for s in
              '45 rue de lattre de tassign pleiade a 3 porte 76130 mont '
              'saint aignan'.split()]
    groups = _extract_manytomany_relations(tokens)
    assert groups == [
        {Token('lattre'), Token('aignan'), Token('76130'), Token('mont')},
    ]
