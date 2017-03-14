import json
import os.path
import sys
from datetime import timedelta

from addok.config import config
from addok.db import DB
from addok.ds import DS
from addok.helpers import iter_pipe, parallelize, yielder


def run(args):
    if args.filepath:
        for path in args.filepath:
            process_file(path)
    elif not sys.stdin.isatty():  # Any better way to check for stdin?
        process_stdin(sys.stdin)


def reset(args):
    if args.force or input('Type "yes" to delete ALL data: ') == 'yes':
        DB.flushdb()
        DS.flushdb()
        print('All data has been deleted.')
    else:
        print('Nothing has been deleted.')


def register_command(subparsers):
    parser = subparsers.add_parser('import', help='Load documents')
    parser.add_argument('filepath', nargs='*',
                        help='Path to file to process')
    parser.set_defaults(func=run)
    parser = subparsers.add_parser('reset',
                                   help='Delete ALL indexes and documents')
    parser.add_argument('--force', help='Do not ask for confirm',
                        action='store_true')
    parser.set_defaults(func=reset)


def process_file(filepath):
    print('Import from file', filepath)
    _, ext = os.path.splitext(filepath)
    if not os.path.exists(filepath):
        sys.stderr.write('File not found: {}'.format(filepath))
        sys.exit(1)
    config.INDEX_EDGE_NGRAMS = False  # Run command "ngrams" instead.
    load(config.IMPORT_FILE_LOADER(filepath))


def process_stdin(stdin):
    print('Import from stdin')
    load(stdin)


@yielder
def to_json(row):
    try:
        return json.loads(row)
    except ValueError:
        return None


def process_documents(*docs):
    return list(iter_pipe(docs, config.IMPORT_PROCESSORS))


def load(iterable):
    parallelize(process_documents, iterable,
                chunk_size=config.IMPORT_CHUNK_SIZE,
                throttle=timedelta(seconds=1))
