import csv
import re

import redis
import ngram
from unidecode import unidecode

from .fuzzy import fuzzy as make_fuzzy

DB = redis.StrictRedis(host='localhost', port=6379, db=0)


def insert_document(document):
    key = document_key(document['id'])
    DB.hmset(key, document)
    for s in prepare(document['name']):
        DB.sadd(token_key(normalize(s)), key)


def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def tokenize(text, lang="fr"):
    """
    Split text into a list of tokens.
    """
    if lang == "fr":
        pattern = r"[\w]+"
    else:
        raise NotImplementedError
    return re.compile(pattern, re.U | re.X).findall(text)


def normalize(text, lang="fr"):
    if lang == "fr":
        return unidecode(text.lower())
    else:
        raise NotImplementedError


def prepare(text):
    for s in tokenize(text):
        yield normalize(s)


def token_key_frequency(key):
    return DB.scard(key)


def token_frequency(token):
    return token_key_frequency(token_key(token))


def word_frequency(word):
    token = normalize(word)
    return token_frequency(token)


def common_term(token):
    return token_frequency(token) > 1000  # TODO: Take a % of nb of docs.


class Result(object):

    def __init__(self, doc):
        for key, value in doc.items():
            setattr(self, key.decode(), value.decode())
        self.score = float(self.importance)

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self.id, self.score)


class Token(object):

    def __init__(self, original):
        self.original = original
        self.key = token_key(original)


def score_ngram(result, query):
    # TODO: case and accents.
    score = ngram.NGram.compare(result.name, query)
    result.score += score


def retrieve_autocomplete_keys(token):
    # TODO: find a way to limit number of results when word is small:
    # - target only "rare" keys?
    key = '{}*'.format(token_key(token))
    return DB.keys(key)


def results_from_keys(keys, limit=100):
    results = []
    ids = []
    if keys:
        ids = DB.sinter(keys)
    for _id in ids:
        results.append(Result(DB.hgetall(_id)))
        if len(results) >= limit:
            break
    return results


def keys_sets_temp_key(keys_sets):
    return 'kstmp|{}'.format('.'.join(keys_sets))


def search(query, match_all=False, fuzzy=0, limit=10, autocomplete=0):
    hard_limit = 100
    results = []
    keys_sets = [[]]
    tokens = list(prepare(query))
    tokens.sort(key=lambda x: len(x), reverse=True)
    for token in tokens:
        key = token_key(token)
        if DB.exists(key):
            if not match_all:
                without = [k[:] for k in keys_sets[:]] or [[]]
            for keys_set in keys_sets:
                keys_set.append(key)
            if not match_all:
                print('extend for', token)
                keys_sets.extend(without)
        elif fuzzy > 0:
            neighbors = make_fuzzy(token)
            print(token, "neighbors", len(neighbors))
            if neighbors:
                new_keys_sets = []
                for neighbor in neighbors:
                    for keys in keys_sets:
                        key = token_key(neighbor)
                        if DB.exists(key):
                            new_keys_set = keys.copy()
                            new_keys_set.append(key)
                            keys_sets_key = keys_sets_temp_key(new_keys_set)
                            if DB.sinterstore(keys_sets_key, new_keys_set):
                                new_keys_sets.append(new_keys_set)
                            DB.delete(keys_sets_key)
                if new_keys_sets:
                    print("Replacing keys_sets for", token)
                    keys_sets = new_keys_sets
        elif match_all:
            return []
    print(keys_sets)
    for keys in keys_sets:
        results.extend(results_from_keys(keys, limit=hard_limit))
    if autocomplete:
        if key in keys:
            keys.remove(key)
        possible_keys = retrieve_autocomplete_keys(token)
        for key in possible_keys:
            try_with = keys.copy()
            try_with.add(key)
            results.extend(results_from_keys(try_with))

    # Score and sort.
    for r in results:
        score_ngram(r, query)
    results.sort(key=lambda d: d.score, reverse=True)
    return results[:limit]


FIELDS = [
    'source_id', 'housenumber', 'name', 'postcode', 'city', 'source', 'lat',
    'lon', 'dep', 'region', 'type'
]
TYPES = [
    'avenue', 'rue', 'boulevard', 'all[ée]es?', 'impasse', 'place',
    'chemin', 'rocade', 'route', 'l[ôo]tissement', 'mont[ée]e', 'c[ôo]te',
    'clos', 'champ', 'bois', 'taillis', 'boucle', 'passage', 'domaine',
    'étang', 'etang', 'quai', 'desserte', 'pré', 'porte', 'square', 'mont',
    'r[ée]sidence', 'parc', 'cours?', 'promenade', 'hameau', 'faubourg',
    'ilot', 'berges?', 'via', 'cit[ée]', 'sent(e|ier)', 'rond[- ][Pp]oint',
    'pas(se)?', 'carrefour', 'traverse', 'giratoire', 'esplanade', 'voie',
]
TYPES_REGEX = '|'.join(
    map(lambda x: '[{}{}]{}'.format(x[0], x[0].upper(), x[1:]), TYPES)
)


def split_address(q):
    m = re.search(
        "^(?P<type>" + TYPES_REGEX + ")"
        "[a-z ']+(?P<name>[\wçàèéuâêôîûöüïäë '\-]+)", q)
    return m.groupdict() if m else {}


def split_housenumber(q):
    m = re.search("^(?P<number>[\d]+)/?(?P<ordinal>([^\d]+|[\d]{1}))?", q)
    return m.groupdict() if m else {}


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
        "id": row["source_id"],
        "importance": 0.0,
        # "coordinate": {
        #     "lat": row['lat'],
        #     "lon": row['lon']
        # },
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
        return  # handle them later
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
            insert_document(doc)
            count += 1
            if count % 1000 == 0:
                print("Done", count)


if __name__ == '__main__':
    import_data('data.csv')
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
