import json
import os.path
import sys

from addok import config
from addok.helpers import iter_pipe, yielder, parallelize
from addok.helpers.index import deindex_document, index_document


def run(args):
    if args.filepath:
        for path in args.filepath:
            process_file(path)
    elif not sys.stdin.isatty():  # Any better way to check for stdin?
        process_stdin(sys.stdin)


def register_command(subparsers):
    parser = subparsers.add_parser('batch', help='Batch import documents')
    parser.add_argument('filepath', nargs='*',
                        help='Path to file to process')
    parser.set_defaults(func=run)


def preprocess_batch(d):
    config.INDEX_EDGE_NGRAMS = False  # Run command "ngrams" instead.
    return iter_pipe(d, config.BATCH_PROCESSORS)


def process_file(filepath):
    print('Import from file', filepath)
    _, ext = os.path.splitext(filepath)
    if ext == '.msgpack':
        import msgpack  # We don't want to make it a required dependency.
        with open(filepath, mode='rb') as f:
            batch(preprocess_batch(msgpack.Unpacker(f, encoding='utf-8')))
    else:
        with open(filepath) as f:
            batch(preprocess_batch(f))


def process_stdin(stdin):
    print('Import from stdin')
    batch(preprocess_batch(stdin))


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
        index_document(doc)


def batch(iterable):
    parallelize(process, iterable, prefix='Importing…', chunk_size=20000,
                throttle=500)
