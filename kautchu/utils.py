import re

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
        return unidecode(text.lower())
    else:
        raise NotImplementedError


def alphanumerize(text):
    return re.sub(' {2,}', ' ', re.sub('[^\w]', ' ', text))
