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
    assert data['features'][0]['properties']['name'] == 'rue des avions'


def test_csv_endpoint(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name,street,postcode,city\n'
               'boulangerie,rue des avions,31310,Montbrun-Bocage')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv')})
    data = resp.data.decode()
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'result_address' in data
    assert 'result_score' in data
    assert data.count('Montbrun-Bocage') == 2
