from addok.core import search, Result


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
    assert results[0].type == 'housenumber'


def test_should_not_return_housenumber_if_number_is_also_in_name(housenumber):
    housenumber.update(name='rue du 11 Novembre')
    results = search('rue du 11 novembre')
    assert not results[0].housenumber
    results = search('11 rue du 11 novembre')
    assert results[0].housenumber == '11'


def test_return_housenumber_if_number_included_in_bigger_one(factory):
    factory(name='rue 1814',
            housenumbers={'8': {'lat': '48.3254', 'lon': '2.256'}})
    results = search('rue 1814')
    assert not results[0].housenumber
    results = search('8 rue 1814')
    assert results[0].housenumber == '8'


def test_should_do_autocomplete_on_last_term(street):
    street.update(name='rue de Wambrechies', city="Bondues")
    assert search('avenue wambre', autocomplete=True)
    assert not search('wambre avenue', autocomplete=True)


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
    assert len(search('rue mont', autocomplete=True)) == 2


def test_found_term_is_not_autocompleted_if_enough_results(factory,
                                                           monkeypatch):
    monkeypatch.setattr('addok.config.COMMON_THRESHOLD', 3)
    monkeypatch.setattr('addok.config.BUCKET_LIMIT', 3)
    montagne = factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    factory(name="rue du mont", city="Paris")
    factory(name="rue du mont", city="Lille")
    results = search('rue mont', limit=2, autocomplete=True)
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
    results = search('bou', lat=48.1, lon=2.2, limit=3, autocomplete=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected['id'] in ids


def test_document_without_name_should_not_be_indexed(factory):
    doc = factory(skip_index=True, city="Montceau-les-Mines")
    del doc['name']
    doc.index()
    assert not search('Montceau-les-Mines')


def test_score_is_not_greater_than_one(factory):
    factory(name='rue de paris', importance=1)
    results = search('rue de paris')
    assert len(results) == 1
    assert results[0].score == 1


def test_search_can_be_filtered(factory):
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    results = search("paris", type="street")
    ids = [r.id for r in results]
    assert street['id'] in ids
    assert city['id'] not in ids


def test_housenumber_type_can_be_filtered(factory):
    street_without_housenumber = factory(name="avenue de Paris", type="street")
    street_with_housenumber = factory(name="rue de Paris", type="street",
                                      housenumbers={'11': {'lat': '48.3254',
                                                           'lon': '2.256'}})
    results = search("paris", type="housenumber")
    ids = [r.id for r in results]
    assert street_with_housenumber['id'] in ids
    assert street_without_housenumber['id'] not in ids


def test_housenumber_are_not_computed_if_another_type_is_asked(factory):
    factory(name="rue de Bamako", type="street",
            housenumbers={'11': {'lat': '48.3254', 'lon': '2.256'}})

    results = search("11 rue de bamako")
    assert len(results) == 1
    assert results[0].type == "housenumber"

    results = search("11 rue de bamako", type="housenumber")
    assert len(results) == 1
    assert results[0].type == "housenumber"

    results = search("11 rue de bamako", type="street")
    assert len(results) == 1
    assert results[0].type == "street"


def test_housenumbers_payload_fields_are_exported(config, factory):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['key']
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.32', 'lon': '2.25', 'key': 'abc'}})
    results = search("rue de paris")
    assert results[0].key == ''
    results = search("1 rue de paris")
    assert results[0].key == 'abc'


def test_id_is_overwritten_when_given_in_housenumber_payload(config, factory):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['id']
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.325', 'lon': '2.256', 'id': 'abc'}})
    results = search("rue de paris")
    assert results[0].id == '123'
    results = search("1 rue de paris")
    assert results[0].id == 'abc'


def test_postcode_is_overwritten_when_in_housenumber_payload(config, factory):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['postcode']
    factory(name="rue de Paris", type="street", id="123", postcode="12345",
            housenumbers={'1': {'lat': '48.325', 'lon': '2.256',
                                'postcode': '54321'}})
    results = search("rue de paris")
    assert results[0].postcode == '12345'
    results = search("1 rue de paris")
    assert results[0].postcode == '54321'


def test_unknown_key_in_housenumber_payload_does_not_fail(config, factory):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['xxxyyy']
    factory(name="rue de Paris", type="street", id="123", postcode="12345",
            housenumbers={'1': {'lat': '48.325', 'lon': '2.256'}})
    results = search("rue de paris")
    assert results[0].id == '123'
    results = search("1 rue de paris")
    assert results[0].id == '123'


def test_from_id(factory):
    factory(name="avenue de Paris", type="street", id="123")
    doc = Result.from_id("123")
    assert doc.id == "123"


def test_should_compare_with_multiple_values(city, factory):
    city.update(name=["Vernou-la-Celle-sur-Seine", "Vernou"])
    factory(name="Vernou", type="city")
    results = search("vernou")
    assert len(results) == 2
    assert results[0].score == results[1].score


def test_config_make_labels_is_used_if_defined(config, factory):

    def make_labels(result):
        if result.name == "porte des lilas":
            return ['areallybadlabel']
        return [result.name]

    config.MAKE_LABELS = make_labels
    factory(name="porte des lilas", type="street", id="456", importance=1)
    factory(name="porte des Lilas", type="street", id="123")
    results = search("porte des lilas")
    assert results[0].id == "123"
    assert results[0].score > 0.9
    assert results[1].score > 0.1


def test_allow_to_set_result_values(factory):
    factory(name="porte des lilas", type="street", id="456")
    results = search("porte des lilas")
    result = results[0]
    result.name = "blah"
    result.score = 22
    # Plugins may need that.
    assert result.name == "blah"
    assert result.score == 22
