from . import config
from .utils import import_by_path


PROCESSORS = [import_by_path(path) for path in config.PROCESSORS]
QUERY_PROCESSORS = [import_by_path(path) for path in config.QUERY_PROCESSORS]


def _preprocess(pipe, processors):
    if isinstance(pipe, str):
        pipe = [pipe]
    for it in processors:
        pipe = it(pipe)
    yield from pipe


_CACHE = {}


def preprocess(s):
    if not s in _CACHE:
        _CACHE[s] = list(_preprocess(s, PROCESSORS))
    return _CACHE[s]


def preprocess_query(s):
    return list(_preprocess(s, QUERY_PROCESSORS + PROCESSORS))
