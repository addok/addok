import re
from functools import lru_cache
from pathlib import Path

from unidecode import unidecode

from addok.config import config
from addok.db import DB
from addok.helpers import keys, yielder
from addok.helpers.index import token_frequency

import editdistance

PATTERN = re.compile(r"[\w]+", re.U | re.X)


class Token(str):

    __slots__ = ('_positions', 'is_last', 'db_key', 'raw', '_frequency',
                 '_key', 'kind', 'is_first')

    def __new__(cls, value, position=None, is_last=False, raw=None, kind=None):
        obj = str.__new__(cls, value)
        obj._positions = []
        position = position or 0
        obj.position = position
        obj.is_first = obj.position[0] == 0
        obj.is_last = is_last
        obj.db_key = None
        obj.raw = raw or value  # Allow to keep raw on update.
        obj.kind = kind
        return obj

    def __repr__(self):
        return '<Token {}>'.format(self)

    def update(self, value, **kwargs):
        default = dict(is_last=self.is_last, raw=self.raw, kind=self.kind,
                       position=self.position[:])
        # Never replace position through `update`.
        position = kwargs.pop('position', None)
        default.update(kwargs)
        token = Token(value=value, **default)
        if position is not None:
            token.position = position
        return token

    def search(self):
        if DB.exists(self.key):
            self.db_key = self.key

    @property
    def is_common(self):
        return self.frequency > config.COMMON_THRESHOLD

    @property
    def frequency(self):
        if not hasattr(self, '_frequency'):
            self._frequency = token_frequency(self)
        return self._frequency

    @property
    def key(self):
        if not hasattr(self, '_key'):
            self._key = keys.token_key(self)
        return self._key

    @property
    def position(self):
        # Allow to store multiple positions when a token is subdivided.
        return self._positions

    @position.setter
    def position(self, position):
        if isinstance(position, list):
            self._positions = position
        else:
            self._positions.append(position)


def _tokenize(text):
    """Split text into a list of tokens."""
    return PATTERN.findall(text)


def tokenize(pipe):
    for text in pipe:
        for position, token in enumerate(_tokenize(text)):
            yield Token(token, position=position)


def _normalize(s):
    return s.update(unidecode(s.lower()))
normalize = yielder(_normalize)


@config.on_load
def load_synonyms():
    config.SYNONYMS = {}
    path = config.SYNONYMS_PATH
    if not path:
        return  # pragma: no cover
    with Path(path).open() as f:
        for line in f:
            if line.startswith('#'):
                continue
            synonyms, wanted = line.split('=>')
            wanted = wanted.strip()
            synonyms = synonyms.split(',')
            for synonym in synonyms:
                synonym = synonym.strip()
                if not synonym:
                    continue
                config.SYNONYMS[synonym] = wanted


def synonymize(tokens):
    for token in tokens:
        for position, subtoken in enumerate(config.SYNONYMS.get(token, token).split()):
            yield token.update(subtoken, position=position)


class ascii(str):
    """Just like a str, but ascii folded and cached."""

    __slots__ = ['_cache', '_raw']

    def __new__(cls, value):
        try:
            cache = value._cache
        except AttributeError:
            cache = alphanumerize(unidecode(value.lower()))
        obj = str.__new__(cls, cache)
        obj._cache = cache
        obj._raw = getattr(value, '_raw', value)
        return obj

    def __str__(self):
        return self._raw


@lru_cache(maxsize=512)
def ngrams(text, n=2):
    text = alphanumerize(' '+text+'$')
    return set([text[i:i+n] for i in range(0, len(text)-(n-1))])


def compare_str(left, right):
    left_n = ngrams(left)
    right_n = ngrams(right)
    distance = editdistance.eval(left, right) / 1000
    return len(list(left_n & right_n)) / len(list(left_n | right_n)) - distance


def contains(candidate, target):
    candidate = ascii(candidate)
    target = ascii(target)
    return candidate in target


def startswith(candidate, target):
    candidate = ascii(candidate)
    target = ascii(target)
    return target.startswith(candidate)


def equals(candidate, target):
    candidate = ascii(candidate)
    target = ascii(target)
    return target == candidate


def alphanumerize(text):
    return re.sub(' {2,}', ' ', re.sub('[^\w]', ' ', text))


def compute_edge_ngrams(token, min=None):
    """Compute edge ngram of token from min. Does not include token itself."""
    if min is None:
        min = config.MIN_EDGE_NGRAMS
    token = token[:config.MAX_EDGE_NGRAMS + 1]
    return [token[:i] for i in range(min, len(token))]


class EntityTooLarge(ValueError):
    pass


@yielder
def check_query_length(q):
    if len(q) > config.QUERY_MAX_LENGTH:
        raise EntityTooLarge('Query too long, {} chars, limit is {}'.format(
            len(q), config.QUERY_MAX_LENGTH))
    return q


@yielder
def flag_housenumber(token):
    """Very basic housenumber flagging. Make your own for your specific needs.
    Eg. in addok-france:
    https://github.com/addok/addok-france/blob/master/addok_france/utils.py#L106
    """
    if token.is_first and token.isdigit():
        token.kind = 'housenumber'
    return token
