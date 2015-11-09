import re

from ngram import NGram
from unidecode import unidecode

from ... import config


PATTERN = re.compile(r"[\w]+", re.U | re.X)


def tokenize(text):
    """Split text into a list of tokens."""
    return PATTERN.findall(text)


def normalize(s):
    return unidecode(s.lower())


SYNONYMS = {}


def load_synonyms():
    with config.RESOURCES_ROOT.joinpath(config.SYNONYMS_PATH).open() as f:
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
load_synonyms()


def synonymize(s):
    return SYNONYMS.get(s, s)


letters = 'abcdefghijklmnopqrstuvwxyz'


def make_fuzzy(word, max=1):
    """Naive neighborhoods algo."""
    # inversions
    neighbors = []
    for i in range(0, len(word) - 1):
        neighbor = list(word)
        neighbor[i], neighbor[i+1] = neighbor[i+1], neighbor[i]
        neighbors.append(''.join(neighbor))
    # substitutions
    for letter in letters:
        for i in range(0, len(word)):
            neighbor = list(word)
            if letter != neighbor[i]:
                neighbor[i] = letter
                neighbors.append(''.join(neighbor))
    # insertions
    for letter in letters:
        for i in range(0, len(word) + 1):
            neighbor = list(word)
            neighbor.insert(i, letter)
            neighbors.append(''.join(neighbor))
    if len(word) > 3:
        # removal
        for i in range(0, len(word)):
            neighbor = list(word)
            del neighbor[i]
            neighbors.append(''.join(neighbor))
    return neighbors


class ascii(str):
    """Just like a str, but ascii folded and cached."""

    def __new__(cls, value):
        try:
            cache = value._cache
        except AttributeError:
            cache = alphanumerize(unidecode(value.lower()))
        obj = str.__new__(cls, cache)
        obj._cache = cache
        return obj


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
    """Compute edge ngram of token from min. Does not includes token itself."""
    if min is None:
        min = config.MIN_EDGE_NGRAMS
    token = token[:config.MAX_EDGE_NGRAMS + 1]
    return [token[:i] for i in range(min, len(token))]
