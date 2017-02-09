import re
from pathlib import Path

from ngram import NGram
from unidecode import unidecode

from addok.config import config
from addok.db import DB
from addok.helpers import keys, yielder
from addok.helpers.index import token_frequency

PATTERN = re.compile(r"[\w]+", re.U | re.X)


class Token(str):

    __slots__ = ('position', 'is_last', 'db_key', 'raw', '_frequency', '_key',
                 'kind')

    def __new__(cls, value, position=0, is_last=False, raw=None, kind=None):
        obj = str.__new__(cls, value)
        obj.position = position
        obj.is_last = is_last
        obj.db_key = None
        obj.raw = raw or value  # Allow to keep raw on update.
        obj.kind = kind
        return obj

    def __repr__(self):
        return '<Token {}>'.format(self)

    def update(self, value, **kwargs):
        default = dict(position=self.position, is_last=self.is_last,
                       raw=self.raw, kind=self.kind)
        default.update(kwargs)
        token = Token(value=value, **default)
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


SYNONYMS = {}


@config.on_load
def load_synonyms():
    path = config.SYNONYMS_PATH
    if not path:
        return
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
                SYNONYMS[synonym] = wanted


def _synonymize(t):
    return t.update(SYNONYMS.get(t, t))
synonymize = yielder(_synonymize)


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


def compare_ngrams(left, right, N=2, pad_len=0):
    left = ascii(left)
    right = ascii(right)
    if len(left) == 1 and len(right) == 1:
        # NGram.compare returns 0.0 for 1 letter comparison, even if letters
        # are equal.
        return 1.0 if left == right else 0.0
    return NGram.compare(left, right, N=N, pad_len=pad_len)


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
