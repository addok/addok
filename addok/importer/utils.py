import time
from multiprocessing import Pool

from addok.index_utils import index_document


def index_doc(doc):
    index_document(doc, update_ngrams=False)


def iter_import(iterable):
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
            pool.map(index_doc, chunk)
            print("Done", count, time.time() - start)
            chunk = []
    if chunk:
        pool.map(index_doc, chunk)
    pool.close()
    pool.join()
    print('Done', count, 'in', time.time() - start)
