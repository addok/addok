from addok.core import Result, search


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


def test_synonyms_should_be_replaced(street, config):
    config.SYNONYMS = {'bd': 'boulevard'}
    config.MIN_SCORE = 0
    street.update(name='boulevard des Fleurs')
    assert search('bd')


def test_should_return_results_if_only_common_terms(factory, config):
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2
    config.BUCKET_MAX = 3
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


def test_should_brute_force_if_common_terms_above_limit(factory, config):
    config.COMMON_THRESHOLD = 2
    config.BUCKET_MAX = 3
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


def test_should_use_filter_if_only_common_terms(factory, config):
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2
    config.BUCKET_MAX = 3
    street1 = factory(name="rue de la monnaie", city="Vitry")
    street2 = factory(name="rue de la monnaie", city="Paris")
    street3 = factory(name="rue de la monnaie", city="Condom")
    city = factory(name="La monnaie", type="city")
    results = search('la monnaie', type="city")
    ids = [r.id for r in results]
    assert city['id'] in ids
    assert street1['id'] not in ids
    assert street2['id'] not in ids
    assert street3['id'] not in ids


def test_not_found_term_is_autocompleted(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue de la monnaie", city="Vitry")
    assert search('rue de la mon')


def test_found_term_is_autocompleted_if_missing_results(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    assert len(search('rue mont', autocomplete=True)) == 2


def test_found_term_is_not_autocompleted_if_enough_results(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    montagne = factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    factory(name="rue du mont", city="Paris")
    factory(name="rue du mont", city="Lille")
    results = search('rue mont', limit=2, autocomplete=True)
    ids = [r.id for r in results]
    assert len(ids) == 2
    assert montagne['id'] not in ids


def test_should_autocomplete_if_only_commons_but_geohash(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue des tilleuls")
    factory(name="rue des chênes")
    factory(name="rue des hètres")
    factory(name="rue des aulnes")
    factory(name="rue descartes", lon=2.2, lat=48.1)
    results = search('rue des', autocomplete=True, lon=2.2, lat=48.1)
    assert results[0].name == 'rue descartes'


def test_should_autocomplete_if_only_housenumbers_but_geohash(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    config.MIN_SCORE = 0.05
    factory(name="rue des tilleuls", lon=2.256, lat=48.3254)
    factory(name="rue des chênes", lon=2.256, lat=48.3254)
    factory(name="rue des hètres", lon=2.256, lat=48.3254)
    factory(name="rue des aulnes", lon=2.256, lat=48.3254)
    factory(name="rue descartes", lon=2.256, lat=48.3254,
            housenumbers={'11': {'lat': '48.3254', 'lon': '2.256'}})
    results = search('11', autocomplete=True, lon=2.256, lat=48.3254)
    assert results[0].name == 'rue descartes'


def test_closer_result_should_be_first_for_same_score(factory):
    expected = factory(name='rue de paris', city='Cergy', lat=48.1, lon=2.2)
    factory(name='rue de paris', city='Perpète', lat=-48.1, lon=-2.2)
    factory(name='rue de paris', city='Loin', lat=8.1, lon=42.2)
    results = search('rue de la monnaie', lat=48.1, lon=2.2)
    assert len(results) == 3
    assert results[0].id == expected['id']


def test_nearby_should_be_included_even_in_overflow(factory, config):
    config.BUCKET_MAX = 3
    config.BUCKET_MIN = 2
    expected = factory(name='Le Bourg', lat=48.1, lon=2.2, importance=0.09)
    factory(name='Le Bourg', lat=-48.1, lon=-2.2, importance=0.1)
    factory(name='Le Bourg', lat=8.1, lon=42.2, importance=0.1)
    factory(name='Le Bourg', lat=10, lon=20, importance=0.1)
    results = search('bourg', lat=48.1, lon=2.2, limit=3, verbose=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected['id'] in ids


def test_autocomplete_should_give_priority_to_nearby(factory, config):
    config.BUCKET_MAX = 3
    config.BUCKET_MIN = 2
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


def test_filters_are_stripped(factory):
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    results = search("paris", type="street ")
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


def test_filter_indexes_multiple_values(factory):
    city = factory(name="Paris", type=["city", "municipality"])
    results = search("paris", type="city")
    ids = [r.id for r in results]
    assert city['id'] in ids
    results = search("paris", type="municipality")
    ids = [r.id for r in results]
    assert city['id'] in ids


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
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.32', 'lon': '2.25', 'key': 'abc'}})
    results = search("rue de paris")
    assert results[0].key == ''
    results = search("1 rue de paris")
    assert results[0].key == 'abc'


def test_id_is_overwritten_when_given_in_housenumber_payload(config, factory):
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.325', 'lon': '2.256', 'id': 'abc'}})
    results = search("rue de paris")
    assert results[0].id == '123'
    results = search("1 rue de paris")
    assert results[0].id == 'abc'


def test_postcode_is_overwritten_when_in_housenumber_payload(config, factory):
    factory(name="rue de Paris", type="street", id="123", postcode="12345",
            housenumbers={'1': {'lat': '48.325', 'lon': '2.256',
                                'postcode': '54321'}})
    results = search("rue de paris")
    assert results[0].postcode == '12345'
    results = search("1 rue de paris")
    assert results[0].postcode == '54321'


def test_from_id(factory):
    doc = factory(name="avenue de Paris", type="street", id="123")
    result = Result.from_id(doc['_id'])
    assert result.id == "123"


def test_should_compare_with_multiple_values(city, factory):
    city.update(name=["Vernou-la-Celle-sur-Seine", "Vernou"])
    factory(name="Vernou", type="city")
    results = search("vernou")
    assert len(results) == 2
    assert results[0].score == results[1].score


def test_allow_to_set_result_values(factory):
    factory(name="porte des lilas", type="street", id="456")
    results = search("porte des lilas")
    result = results[0]
    result.name = "blah"
    result.score = 22
    # Plugins may need that.
    assert result.name == "blah"
    assert result.score == 22


def test_should_keep_unchanged_name_as_default_label(factory):
    factory(name="Porte des Lilas")
    results = search("porte des lilas")
    str(results[0]) == "Porte des Lilas"


def test_does_not_fail_without_usable_tokens(street):
    assert not search('./.$*')


def test_word_order_priority(factory):
    factory(name='avenue de paris', city='saint-mandé', importance=0.0185)
    factory(name='avenue de saint-mandé', city='paris', importance=0.0463)
    results = search('avenue de paris saint-mandé')
    assert results[0].name == 'avenue de paris'
    results = search('avenue de paris saint-mandé france')
    assert results[0].name == 'avenue de paris'
    results = search('avenue de saint-mandé paris')
    assert results[0].name == 'avenue de saint-mandé'


def test_bucket_respects_limit(config, factory):
    # issue #422
    config.BUCKET_MAX = 100
    limit = config.BUCKET_MAX * 2
    fields = {'name': "allée des acacias", 'type': "street",
              'housenumbers': {'1': {'lat': '48.325', 'lon': '2.256'}}}
    for city in range(0, limit):
        factory(id=str(city), postcode=str(10000+city), **fields)
    results = search('allée des acacias', limit=limit, autocomplete=True)
    assert len(results) == limit
