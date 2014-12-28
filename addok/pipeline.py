from . import config
from .utils import import_by_path


PIPELINE = [import_by_path(path) for path in config.PIPELINE]


def _preprocess(pipe):
    if isinstance(pipe, str):
        pipe = [pipe]
    for it in PIPELINE:
        pipe = it(pipe)
    yield from pipe


_CACHE = {}


def preprocess(s):
    if not s in _CACHE:
        _CACHE[s] = list(_preprocess(s))
    return _CACHE[s]
