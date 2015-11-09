"""Import from Nominatim database."""

import psycopg2
import psycopg2.extras

from addok.utils import yielder
from .psql import connection


@yielder
def get_context(row):
    if "context" not in row:
        row['context'] = []
    add_parent(row, row)
    return row


def add_parent(child, row):
    if child['parent_place_id']:
        sql = """SELECT parent_place_id, type, class, name->'name' as name,
            admin_level FROM placex WHERE place_id=%(parent_place_id)s"""
        cur = connection.cursor(str(child['parent_place_id']),
                                cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, {'parent_place_id': child['parent_place_id']})
        parent = cur.fetchone()
        cur.close()
        add_parent_data(parent, row)
        add_parent(parent, row)


def add_parent_data(parent, row):
    name = parent['name']
    if name and name not in row['context']:
        row["context"].append(name)
    if (parent['class'] == 'boundary'
       and parent['type'] == 'administrative'
       and parent['admin_level'] == 8 and not row.get('city')):
        row['city'] = name


@yielder
def get_housenumbers(row):
    if row['class'] == 'highway':
        sql = """SELECT housenumber, ST_X(ST_Centroid(geometry)) as lon,
            ST_Y(ST_Centroid(geometry)) as lat
            FROM placex
            WHERE housenumber IS NOT NULL
            AND parent_place_id=%(place_id)s"""
        cur = connection.cursor(str(row['place_id']),
                                cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, {'place_id': row['place_id']})
        housenumbers = cur.fetchall()
        cur.close()
        row['housenumbers'] = {
            hn['housenumber']: {'lat': hn['lat'], 'lon': hn['lon']}
            for hn in housenumbers
        }
    return row


@yielder
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
