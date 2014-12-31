import csv


from addok.import_utils import index_document, split_housenumber


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
    if type_ == 'number':
        type_ = 'housenumber'
    elif type_ in ['hamlet', 'place']:
        type_ = 'locality'
    doc = {
        "id": row["source_id"].split('-')[0],
        "importance": 0.0,
        "lat": row['lat'],
        "lon": row['lon'],
        "postcode": row['postcode'],
        "city": row['city'],
        "context": context,
        "type": type_,
    }
    name = row.get('name')
    # way_label = None
    # way_keywords = None
    # if name:
    #     split = split_address(name)
    #     if split:
    #         way_label = split['type']
    #         way_keywords = split['name']

    # if way_label:
    #     doc['way_label'] = way_label

    housenumber = row.get('housenumber')
    if housenumber:
        els = split_housenumber(housenumber)
        if els:
            doc['housenumber'] = els['number']
            doc['ordinal'] = els['ordinal']
        else:
            doc['housenumber'] = housenumber
        doc['name'] = name
        # if way_keywords:
        #     doc['street']['keywords'] = way_keywords
    elif type_ in ['street', 'locality']:
        doc['name'] = name
    elif type_ in ['village', 'town', 'city', 'commune']:
        doc['importance'] = 1
        # Sometimes, a village is in reality an hamlet, so it has both a name
        # (the hamlet name) and a city (the administrative entity it belongs
        # to), this is why we first look if a name exists.
        doc['name'] = name or row.get('city')
    else:
        doc['name'] = name
    # if way_keywords and 'name' in doc:
    #     doc['name']['keywords'] = way_keywords
    return doc


def import_data(filepath, limit=None):
    print('Importing from', filepath)
    with open(filepath) as f:
        reader = csv.DictReader(f, fieldnames=FIELDS, delimiter='|')
        count = 0
        for row in reader:
            doc = row_to_doc(row)
            if not doc:
                continue
            index_document(doc)
            count += 1
            if count % 1000 == 0:
                print("Done", count)
            if limit and count >= limit:
                break


if __name__ == '__main__':
    import_data('data.csv')
    # import_data('idf.csv')
    # document = {
    #     "id": "590010020E",
    #     "name": "rue vicq d'Azir",
    #     "context": "Xe arrondissement Paris Île-de-France"
    # }
    # insert_document(document)
    # document = {
    #     "id": "590010020X",
    #     "name": "Avenue des Champs-Élysées",
    #     "context": "Ve arrondissement Paris Île-de-France"
    # }
    # insert_document(document)
