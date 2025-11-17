from addok.http import View


def test_search_without_query_should_return_400(client):
    resp = client.get("/search")
    assert resp.status_code == 400


def test_search_should_return_geojson(client, factory):
    factory(name="rue des avions")
    resp = client.get("/search/", query_string={"q": "avions"})
    assert resp.headers["Content-Type"] == "application/json; charset=utf-8"
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 1
    feature = resp.json["features"][0]
    assert feature["properties"]["name"] == "rue des avions"
    assert feature["properties"]["id"]
    assert feature["properties"]["type"]
    assert feature["properties"]["score"]
    assert "attribution" in resp.json
    assert "licence" in resp.json


def test_search_should_have_cors_headers(client, factory):
    factory(name="rue des avions")
    resp = client.get("/search/", query_string={"q": "avions"})
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert resp.headers["Access-Control-Allow-Headers"] == "X-Requested-With"


def test_search_without_trailing_slash_should_not_be_redirected(client):
    resp = client.get("/search", query_string={"q": "avions"})
    assert resp.status_code == 200


def test_search_can_be_filtered(client, factory):
    factory(name="rue de Paris", type="street")
    factory(name="Paris", type="city")
    resp = client.get("/search/", query_string={"q": "paris", "type": "city"})
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 1
    feature = resp.json["features"][0]
    assert feature["properties"]["name"] == "Paris"
    assert feature["properties"]["type"] == "city"


def test_search_filters_can_be_combined(client, factory):
    factory(name="rue de Paris", type="street", postcode="77000")
    factory(name="avenue de Paris", type="street", postcode="22000")
    factory(name="Paris", type="city")
    resp = client.get(
        "/search/", query_string={"q": "paris", "type": "street", "postcode": "77000"}
    )
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 1
    feature = resp.json["features"][0]
    assert feature["properties"]["name"] == "rue de Paris"
    assert feature["properties"]["type"] == "street"


def test_search_supports_multi_value_filter_via_http(client, factory):
    factory(name="rue de Paris", type="street")
    factory(name="Paris", type="city")
    # With default separator ' ' (space), pass "street city" as value
    resp = client.get(
        "/search/", query_string={"q": "paris", "type": "street city"}
    )
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 2
    types = {feature["properties"]["type"] for feature in resp.json["features"]}
    assert types == {"street", "city"}


def test_centered_search_should_return_center(client, factory):
    factory(name="rue de Paris", type="street")
    resp = client.get("/search/", query_string={"q": "paris", "lat": "44", "lon": "4"})
    assert resp.json["center"] == [4, 44]


def test_reverse_should_return_geojson(client, factory):
    factory(name="rue des avions", lat=44, lon=4)
    resp = client.get("/reverse/", query_string={"lat": "44", "lon": "4"})
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 1
    feature = resp.json["features"][0]
    assert feature["properties"]["name"] == "rue des avions"
    assert feature["properties"]["id"]
    assert feature["properties"]["type"]
    assert feature["properties"]["score"]
    assert "attribution" in resp.json
    assert "licence" in resp.json


def test_reverse_should_also_accept_lng(client, factory):
    factory(name="rue des avions", lat=44, lon=4)
    resp = client.get("/reverse/", query_string={"lat": "44", "lng": "4"})
    assert len(resp.json["features"]) == 1


def test_reverse_without_trailing_slash_should_not_be_redirected(client):
    resp = client.get("/reverse", query_string={"lat": "44", "lon": "4"})
    assert resp.status_code == 200


def test_reverse_can_be_filtered(client, factory):
    factory(lat=48.234545, lon=5.235445, type="street")
    factory(lat=48.234546, lon=5.235446, type="city")
    resp = client.get(
        "/reverse/",
        query_string={"lat": "48.234545", "lon": "5.235446", "type": "city"},
    )
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 1
    feature = resp.json["features"][0]
    assert feature["properties"]["type"] == "city"


def test_reverse_supports_multi_value_filter(client, factory):
    """Test that reverse geocoding supports multi-value filters with OR logic"""
    street = factory(name="rue des avions", lat=48.2345, lon=5.2354, type="street")
    city = factory(name="Ville", lat=48.2345, lon=5.2354, type="city")
    locality = factory(name="Lieu-dit", lat=48.2345, lon=5.2354, type="locality")
    # With default separator ' ' (space), pass "street city" as value
    resp = client.get(
        "/reverse/",
        query_string={"lat": "48.2345", "lon": "5.2354", "type": "street city", "limit": "10"},
    )
    assert resp.json["type"] == "FeatureCollection"
    assert len(resp.json["features"]) == 2
    types = {feature["properties"]["type"] for feature in resp.json["features"]}
    assert types == {"street", "city"}


def test_reverse_multi_filter_combination(client, factory):
    """Test that reverse geocoding combines multiple filters with AND logic"""
    factory(name="rue A", lat=48.2345, lon=5.2354, type="street", postcode="75001")
    factory(name="rue B", lat=48.2345, lon=5.2354, type="street", postcode="75002")
    factory(name="Ville C", lat=48.2345, lon=5.2354, type="city", postcode="75001")
    resp = client.get(
        "/reverse/",
        query_string={
            "lat": "48.2345",
            "lon": "5.2354",
            "type": "street city",
            "postcode": "75001",
            "limit": "10",
        },
    )
    assert resp.json["type"] == "FeatureCollection"
    # Should only match: rue A (street+75001) and Ville C (city+75001)
    # Should NOT match: rue B (street but wrong postcode)
    assert len(resp.json["features"]) == 2
    names = {feature["properties"]["name"] for feature in resp.json["features"]}
    assert names == {"rue A", "Ville C"}


def test_reverse_multi_params_without_separator(config, client, factory):
    """Test that reverse with multiple parameters works even when separator=None"""
    config.FILTERS_MULTI_VALUE_SEPARATOR = None
    
    street = factory(name="rue Test", lat=48.2345, lon=5.2354, type="street")
    city = factory(name="City Test", lat=48.2345, lon=5.2354, type="city")
    locality = factory(name="Locality Test", lat=48.2345, lon=5.2354, type="locality")
    
    # Multiple parameters should still work with OR logic
    resp = client.get("/reverse/?lat=48.2345&lon=5.2354&type=street&type=city&limit=10")
    assert len(resp.json["features"]) == 2
    types = {feature["properties"]["type"] for feature in resp.json["features"]}
    assert types == {"street", "city"}


def test_reverse_should_have_cors_headers(client, factory):
    factory(name="rue des avions", lat=44, lon=4)
    resp = client.get("/reverse/", query_string={"lat": "44", "lng": "4"})
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert resp.headers["Access-Control-Allow-Headers"] == "X-Requested-With"


def test_reverse_without_lat_or_lng_should_return_400(client, factory):
    resp = client.get("/reverse/", query_string={"lat": "44"})
    assert resp.status_code == 400
    resp = client.get("/reverse/", query_string={"lng": "4"})
    assert resp.status_code == 400


def test_view_should_expose_config(config):
    config.NEW_PROPERTY = "ok"
    assert View.config.NEW_PROPERTY == "ok"


def test_geojson_should_return_housenumber_payload(client, factory, config):
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        housenumbers={"1": {"lat": "48.32", "lon": "2.25", "key": "abc"}},
    )
    resp = client.get("/search/", query_string={"q": "rue de paris"})
    assert "key" not in resp.json["features"][0]["properties"]
    resp = client.get("/search/", query_string={"q": "1 rue de paris"})
    assert resp.json["features"][0]["properties"]["key"] == "abc"


def test_geojson_should_keep_housenumber_parent_name(client, factory):
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        housenumbers={"1": {"lat": "48.32", "lon": "2.25"}},
    )
    factory(
        name="Le Vieux-Chêne",
        type="locality",
        id="124",
        housenumbers={"2": {"lat": "48.22", "lon": "2.22"}},
    )
    resp = client.get("/search/", query_string={"q": "1 rue de paris"})
    assert resp.json["features"][0]["properties"]["name"] == "1 rue de Paris"
    assert resp.json["features"][0]["properties"]["street"] == "rue de Paris"
    resp = client.get("/search/", query_string={"q": "2 Le Vieux-Chêne"})
    props = resp.json["features"][0]["properties"]
    assert props["name"] == "2 Le Vieux-Chêne"
    assert props["locality"] == "Le Vieux-Chêne"


def test_search_should_not_split_querystring_on_commas(client, factory):
    factory(name="rue des avions", housenumbers={"18": {"lat": "48.22", "lon": "2.22"}})
    # Pass query string as a string to avoid additional encoding by the test client.
    resp = client.get("/search/", query_string="q=18, rue des avions")
    props = resp.json["features"][0]["properties"]
    assert props["label"] == "18 rue des avions"
    assert resp.json["query"] == "18, rue des avions"


def test_query_string_length_should_be_checked(client, config):
    config.QUERY_MAX_LENGTH = 10
    resp = client.get("/search/", query_string={"q": "this is too long"})
    assert resp.status_code == 413
    assert resp.json["title"] == "Query too long, 16 chars, limit is 10"


def test_geojson_should_have_document_type_as_key(client, factory):
    factory(
        name="rue de Paris",
        type="street",
        id="123",
        housenumbers={"1": {"lat": "48.32", "lon": "2.25"}},
    )
    factory(name="rue de foobar", type="foo", id="123", foo="bar")
    resp = client.get("/search/", query_string={"q": "1 rue de paris"})
    properties = resp.json["features"][0]["properties"]
    assert properties["name"] == "1 rue de Paris"
    assert properties["street"] == "rue de Paris"
    resp = client.get("/search/", query_string={"q": "rue de paris"})
    properties = resp.json["features"][0]["properties"]
    assert properties["name"] == "rue de Paris"
    assert properties["street"] == "rue de Paris"
    resp = client.get("/search/", query_string={"q": "rue de foobar"})
    properties = resp.json["features"][0]["properties"]
    assert properties["name"] == "rue de foobar"
    assert properties["foo"] == "bar"  # Not overridden.


def test_search_should_catch_invalid_lat(client):
    resp = client.get("/search?q=blah&lat=invalid&lon=3.21")
    assert resp.status_code == 400
    assert resp.json == {
        "description": 'The "lat" parameter is invalid. invalid value',
        "title": "Invalid parameter",
    }


def test_search_should_catch_invalid_lon(client):
    resp = client.get("/search?q=blah&longitude=invalid&lat=3.21")
    assert resp.status_code == 400
    assert resp.json == {
        "description": 'The "longitude" parameter is invalid. invalid value',
        "title": "Invalid parameter",
    }


def test_search_should_catch_out_of_range_lon(client):
    resp = client.get("/search?q=blah&longitude=200&lat=3.21")
    assert resp.status_code == 400
    assert resp.json == {
        "description": 'The "lon" parameter is invalid. out of range',
        "title": "Invalid parameter",
    }

def test_health_should_return_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json
    assert resp.json["status"] == "HEALTHY"


def test_multi_value_filters_can_be_disabled(config, client, factory):
    """Test that multi-value filters can be completely disabled.

    When FILTERS_MULTI_VALUE_SEPARATOR=None, filter values are never split,
    but multiple query parameters should still work for multi-value OR logic.
    """
    config.FILTERS_MULTI_VALUE_SEPARATOR = None

    factory(name="Test Item", type="foo bar")  # Literal value with space
    factory(name="Rue Test", type="street")
    factory(name="City Test", type="city")

    # type=foo+bar → decoded as "foo bar" → not split because separator disabled
    resp = client.get("/search/?q=test&type=foo+bar")
    assert len(resp.json["features"]) == 1
    assert resp.json["features"][0]["properties"]["type"] == "foo bar"
    
    # Multi-parameters should still work even with separator=None
    resp = client.get("/search/?q=test&type=street&type=city")
    assert len(resp.json["features"]) == 2
    types = {f["properties"]["type"] for f in resp.json["features"]}
    assert types == {"street", "city"}


def test_multi_value_filter_with_space_separator(config, client, factory):
    """Test multi-value filters using space as separator.

    When the separator is a space, URL-encoded spaces ('+' or '%20') are decoded
    and then used to split the value into multiple filter values.

    Note: This means filter values cannot themselves contain spaces.
    This is an edge case, not the recommended configuration.
    """
    config.FILTERS_MULTI_VALUE_SEPARATOR = " "

    factory(name="Place Test", type="foo")
    factory(name="Place Test 2", type="bar")

    # type=foo+bar → decoded as "foo bar" → split on " " → ["foo", "bar"] (OR logic)
    resp = client.get("/search/?q=place&type=foo+bar")

    assert len(resp.json["features"]) == 2
    types = {f["properties"]["type"] for f in resp.json["features"]}
    assert types == {"foo", "bar"}


def test_custom_separator_allows_values_with_spaces(config, client, factory):
    """Test using comma separator to support filter values containing spaces.

    This is the recommended approach when filter values can contain spaces.
    With comma separator:
    - Spaces in values are preserved (type=my+foo → "my foo")
    - Multiple values are split on comma (type=my+foo,bar → ["my foo", "bar"])
    """
    config.FILTERS_MULTI_VALUE_SEPARATOR = ','

    factory(name="Rue Street A", type="my foo")  # Value with space
    factory(name="City B", type="bar")

    # type=my+foo,bar → decoded as "my foo,bar" → split on "," → ["my foo", "bar"]
    resp = client.get("/search/?q=rue city&type=my+foo,bar")
    assert len(resp.json["features"]) == 2
    types = {f["properties"]["type"] for f in resp.json["features"]}
    assert types == {"my foo", "bar"}


def test_multi_querystring_parameters(config, client, factory):
    """Test using multiple query string parameters for multi-value filters.

    When FILTERS_MULTI_VALUE_SEPARATOR is set, you can pass the same
    filter parameter multiple times for OR logic, as an alternative
    to using separators within a single value.
    """
    config.FILTERS_MULTI_VALUE_SEPARATOR = " "

    factory(name="Rue Test", type="street")
    factory(name="City Test", type="city")

    # Using multiple parameters: type=street&type=city (OR logic)
    resp = client.get("/search/?q=test&type=street&type=city")
    assert len(resp.json["features"]) == 2
    types = {f["properties"]["type"] for f in resp.json["features"]}
    assert types == {"street", "city"}

def test_multi_mixed(config, client, factory):
    """Test combining multi-value filters via separator and multiple parameters.

    When FILTERS_MULTI_VALUE_SEPARATOR is set, you can combine:
    - Multiple query parameters: ?type=street&type=city boulevard
    - Each parameter value can also contain the separator
    """
    config.FILTERS_MULTI_VALUE_SEPARATOR = " "

    factory(name="Street Test", type="street")
    factory(name="City Test", type="city")
    factory(name="Boulevard Test", type="boulevard")
    factory(name="Avenue Test", type="avenue")

    # type=street&type=city+boulevard
    # → ["street", "city boulevard"] joined with " "
    # → "street city boulevard"
    # → split on " " → ["street", "city", "boulevard"]
    resp = client.get("/search/?q=test&type=street&type=city+boulevard")
    assert len(resp.json["features"]) == 3
    types = {f["properties"]["type"] for f in resp.json["features"]}
    assert types == {"street", "city", "boulevard"}
