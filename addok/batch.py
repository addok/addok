import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from progressist import ProgressBar

from addok import config
from addok.helpers import iter_pipe, yielder
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
    return list(iter_pipe(d, config.BATCH_PROCESSORS))[0]


def process_file(filepath):
    print('Import from file', filepath)
    config.INDEX_EDGE_NGRAMS = False  # Run command "ngrams" instead.
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
        index_document(doc)


class Bar(ProgressBar):
    animation = '{spinner}'
    template = 'Importing… {animation} Done: {done} | Elapsed: {elapsed}'
    throttle = 100


def batch(iterable):
    bar = Bar()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        count = 0
        chunk = []
        for item in iterable:
            if not item:
                continue
            chunk.append(item)
            count += 1
            if count % 20000 == 0:
                for r in executor.map(process, chunk):
                    bar()
                chunk = []
        if chunk:
            for r in executor.map(process, chunk):
                bar()
        bar.finish()
