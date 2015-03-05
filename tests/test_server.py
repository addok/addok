import io
import json


def test_search_without_query_should_return_400(client):
    resp = client.get('/search/')
    assert resp.status_code == 400


def test_search_should_return_geojson(client, factory):
    factory(name='rue des avions')
    resp = client.get('/search/', query_string={'q': 'avions'})
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
