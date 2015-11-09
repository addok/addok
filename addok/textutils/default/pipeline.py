from addok.utils import yielder

from . import normalize as _normalize
from . import synonymize as _synonymize
from . import tokenize as _tokenize


def tokenize(pipe):
    for text in pipe:
        for token in _tokenize(text):
            yield token


normalize = yielder(_normalize)
synonymize = yielder(_synonymize)
