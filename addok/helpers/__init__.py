import csv
import os
import pickle
import sys
from functools import wraps
from importlib import import_module
from math import asin, cos, exp, radians, sin, sqrt
from multiprocessing import get_context
from multiprocessing.pool import RUN, IMapUnorderedIterator, Pool
from types import FunctionType, ModuleType

from progressist import ProgressBar

from addok.config import config

PYTHON_VERSION = sys.version_info


def load_file(filepath):
    with open(filepath) as f:
        for line in f:
            yield line


def load_msgpack_file(filepath):
    import msgpack  # We don't want to make it a required dependency.

    with open(filepath, mode="rb") as f:
        for line in msgpack.Unpacker(f, encoding="utf-8"):
            yield line


def load_csv_file(filepath):
    with open(filepath, newline="") as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.DictReader(csvfile, dialect=dialect)
        yield from reader


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
    module_path, *name = path.rsplit(".", 1)
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
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # 6367 km is the radius of the Earth.
    km = 6367 * c
    return km


def km_to_score(km):
    # Score between 0 and 0.1 (close to 0 km will be close to 0.1, and 100 and
    # above will be 0).
    return 0.0 if km > 100 else exp(-((km / 50.0) ** 2))


COLORS = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "reset": "39",
}


def colorText(s, color):
    # color should be a string from COLORS
    return "\033[%sm%s\033[%sm" % (COLORS[color], s, COLORS["reset"])


def red(s):
    return colorText(s, "red")


def green(s):
    return colorText(s, "green")


def yellow(s):
    return colorText(s, "yellow")


def blue(s):
    return colorText(s, "blue")


def magenta(s):
    return colorText(s, "magenta")


def cyan(s):
    return colorText(s, "cyan")


def white(s):
    return colorText(s, "white")


class Bar(ProgressBar):
    animation = "{spinner}"
    template = "{prefix} {animation} Done: {done} | Elapsed: {elapsed}"


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
        result = IMapUnorderedIterator(
            self if PYTHON_VERSION >= (3, 8) else self._cache
        )
        tasks = (
            (result._job, i, func, chunk, {})
            for i, (_, chunk) in enumerate(task_batches)
        )
        self._taskqueue.put((tasks, result._set_length))
        return result


def _get_config_overrides():
    """Extract configuration values that differ from defaults.

    Returns:
        Dict of config keys and their overridden values (only simple serializable types).
    """
    # Import here to avoid circular dependencies
    from addok.config import default as default_config

    # Only propagate uppercase config keys (actual settings, not methods)
    overrides = {}
    for key in config.keys():
        if not key.isupper():
            continue

        current_value = config.get(key)
        default_value = getattr(default_config, key, None)

        # Skip if values are the same
        if current_value == default_value:
            continue

        # Skip non-serializable types (functions, classes, modules)
        if isinstance(current_value, (FunctionType, type, ModuleType)):
            continue

        # Skip lists/dicts containing functions or classes
        if isinstance(current_value, (list, tuple)):
            if any(isinstance(item, (FunctionType, type, ModuleType)) for item in current_value):
                continue
        elif isinstance(current_value, dict):
            if any(isinstance(v, (FunctionType, type, ModuleType)) for v in current_value.values()):
                continue

        # Test if value is pickle-serializable
        try:
            pickle.dumps(current_value)
            overrides[key] = current_value
        except (pickle.PicklingError, TypeError, AttributeError):
            # Skip values that can't be pickled
            pass

    return overrides


def _worker_init(redis_params, config_env_vars=None, config_overrides=None):
    """Initialize Redis connection in worker processes for multiprocessing.

    This is required for spawn context where the connection object doesn't
    get properly inherited by child processes.

    Args:
        redis_params: Dict with Redis connection parameters (host, port, db, etc.)
        config_env_vars: Dict of environment variables to set for configuration
        config_overrides: Dict of config values to override after loading
    """
    # Import here to avoid circular dependencies and ensure fresh imports in spawned processes
    from addok import ds
    from addok.config import config as addok_config
    from addok.db import DB

    # Set environment variables for configuration
    if config_env_vars:
        for key, value in config_env_vars.items():
            if value is not None:
                os.environ[key] = str(value)

    # Force reload of config in worker process
    if not addok_config.loaded:
        addok_config.load()

    # Apply config overrides (for test monkeypatching)
    if config_overrides:
        for key, value in config_overrides.items():
            addok_config[key] = value

    # Connect to Redis with provided parameters
    DB.connect(**redis_params['indexes'])

    # Also connect document store if using Redis
    if 'documents' in redis_params and redis_params.get('use_redis_documents'):
        ds._DB.connect(**redis_params['documents'])


def parallelize(func, iterable, chunk_size, **bar_kwargs):
    """Execute func on iterable chunks using multiprocessing.

    Uses 'spawn' context on macOS for fork-safety, 'fork' on Linux for speed.
    """
    # Import here to avoid circular dependencies
    from addok.db import get_redis_params

    bar = Bar(prefix="Processing…", **bar_kwargs)

    # Prepare worker initialization parameters
    redis_params = get_redis_params()
    config_env_vars = {'ADDOK_CONFIG_MODULE': os.environ.get('ADDOK_CONFIG_MODULE')} if 'ADDOK_CONFIG_MODULE' in os.environ else {}
    config_overrides = _get_config_overrides()

    # Use 'spawn' on macOS for fork-safety, 'fork' on Linux for performance
    context = get_context('spawn' if sys.platform == 'darwin' else 'fork')

    with ChunkedPool(
        processes=config.BATCH_WORKERS,
        initializer=_worker_init,
        initargs=(redis_params, config_env_vars, config_overrides),
        context=context
    ) as pool:
        for chunk in pool.imap_unordered(func, iterable, chunk_size):
            bar(step=len(chunk))
        bar.finish()
