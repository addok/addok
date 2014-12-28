import re

from .core import DB, token_key, document_key, housenumber_field_key
from .pipeline import preprocess


def index_housenumber(key, document):
    val = '|'.join([document['housenumber'], document['lat'], document['lon']])
    for hn in preprocess(document['housenumber']):
        DB.hset(key, housenumber_field_key(hn), val)


def index_field(key, string, boost=1.0):
    els = list(preprocess(string))
    for s in els:
        DB.zadd(token_key(s), 1.0 / len(els) * boost, key)


def index_document(document):
    key = document_key(document['id'])
    exists = DB.exists(key)
    if document['type'] == 'housenumber':
        index_housenumber(key, document)
        index_field(key, document['housenumber'])
    if not exists or document['type'] != 'housenumber':
        document.pop('housenumber', None)  # When we create the street from the
                                           # housenumber row.
        DB.hmset(key, document)
        name = document['name']
        index_field(key, name, boost=3.0)
        city = document.get('city')
        if city and city != name:
            index_field(key, city)
        postcode = document.get('postcode')
        if postcode:
            boost = 1.2 if document['type'] == 'city' else 1
            index_field(key, postcode, boost=boost)


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
