import json
import os.path
import sys
from datetime import timedelta

import redis

from addok.config import config
from addok.db import DB
from addok.ds import get_document
from addok.helpers import iter_pipe, keys, parallelize, yielder
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
    if not os.path.exists(filepath):
        sys.stderr.write('File not found: {}'.format(filepath))
        sys.exit(1)
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


def process_documents(docs):
    pipe = DB.pipeline(transaction=False)
    for doc in iter_pipe(docs, config.DOCUMENT_PROCESSORS):
        if doc.get('_action') in ['delete', 'update']:
            key = keys.document_key(doc['id']).encode()
            known_doc = get_document(key)
            if known_doc:
                deindex_document(known_doc)
        if doc.get('_action') in ['index', 'update', None]:
            index_document(pipe, doc)
    try:
        pipe.execute()
    except redis.RedisError as e:
        msg = 'Error while importing document:\n{}\n{}'.format(doc, str(e))
        raise ValueError(msg)
    return docs


def batch(iterable):
    parallelize(process_documents, iterable,
                chunk_size=config.BATCH_CHUNK_SIZE,
                throttle=timedelta(seconds=1))
