from addok.core import search


def test_should_match_name(street):
    assert not search('Conflans')
    street.update(name='Conflans')
    results = search('Conflans')
    assert results
    result = results[0]
    assert result.name == 'Conflans'
    assert result.id == street['id']


def test_should_match_name_case_insensitive(street):
    assert not search('conflans')
    street.update(name='Conflans')
    assert search('conflans')


def test_should_match_name_with_accent(street):
    assert not search('andrésy')
    street.update(name='Andrésy')
    assert search('andrésy')


def test_should_match_name_without_accent(street):
    assert not search('andresy')
    street.update(name='Andrésy')
    assert search('andresy')


def test_should_give_priority_to_best_match(street, city):
    street.update(name="rue d'Andrésy")
    city.update(name='Andrésy')
    results = search('andresy')
    assert results[0].id == city['id']


def test_should_give_priority_to_best_match2(street, factory):
    street.update(name="rue d'Andrésy", city="Conflans")
    factory(name="rue de Conflans", city="Andrésy")
    results = search("rue andresy")
    assert len(results) == 2
    assert results[0].id == street['id']


def test_should_give_priority_to_best_match3(street, factory):
    street.update(name="rue de Lille", city="Douai")
    other = factory(name="rue de Douai", city="Lille")
    results = search("rue de lille douai")
    assert len(results) == 2
    assert results[0].id == street['id']
    results = search("rue de douai lille")
    assert len(results) == 2
    assert results[0].id == other['id']


def test_should_be_fuzzy_of_1_by_default(city):
    city.update(name="Andrésy")
    assert search('antresy')
    assert not search('antresu')


def test_fuzzy_should_work_with_inversion(city):
    city.update(name="Andrésy")
    assert search('andreys')


def test_fuzzy_should_match_with_removal(city):
    city.update(name="Andrésy")
    assert search('andressy')


def test_should_give_priority_to_housenumber_if_match(housenumber):
    housenumber.update(name='rue des Berges')
    results = search('rue des berges')
    assert not results[0].housenumber
    results = search('11 rue des berges')
    assert results[0].housenumber == '11'


def test_should_not_return_housenumber_if_number_is_also_in_name(housenumber):
    housenumber.update(name='rue du 11 Novembre')
    results = search('rue du 11 novembre')
    assert not results[0].housenumber
    results = search('11 rue du 11 novembre')
    assert results[0].housenumber == '11'


def test_should_do_autocomplete_on_last_term(street):
    street.update(name='rue de Wambrechies', city="Bondues")
    assert search('avenue wambre')
    assert not search('wambre avenue')


def test_synonyms_should_be_replaced(street, monkeypatch):
    monkeypatch.setattr('addok.textutils.default.SYNONYMS',
                        {'bd': 'boulevard'})
    street.update(name='boulevard des Fleurs')
    assert search('bd')


def test_should_return_results_if_only_common_terms(factory, monkeypatch):
    monkeypatch.setattr('addok.config.COMMON_THRESHOLD', 3)
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    street1 = factory(name="rue de la monnaie", city="Vitry")
    street2 = factory(name="rue de la monnaie", city="Paris")
    street3 = factory(name="rue de la monnaie", city="Condom")
    street4 = factory(name="La monnaye", city="Saint-Loup-Cammas")
    results = search('rue de la monnaie')
    ids = [r.id for r in results]
    assert street1['id'] in ids
    assert street2['id'] in ids
    assert street3['id'] in ids
    assert street4['id'] not in ids


def test_not_found_term_is_autocompleted(factory, monkeypatch):
    monkeypatch.setattr('addok.config.COMMON_THRESHOLD', 3)
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    factory(name="rue de la monnaie", city="Vitry")
    assert search('rue de la mon')


def test_found_term_is_autocompleted_if_missing_results(factory, monkeypatch):
    monkeypatch.setattr('addok.config.COMMON_THRESHOLD', 3)
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    assert len(search('rue mont')) == 2


def test_found_term_is_not_autocompleted_if_enough_results(factory,
                                                           monkeypatch):
    monkeypatch.setattr('addok.config.COMMON_THRESHOLD', 3)
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    montagne = factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    factory(name="rue du mont", city="Paris")
    factory(name="rue du mont", city="Lille")
    results = search('rue mont', limit=2)
    ids = [r.id for r in results]
    assert len(ids) == 2
    assert montagne['id'] not in ids


def test_closer_result_should_be_first_for_same_score(factory):
    expected = factory(name='rue de paris', city='Cergy', lat=48.1, lon=2.2)
    factory(name='rue de paris', city='Perpète', lat=-48.1, lon=-2.2)
    factory(name='rue de paris', city='Loin', lat=8.1, lon=42.2)
    results = search('rue de la monnaie', lat=48.1, lon=2.2)
    assert len(results) == 3
    assert results[0].id == expected['id']


def test_nearby_should_be_included_even_in_overflow(factory, monkeypatch):
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    monkeypatch.setattr('addok.core.Search.SMALL_BUCKET_LIMIT', 2)
    expected = factory(name='Le Bourg', lat=48.1, lon=2.2, importance=0.09)
    factory(name='Le Bourg', lat=-48.1, lon=-2.2, importance=0.1)
    factory(name='Le Bourg', lat=8.1, lon=42.2, importance=0.1)
    factory(name='Le Bourg', lat=10, lon=20, importance=0.1)
    results = search('bourg', lat=48.1, lon=2.2, limit=3, verbose=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected['id'] in ids


def test_autocomplete_should_give_priority_to_nearby(factory, monkeypatch):
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    monkeypatch.setattr('addok.core.Search.SMALL_BUCKET_LIMIT', 2)
    expected = factory(name='Le Bourg', lat=48.1, lon=2.2, importance=0.09)
    factory(name='Le Bourg', lat=-48.1, lon=-2.2, importance=0.1)
    factory(name='Le Bourg', lat=8.1, lon=42.2, importance=0.1)
    factory(name='Le Bourg', lat=10, lon=20, importance=0.1)
    results = search('bou', lat=48.1, lon=2.2, limit=3, verbose=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected['id'] in ids


def test_document_without_name_should_not_be_indexed(factory):
    doc = factory(skip_index=True, city="Montceau-les-Mines")
    del doc['name']
    doc.index()
    assert not search('Montceau-les-Mines')
