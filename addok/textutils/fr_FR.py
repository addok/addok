"""France dedicated text utils."""

import re

from addok.utils import yielder


TYPES = [
    'avenue', 'rue', 'boulevard', 'all[ée]es?', 'impasse', 'place',
    'chemin', 'rocade', 'route', 'l[ôo]tissement', 'mont[ée]e', 'c[ôo]te',
    'clos', 'champ', 'bois', 'taillis', 'boucle', 'passage', 'domaine',
    'étang', 'etang', 'quai', 'desserte', 'pré', 'porte', 'square', 'mont',
    'r[ée]sidence', 'parc', 'cours?', 'promenade', 'hameau', 'faubourg',
    'ilot', 'berges?', 'via', 'cit[ée]', 'sent(e|ier)', 'rond[- ][Pp]oint',
    'pas(se)?', 'carrefour', 'traverse', 'giratoire', 'esplanade', 'voie',
    'chauss[ée]e',
]
TYPES_REGEX = '|'.join(
    map(lambda x: '[{}{}]{}'.format(x[0], x[0].upper(), x[1:]), TYPES)
)


def _clean_query(q):
    q = re.sub('c(e|é)dex ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub('bp ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub('cs ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub('\d{,2}(e|[eè]me) ([eé]tage)', '', q, flags=re.IGNORECASE)
    q = re.sub(' {2,}', ' ', q, flags=re.IGNORECASE)
    q = re.sub('[ -]s/[ -]', ' sur ', q, flags=re.IGNORECASE)
    q = q.strip()
    return q
clean_query = yielder(_clean_query)


def _extract_address(q):
    m = extract_address_pattern.search(q)
    return m.group() if m else q
extract_address_pattern = re.compile(
    '(\d+( *(bis|ter))?,? +(' + TYPES_REGEX + ') .*(\d{5})?).*',
    flags=re.IGNORECASE)
extract_address = yielder(_extract_address)


def _glue_ordinal(q):
    """Glue '3' and 'bis'."""
    return glue_ordinal_pattern.sub('\g<1>\g<2>\g<3>', q)
ORDINAL_REGEX = 'bis|ter|quater|quinquies|sexies|[a-z]'
glue_ordinal_pattern = re.compile('(\d{1,4}) (' + ORDINAL_REGEX + ')\\b($|(?:,? (' + TYPES_REGEX + ')))',  # noqa
                                  flags=re.IGNORECASE)
glue_ordinal = yielder(_glue_ordinal)


def _fold_ordinal(s):
    """3bis => 3b."""
    if s not in _CACHE:
        rules = (
            ("(\d{1,4})bis\\b", "\g<1>b"),
            ("(\d{1,4})ter\\b", "\g<1>t"),
            ("(\d{1,4})quater\\b", "\g<1>q"),
            ("(\d{1,4})quinquies\\b", "\g<1>c"),
            ("(\d{1,4})sexies\\b", "\g<1>s"),
        )
        _s = s
        for pattern, repl in rules:
            _s = re.sub(pattern, repl, _s, flags=re.IGNORECASE)
        _CACHE[s] = _s
    return _CACHE[s]
_CACHE = {}
fold_ordinal = yielder(_fold_ordinal)
