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
    assert resp.json['status'] == "HEALTHY"
