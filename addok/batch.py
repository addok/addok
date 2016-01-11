import json
import sys
import time
from multiprocessing import Pool

from addok import config, hooks
from addok.index_utils import deindex_document, index_document
from addok.utils import import_by_path, iter_pipe, yielder

BATCH_PROCESSORS = []


def on_load():
    BATCH_PROCESSORS.extend([import_by_path(path)
                             for path in config.BATCH_PROCESSORS])


config.on_load(on_load)


def run(args):
    if args.filepath:
        for path in args.filepath:
            process_file(path)
    elif not sys.stdin.isatty():  # Any better way to check for stdin?
        process_stdin(sys.stdin)


@hooks.register
def addok_register_command(subparsers):
    parser = subparsers.add_parser('batch', help='Batch import documents')
    parser.add_argument('filepath', nargs='*',
                        help='Path to file to process')
    parser.set_defaults(func=run)


def preprocess_batch(d):
    return list(iter_pipe(d, BATCH_PROCESSORS))[0]


def process_file(filepath):
    print('Import from file', filepath)
    with open(filepath) as f:
        batch(map(preprocess_batch, f))


def process_stdin(stdin):
    print('Import from stdin')
    batch(map(preprocess_batch, stdin))


@yielder
def to_json(row):
    try:
        return json.loads(row)
    except ValueError:
        return None


def process(doc):
    if doc.get('_action') in ['delete', 'update']:
        deindex_document(doc['id'])
    if doc.get('_action') in ['index', 'update', None]:
        index_document(doc, update_ngrams=False)


def batch(iterable):
    start = time.time()
    pool = Pool()
    count = 0
    chunk = []
    for doc in iterable:
        if not doc:
            continue
        chunk.append(doc)
        count += 1
        if count % 10000 == 0:
            pool.map(process, chunk)
            print("Done", count, time.time() - start)
            chunk = []
    if chunk:
        pool.map(process, chunk)
    pool.close()
    pool.join()
    print('Done', count, 'in', time.time() - start)
