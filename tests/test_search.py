from addok.core import Result, search
from addok.helpers import collectors


def test_should_match_name(street):
    assert not search("Conflans")
    street.update(name="Conflans")
    results = search("Conflans")
    assert results
    result = results[0]
    assert result.name == "Conflans"
    assert result.id == street["id"]


def test_should_match_name_case_insensitive(street):
    assert not search("conflans")
    street.update(name="Conflans")
    assert search("conflans")


def test_should_match_name_with_accent(street):
    assert not search("andrésy")
    street.update(name="Andrésy")
    assert search("andrésy")


def test_should_match_name_without_accent(street):
    assert not search("andresy")
    street.update(name="Andrésy")
    assert search("andresy")


def test_should_give_priority_to_best_match(street, city):
    street.update(name="rue d'Andrésy")
    city.update(name="Andrésy")
    results = search("andresy")
    assert results[0].id == city["id"]


def test_should_give_priority_to_best_match2(street, factory):
    street.update(name="rue d'Andrésy", city="Conflans")
    factory(name="rue de Conflans", city="Andrésy")
    results = search("rue andresy")
    assert len(results) == 2
    assert results[0].id == street["id"]


def test_should_give_priority_to_best_match3(street, factory):
    street.update(name="rue de Lille", city="Douai")
    other = factory(name="rue de Douai", city="Lille")
    results = search("rue de lille douai")
    assert len(results) == 2
    assert results[0].id == street["id"]
    results = search("rue de douai lille")
    assert len(results) == 2
    assert results[0].id == other["id"]


def test_should_be_fuzzy_of_1_by_default(city, config):
    config.FUZZY_KEY_MAP = None
    city.update(name="Andrésy")
    assert search("antresy")
    assert not search("antresu")


def test_fuzzy_should_work_with_inversion(city):
    city.update(name="Andrésy")
    assert search("andreys")


def test_fuzzy_should_match_with_removal(city):
    city.update(name="Andrésy")
    assert search("andressy")


def test_should_give_priority_to_housenumber_if_match(housenumber):
    housenumber.update(name="rue des Berges")
    results = search("rue des berges")
    assert not results[0].housenumber
    results = search("11 rue des berges")
    assert results[0].housenumber == "11"
    assert results[0].type == "housenumber"


def test_return_housenumber_if_number_included_in_bigger_one(factory):
    factory(name="rue 1814", housenumbers={"8": {"lat": "48.3254", "lon": "2.256"}})
    results = search("rue 1814")
    assert not results[0].housenumber
    results = search("8 rue 1814")
    assert results[0].housenumber == "8"


def test_should_do_autocomplete_on_last_term(street):
    street.update(name="rue de Wambrechies", city="Bondues")
    assert search("avenue wambre", autocomplete=True)
    assert not search("wambre avenue", autocomplete=True)


def test_synonyms_should_be_replaced(street, config):
    config.SYNONYMS = {"bd": "boulevard"}
    config.MIN_SCORE = 0
    street.update(name="boulevard des Fleurs")
    assert search("bd")


def test_should_return_results_if_only_common_terms(factory, config):
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2
    config.BUCKET_MAX = 3
    street1 = factory(name="rue de la monnaie", city="Vitry")
    street2 = factory(name="rue de la monnaie", city="Paris")
    street3 = factory(name="rue de la monnaie", city="Condom")
    street4 = factory(name="La monnaye", city="Saint-Loup-Cammas")
    results = search("rue de la monnaie")
    ids = [r.id for r in results]
    assert street1["id"] in ids
    assert street2["id"] in ids
    assert street3["id"] in ids
    assert street4["id"] not in ids


def test_should_brute_force_if_common_terms_above_limit(factory, config):
    config.COMMON_THRESHOLD = 2
    config.BUCKET_MAX = 3
    street1 = factory(name="rue de la monnaie", city="Vitry")
    street2 = factory(name="rue de la monnaie", city="Paris")
    street3 = factory(name="rue de la monnaie", city="Condom")
    street4 = factory(name="La monnaye", city="Saint-Loup-Cammas")
    results = search("rue de la monnaie")
    ids = [r.id for r in results]
    assert street1["id"] in ids
    assert street2["id"] in ids
    assert street3["id"] in ids
    assert street4["id"] not in ids


def test_should_use_filter_if_only_common_terms(factory, config):
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2
    config.BUCKET_MAX = 3
    street1 = factory(name="rue de la monnaie", city="Vitry")
    street2 = factory(name="rue de la monnaie", city="Paris")
    street3 = factory(name="rue de la monnaie", city="Condom")
    city = factory(name="La monnaie", type="city")
    results = search("la monnaie", type="city")
    ids = [r.id for r in results]
    assert city["id"] in ids
    assert street1["id"] not in ids
    assert street2["id"] not in ids
    assert street3["id"] not in ids


def test_should_use_intersect_if_filter_smaller_than_token(factory, config, monkeypatch):
    """Test that Redis intersect is used when filter is more selective than token.

    Even if token frequency exceeds INTERSECT_LIMIT, if the filter size is smaller
    than the token frequency, we should use Redis intersection instead of manual scan.
    """
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2  # Very low to force manual scan normally
    config.BUCKET_MAX = 10

    # Track which strategy was used by mocking the manual_scan script
    manual_scan_called = []
    from addok.helpers import scripts
    original_manual_scan = scripts.manual_scan
    def mock_manual_scan(*args, **kwargs):
        manual_scan_called.append(True)
        return original_manual_scan(*args, **kwargs)
    monkeypatch.setattr(scripts, 'manual_scan', mock_manual_scan)

    # Create streets with common terms
    street1 = factory(name="rue de la monnaie", city="Vitry", type="street")
    street2 = factory(name="rue de la monnaie", city="Paris", type="street")
    street3 = factory(name="rue de la republique", city="Lyon", type="street")
    # Create cities (different type filter)
    city1 = factory(name="La monnaie", type="city")
    city2 = factory(name="La poste", type="city")

    # Search with a filter that has fewer items than the common token
    # "la" is very common (>2), but type=city filter has only 2 items
    results = search("la", type="city")
    ids = [r.id for r in results]

    # Should find cities, not streets (even though "la" is in both)
    assert city1["id"] in ids
    assert city2["id"] in ids
    assert street1["id"] not in ids
    assert street2["id"] not in ids

    # Verify that manual_scan was NOT called (intersect was used instead)
    assert not manual_scan_called, "manual_scan should not be called when filter is smaller than token"


def test_should_use_manual_scan_if_both_token_and_filter_large(factory, config, monkeypatch):
    """Test that manual scan is used when both token and filter are large.

    When both token frequency and filter size exceed INTERSECT_LIMIT,
    and the filter is NOT more selective than the token, manual scan should be used.
    """
    config.COMMON_THRESHOLD = 2
    config.INTERSECT_LIMIT = 2  # Very low threshold
    config.BUCKET_MAX = 10

    # Track if manual_scan was called
    manual_scan_called = []
    from addok.helpers import scripts
    original_manual_scan = scripts.manual_scan
    def mock_manual_scan(*args, **kwargs):
        manual_scan_called.append(True)
        return original_manual_scan(*args, **kwargs)
    monkeypatch.setattr(scripts, 'manual_scan', mock_manual_scan)

    # Create items to make token "la" common but with LESS frequency than filter
    # Token "la" will have 3 occurrences
    factory(name="La rue", city="City1", type="street")
    factory(name="La place", city="City2", type="locality")
    factory(name="La avenue", city="City3", type="way")
    # Create many streets (filter will be larger: 5 items)
    factory(name="Rue principale", city="City4", type="street")
    factory(name="Rue secondaire", city="City5", type="street")
    factory(name="Rue tertiaire", city="City6", type="street")
    factory(name="Rue autre", city="City7", type="street")

    # Now: token "la" has 3 occurrences (>2), filter "street" has 5 items (>2 and >3)
    # Both exceed INTERSECT_LIMIT but filter is LARGER than token
    # So manual scan should be used
    results = search("la", type="street")

    # Verify that manual_scan WAS called (filter larger than token)
    assert manual_scan_called, "manual_scan should be called when filter is larger than token"


def test_not_found_term_is_autocompleted(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue de la monnaie", city="Vitry")
    assert search("rue de la mon")


def test_found_term_is_autocompleted_if_missing_results(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    assert len(search("rue mont", autocomplete=True)) == 2


def test_found_term_is_not_autocompleted_if_enough_results(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    montagne = factory(name="rue de la montagne", city="Vitry")
    factory(name="rue du mont", city="Vitry")
    factory(name="rue du mont", city="Paris")
    factory(name="rue du mont", city="Lille")
    results = search("rue mont", limit=2, autocomplete=True)
    ids = [r.id for r in results]
    assert len(ids) == 2
    assert montagne["id"] not in ids


def test_should_autocomplete_if_only_commons_but_geohash(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    factory(name="rue des tilleuls")
    factory(name="rue des chênes")
    factory(name="rue des hètres")
    factory(name="rue des aulnes")
    factory(name="rue descartes", lon=2.2, lat=48.1)
    results = search("rue des", autocomplete=True, lon=2.2, lat=48.1)
    assert results[0].name == "rue descartes"


def test_should_autocomplete_if_only_housenumbers_but_geohash(factory, config):
    config.COMMON_THRESHOLD = 3
    config.BUCKET_MAX = 3
    config.MIN_SCORE = 0.05
    factory(name="rue des tilleuls", lon=2.256, lat=48.3254)
    factory(name="rue des chênes", lon=2.256, lat=48.3254)
    factory(name="rue des hètres", lon=2.256, lat=48.3254)
    factory(name="rue des aulnes", lon=2.256, lat=48.3254)
    factory(
        name="rue descartes",
        lon=2.256,
        lat=48.3254,
        housenumbers={"11": {"lat": "48.3254", "lon": "2.256"}},
    )
    results = search("11", autocomplete=True, lon=2.256, lat=48.3254)
    assert results[0].name == "rue descartes"


def test_closer_result_should_be_first_for_same_score(factory):
    expected = factory(name="rue de paris", city="Cergy", lat=48.1, lon=2.2)
    factory(name="rue de paris", city="Perpète", lat=-48.1, lon=-2.2)
    factory(name="rue de paris", city="Loin", lat=8.1, lon=42.2)
    results = search("rue de la monnaie", lat=48.1, lon=2.2)
    assert len(results) == 3
    assert results[0].id == expected["id"]


def test_nearby_should_be_included_even_in_overflow(factory, config):
    config.BUCKET_MAX = 3
    config.BUCKET_MIN = 2
    expected = factory(name="Le Bourg", lat=48.1, lon=2.2, importance=0.09)
    factory(name="Le Bourg", lat=-48.1, lon=-2.2, importance=0.1)
    factory(name="Le Bourg", lat=8.1, lon=42.2, importance=0.1)
    factory(name="Le Bourg", lat=10, lon=20, importance=0.1)
    results = search("bourg", lat=48.1, lon=2.2, limit=3, verbose=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected["id"] in ids


def test_autocomplete_should_give_priority_to_nearby(factory, config):
    config.BUCKET_MAX = 3
    config.BUCKET_MIN = 2
    expected = factory(name="Le Bourg", lat=48.1, lon=2.2, importance=0.09)
    factory(name="Le Bourg", lat=-48.1, lon=-2.2, importance=0.1)
    factory(name="Le Bourg", lat=8.1, lon=42.2, importance=0.1)
    factory(name="Le Bourg", lat=10, lon=20, importance=0.1)
    results = search("bou", lat=48.1, lon=2.2, limit=3, autocomplete=True)
    assert len(results) == 3
    ids = [r.id for r in results]
    assert expected["id"] in ids


def test_document_without_name_should_not_be_indexed(factory):
    doc = factory(skip_index=True, city="Montceau-les-Mines")
    del doc["name"]
    doc.index()
    assert not search("Montceau-les-Mines")


def test_score_is_not_greater_than_one(factory):
    factory(name="rue de paris", importance=1)
    results = search("rue de paris")
    assert len(results) == 1
    assert results[0].score == 1


def test_search_can_be_filtered(factory):
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    results = search("paris", type="street")
    ids = [r.id for r in results]
    assert street["id"] in ids
    assert city["id"] not in ids


def test_search_supports_multi_value_filter(factory):
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    locality = factory(name="Grenelle", type="locality") # Unwanted result
    results = search("paris", type=["street", "city"])
    ids = {r.id for r in results}
    assert street["id"] in ids
    assert city["id"] in ids
    assert locality["id"] not in ids


def test_search_multi_filter_combination_with_other_filters(factory):
    street_75000 = factory(name="rue de Paris", type="street", postcode="75000")
    street_77000 = factory(name="avenue de Paris", type="street", postcode="77000")
    city = factory(name="Paris", type="city", postcode="75000")
    results = search("paris", type=["street", "city"], postcode="75000")
    ids = {r.id for r in results}
    assert street_75000["id"] in ids
    assert city["id"] in ids
    assert street_77000["id"] not in ids


def test_multifilter_with_duplicate_values(factory):
    """Test that duplicate values in multi-filter are deduplicated"""
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    # Duplicate "street" should be deduplicated
    results = search("paris", type=["street", "street", "city"])
    ids = {r.id for r in results}
    assert street["id"] in ids
    assert city["id"] in ids


def test_multifilter_respects_max_values(factory):
    """Test that multi-filter is limited to MAX_FILTER_VALUES (default: 10)"""
    # Create various types
    street = factory(name="rue de Paris", type="street")
    city = factory(name="Paris", type="city")
    locality = factory(name="Paris Locality", type="locality")
    municipality = factory(name="Paris Municipality", type="municipality")

    # Try to use 12 values (default limit is 10), only first 10 should be used
    filter_value = [
        "street", "city", "locality", "municipality",
        "zone", "district", "sector", "area",
        "region", "country", "extra1", "extra2"
    ]
    results = search("paris", type=filter_value)
    # Should match at least the first few types created
    ids = {r.id for r in results}
    assert street["id"] in ids
    assert city["id"] in ids

def test_multifilter_case_sensitivity(factory):
    """Test that multi-filter values maintain case"""
    street = factory(name="rue de Paris", type="Street")
    city = factory(name="Paris", type="City")
    locality = factory(name="Paris Locality", type="locality")
    # Filter values should be case-sensitive - "street" won't match "Street"
    results = search("paris", type=["Street", "City"])
    ids = {r.id for r in results}
    assert street["id"] in ids
    assert city["id"] in ids
    # locality should not be in results since it doesn't match the filter
    assert locality["id"] not in ids


def test_housenumber_type_should_enforce_housenumber_match(factory):
    without_housenumber = factory(name="avenue de Paris", type="street")
    with_wrong_housenumber = factory(
        name="boulevard de Paris",
        type="street",
        housenumbers={"12": {"lat": "48.3254", "lon": "2.256"}},
    )
    with_housenumber = factory(
        name="rue de Paris",
        type="street",
        housenumbers={"11": {"lat": "48.3254", "lon": "2.256"}},
    )
    results = search("11 paris", type="housenumber")
    ids = [r.id for r in results]
    assert with_housenumber["id"] in ids
    assert without_housenumber["id"] not in ids
    assert with_wrong_housenumber["id"] not in ids


def test_filter_indexes_multiple_values(factory):
    city = factory(name="Paris", type=["city", "municipality"])
    results = search("paris", type="city")
    ids = [r.id for r in results]
    assert city["id"] in ids
    results = search("paris", type="municipality")
    ids = [r.id for r in results]
    assert city["id"] in ids


def test_housenumber_are_not_computed_if_another_type_is_asked(factory):
    factory(
        name="rue de Bamako",
        type="street",
        housenumbers={"11": {"lat": "48.3254", "lon": "2.256"}},
    )

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
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        housenumbers={"1": {"lat": "48.32", "lon": "2.25", "key": "abc"}},
    )
    results = search("rue de paris")
    assert results[0].key == ""
    results = search("1 rue de paris")
    assert results[0].key == "abc"


def test_id_is_overwritten_when_given_in_housenumber_payload(config, factory):
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        housenumbers={"1": {"lat": "48.325", "lon": "2.256", "id": "abc"}},
    )
    results = search("rue de paris")
    assert results[0].id == "123"
    results = search("1 rue de paris")
    assert results[0].id == "abc"


def test_postcode_is_overwritten_when_in_housenumber_payload(config, factory):
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        postcode="12345",
        housenumbers={"1": {"lat": "48.325", "lon": "2.256", "postcode": "54321"}},
    )
    results = search("rue de paris")
    assert results[0].postcode == "12345"
    results = search("1 rue de paris")
    assert results[0].postcode == "54321"


def test_from_id(factory):
    doc = factory(name="avenue de Paris", type="street", id="123")
    result = Result.from_id(doc["_id"])
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
    assert not search("./.$*")


def test_word_order_priority(factory):
    factory(name="avenue de paris", city="saint-mandé", importance=0.0185)
    factory(name="avenue de saint-mandé", city="paris", importance=0.0463)
    results = search("avenue de paris saint-mandé")
    assert results[0].name == "avenue de paris"

    # Does not work with compare_ngram.
    # Both document have same score:
    # Comparing "avenue de paris saint-mandé france"
    # - with "avenue de saint-mandé paris" => 0.7878787878787878
    # - with "avenue de paris saint-mandé" => 0.7878787878787878
    # results = search("avenue de paris saint-mandé france")
    # assert results[0].name == "avenue de paris"

    results = search("avenue de saint-mandé paris")
    assert results[0].name == "avenue de saint-mandé"


def test_bucket_respects_limit(config, factory):
    # issue #422
    config.BUCKET_MAX = 100
    limit = config.BUCKET_MAX * 2
    fields = {
        "name": "allée des acacias",
        "type": "street",
        "housenumbers": {"1": {"lat": "48.325", "lon": "2.256"}},
    }
    for city in range(0, limit):
        factory(id=str(city), postcode=str(10000 + city), **fields)
    results = search("allée des acacias", limit=limit, autocomplete=True)
    assert len(results) == limit
    results = search("allée des acacias", limit=limit, autocomplete=False)
    assert len(results) == limit


def test_geo_priority(config, factory):
    factory(
        name="Villa Eugène",
        city="Colombes",
        importance=0.0147,
        housenumbers={"13": {"lat": "48.915805", "lon": "2.260938"}},
    )
    factory(
        name="Villa Eugène",
        city="Fontenay",
        importance=0.0191,
        housenumbers={"13": {"lat": "48.879839", "lon": "2.393369"}},
    )
    results = search("13 vla eugène", lat=48.9158, lon=2.2609, autocomplete=True)
    assert results[0].city == "Colombes"
    results = search("13 vla eugène", lat=48.9158, lon=2.2609, autocomplete=False)
    assert results[0].city == "Colombes"


def test_geo_importance_weight(config, factory):
    initial_weight = config.GEO_DISTANCE_WEIGHT
    factory(name="rue descartes", lon=2.2, lat=48.1)
    results = search("rue descartes", lat=48.9158, lon=2.2609)
    initial_geo_score = results[0]._scores["geo_distance"]
    config.GEO_DISTANCE_WEIGHT = 2.0
    results = search("rue descartes", lat=48.9158, lon=2.2609)
    assert (
        results[0]._scores["geo_distance"][0]
        == initial_geo_score[0] * config.GEO_DISTANCE_WEIGHT / initial_weight
    )
    assert results[0]._scores["geo_distance"][1] == config.GEO_DISTANCE_WEIGHT


def test_importance_should_be_minored_if_geohash(factory, config):
    factory(name="rue descartes", lon=2.2, lat=48.1, importance=1)
    results = search("rue descartes")
    assert results[0]._scores["importance"][0] == 0.1
    results = search("rue descartes", lon=2.2, lat=48.1)
    assert results[0]._scores["importance"][0] == 0.010000000000000002


def test_extend_results_reducing_tokens_should_remove_two_tokens(factory, config):
    # Keep the basic bucket_with_meaningful to fill in the various helper
    # properties.
    config.RESULTS_COLLECTORS = [
        collectors.bucket_with_meaningful,
        collectors.extend_results_reducing_tokens,
    ]
    factory(name="quai jules verne", city="saint cyprien")
    factory(name="allee des cyprie", city="larmor plage")
    factory(name="rue jules verne", city="chatelaillon plage")
    factory(name="quai saint truc", city="la plage")
    # "plage" is the bad guy here: it has been seen with every other terms of
    # the search string, but it's not in the searched document.
    results = search("quai jules verne saint cyprie plage")
    assert results[0].name == "quai jules verne"
