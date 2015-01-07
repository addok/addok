import csv
import time

from multiprocessing import Pool

from addok.core import DB
from addok.index_utils import index_document, index_edge_ngrams
from addok.textutils.fr import split_housenumber


FIELDS = [
    'source_id', 'housenumber', 'name', 'postcode', 'city', 'source', 'lat',
    'lon', 'dep', 'region', 'type'
]


def row_to_doc(row):
    dep_id_len = 3 if row['source_id'].startswith('97') else 2
    dep_id = str(row['source_id'])[:dep_id_len]
    context = ', '.join([dep_id, row['dep'], row['region']])
    # type can be:
    # - number => housenumber
    # - street => street
    # - hamlet => locality found in OSM as place=hamlet
    # - place => locality not found in OSM
    # - village => village
    # - town => town
    # - city => city
    type_ = row['type']
    name = row.get('name')
    if type_ == 'number':
        type_ = 'housenumber'
    elif type_ in ['hamlet', 'place']:
        type_ = 'locality'
    doc = {
        "id": row["source_id"].split('-')[0],
        "lat": row['lat'],
        "lon": row['lon'],
        "postcode": row['postcode'],
        "city": row['city'],
        "context": context,
        "type": type_,
        "name": name
    }
    housenumber = row.get('housenumber')
    if housenumber:
        els = split_housenumber(housenumber)
        if els:
            doc['housenumber'] = els['number']
            if els['ordinal']:
                doc['ordinal'] = els['ordinal']
        else:
            doc['housenumber'] = housenumber
    elif type_ in ['village', 'town', 'city', 'commune']:
        doc['importance'] = 0.1
        # Sometimes, a village is in reality an hamlet, so it has both a name
        # (the hamlet name) and a city (the administrative entity it belongs
        # to), this is why we first look if a name exists.
        doc['name'] = name or row.get('city')
    return doc


def index_row(row):
    doc = row_to_doc(row)
    if not doc:
        return
    index_document(doc)


def import_from_csv(filepath, limit=None):
    print('Importing from', filepath)

    start = time.time()
    with open(filepath) as f:
        pool = Pool()
        reader = csv.DictReader(f, fieldnames=FIELDS, delimiter='|')
        count = 0
        chunk = []
        for row in reader:
            count += 1
            chunk.append(row)
            if count % 10000 == 0:
                pool.map(index_row, chunk)
                print("Done", count, time.time() - start)
                chunk = []
        pool.close()
        pool.join()
    print('Done in', time.time() - start)


def create_edge_ngrams():
    for key in DB.scan_iter(match='w|*'):
        key = key.decode()
        _, token = key.split('|')
        if token.isdigit():
            continue
        index_edge_ngrams(token)
