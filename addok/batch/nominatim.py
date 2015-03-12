"""Import from Nominatim database."""

import psycopg2
import psycopg2.extras

from .utils import batch


class NominatimExport(object):

    def __init__(self, itersize=1000, limit=None, dbname='nominatim',
                 user='nominatim', host=None, port=None, onlyaddress=False,
                 noaddress=False):
        self.dbname = dbname
        self.user = user
        self.host = host
        self.port = port
        self.onlyaddress = onlyaddress
        self.noaddress = noaddress
        print('***************** Export init ***************')
        self.cur = self.conn.cursor(
            "nominatim", cursor_factory=psycopg2.extras.DictCursor)
        self.cur.itersize = itersize
        print('Cursor created')
        self.limit = limit

    @property
    def conn(self):
        if not getattr(self, '_conn', None):
            credentials = {
                'dbname': self.dbname
            }
            if self.user:
                credentials['user'] = self.user
            if self.host:
                credentials['host'] = self.host
            if self.port:
                credentials['port'] = self.port
            self._conn = psycopg2.connect(**credentials)
            print('Created connection')
        return self._conn

    def __enter__(self):
        sql = """SELECT osm_type,osm_id,class,type,admin_level,rank_search,
            place_id,parent_place_id,street,postcode,
            (extratags->'ref') as ref,
            ST_X(ST_Centroid(geometry)) as lon,
            ST_Y(ST_Centroid(geometry)) as lat,
            name->'name' as name, name->'short_name' as short_name,
            name->'official_name' as official_name,
            name->'alt_name' as alt_name
            FROM placex
            WHERE name ? 'name'
            {extrawhere}
            ORDER BY place_id
            {limit}
            """
        extrawhere = ""
        if self.noaddress:
            extrawhere = ("AND (class!='highway' OR osm_type='W') "
                          "AND class!='place'")
        elif self.onlyaddress:
            extrawhere = "AND class='highway' AND osm_type='W'"
        limit = ''
        if self.limit:
            limit = 'LIMIT {limit}'.format(limit=limit)
        # Python format because SQL one doesn't handle empty strings.
        sql = sql.format(extrawhere=extrawhere, limit=limit)
        self.cur.execute(sql)
        print('Query executed with itersize', self.cur.itersize)
        return self

    def __iter__(self):
        for row in self.cur.__iter__():
            yield self.extend_row(dict(row))

    def extend_row(self, row):
        if "context_name" not in row:
            row['context'] = []
        self.add_parent(row, row)
        if not self.noaddress and row['class'] == 'highway':
            self.add_housenumbers(row)
        return row

    def add_parent(self, child, row):
        if child['parent_place_id']:
            sql = """SELECT parent_place_id, type, class, name->'name' as name,
                admin_level FROM placex WHERE place_id=%(parent_place_id)s"""
            cur = self.conn.cursor(str(child['parent_place_id']),
                                   cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(sql, {'parent_place_id': child['parent_place_id']})
            parent = cur.fetchone()
            cur.close()
            self.add_parent_data(parent, row)
            self.add_parent(parent, row)

    def add_parent_data(self, parent, row):
        name = parent['name']
        if name and name not in row['context']:
            row["context"].append(name)
        if (parent['class'] == 'boundary'
           and parent['type'] == 'administrative'
           and parent['admin_level'] == 8 and not row.get('city')):
            row['city'] = name

    def add_housenumbers(self, row):
        if not row['name'] or not row['postcode']:
            return
        sql = """SELECT housenumber, ST_X(ST_Centroid(geometry)) as lon,
            ST_Y(ST_Centroid(geometry)) as lat
            FROM placex
            WHERE housenumber IS NOT NULL
            AND parent_place_id=%(place_id)s"""
        cur = self.conn.cursor(str(row['place_id']),
                               cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, {'place_id': row['place_id']})
        housenumbers = cur.fetchall()
        cur.close()
        row['housenumbers'] = {
            hn['housenumber']: {'lat': hn['lat'], 'lon': hn['lon']}
            for hn in housenumbers
        }

    def __exit__(self, *args):
        self.cur.close()
        self.conn.close()


def row_to_doc(row):
    doc = {
        "id": row["osm_type"] + str(row["osm_id"]),
        "lat": row['lat'],
        "lon": row['lon'],
        "name": row['name'],
        "importance": row.get('importance', 0.0) * 0.1
    }
    city = row.get('city')
    if city:
        doc['city'] = city
    street = row.get('street')
    if street:
        doc['street'] = street
    context = row.get('context')
    if context:
        doc['context'] = context
    housenumbers = row.get('housenumbers')
    if housenumbers:
        doc['housenumbers'] = housenumbers
    doc['type'] = row.get('class', 'unknown')
    try:
        doc['postcode'] = row['postcode'].split(';')[0]
    except (ValueError, AttributeError):
        pass
    else:
        # Departement number.
        doc['context'] = doc.get('context', []) + [doc['postcode'][:2]]
    if doc.get('context'):
        doc['context'] = ', '.join(doc['context'])
    row['source'] = 'OSM'
    # See https://wiki.osm.org/wiki/Nominatim/Development_overview#Country_to_street_level  # noqa
    doc['importance'] = (row.get('rank_search', 30) / 30) * 0.1
    return doc


def import_from_sql(**kwargs):
    print('Import from Nominatim DB')
    with NominatimExport(**kwargs) as exporter:
        batch(map(row_to_doc, exporter))
