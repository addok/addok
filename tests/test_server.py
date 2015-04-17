import io
import json


def test_search_without_query_should_return_400(client):
    resp = client.get('/search/')
    assert resp.status_code == 400


def test_search_should_return_geojson(client, factory):
    factory(name='rue des avions')
    resp = client.get('/search/', query_string={'q': 'avions'})
    assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
    data = json.loads(resp.data.decode())
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    feature = data['features'][0]
    assert feature['properties']['name'] == 'rue des avions'
    assert feature['properties']['id']
    assert feature['properties']['type']
    assert feature['properties']['score']
    assert 'attribution' in data
    assert 'licence' in data


def test_search_can_be_filtered(client, factory):
    factory(name='rue de Paris', type="street")
    factory(name='Paris', type="city")
    resp = client.get('/search/', query_string={'q': 'paris', 'type': 'city'})
    data = json.loads(resp.data.decode())
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    feature = data['features'][0]
    assert feature['properties']['name'] == 'Paris'
    assert feature['properties']['type'] == 'city'


def test_search_filters_can_be_combined(client, factory):
    factory(name='rue de Paris', type="street", postcode="77000")
    factory(name='avenue de Paris', type="street", postcode="22000")
    factory(name='Paris', type="city")
    resp = client.get('/search/', query_string={'q': 'paris', 'type': 'street',
                                                'postcode': '77000'})
    data = json.loads(resp.data.decode())
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    feature = data['features'][0]
    assert feature['properties']['name'] == 'rue de Paris'
    assert feature['properties']['type'] == 'street'


def test_csv_endpoint(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name,street,postcode,city\n'
               'Boulangerie Brûlé,rue des avions,31310,Montbrun-Bocage')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['street', 'postcode', 'postcode', 'city']})
    data = resp.data.decode()
    assert 'file.geocoded.csv' in resp.headers['Content-Disposition']
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'result_address' in data
    assert 'result_score' in data
    assert data.count('Montbrun-Bocage') == 2
    assert data.count('Boulangerie Brûlé') == 1  # Make sure accents are ok.


def test_csv_endpoint_with_empty_file(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name,street,postcode,city\n'
               ',,,')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv')})
    assert resp.data.decode()


def test_csv_endpoint_with_multilines_fields(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name,adresse\n'
               '"Boulangerie Brûlé","rue des avions\n31310\nMontbrun-Bocage"\n'
               '"Pâtisserie Crème","rue des avions\n31310\nMontbrun-Bocage"\n')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['adresse']})
    data = resp.data.decode()
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'result_address' in data
    assert 'result_score' in data
    # \n as been replaced by \r\n
    assert 'rue des avions\r\n31310\r\nMontbrun-Bocage' in data


def test_csv_endpoint_with_tab_as_delimiter(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name\tadresse\n'
               'Boulangerie\true des avions Montbrun')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['adresse']})
    data = resp.data.decode()
    assert 'Boulangerie\true des avions Montbrun' in data


def test_reverse_should_return_geojson(client, factory):
    factory(name='rue des avions', lat=44, lon=4)
    resp = client.get('/reverse/', query_string={'lat': '44', 'lon': '4'})
    data = json.loads(resp.data.decode())
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    feature = data['features'][0]
    assert feature['properties']['name'] == 'rue des avions'
    assert feature['properties']['id']
    assert feature['properties']['type']
    assert feature['properties']['score']
    assert 'attribution' in data
    assert 'licence' in data


def test_reverse_can_be_filtered(client, factory):
    factory(lat=48.234545, lon=5.235445, type="street")
    factory(lat=48.234546, lon=5.235446, type="city")
    resp = client.get('/reverse/', query_string={'lat': '48.234545',
                                                 'lon': '5.235446',
                                                 'type': 'city'})
    data = json.loads(resp.data.decode())
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    feature = data['features'][0]
    assert feature['properties']['type'] == 'city'
