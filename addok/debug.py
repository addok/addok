from .core import DB, preprocess


def doc_by_id(_id):
    return DB.hgetall(_id)


def indexed_string(s):
    return list(preprocess(s))
