import os
import sys
from functools import wraps
from importlib import import_module
from math import asin, cos, exp, radians, sin, sqrt
from multiprocessing.pool import RUN, IMapUnorderedIterator, Pool

from progressist import ProgressBar

from addok.config import config

PYTHON_VERSION = sys.version_info


def load_file(filepath):
    with open(filepath) as f:
        for line in f:
            yield line


def load_msgpack_file(filepath):
    import msgpack  # We don't want to make it a required dependency.
    with open(filepath, mode='rb') as f:
        for line in msgpack.Unpacker(f, encoding='utf-8'):
            yield line


def iter_pipe(pipe, processors):
    """Allow for iterators to return either an item or an iterator of items."""
    if isinstance(pipe, str):
        pipe = [pipe]
    for it in processors:
        pipe = it(pipe)
    yield from pipe


def import_by_path(path):
    """
    Import functions or class by their path. Should be of the form:
    path.to.module.func
    """
    if not isinstance(path, str):
        return path
    module_path, *name = path.rsplit('.', 1)
    func = import_module(module_path)
    if name:
        func = getattr(func, name[0])
    return func


def yielder(func):
    @wraps(func)
    def wrapper(pipe):
        for item in pipe:
            yield func(item)
    return wrapper


def haversine_distance(point1, point2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    """
    lat1, lon1 = point1
    lat2, lon2 = point2

    # Convert decimal degrees to radians.
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula.
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # 6367 km is the radius of the Earth.
    km = 6367 * c
    return km


def km_to_score(km):
    # Score between 0 and 0.1 (close to 0 km will be close to 0.1, and 100 and
    # above will be 0).
    return 0.0 if km > 100 else .1 * exp(-(km / 50.0) ** 2)


COLORS = {
    'red': '31',
    'green': '32',
    'yellow': '33',
    'blue': '34',
    'magenta': '35',
    'cyan': '36',
    'white': '37',
    'reset': '39'
}


def colorText(s, color):
    # color should be a string from COLORS
    return '\033[%sm%s\033[%sm' % (COLORS[color], s, COLORS['reset'])


def red(s):
    return colorText(s, 'red')


def green(s):
    return colorText(s, 'green')


def yellow(s):
    return colorText(s, 'yellow')


def blue(s):
    return colorText(s, 'blue')


def magenta(s):
    return colorText(s, 'magenta')


def cyan(s):
    return colorText(s, 'cyan')


def white(s):
    return colorText(s, 'white')


class Bar(ProgressBar):
    animation = '{spinner}'
    template = '{prefix} {animation} Done: {done} | Elapsed: {elapsed}'


class ChunkedPool(Pool):

    def imap_unordered(self, func, iterable, chunksize):
        """Customized version of imap_unordered.

        Directly send chunks to func, instead of iterating in each process and
        sending one by one.

        Original:
        https://hg.python.org/cpython/file/tip/Lib/multiprocessing/pool.py#l271

        Other tried options:
        - map_async: makes a list(iterable), so it loads all the data for each
          process into RAM
        - apply_async: needs manual chunking
        """
        assert self._state == RUN
        task_batches = Pool._get_tasks(func, iterable, chunksize)
        result = IMapUnorderedIterator(self if PYTHON_VERSION >= (3, 8) else self._cache)
        tasks = ((result._job, i, func, chunk, {})
                 for i, (_, chunk) in enumerate(task_batches))
        self._taskqueue.put((tasks, result._set_length))
        return result


def parallelize(func, iterable, chunk_size, **bar_kwargs):
    bar = Bar(prefix='Processing…', **bar_kwargs)
    with ChunkedPool(processes=config.BATCH_WORKERS) as pool:
        for chunk in pool.imap_unordered(func, iterable, chunk_size):
            bar(step=len(chunk))
        bar.finish()
