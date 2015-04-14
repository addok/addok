"""Import data."""
from addok import config
from addok.utils import import_by_path, iter_pipe
from .utils import batch

BATCH_PROCESSORS = [import_by_path(path) for path in config.BATCH_PROCESSORS]


def preprocess_batch(d):
    return list(iter_pipe(d, BATCH_PROCESSORS))[0]


def preprocess_nominatim():
    # Do not import at load time, because we don't want to have a hard
    # dependency to psycopg2, which is imported on nominatim module.
    NOMINATIM_PROCESSORS = [import_by_path(path) for path in config.NOMINATIM_PROCESSORS]  # noqa
    return iter_pipe(None, NOMINATIM_PROCESSORS)


def process_file(filepath):
    with open(filepath) as f:
        batch(map(preprocess_batch, f))


def process_stdin(stdin):
    print('Import from stdin')
    batch(map(preprocess_batch, stdin))


def process_nominatim():
    batch(preprocess_nominatim())
