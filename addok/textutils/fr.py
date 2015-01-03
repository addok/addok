import re

from addok.utils import yielder


_CACHE = {}


def _stemmize(s):
    """Very lite French stemming. Try to remove every letter that is not
    significant."""
    if not s in _CACHE:
        rules = (
            ("(?<=[^g])g(?=[eyi])", "j"),
            ("(?<=g)u(?=[aeio])", ""),
            ("c(?=[^hieyw])", "k"),
            ("((?<=[^s])ch|c)$", "k"),  # final "c", "ch", but not "sch".
            ("(?<=[aeiouy])s(?=[aeiouy])", "z"),
            ("qu?", "k"),
            ("cc(?=[ie])", "s"),  # Others will hit the c => k and deduplicate
            ("ck", "k"),
            ("ph", "f"),
            ("th$", "te"),  # This t sounds.
            ("(?<=[^sc])h", ""),
            ("^h", ""),
            ("sc", "s"),
            ("sh", "ch"),
            ("w", "v"),
            ("c(?=[eiy])", "s"),
            ("y", "i"),
            ("esn", "en"),
            ("oe(?=\\w)", "e"),
            ("s$", ""),
            ("(?<=u)l?x$", ""),  # eaux, eux, aux, aulx
            ("(?<=u)lt$", "t"),
            ("(?<=\\w)[dg]$", ""),
            ("(?<=[^es])t$", ""),
            ("(?<=[aeiou])(m)(?=[pbgf])", "n"),
            ("(?<=\\w\\w)(e$)", ""),  # Remove "e" at last position only if it
                                      # follows two letters?
            ("(\\D)(?=\\1)", ""),  # Remove duplicate letters.
        )
        _s = s
        for pattern, repl in rules:
            _s = re.sub(pattern, repl, _s)
        _CACHE[s] = _s
    return _CACHE[s]

stemmize = yielder(_stemmize)


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


def _clean_query(q):
    q = re.sub('c(e|é)dex ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub('bp ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub('cs ?[\d]*', '', q, flags=re.IGNORECASE)
    q = re.sub(' {2,}', ' ', q, flags=re.IGNORECASE)
    q = q.strip()
    return q
clean_query = yielder(_clean_query)


def _extract_address(q):
    m = extract_address_pattern.search(q)
    return m.group() if m else q
extract_address_pattern = re.compile(
    '(\d*( ?(bis|ter))?(,? )?(' + TYPES_REGEX + ') .*(\d{5})?).*',
    flags=re.IGNORECASE)
extract_address = yielder(_extract_address)
