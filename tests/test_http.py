import json
from urllib.parse import urlencode

import pytest

pytestmark = pytest.mark.asyncio


async def test_search_without_query_should_return_400(client):
    resp = await client.get('/search/')
    assert resp.status == 400


async def test_search_should_return_geojson(client, factory):
    factory(name='rue des avions')
    resp = await client.get('/search/?q=avions')
    assert resp.status == 200
    assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
    geojson = json.loads(resp.body)
    assert geojson['type'] == 'FeatureCollection'
    assert len(geojson['features']) == 1
    feature = geojson['features'][0]
    assert feature['properties']['name'] == 'rue des avions'
    assert feature['properties']['id']
    assert feature['properties']['type']
    assert feature['properties']['score']
    assert 'attribution' in geojson
    assert 'licence' in geojson


async def test_search_should_have_cors_headers(client, factory):
    factory(name='rue des avions')
    resp = await client.get('/search/?q=avions')
    assert resp.headers['Access-Control-Allow-Origin'] == '*'
    assert resp.headers['Access-Control-Allow-Headers'] == 'X-Requested-With'


async def test_search_without_trailing_slash_should_not_be_redirected(client):
    resp = await client.get('/search?q=avions')
    assert resp.status == 200


async def test_search_can_be_filtered(client, factory):
    factory(name='rue de Paris', type="street")
    factory(name='Paris', type="city")
    resp = await client.get('/search/?q=paris&type=city')
    geojson = json.loads(resp.body)
    assert geojson['type'] == 'FeatureCollection'
    assert len(geojson['features']) == 1
    feature = geojson['features'][0]
    assert feature['properties']['name'] == 'Paris'
    assert feature['properties']['type'] == 'city'


async def test_search_filters_can_be_combined(client, factory):
    factory(name='rue de Paris', type="street", postcode="77000")
    factory(name='avenue de Paris', type="street", postcode="22000")
    factory(name='Paris', type="city")
    resp = await client.get('/search/?q=paris&type=street&postcode=77000')
    geojson = json.loads(resp.body)
    assert geojson['type'] == 'FeatureCollection'
    assert len(geojson['features']) == 1
    feature = geojson['features'][0]
    assert feature['properties']['name'] == 'rue de Paris'
    assert feature['properties']['type'] == 'street'


async def test_centered_search_should_return_center(client, factory):
    factory(name='rue de Paris', type="street")
    resp = await client.get('/search/?q=paris&lat=44&lon=4')
    geojson = json.loads(resp.body)
    assert geojson['center'] == [4, 44]


async def test_reverse_should_return_geojson(client, factory):
    factory(name='rue des avions', lat=44, lon=4)
    resp = await client.get('/reverse/?lat=44&lon=4')
    geojson = json.loads(resp.body)
    assert geojson['type'] == 'FeatureCollection'
    assert len(geojson['features']) == 1
    feature = geojson['features'][0]
    assert feature['properties']['name'] == 'rue des avions'
    assert feature['properties']['id']
    assert feature['properties']['type']
    assert feature['properties']['score']
    assert 'attribution' in geojson
    assert 'licence' in geojson


async def test_reverse_should_also_accept_lng(client, factory):
    factory(name='rue des avions', lat=44, lon=4)
    resp = await client.get('/reverse/?lat=44&lng=4')
    geojson = json.loads(resp.body)
    assert len(geojson['features']) == 1


async def test_reverse_without_trailing_slash_should_not_be_redirected(client):
    resp = await client.get('/reverse?lat=44&lon=4')
    assert resp.status == 200


async def test_reverse_can_be_filtered(client, factory):
    factory(lat=48.234545, lon=5.235445, type="street")
    factory(lat=48.234546, lon=5.235446, type="city")
    resp = await client.get('/reverse/?lat=48.234545&lon=5.235446&type=city')
    geojson = json.loads(resp.body)
    assert geojson['type'] == 'FeatureCollection'
    assert len(geojson['features']) == 1
    feature = geojson['features'][0]
    assert feature['properties']['type'] == 'city'


async def test_reverse_should_have_cors_headers(client, factory):
    factory(name='rue des avions', lat=44, lon=4)
    resp = await client.get('/reverse/?lat=44&lng=4')
    assert resp.headers['Access-Control-Allow-Origin'] == '*'
    assert resp.headers['Access-Control-Allow-Headers'] == 'X-Requested-With'


async def test_reverse_without_lat_or_lng_should_return_400(client, factory):
    resp = await client.get('/reverse/?lat=44')
    assert resp.status == 400
    resp = await client.get('/reverse/?lng=4')
    assert resp.status == 400


async def test_app_should_expose_config(app, config):
    config.NEW_PROPERTY = "ok"
    assert app.config.NEW_PROPERTY == "ok"


async def test_geojson_should_return_housenumber_payload(client, factory,
                                                         config):
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.32', 'lon': '2.25', 'key': 'abc'}})
    resp = await client.get('/search/?' + urlencode({'q': 'rue de paris'}))
    geojson = json.loads(resp.body)
    assert 'key' not in geojson['features'][0]['properties']
    resp = await client.get('/search/?' + urlencode({'q': '1 rue de paris'}))
    geojson = json.loads(resp.body)
    assert geojson['features'][0]['properties']['key'] == 'abc'


async def test_geojson_should_keep_housenumber_parent_name(client, factory):
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.32', 'lon': '2.25'}})
    factory(name="Le Vieux-Chêne", type="locality", id="124",
            housenumbers={'2': {'lat': '48.22', 'lon': '2.22'}})
    resp = await client.get('/search/?' + urlencode({'q': '1 rue de paris'}))
    geojson = json.loads(resp.body)
    assert geojson['features'][0]['properties']['name'] == '1 rue de Paris'
    assert geojson['features'][0]['properties']['street'] == 'rue de Paris'
    resp = await client.get('/search/?' + urlencode({'q': '2 Le Vieux-Chêne'}))
    geojson = json.loads(resp.body)
    props = geojson['features'][0]['properties']
    assert props['name'] == '2 Le Vieux-Chêne'
    assert props['locality'] == 'Le Vieux-Chêne'


async def test_search_should_not_split_querystring_on_commas(client, factory):
    factory(name='rue des avions',
            housenumbers={'18': {'lat': '48.22', 'lon': '2.22'}})
    resp = await client.get(
        '/search/?' + urlencode({'q': '18, rue des avions'}))
    geojson = json.loads(resp.body)
    props = geojson['features'][0]['properties']
    assert props['label'] == '18 rue des avions'
    assert geojson['query'] == '18, rue des avions'


async def test_query_string_lenght_should_be_checked(client, config):
    config.QUERY_MAX_LENGTH = 10
    resp = await client.get('/search/?q=this+is+too+long')
    assert resp.status == 413
    assert resp.body == b'Query too long, 16 chars, limit is 10'
