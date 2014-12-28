import re
from pathlib import Path


from ngram import NGram
from unidecode import unidecode


letters = 'abcdefghijklmnopqrstuvwxyz'


def make_fuzzy(word, max=1):
    """Naive neighborhoods algo."""
    # inversions
    neighbors = []
    for i in range(0, len(word) - 1):
        neighbor = list(word)
        neighbor[i], neighbor[i+1] = neighbor[i+1], neighbor[i]
        neighbors.append(''.join(neighbor))
    # insertions
    for letter in letters:
        for i in range(0, len(word) + 1):
            neighbor = list(word)
            neighbor.insert(i, letter)
            neighbors.append(''.join(neighbor))
    # substitutions
    for letter in letters:
        for i in range(0, len(word)):
            neighbor = list(word)
            neighbor[i] = letter
            neighbors.append(''.join(neighbor))
    return neighbors


def compare_ngrams(left, right, N=2, pad_len=0):
    left = alphanumerize(unidecode(left.lower()))
    right = alphanumerize(unidecode(right.lower()))
    return NGram.compare(left, right, N=N, pad_len=pad_len)


def tokenize(text, lang="fr"):
    """Split text into a list of tokens."""
    if lang == "fr":
        pattern = r"[\w]+"
    else:
        raise NotImplementedError
    return re.compile(pattern, re.U | re.X).findall(text)


def normalize(text, lang="fr"):
    if lang == "fr":
        return synonymize(unidecode(text.lower()))
    else:
        raise NotImplementedError


def alphanumerize(text):
    return re.sub(' {2,}', ' ', re.sub('[^\w]', ' ', text))


SYNONYMS = {}


def load_synonyms():
    directory = Path(__file__).parent
    with directory.joinpath('resources/synonyms.txt').open() as f:
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


def synonymize(token):
    return SYNONYMS.get(token, token)
