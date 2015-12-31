import io
import json


from addok.server import View


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


def test_search_without_trailing_slash_should_not_be_redirected(client):
    resp = client.get('/search', query_string={'q': 'avions'})
    assert resp.status_code == 200


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
                       'columns': ['street', 'postcode', 'city']})
    data = resp.data.decode()
    assert 'file.geocoded.csv' in resp.headers['Content-Disposition']
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'result_label' in data
    assert 'result_score' in data
    assert data.count('Montbrun-Bocage') == 3
    assert data.count('Boulangerie Brûlé') == 1  # Make sure accents are ok.


def test_csv_endpoint_with_housenumber(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage',
            housenumbers={'118': {'lat': 10.22334401, 'lon': 12.33445501}})
    content = ('name,housenumber,street,postcode,city\n'
               'Boulangerie Brûlé,118,rue des avions,31310,Montbrun-Bocage')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['housenumber', 'street', 'postcode',
                                   'city']})
    data = resp.data.decode()
    assert 'result_housenumber' in data
    assert data.count('118') == 3


def test_csv_endpoint_with_empty_file(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('name,street,postcode,city\n'
               ',,,')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv')})
    assert resp.data.decode()


def test_csv_endpoint_with_bad_column(client, factory):
    content = ('name,street,postcode,city\n'
               ',,,')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': 'xxxxx'})
    assert resp.status_code == 400


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
    assert 'result_label' in data
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


def test_csv_endpoint_with_one_column(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    factory(name='rue des bateaux', postcode='31310', city='Montbrun-Bocage')
    content = ('adresse\n'
               'rue des avions Montbrun\nrue des bateaux Montbrun')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['adresse']})
    data = resp.data.decode()
    assert 'rue des avions Montbrun' in data


def test_csv_endpoint_with_not_enough_content(client, factory):
    factory(name='rue', postcode='80688', type='city')
    content = ('q\n'
               'rue')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'delimiter': ','})
    data = resp.data.decode()
    assert '80688' in data


def test_csv_endpoint_with_not_enough_content_but_delimiter(client, factory):
    factory(name='rue', postcode='80688', type='city')
    content = ('q\n'
               'rue')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'delimiter': ','})
    data = resp.data.decode()
    assert '80688' in data


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


def test_reverse_should_also_accept_lng(client, factory):
    factory(name='rue des avions', lat=44, lon=4)
    resp = client.get('/reverse/', query_string={'lat': '44', 'lng': '4'})
    data = json.loads(resp.data.decode())
    assert len(data['features']) == 1


def test_reverse_without_trailing_slash_should_not_be_redirected(client):
    resp = client.get('/reverse', query_string={'lat': '44', 'lon': '4'})
    assert resp.status_code == 200


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


def test_csv_reverse_endpoint(client, factory):
    factory(name='rue des brûlés', postcode='31310', city='Montbrun-Bocage',
            lat=10.22334401, lon=12.33445501)
    content = ('latitude,longitude\n'
               '10.223344,12.334455')
    resp = client.post(
        '/reverse/csv/',
        data={'data': (io.BytesIO(content.encode()), 'file.csv')})
    data = resp.data.decode()
    assert 'file.geocoded.csv' in resp.headers['Content-Disposition']
    assert 'result_latitude' in data
    assert '10.22334401' in data
    assert 'result_longitude' in data
    assert '12.33445501' in data
    assert 'result_label' in data
    assert 'result_distance' in data
    assert 'Montbrun-Bocage' in data
    assert 'rue des brûlés' in data


def test_csv_endpoint_can_be_filtered(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    factory(name='rue des avions', postcode='09350', city='Fornex')
    content = ('rue,code postal,ville\n'
               'rue des avions,31310,Montbrun-Bocage')
    # We are asking to filter by 'postcode' using the column 'code postal'.
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['rue'], 'postcode': 'code postal'})
    data = resp.data.decode()
    assert data.count('31310') == 3
    assert data.count('09350') == 0
    content = ('rue,code postal,ville\n'
               'rue des avions,09350,Fornex')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['rue'], 'postcode': 'code postal'})
    data = resp.data.decode()
    assert data.count('09350') == 3
    assert data.count('31310') == 0


def test_csv_endpoint_skip_empty_filter_value(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage')
    content = ('rue,code postal,ville\n'
               'rue des avions,,Montbrun-Bocage')
    # We are asking to filter by 'postcode' using the column 'code postal'.
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['rue'], 'postcode': 'code postal'})
    data = resp.data.decode()
    assert data.count('31310') == 2


def test_csv_endpoint_can_use_geoboost(client, factory):
    factory(name='rue des avions', postcode='31310', city='Montbrun-Bocage',
            lat=10.22334401, lon=12.33445501)
    factory(name='rue des avions', postcode='59118', city='Wambrechies',
            lat=50.6845, lon=3.0480)
    content = ('rue,latitude,longitude\n'
               'rue des avions,10.22334401,12.33445501')
    # We are asking to center with 'lat' & 'lon'.
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['rue'], 'lat': 'latitude',
                       'lon': 'longitude'})
    data = resp.data.decode()
    assert data.count('31310') == 2
    assert data.count('59118') == 0
    content = ('rue,latitude,longitude\n'
               'rue des avions,50.6845,3.0480')
    resp = client.post(
        '/csv/', data={'data': (io.BytesIO(content.encode()), 'file.csv'),
                       'columns': ['rue'], 'lat': 'latitude',
                       'lon': 'longitude'})
    data = resp.data.decode()
    assert data.count('59118') == 2
    assert data.count('31310') == 0


def test_csv_reverse_endpoint_can_be_filtered(client, factory):
    factory(name='rue des brûlés', postcode='31310', city='Montbrun-Bocage',
            lat=10.22334401, lon=12.33445501,
            housenumbers={'118': {'lat': 10.22334401, 'lon': 12.33445501}})
    # First we ask for a street.
    content = ('latitude,longitude,object\n'
               '10.223344,12.334455,street\n')
    resp = client.post(
        '/reverse/csv/',
        data={'data': (io.BytesIO(content.encode()), 'file.csv'),
              'type': 'object'})
    data = resp.data.decode()
    assert data.count('118') == 0
    # Now we ask for a housenumber.
    content = ('latitude,longitude,object\n'
               '10.223344,12.334455,housenumber\n')
    resp = client.post(
        '/reverse/csv/',
        data={'data': (io.BytesIO(content.encode()), 'file.csv'),
              'type': 'object'})
    data = resp.data.decode()
    assert data.count('118') == 2


def test_get_endpoint(client, factory):
    factory(name='sentier de la côte', id='123')
    resp = client.get('/get/123')
    data = json.loads(resp.data.decode())
    assert data['properties']['id'] == '123'


def test_get_endpoint_with_invalid_id(client):
    resp = client.get('/get/123')
    assert resp.status_code == 404


def test_allow_to_extend_api_endpoints(client, config):
    config.URL_MAP = None  # Reset map.
    config.API_ENDPOINTS = config.API_ENDPOINTS + [('/custom/<param>/',
                                                    'custom')]

    class MyEndPoint(View):
        endpoint = 'custom'

        def get(self, param):
            return param

    resp = client.get('/custom/xxxxx/')
    assert resp.status_code == 200
    assert resp.data == b'xxxxx'


def test_view_should_expose_config(config):
    config.NEW_PROPERTY = "ok"
    assert View.config.NEW_PROPERTY == "ok"


def test_geojson_should_return_housenumber_payload(client, factory, config):
    config.HOUSENUMBERS_PAYLOAD_FIELDS = ['key']
    factory(name="rue de Paris", type="street", id="123",
            housenumbers={'1': {'lat': '48.32', 'lon': '2.25', 'key': 'abc'}})
    resp = client.get('/search/', query_string={'q': 'rue de paris'})
    data = json.loads(resp.data.decode())
    assert 'key' not in data['features'][0]['properties']
    resp = client.get('/search/', query_string={'q': '1 rue de paris'})
    data = json.loads(resp.data.decode())
    assert data['features'][0]['properties']['key'] == 'abc'
