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
    for s in prepare(document.get('city', '')):
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
        label = self.name
        city = getattr(self, 'city', None)
        if city:
            label = '{} {}'.format(label, city)
        return label

    def __repr__(self):
        return '<{} - {} ({})>'.format(str(self), self.id, self.score)


class Token(object):

    def __init__(self, original, position, is_last=False):
        self.original = original
        self.position = position
        self.is_last = is_last
        self.key = token_key(original)
        self.db_key = None
        self.fuzzy_keys = []

    def __len__(self):
        return len(self.original)

    def __str__(self):
        return self.original

    def __repr__(self):
        return '<Token {}>'.format(self.original)

    def search(self):
        if DB.exists(self.key):
            self.db_key = self.key

    def make_fuzzy(self):
        neighbors = self.neighbors
        keys = []
        if neighbors:
            for neighbor in neighbors:
                key = token_key(neighbor)
                count = DB.scard(key)
                if count:
                    keys.append((key, count))
        keys.sort(key=lambda x: x[1])
        for key, count in keys:
            self.fuzzy_keys.append(key)

    @property
    def neighbors(self):
        return make_fuzzy(self.original)

    @property
    def is_common(self):
        return self.frequency > 1000

    @property
    def frequency(self):
        if not hasattr(self, '_frequency'):
            self._frequency = common_term(self.original)
        return self._frequency

    @property
    def is_fuzzy(self):
        return not self.db_key and self.fuzzy_keys


def score_ngram(result, query):
    # TODO: case and accents.
    score = ngram.NGram.compare(result.name, query)
    result.score += score


def retrieve_autocomplete_keys(token):
    # TODO: find a way to limit number of results when word is small:
    # - target only "rare" keys?
    key = '{}*'.format(token_key(token))
    return DB.keys(key)


def keys_sets_temp_key(keys_sets):
    return 'kstmp|{}'.format('.'.join(keys_sets))


class Empty(Exception):
    pass


class Search(object):

    HARD_LIMIT = 1000

    def __init__(self, match_all=False, fuzzy=0, limit=10, autocomplete=0):
        self.match_all = match_all
        self.fuzzy = fuzzy
        self.limit = limit

    def __call__(self, query):
        self.results = []
        ok_tokens = []
        pending_tokens = []
        self.ids = []
        self.query = query
        self.preprocess(query)
        self.search_all()
        for token in self.tokens:
            if token.db_key and not token.is_common:
                ok_tokens.append(token)
            else:
                pending_tokens.append(token)
        if not ok_tokens:  # Take the less common as basis.
            commons = [t for t in self.tokens if t.is_common]
            if commons:
                commons.sort(lambda x: x.frequency, reverse=True)
                ok_tokens = commons[:1]
        ok_keys = [t.db_key for t in ok_tokens]
        ids = self.intersect(ok_keys)
        if ids and len(ids) <= self.HARD_LIMIT or not pending_tokens:
            return self.render(ids)
        # Retrieve not found.
        not_found = []
        for token in pending_tokens:
            if not token.db_key:
                not_found.append(token)
        if not_found and self.fuzzy:
            not_found.sort(key=lambda t: len(t), reverse=True)
            try_one = not_found[0]  # Take the biggest one.
            print('trying with', try_one)
            try_one.make_fuzzy()
            for key in try_one.fuzzy_keys:
                ids = self.intersect(ok_keys + [key])
                if ids:
                    return self.render(ids)
        return self.render(ids)

    def render(self, ids):
        self.compute_results(ids)
        # Score and sort.
        for r in self.results:
            score_ngram(r, self.query)
        self.results.sort(key=lambda d: d.score, reverse=True)
        return self.results[:self.limit]

    def preprocess(self, query):
        self.tokens = [Token(t, position=i) for i, t in enumerate(prepare(query))]
        self.tokens.sort(key=lambda x: len(x), reverse=True)

    def search_all(self):
        for token in self.tokens:
            token.search()
            if (self.match_all and (not self.fuzzy or not token.fuzzy_keys)
               and not token.db_key):
                raise Empty

    def intersect(self, keys):
        if keys:
            return DB.sinter(keys)
        else:
            return []

    def compute_results(self, ids):
        for _id in ids:
            self.results.append(Result(DB.hgetall(_id)))
            if len(self.results) >= self.HARD_LIMIT:
                print('Hit HARD_LIMIT for', self.query)
                break


def search(query, match_all=False, fuzzy=0, limit=10, autocomplete=0):
    helper = Search(match_all=match_all, fuzzy=fuzzy, limit=limit)
    return helper(query)


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
