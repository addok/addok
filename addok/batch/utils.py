import time
from multiprocessing import Pool

from addok.index_utils import index_document, deindex_document


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
