"""Import data from the BANO project."""
import json

from .utils import batch


def row_to_doc(row):
    try:
        row = json.loads(row)
    except ValueError:
        return
    if row.get('_action') == "delete":
        return row
    dep_id_len = 3 if row['id'].startswith('97') else 2
    dep_id = str(row['id'])[:dep_id_len]
    context = [dep_id]
    if row['departement'] != row.get('city'):
        context.append(row['departement'])
    context.append(row['region'])
    context = ', '.join(context)
    # type can be:
    # - street => street
    # - hamlet => locality found in OSM as place=hamlet
    # - place => locality not found in OSM
    # - village => village
    # - town => town
    # - city => city
    type_ = row['type']
    name = row.get('name')
    if type_ in ['hamlet', 'place']:
        type_ = 'locality'
    doc = {
        "id": row["id"].split('-')[0],
        "lat": row['lat'],
        "lon": row['lon'],
        "postcode": row['postcode'],
        "city": row['city'],
        "context": context,
        "type": type_,
        "name": name,
        "importance": row.get('importance', 0.0)
    }
    housenumbers = row.get('housenumbers')
    if housenumbers:
        doc['housenumbers'] = housenumbers
    if type_ in ['village', 'town', 'city', 'commune', 'locality']:
        # Sometimes, a village is in reality an hamlet, so it has both a name
        # (the hamlet name) and a city (the administrative entity it belongs
        # to), this is why we first look if a name exists.
        doc['name'] = name or row.get('city')
    return doc


def process_file(filepath):
    with open(filepath) as f:
        batch(map(row_to_doc, f))


def process_stdin(stdin):
    print('Import from stdin')
    batch(map(row_to_doc, stdin))
