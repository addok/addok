import csv
import json
import time

from multiprocessing import Pool

from addok.core import DB
from addok.index_utils import index_document, index_edge_ngrams


FIELDS = [
    'source_id', 'housenumber', 'name', 'postcode', 'city', 'source', 'lat',
    'lon', 'dep', 'region', 'type'
]


def row_to_doc(row):
    dep_id_len = 3 if row['id'].startswith('97') else 2
    dep_id = str(row['id'])[:dep_id_len]
    context = [dep_id]
    if row['dep'] != row.get('city'):
        context.append(row['dep'])
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
        "importance": row.get('importance', 0.000) * 0.1
    }
    housenumbers = row.get('housenumbers')
    if housenumbers:
        doc['housenumbers'] = housenumbers
    if type_ in ['village', 'town', 'city', 'commune', 'locality']:
        # Sometimes, a village is in reality an hamlet, so it has both a name
        # (the hamlet name) and a city (the administrative entity it belongs
        # to), this is why we first look if a name exists.
        doc['name'] = name or row.get('city')
    return doc


def index_row(row):
    doc = row_to_doc(row)
    if not doc:
        return
    index_document(doc, update_ngrams=False)


def import_from_stream_json(filepath, limit=None):
    print('Importing from', filepath)

    start = time.time()
    with open(filepath) as f:
        pool = Pool()
        count = 0
        chunk = []
        for row in f:
            count += 1
            chunk.append(json.loads(row))
            if count % 10000 == 0:
                pool.map(index_row, chunk)
                print("Done", count, time.time() - start)
                chunk = []
        if chunk:
            pool.map(index_row, chunk)
        pool.close()
        pool.join()
    print('Done', count, 'in', time.time() - start)


def index_ngram_key(key):
    key = key.decode()
    _, token = key.split('|')
    if token.isdigit():
        return
    index_edge_ngrams(DB, token)


def create_edge_ngrams():
    start = time.time()
    pool = Pool()
    count = 0
    chunk = []
    for key in DB.scan_iter(match='w|*'):
        count += 1
        chunk.append(key)
        if count % 10000 == 0:
            pool.map(index_ngram_key, chunk)
            print("Done", count, time.time() - start)
            chunk = []
    if chunk:
        pool.map(index_ngram_key, chunk)
    pool.close()
    pool.join()
    print('Done', count, 'in', time.time() - start)
